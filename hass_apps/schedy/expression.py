"""
Module containing functionality to evaluate expressions.
"""

import types
import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from . import schedule
    from .app import SchedyApp

import datetime


__all__ = [
    "Abort", "Break", "IncludeSchedule", "Skip",
    "Add", "And", "Multiply", "Negate", "Or",
]


class PreliminaryCombiningError(Exception):
    """Raised when PreliminaryResult.combine_with() fails."""

    pass

class PreliminaryValueMixin:
    """Makes a PreliminaryResult having a value."""

    def __init__(self, value: T.Any) -> None:
        self.value = value

    def __eq__(self, other: T.Any) -> bool:
        return super().__eq__(other) and self.value == other.value

class PreliminaryValidationMixin(PreliminaryValueMixin):
    """Marks a PreliminaryResult for needing value validation by the
    used actor type."""

    pass

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

class Skip(ControlResult):
    """Result of an expression which should be ignored."""

    def __repr__(self) -> str:
        return "Skip()"


def build_expr_env(app: "SchedyApp") -> T.Dict[str, T.Any]:
    """This function builds and returns an environment usable as globals
    for the evaluation of an expression. It will add all members
    of this module's __all__ to the environment. Additionally, some
    helpers will be constructed based on the SchedyApp object"""

    # use date/time provided by appdaemon to support time-traveling
    now = app.datetime()
    is_on = lambda _id: str(app.get_state(_id)).lower() == "on"  # type: T.Callable[[str], bool]
    is_off = lambda _id: str(app.get_state(_id)).lower() == "off"  # type: T.Callable[[str], bool]
    env = {
        "app": app,
        "schedule_snippets": app.cfg["schedule_snippets"],
        "datetime": datetime,
        "now": now,
        "date": now.date(),
        "time": now.time(),
        "state": app.get_state,
        "any_on": lambda ids: any([is_on(_id) for _id in ids]),
        "any_off": lambda ids: any([is_off(_id) for _id in ids]),
        "is_on": is_on,
        "is_off": is_off,
    }

    globs = globals()
    for name in __all__:
        env[name] = globs[name]

    env.update(app.expression_modules)

    return env

def eval_expr(
        expr: types.CodeType, app: "SchedyApp",
        extra_env: T.Optional[T.Dict[str, T.Any]] = None
) -> T.Any:
    """This method evaluates the given expression. The evaluation result
    is returned. The items of the extra_env dict are added to the globals
    available during evaluation."""

    env = build_expr_env(app)
    if extra_env:
        env.update(extra_env)

    exec(expr, env)  # pylint: disable=exec-used
    return env.get("result")
