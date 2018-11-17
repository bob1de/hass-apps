"""
This module implements the Room class.
"""

import types
import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from .app import SchedyApp
    from .actor.base import ActorBase

import datetime

from .. import common
from . import expression, schedule, util


SchedulingResultType = T.Optional[T.Tuple[T.Any, T.Set[str], schedule.Rule]]


class Room:
    """A room to be controlled by Schedy."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str, cfg: dict, app: "SchedyApp") -> None:
        self.name = name
        self.cfg = cfg
        self.app = app
        self.actors = []  # type: T.List[ActorBase]
        self.actor_wanted_values = {}  # type: T.Dict[ActorBase, T.Any]
        self.schedule = None  # type: T.Optional[schedule.Schedule]

        self.wanted_value = None  # type: T.Any
        self.scheduled_value = None  # type: T.Any
        self.overlaid_value = None  # type: T.Any
        self.overlaid_scheduled_value = None  # type: T.Any
        self.rescheduling_time = None  # type: T.Optional[datetime.datetime]
        self.rescheduling_timer = None  # type: T.Optional[uuid.UUID]

    def __repr__(self) -> str:
        return "<Room {}>".format(str(self))

    def __str__(self) -> str:
        return "R:{}".format(self.cfg.get("friendly_name", self.name))

    def _get_sensor(self, param: str) -> T.Any:
        """Returns the state value of the sensor for given parameter in HA."""

        entity_id = "sensor.schedy_{}_room_{}_{}" \
                    .format(self.app.name, self.name, param)
        self.log("Querying state of {}."
                 .format(repr(entity_id)),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
        state = self.app.get_state(entity_id)
        self.log("= {}".format(repr(state)),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
        return state

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
        if self.wanted_value is not None and \
           all([a.is_initialized for a in self.actors]):
            self.set_value(self.wanted_value, scheduled=False)

    def _rescheduling_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a re-scheduling timer fires.
        reset may be given in kwargs and is passed to apply_schedule()."""

        self.log("Re-scheduling timer fired.",
                 level="DEBUG")
        self.rescheduling_time, self.rescheduling_timer = None, None
        self.apply_schedule(reset=True)

    def _schedule_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a schedule timer fires."""

        self.log("Schedule timer fired.",
                 level="DEBUG")
        self.apply_schedule()

    def _set_sensor(self, param: str, state: T.Any) -> None:
        """Updates the sensor for given parameter in HA."""

        entity_id = "sensor.schedy_{}_room_{}_{}" \
                    .format(self.app.name, self.name, param)
        self.log("Setting state of {} to {}."
                 .format(repr(entity_id), repr(state)),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
        self.app.set_state(entity_id, state=state)

    def _validate_value(self, value: T.Any) -> T.Any:
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

    @util.synchronized
    def apply_schedule(
            self, reset: bool = False, force_resend: bool = False,
    ) -> None:
        """Sets the value that is configured for the current date and
        time.
        This method won't re-schedule if a re-schedule timer runs. It
        will also detect when the result hasn't changed compared to
        the last run and prevent re-setting it in that case. These both
        checks can be skipped by setting reset to True.
        force_resend is passed through to set_value()."""

        self.log("Applying room's schedule (reset={}, force_resend={})."
                 .format(reset, force_resend),
                 level="DEBUG")

        assert self.app.actor_type is not None

        result = self.get_scheduled_value()
        if result is None:
            self.log("No suitable value found in schedule.",
                     level="DEBUG")
            return

        value, markers = result[:2]
        if self.app.actor_type.values_equal(value, self.scheduled_value) and \
           not reset and not force_resend:
            self.log("Result didn't change, not setting it again.",
                     level="DEBUG")
            return

        previous_scheduled_value = self.scheduled_value
        self.scheduled_value = value
        try:
            self._set_sensor(
                "scheduled_value", self.app.actor_type.serialize_value(value)
            )
        except ValueError as err:
            self.log("Can't store scheduling result in HA: {}"
                     .format(err),
                     level="ERROR")

        if reset:
            self.cancel_rescheduling_timer()
        elif expression.Mark.OVERLAY in markers:
            if self.overlaid_value is None:
                self.overlaid_value = self.wanted_value
                self.overlaid_scheduled_value = previous_scheduled_value
                self.cancel_rescheduling_timer(reset=False)
        elif self.overlaid_value is not None:
            overlaid_value = self.overlaid_value
            equal = self.app.actor_type.values_equal(
                value, self.overlaid_scheduled_value
            )
            self.overlaid_value = None
            self.overlaid_scheduled_value = None
            delay = None  # type: T.Union[None, int, datetime.datetime]
            if self.rescheduling_time:
                if self.rescheduling_time < self.app.datetime():
                    delay = self.rescheduling_time
            elif equal:
                delay = 0
            if delay is not None:
                self.set_value_manually(
                    overlaid_value, rescheduling_delay=delay
                )
                return
        elif self.rescheduling_timer:
            self.log("Not scheduling now due to a running re-scheduling "
                     "timer.",
                     level="DEBUG")
            return

        self.set_value(value, scheduled=True, force_resend=force_resend)

    def cancel_rescheduling_timer(self, reset: bool = True) -> bool:
        """Cancels the re-scheduling timer for this room, if one
        exists.
        When reset is unset, the planned rescheduling time is not wiped
        upon timer cancellation.
        Returns whether a timer has been cancelled."""

        timer = self.rescheduling_timer
        if timer is None:
            return False

        self.app.cancel_timer(timer)
        self.rescheduling_timer = None
        if reset:
            self.rescheduling_time = None
        self.log("Cancelled re-scheduling timer.", level="DEBUG")
        return True

    def eval_expr(
            self, expr: types.CodeType
    ) -> T.Any:
        """This is a wrapper around expression.eval_expr that adds
        the room_name to the evaluation environment, as well as all
        configured expression_modules. It also catches any exception
        raised during evaluation. In this case, the caught Exception
        object is returned."""

        extra_env = {
            "room_name": self.name,
        }
        assert self.app.actor_type is not None
        self.app.actor_type.prepare_eval_environment(extra_env)

        try:
            return expression.eval_expr(expr, self.app, extra_env=extra_env)
        except Exception as err:  # pylint: disable=broad-except
            self.log("Error while evaluating expression: {}".format(repr(err)),
                     level="ERROR")
            return err

    def eval_schedule(  # pylint: disable=too-many-locals
            self, sched: schedule.Schedule, when: datetime.datetime
    ) -> SchedulingResultType:
        """Evaluates a schedule, computing the value for the time the
        given datetime object represents. The resulting value, a set of
        markers applied to the value and the matched rule are returned.
        If no value could be found in the schedule (e.g. all rules
        evaluate to Skip()), None is returned."""

        def insert_paths(
                paths: T.List[schedule.RulePath], first_index: int,
                path_prefix: schedule.RulePath,
                rules: T.Iterable[schedule.Rule]
        ) -> None:
            """Helper to append each single of a set of rules to a commmon
            path prefix and insert the resulting paths into a list."""

            for rule in rules:
                path = path_prefix.copy()
                path.add(rule)
                paths.insert(first_index, path)
                first_index += 1

        def log(
                msg: str, path: schedule.RulePath,
                *args: T.Any, **kwargs: T.Any
        ) -> None:
            """Wrapper around self.log that prefixes spaces to the
            message based on the length of the rule path."""

            prefix = " " * 3 * max(0, len(path.rules) - 1) + "\u251c\u2500"
            self.log("{} {}".format(prefix, msg), *args, **kwargs)

        self.log("Assuming it to be {}.".format(when),
                 level="DEBUG")

        rules = list(sched.get_matching_rules(when))
        self.log("{} / {} rules of {} are currently valid."
                 .format(len(rules), len(sched.rules), sched),
                 level="DEBUG")

        expr_cache = {}  # type: T.Dict[types.CodeType, T.Any]
        markers = set()
        pre_results = []
        paths = []  # type: T.List[schedule.RulePath]
        insert_paths(paths, 0, schedule.RulePath(sched), rules)
        path_idx = 0
        while path_idx < len(paths):
            path = paths[path_idx]
            path_idx += 1

            log("{}".format(path), path, level="DEBUG")

            last_rule = path.rules[-1]
            if isinstance(last_rule, schedule.SubScheduleRule):
                _rules = list(last_rule.sub_schedule.get_matching_rules(when))
                log("{} / {} rules of {} are currently valid."
                    .format(len(_rules), len(last_rule.sub_schedule.rules),
                            last_rule.sub_schedule),
                    path, level="DEBUG")
                insert_paths(paths, path_idx, path, _rules)
                continue

            result = None
            rules_with_expr_or_value = path.rules_with_expr_or_value
            for rule in reversed(rules_with_expr_or_value):
                if rule.expr is not None:
                    if rule.expr in expr_cache:
                        result = expr_cache[rule.expr]
                        log("=> {}  [cache-hit]".format(repr(result)),
                            path, level="DEBUG")
                    else:
                        result = self.eval_expr(rule.expr)
                        expr_cache[rule.expr] = result
                        log("=> {}".format(repr(result)),
                            path, level="DEBUG")
                elif rule.value is not None:
                    result = rule.value
                    log("=> {}".format(repr(result)),
                        path, level="DEBUG")
                if result is not None:
                    break

            if isinstance(result, expression.Mark):
                markers.update(result.markers)
                result = result.result

            if result is None:
                if rules_with_expr_or_value:
                    log("All expressions returned None, skipping rule.",
                        path, level="WARNING")
                else:
                    log("No expression/value definition found, skipping rule.",
                        path, level="WARNING")
            elif isinstance(result, Exception):
                log("Evaluation failed, skipping rule.",
                    path, level="DEBUG")
            elif isinstance(result, expression.Abort):
                break
            elif isinstance(result, expression.Break):
                prefix_size = max(0, len(path.rules) - result.levels)
                prefix = path.rules[:prefix_size]
                while path_idx < len(paths) and \
                      paths[path_idx].root_schedule == path.root_schedule and \
                      paths[path_idx].rules[:prefix_size] == prefix:
                    del paths[path_idx]
            elif isinstance(result, expression.IncludeSchedule):
                _rules = list(result.schedule.get_matching_rules(when))
                log("{} / {} rules of {} are currently valid."
                    .format(len(_rules), len(result.schedule.rules),
                            result.schedule),
                    path, level="DEBUG")
                _path = path.copy()
                del _path.rules[-1]
                _path.add(schedule.SubScheduleRule(result.schedule))
                insert_paths(paths, path_idx, _path, _rules)
            elif isinstance(result, expression.PreliminaryResult):
                if isinstance(result, expression.PreliminaryValidationMixin):
                    value = self._validate_value(result.value)
                    if value is None:
                        self.log("Aborting scheduling",
                                 level="ERROR")
                        break
                    result.value = value
                pre_results.append(result)
            elif isinstance(result, expression.Skip):
                continue
            else:
                result = self._validate_value(result)
                for pre_result in pre_results:
                    if result is None:
                        break
                    log("+ {}".format(repr(pre_result)),
                        path, level="DEBUG")
                    try:
                        result = pre_result.combine_with(result)
                    except expression.PreliminaryCombiningError as err:
                        self.log("Error while combining {} with result {}: {}"
                                 .format(repr(pre_result), repr(result), err),
                                 level="ERROR")
                        result = None
                        break
                    log("= {}".format(repr(result)),
                        path, level="DEBUG")
                    result = self._validate_value(result)
                if result is None:
                    self.log("Aborting scheduling",
                             level="ERROR")
                    break
                self.log("Final result: {}".format(repr(result)),
                         level="DEBUG")
                return result, markers, last_rule

        self.log("Found no result.", level="DEBUG")
        return None

    def get_scheduled_value(self) -> SchedulingResultType:
        """Computes and returns the value that is configured for the
        current date and time."""

        if self.schedule is None:
            return None
        return self.eval_schedule(self.schedule, self.app.datetime())

    def initialize(self) -> None:
        """Should be called after all schedules and actors have been
        added in order to register state listeners and timers."""

        self.log("Initializing room (name={})."
                 .format(repr(self.name)),
                 level="DEBUG")

        _scheduled_value = self._get_sensor("scheduled_value")
        assert self.app.actor_type is not None
        try:
            self.scheduled_value = self.app.actor_type.validate_value(
                self.app.actor_type.deserialize_value(_scheduled_value)
            )
        except ValueError:
            self.log("Last scheduled value is unknown.",
                     level="DEBUG")
        else:
            self.log("Last scheduled value was {}."
                     .format(repr(self.scheduled_value)),
                     level="DEBUG")

        for actor in self.actors:
            self._initialize_actor_cb({"actor": actor})

        if self.schedule:
            times = self.schedule.get_scheduling_times()
            self.log("Registering scheduling timers at: {{{}}}"
                     .format(", ".join([str(_time) for _time in times])),
                     level="DEBUG")
            for _time in times:
                self.app.run_daily(self._schedule_timer_cb, _time)
        else:
            self.log("No schedule configured.", level="DEBUG")

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the room to log messages."""

        msg = "[{}] {}".format(self, msg)
        self.app.log(msg, *args, **kwargs)

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
        """Should be called when the value has been changed externally
        by manual adjustment at an actor."""

        if self.cfg["replicate_changes"] and len(self.actors) > 1:
            self.log("Propagating the change to all actors in the room.",
                     prefix=common.LOG_PREFIX_OUTGOING)
            self.set_value(value, scheduled=False)

        wanted = self.actor_wanted_values.get(actor)
        if wanted is not None and actor.values_equal(value, wanted):
            self.cancel_rescheduling_timer()
        elif self.cfg["rescheduling_delay"]:
            self.start_rescheduling_timer()

    def set_value(
            self, value: T.Any, scheduled: bool = False,
            force_resend: bool = False
    ) -> None:
        """Sets the given value for all actors in the room.
        Values won't be send to actors redundantly unless force_resend
        is True."""

        self.log("Setting value to {}.  [{}{}]"
                 .format(repr(value),
                         "scheduled" if scheduled else "manual",
                         ", force re-sending" if force_resend else ""),
                 level="DEBUG")

        self.wanted_value = value

        changed = False
        for actor in filter(lambda a: a.is_initialized, self.actors):
            _changed, self.actor_wanted_values[actor] = actor.set_value(
                value, force_resend=force_resend
            )
            if _changed:
                changed = True

        if changed:
            self.log("Value set to {}.  [{}]"
                     .format(repr(value),
                             "scheduled" if scheduled else "manual"),
                     prefix=common.LOG_PREFIX_OUTGOING)

    def set_value_manually(
            self, expr_raw: str = None, value: T.Any = None,
            force_resend: bool = False,
            rescheduling_delay: T.Union[
                float, int, datetime.datetime, datetime.timedelta, None
            ] = None
    ) -> None:
        """Evaluates the given expression or value and sets the result.
        An existing re-schedule timer is cancelled and a new one is
        started if re-scheduling timers are
        configured. rescheduling_delay, if given, overwrites the value
        configured for the room."""

        checks = (expr_raw is None, value is None)
        assert any(checks) and not all(checks), \
            "specify exactly one of expr_raw and value"

        if expr_raw is not None:
            expr = util.compile_expression(expr_raw)
            result = self.eval_expr(expr)
            self.log("Evaluated expression {} to {}."
                     .format(repr(expr_raw), repr(result)),
                     level="DEBUG")

            not_allowed_result_types = (
                expression.ControlResult, expression.PreliminaryResult,
                type(None), Exception,
            )
            value = None
            if isinstance(result, expression.IncludeSchedule):
                _result = self.eval_schedule(result.schedule, self.app.datetime())
                if _result is not None:
                    value = _result[0]
            elif not isinstance(result, not_allowed_result_types):
                value = result.value

        if value is not None:
            value = self._validate_value(value)

        if value is None:
            self.log("Ignoring value.")
            return

        self.set_value(value, scheduled=False, force_resend=force_resend)
        if rescheduling_delay is None:
            self.cancel_rescheduling_timer()
        else:
            self.start_rescheduling_timer(delay=rescheduling_delay)

    def start_rescheduling_timer(
            self, delay: T.Union[
                float, int, datetime.datetime, datetime.timedelta, None
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

        self.rescheduling_time, self.rescheduling_timer = when, self.app.run_at(
            self._rescheduling_timer_cb, when
        )
