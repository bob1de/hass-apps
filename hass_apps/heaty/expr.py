"""
Module containing functionality to evaluate temperature expressions.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from . import schedule
    from .app import HeatyApp
import types

import datetime
import functools


__all__ = ["Abort", "Add", "Break", "IncludeSchedule", "OFF", "Off", "Result",
           "Skip", "Temp"]


# type of an evaluable expression
ExprType = T.Union[str, types.CodeType, "Temp"]
# allowed types of values to initialize Temp() with
TempValueType = T.Union[float, int, str, "Off", "Temp"]


class AddibleMixin:
    """Mixin that marks a temperature expression's result as addible."""

    def __init__(self, value: TempValueType) -> None:
        self.value = Temp(value)

    def __eq__(self, other: T.Any) -> bool:
        return type(self) is type(other) and self.value == other.value

class ResultBase:
    """Holds the result of a temperature expression."""

    def __eq__(self, other: T.Any) -> bool:
        return type(self) is type(other)

class Result(ResultBase, AddibleMixin):
    """Final result of a temperature expression."""

    def __repr__(self) -> str:
        return "Result({})".format(self.value)

class Abort(ResultBase):
    """Result of a temperature expression that should cause scheduling
    to be aborted and the temperature left unchanged."""

    def __repr__(self) -> str:
        return "Abort()"

class Add(ResultBase, AddibleMixin):
    """Result of a temperature expression to which the result of a
    consequent expression should be added."""

    def __add__(self, other: ResultBase) -> ResultBase:
        if not isinstance(other, AddibleMixin):
            raise TypeError("can't add {} and {}"
                            .format(repr(type(self)), repr(type(other))))

        return type(other)(self.value + other.value)

    def __repr__(self) -> str:
        return "Add({})".format(self.value)

class Break(ResultBase):
    """Result of a temperature expression that should cause the rest of
    a sub-schedule to be skipped."""

    def __init__(self, levels: int = 1) -> None:
        if not isinstance(levels, int) or levels < 1:
            raise ValueError(
                "levels to break must be >= 1, but is {}".format(repr(levels))
            )
        self.levels = levels

    def __repr__(self) -> str:
        return "Break({})".format(self.levels if self.levels != 1 else "")

class IncludeSchedule(ResultBase):
    """Result that inserts a schedule in place for further processing."""

    def __init__(self, sched: "schedule.Schedule") -> None:
        self.schedule = sched

    def __repr__(self) -> str:
        return "IncludeSchedule({})".format(self.schedule)

class Skip(ResultBase):
    """Result of a temperature expression which should be ignored."""

    def __repr__(self) -> str:
        return "Skip()"


class Off:
    """A special value Temp() may be initialized with in order to turn
    a thermostat off."""

    def __add__(self, other: T.Any) -> "Off":
        return self

    def __eq__(self, other: T.Any) -> bool:
        return isinstance(other, Off)

    def __hash__(self) -> int:
        return hash(str(self))

    def __neg__(self) -> "Off":
        return self

    def __repr__(self) -> str:
        return "OFF"

    def __sub__(self, other: T.Any) -> "Off":
        return self

OFF = Off()

@functools.total_ordering
class Temp:
    """A class holding a temperature value."""

    def __init__(self, temp_value: T.Any) -> None:
        if isinstance(temp_value, Temp):
            # Just copy the value over.
            parsed = self.parse_temp(temp_value.value)
        else:
            parsed = self.parse_temp(temp_value)

        if parsed is None:
            raise ValueError("{} is no valid temperature"
                             .format(repr(temp_value)))

        self.value = parsed  # type: T.Union[float, Off]

    def __add__(self, other: T.Any) -> "Temp":
        if isinstance(other, (float, int)):
            other = type(self)(other)
        elif not isinstance(other, type(self)):
            raise TypeError("can't add {} and {}"
                            .format(repr(type(self)), repr(type(other))))

        # OFF + something is OFF
        if self.is_off or other.is_off:
            return type(self)(Off())

        return type(self)(self.value + other.value)

    def __eq__(self, other: T.Any) -> bool:
        return isinstance(other, Temp) and self.value == other.value

    def __float__(self) -> float:
        if isinstance(self.value, float):
            return self.value
        raise ValueError("{} has no numeric value.".format(repr(self)))

    def __hash__(self) -> int:
        return hash(str(self))

    def __lt__(self, other: T.Any) -> bool:
        if isinstance(other, (float, int)):
            other = Temp(other)

        if type(self) is not type(other):
            raise TypeError("can't compare {} and {}"
                            .format(repr(type(self)), repr(type(other))))

        if not self.is_off and other.is_off:
            return False
        if self.is_off and not other.is_off or \
           self.value < other.value:
            return True
        return False

    def __neg__(self) -> "Temp":
        return Temp(-self.value)  # pylint: disable=invalid-unary-operand-type

    def __repr__(self) -> str:
        if isinstance(self.value, (float, int)):
            return "{}°".format(self.value)
        return "{}".format(self.value)

    def __sub__(self, other: T.Any) -> "Temp":
        return self.__add__(-other)

    @property
    def is_off(self) -> bool:
        """Tells whether this temperature means OFF."""

        return isinstance(self.value, Off)

    @staticmethod
    def parse_temp(value: T.Any) -> T.Union[float, Off, None]:
        """Converts the given value to a valid temperature of type float
        or Off.
        If value is a string, all whitespace is removed first.
        If conversion is not possible, None is returned."""

        if isinstance(value, str):
            value = "".join(value.split())
            if value.upper() == "OFF":
                return Off()

        if isinstance(value, Off):
            return Off()

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def serialize(self) -> str:
        """Converts the temperature into a string that Temp can be
        initialized with again later."""

        if self.is_off:
            return "OFF"
        return str(self.value)


def build_expr_env(app: "HeatyApp") -> T.Dict[str, T.Any]:
    """This function builds and returns an environment usable as globals
    for the evaluation of an expression. It will add all members
    of this module's __all__ to the environment. Additionally, some
    helpers will be constructed based on the HeatyApp object"""

    # use date/time provided by appdaemon to support time-traveling
    now = app.datetime()
    env = {
        "app": app,
        "schedule_snippets": app.cfg["schedule_snippets"],
        "datetime": datetime,
        "now": now,
        "date": now.date(),
        "time": now.time(),
        "state": app.get_state,
        "is_on":
            lambda entity_id: str(app.get_state(entity_id)).lower() == "on",
        "is_off":
            lambda entity_id: str(app.get_state(entity_id)).lower() == "off",
    }

    globs = globals()
    for name in __all__:
        env[name] = globs[name]

    env.update(app.temp_expression_modules)

    return env

def eval_temp_expr(
        temp_expr: ExprType,
        app: "HeatyApp",
        extra_env: T.Optional[T.Dict[str, T.Any]] = None
) -> T.Optional[ResultBase]:
    """This method evaluates the given temperature expression.
    The evaluation result is returned. The items of the extra_env
    dict are added to the globals available during evaluation.
    If the expression is a Temp object already, it's just packed into
    a Result and returned directly."""

    # pylint: disable=eval-used

    if isinstance(temp_expr, Temp):
        return Result(temp_expr)

    env = build_expr_env(app)
    if extra_env:
        env.update(extra_env)

    eval_result = eval(temp_expr, env)
    if eval_result is None or isinstance(eval_result, ResultBase):
        return eval_result
    return Result(eval_result)
