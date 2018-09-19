"""
This module implements the Schedule and Rule classes.
"""

import typing as T

import datetime

from . import expr, util


class Rule:
    """A rule that can be added to a schedule."""

    # names of schedule rule constraints to be fetched from a rule definition
    CONSTRAINTS = ("years", "months", "days", "weeks", "weekdays",
                   "start_date", "end_date")

    def __init__(
            self, name: str = None,
            start_time: datetime.time = None, end_time: datetime.time = None,
            end_plus_days: int = None, constraints: T.Dict[str, T.Any] = None,
            temp_expr: expr.ExprType = None,
        ) -> None:

        self.name = name

        midnight = datetime.time(0, 0)
        if start_time is None:
            start_time = midnight
        self.start_time = start_time

        if end_time is None:
            end_time = midnight
        self.end_time = end_time

        if end_plus_days is None:
            end_plus_days = 1 if end_time <= start_time else 0
        self.end_plus_days = end_plus_days

        if constraints is None:
            constraints = {}
        self.constraints = constraints

        # try to simplify the rule
        if self.is_always_valid:
            self.start_time = midnight
            self.end_time = midnight
            self.end_plus_days = 1

        self.temp_expr = None  # type: T.Optional[expr.ExprType]
        self.temp_expr_raw = None  # type: T.Optional[expr.ExprType]
        if temp_expr is not None:
            if isinstance(temp_expr, str):
                temp_expr = temp_expr.strip()
            self.temp_expr_raw = temp_expr
            try:
                temp = expr.Temp(temp_expr)
            except ValueError:
                # this is a temperature expression, precompile it
                self.temp_expr = compile(temp_expr, "temp_expr", "eval")  # type: expr.ExprType
            else:
                self.temp_expr = temp

    def __repr__(self) -> str:
        return "<Rule {}{}>".format(
            "{} ".format(repr(self.name)) if self.name is not None else "",
            ", ".join(self._get_repr_tokens())
        )

    def _get_repr_tokens(self) -> T.List[str]:
        """Returns a list of tokens to be shown in repr()."""

        tokens = []  # type: T.List[str]

        midnight = datetime.time(0, 0)
        if self.start_time != midnight or self.end_time != midnight:
            fmt_t = lambda t: t.strftime("%H:%M:%S" if t.second else "%H:%M")  # type: T.Callable[[datetime.time], str]
            times = "from {} to {}".format(
                fmt_t(self.start_time), fmt_t(self.end_time)
            )
            if self.end_plus_days:
                times += "+{}d".format(self.end_plus_days)
            tokens.append(times)
        elif self.end_plus_days > 1:
            tokens.append("+{}d".format(self.end_plus_days - 1))

        fmt_c = lambda x: str(x).replace(" ", "").replace("'", "")  # type: T.Callable[[T.Any], str]
        for constraint in sorted(self.constraints):
            tokens.append("{}={}".format(
                constraint, fmt_c(self.constraints[constraint])
            ))

        if self.temp_expr_raw is not None:
            tokens.append("temp={}".format(repr(self.temp_expr_raw)))

        return tokens

    def check_constraints(self, date: datetime.date) -> bool:
        """Checks all constraints of this rule against the given date
        and returns whether they are fulfilled"""

        # pylint: disable=too-many-return-statements

        year, week, weekday = date.isocalendar()
        for constraint, allowed in self.constraints.items():
            if constraint == "years" and year not in allowed:
                return False
            if constraint == "months" and date.month not in allowed:
                return False
            if constraint == "days" and date.day not in allowed:
                return False
            if constraint == "weeks" and week not in allowed:
                return False
            if constraint == "weekdays" and weekday not in allowed:
                return False
            if constraint == "start_date" and \
               date < util.build_date_from_constraint(allowed, date, 1):
                return False
            if constraint == "end_date" and \
               date > util.build_date_from_constraint(allowed, date, -1):
                return False
        return True

    @property
    def is_always_valid(self) -> bool:
        """Tells whether this rule is universally valid (has no
        constraints and duration >= 1 day)."""

        if self.constraints:
            return False
        if self.end_time < self.start_time:
            return self.end_plus_days > 1
        return self.end_plus_days >= 1


class RulePath:
    """A chain of rules starting from a root schedule through sub-schedule
    rules."""

    def __init__(self, root_schedule: "Schedule") -> None:
        self.root_schedule = root_schedule
        self.rules = []  # type: T.List[Rule]

    def __repr__(self) -> str:
        if not self.rules:
            return "<{}/<empty rule path>".format(self.root_schedule)
        loc = []
        sched = self.root_schedule
        for rule in self.rules:
            loc.append(str(sched.rules.index(rule) + 1))
            if isinstance(rule, SubScheduleRule):
                sched = rule.sub_schedule
        return "<{}/{}:{}>".format(self.root_schedule, "/".join(loc), rule)  # pylint: disable=undefined-loop-variable

    def add(self, rule: Rule) -> None:
        """Add's a rule to the end of the path.
        A ValueError is raised when the rule to add isn't part of the
        previous rule's sub-schedule or the previous rule is a final
        rule."""

        if self.rules:
            if not isinstance(self.rules[-1], SubScheduleRule):
                raise ValueError(
                    "The previous rule in the path ({}) is no SubScheduleRule."
                    .format(self.rules[-1])
                )
            if rule not in self.rules[-1].sub_schedule.rules:
                raise ValueError(
                    "{} isn't part of the previous rule in path "
                    "({})'s sub-schedule ({})."
                    .format(rule, self.rules[-1], self.rules[-1].sub_schedule)
                )
        elif rule not in self.root_schedule.rules:
            raise ValueError(
                "{} isn't part of the path's root schedule ({})."
                .format(rule, self.root_schedule)
            )
        self.rules.append(rule)

    def copy(self) -> "RulePath":
        """Creates a mutable copy of this path and returns it."""

        path = type(self)(self.root_schedule)
        for rule in self.rules:
            path.add(rule)
        return path

    @property
    def is_final(self) -> bool:
        """Tells whether the last rule in the path is no SubScheduleRule."""

        if not self.rules:
            return False
        return not isinstance(self.rules[-1], SubScheduleRule)

    @property
    def rules_with_temp(self) -> T.Tuple[Rule, ...]:
        """A tuple with rules of the path containing a temperature
        expression, sorted from left to right."""

        return tuple(filter(lambda r: r.temp_expr is not None, self.rules))


