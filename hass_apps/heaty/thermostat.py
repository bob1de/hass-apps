"""
This module implements the Thermostat class.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from . import room as _room

from .. import common
from . import expr, util


class Thermostat:
    """A thermostat to be controlled by Heaty."""

    def __init__(self, entity_id: str, cfg: dict, room: "_room.Room") -> None:
        self.entity_id = entity_id
        self.cfg = cfg
        self.room = room
        self.app = room.app
        self.current_temp = None  # type: T.Optional[expr.Temp]
        self.wanted_temp = None  # type: T.Optional[expr.Temp]
        self.resend_timer = None  # type: T.Optional[uuid.UUID]

    def __repr__(self) -> str:
        return "<Thermostat {}>".format(str(self))

    def __str__(self) -> str:
        return self.cfg.get("friendly_name", self.entity_id)

    def _check_config_plausibility(self) -> None:
        """Is called during initialization to warn the user about some
        possible common configuration mistakes."""

        state = self.app.get_state(self.entity_id, attribute="all")
        if not state:
            self.log("Thermostat couldn't be found.", level="WARNING")
            return

        state = (state or {}).get("attributes", {})

        required_attrs = [self.cfg["temp_state_attr"]]
        if self.cfg["supports_opmodes"]:
            required_attrs.append(self.cfg["opmode_state_attr"])
        for attr in required_attrs:
            if attr not in state:
                self.log("Thermostat has no attribute named {}. "
                         "Available attributes are {}. "
                         "Please check your config!"
                         .format(repr(attr), list(state.keys())),
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

    @util.modifies_state
    def _state_cb(
            self, entity: str, attr: str,
            old: T.Optional[dict], new: T.Optional[dict],
            kwargs: dict, no_reschedule: bool = False
    ) -> None:
        """Is called when the thermostat's state changes.
        This method fetches the set target temperature from the
        thermostat and reacts accordingly."""

        attrs = (new or {}).get("attributes", {})

        opmode = attrs.get(self.cfg["opmode_state_attr"])
        self.log("Attribute {} is {}."
                 .format(self.cfg["opmode_state_attr"], opmode),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)

        _temp = None
        if self.cfg["supports_opmodes"]:
            if opmode is None:
                # don't consider this thermostat
                return
            elif opmode == self.cfg["opmode_off"]:
                _temp = expr.Off()

        if _temp is None:
            _temp = attrs.get(self.cfg["temp_state_attr"])
            self.log("Attribute {} is {}."
                     .format(self.cfg["temp_state_attr"], _temp),
                     level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)

        try:
            temp = expr.Temp(_temp)
        except ValueError:
            # not a valid temperature, don't consider this thermostat
            return

        if temp == self.wanted_temp:
            # thermostat adapted to the temperature we want,
            # cancel any re-send timer
            self.cancel_resend_timer()

        if temp == self.current_temp:
            # nothing changed, hence no further actions needed
            return

        self.current_temp = temp

        self.log("Received target temperature {}."
                 .format(repr(temp)),
                 prefix=common.LOG_PREFIX_INCOMING)

        temp -= self.cfg["delta"]

        self.room.notify_temp_changed(temp, no_reschedule=no_reschedule)

    def initialize(self) -> None:
        """Should be called in order to register state listeners and
        timers."""

        self._check_config_plausibility()

        # only consider one thermostat per room
        if self.room.wanted_temp is None:
            self.log("Getting current temperature from thermostat.",
                     level="DEBUG")
            state = self.app.get_state(self.entity_id, attribute="all")
            if state is None:
                # unknown entity
                self.log("State for thermostat is None, ignoring it.",
                         level="WARNING")
            else:
                # populate self.current_temp by simulating a state change
                self._state_cb(self.entity_id, "all", state, state, {},
                               no_reschedule=True)

        self.log("Registering thermostat state listener.", level="DEBUG")
        self.app.listen_state(self._state_cb, self.entity_id, attribute="all")

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the thermostat to log messages."""
        msg = "[{}] {}".format(self, msg)
        self.room.log(msg, *args, **kwargs)

    def cancel_resend_timer(self) -> bool:
        """Cancel the resend timer for this thermostat, if one exists.
        Returns whether a timer was cancelled."""

        timer = self.resend_timer
        if timer is None:
            return False

        self.app.cancel_timer(timer)
        self.resend_timer = None
        self.log("Cancelled resend timer.", level="DEBUG")
        return True

    def is_synced(self) -> bool:
        """Returns whether the thermostat's target temperature is the
        wanted temperature and no re-sending is in progress."""

        return self.resend_timer is None and \
               self.current_temp is not None and \
               self.current_temp == self.wanted_temp

    @util.modifies_state
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

        if target_temp.is_off():
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

        if opmode is None and temp is None:
            self.log("Nothing to send to thermostat.",
                     level="DEBUG")
            return None

        self.wanted_temp = temp or expr.Temp(expr.OFF)
        if not force_resend and self.is_synced():
            self.log("Not sending temperature redundantly.",
                     level="DEBUG")
            return None

        left_retries = self.cfg["set_temp_retries"]
        self.cancel_resend_timer()
        timer = self.app.run_in(
            self._set_temp_resend_cb, 1,
            left_retries=left_retries,
            opmode=opmode, temp=temp
        )
        self.resend_timer = timer

        return self.wanted_temp

    def _set_temp_resend_cb(self, kwargs: dict) -> None:
        """This callback sends the operation_mode and temperature to the
        thermostat. Expected values for kwargs are:
        - opmode and temp (incl. delta)
        - left_retries (after this round)"""

        opmode = kwargs["opmode"]
        temp = kwargs["temp"]
        left_retries = kwargs["left_retries"]

        self.cancel_resend_timer()

        self.log("Setting {} = {}, {} = {}, left retries = {}"
                 .format(self.cfg["temp_service_attr"],
                         temp if temp is not None else "<unset>",
                         self.cfg["opmode_service_attr"],
                         opmode if opmode is not None else "<unset>",
                         left_retries),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)

        if opmode is not None:
            attrs = {"entity_id": self.entity_id,
                     self.cfg["opmode_service_attr"]: opmode}
            self.app.call_service(self.cfg["opmode_service"], **attrs)
        if temp is not None:
            attrs = {"entity_id": self.entity_id,
                     self.cfg["temp_service_attr"]: temp.value}
            self.app.call_service(self.cfg["temp_service"], **attrs)

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
