"""
Module containing functionality to evaluate temperature expressions.
"""

import datetime
import functools


__all__ = ["Add", "Break", "Ignore", "IncludeSchedule", "OFF", "Result",
           "Temp"]


# special value Temp can be initialized with
OFF = "OFF"


class AddibleMixin:
    """Mixin that makes a temperature expression result addible."""
    pass

class ResultBase:
    """Holds the result of a temperature expression."""

    def __init__(self, temp):
        self.temp = Temp(temp)

    def __eq__(self, other):
        return type(self) is type(other) and self.temp == other.temp


class Result(ResultBase, AddibleMixin):
    """Final result of a temperature expression."""

    def __repr__(self):
        return "{}".format(self.temp)

class Add(ResultBase, AddibleMixin):
    """Result of a temperature expression that is intended to be added
    to the result of a consequent expression."""

    def __add__(self, other):
        if not isinstance(other, AddibleMixin):
            raise TypeError("can't add {} and {}"
                            .format(repr(type(self)), repr(type(other))))

        return type(other)(self.temp + other.temp)

    def __repr__(self):
        return "Add({})".format(self.temp)

class Break(ResultBase):
    """Result of a temperature expression that should abort scheduling and
    leave the temperature unchanged."""

    def __init__(self):
        # pylint: disable=super-init-not-called
        self.temp = None

    def __repr__(self):
        return "Break()"

class Ignore(ResultBase):
    """Result of a temperature expression which should be ignored."""

    def __init__(self):
        # pylint: disable=super-init-not-called
        self.temp = None

    def __repr__(self):
        return "Ignore()"

class IncludeSchedule(ResultBase):
    """Result that includes a schedule for processing."""

    def __init__(self, schedule):
        # pylint: disable=super-init-not-called

        self.schedule = schedule

    def __repr__(self):
        return "IncludeSchedule({})".format(self.schedule)


@functools.total_ordering
class Temp:
    """A class holding a temperature value."""

    def __init__(self, value):
        if isinstance(value, Temp):
            # just copy the value over
            value = value.value

        parsed = self.parse_temp(value)
        if parsed is None:
            raise ValueError("{} is no valid temperature"
                             .format(repr(value)))

        self.value = parsed

    def __add__(self, other):
        if isinstance(other, (float, int)):
            other = Temp(other)
        elif not isinstance(other, Temp):
            raise TypeError("can't add {} and {}"
                            .format(repr(type(self)), repr(type(other))))

        # OFF + something is OFF
        if self.is_off() or other.is_off():
            return Temp(OFF)

        return Temp(self.value + other.value)

    def __neg__(self):
        # pylint: disable=invalid-unary-operand-type
        if self.is_off():
            return Temp(self.value)
        return Temp(-self.value)

    def __sub__(self, other):
        if isinstance(other, (float, int)):
            other = Temp(other)
        return self.__add__(-other)

    def __eq__(self, other):
        return isinstance(other, Temp) and self.value == other.value

    def __lt__(self, other):
        if isinstance(other, (float, int)):
            other = Temp(other)

        if type(self) is not type(other):
            raise TypeError("can't compare {} and {}"
                            .format(repr(type(self)), repr(type(other))))

        if not self.is_off() and other.is_off():
            return False
        if self.is_off() and not other.is_off() or \
           self.value < other.value:
            return True
        return False

    def __repr__(self):
        if self.is_off():
            return "OFF"
        return repr(self.value)

    def is_off(self):
        """Returns True if this temperature is OFF, False otherwise."""
        return self.value == OFF

    @staticmethod
    def parse_temp(value):
        """Converts the given value to a valid temperature of type float or OFF.
        If value is a string, all whitespace is removed first.
        If conversion is not possible, None is returned."""

        if isinstance(value, str):
            value = "".join(value.split())
            if value.upper() == OFF.upper():
                return OFF

        try:
            return float(value)
        except (ValueError, TypeError):
            return None


def build_time_expression_env():
    """This function builds and returns an environment usable as globals
    for the evaluation of a time expression. It will add all members
    of this module's __all__ to the environment."""

    env = {"datetime": datetime}
    for name in __all__:
        env[name] = globals()[name]
    return env

def eval_temp_expr(temp_expr, extra_env=None):
    """This method evaluates the given temperature expression.
    The evaluation result is returned. The items of the extra_env
    dict are added to the globals available during evaluation.
    The result is a ResultBase (or sub-type) object."""

    # pylint: disable=eval-used

    try:
        return Result(temp_expr)
    except ValueError:
        # it's an expression, not a simple temperature value
        pass

    env = build_time_expression_env()
    if extra_env:
        env.update(extra_env)
    result = eval(temp_expr, env)

    if not isinstance(result, ResultBase):
        result = Result(result)

    return result
