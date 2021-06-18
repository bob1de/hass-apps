"""
This module implements the dual thermostat actor.
"""

import typing as T

if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from ..room import Room

import functools
import voluptuous as vol

from ... import common
from .. import stats
from ..expression.helpers import HelperBase as ExpressionHelperBase
from .base import ActorBase
from .thermostat import Off, Temp

OFF = Off()


class DualTemp:
    """A class holding a temperature value."""

    def __init__(self, temp_value: T.Any) -> None:
        if isinstance(temp_value, DualTemp):
            # Just copy the value over.
            self.temp_low = temp_value.temp_low
            self.temp_high = temp_value.temp_high
            return
        else:
            parsed = self.parse_temp(temp_value)

        if parsed is None:
            raise ValueError("{} is no valid temperature".format(repr(temp_value)))

        if isinstance(parsed, Off):
            self.temp_low = OFF  # type: T.Union[float, Off]
            self.temp_high = OFF  # type: T.Union[float, Off]
        else:
            self.temp_low = parsed[0]  # type: T.Union[float, Off]
            self.temp_high = parsed[1]  # type: T.Union[float, Off]

    def __add__(self, other: T.Any) -> "DualTemp":
        # OFF + something is OFF
        if self.is_off or (isinstance(other, (Temp, DualTemp)) and other.is_off):
            return type(self)(OFF)

        if isinstance(other, (float, int)):
            return type(self)((self.temp_low + other, self.temp_high + other))
        if isinstance(other, list):
            return type(self)((self.temp_low + other[0], self.temp_high + other[1]))
        if isinstance(other, Temp):
            return type(self)((self.temp_low + other.value, self.temp_high + other.value))
        if isinstance(other, DualTemp):
            return type(self)((self.temp_low + other.temp_low, self.temp_high + other.temp_high))
        return NotImplemented

    def __eq__(self, other: T.Any) -> bool:
        if isinstance(other, type(self)):
            return (self.temp_low == other.temp_low) and (self.temp_high == other.temp_high)
        if isinstance(other, Temp):
            return (self.temp_low == other.value) and (self.temp_high == other.value)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(str(self))

    def __repr__(self) -> str:
        return "{}° - {}°".format(self.temp_low, self.temp_high)

    def serialize(self) -> str:
        """Converts the temperature into a string that Temp can be
        initialized with again later."""

        if self.is_off:
            return "OFF"
        return str("({},{})".format(self.temp_low, self.temp_high))

    @property
    def is_off(self) -> bool:
        """Tells whether this temperature means OFF."""

        return isinstance(self.temp_low, Off)

    @staticmethod
    def parse_temp(value: T.Any) -> T.Union[T.List[float], Off, None]:
        """Converts the given value to a valid temperature of type float
        or Off.
        If value is a string, all whitespace is removed first.
        If conversion is not possible, None is returned."""

        if isinstance(value, str):
            value = "".join(value.split())
            if value.upper() == "OFF":
                return OFF

        if isinstance(value, Off):
            return OFF

        if isinstance(value, (tuple, list)) and len(value) == 2 and \
           isinstance(value[0], (float, int)) and isinstance(value[1], (float, int)):
            return value

        return None


class ThermostatExpressionHelper(ExpressionHelperBase):
    """Adds Temp and OFF to the evaluation environment."""

    OFF = OFF
    DualTemp = DualTemp


TEMP_SCHEMA = vol.Schema(
    vol.All(
        vol.Any(list, tuple, Off, vol.All(str, lambda v: v.upper(), "OFF")),
        lambda v: DualTemp(v),  # pylint: disable=unnecessary-lambda
    )
)


class _DualTempDeltaParameter(stats.ActorValueCollectorMixin, stats.MinAvgMaxParameter):
    """The difference between target and current temperature."""

    config_schema_dict = {
        **stats.ActorValueCollectorMixin.config_schema_dict,
        **stats.MinAvgMaxParameter.config_schema_dict,
        vol.Optional("off_value", default=0): vol.Any(float, int, None),
    }
    round_places = 2
    attribute = None

    def collect_actor_value(self, actor: "DualThermostatActor") -> T.Optional[float]:
        """Collects the difference between target and current temperature."""

        assert isinstance(actor, DualThermostatActor)
        assert self.attribute is not None
        current = actor.current_temp
        target = actor.current_value
        if current is None or target is None or current.is_off or target.is_off:
            off_value = self.cfg["off_value"]
            if off_value is None:
                # thermostats that are off should be excluded
                return None
            return float(off_value)
        return float(getattr(target, self.attribute) - current)

    def initialize_actor_listeners(self, actor: ActorBase) -> None:
        """Listens for changes of current and target temperature."""

        self.log(
            "Listening for temperature changes of {} in {}.".format(actor, actor.room),
            level="DEBUG",
        )
        actor.events.on("current_temp_changed", self.update_handler)
        actor.events.on("value_changed", self.update_handler)


