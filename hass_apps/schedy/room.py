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


class Room:
    """A room to be controlled by Schedy."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str, cfg: dict, app: "SchedyApp") -> None:
        self.name = name
        self.cfg = cfg
        self.app = app
        self.actors = []  # type: T.List[ActorBase]
        self.schedule = None  # type: T.Optional[schedule.Schedule]

        self.wanted_value = None  # type: T.Any
        self.scheduled_value = None  # type: T.Any
        self.reschedule_timer = None  # type: T.Optional[uuid.UUID]

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

    def _reschedule_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a re-schedule timer fires."""

        self.log("Re-schedule timer fired.",
                 level="DEBUG")
        self.reschedule_timer = None
        self.apply_schedule(force_reschedule=True)

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

    def apply_schedule(
            self, force_reschedule: bool = False, force_resend: bool = False
    ) -> None:
        """Sets the value that is configured for the current date and
        time.
        This method won't re-schedule if a re-schedule timer runs. It
        will also detect when the result hasn't changed compared to
        the last run and prevent re-setting it in that case. These both
        checks can be skipped by setting force_reschedule.
        force_resend is passed through to set_value()."""

        self.log("Applying room's schedule (force_reschedule={}, "
                 "force_resend={})."
                 .format(force_reschedule, force_resend),
                 level="DEBUG")

        if force_reschedule:
            self.cancel_reschedule_timer()
        elif self.reschedule_timer:
            self.log("Not scheduling now due to a running re-schedule "
                     "timer.",
                     level="DEBUG")
            return

        assert self.app.actor_type is not None

        result = self.get_scheduled_value()
        if result is None:
            self.log("No suitable value found in schedule.",
                     level="DEBUG")
            return

        value = result[0]
        if self.app.actor_type.values_equal(value, self.scheduled_value) and \
           not force_reschedule and not force_resend:
            self.log("Result didn't change, not setting it again.",
                     level="DEBUG")
            return

        self.scheduled_value = value
        try:
            self._set_sensor(
                "scheduled_value", self.app.actor_type.serialize_value(value)
            )
        except ValueError as err:
            self.log("Can't store scheduling result in HA: {}"
                     .format(err),
                     level="ERROR")

        self.set_value(value, scheduled=True, force_resend=force_resend)

    def cancel_reschedule_timer(self) -> bool:
        """Cancels the reschedule timer for this room, if one
        exists. Returns whether a timer has been cancelled."""

        timer = self.reschedule_timer
        if timer is None:
            return False

        self.app.cancel_timer(timer)
        self.reschedule_timer = None
        self.log("Cancelled re-schedule timer.", level="DEBUG")
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
    ) -> T.Optional[T.Tuple[T.Any, schedule.Rule]]:
        """Evaluates a schedule, computing the value for the time the
        given datetime object represents. The resulting value and the
        matched rule are returned.
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

        pre_results = []
        expr_cache = {}  # type: T.Dict[types.CodeType, T.Any]
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
                return result, last_rule

        self.log("Found no result.", level="DEBUG")
        return None

    def get_scheduled_value(self) -> T.Optional[T.Tuple[T.Any, schedule.Rule]]:
        """Computes and returns the value that is configured for the
        current date and time. The second return value is the rule which
        generated the result.
        If no value could be found in the schedule (e.g. all rules
        evaluate to Skip()), None is returned."""

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
            reschedule_delay: T.Union[float, int, None] = None
    ) -> None:
        """Handles a schedy_set_value event for this room."""

        self.log("schedy_set_value event received, {}"
                 .format(
                     "expression={}".format(repr(expr_raw)) \
                     if expr_raw is not None \
                     else "value={}".format(repr(value))
                 ))
        self.set_value_manually(
            expr_raw=expr_raw, value=value, force_resend=force_resend,
            reschedule_delay=reschedule_delay
        )

    def notify_value_changed(
            self, actor: "ActorBase", value: T.Any  # pylint: disable=unused-argument
    ) -> None:
        """Should be called when the value has been changed externally
        by manual adjustment at an actor."""

        if self.cfg["replicate_changes"] and len(self.actors) > 1:
            self.log("Propagating the change to all actors in the room.",
                     prefix=common.LOG_PREFIX_OUTGOING)
            self.set_value(value, scheduled=False)

        if actor.values_equal(value, self.wanted_value):
            self.cancel_reschedule_timer()
        elif self.cfg["reschedule_delay"]:
            self.start_reschedule_timer(restart=True)

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
            result = actor.set_value(value, force_resend=force_resend)
            changed = changed or bool(result)

        if changed:
            self.log("Value set to {}.  [{}]"
                     .format(repr(value),
                             "scheduled" if scheduled else "manual"),
                     prefix=common.LOG_PREFIX_OUTGOING)

    def set_value_manually(
            self, expr_raw: str = None, value: T.Any = None,
            force_resend: bool = False,
            reschedule_delay: T.Union[float, int, None] = None
    ) -> None:
        """Evaluates the given expression or value and sets the result.
        An existing re-schedule timer is cancelled and a new one is
        started if re-schedule timers are configured. reschedule_delay,
        if given, overwrites the value configured for the room."""

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
                value = self._validate_value(result.value)

        if value is None:
            self.log("Ignoring value.")
            return

        self.set_value(value, scheduled=False, force_resend=force_resend)
        self.start_reschedule_timer(
            reschedule_delay=reschedule_delay, restart=True
        )

    def start_reschedule_timer(
            self, reschedule_delay: T.Union[float, int, None] = None,
            restart: bool = False,
    ) -> bool:
        """This method registers a re-schedule timer according to the
        room's settings. reschedule_delay, if given, overwrites the value
        configured for the room. If there is a timer running already,
        no new one is started unless restart is set. The return value
        tells whether a timer has been started or not."""

        if self.reschedule_timer is not None:
            if restart:
                self.cancel_reschedule_timer()
            else:
                self.log("Re-schedule timer running already, starting no "
                         "second one.",
                         level="DEBUG")
                return False

        if reschedule_delay is None:
            reschedule_delay = self.cfg["reschedule_delay"]
        assert isinstance(reschedule_delay, (float, int))

        delta = datetime.timedelta(minutes=reschedule_delay)
        when = self.app.datetime() + delta
        self.log("Re-scheduling not before {} ({})."
                 .format(util.format_time(when.time()), delta))
        self.reschedule_timer = self.app.run_at(self._reschedule_timer_cb, when)

        return True
