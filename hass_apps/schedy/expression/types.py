"""
Module containing types to be used during expression evaluation.
"""

import typing as T

if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from .. import schedule


__all__ = [
    "Abort",
    "Break",
    "IncludeSchedule",
    "Inherit",
    "Mark",
    "Next",
    "Skip",
    "Add",
    "Multiply",
    "Invert",
    "Postprocess",
]


class PostprocessingError(Exception):
    """Raised when Postprocessor.apply() fails."""


class PostprocessorValueMixin:
    """Makes a Postprocessor having a value to be validated by the used
    actor type."""

    def __init__(self, value: T.Any) -> None:
        self.value = value

    def __eq__(self, other: T.Any) -> bool:
        return super().__eq__(other) and self.value == other.value


class Postprocessor:
    """A postprocessor for the scheduling result."""

    def __eq__(self, other: T.Any) -> bool:
        return type(self) is type(other)

    def apply(self, result: T.Any) -> T.Any:
        """Implements the postprocessor-specific logic for updating the
        result. The returned value should have the type of result."""

        raise NotImplementedError()


class Add(PostprocessorValueMixin, Postprocessor):
    """Adds a value to the final result."""

    def apply(self, result: T.Any) -> T.Any:
        try:
            return type(result)(result + self.value)
        except TypeError as err:
            raise PostprocessingError(repr(err))

    def __repr__(self) -> str:
        return "Add({})".format(repr(self.value))


class Multiply(PostprocessorValueMixin, Postprocessor):
    """Multiplies a value with the final result."""

    def apply(self, result: T.Any) -> T.Any:
        try:
            return type(result)(result * self.value)
        except TypeError as err:
            raise PostprocessingError(repr(err))

    def __repr__(self) -> str:
        return "Multiply({})".format(repr(self.value))


class Invert(Postprocessor):
    """Negates the final result by calling __neg__().
    Booleans and the strings "on"/"off" are inverted instead."""

    specials = {True: False, False: True, "on": "off", "off": "on"}

    def apply(self, result: T.Any) -> T.Any:
        try:
            return self.specials[result]
        except KeyError:
            try:
                return -result
            except TypeError as err:
                raise PostprocessingError(repr(err))

    def __repr__(self) -> str:
        return "Invert()"


class Postprocess(Postprocessor):
    """A type which can be used for post-processing the later result by
    a custom function (i.e. a lambda closure)."""

    def __init__(self, func: T.Callable[[T.Any], T.Any]) -> None:
        self._func = func

    def apply(self, result: T.Any) -> T.Any:
        return self._func(result)


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


class Inherit(ControlResult):
    """Causes the next parent's value to be used as the result."""

    def __repr__(self) -> str:
        return "Inherit()"


class Mark(ControlResult):
    """A result with some markers applied."""

    # available markers
    OVERLAY = "OVERLAY"
    OVERLAY_REVERT_ON_NO_RESULT = "OVERLAY_REVERT_ON_NO_RESULT"

    def __init__(self, result: T.Any, *markers: str) -> None:
        self.markers = set(markers)
        if isinstance(result, Mark):
            # Unwrap the result, combining present markers with our own ones
            self.result = result.unwrap(self.markers)
        else:
            self.result = result

    def __eq__(self, other: T.Any) -> bool:
        return (
            isinstance(other, self.__class__)
            and self.result == other.result
            and self.markers == other.markers
        )

    def __repr__(self) -> str:
        return "Mark({}, {})".format(repr(self.result), self.markers)

    def unwrap(self, markers_set: T.Set[str]) -> T.Any:
        """Returns the real, wrapped result. The applied markers will
        be added to markers_set."""

        markers_set.update(self.markers)
        return self.result


class Next(ControlResult):
    """Result of an expression which should be ignored."""

    def __repr__(self) -> str:
        return "Next()"


class Skip(Next):
    """For backwards compatibility."""

    def __init__(self) -> None:
        import warnings

        warnings.warn(
            "Skip was renamed to Next and will be removed in version 0.7.",
            DeprecationWarning,
        )
