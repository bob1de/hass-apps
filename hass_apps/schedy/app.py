"""
A multi-purpose scheduler for Home Assistant + AppDaemon.
"""

import typing as T
import types  # pylint: disable=unused-import
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from .room import Room
    from .stats import StatisticalParameter

import importlib

from .. import common
from . import __version__, config, util
from .actor.base import ActorBase


__all__ = ["SchedyApp"]


class SchedyApp(common.App):
    """The Schedy app class for AppDaemon."""

    class Meta(common.App.Meta):
        # pylint: disable=missing-docstring
        name = "schedy"
        version = __version__
        config_schema = config.CONFIG_SCHEMA

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        self.actor_type = None  # type: T.Optional[T.Type[ActorBase]]
        self.rooms = []  # type: T.List[Room]
        self.stats_params = []  # type: T.List[StatisticalParameter]
        self.expression_modules = {}  # type: T.Dict[str, types.ModuleType]
        super().__init__(*args, **kwargs)

    def _check_accept_event(self, event: str, data: dict) -> bool:
        """Returns whether this Schedy instance is addressed by the
        given event name and data."""

        app_name = data.get("app_name", self.name)
        if app_name != self.name:
            self.log("Ignoring {} event for app_name '{}', "
                     "ours is '{}'."
                     .format(event, app_name, self.name),
                     level="DEBUG")
            return False
        return True

    def _get_event_rooms(
            self, event: str, room_names: T.Any
    ) -> T.Iterable["Room"]:
        """Returns an iterable over the rooms whose names were passed
        for the given event name. Passing None as room_names causes all
        rooms to be returned. A string or list of strings is converted
        to a list of the corresponding Room objects."""

        rooms = []
        if room_names is None:
            rooms.extend(self.rooms)
        else:
            if isinstance(room_names, str):
                room_names = [room_names]
            elif not isinstance(room_names, list):
                room_names = []
            for room_name in room_names:
                room = self.get_room(room_name)
                if room:
                    rooms.append(room)
                else:
                    self.log("Ignoring {} event for unknown room {}."
                             .format(event, repr(room_name)),
                             level="WARNING")

        return rooms

    def _reschedule_event_cb(
            self, event: str, data: dict, kwargs: dict
    ) -> None:
        """This callback executes when a schedy_reschedule event is received.
        data may contain a "room_name", which limits the re-scheduling
        to the given room.
        mode has to be one of "reevaluate" (the default, only set the
        value when it changed) or "reset" (restart an eventually running
        timer and start a new one with reset=True)."""

        if not self._check_accept_event(event, data):
            return

        mode = data.get("mode", "reevaluate")
        if mode not in ("reset", "reevaluate"):
            self.log("Unknown mode {}."
                     .format(repr(mode)),
                     level="ERROR")
            return

        rooms = self._get_event_rooms(event, data.get("room"))
        self.log("Re-schedule event received for: {} [mode={}, delay=1sec]"
                 .format(", ".join([str(room) for room in rooms]),
                         repr(mode)),
                 prefix=common.LOG_PREFIX_INCOMING)

        for room in rooms:
            # delay for one second to have the state fully updated when
            # when schedules are evaluated
            gen = lambda func, reset: lambda *a, **kw: func(reset=reset)
            self.run_in(gen(room.apply_schedule, bool(mode == "reset")), 1)  # type: ignore

    def _set_value_event_cb(
            self, event: str, data: dict, kwargs: dict
    ) -> None:
        """This callback executes when a schedy_set_value event is received.
        data must contain a "room_name" and an "expression"/"x" or
        "value"/"v".
        "force_resend" is optional and False by default. If it is set
        to True, the value is re-sent to the actorss even if it hasn't
        changed."""

        if not self._check_accept_event(event, data):
            return

        try:
            rescheduling_delay = data.get("rescheduling_delay")
            if isinstance(rescheduling_delay, str):
                rescheduling_delay = float(rescheduling_delay)
            if not isinstance(rescheduling_delay, (type(None), float, int)):
                raise TypeError()
            if isinstance(rescheduling_delay, (float, int)) and \
               rescheduling_delay < 0:
                raise ValueError()
            util.normalize_dict_key(data, "expression", "x")
            expr = data.get("expression")
            util.normalize_dict_key(data, "value", "v")
            value = data.get("value")
            if expr is not None and value is not None:
                raise ValueError()
            if expr is not None:
                if not self.cfg["expressions_from_events"]:
                    self.log("Received a {} event with an expression, "
                             "but expressions_from_events is not enabled "
                             "in your config. Ignoring event."
                             .format(event),
                             level="ERROR")
                    raise ValueError()
            elif value is None:
                raise ValueError()
        except (TypeError, ValueError):
            self.log("Ignoring {} event with invalid data: {}"
                     .format(event, repr(data)),
                     level="WARNING")
            return

        rooms = self._get_event_rooms(event, data.get("room"))
        for room in rooms:
            room.notify_set_value_event(
                expr_raw=expr, value=value,
                force_resend=bool(data.get("force_resend")),
                rescheduling_delay=rescheduling_delay
            )

    def get_room(self, room_name: str) -> T.Optional["Room"]:
        """Returns the room with given name or None, if no such room
        exists."""

        for room in self.rooms:
            if room.name == room_name:
                return room
        return None

    def initialize_inner(self) -> None:
        """Checks the configuration, initializes all timers, state and
        event callbacks and sets values in all rooms according to the
        configured schedules."""

        assert self.actor_type is not None
        self.log("Actor type is: {}".format(repr(self.actor_type.name)))

        self.log("Importing modules for use in expressions.",
                 level="DEBUG")
        for mod_name, mod_data in self.cfg["expression_modules"].items():
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
                self.expression_modules[as_name] = mod

        for room in self.rooms:
            room.initialize(reset=self.cfg["reset_at_startup"])

        self.log("Listening for schedy_reschedule event.",
                 level="DEBUG")
        self.listen_event(self._reschedule_event_cb, "schedy_reschedule")

        self.log("Listening for schedy_set_value event.",
                 level="DEBUG")
        self.listen_event(self._set_value_event_cb, "schedy_set_value")

        for stats_param in self.stats_params:
            stats_param.initialize()
