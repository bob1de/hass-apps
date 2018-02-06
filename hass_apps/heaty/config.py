"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import voluptuous as vol

from . import expr, schedule, util


# names of schedule rule constraints to be fetched from the rule definition
CONSTRAINTS = ("years", "months", "days", "weeks", "weekdays",
               "start_date", "end_date")


def build_schedule_rule(rule):
    """Builds and returns a schedule rule from the given rule
    definition."""

    constraints = {}
    for name, value in rule.items():
        if name in CONSTRAINTS:
            constraints[name] = value

    start_time = rule.get("start")
    if start_time is not None:
        start_time = util.parse_time_string(start_time)

    end_time = rule.get("end")
    if end_time is not None:
        end_time = util.parse_time_string(end_time)
    end_plus_days = rule["end_plus_days"]

    temp_expr = rule["temp"]

    return schedule.Rule(temp_expr=temp_expr,
                         start_time=start_time,
                         end_time=end_time,
                         end_plus_days=end_plus_days,
                         constraints=constraints)

def build_schedule(items):
    """Builds and returns a schedule containing the given items."""

    sched = schedule.Schedule()
    sched.items.extend(items)
    return sched

def config_post_hook(cfg):
    """Sets some initial values after config has been parsed."""

    for room_name, room in cfg["rooms"].items():
        room.setdefault("friendly_name", room_name)

        room["wanted_temp"] = None

        room["schedule"].items.insert(0, cfg["schedule_prepend"])
        room["schedule"].items.append(cfg["schedule_append"])

        # copy settings from defaults sections to this room
        for therm_name, therm in room["thermostats"].items():
            for key, val in cfg["thermostat_defaults"].items():
                therm.setdefault(key, val)
            therm = THERMOSTAT_SCHEMA(therm)
            therm["current_temp"] = None
            room["thermostats"][therm_name] = therm
        for sensor_name, sensor in room["window_sensors"].items():
            for key, val in cfg["window_sensor_defaults"].items():
                sensor.setdefault(key, val)
            sensor = WINDOW_SENSOR_SCHEMA(sensor)
            room["window_sensors"][sensor_name] = sensor

    return cfg


ENTITY_ID_SCHEMA = vol.Schema(vol.Match(r"^[A-Za-z_]+\.[A-Za-z0-9_]+$"))
PYTHON_VAR_SCHEMA = vol.Schema(vol.Match(r"^[a-zA-Z_]+[a-zA-Z0-9_]*$"))
RANGE_STRING_SCHEMA = vol.Schema(vol.All(
    vol.Any(
        int,
        vol.Match(r"^ *\d+( *\- *\d+)?( *\, *\d+( *\- *\d+)?)* *$"),
    ),
    util.expand_range_string,
))
PARTIAL_DATE_SCHEMA = vol.Schema({
    vol.Optional("year"): vol.All(int, vol.Range(min=1970, max=9999)),
    vol.Optional("month"): vol.All(int, vol.Range(min=1, max=12)),
    vol.Optional("day"): vol.All(int, vol.Range(min=1, max=31)),
})
TIME_SCHEMA = vol.Schema(vol.Match(r"^ *([01]\d|2[0123]) *\: *([012345]\d) *$"))
TEMP_SCHEMA = vol.Schema(vol.All(
    vol.Any(float, int, "OFF", "off"),
    lambda v: expr.Temp(v),  # pylint: disable=unnecessary-lambda
))
TEMP_EXPRESSION_SCHEMA = vol.Schema(str)

# This schema does no real validation and default value insertion,
# it just ensures a dictionary containing dictionaries is returned.
DICT_IN_DICT_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Extra: lambda v: v or {},
    },
))

TEMP_EXPRESSION_MODULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "as": PYTHON_VAR_SCHEMA,
    },
))
TEMP_EXPRESSION_MODULES_SCHEMA = vol.Schema({
    vol.Extra: lambda v: TEMP_EXPRESSION_MODULE_SCHEMA(v or {}),
})

