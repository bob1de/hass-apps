"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import voluptuous as vol

from . import schedule, util


# all constraints that have values in the range_string format
# (see util.expand_range_string)
RANGE_STRING_CONSTRAINTS = ("years", "months", "days", "weeks", "weekdays")


def build_schedule_rule(rule):
    """Builds and returns a schedule rule from the given rule
    definition."""

    constraints = {}
    for name, value in rule.items():
        if name in RANGE_STRING_CONSTRAINTS:
            constraints[name] = util.expand_range_string(value)

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
        for therm in room["thermostats"].values():
            for key, val in cfg["thermostat_defaults"].items():
                therm.setdefault(key, val)
            therm["current_temp"] = None
        for sensor in room["window_sensors"].values():
            for key, val in cfg["window_sensor_defaults"].items():
                sensor.setdefault(key, val)

    return cfg


ENTITY_ID_SCHEMA = vol.Schema(vol.Match(r"^[A-Za-z_]+\.[A-Za-z0-9_]+$"))
PYTHON_VAR_SCHEMA = vol.Schema(vol.Match(r"^[a-zA-Z_]+[a-zA-Z0-9_]*$"))
RANGE_STRING_SCHEMA = vol.Schema(vol.Match(r"^ *\d+( *\- *\d+)?( *\, *\d+( *\- *\d+)?)* *$"))
TIME_SCHEMA = vol.Schema(vol.Match(r"^ *([01]\d|2[0123]) *\: *([012345]\d) *$"))

TEMP_SCHEMA = vol.Schema(vol.Any(float, int, "off"))
TEMP_EXPRESSION_SCHEMA = vol.Schema(str)

TEMP_EXPRESSION_MODULE_SCHEMA = vol.Schema({
    "as": PYTHON_VAR_SCHEMA,
})
TEMP_EXPRESSION_MODULES_SCHEMA = vol.Schema({
    vol.Extra: lambda v: TEMP_EXPRESSION_MODULE_SCHEMA(v or {}),
})

THERMOSTAT_SCHEMA = vol.Schema({
    vol.Optional("delta", default=0): float,
    vol.Optional("min_temp", default=None): vol.Any(TEMP_SCHEMA, None),
    vol.Optional("set_temp_retries", default=10):
        vol.All(int, vol.Range(min=-1)),
    vol.Optional("set_temp_retry_interval", default=30):
        vol.All(int, vol.Range(min=1)),
    vol.Optional("opmode_heat", default="Heat"): str,
    vol.Optional("opmode_off", default="Off"): str,
    vol.Optional("opmode_service", default="climate/set_operation_mode"): str,
    vol.Optional("opmode_service_attr", default="operation_mode"): str,
    vol.Optional("opmode_state_attr", default="operation_mode"): str,
    vol.Optional("temp_service", default="climate/set_temperature"): str,
    vol.Optional("temp_service_attr", default="temperature"): str,
    vol.Optional("temp_state_attr", default="temperature"): str,
})
THERMOSTATS_SCHEMA = vol.Schema({
    vol.Extra: lambda v: THERMOSTAT_SCHEMA(v or {}),
})

WINDOW_SENSOR_SCHEMA = vol.Schema({
    vol.Optional("delay", default=10): vol.All(int, vol.Range(min=0)),
    vol.Optional("inverted", default=False): bool,
})
WINDOW_SENSORS_SCHEMA = vol.Schema({
    vol.Extra: lambda v: WINDOW_SENSOR_SCHEMA(v or {}),
})

SCHEDULE_RULE_SCHEMA = vol.Schema(vol.All({
    "temp": vol.Any(TEMP_SCHEMA, TEMP_EXPRESSION_SCHEMA),
    vol.Optional("start", default=None): vol.Any(TIME_SCHEMA, None),
    vol.Optional("end", default=None): vol.Any(TIME_SCHEMA, None),
    vol.Optional("end_plus_days", default=0): vol.All(int, vol.Range(min=0)),
    vol.Optional("years"): vol.Any(RANGE_STRING_SCHEMA, int),
    vol.Optional("months"): vol.Any(RANGE_STRING_SCHEMA, int),
    vol.Optional("days"): vol.Any(RANGE_STRING_SCHEMA, int),
    vol.Optional("weeks"): vol.Any(RANGE_STRING_SCHEMA, int),
    vol.Optional("weekdays"): vol.Any(RANGE_STRING_SCHEMA, int),
}, build_schedule_rule))
SCHEDULE_SCHEMA = vol.Schema(vol.All([SCHEDULE_RULE_SCHEMA], build_schedule))

ROOM_SCHEMA = vol.Schema({
    "friendly_name": str,
    vol.Optional("replicate_changes", default=True): bool,
    vol.Optional("reschedule_delay", default=0):
        vol.All(int, vol.Range(min=0)),
    vol.Optional("thermostats", default=dict):
        lambda v: THERMOSTATS_SCHEMA(v or {}),
    vol.Optional("window_sensors", default=dict):
        lambda v: WINDOW_SENSORS_SCHEMA(v or {}),
    vol.Optional("schedule", default=list): SCHEDULE_SCHEMA,
})
ROOMS_SCHEMA = vol.Schema({
    vol.Extra: lambda v: ROOM_SCHEMA(v or {}),
})

CONFIG_SCHEMA = vol.Schema(vol.All(vol.Schema({
    vol.Optional("heaty_id", default="default"): str,
    vol.Optional("untrusted_temp_expressions", default=False): bool,
    vol.Optional("master_switch", default=None):
        vol.Any(ENTITY_ID_SCHEMA, None),
    vol.Optional("off_temp", default="off"): TEMP_SCHEMA,
    vol.Optional("temp_expression_modules", default=dict):
        lambda v: TEMP_EXPRESSION_MODULES_SCHEMA(v or {}),
    vol.Optional("thermostat_defaults", default=dict): THERMOSTAT_SCHEMA,
    vol.Optional("window_sensor_defaults", default=dict):
        WINDOW_SENSOR_SCHEMA,
    vol.Optional("schedule_prepend", default=list):
        lambda v: SCHEDULE_SCHEMA(v or []),
    vol.Optional("schedule_append", default=list):
        lambda v: SCHEDULE_SCHEMA(v or []),
    vol.Optional("rooms", default=dict): lambda v: ROOMS_SCHEMA(v or {}),
}, extra=True), config_post_hook))
