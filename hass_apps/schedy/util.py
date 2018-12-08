"""
Utility functions that are used all around Schedy.
"""

import types
import typing as T

import collections
import datetime
import re
import voluptuous as vol


# matches any character not allowed in Python variable names
INVALID_VAR_NAME_CHAR_PATTERN = re.compile(r"[^0-9a-z_]", re.I)

# regexp pattern matching a range spec like 5, 3-7 or */5 without spaces
RANGE_PATTERN = re.compile(r"^(?:(\*)|(\d+)(?:\-(\d+))?)(?:\/([1-9]\d*))?$")

# strftime-compatible format string for military time
TIME_FORMAT = "%H:%M:%S"
# regular expression for time formats, group 1 is hours, group 2 is minutes,
# optional group 3 is seconds
TIME_REGEXP = re.compile(r"^ *([01]?\d|2[0-3]) *\: *([0-5]\d) *(?:\: *([0-5]\d) *)?$")

# used instead of vol.Extra to ensure keys are strings
CONF_STR_KEY = vol.Coerce(str)


class RangingSet(set):
    """A set for integers that forms nice ranges in its __repr__,
    perfectly suited for the expansion of range strings."""

    def __repr__(self) -> str:
        if not self:
            return "{}"

        # fall back to legacy representation when non-ints are found
        for item in self:
            if not isinstance(item, int):
                return super().__repr__()

        nums = sorted(self)  # type: T.List[int]
        ranges = collections.OrderedDict()  # type: T.Dict[int, int]
        range_start = nums[0]
        ranges[range_start] = range_start
        for num in nums[1:]:
            if num - 1 != ranges[range_start]:
                range_start = num
            ranges[range_start] = num

        return "{{{}}}".format(", ".join(
            [str(start) if start == end else "{}-{}".format(start, end)
             for start, end in ranges.items()]
        ))


def build_date_from_constraint(
        constraint: T.Dict[str, int], default_date: datetime.date,
        direction: int = 0
) -> datetime.date:
    """Builds and returns a datetime.date object from the given constraint,
    taking missing values from the given default_date.
    In case the date is not valid (e.g. 2017-02-29), a ValueError is
    raised, unless a number has been given for direction, in which case
    the next/previous valid date will be chosen, depending on the sign
    of direction."""

    fields = {}
    for field in ("year", "month", "day"):
        fields[field] = constraint.get(field, getattr(default_date, field))

    while True:
        try:
            return datetime.date(**fields)
        except ValueError:
            if direction > 0:
                fields["day"] += 1
            elif direction < 0:
                fields["day"] -= 1
            else:
                raise

            # handle month/year transitions correctly
            if fields["day"] < 1:
                fields["day"] = 31
                fields["month"] -= 1
            elif fields["day"] > 31:
                fields["day"] = 1
                fields["month"] += 1
            if fields["month"] < 1:
                fields["month"] = 12
                fields["year"] -= 1
            elif fields["month"] > 12:
                fields["month"] = 1
                fields["year"] += 1

def compile_expression(expr: str) -> types.CodeType:
    """Compiles strings to code objects.
    Strings containing one or more newlines are assumed to contain
    whole statements. Others are treated as simple expressions and
    "result = " is prepended to them before compilation is done as a
    single statement."""

    if "\n" in expr:
        mode = "exec"
    else:
        expr = "result = {}".format(expr)
        mode = "single"

    compiled = compile(expr, "expr", mode, dont_inherit=True)  # type: types.CodeType
    return compiled

def deep_merge_dicts(source: dict, dest: dict) -> None:
    """Updates items of dest with those of source, descending into and
    merging child dictionaries as well. Child lists are combined as
    well so that the items of a list from source are appended to the
    list found in dest under the same name."""

    for key, value in source.items():
        dest_value = dest.get(key)
        if isinstance(value, dict) and isinstance(dest_value, dict):
            deep_merge_dicts(value, dest[key])
        elif isinstance(value, list) and isinstance(dest_value, list):
            dest_value.extend(value)
        else:
            dest[key] = value

def escape_var_name(name: str) -> str:
    """Converts the given string to a valid Python variable name.
    All unsupported characters are replaced by "_". If name would
    start with a digit, "_" is put infront."""

    name = INVALID_VAR_NAME_CHAR_PATTERN.sub("_", name)
    digits = tuple([str(i) for i in range(10)])
    if name.startswith(digits):
        name = "_" + name
    return name

def expand_range_spec(
        spec: T.Union[int, str], min_value: int, max_value: int
) -> T.Set[int]:
    """Expands strings of the range specification format to RangingSet
    objects containing the individual numbers.
    Any whitespace is ignored. If an int is given instead of a string,
    a set containing only that is returned.
    The min_value and max_value are required to support the * specifier
    and a ValueError is raised when the range specification exceeds
    these boundaries."""

    if isinstance(spec, int):
        spec = str(spec)

    numbers = RangingSet()
    for part in "".join(spec.split()).split(","):
        match = RANGE_PATTERN.match(part)
        if match is None:
            raise ValueError("invalid range definition: {}".format(repr(part)))

        _wildcard, _start, _end, _step = match.groups()
        if _wildcard:
            start = min_value
            end = max_value
        else:
            start = int(_start)
            end = start if _end is None else int(_end)
            for value in (start, end):
                if value < min_value or value > max_value:
                    raise ValueError(
                        "value {} is out of range {}..{}"
                        .format(value, min_value, max_value)
                    )
            if end < start:
                start, end = end, start
        step = int(_step or 1)

        for i in range(start, end + 1, step):
            numbers.add(i)

    return numbers

def format_time(when: datetime.time, format_str: str = TIME_FORMAT) -> str:
    """Returns a string representing the given datetime.time object.
    If no strftime-compatible format is provided, the default is used."""

    return when.strftime(format_str)

def normalize_dict_key(
        obj: dict, dest_key: T.Any, *alt_keys: T.Any,
        keep_alt_keys: bool = False
) -> None:
    """If dest_key is missing in the dict obj but one of the alt_keys
    is found instead, the value of the first alt_key is moved over
    to dest_key.
    All alt_keys are deleted from dict obj unless keep_alt_keys is True."""

    for alt_key in alt_keys:
        if alt_key in obj:
            if dest_key not in obj:
                obj[dest_key] = obj[alt_key]
            if not keep_alt_keys:
                del obj[alt_key]

def parse_time_string(time_str: str) -> datetime.time:
    """Parses a string recognizable by TIME_REGEXP format into
    a datetime.time object. If the string has an invalid format, a
    ValueError is raised."""

    match = TIME_REGEXP.match(time_str)
    if match is None:
        raise ValueError("time string {} has an invalid format"
                         .format(repr(time_str)))
    components = [int(comp) for comp in match.groups() if comp is not None]
    return datetime.time(*components)  # type: ignore

def round_number(
        number: T.Union[float, int], places: int
) -> T.Union[float, int]:
    """Rounds the given number to the given decimal places. If places
    is 0, an integer is returned, a float otherwise."""

    if places < 0:
        raise ValueError("can'T round to a negative number of decimal places")

    if places == 0:
        return round(number, 0)

    string = "{{:.{}f}}".format(places).format(number).rstrip("0")
    if string.endswith("."):
        string += "0"
    return float(string)
