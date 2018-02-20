"""
This module implements the Schedule and Rule classes.
"""

import typing as T  # pylint: disable=unused-import

import datetime

from . import expr, util


class Rule:
    """A rule that can be added to a schedule."""

    # names of schedule rule constraints to be fetched from a rule definition
    CONSTRAINTS = ("years", "months", "days", "weeks", "weekdays",
                   "start_date", "end_date")

    def __init__(
            self, temp_expr: expr.EXPR_TYPE,
            start_time: datetime.time = None, end_time: datetime.time = None,
            end_plus_days: int = 0, constraints: T.Dict[str, T.Any] = None
        ) -> None:
        if start_time is None:
            # make it midnight
            start_time = datetime.time(0, 0)
        self.start_time = start_time

        if end_time is None:
            # make it midnight (00:00 of the next day)
            end_time = datetime.time(0, 0)
            end_plus_days += 1
        self.end_time = end_time

        if end_time < start_time and end_plus_days == 0:
            end_plus_days = 1
        self.end_plus_days = end_plus_days

        if constraints is None:
            constraints = {}
        self.constraints = constraints

        if isinstance(temp_expr, str):
            temp_expr = temp_expr.strip()
        self.temp_expr_raw = temp_expr
        try:
            temp = expr.Temp(temp_expr)
        except ValueError:
            # this is a temperature expression, precompile it
            self.temp_expr = compile(temp_expr, "temp_expr", "eval")  # type: expr.EXPR_TYPE
        else:
            self.temp_expr = temp

    def check_constraints(self, date: datetime.date) -> bool:
        """Checks all constraints of this rule against the given date."""

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


class Schedule:
    """Holds the schedule for a room with all its rules."""

    def __init__(self) -> None:
        self.items = []  # type: T.List[T.Union[Rule, Schedule]]

    def unfold(self) -> T.Iterator[Rule]:
        """Returns an iterator over all rules of this schedule. Included
        sub-schedules are replaced by the rules they contain."""

        for item in self.items:
            if isinstance(item, Rule):
                yield item
            elif isinstance(item, Schedule):
                for rule in item.unfold():
                    yield rule

    def matching_rules(self, when: datetime.datetime) -> T.Iterator[Rule]:
        """Returns an iterator over all rules of the schedule that are
        valid at the time represented by the given datetime object,
        keeping the order from the items list. Rules of sub-schedules
        are included."""

        _time = when.time()
        for rule in self.unfold():
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
                if days_back == rule.end_plus_days and rule.end_time <= _time:
                    # rule finally disqualified
                    break

                # rule matches!
                yield rule
                break

    def next_schedule_datetime(
            self, now: datetime.datetime
    ) -> T.Optional[datetime.datetime]:
        """Returns a datetime object with the time at which the next
        re-scheduling should be done. now should be a datetime object
        containing the current date and time.
        None is returned in case there are no rules in the schedule."""

        times = set()
        for rule in self.unfold():
            times.add(rule.start_time)
            times.add(rule.end_time)

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

            if _time < current_time:
                # midnight transition
                return datetime.datetime.combine(tomorrow, _time)

            return datetime.datetime.combine(today, _time)

        return min(map(map_func, times))
