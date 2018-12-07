"""
This module implements the Room class.
"""

import types
import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from .app import SchedyApp
    from .schedule import Schedule
    from .actor.base import ActorBase

import datetime
import functools
import threading

from .. import common
from . import expression, util
from .expression import types as expression_types


def sync_proxy(handler: T.Callable) -> T.Callable:
    """A decorator for wrapping event and state handlers.
    It can be applied to members of Room or of objects having a Room
    object as their "room" attribute.
    It ensures all handlers are executed synchronously by acquiring a
    re-entrant lock stored in the Room object.
    Room._update_state() is called after the outmost handler wrapped
    with this decorator finishes."""

    @functools.wraps(handler)
    def wrapper(self: T.Any, *args: T.Any, **kwargs: T.Any) -> T.Any:
        """Wrapper around the event handler."""

        # pylint: disable=protected-access

        if isinstance(self, Room):
            room = self
        else:
            room = self.room

        with room._sync_proxy_lock:
            first = not room._sync_proxy_running
            try:
                if first:
                    room._sync_proxy_running = True
                result = handler(self, *args, **kwargs)
                if first:
                    room._update_state()
            finally:
                if first:
                    room._sync_proxy_running = False
            return result

    return wrapper


class Room:
    """A room to be controlled by Schedy."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str, cfg: dict, app: "SchedyApp") -> None:
        self.name = name
        self.cfg = cfg
        self.app = app
        self.actors = []  # type: T.List[ActorBase]
        self.schedule = None  # type: T.Optional[Schedule]

        self._wanted_value = None  # type: T.Any
        self._scheduled_value = None  # type: T.Any
        self._rescheduling_time = None  # type: T.Optional[datetime.datetime]
        self._rescheduling_timer = None  # type: T.Optional[uuid.UUID]
        self._overlaid_wanted_value = None  # type: T.Any
        self._overlaid_scheduled_value = None  # type: T.Any
        self._overlaid_rescheduling_time = None  # type: T.Optional[datetime.datetime]

        self._last_state = None  # type: T.Optional[T.Tuple[str, T.Dict[str, T.Any]]]

        self._sync_proxy_lock = threading._RLock()  # pylint: disable=protected-access
        self._sync_proxy_running = False

    def __repr__(self) -> str:
        return "<Room {}>".format(str(self))

    def __str__(self) -> str:
        return "R:{}".format(self.cfg.get("friendly_name", self.name))

    def _clear_overlay(self) -> None:
        """Removes all stored overlay state."""

        self._overlaid_wanted_value = None
        self._overlaid_scheduled_value = None
        self._overlaid_rescheduling_time = None

    @sync_proxy
    def _initialize_actor_cb(self, kwargs: dict) -> None:
        """Is called for each actor until it's initialized successfully."""

        actor = kwargs["actor"]
        if not actor.initialize():
            self.log("Actor {} couldn't be initialized, "
                     "retrying in 10 seconds."
                     .format(repr(actor)),
                     level="WARNING")
            self.app.run_in(self._initialize_actor_cb, 10, actor=actor)
            return

        actor.events.on(
            "value_changed", self.notify_value_changed
        )
        if self._wanted_value is not None and \
           all([a.is_initialized for a in self.actors]):
            self.set_value(self._wanted_value)

    def _restore_state(self) -> None:
        """Restores a stored state from Home Assistant and.applies it.
        If no state was found, the schedule is just applied."""

        def deserialize(value: T.Any) -> T.Any:
            """Return the deserialized value or None, if value is None
            or serialization fails."""

            if value is None:
                return None

            assert self.app.actor_type is not None
            return self.app.actor_type.deserialize_value(value)

        def deserialize_dt(value: T.Any) -> T.Optional[datetime.datetime]:
            """Return the datetime object for the given timestamp or None,
            if it is None."""

            if not isinstance(value, (float, int)):
                return None

            return datetime.datetime.fromtimestamp(value)

        entity_id = self._state_entity_id
        self.log("Loading state of {} from Home Assistant."
                 .format(repr(entity_id)),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
        state = self.app.get_state(entity_id, attribute="all")
        self.log("  = {}".format(repr(state)),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)

        reset = False
        if isinstance(state, dict):
            attrs = state.get("attributes", {})
            actor_wanted_values = attrs.get("actor_wanted_values", {})
            for entity_id, value in actor_wanted_values.items():
                value = deserialize(value)
                for actor in self.actors:
                    if actor.entity_id == entity_id:
                        actor.wanted_value = value
            self._wanted_value = deserialize(state.get("state") or None)
            self._scheduled_value = deserialize(attrs.get("scheduled_value"))
            self._rescheduling_time = deserialize_dt(
                attrs.get("rescheduling_time")
            )
            self._overlaid_wanted_value = deserialize(
                attrs.get("overlaid_wanted_value")
            )
            self._overlaid_scheduled_value = deserialize(
                attrs.get("overlaid_scheduled_value")
            )
            self._overlaid_rescheduling_time = deserialize_dt(
                attrs.get("overlaid_rescheduling_time")
            )

            if self._rescheduling_time:
                if self._rescheduling_time > self.app.datetime():
                    if self.cfg["replicate_changes"]:
                        self.set_value(self._wanted_value)
                    self.start_rescheduling_timer(self._rescheduling_time)
                else:
                    self._rescheduling_time = None
                    reset = True

        self.apply_schedule(reset=reset)

    @sync_proxy
    def _rescheduling_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a re-scheduling timer fires.
        reset may be given in kwargs and is passed to apply_schedule()."""

        self.log("Re-scheduling timer fired.",
                 level="DEBUG")
        self._rescheduling_time, self._rescheduling_timer = None, None
        self.apply_schedule(reset=True)

    @sync_proxy
    def _scheduling_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a scheduling timer fires."""

        self.log("Scheduling timer fired.",
                 level="DEBUG")
        self.apply_schedule()

    @property
    def _state_entity_id(self) -> str:
        """Generates the entity id for storing this room's state as."""

        return "schedy_room.{}_{}".format(self.app.name, self.name)

    def _store_for_overlaying(self, scheduled_value: T.Any) -> bool:
        """This method is called before a value overlay is put into place.
        When a re-scheduling timer is running or the scheduled and
        wanted values differ, this method stores the scheduled and wanted
        value together with the re-scheduling time to later be able to
        re-set it.
        Everything except scheduled_value is fetched from self._*.
        A running re-scheduling timer is cancelled.
        If there already is an overlaid value stored, this does nothing.
        Returns whether values have been stored."""

        assert self.app.actor_type is not None
        values_differ = not self.app.actor_type.values_equal(
            scheduled_value, self._wanted_value
        )
        if self._overlaid_wanted_value is None and \
           (values_differ or self._rescheduling_timer):
            self.log("Storing currently wanted value {} before an overlay "
                     "is applied."
                     .format(repr(self._wanted_value)))
            self._overlaid_wanted_value = self._wanted_value
            self._overlaid_scheduled_value = scheduled_value
            self._overlaid_rescheduling_time = self._rescheduling_time
            self.cancel_rescheduling_timer()
            return True
        return False

    def _update_state(self) -> None:
        """Update the room's state in Home Assistant."""

        D = T.TypeVar("D")
        def serialize(value: T.Any, default: D) -> T.Union[str, D]:
            """Return the serialized value or the default, if value is None."""

            if value is None:
                return default

            assert self.app.actor_type is not None
            return self.app.actor_type.serialize_value(value)

        def serialize_dt(
                value: T.Optional[datetime.datetime]
        ) -> T.Optional[float]:
            """Return the timestamp of the given datetime or None,
            if it is None."""

            if value is None:
                return None

            return value.timestamp()

        state = serialize(self._wanted_value, "")
        attrs = {
            "actor_wanted_values": {
                actor.entity_id: serialize(actor.wanted_value, None)
                for actor in self.actors
            },
            "scheduled_value": serialize(self._scheduled_value, None),
            "rescheduling_time": serialize_dt(self._rescheduling_time),
            "overlaid_wanted_value":
                serialize(self._overlaid_wanted_value, None),
            "overlaid_scheduled_value":
                serialize(self._overlaid_scheduled_value, None),
            "overlaid_rescheduling_time": serialize_dt(
                self._overlaid_rescheduling_time
            ),
        }
        if "friendly_name" in self.cfg:
            attrs["friendly_name"] = self.cfg["friendly_name"]

        unchanged = (state, attrs) == self._last_state
        if unchanged:
            self.log("Unchanged HA state: state={}, attributes={}"
                     .format(repr(state), attrs),
                     level="DEBUG")
            return
        self.log("Sending state to HA: state={}, attributes={}"
                 .format(repr(state), attrs),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)

        entity_id = self._state_entity_id
        self.app.set_state(entity_id, state=state, attributes=attrs)
        self._last_state = (state, attrs)

    def validate_value(self, value: T.Any) -> T.Any:
        """A wrapper around self.app.actor_type.validate_value() that
        sanely logs validation errors and returns None in that case."""

        assert self.app.actor_type is not None
        try:
            value = self.app.actor_type.validate_value(value)
        except ValueError as err:
            self.log("Invalid value {} for actor type {}: {}"
                     .format(repr(value), repr(self.app.actor_type.name), err),
                     level="ERROR")
            return None
        return value

    @sync_proxy
    def apply_schedule(
            self, reset: bool = False, force_resend: bool = False
    ) -> None:
        """Applies the value scheduled for the current date and time.
        It detects when the result hasn't changed compared to the last
        run and prevent re-setting it in that case.
        This method will also not re-apply the schedule if a re-schedule
        timer runs - however, the OVERLAY marker is regarded.
        These both checks can be skipped by setting reset to True.
        force_resend is passed through to set_value()."""

        self.log("Evaluating room's schedule (reset={}, force_resend={})."
                 .format(reset, force_resend),
                 level="DEBUG")

        result = None
        if self.schedule:
            result = self.schedule.evaluate(self, self.app.datetime())
        if result is None:
            self.log("No suitable value found in schedule.",
                     level="DEBUG")
            return

        value, markers = result[:2]
        assert self.app.actor_type is not None
        if self.app.actor_type.values_equal(value, self._scheduled_value) and \
           not reset and not force_resend:
            self.log("Result didn't change, not setting it again.",
                     level="DEBUG")
            return

        previous_scheduled_value = self._scheduled_value
        self._scheduled_value = value

        if reset:
            self.cancel_rescheduling_timer()
            self._clear_overlay()
        elif expression_types.Mark.OVERLAY in markers:
            self._store_for_overlaying(previous_scheduled_value)
        elif self._overlaid_wanted_value is not None:
            overlaid_wanted_value = self._overlaid_wanted_value
            equal = self.app.actor_type.values_equal(
                value, self._overlaid_scheduled_value
            )
            delay = None  # type: T.Union[None, int, datetime.datetime]
            if self._overlaid_rescheduling_time:
                if self._overlaid_rescheduling_time > self.app.datetime():
                    delay = self._overlaid_rescheduling_time
            elif equal:
                delay = 0
            self._clear_overlay()
            if delay is not None:
                self.log("Restoring overlaid value.")
                self.set_value_manually(
                    value=overlaid_wanted_value, rescheduling_delay=delay
                )
                return
        elif self._rescheduling_timer:
            self.log("Not applying the schedule now due to a running "
                     "re-scheduling timer.",
                     level="DEBUG")
            return

        self.set_value(value, force_resend=force_resend)

    def cancel_rescheduling_timer(self) -> bool:
        """Cancels the re-scheduling timer for this room, if one
        exists.
        Returns whether a timer has been cancelled."""

        timer = self._rescheduling_timer
        if timer is None:
            return False

        self.app.cancel_timer(timer)
        self._rescheduling_time, self._rescheduling_timer = None, None
        self.log("Cancelled re-scheduling timer.", level="DEBUG")
        return True

    def eval_expr(
            self, expr: types.CodeType, now: datetime.datetime
    ) -> T.Any:
        """This is a wrapper around expression.eval_expr().
        It catches any exception raised during evaluation. In this case,
        the caught Exception object is returned."""

        try:
            return expression.eval_expr(expr, self, now)
        except Exception as err:  # pylint: disable=broad-except
            self.log("Error while evaluating expression: {}".format(repr(err)),
                     level="ERROR")
            return err

    @sync_proxy
    def initialize(self, reset: bool = False) -> None:
        """Should be called after all schedules and actors have been
        added in order to register state listeners and timers.
        If reset is True, the previous state won't be restored from Home
        Assistant and the schedule will be applied instead."""

        self.log("Initializing room (name={})."
                 .format(repr(self.name)),
                 level="DEBUG")

        for actor in self.actors:
            self._initialize_actor_cb({"actor": actor})

        if self.schedule:
            times = self.schedule.get_scheduling_times()
            for snippet in self.app.cfg["schedule_snippets"].values():
                times.update(snippet.get_scheduling_times())
            self.log("Registering scheduling timers at: {{{}}}"
                     .format(", ".join([str(_time) for _time in times])),
                     level="DEBUG")
            for _time in times:
                self.app.run_daily(self._scheduling_timer_cb, _time)
        else:
            self.log("No schedule configured.", level="DEBUG")

        if reset:
            self.apply_schedule(reset=True)
        else:
            self._restore_state()

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the room to log messages."""

        msg = "[{}] {}".format(self, msg)
        self.app.log(msg, *args, **kwargs)

    @sync_proxy
    def notify_set_value_event(
            self, expr_raw: str = None, value: T.Any = None,
            force_resend: bool = False,
            rescheduling_delay: T.Union[float, int, None] = None
    ) -> None:
        """Handles a schedy_set_value event for this room."""

        self.log("schedy_set_value event received, [{}] "
                 "[rescheduling_delay={}]"
                 .format("expression={}".format(repr(expr_raw)) \
                         if expr_raw is not None \
                         else "value={}".format(repr(value)),
                         rescheduling_delay),
                 prefix=common.LOG_PREFIX_INCOMING)
        self.set_value_manually(
            expr_raw=expr_raw, value=value, force_resend=force_resend,
            rescheduling_delay=rescheduling_delay
        )

    def notify_value_changed(
            self, actor: "ActorBase", value: T.Any
    ) -> None:
        """Should be called when an actor reports a value change.
        Handles change replication and re-scheduling timers."""

        if actor.is_sending:
            self.log("Not respecting value change from a sending actor.",
                     level="DEBUG")
            return
        if actor.gave_up_sending:
            self.log("Not respecting value change from an actor that "
                     "gave up sending.",
                     level="DEBUG")
            return

        actor_wanted = actor.wanted_value
        was_actor_wanted = actor_wanted is not None and \
                           actor.values_equal(value, actor_wanted)
        replicating = self.cfg["replicate_changes"]
        single_actor = len([a.is_initialized for a in self.actors]) == 1

        if was_actor_wanted:
            synced = all(actor.is_initialized and actor.is_synced
                         for actor in self.actors)
            if self.tracking_schedule and synced:
                self.cancel_rescheduling_timer()
        else:
            if not self.cfg["allow_manual_changes"]:
                if self._wanted_value is None:
                    self.log("Not rejecting manual value change by {} to "
                             "{} because we don't know what else to set."
                             .format(actor, repr(value)))
                else:
                    self.log("Rejecting manual value change by {} to {}."
                             .format(actor, repr(value)))
                    self.set_value(self._wanted_value)
                return

            if replicating:
                if not single_actor:
                    self.log("Propagating the change to all actors in the room.")
                self.set_value(value)

            if self.cfg["rescheduling_delay"] and \
               not (replicating and self.tracking_schedule):
                self.start_rescheduling_timer()

    def set_value(
            self, value: T.Any, force_resend: bool = False
    ) -> None:
        """Sets the given value for all actors in the room.
        Values won't be send to actors redundantly unless force_resend
        is True."""

        assert self.app.actor_type is not None
        scheduled = \
            self._scheduled_value is not None and \
            self.app.actor_type.values_equal(value, self._scheduled_value)

        self.log("Setting value to {}.  [{}{}]"
                 .format(repr(value),
                         "scheduled" if scheduled else "manual",
                         ", force re-sending" if force_resend else ""),
                 level="DEBUG")

        self._wanted_value = value

        changed = False
        for actor in self.actors:
            if not actor.is_initialized:
                self.log("Skipping uninitialized {}.".format(repr(actor)),
                         level="DEBUG")
                continue
            changed |= actor.set_value(value, force_resend=force_resend)[0]

        if changed:
            self.log("Value set to {}.  [{}]"
                     .format(repr(value),
                             "scheduled" if scheduled else "manual"),
                     prefix=common.LOG_PREFIX_OUTGOING)

    def set_value_manually(
            self, expr_raw: str = None, value: T.Any = None,
            force_resend: bool = False,
            rescheduling_delay: T.Union[
                float, int, datetime.datetime, datetime.timedelta
            ] = None
    ) -> None:
        """Evaluates the given expression or value and sets the result.
        An existing re-scheduling timer is cancelled and a new one is
        started if re-scheduling timers are configured.
        rescheduling_delay, if given, overwrites the value configured
        for the room. Passing 0 disables re-scheduling."""

        _checks = expr_raw is None, value is None
        if all(_checks) or not any(_checks):
            raise ValueError("specify exactly one of expr_raw and value")

        markers = set()
        now = self.app.datetime()
        if expr_raw is not None:
            expr = util.compile_expression(expr_raw)
            result = self.eval_expr(expr, now)
            self.log("Evaluated expression {} to {}."
                     .format(repr(expr_raw), repr(result)),
                     level="DEBUG")

            if isinstance(result, expression_types.Mark):
                markers.update(result.markers)
                result = result.result

            not_allowed_result_types = (
                expression_types.ControlResult,
                expression_types.PreliminaryResult,
                type(None), Exception,
            )
            value = None
            if isinstance(result, expression_types.IncludeSchedule):
                _result = result.schedule.evaluate(self, now)
                if _result is not None:
                    value = _result[0]
                    markers.update(_result[1])
            elif not isinstance(result, not_allowed_result_types):
                value = result

        if value is not None:
            value = self.validate_value(value)

        if value is None:
            self.log("Ignoring value.")
            return

        if expression_types.Mark.OVERLAY in markers:
            self._store_for_overlaying(self._scheduled_value)

        self.set_value(value, force_resend=force_resend)
        if rescheduling_delay != 0:
            self.start_rescheduling_timer(delay=rescheduling_delay)
        else:
            self.cancel_rescheduling_timer()

    def start_rescheduling_timer(
            self, delay: T.Union[
                float, int, datetime.datetime, datetime.timedelta
            ] = None
    ) -> None:
        """This method registers a re-scheduling timer according to the
        room's settings. delay, if given, overwrites the rescheduling_delay
        configured for the room. If there is a timer running already,
        it's replaced by a new one."""

        self.cancel_rescheduling_timer()

        if delay is None:
            delay = self.cfg["rescheduling_delay"]

        if isinstance(delay, (float, int)):
            delta = datetime.timedelta(minutes=delay)
            when = self.app.datetime() + delta
        elif isinstance(delay, datetime.datetime):
            delta = delay - self.app.datetime()
            when = delay
        elif isinstance(delay, datetime.timedelta):
            delta = delay
            when = self.app.datetime() + delay

        self.log("Re-applying the schedule not before {} (in {})."
                 .format(util.format_time(when.time()), delta))

        self._rescheduling_time, self._rescheduling_timer = when, self.app.run_at(
            self._rescheduling_timer_cb, when
        )

    @property
    def tracking_schedule(self) -> bool:
        """Returns whether the value wanted by this room is the scheduled
        one."""

        assert self.app.actor_type is not None
        return self._scheduled_value is not None and \
               self._wanted_value is not None and \
               self.app.actor_type.values_equal(
                   self._scheduled_value, self._wanted_value
               )