class HighTempDeltaParameter(_DualTempDeltaParameter):
    attribute = "temp_high"
    name = "temp_high_delta"


class LowTempDeltaParameter(_DualTempDeltaParameter):
    attribute = "temp_low"
    name = "temp_low_delta"


class DualThermostatActor(ActorBase):
    """A thermostat to be controlled by Schedy."""

    name = "dualthermostat"
    config_schema_dict = {
        **ActorBase.config_schema_dict,
        #TODO: Look into error when enabling this
        # "Configuration error: expected list for dictionary value @ data['delta']. Got None"
        # vol.Optional("delta", default=DualTemp([0, 0])): vol.All(TEMP_SCHEMA, vol.NotIn([DualTemp(OFF)])),
        vol.Optional("min_temp", default=None): vol.Any(
            vol.All(TEMP_SCHEMA, vol.NotIn([DualTemp(OFF)])), None
        ),
        vol.Optional("max_temp", default=None): vol.Any(
            vol.All(TEMP_SCHEMA, vol.NotIn([DualTemp(OFF)])), None
        ),
        vol.Optional("off_temp", default=OFF): TEMP_SCHEMA,
        vol.Optional("supports_hvac_modes", default=True): bool,
        vol.Optional("hvac_mode_on", default="heat_cool"): str,
        vol.Optional("hvac_mode_off", default="off"): str,
    }

    expression_helpers = ActorBase.expression_helpers + [ThermostatExpressionHelper]

    stats_param_types = [HighTempDeltaParameter, LowTempDeltaParameter]

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)
        self._current_temp = None  # type: T.Optional[Temp]

    def check_config_plausibility(self, state: dict) -> None:
        """Is called during initialization to warn the user about some
        possible common configuration mistakes."""

        if not state:
            self.log("Thermostat couldn't be found.", level="WARNING")
            return

        required_attrs = ["target_temp_high", "target_temp_low"]
        if self.cfg["supports_hvac_modes"]:
            required_attrs.append("state")
        for attr in required_attrs:
            if attr not in state:
                self.log(
                    "Thermostat has no attribute named {!r}. Available are {!r}. "
                    "Please check your config!".format(attr, list(state.keys())),
                    level="WARNING",
                )

        temp_attrs = ["temperature", "current_temperature"]
        for attr in temp_attrs:
            value = state.get(attr)
            try:
                value = float(value)  # type: ignore
            except (TypeError, ValueError):
                self.log(
                    "The value {!r} of attribute {!r} is not a valid dual temperature.".format(
                        value, attr
                    ),
                    level="WARNING",
                )

        allowed_hvac_modes = state.get("hvac_modes")
        if not self.cfg["supports_hvac_modes"]:
            if allowed_hvac_modes:
                self.log(
                    "HVAC mode support has been disabled, but the modes {!r} seem to "
                    "be supported. Maybe disabling it was a mistake?".format(
                        allowed_hvac_modes
                    ),
                    level="WARNING",
                )
            return

        if not allowed_hvac_modes:
            self.log(
                "Attributes for thermostat contain no 'hvac_modes', Consider "
                "disabling HVAC mode support.",
                level="WARNING",
            )
            return
        for hvac_mode in (self.cfg["hvac_mode_on"], self.cfg["hvac_mode_off"]):
            if hvac_mode not in allowed_hvac_modes:
                self.log(
                    "Thermostat doesn't seem to support the "
                    "HVAC mode {}, supported modes are: {}. "
                    "Please check your config!".format(hvac_mode, allowed_hvac_modes),
                    level="WARNING",
                )

    @property
    def current_temp(self) -> T.Optional[Temp]:
        """Returns the current temperature as measured by the thermostat."""

        return self._current_temp

    @staticmethod
    def deserialize_value(value: str) -> DualTemp:
        """Deserializes by calling validate_value()."""

        return DualThermostatActor.validate_value(value)

    def do_send(self) -> None:
        """Sends self._wanted_value to the thermostat."""

        target_temp = self._wanted_value  # type: DualTemp
        if target_temp.is_off:
            hvac_mode = self.cfg["hvac_mode_off"]
            temp = None
        else:
            hvac_mode = self.cfg["hvac_mode_on"]
            temp = target_temp
        if not self.cfg["supports_hvac_modes"]:
            hvac_mode = None

        self.log(
            "Setting temperature = {!r}, HVAC mode = {!r}.".format(
                "<unset>" if temp is None else temp,
                "<unset>" if hvac_mode is None else hvac_mode,
            ),
            level="DEBUG",
            prefix=common.LOG_PREFIX_OUTGOING,
        )
        if hvac_mode is not None:
            self.app.call_service(
                "climate/set_hvac_mode", entity_id=self.entity_id, hvac_mode=hvac_mode
            )
        if temp is not None:
            self.app.call_service(
                "climate/set_temperature",
                entity_id=self.entity_id,
                target_temp_low=temp.temp_low,
                target_temp_high=temp.temp_high,
            )

    def filter_set_value(self, value: DualTemp) -> T.Optional[DualTemp]:
        """Preprocesses the given target temperature for setting on this
        thermostat. This algorithm will try best to achieve the closest
        possible temperature supported by this particular thermostat.
        The return value is either the temperature to set or None,
        if nothing has to be sent."""

        if value.is_off:
            value = self.cfg["off_temp"]

        if not value.is_off:
            # value += self.cfg["delta"]

            if isinstance(self.cfg["min_temp"], DualTemp):
                if value.temp_low < self.cfg["min_temp"].temp_low:
                    value.temp_low = self.cfg["min_temp"].temp_low
                if value.temp_high < self.cfg["min_temp"].temp_high:
                    value.temp_high = self.cfg["min_temp"].temp_high

            if isinstance(self.cfg["max_temp"], DualTemp):
                if value.temp_low > self.cfg["max_temp"].temp_low:
                    value.temp_low = self.cfg["max_temp"].temp_low
                if value.temp_high > self.cfg["max_temp"].temp_high:
                    value.temp_high = self.cfg["max_temp"].temp_high

        elif not self.cfg["supports_hvac_modes"]:
            self.log(
                "Not turning off because it doesn't support HVAC modes.",
                level="WARNING",
            )
            self.log(
                "Consider defining an off_temp in the actor "
                "configuration for these cases.",
                level="WARNING",
            )
            return None

        return value

    def notify_state_changed(self, attrs: dict) -> T.Optional[DualTemp]:
        """Is called when the thermostat's state changes.
        This method fetches both the current and target temperature from
        the thermostat and reacts accordingly."""

        target_temp = None  # type: T.Optional[DualTemp]
        if self.cfg["supports_hvac_modes"]:
            hvac_mode = attrs.get("state")
            self.log(
                "Attribute 'state' is {}.".format(repr(hvac_mode)),
                level="DEBUG",
                prefix=common.LOG_PREFIX_INCOMING,
            )
            if hvac_mode == self.cfg["hvac_mode_off"]:
                target_temp = DualTemp(OFF)
            elif hvac_mode != self.cfg["hvac_mode_on"]:
                self.log(
                    "Unknown HVAC mode {!r}, ignoring thermostat.".format(hvac_mode),
                    level="ERROR",
                )
                return None

        if target_temp is None:
            target_temp = DualTemp((attrs.get("target_temp_low"), attrs.get("target_temp_high")))
            self.log(
                "Attribute 'temperature' is {}.".format(repr(target_temp)),
                level="DEBUG",
                prefix=common.LOG_PREFIX_INCOMING,
            )

        _current_temp = attrs.get("current_temperature")
        self.log(
            "Attribute 'current_temperature' is {}.".format(repr(_current_temp)),
            level="DEBUG",
            prefix=common.LOG_PREFIX_INCOMING,
        )
        if _current_temp is not None:
            try:
                current_temp = Temp(_current_temp)  # type: T.Optional[Temp]
            except ValueError:
                self.log(
                    "Invalid current temperature {!r}, not updating it.".format(
                        _current_temp
                    ),
                    level="ERROR",
                )
            else:
                if current_temp != self._current_temp:
                    self._current_temp = current_temp
                    self.events.trigger("current_temp_changed", self, current_temp)

        return target_temp

    @staticmethod
    def serialize_value(value: DualTemp) -> str:
        """Wrapper around Temp.serialize()."""

        if not isinstance(value, DualTemp):
            raise ValueError(
                "can only serialize Temp objects, not {}".format(repr(value))
            )
        return value.serialize()

    @staticmethod
    def validate_value(value: T.Any) -> DualTemp:
        """Ensures the given value is a valid temperature."""

        return DualTemp(value)
