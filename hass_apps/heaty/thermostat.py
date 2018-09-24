"""
This module implements the Thermostat class.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from .room import Room

import copy
import observable

from .. import common
from . import expr


class Thermostat:
    """A thermostat to be controlled by Heaty."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, entity_id: str, cfg: dict, room: "Room") -> None:
        self.entity_id = entity_id
        self.cfg = cfg
        self.room = room
        self.app = room.app
        self.current_temp = None  # type: T.Optional[expr.Temp]
        self.current_target_temp = None  # type: T.Optional[expr.Temp]
        self.wanted_temp = None  # type: T.Optional[expr.Temp]
        self.resend_timer = None  # type: T.Optional[uuid.UUID]
        self.events = observable.Observable()  # type: observable.Observable

    def __repr__(self) -> str:
        return "<Thermostat {}>".format(str(self))

    def __str__(self) -> str:
        return "T:{}".format(self.cfg.get("friendly_name", self.entity_id))

    def _check_config_plausibility(self) -> None:
        """Is called during initialization to warn the user about some
        possible common configuration mistakes."""

        _state = self.app.get_state(self.entity_id, attribute="all")
        if not _state:
            self.log("Thermostat couldn't be found.", level="WARNING")
            return

        state = copy.deepcopy(_state or {})  # type: T.Dict[str, T.Any]
        state.update((state or {}).get("attributes", {}))

        required_attrs = []
        if self.cfg["supports_opmodes"]:
            required_attrs.append(self.cfg["opmode_state_attr"])
        if self.cfg["supports_temps"]:
            required_attrs.append(self.cfg["target_temp_state_attr"])
        if not required_attrs:
            self.log("At least one of supports_opmodes and "
                     "supports_temps should be enabled. "
                     "Please check your config!",
                     level="WARNING")
        for attr in required_attrs:
            if attr not in state:
                self.log("Thermostat has no attribute named {}. "
                         "Available attributes are {}. "
                         "Please check your config!"
                         .format(repr(attr), list(state.keys())),
                         level="WARNING")

        if self.cfg["supports_temps"]:
            temp_attrs = [self.cfg["target_temp_state_attr"]]
            if self.cfg["current_temp_state_attr"]:
                temp_attrs.append(self.cfg["current_temp_state_attr"])
            for attr in temp_attrs:
                value = state.get(attr)
                try:
                    value = float(value)  # type: ignore
                except (TypeError, ValueError):
                    self.log("The value {} for attribute {} is no valid "
                             "temperature value. "
                             "Please check your config!"
                             .format(repr(value), repr(attr)),
                             level="WARNING")

        allowed_opmodes = state.get("operation_list")
        if not self.cfg["supports_opmodes"]:
            if allowed_opmodes:
                self.log("Operation mode support has been disabled, "
                         "but the following modes seem to be supported: {} "
                         "Maybe disabling it was a mistake?"
                         .format(allowed_opmodes),
                         level="WARNING")
            return

        if self.cfg["opmode_state_attr"] != "operation_mode":
            # we can't rely on operation_list in this case
            return
        if not allowed_opmodes:
            self.log("Attributes for thermostat contain no "
                     "'operation_list', Consider disabling "
                     "operation mode support.",
                     level="WARNING")
            return
        for opmode in (self.cfg["opmode_heat"], self.cfg["opmode_off"]):
            if opmode not in allowed_opmodes:
                self.log("Thermostat doesn't seem to support the "
                         "operation mode {}, supported modes are: {}. "
                         "Please check your config!"
                         .format(opmode, allowed_opmodes),
                         level="WARNING")

    def _state_cb(
            self, entity: str, attr: str,
            old: T.Optional[dict], new: T.Optional[dict],
            kwargs: dict,
    ) -> None:
        """Is called when the thermostat's state changes.
        This method fetches both the current and target temperature from
        the thermostat and reacts accordingly."""

        attrs = copy.deepcopy(new or {})
        attrs.update((attrs or {}).get("attributes", {}))

        _target_temp = None  # type: T.Optional[expr.TempValueType]
        if self.cfg["supports_opmodes"]:
            opmode = attrs.get(self.cfg["opmode_state_attr"])
            self.log("Attribute {} is {}."
                     .format(repr(self.cfg["opmode_state_attr"]), repr(opmode)),
                     level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
            if opmode == self.cfg["opmode_off"]:
                _target_temp = expr.Off()
            elif opmode != self.cfg["opmode_heat"]:
                self.log("Unknown operation mode, ignoring thermostat.",
                         level="ERROR")
                return
        else:
            opmode = None

        if _target_temp is None:
            if self.cfg["supports_temps"]:
                _target_temp = attrs.get(self.cfg["target_temp_state_attr"])
                self.log("Attribute {} is {}."
                         .format(repr(self.cfg["target_temp_state_attr"]),
                                 repr(_target_temp)),
                         level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
            else:
                _target_temp = 0

        try:
            target_temp = expr.Temp(_target_temp)
        except ValueError:
            self.log("Invalid target temperature, ignoring thermostat.",
                     level="ERROR")
            return

        current_temp_attr = self.cfg["current_temp_state_attr"]
        if current_temp_attr and self.cfg["supports_temps"]:
            _current_temp = attrs.get(current_temp_attr)
            self.log("Attribute {} is {}."
                     .format(repr(current_temp_attr), repr(_current_temp)),
                     level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
            try:
                current_temp = expr.Temp(_current_temp)  # type: T.Optional[expr.Temp]
            except ValueError:
                self.log("Invalid current temperature, not updating it.",
                         level="ERROR")
            else:
                if current_temp != self.current_temp:
                    self.current_temp = current_temp
                    self.events.trigger(
                        "current_temp_changed", self, current_temp
                    )

        if target_temp == self.wanted_temp:
            self.cancel_resend_timer()

        if target_temp != self.current_target_temp:
            if self.cfg["supports_temps"]:
                self.log("Received target temperature of {}."
                         .format(str(target_temp)),
                         prefix=common.LOG_PREFIX_INCOMING)
            else:
                self.log("Received state of {}."
                         .format("OFF" if target_temp.is_off else "ON"),
                         prefix=common.LOG_PREFIX_INCOMING)

            self.current_target_temp = target_temp
            self.events.trigger(
                "target_temp_changed", self, target_temp
            )

    def initialize(self) -> None:
        """Should be called in order to register state listeners and
        timers."""

        self.log("Initializing thermostat (entity_id={})."
                 .format(repr(self.entity_id)),
                 level="DEBUG")

        self._check_config_plausibility()

        self.log("Fetching initial state.",
                 level="DEBUG")
        state = self.app.get_state(self.entity_id, attribute="all")
        if state is None:
            self.log("State for thermostat is None, ignoring it for now.",
                     level="WARNING")
        else:
            # populate self.current_target_temp etc. by simulating a
            # state change
            self._state_cb(self.entity_id, "all", state, state, {})

        self.log("Listening for state changes.",
                 level="DEBUG")
        self.app.listen_state(self._state_cb, self.entity_id, attribute="all")

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the thermostat to log messages."""
        msg = "[{}] {}".format(self, msg)
        self.room.log(msg, *args, **kwargs)

    def cancel_resend_timer(self) -> None:
        """Cancels the resend timer for this thermostat, if one exists."""

        timer = self.resend_timer
        if timer is None:
            return
        self.app.cancel_timer(timer)
        self.resend_timer = None
        self.log("Cancelled resend timer.", level="DEBUG")

    @property
    def is_synced(self) -> bool:
        """Tells whether the thermostat's target temperature is the
        wanted temperature and no re-sending is in progress."""

        return self.resend_timer is None and \
               self.current_target_temp is not None and \
               self.current_target_temp == self.wanted_temp

    def set_temp(
            self, target_temp: expr.Temp, force_resend: bool = False
    ) -> T.Optional[expr.Temp]:
        """Sets the given target temperature on this thermostat
        The temperature should be the desired room temperature,
        without delta added. This method will try best to achieve
        the closest possible temperature supported by this particular
        thermostat.
        A temperature won't be send to the thermostat redundantly
        unless force_resend is True.
        The return value is either the actually set temperature or
        None, if nothing has been sent."""

        if target_temp.is_off:
            target_temp = self.cfg["off_temp"]

        if target_temp.is_off:
            temp = None
            opmode = self.cfg["opmode_off"]
        else:
            temp = target_temp + self.cfg["delta"]
            if isinstance(self.cfg["min_temp"], expr.Temp) and \
               temp < self.cfg["min_temp"]:
                temp = None
                opmode = self.cfg["opmode_off"]
            else:
                opmode = self.cfg["opmode_heat"]
                if isinstance(self.cfg["max_temp"], expr.Temp) and \
                   temp > self.cfg["max_temp"]:
                    temp = self.cfg["max_temp"]

        if not self.cfg["supports_opmodes"]:
            if opmode == self.cfg["opmode_off"]:
                self.log("Not turning off because it doesn't support "
                         "operation modes.",
                         level="DEBUG")
                if self.cfg["min_temp"] is not None:
                    self.log("Setting to minimum supported temperature "
                             "instead.",
                             level="DEBUG")
                    temp = self.cfg["min_temp"]
            opmode = None

        if not self.cfg["supports_temps"] and temp is not None:
            self.log("Not setting temperature because thermostat doesn't "
                     "support temperatures.",
                     level="DEBUG")
            temp = None

        if opmode is None and temp is None:
            self.log("Nothing to send to this thermostat.",
                     level="DEBUG")
            return None

        if opmode == self.cfg["opmode_off"]:
            wanted_temp = expr.Temp(expr.OFF)  # type: T.Optional[expr.Temp]
        elif self.cfg["supports_temps"]:
            wanted_temp = temp
        else:
            wanted_temp = expr.Temp(0)
        self.wanted_temp = wanted_temp

        if not force_resend and self.is_synced:
            self.log("Not sending temperature redundantly.",
                     level="DEBUG")
            return None

        self.cancel_resend_timer()
        self._set_temp_resend_cb({
            "left_retries": self.cfg["set_temp_retries"],
            "opmode": opmode,
            "temp": temp,
        })

        return wanted_temp

    def _set_temp_resend_cb(self, kwargs: dict) -> None:
        """This callback sends the operation_mode and temperature to the
        thermostat. Expected values for kwargs are:
        - opmode and temp (incl. delta)
        - left_retries (after this round)"""

        opmode = kwargs["opmode"]
        temp = kwargs["temp"]
        left_retries = kwargs["left_retries"]

        self.resend_timer = None

        self.log("Setting temperature = {}, operation mode = {}, "
                 "left retries = {}."
                 .format(temp or "<unset>", repr(opmode) or "<unset>",
                         left_retries),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)

        if opmode is not None:
            if opmode == self.cfg["opmode_heat"]:
                opmode_service = self.cfg["opmode_heat_service"]
                opmode_service_attr = self.cfg["opmode_heat_service_attr"]
            else:
                opmode_service = self.cfg["opmode_off_service"]
                opmode_service_attr = self.cfg["opmode_off_service_attr"]
            attrs = {"entity_id": self.entity_id}
            if opmode_service_attr:
                attrs[opmode_service_attr] = opmode
            self.app.call_service(opmode_service, **attrs)
        if temp is not None:
            attrs = {"entity_id": self.entity_id,
                     self.cfg["target_temp_service_attr"]: temp.value}
            self.app.call_service(self.cfg["target_temp_service"], **attrs)

        if not left_retries:
            return

        interval = self.cfg["set_temp_retry_interval"]
        self.log("Re-sending in {} seconds."
                 .format(interval),
                 level="DEBUG")
        timer = self.app.run_in(
            self._set_temp_resend_cb, interval,
            left_retries=left_retries - 1,
            opmode=opmode, temp=temp)
        self.resend_timer = timer
