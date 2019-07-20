"""
This module implements the thermostat actor.
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


# allowed types of values to initialize Temp() with
TempValueType = T.Union[float, int, str, "Off", "Temp"]


class Off:
    """A special value Temp() may be initialized with in order to turn
    a thermostat off."""

    def __add__(self, other: T.Any) -> "Off":
        return self

    def __eq__(self, other: T.Any) -> bool:
        return isinstance(other, Off)

    def __hash__(self) -> int:
        return hash(str(self))

    def __neg__(self) -> "Off":
        return self

    def __repr__(self) -> str:
        return "OFF"

    def __sub__(self, other: T.Any) -> "Off":
        return self


OFF = Off()


@functools.total_ordering
class Temp:
    """A class holding a temperature value."""

    def __init__(self, temp_value: T.Any) -> None:
        if isinstance(temp_value, Temp):
            # Just copy the value over.
            parsed = self.parse_temp(temp_value.value)
        else:
            parsed = self.parse_temp(temp_value)

        if parsed is None:
            raise ValueError("{} is no valid temperature".format(repr(temp_value)))

        self.value = parsed  # type: T.Union[float, Off]

    def __add__(self, other: T.Any) -> "Temp":
        if isinstance(other, (float, int)):
            other = type(self)(other)
        elif not isinstance(other, type(self)):
            raise TypeError(
                "can't add {} and {}".format(repr(type(self)), repr(type(other)))
            )

        # OFF + something is OFF
        if self.is_off or other.is_off:
            return type(self)(OFF)

        return type(self)(self.value + other.value)

    def __eq__(self, other: T.Any) -> bool:
        return isinstance(other, Temp) and self.value == other.value

    def __float__(self) -> float:
        if isinstance(self.value, float):
            return self.value
        raise ValueError("{} has no numeric value.".format(repr(self)))

    def __hash__(self) -> int:
        return hash(str(self))

    def __lt__(self, other: T.Any) -> bool:
        if isinstance(other, (float, int)):
            other = Temp(other)

        if type(self) is not type(other):
            raise TypeError(
                "can't compare {} and {}".format(repr(type(self)), repr(type(other)))
            )

        if not self.is_off and other.is_off:
            return False
        if self.is_off and not other.is_off or self.value < other.value:
            return True
        return False

    def __neg__(self) -> "Temp":
        return Temp(-self.value)  # pylint: disable=invalid-unary-operand-type

    def __repr__(self) -> str:
        if isinstance(self.value, (float, int)):
            return "{}°".format(self.value)
        return "{}".format(self.value)

    def __sub__(self, other: T.Any) -> "Temp":
        return self.__add__(-other)

    @property
    def is_off(self) -> bool:
        """Tells whether this temperature means OFF."""

        return isinstance(self.value, Off)

    @staticmethod
    def parse_temp(value: T.Any) -> T.Union[float, Off, None]:
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

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def serialize(self) -> str:
        """Converts the temperature into a string that Temp can be
        initialized with again later."""

        if self.is_off:
            return "OFF"
        return str(self.value)


class ThermostatExpressionHelper(ExpressionHelperBase):
    """Adds Temp and OFF to the evaluation environment."""

    OFF = OFF
    Temp = Temp


TEMP_SCHEMA = vol.Schema(
    vol.All(
        vol.Any(float, int, Off, vol.All(str, lambda v: v.upper(), "OFF")),
        lambda v: Temp(v),  # pylint: disable=unnecessary-lambda
    )
)


class TempDeltaParameter(stats.ActorValueCollectorMixin, stats.MinAvgMaxParameter):
    """The difference between target and current temperature."""

    name = "temp_delta"
    config_schema_dict = {
        **stats.ActorValueCollectorMixin.config_schema_dict,
        **stats.MinAvgMaxParameter.config_schema_dict,
        vol.Optional("off_value", default=0): vol.Any(float, int, None),
    }
    round_places = 2

    def collect_actor_value(self, actor: ActorBase) -> T.Optional[float]:
        """Collects the difference between target and current temperature."""

        assert isinstance(actor, ThermostatActor)
        current = actor.current_temp
        target = actor.current_value
        if current is None or target is None or current.is_off or target.is_off:
            off_value = self.cfg["off_value"]
            if off_value is None:
                # thermostats that are off should be excluded
                return None
            return float(off_value)
        return float(target - current)

    def initialize_actor_listeners(self, actor: ActorBase) -> None:
        """Listens for changes of current and target temperature."""

        self.log(
            "Listening for temperature changes of {} in {}.".format(actor, actor.room),
            level="DEBUG",
        )
        actor.events.on("current_temp_changed", self.update_handler)
        actor.events.on("value_changed", self.update_handler)


class ThermostatActor(ActorBase):
    """A thermostat to be controlled by Schedy."""

    name = "thermostat"
    config_schema_dict = {
        **ActorBase.config_schema_dict,
        vol.Optional("delta", default=0): vol.All(TEMP_SCHEMA, vol.NotIn([Temp(OFF)])),
        vol.Optional("min_temp", default=None): vol.Any(
            vol.All(TEMP_SCHEMA, vol.NotIn([Temp(OFF)])), None
        ),
        vol.Optional("max_temp", default=None): vol.Any(
            vol.All(TEMP_SCHEMA, vol.NotIn([Temp(OFF)])), None
        ),
        vol.Optional("off_temp", default=OFF): TEMP_SCHEMA,
        vol.Optional("supports_hvac_modes", default=True): bool,
        vol.Optional("hvac_mode_on", default="heat"): str,
        vol.Optional("hvac_mode_off", default="off"): str,
    }

    expression_helpers = ActorBase.expression_helpers + [ThermostatExpressionHelper]

    stats_param_types = [TempDeltaParameter]

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)
        self._current_temp = None  # type: T.Optional[Temp]

    def check_config_plausibility(self, state: dict) -> None:
        """Is called during initialization to warn the user about some
        possible common configuration mistakes."""

        if not state:
            self.log("Thermostat couldn't be found.", level="WARNING")
            return

        required_attrs = ["temperature"]
        if self.cfg["supports_hvac_modes"]:
            required_attrs.append("state")
        for attr in required_attrs:
            if attr not in state:
                self.log(
                    "Thermostat has no attribute named {}. "
                    "Available attributes are {}. "
                    "Please check your config!".format(repr(attr), list(state.keys())),
                    level="WARNING",
                )

        temp_attrs = ["temperature", "current_temperature"]
        for attr in temp_attrs:
            value = state.get(attr)
            try:
                value = float(value)  # type: ignore
            except (TypeError, ValueError):
                self.log(
                    "The value {} for attribute {} is no valid "
                    "temperature value. "
                    "Please check your config!".format(repr(value), repr(attr)),
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
    def deserialize_value(value: str) -> Temp:
        """Deserializes by calling validate_value()."""

        return ThermostatActor.validate_value(value)

    def do_send(self) -> None:
        """Sends self._wanted_value to the thermostat."""

        target_temp = self._wanted_value
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
                temperature=temp.value,
            )

    def filter_set_value(self, value: Temp) -> T.Optional[Temp]:
        """Preprocesses the given target temperature for setting on this
        thermostat. This algorithm will try best to achieve the closest
        possible temperature supported by this particular thermostat.
        The return value is either the temperature to set or None,
        if nothing has to be sent."""

        if value.is_off:
            value = self.cfg["off_temp"]

        if not value.is_off:
            value = value + self.cfg["delta"]
            if isinstance(self.cfg["min_temp"], Temp) and value < self.cfg["min_temp"]:
                value = self.cfg["min_temp"]
            elif (
                isinstance(self.cfg["max_temp"], Temp) and value > self.cfg["max_temp"]
            ):
                value = self.cfg["max_temp"]
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

    def notify_state_changed(self, attrs: dict) -> T.Any:
        """Is called when the thermostat's state changes.
        This method fetches both the current and target temperature from
        the thermostat and reacts accordingly."""

        _target_temp = None  # type: T.Optional[TempValueType]
        if self.cfg["supports_hvac_modes"]:
            hvac_mode = attrs.get("state")
            self.log(
                "Attribute 'state' is {}.".format(repr(hvac_mode)),
                level="DEBUG",
                prefix=common.LOG_PREFIX_INCOMING,
            )
            if hvac_mode == self.cfg["hvac_mode_off"]:
                _target_temp = OFF
            elif hvac_mode != self.cfg["hvac_mode_on"]:
                self.log(
                    "Unknown HVAC mode {!r}, ignoring thermostat.".format(hvac_mode),
                    level="ERROR",
                )
                return None
        else:
            hvac_mode = None

        if _target_temp is None:
            _target_temp = attrs.get("temperature")
            self.log(
                "Attribute 'temperature' is {}.".format(repr(_target_temp)),
                level="DEBUG",
                prefix=common.LOG_PREFIX_INCOMING,
            )

        try:
            target_temp = Temp(_target_temp)
        except ValueError:
            self.log("Invalid target temperature, ignoring thermostat.", level="ERROR")
            return None

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
    def serialize_value(value: Temp) -> str:
        """Wrapper around Temp.serialize()."""

        if not isinstance(value, Temp):
            raise ValueError(
                "can only serialize Temp objects, not {}".format(repr(value))
            )
        return value.serialize()

    @staticmethod
    def validate_value(value: T.Any) -> Temp:
        """Ensures the given value is a valid temperature."""

        return Temp(value)