THERMOSTAT_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Optional("delta", default=0): vol.Any(float, int),
        vol.Optional("min_temp", default=None): vol.Any(TEMP_SCHEMA, None),
        vol.Optional("set_temp_retries", default=10):
            vol.All(int, vol.Range(min=-1)),
        vol.Optional("set_temp_retry_interval", default=30):
            vol.All(int, vol.Range(min=1)),
        vol.Optional("opmode_heat", default="Heat"): str,
        vol.Optional("opmode_off", default="Off"): str,
        vol.Optional("opmode_service", default="climate/set_operation_mode"):
            str,
        vol.Optional("opmode_service_attr", default="operation_mode"): str,
        vol.Optional("opmode_state_attr", default="operation_mode"): str,
        vol.Optional("temp_service", default="climate/set_temperature"): str,
        vol.Optional("temp_service_attr", default="temperature"): str,
        vol.Optional("temp_state_attr", default="temperature"): str,
    },
))

STATE_SCHEMA = vol.Schema(vol.Any(float, int, str))
WINDOW_SENSOR_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Optional("delay", default=10): vol.All(int, vol.Range(min=0)),
        vol.Optional("open_state", default="on"):
            vol.Any(STATE_SCHEMA, [STATE_SCHEMA]),
    },
))
WINDOW_SENSORS_SCHEMA = vol.Schema({
    vol.Extra: lambda v: WINDOW_SENSOR_SCHEMA(v or {}),
})

SCHEDULE_RULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "temp": vol.Any(TEMP_SCHEMA, TEMP_EXPRESSION_SCHEMA),
        vol.Optional("start", default=None): vol.Any(TIME_SCHEMA, None),
        vol.Optional("end", default=None): vol.Any(TIME_SCHEMA, None),
        vol.Optional("end_plus_days", default=0):
            vol.All(int, vol.Range(min=0)),
        vol.Optional("years"): RANGE_STRING_SCHEMA,
        vol.Optional("months"): RANGE_STRING_SCHEMA,
        vol.Optional("days"): RANGE_STRING_SCHEMA,
        vol.Optional("weeks"): RANGE_STRING_SCHEMA,
        vol.Optional("weekdays"): RANGE_STRING_SCHEMA,
        vol.Optional("start_date"): PARTIAL_DATE_SCHEMA,
        vol.Optional("end_date"): PARTIAL_DATE_SCHEMA,
    },
    build_schedule_rule,
))
SCHEDULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or [],
    [SCHEDULE_RULE_SCHEMA],
    build_schedule,
))

SCHEDULE_SNIPPETS_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Extra: SCHEDULE_SCHEMA,
    },
))

ROOM_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "friendly_name": str,
        vol.Optional("replicate_changes", default=True): bool,
        vol.Optional("reschedule_delay", default=0):
            vol.All(int, vol.Range(min=0)),
        vol.Optional("thermostats", default=dict): DICT_IN_DICT_SCHEMA,
        vol.Optional("window_sensors", default=dict): DICT_IN_DICT_SCHEMA,
        vol.Optional("schedule", default=lambda: build_schedule([])):
            SCHEDULE_SCHEMA,
    },
))
ROOMS_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Extra: ROOM_SCHEMA,
    },
))

CONFIG_SCHEMA = vol.Schema(vol.All(vol.Schema({
    vol.Optional("heaty_id", default="default"): str,
    vol.Optional("untrusted_temp_expressions", default=False): bool,
    vol.Optional("master_switch", default=None):
        vol.Any(ENTITY_ID_SCHEMA, None),
    vol.Optional("off_temp", default=expr.Temp(expr.OFF)): TEMP_SCHEMA,
    vol.Optional("temp_expression_modules", default=dict):
        TEMP_EXPRESSION_MODULES_SCHEMA,
    # defaults sections are not parsed
    vol.Optional("thermostat_defaults", default=dict): lambda v: v or {},
    vol.Optional("window_sensor_defaults", default=dict): lambda v: v or {},
    vol.Optional("schedule_prepend", default=lambda: build_schedule([])):
        SCHEDULE_SCHEMA,
    vol.Optional("schedule_append", default=lambda: build_schedule([])):
        SCHEDULE_SCHEMA,
    vol.Optional("schedule_snippets", default=dict):
        SCHEDULE_SNIPPETS_SCHEMA,
    vol.Optional("rooms", default=dict):
        ROOMS_SCHEMA,
}, extra=True), config_post_hook))
