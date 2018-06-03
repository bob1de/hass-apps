"""
A highly-configurable, comfortable to use Home Assistant / appdaemon app
that controls thermostats based on a schedule while still facilitating
manual intervention at any time.
"""

import typing as T
import types  # pylint: disable=unused-import

import importlib

from .. import common
from . import __version__, config, expr, util
from .room import Room


__all__ = ["HeatyApp"]


class HeatyApp(common.App):
    """The Heaty app class for AppDaemon."""

    class Meta(common.App.Meta):
        # pylint: disable=missing-docstring
        name = "heaty"
        version = __version__
        config_schema = config.CONFIG_SCHEMA

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        self.app = self
        self.cfg = None
        self.rooms = []  # type: T.List[Room]
        self.temp_expression_modules = {}  # type: T.Dict[str, types.ModuleType]
        super().__init__(*args, **kwargs)

    def initialize_inner(self) -> None:
        """Checks the configuration, initializes all timers, state and
        event callbacks and sets temperatures in all rooms according
        to the configured schedules."""

        heaty_id = self.cfg["heaty_id"]
        self.log("Heaty id is: {}".format(repr(heaty_id)))
        heaty_id_kwargs = {}
        if heaty_id != "default":
            heaty_id_kwargs["heaty_id"] = heaty_id

        self.log("Importing modules for use in temperature expressions.",
                 level="DEBUG")
        for mod_name, mod_data in self.cfg["temp_expression_modules"].items():
            as_name = util.escape_var_name(mod_data.get("as", mod_name))
            self.log("Importing module {} as {}."
                     .format(repr(mod_name), repr(as_name)),
                     level="DEBUG")
            try:
                mod = importlib.import_module(mod_name)
            except Exception as err:  # pylint: disable=broad-except
                self.log("Error while importing module {}: {}"
                         .format(repr(mod_name), repr(err)),
                         level="ERROR")
                self.log("Module won't be available.", level="ERROR")
            else:
                self.temp_expression_modules[as_name] = mod

        for room in self.rooms:
            room.initialize()

        self.log("Registering event listener for heaty_reschedule.",
                 level="DEBUG")
        self.listen_event(self._reschedule_event_cb, "heaty_reschedule",
                          **heaty_id_kwargs)

        self.log("Registering event listener for heaty_set_temp.",
                 level="DEBUG")
        self.listen_event(self._set_temp_event_cb, "heaty_set_temp",
                          **heaty_id_kwargs)

        master_switch = self.cfg["master_switch"]
        if master_switch:
            self.log("Registering state listener for master switch {}."
                     .format(master_switch),
                     level="DEBUG")
            self.listen_state(self._master_switch_cb, master_switch)

        if self.master_switch_enabled():
            for room in self.rooms:
                if not room.check_for_open_window():
                    room.set_scheduled_temp()
        else:
            self.log("Master switch is off, not setting temperatures "
                     "initially.")

    def _master_switch_cb(
            self, entity: str, attr: str, old: T.Any, new: T.Any, kwargs: dict
    ) -> None:
        """Is called when the master switch is toggled.
        If turned on, it sets the scheduled temperatures in all rooms.
        If switch is turned off, all re-schedule timers are cancelled
        and temperature is set to self.cfg["off_temp"] everywhere."""

        self.log("Master switch turned {}.".format(new),
                 prefix=common.LOG_PREFIX_INCOMING)
        for room in self.rooms:
            if new == "on":
                room.set_scheduled_temp()
            else:
                room.cancel_reschedule_timer()
                room.set_temp(self.cfg["off_temp"], scheduled=False)
                # invalidate cached temp/rule
                room.current_schedule_temp = None
                room.current_schedule_rule = None

    def _reschedule_event_cb(
            self, event: str, data: dict, kwargs: dict
    ) -> None:
        """This callback executes when a heaty_reschedule event is received.
        data may contain a "room_name", which limits the re-scheduling
        to the given room."""

        if data.get("heaty_id", self.cfg["heaty_id"]) != self.cfg["heaty_id"]:
            self.log("Ignoring reschedule event for heaty_id '{}', "
                     "ours is '{}'."
                     .format(data.get("heaty_id"), self.cfg["heaty_id"]),
                     level="DEBUG")
            return

        if not self.master_switch_enabled():
            self.log("Ignoring re-schedule event because master "
                     "switch is off.",
                     level="DEBUG")
            return

        room_name = data.get("room_name")
        if room_name:
            room = self.get_room(room_name)
            if not room:
                self.log("Ignoring heaty_reschedule event for "
                         "unknown room {}.".format(room_name),
                         level="WARNING")
                return
            rooms = [room]
        else:
            rooms = self.rooms

        self.log("Re-schedule event received for: {}"
                 .format(", ".join([str(room) for room in rooms])),
                 prefix=common.LOG_PREFIX_INCOMING)

        for room in rooms:
            # delay for 6 seconds to avoid re-scheduling multiple
            # times if multiple events come in shortly
            room.update_reschedule_timer(reschedule_delay=0.1,
                                         force=True)

    def _set_temp_event_cb(
            self, event: str, data: dict, kwargs: dict
    ) -> None:
        """This callback executes when a heaty_set_temp event is received.
        data must contain a "room_name" and a "temp", which may also
        be a temperature expression. "force_resend" is optional and
        False by default. If it is set to True, the temperature is
        re-sent to the thermostats even if it hasn't changed due to
        Heaty's records."""

        if data.get("heaty_id", self.cfg["heaty_id"]) != self.cfg["heaty_id"]:
            self.log("Ignoring set_temp event for heaty_id '{}', "
                     "ours is '{}'."
                     .format(data.get("heaty_id"), self.cfg["heaty_id"]),
                     level="DEBUG")
            return

        try:
            room_name = data["room_name"]
            temp_expr = data["temp"]
            reschedule_delay = data.get("reschedule_delay")
            if not isinstance(reschedule_delay, (type(None), float, int)):
                raise TypeError()
            if isinstance(reschedule_delay, (float, int)) and \
               reschedule_delay < 0:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            self.log("Ignoring heaty_set_temp event with invalid data: {}"
                     .format(repr(data)),
                     level="WARNING")
            return

        room = self.get_room(room_name)
        if not room:
            self.log("Ignoring heaty_set_temp event for unknown "
                     "room {}.".format(room_name),
                     level="WARNING")
            return

        if not self.cfg["untrusted_temp_expressions"] and \
           expr.Temp.parse_temp(temp_expr) is None:
            self.log("Ignoring heaty_set_temp event with an "
                     "untrusted temperature expression. "
                     "(untrusted_temp_expressions = false)",
                     level="WARNING")
            return

        room.notify_set_temp_event(
            temp_expr, force_resend=bool(data.get("force_resend")),
            reschedule_delay=reschedule_delay
        )

    def get_room(self, room_name: str) -> T.Optional[Room]:
        """Returns the room with given name or None, if no such room
        exists."""

        for room in self.rooms:
            if room.name == room_name:
                return room
        return None

    def master_switch_enabled(self) -> bool:
        """Returns the state of the master switch or True if no master
        switch is configured."""
        master_switch = self.cfg["master_switch"]
        if master_switch:
            return self.get_state(master_switch) == "on"  # type: ignore
        return True
