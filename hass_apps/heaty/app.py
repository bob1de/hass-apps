"""
A highly-configurable, comfortable to use Home Assistant / appdaemon app
that controls thermostats based on a schedule while still facilitating
manual intervention at any time.
"""

import typing as T
import types  # pylint: disable=unused-import
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from .room import Room
    from .stats import StatisticsZone

import importlib
import inspect

from .. import common
from . import __version__, config, expr, util


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
        self.stats_zones = []  # type: T.List[StatisticsZone]
        self.temp_expression_modules = {}  # type: T.Dict[str, types.ModuleType]
        super().__init__(*args, **kwargs)

    def initialize_inner(self) -> None:
        """Checks the configuration, initializes all timers, state and
        event callbacks and sets temperatures in all rooms according
        to the configured schedules."""

        self.log("Heaty is deprecated in favour of Schedy. Please consult "
                 "the documentation for further information.",
                 level="WARNING")

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

        self.log("Listening for heaty_reschedule event.",
                 level="DEBUG")
        self.listen_event(self._reschedule_event_cb, "heaty_reschedule",
                          **heaty_id_kwargs)

        self.log("Listening for heaty_set_temp event.",
                 level="DEBUG")
        self.listen_event(self._set_temp_event_cb, "heaty_set_temp",
                          **heaty_id_kwargs)

        master = self.cfg["master_switch"]
        if master:
            self.log("Listening for state changes of master switch "
                     "(entity_id={})."
                     .format(repr(master)),
                     level="DEBUG")
            self.listen_state(self._master_switch_cb, master)

        if self.master_is_on():
            for room in self.rooms:
                if not room.check_for_open_window():
                    room.apply_schedule(
                        send=self.cfg["reschedule_at_startup"]
                    )
        else:
            self.log("Master switch is off, not setting temperatures "
                     "initially.")

        for zone in self.stats_zones:
            zone.initialize()

    def _master_switch_cb(
            self, entity: str, attr: str, old: T.Any, new: T.Any, kwargs: dict
    ) -> None:
        """Is called when the master switch is toggled.
        If turned on, it sets the scheduled temperatures in all rooms.
        If switch is turned off, all re-schedule timers are cancelled and
        temperature is set to self.cfg["master_off_temp"] everywhere."""

        self.log("Master switch turned {}.".format(new),
                 prefix=common.LOG_PREFIX_INCOMING)
        for room in self.rooms:
            if new == "on":
                room.apply_schedule()
            else:
                room.cancel_reschedule_timer()
                room.set_temp(self.cfg["master_off_temp"], scheduled=False)
                # invalidate cached temp
                room.scheduled_temp = None

    def _reschedule_event_cb(
            self, event: str, data: dict, kwargs: dict
    ) -> None:
        """This callback executes when a heaty_reschedule event is received.
        data may contain a "room_name", which limits the re-scheduling
        to the given room."""

        if data.get("heaty_id", self.cfg["heaty_id"]) != self.cfg["heaty_id"]:
            self.log("Ignoring re-schedule event for heaty_id '{}', "
                     "ours is '{}'."
                     .format(data.get("heaty_id"), self.cfg["heaty_id"]),
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
        restart = bool(data.get("cancel_running_timer", False))

        self.log("Re-schedule event received for: {}{}."
                 .format(", ".join([str(room) for room in rooms]),
                         " [cancel running timer]" if restart else ""),
                 prefix=common.LOG_PREFIX_INCOMING)

        if not self.require_master_is_on():
            return

        for room in rooms:
            # delay for 6 seconds to avoid re-scheduling multiple
            # times if multiple events come in shortly
            room.start_reschedule_timer(reschedule_delay=0.1, restart=restart)

    def _set_temp_event_cb(
            self, event: str, data: dict, kwargs: dict
    ) -> None:
        """This callback executes when a heaty_set_temp event is received.
        data must contain a "room_name" and a "value"/"v", which may also
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
            for key in ("v", "temp"):
                if key in data:
                    data.setdefault("value", data[key])
                    break
            temp_expr = data["value"]
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

    def get_room(self, room_name: str) -> T.Optional["Room"]:
        """Returns the room with given name or None, if no such room
        exists."""

        for room in self.rooms:
            if room.name == room_name:
                return room
        return None

    def master_is_on(self) -> bool:
        """Returns whether the master switch is "on". If no master switch
        is configured, this returns True."""

        master = self.cfg["master_switch"]
        if master:
            return self.get_state(master) == "on"  # type: ignore
        return True

    def require_master_is_on(self) -> bool:
        """Returns whether the master switch is on. If not, a debug
        message is logged."""

        if not self.master_is_on():
            stack = inspect.stack()
            caller_name = stack[1].function
            self.log("Master switch is off, aborting {}."
                     .format(repr(caller_name)),
                     level="DEBUG")
            return False
        return True
