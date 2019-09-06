"""
This module implements the Schedule and Rule classes.
"""

import typing as T

if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import types
    from .room import Room

import datetime
import functools

from cached_property import cached_property

from . import util
from . import expression


ScheduleEvaluationResultType = T.Tuple[T.Any, T.Set[str], "Rule"]


class Rule:
    """A rule that can be added to a schedule."""

    # names of schedule rule constraints to be fetched from a rule definition
    CONSTRAINTS = (
        "years",
        "months",
        "days",
        "weeks",
        "weekdays",
        "start_date",
        "end_date",
    )

    def __init__(  # pylint: disable=too-many-arguments
        self,
        name: str = None,
        start_time: datetime.time = None,
        start_plus_days: int = None,
        end_time: datetime.time = None,
        end_plus_days: int = None,
        constraints: T.Dict[str, T.Any] = None,
        expr: "types.CodeType" = None,
        expr_raw: str = None,
        value: T.Any = None,
    ) -> None:
        _checks = [expr is None, expr_raw is None]
        if any(_checks) and not all(_checks):
            raise ValueError("expr and expr_raw may only be passed together")
        if expr is not None and value is not None:
            raise ValueError("specify only one of expr and value, not both")

        self.name = name

        self.start_time = start_time
        self.start_plus_days = start_plus_days
        self.end_time = end_time
        self.end_plus_days = end_plus_days

        if constraints is None:
            constraints = {}
        self.constraints = constraints

        self.expr = expr
        self.expr_raw = expr_raw
        self.value = value

        # We cache constraint check results for the latest-checked 64 days
        self.check_constraints = functools.lru_cache(maxsize=64)(
            self._check_constraints
        )

    def __repr__(self) -> str:
        return "<Rule {}{}>".format(
            "{} ".format(repr(self.name)) if self.name is not None else "",
            ", ".join(self._get_repr_tokens()),
        )

    @staticmethod
    def _format_constraint(data: T.Any) -> str:
        """Formats constraint values for use in __repr__."""

        return str(data).replace(" ", "").replace("'", "")

    @staticmethod
    def _format_time(_time: datetime.time = None, days: int = None) -> str:
        """Formats time + shift days as a string for use in __repr__."""

        if _time is None:
            time_repr = "??:??"
        else:
            time_repr = _time.strftime("%H:%M:%S" if _time.second else "%H:%M")
        if days is None:
            days_repr = ""
        elif days < 0:
            days_repr = "{}d".format(days)
        else:
            days_repr = "+{}d".format(days)
        return "{}{}".format(time_repr, days_repr)

    def _get_repr_tokens(self) -> T.List[str]:
        """Returns a list of tokens to be shown in repr()."""

        tokens = []  # type: T.List[str]

        if (
            self.start_time is not None
            or self.start_plus_days is not None
            or self.end_time is not None
            or self.end_plus_days is not None
        ):
            times = "from {} to {}".format(
                self._format_time(self.start_time, self.start_plus_days),
                self._format_time(self.end_time, self.end_plus_days),
            )
            tokens.append(times)

        for constraint in sorted(self.constraints):
            tokens.append(
                "{}={}".format(
                    constraint, self._format_constraint(self.constraints[constraint])
                )
            )

        if self.expr_raw is not None:
            if len(self.expr_raw) > 43:
                tokens.append("x={}...".format(repr(self.expr_raw[:40])))
            else:
                tokens.append("x={}".format(repr(self.expr_raw)))

        if self.value is not None:
            tokens.append("v={}".format(repr(self.value)))

        return tokens

    def _check_constraints(self, date: datetime.date) -> bool:
        """Checks all constraints of this rule against the given date
        and returns whether they are fulfilled"""

        if not self.constraints:
            return True

        year, week, weekday = date.isocalendar()
        checks = {
            "years": lambda a: year in a,
            "months": lambda a: date.month in a,
            "days": lambda a: date.day in a,
            "weeks": lambda a: week in a,
            "weekdays": lambda a: weekday in a,
            "start_date": lambda a: date >= util.build_date_from_constraint(a, date, 1),
            "end_date": lambda a: date <= util.build_date_from_constraint(a, date, -1),
        }

        for constraint, allowed in self.constraints.items():
            if not checks[constraint](allowed):  # type: ignore
                return False
        return True


