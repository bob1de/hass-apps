"""
Helpers to be available in the expression evaluation environment.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from .. import schedule as schedule_mod
    from ..room import Room

import datetime


class HelperBase:
    """A base for helpers to be available in the evaluation environment."""

    namespace = ""

    def __init__(self, room: "Room", now: datetime.datetime) -> None:
        self._room = room
        self._app = room.app
        self._now = now


class BasicHelper(HelperBase):
    """Adds some basic helpers."""

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)

        self.app = self._app
        self.room = self._room
        self.room_name = self._room.name

        self.datetime = datetime
        self.now = self._now
        self.date = self._now.date()
        self.time = self._now.time()

        self.schedule_snippets = self._app.cfg["schedule_snippets"]

    @staticmethod
    def round_to_step(
            value: T.Union[float, int], step: T.Union[float, int],
            decimal_places: int = None
    ) -> T.Union[float, int]:
        """Round the value to the nearest step and, optionally, the
        given number of decimal places.
        Examples:
            round_to_step(34, 25) == 25
            round_to_step(0.665, 0.2, 1) == 0.6"""

        value = step * round(value / step)
        if decimal_places is not None:
            value = round(value, decimal_places)
        return value


class CustomModulesHelper(HelperBase):
    """Adds the modules configured for expression_modules."""

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)

        self.__dict__.update(self._app.expression_modules)


class StateHelper(HelperBase):
    """Various state-related helpers."""

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)

        self.state = self._app.get_state

    def is_on(self, entity_id: str) -> bool:
        """Returns whether an entity'S state is "on" (case-insensitive)."""

        return str(self._app.get_state(entity_id)).lower() == "on"

    def is_off(self, entity_id: str) -> bool:
        """Returns whether an entity'S state is "off" (case-insensitive)."""

        return str(self._app.get_state(entity_id)).lower() == "off"


class ScheduleHelper(HelperBase):
    """Helpers related to schedule evaluation."""

    namespace = "schedule"

    def evaluate(
            self, schedule: "schedule_mod.Schedule",
            when: datetime.datetime = None
    ) -> T.Any:
        """Evaluates the given schedule for the given point in time."""

        when = when or self._now
        return schedule.evaluate(self._room, when)

    def next_results(
            self, schedule: "schedule_mod.Schedule",
            start: datetime.datetime = None, end: datetime.datetime = None
    ) -> T.Iterable[T.Tuple[
        datetime.datetime, "schedule_mod.ScheduleEvaluationResultType"
    ]]:
        """Returns an iterator over tuples of datetime objects and
        schedule evaluation results. At each of these datetimes, the
        scheduling result will change to the returned one."""

        when = start or self._now  # type: T.Optional[datetime.datetime]
        last_result = None
        while when and (not end or end > when):
            result = schedule.evaluate(self._room, when)
            if result is not None and result != last_result:
                yield when, result
                last_result = result
            when = schedule.get_next_scheduling_datetime(when)


class PatternHelper(HelperBase):
    """Help generate values based on different patterns."""

    namespace = "pattern"

    @staticmethod
    def linear(
            start_value: float, end_value: float,
            factor: float = None, percentage: float = None
    ) -> float:
        """Calculate the value at a given percentage between start_value
        and end_value. As an alternative to percentage, a factor between
        0 and 1 may be given."""

        _checks = factor is None, percentage is None
        if all(_checks) or not any(_checks):
            raise ValueError("either factor or percentage must be given")
        if percentage is not None:
            factor = percentage / 100

        assert factor is not None  # required for mypy
        return start_value + factor * (end_value - start_value)