class SubScheduleRule(Rule):
    """A schedule rule with a sub-schedule attached."""

    def __init__(
            self, sub_schedule: "Schedule",
            *args: T.Any, **kwargs: T.Any
        ) -> None:

        super().__init__(*args, **kwargs)

        self.sub_schedule = sub_schedule

    def _get_repr_tokens(self) -> T.List[str]:
        """Adds the sub-schedule information to repr()."""

        tokens = super()._get_repr_tokens()
        tokens.insert(0, "with sub-schedule")
        return tokens


class Schedule:
    """Holds the schedule for a room with all its rules."""

    def __init__(
            self, name: str = None, rules: T.Iterable[Rule] = None,
    ) -> None:
        self.name = name
        self.rules = []  # type: T.List[Rule]
        if rules is not None:
            self.rules.extend(rules)

    def __add__(self, other: "Schedule") -> "Schedule":
        if not isinstance(other, type(self)):
            raise ValueError("{} objects may not be added to {}."
                             .format(type(other), self))
        return Schedule(name=self.name, rules=self.rules + other.rules)

    def __repr__(self) -> str:
        if self.name is None:
            return "<Schedule with {} rules>".format(len(self.rules))
        return "<Schedule {}>".format(repr(self.name))

    def get_matching_rules(
            self, when: datetime.datetime
        ) -> T.Iterator[Rule]:
        """Returns an iterator over all rules of this schedule that are
        valid at the time represented by the given datetime object,
        keeping the order from the rules list. SubScheduleRule objects are
        not expanded and yielded like normal rules."""

        _time = when.time()
        for rule in self.rules:
            days_back = -1
            found_start_day = False
            while days_back < rule.end_plus_days:
                days_back += 1
                # starts with days=0 (meaning the current date)
                _date = when.date() - datetime.timedelta(days=days_back)

                found_start_day = found_start_day or \
                                  rule.check_constraints(_date)
                if not found_start_day:
                    # try next day
                    continue

                # in first loop run, rule has to start today and not
                # later than now (rule start <= when.time())
                if days_back == 0 and rule.start_time > _time:
                    # maybe there is a next day to try out
                    continue

                # in last loop run, rule is going to end today and that
                # has to be later than now (rule end > when.time())
                if days_back == rule.end_plus_days and \
                   rule.end_time <= _time:
                    # rule finally disqualified, continue with next rule
                    break

                # rule matches!
                yield rule
                break

    def get_next_scheduling_datetime(
            self, now: datetime.datetime
    ) -> T.Optional[datetime.datetime]:
        """Returns a datetime object with the time at which the next
        re-scheduling should be done. now should be a datetime object
        containing the current date and time.
        SubScheduleRule objects and their rules are considered as well.
        None is returned in case there are no rules in the schedule
        which are not universally valid anyway."""

        times = self.get_scheduling_times()
        if not times:
            # no constrained rules in schedule
            return None

        current_time = now.time()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)

        def map_func(_time: datetime.time) -> datetime.datetime:
            """Maps a time object to a datetime containing the next
            occurrence of that time. Midnight transitions are handled
            correctly."""

            if _time < current_time:
                # midnight transition
                return datetime.datetime.combine(tomorrow, _time)

            return datetime.datetime.combine(today, _time)

        return min(map(map_func, times))

    def get_scheduling_times(self) -> T.Set[datetime.time]:
        """Returns a set of times a re-scheduling should be triggered
        at. Rules of sub-schedules are considered as well."""

        times = set()  # type: T.Set[datetime.time]
        for path in self.unfold():
            for rule in path.rules:
                if not rule.is_always_valid:
                    times.update((rule.start_time, rule.end_time,))
        return times

    def unfold(self) -> T.Iterator[RulePath]:
        """Returns an iterator over rule paths.
        The last rule of a path may either be a SubScheduleRule (meaning
        the path leads to a node) or a Rule (meaning the path leads to
        a leaf). A node is returned first, followed by it's successors
        (like in depth-first search)."""

        for rule in self.rules:
            path = RulePath(self)
            path.add(rule)
            yield path
            if isinstance(rule, SubScheduleRule):
                for path in rule.sub_schedule.unfold():
                    path.root_schedule = self
                    path.rules.insert(0, rule)
                    yield path
