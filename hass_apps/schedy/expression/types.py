"""
Module containing types to be used in expression evaluation.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from .. import schedule


__all__ = [
    "Abort", "Break", "Mark", "IncludeSchedule", "Skip",
    "Add", "And", "Multiply", "Negate", "Or",
]


class PreliminaryCombiningError(Exception):
    """Raised when PreliminaryResult.combine_with() fails."""

class PreliminaryValueMixin:
    """Makes a PreliminaryResult having a value."""

    def __init__(self, value: T.Any) -> None:
        self.value = value

    def __eq__(self, other: T.Any) -> bool:
        return super().__eq__(other) and self.value == other.value

class PreliminaryValidationMixin(PreliminaryValueMixin):
    """Marks a PreliminaryResult for needing value validation by the
    used actor type."""

class PreliminaryResult:
    """Marks an expressions result as preliminary."""

    def __eq__(self, other: T.Any) -> bool:
        return type(self) is type(other)

    def combine_with(self, other: T.Any) -> T.Any:
        """Implements the logic to update other with self. The result
        should have the type of other."""

        raise NotImplementedError()

class Add(PreliminaryValidationMixin, PreliminaryResult):
    """Adds a value to the final result."""

    def combine_with(self, other: T.Any) -> T.Any:
        try:
            return type(other)(other + self.value)
        except TypeError as err:
            raise PreliminaryCombiningError(repr(err))

    def __repr__(self) -> str:
        return "Add({})".format(repr(self.value))

class And(PreliminaryValidationMixin, PreliminaryResult):
    """And-combines a value with the final result."""

    def combine_with(self, other: T.Any) -> T.Any:
        return type(other)(other and self.value)

    def __repr__(self) -> str:
        return "And({})".format(repr(self.value))

class Multiply(PreliminaryValidationMixin, PreliminaryResult):
    """Multiplies a value with the final result."""

    def combine_with(self, other: T.Any) -> T.Any:
        try:
            return type(other)(other * self.value)
        except TypeError as err:
            raise PreliminaryCombiningError(repr(err))

    def __repr__(self) -> str:
        return "Multiply({})".format(repr(self.value))

class Negate(PreliminaryResult):
    """Negates the final result by calling __neg__().
    Booleans and the strings "on"/"off" are inverted instead."""

    specials = {True:False, False:True, "on":"off", "off":"on"}

    def combine_with(self, other: T.Any) -> T.Any:
        try:
            return self.specials[other]
        except KeyError:
            try:
                return -other
            except TypeError as err:
                raise PreliminaryCombiningError(repr(err))

    def __repr__(self) -> str:
        return "Negate()"

class Or(PreliminaryValidationMixin, PreliminaryResult):
    """Or-combines a value with the final result."""

    def combine_with(self, other: T.Any) -> T.Any:
        return type(other)(other or self.value)

    def __repr__(self) -> str:
        return "Or({})".format(repr(self.value))


class ControlResult:
    """A special expression result used for evaluation flow control."""

    def __eq__(self, other: T.Any) -> bool:
        return type(self) is type(other)

class Abort(ControlResult):
    """Result of an expression that should cause scheduling to be aborted
    and the value left unchanged."""

    def __repr__(self) -> str:
        return "Abort()"

class Break(ControlResult):
    """Result of an expression that should cause the rest of a
    sub-schedule to be skipped."""

    def __init__(self, levels: int = 1) -> None:
        if not isinstance(levels, int) or levels < 1:
            raise ValueError(
                "levels to break must be >= 1, but is {}".format(repr(levels))
            )
        self.levels = levels

    def __eq__(self, other: T.Any) -> bool:
        return super().__eq__(other) and self.levels == other.levels

    def __repr__(self) -> str:
        return "Break({})".format(self.levels if self.levels != 1 else "")

class IncludeSchedule(ControlResult):
    """Result that inserts a schedule in place for further processing."""

    def __init__(self, sched: "schedule.Schedule") -> None:
        self.schedule = sched

    def __eq__(self, other: T.Any) -> bool:
        return super().__eq__(other) and self.schedule == other.schedule

    def __repr__(self) -> str:
        return "IncludeSchedule({})".format(self.schedule)

class Mark(ControlResult):
    """A result with some markers applied."""

    # available markers
    OVERLAY = "overlay"

    def __init__(self, result: T.Any, *markers: str) -> None:
        self.markers = set(markers)
        if isinstance(result, Mark):
            self.markers.update(result.markers)
            self.result = result.result  # type: T.Any
        else:
            self.result = result

    def __eq__(self, other: T.Any) -> bool:
        return super().__eq__(other) and self.result == other.result and \
               self.markers == other.markers

    def __repr__(self) -> str:
        return "Mark({}, {})".format(repr(self.result), self.markers)

class Skip(ControlResult):
    """Result of an expression which should be ignored."""

    def __repr__(self) -> str:
        return "Skip()"
