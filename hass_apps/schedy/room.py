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
import os
import sys
import threading
import traceback

from .. import common
from . import expression, util


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
        self._overlay_active = False
        self._overlaid_wanted_value = None  # type: T.Any
        self._overlaid_scheduled_value = None  # type: T.Any
        self._overlaid_rescheduling_time = None  # type: T.Optional[datetime.datetime]

        self._last_state = None  # type: T.Optional[T.Tuple[str, T.Dict[str, T.Any]]]

        self._sync_proxy_lock = threading.RLock()
        self._sync_proxy_running = False
        self._timer_lock = threading.RLock()

        self._reevaluation_timer = None  # type: T.Optional[uuid.UUID]

    def __repr__(self) -> str:
        return "<Room {}>".format(str(self))

    def __str__(self) -> str:
        return "R:{}".format(self.cfg.get("friendly_name", self.name))

    def _clear_overlay(self) -> None:
        """Removes all stored overlay state."""

        self._overlay_active = False
        self._overlaid_wanted_value = None
        self._overlaid_scheduled_value = None
        self._overlaid_rescheduling_time = None

    @sync_proxy
    def _initialize_actor_cb(self, kwargs: dict) -> None:
        """Is called for each actor until it's initialized successfully."""

        actor = kwargs["actor"]
        if not actor.initialize():
            self.log(
                "Actor {} couldn't be initialized, "
                "retrying in 10 seconds.".format(repr(actor)),
                level="WARNING",
            )
            self.app.run_in(self._initialize_actor_cb, 10, actor=actor)
            return

        actor.events.on("value_changed", self.notify_value_changed)
        if (
            self._wanted_value is not None
            and self.cfg["replicate_changes"]
            and all([a.is_initialized for a in self.actors])
        ):
            self.set_value(self._wanted_value)

    def _restore_state(self) -> None:
        """Restores a stored state from Home Assistant and.applies it.
        If no state was found, the schedule is just applied."""

        def _deserialize(value: T.Any) -> T.Any:
            if value is None:
                return None
            assert self.app.actor_type is not None
            return self.app.actor_type.deserialize_value(value)

        def _deserialize_dt(value: T.Any) -> T.Optional[datetime.datetime]:
            if not isinstance(value, (float, int)):
                return None
            return datetime.datetime.fromtimestamp(value)

        entity_id = self._state_entity_id
        self.log(
            "Loading state of {} from Home Assistant.".format(repr(entity_id)),
            level="DEBUG",
            prefix=common.LOG_PREFIX_OUTGOING,
        )
        state = self.app.get_state(entity_id, attribute="all")
        self.log(
            "  = {}".format(repr(state)),
            level="DEBUG",
            prefix=common.LOG_PREFIX_INCOMING,
        )

        reset = False
        if isinstance(state, dict):
            attrs = state.get("attributes", {})
            actor_wanted_values = attrs.get("actor_wanted_values", {})
            for entity_id, value in actor_wanted_values.items():
                value = _deserialize(value)
                for actor in self.actors:
                    if actor.entity_id == entity_id:
                        actor.wanted_value = value
            self._wanted_value = _deserialize(state.get("state") or None)
            self._scheduled_value = _deserialize(attrs.get("scheduled_value"))
            self._rescheduling_time = _deserialize_dt(attrs.get("rescheduling_time"))
            self._overlay_active = attrs.get("overlay_active") or False
            self._overlaid_wanted_value = _deserialize(
                attrs.get("overlaid_wanted_value")
            )
            self._overlaid_scheduled_value = _deserialize(
                attrs.get("overlaid_scheduled_value")
            )
            self._overlaid_rescheduling_time = _deserialize_dt(
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

        self.log("Re-scheduling timer fired.", level="DEBUG")
        with self._timer_lock:
            self._rescheduling_time = None
            self._rescheduling_timer = None
        self.apply_schedule(reset=True)

    @sync_proxy
    def _scheduling_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a scheduling timer fires."""

        self.log("Scheduling timer fired.", level="DEBUG")
        self.apply_schedule()

    @property
    def _state_entity_id(self) -> str:
        """Generates the entity id for storing this room's state as."""

        return "schedy_room.{}_{}".format(self.app.name, self.name)

    def _store_for_overlaying(self) -> None:
        """This method is called before a value overlay is put into place.
        It stores the scheduled and wanted value together with the re-scheduling
        time for later restoration. A running re-scheduling timer is cancelled.
        If an overlay is active already, this does nothing."""

        if self._overlay_active:
            # Don't overwrite existing restoration records
            return

        self.log("Storing value {!r} before overlaying.".format(self._wanted_value))
        self._overlay_active = True
        self._overlaid_wanted_value = self._wanted_value
        self._overlaid_scheduled_value = self._scheduled_value
        self._overlaid_rescheduling_time = self._rescheduling_time
        self.cancel_rescheduling_timer()

    def _update_state(self) -> None:
        """Update the room's state in Home Assistant."""

        D = T.TypeVar("D")

        def _serialize(value: T.Any, default: D) -> T.Union[str, D]:
            if value is None:
                return default
            assert self.app.actor_type is not None
            return self.app.actor_type.serialize_value(value)

        def _serialize_dt(value: T.Optional[datetime.datetime]) -> T.Optional[float]:
            if value is None:
                return None
            return value.timestamp()

        def _maybe_add(key: str, value: T.Any) -> None:
            if value is not None:
                attrs[key] = value

        state = _serialize(self._wanted_value, "")
        attrs = {
            "actor_wanted_values": {
                actor.entity_id: _serialize(actor.wanted_value, None)
                for actor in self.actors
            },
            "scheduled_value": _serialize(self._scheduled_value, None),
            "rescheduling_time": _serialize_dt(self._rescheduling_time),
            "overlay_active": self._overlay_active,
        }  # type: T.Dict[str, T.Any]
        _maybe_add(
            "overlaid_wanted_value", _serialize(self._overlaid_wanted_value, None)
        )
        _maybe_add(
            "overlaid_scheduled_value", _serialize(self._overlaid_scheduled_value, None)
        )
        _maybe_add(
            "overlaid_rescheduling_time",
            _serialize_dt(self._overlaid_rescheduling_time),
        )
        _maybe_add("friendly_name", self.cfg.get("friendly_name"))

        unchanged = (state, attrs) == self._last_state
        if unchanged:
            self.log(
                "Unchanged HA state: state={}, attributes={}".format(
                    repr(state), attrs
                ),
                level="DEBUG",
            )
            return
        self.log(
            "Sending state to HA: state={}, attributes={}".format(repr(state), attrs),
            level="DEBUG",
            prefix=common.LOG_PREFIX_OUTGOING,
        )

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
            self.log(
                "Invalid value {} for actor type {}: {}".format(
                    repr(value), repr(self.app.actor_type.name), err
                ),
                level="ERROR",
            )
            return None
        return value

    @sync_proxy
    def apply_schedule(self, reset: bool = False, force_resend: bool = False) -> None:
        """Applies the value scheduled for the current date and time.
        It detects when the result hasn't changed compared to the last
        run and prevent re-setting it in that case.
        This method will also not re-apply the schedule if a re-schedule
        timer runs - however, the OVERLAY marker is regarded.
        These both checks can be skipped by setting reset to True.
        force_resend is passed through to set_value()."""

        def _restore_overlaid_value() -> bool:
            """Restores and clears an overlaid value.
            Returns whether a value has actually been restored or not."""

            overlaid_wanted_value = self._overlaid_wanted_value
            if overlaid_wanted_value is None:
                self.log(
                    "Overlay ended but knowing no value to restore.", level="WARNING"
                )
                self._clear_overlay()
                return False

            delay = None  # type: T.Union[None, int, datetime.datetime]
            if not self._overlaid_rescheduling_time:
                if new_scheduled_value == self._overlaid_scheduled_value:
                    # Scheduled value hasn't changed compared to before overlay,
                    # hence revert to overlaid wanted value without timer
                    delay = 0
            elif self._overlaid_rescheduling_time > self.app.datetime():
                # Resume overlaid re-scheduling timer
                delay = self._overlaid_rescheduling_time
            else:
                self.log(
                    "Overlaid value {!r} has expired, not restoring it.".format(
                        overlaid_wanted_value
                    )
                )

            self._clear_overlay()
            if delay is None:
                return False
            self.log("Restoring overlaid value {}.".format(repr(overlaid_wanted_value)))
            self.set_value_manually(
                value=overlaid_wanted_value, rescheduling_delay=delay
            )
            return True

        self.log(
            "Evaluating room's schedule (reset={}, force_resend={}).".format(
                reset, force_resend
            ),
            level="DEBUG",
        )

        result = None
        if self.schedule:
            result = self.schedule.evaluate(self, self.app.datetime())
        if result is None:
            self.log("No suitable value found in schedule.", level="DEBUG")
            # revert an eventual overlay
            if self._overlay_active:
                new_scheduled_value = self._overlaid_scheduled_value
                _restore_overlaid_value()
                self._scheduled_value = new_scheduled_value
            return

        new_scheduled_value, markers = result[:2]
        if not (new_scheduled_value != self._scheduled_value or reset or force_resend):
            self.log("Result didn't change, not setting it again.", level="DEBUG")
            return

        if reset:
            self.cancel_rescheduling_timer()
            self._clear_overlay()
        elif expression.types.Mark.OVERLAY in markers:
            # Create restoration records if overlay not active already
            self._store_for_overlaying()
        # No overlay should be set, hence try to revert an existing one
        elif self._overlay_active and _restore_overlaid_value():
            self._scheduled_value = new_scheduled_value
            return
        elif self._rescheduling_timer:
            self.log(
                "Not applying the schedule now due to a running "
                "re-scheduling timer.",
                level="DEBUG",
            )
            return

        self._scheduled_value = new_scheduled_value
        self.set_value(new_scheduled_value, force_resend=force_resend)

    def cancel_rescheduling_timer(self) -> bool:
        """Cancels the re-scheduling timer for this room, if one
        exists.
        Returns whether a timer has been cancelled."""

        with self._timer_lock:
            timer = self._rescheduling_timer
            if timer is None:
                return False
            self.app.cancel_timer(timer)
            self._rescheduling_time = None
            self._rescheduling_timer = None

        self.log("Cancelled re-scheduling timer.", level="DEBUG")
        return True

    def eval_expr(self, expr: types.CodeType, env: T.Dict[str, T.Any]) -> T.Any:
        """This is a wrapper around expression.eval_expr().
        It catches and logs any exception raised during evaluation. In
        this case, the caught Exception object is returned."""

        try:
            return expression.eval_expr(expr, env)
        except Exception as err:  # pylint: disable=broad-except
            self.log("Error while evaluating expression:", level="ERROR")
            tb_exc = traceback.TracebackException(*sys.exc_info())  # type: ignore
            while tb_exc.stack and tb_exc.stack[0].filename != "expression":
                del tb_exc.stack[0]
            for line in tb_exc.format():
                self.log(line.rstrip(os.linesep), level="ERROR")
            return err

    @sync_proxy
    def initialize(self, reset: bool = False) -> None:
        """Should be called after all schedules and actors have been
        added in order to register state listeners and timers.
        If reset is True, the previous state won't be restored from Home
        Assistant and the schedule will be applied instead."""

        self.log("Initializing room (name={}).".format(repr(self.name)), level="DEBUG")

        for actor in self.actors:
            self._initialize_actor_cb({"actor": actor})

        assert self.schedule is not None
        times = self.schedule.get_scheduling_times()
        for snippet in self.app.cfg["schedule_snippets"].values():
            times.update(snippet.get_scheduling_times())
        self.log(
            "Registering scheduling timers at: [{}]".format(
                ", ".join(str(_time) for _time in sorted(times))
            ),
            level="DEBUG",
        )
        for _time in times:
            self.app.run_daily(self._scheduling_timer_cb, _time)

        if reset:
            self.apply_schedule(reset=True)
        else:
            self._restore_state()

        for definition in self.cfg["watched_entities"]:
            self.app.watch_entity(definition, [self])

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the room to log messages."""

        msg = "[{}] {}".format(self, msg)
        self.app.log(msg, *args, **kwargs)

    @sync_proxy
    def notify_set_value_event(
        self,
        expr_raw: str = None,
        value: T.Any = None,
        force_resend: bool = False,
        rescheduling_delay: T.Union[float, int, None] = None,
    ) -> None:
        """Handles a schedy_set_value event for this room."""

        self.log(
            "schedy_set_value event received, [{}] "
            "[rescheduling_delay={}]".format(
                "expression={}".format(repr(expr_raw))
                if expr_raw is not None
                else "value={}".format(repr(value)),
                rescheduling_delay,
            ),
            prefix=common.LOG_PREFIX_INCOMING,
        )
        self.set_value_manually(
            expr_raw=expr_raw,
            value=value,
            force_resend=force_resend,
            rescheduling_delay=rescheduling_delay,
        )

    def notify_value_changed(self, actor: "ActorBase", value: T.Any) -> None:
        """Should be called when an actor reports a value change.
        Handles change replication and re-scheduling timers."""

        if actor.is_sending:
            self.log("Not respecting value change from a sending actor.", level="DEBUG")
            return
        if actor.gave_up_sending:
            self.log(
                "Not respecting value change from an actor that " "gave up sending.",
                level="DEBUG",
            )
            return

        actor_wanted = actor.wanted_value
        was_actor_wanted = actor_wanted is not None and value == actor_wanted
        replicating = self.cfg["replicate_changes"]
        single_actor = len([a.is_initialized for a in self.actors]) == 1

        if was_actor_wanted:
            synced = all(
                actor.is_initialized and actor.is_synced for actor in self.actors
            )
            if self.tracking_schedule and synced:
                self.cancel_rescheduling_timer()
        else:
            if not self.cfg["allow_manual_changes"]:
                if self._wanted_value is None:
                    self.log(
                        "Not rejecting manual value change by {} to "
                        "{} because we don't know what else to set.".format(
                            actor, repr(value)
                        )
                    )
                else:
                    self.log(
                        "Rejecting manual value change by {} to {}.".format(
                            actor, repr(value)
                        )
                    )
                    self.set_value(self._wanted_value)
                return

            if replicating:
                if not single_actor:
                    self.log("Propagating the change to all actors in the room.")
                self.set_value(value)

            if self.cfg["rescheduling_delay"] and not (
                replicating and self.tracking_schedule
            ):
                self.start_rescheduling_timer()

    def set_value(self, value: T.Any, force_resend: bool = False) -> None:
        """Sets the given value for all actors in the room.
        Values won't be send to actors redundantly unless force_resend
        is True."""

        scheduled = self._scheduled_value is not None and value == self._scheduled_value

        self.log(
            "Setting value to {}.  [{}{}]".format(
                repr(value),
                "scheduled" if scheduled else "manual",
                ", force re-sending" if force_resend else "",
            ),
            level="DEBUG",
        )

        self._wanted_value = value

        changed = False
        for actor in self.actors:
            if not actor.is_initialized:
                self.log(
                    "Skipping uninitialized {}.".format(repr(actor)), level="DEBUG"
                )
                continue
            changed |= actor.set_value(value, force_resend=force_resend)[0]

        if changed:
            self.log(
                "Value set to {}.  [{}]".format(
                    repr(value), "scheduled" if scheduled else "manual"
                ),
                prefix=common.LOG_PREFIX_OUTGOING,
            )

    def set_value_manually(
        self,
        expr_raw: str = None,
        value: T.Any = None,
        force_resend: bool = False,
        rescheduling_delay: T.Union[
            float, int, datetime.datetime, datetime.timedelta
        ] = None,
    ) -> None:
        """Evaluates the given expression or value and sets the result.
        An existing re-scheduling timer is cancelled and a new one is
        started if re-scheduling timers are configured.
        rescheduling_delay, if given, overwrites the value configured
        for the room. Passing 0 disables re-scheduling."""

        _checks = expr_raw is None, value is None
        if all(_checks) or not any(_checks):
            raise ValueError("specify exactly one of expr_raw and value")

        markers = set()  # type: T.Set[str]
        now = self.app.datetime()
        if expr_raw is not None:
            try:
                expr = util.compile_expression(expr_raw)
            except SyntaxError:
                for line in traceback.format_exc(limit=0):
                    self.log(line.rstrip(os.linesep), level="ERROR")
                self.log("Failed expression: {}".format(repr(expr_raw)), level="ERROR")
                return
            env = expression.build_expr_env(self, now)
            result = self.eval_expr(expr, env)
            self.log(
                "Evaluated expression {} to {}.".format(repr(expr_raw), repr(result)),
                level="DEBUG",
            )

            if isinstance(result, Exception):
                self.log("Failed expression: {}".format(repr(expr_raw)), level="ERROR")
                return

            if isinstance(result, expression.types.Mark):
                result = result.unwrap(markers)

            not_allowed_result_types = (
                expression.types.ControlResult,
                expression.types.Postprocessor,
                type(None),
            )
            value = None
            if isinstance(result, expression.types.IncludeSchedule):
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

        if expression.types.Mark.OVERLAY in markers:
            self._store_for_overlaying()

        self.set_value(value, force_resend=force_resend)
        if rescheduling_delay != 0:
            self.start_rescheduling_timer(delay=rescheduling_delay)
        else:
            self.cancel_rescheduling_timer()

    def start_rescheduling_timer(
        self, delay: T.Union[float, int, datetime.datetime, datetime.timedelta] = None
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

        self.log(
            "Re-applying the schedule not before {} (in {}).".format(
                util.format_time(when.time()), delta
            )
        )

        with self._timer_lock:
            self._rescheduling_time = when
            self._rescheduling_timer = self.app.run_at(
                self._rescheduling_timer_cb, when
            )

    @property
    def tracking_schedule(self) -> bool:
        """Returns whether the value wanted by this room is the scheduled
        one."""

        return (
            self._scheduled_value is not None
            and self._wanted_value is not None
            and self._scheduled_value == self._wanted_value
        )

    def trigger_reevaluation(self, reset: bool = False) -> None:
        """Initializes a schedule re-evaluation in 1 second.
        The reset parameter is passed through to apply_schedule()."""

        def _reevaluation_cb(*args: T.Any, **kwargs: T.Any) -> None:
            with self._timer_lock:
                self._reevaluation_timer = None
            self.apply_schedule(reset=reset)

        with self._timer_lock:
            if self._reevaluation_timer:
                if reset:
                    self.app.cancel_timer(self._reevaluation_timer)
                else:
                    self.log("Re-evaluation pending, doing nothing.", level="DEBUG")
                    return

            self.log(
                "Doing schedule re-evaluation in 1 second [reset={}]".format(reset),
                level="DEBUG",
            )
            self._reevaluation_timer = self.app.run_in(_reevaluation_cb, 1)