class RulePath:
    """A chain of rules starting from a root schedule through sub-schedule
    rules."""

    def __init__(self, root_schedule: "Schedule") -> None:
        self.root_schedule = root_schedule
        self.rules = []  # type: T.List[Rule]

    def __add__(self, other: "RulePath") -> "RulePath":
        """Creates a new RulePath with rules of self and another path.
        The paths have to fit together, meaning the root schedule of the other path
        must be the sub schedule of the rightmost rule of this path."""

        if (
            not isinstance(other, RulePath)
            or not self.rules
            or not isinstance(self.rules[-1], SubScheduleRule)
            or self.rules[-1].sub_schedule is not other.root_schedule
        ):
            raise ValueError("{!r} and {!r} don't fit together".format(self, other))

        path = self.copy()
        path.extend(other.rules)
        return path

    def __repr__(self) -> str:
        if not self.rules:
            return "<{}/empty rule path>".format(self.root_schedule)

        locs = []
        sched = self.root_schedule
        for rule in self.rules:
            if rule in sched.rules:
                loc = str(sched.rules.index(rule) + 1)
            else:
                loc = "?"
            locs.append(loc)
            if not isinstance(rule, SubScheduleRule):
                break
            sched = rule.sub_schedule

        return "<{}/{}:{}>".format(
            self.root_schedule,
            "/".join(locs),
            rule,  # pylint: disable=undefined-loop-variable
        )

    def _clear_cache(self) -> None:
        """Clears out all cached properties. For internal use only."""

        for attr in ("rules_with_expr_or_value", "times"):
            try:
                del self.__dict__[attr]
            except KeyError:
                pass

    def append(self, rule: Rule, clear_cache: bool = True) -> None:
        """Add's a rule to the end of the path.
        A ValueError is raised when the previous rule is a final rule."""

        if self.rules and not isinstance(self.rules[-1], SubScheduleRule):
            raise ValueError(
                "The previous rule in the path ({}) is no SubScheduleRule.".format(
                    self.rules[-1]
                )
            )

        self.rules.append(rule)

        if clear_cache:
            self._clear_cache()

    def copy(self) -> "RulePath":
        """Returns a mutable copy of this path."""

        path = type(self)(self.root_schedule)
        path.extend(self.rules)
        return path

    def extend(self, rules: T.Iterable[Rule]) -> None:
        """Appends each of the supplied rules to the path.
        If append() raises a ValueError for one of the rules to add, all rules already
        appended successfully are removed again before the exception is re-raised.
        Note: This method is not thread-safe!"""

        added = 0
        try:
            for rule in rules:
                self.append(rule, clear_cache=False)
                added += 1
        except ValueError:
            for _ in range(added):
                self.pop(clear_cache=False)
            added = 0
            raise
        finally:
            if added:
                self._clear_cache()

    def includes_schedule(self, schedule: "Schedule") -> bool:
        """Checks whether the given schedule is included in this path."""

        if schedule is self.root_schedule:
            return True

        for rule in self.rules:
            if isinstance(rule, SubScheduleRule) and rule.sub_schedule is schedule:
                return True
        return False

    def check_constraints(self, date: datetime.date) -> bool:
        """Checks constraints of all rules along this path against the
        given date and returns whether they are all fulfilled."""

        for rule in self.rules:
            if not rule.check_constraints(date):
                return False
        return True

    def is_active(self, when: datetime.datetime) -> bool:
        """Returns whether the rule this path leads to is active at
        given point in time."""

        _date, _time = when.date(), when.time()
        start_time, start_plus_days, end_time, end_plus_days = self.times

        # We first build a list of possible dates on which the path could start
        # being active, then we check whether one of these dates fulfills the path's
        # constraints.
        shift_list = list(range(end_plus_days + 1))
        # List isn't empty, 0 will always be included
        if _time >= end_time:
            # Don't check the most distant date, already ended earlier today
            del shift_list[-1]
        if shift_list and _time < start_time:
            # Today can't be the starting day, it's too early
            del shift_list[0]

        # Now check the constraints for each possible starting date
        for days_back in shift_list:
            start_date = _date - datetime.timedelta(days=days_back + start_plus_days)
            if not self.check_constraints(start_date):
                # Not starting this day, try next one
                continue
            # Found valid starting day, path is active now
            return True
        return False

    @property
    def is_final(self) -> bool:
        """Returns whether the last rule in the path is no SubScheduleRule."""

        if not self.rules:
            return False
        return not isinstance(self.rules[-1], SubScheduleRule)

    def pop(self, clear_cache: bool = True) -> Rule:
        """Removes and returns the rightmost rule of this path.
        IndexError is raised when there is no rule to pop."""

        try:
            rule = self.rules.pop()
        except IndexError:
            raise IndexError("no rule to pop")
        if clear_cache:
            self._clear_cache()
        return rule

    @cached_property
    def rules_with_expr_or_value(self) -> T.Tuple[Rule, ...]:
        """A tuple with rules of the path containing an expression or value,
        sorted from left to right."""

        return tuple(
            filter(lambda r: r.expr is not None or r.value is not None, self.rules)
        )

    @cached_property
    def times(self) -> T.Tuple[datetime.time, int, datetime.time, int]:
        """Returns (start_time, start_plus_days, end_time, end_plus_days) for this
        path. Rules are searched for these values from right to left.
        Missing times are assumed to be midnight. If not set explicitly, end_plus_days
        is 1 if start <= end else 0."""

        for rule in reversed(self.rules):
            if rule.start_time is not None:
                start_time = rule.start_time
                break
        else:
            start_time = datetime.time(0, 0)

        for rule in reversed(self.rules):
            if rule.start_plus_days is not None:
                start_plus_days = rule.start_plus_days
                break
        else:
            start_plus_days = 0

        for rule in reversed(self.rules):
            if rule.end_time is not None:
                end_time = rule.end_time
                break
        else:
            end_time = datetime.time(0, 0)

        for rule in reversed(self.rules):
            if rule.end_plus_days is not None:
                end_plus_days = rule.end_plus_days
                break
        else:
            end_plus_days = 1 if start_time >= end_time else 0

        return start_time, start_plus_days, end_time, end_plus_days


