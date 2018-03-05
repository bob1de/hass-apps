"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import typing as T

import voluptuous as vol

from . import expr, schedule, thermostat, util, window_sensor
from . import room as _room


def build_schedule_rule(rule: dict) -> schedule.Rule:
    """Builds and returns a schedule rule from the given rule
    definition."""

    constraints = {}
    for name, value in rule.items():
        if name in schedule.Rule.CONSTRAINTS:
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

def build_schedule(rules: T.Iterable[dict]) -> schedule.Schedule:
    """Compiles the given rules and returns a schedule containing them."""

    sched = schedule.Schedule()
    for rule in rules:
        sched.items.append(build_schedule_rule(rule))
    return sched

def config_post_hook(cfg: dict) -> dict:
    """Creates room and thermostat objects after config has been parsed."""

    # Compile the pre/post schedules.
    cfg["schedule_prepend"] = build_schedule(cfg["schedule_prepend"])
    cfg["schedule_append"] = build_schedule(cfg["schedule_append"])

    # Build room objects.
    rooms = []
    for room_name, room_data in cfg["rooms"].items():
        therms = {}
        wsensors = {}

        # copy settings from defaults sections to this room
        for therm_name, therm_data in room_data["thermostats"].items():
            for key, val in cfg["thermostat_defaults"].items():
                therm_data.setdefault(key, val)
            therm_data = THERMOSTAT_SCHEMA(therm_data)
            therms[therm_name] = therm_data
        for wsensor_name, wsensor_data in room_data["window_sensors"].items():
            for key, val in cfg["window_sensor_defaults"].items():
                wsensor_data.setdefault(key, val)
            wsensor_data = WINDOW_SENSOR_SCHEMA(wsensor_data)
            wsensors[wsensor_name] = wsensor_data

        # Compile the room's schedule.
        sched = build_schedule(room_data["schedule"])
        sched.items.insert(0, cfg["schedule_prepend"])
        sched.items.append(cfg["schedule_append"])

        del room_data["thermostats"]
        del room_data["window_sensors"]
        del room_data["schedule"]

        room = _room.Room(room_name, room_data, cfg["_app"])
        rooms.append(room)

        # Create thermostat and window sensor objects and attach to room.
        for therm_name, therm_data in therms.items():
            therm = thermostat.Thermostat(therm_name, therm_data, room)
            room.thermostats.append(therm)
        for wsensor_name, wsensor_data in wsensors.items():
            wsensor = window_sensor.WindowSensor(
                wsensor_name, wsensor_data, room
            )
            room.window_sensors.append(wsensor)

        room.schedule = sched

    del cfg["rooms"], cfg["schedule_prepend"], cfg["schedule_append"]
    cfg["_app"].rooms = rooms

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
    vol.Any(float, int, expr.Off, vol.All(str, lambda v: v.upper(), "OFF")),
    lambda v: expr.Temp(v),  # pylint: disable=unnecessary-lambda
))
TEMP_EXPRESSION_SCHEMA = vol.Schema(str)

# This schema does no real validation and default value insertion,
# it just ensures a dictionary containing dictionaries is returned.
DICTS_IN_DICT_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {vol.Extra: lambda v: v or {}},
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
        "friendly_name": str,
        vol.Optional("delta", default=0): vol.Any(float, int),
        vol.Optional("min_temp", default=None): vol.Any(
            vol.All(TEMP_SCHEMA, vol.NotIn([expr.Temp(expr.OFF)])),
            None,
        ),
        vol.Optional("set_temp_retries", default=10):
            vol.All(int, vol.Range(min=-1)),
        vol.Optional("set_temp_retry_interval", default=30):
            vol.All(int, vol.Range(min=1)),
        vol.Optional("supports_opmodes", default=True): bool,
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
        "friendly_name": str,
        vol.Optional("delay", default=10): vol.All(int, vol.Range(min=0)),
        vol.Optional("open_state", default="on"):
            vol.Any(STATE_SCHEMA, [STATE_SCHEMA]),
    },
))

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
))
SCHEDULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or [],
    [SCHEDULE_RULE_SCHEMA],
))

SCHEDULE_SNIPPETS_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {vol.Extra: SCHEDULE_SCHEMA},
))

ROOM_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "friendly_name": str,
        vol.Optional("replicate_changes", default=True): bool,
        vol.Optional("reschedule_delay", default=0):
            vol.All(int, vol.Range(min=0)),
        vol.Optional("thermostats", default=dict): DICTS_IN_DICT_SCHEMA,
        vol.Optional("window_sensors", default=dict): DICTS_IN_DICT_SCHEMA,
        vol.Optional("schedule", default=list):
            SCHEDULE_SCHEMA,
    },
))

CONFIG_SCHEMA = vol.Schema(vol.All(
    vol.Schema({
        vol.Optional("heaty_id", default="default"): str,
        vol.Optional("untrusted_temp_expressions", default=False): bool,
        vol.Optional("master_switch", default=None):
            vol.Any(ENTITY_ID_SCHEMA, None),
        vol.Optional("off_temp", default=expr.OFF): TEMP_SCHEMA,
        vol.Optional("temp_expression_modules", default=dict):
            TEMP_EXPRESSION_MODULES_SCHEMA,
        vol.Optional("thermostat_defaults", default=dict):
            lambda v: v or {},
        vol.Optional("window_sensor_defaults", default=dict):
            lambda v: v or {},
        vol.Optional("schedule_prepend", default=list):
            SCHEDULE_SCHEMA,
        vol.Optional("schedule_append", default=list):
            SCHEDULE_SCHEMA,
        vol.Optional("schedule_snippets", default=dict):
            SCHEDULE_SNIPPETS_SCHEMA,
        vol.Optional("rooms", default=dict): vol.All(
            lambda v: v or {},
            {vol.Extra: ROOM_SCHEMA},
        ),
    }, extra=True),
    config_post_hook,
))