class SubScheduleRule(Rule):
    """A schedule rule with a sub-schedule attached."""

    def __init__(self, sub_schedule: "Schedule", *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)

        self.sub_schedule = sub_schedule

    def _get_repr_tokens(self) -> T.List[str]:
        """Adds the sub-schedule information to repr()."""

        tokens = super()._get_repr_tokens()
        tokens.insert(0, "with sub {}".format(self.sub_schedule))
        return tokens


class Schedule:
    """Holds the schedule for a room with all its rules."""

    def __init__(self, name: str = None, rules: T.Iterable[Rule] = None) -> None:
        self.name = name
        self.rules = []  # type: T.List[Rule]
        if rules is not None:
            self.rules.extend(rules)

    def __add__(self, other: "Schedule") -> "Schedule":
        if not isinstance(other, type(self)):
            raise ValueError(
                "{} objects may not be added to {}.".format(type(other), self)
            )
        return Schedule(name=self.name, rules=self.rules + other.rules)

    def __repr__(self) -> str:
        if self.name is None:
            return "<Schedule of {} rules>".format(len(self.rules))
        return "<Schedule {}>".format(repr(self.name))

    def evaluate(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
        self, room: "Room", when: datetime.datetime
    ) -> T.Optional[ScheduleEvaluationResultType]:
        """Evaluates the schedule, computing the value for the time the
        given datetime object represents. The resulting value, a set of
        markers applied to the value and the matching rule are returned.
        If no value could be found in the schedule (e.g. all rules
        evaluate to Next()), None is returned."""

        def log(msg: str, path: RulePath, *args: T.Any, **kwargs: T.Any) -> None:
            """Wrapper around room.log that prefixes spaces to the
            message based on the length of the rule path."""

            prefix = " " * 4 * max(0, len(path.rules) - 1) + "\u251c\u2500"
            room.log("{} {}".format(prefix, msg), *args, **kwargs)

        room.log("Assuming it to be {}.".format(when), level="DEBUG")

        expr_cache = {}  # type: T.Dict[types.CodeType, T.Any]
        expr_env = None
        markers = set()  # type: T.Set[str]
        postprocessors = []
        paths = list(self.unfolded)
        path_idx = 0
        while path_idx < len(paths):
            path = paths[path_idx]
            path_idx += 1

            last_rule = path.rules[-1]
            if isinstance(last_rule, SubScheduleRule):
                log("[SUB]  {}".format(path), path, level="DEBUG")
                continue
            elif not path.is_active(when):
                log("[INA]  {}".format(path), path, level="DEBUG")
                continue
            log("[ACT]  {}".format(path), path, level="DEBUG")

            result = None
            for rule in reversed(path.rules_with_expr_or_value):
                if rule.expr is not None:
                    plain_value = False
                    try:
                        result = expr_cache[rule.expr]
                    except KeyError:
                        if expr_env is None:
                            expr_env = expression.build_expr_env(room, when)
                        result = room.eval_expr(rule.expr, expr_env)
                        expr_cache[rule.expr] = result
                        log("=> {}".format(repr(result)), path, level="DEBUG")
                    else:
                        log(
                            "=> {}  [cache-hit]".format(repr(result)),
                            path,
                            level="DEBUG",
                        )
                    if isinstance(result, Exception):
                        room.log(
                            "Failed expression: {}".format(repr(rule.expr_raw)),
                            level="ERROR",
                        )
                elif rule.value is not None:
                    plain_value = True
                    result = rule.value
                    log("=> {}".format(repr(result)), path, level="DEBUG")

                # Unwrap a result with markers
                if isinstance(result, expression.types.Mark):
                    result = result.unwrap(markers)

                if isinstance(
                    result, expression.types.IncludeSchedule
                ) and path.includes_schedule(result.schedule):
                    # Prevent reusing IncludeSchedule results that would
                    # lead to a cycle. This happens when a rule of an
                    # included schedule returns Inherit() and the search
                    # then reaches the IncludeSchedule within the parent.
                    log(
                        "==   skipping in favour of the parent to prevent " "a cycle",
                        path,
                        level="DEBUG",
                    )
                    result = None
                elif result is None or isinstance(result, expression.types.Inherit):
                    log("==   skipping in favour of the parent", path, level="DEBUG")
                    result = None
                else:
                    break

            if result is None:
                room.log(
                    "No expression/value definition found, skipping {}.".format(path),
                    level="WARNING",
                )
            elif isinstance(result, Exception):
                room.log(
                    "Evaluation failed, skipping {}.".format(path), level="WARNING"
                )
            elif isinstance(result, expression.types.Abort):
                break
            elif isinstance(result, expression.types.Break):
                prefix_size = max(0, len(path.rules) - result.levels)
                prefix = path.rules[:prefix_size]
                log("== breaking out of {}".format(prefix), path, level="DEBUG")
                while (
                    path_idx < len(paths)
                    and paths[path_idx].root_schedule == path.root_schedule
                    and paths[path_idx].rules[:prefix_size] == prefix
                ):
                    del paths[path_idx]
            elif isinstance(result, expression.types.IncludeSchedule):
                # Replace the current rule with a dynamic SubScheduleRule
                _path = path.copy()
                _path.pop()
                _path.append(SubScheduleRule(result.schedule))
                paths.insert(path_idx, _path)
                for i, sub_path in enumerate(result.schedule.unfolded):
                    paths.insert(path_idx + i + 1, _path + sub_path)
            elif isinstance(result, expression.types.Postprocessor):
                if isinstance(result, expression.types.PostprocessorValueMixin):
                    value = room.validate_value(result.value)
                    if value is None:
                        room.log("Aborting schedule evaluation.", level="ERROR")
                        break
                    result.value = value
                postprocessors.append(result)
            elif isinstance(result, expression.types.Next):
                continue
            else:
                postprocessor_markers = set()  # type: T.Set[str]
                result = room.validate_value(result)
                if result is None and plain_value:
                    room.log(
                        "Maybe this is an expression? If so, set it "
                        "as the rule's 'expression' parameter "
                        "rather than as 'value'.",
                        level="WARNING",
                    )
                elif postprocessors:
                    room.log("Applying postprocessors.", level="DEBUG")
                    for postprocessor in postprocessors:
                        if result is None:
                            break
                        markers.update(postprocessor_markers)
                        postprocessor_markers.clear()
                        room.log("+ {}".format(repr(postprocessor)), level="DEBUG")
                        try:
                            result = postprocessor.apply(result)
                        except expression.types.PostprocessingError as err:
                            room.log(
                                "Error while applying {} to result {}: {}".format(
                                    repr(postprocessor), repr(result), err
                                ),
                                level="ERROR",
                            )
                            result = None
                            break
                        room.log("= {}".format(repr(result)), level="DEBUG")
                        if isinstance(result, expression.types.Mark):
                            result = result.unwrap(postprocessor_markers)
                        result = room.validate_value(result)

                if result is None:
                    room.log("Aborting schedule evaluation.", level="ERROR")
                    break
                markers.update(postprocessor_markers)

                room.log("Final result: {}".format(repr(result)), level="DEBUG")
                if markers:
                    room.log("Result markers: {}".format(markers), level="DEBUG")
                return result, markers, last_rule

        room.log("Found no result.", level="DEBUG")
        return None

    def get_next_scheduling_datetime(
        self, now: datetime.datetime
    ) -> T.Optional[datetime.datetime]:
        """Returns a datetime object with the time at which the next
        re-scheduling should be done. now should be a datetime object
        containing the current date and time.
        SubScheduleRule objects and their rules are considered as well.
        None is returned in case there are no rules in the schedule."""

        times = self.get_scheduling_times()
        if not times:
            # no rules in schedule
            return None

        current_time = now.time()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)

        def map_func(_time: datetime.time) -> datetime.datetime:
            """Maps a time object to a datetime containing the next
            occurrence of that time. Midnight transitions are handled
            correctly."""

            if _time <= current_time:
                # midnight transition
                return datetime.datetime.combine(tomorrow, _time)
            return datetime.datetime.combine(today, _time)

        return min(map(map_func, times))

    def get_scheduling_times(self) -> T.Set[datetime.time]:
        """Returns a set of times a re-scheduling should be triggered
        at. Rules of sub-schedules are considered as well."""

        times = set()  # type: T.Set[datetime.time]
        for path in self.unfolded:
            start_time, _, end_time, _ = path.times
            times.update((start_time, end_time))
        return times

    def unfolded_gen(self) -> T.Generator[RulePath, None, None]:
        """Implements recursive building of RulePath objects as a generator.
        It's like the unfolded property, but without being cached."""

        for rule in self.rules:
            path = RulePath(self)
            path.append(rule)
            yield path
            if isinstance(rule, SubScheduleRule):
                for sub_path in rule.sub_schedule.unfolded_gen():
                    yield path + sub_path

    @cached_property
    def unfolded(self) -> T.Tuple[RulePath, ...]:
        """Returns a tuple of rule paths.
        The last rule of a path may either be a SubScheduleRule (meaning
        the path leads to a node) or a Rule (meaning the path leads to
        a leaf). A node is returned first, followed by it's successors
        (like in depth-first search).
        NOTE: This is a cached property and only evaluated once."""

        return tuple(self.unfolded_gen())
