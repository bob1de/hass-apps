"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import typing as T

import voluptuous as vol

from . import expr, schedule, util
from .room import Room
from .thermostat import Thermostat
from .window_sensor import WindowSensor
from .stats import StatisticsZone


def build_schedule_rule(rule: dict) -> schedule.Rule:
    """Builds and returns a schedule rule from the given rule
    definition."""

    constraints = {}
    for name, value in rule.items():
        if name in schedule.Rule.CONSTRAINTS:
            constraints[name] = value

    kwargs = {
        "start_time": rule["start"],
        "end_time": rule["end"],
        "end_plus_days": rule["end_plus_days"],
        "constraints": constraints,
        "temp_expr": rule.get("value"),
    }

    if "rules" in rule:
        return schedule.SubScheduleRule(rule["rules"], **kwargs)
    return schedule.Rule(**kwargs)

def build_schedule(rules: T.Iterable[dict]) -> schedule.Schedule:
    """Compiles the given rules and returns a schedule containing them."""

    sched = schedule.Schedule()
    for rule in rules:
        sched.rules.append(build_schedule_rule(rule))
    return sched

def config_post_hook(cfg: dict) -> dict:
    """Creates Room and other objects after config has been parsed."""

    # pylint: disable=too-many-locals

    # name schedule snippets
    for name, sched in cfg["schedule_snippets"].items():
        sched.name = name

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

        # complete the room's schedule.
        sched = cfg["schedule_prepend"] + room_data["schedule"] + \
                cfg["schedule_append"]
        sched.name = room_name

        del room_data["thermostats"]
        del room_data["window_sensors"]
        del room_data["schedule"]

        room = Room(room_name, room_data, cfg["_app"])
        rooms.append(room)

        # Create thermostat and window sensor objects and attach to room.
        for therm_name, therm_data in therms.items():
            therm = Thermostat(therm_name, therm_data, room)
            room.thermostats.append(therm)
        for wsensor_name, wsensor_data in wsensors.items():
            wsensor = WindowSensor(wsensor_name, wsensor_data, room)
            room.window_sensors.append(wsensor)

        room.schedule = sched
    del cfg["rooms"], cfg["schedule_prepend"], cfg["schedule_append"]
    cfg["_app"].rooms = rooms

    szones = []
    for zone_name, zone_cfg in cfg["statistics"].items():
        zone = StatisticsZone(zone_name, zone_cfg, cfg["_app"])
        szones.append(zone)
    del cfg["statistics"]
    cfg["_app"].stats_zones = szones

    return cfg

def schedule_rule_pre_hook(rule: dict) -> dict:
    """Copy value for the value key over from alternative names."""

    rule = rule.copy()
    for key in ("v", "temp"):
        if key in rule:
            rule.setdefault("value", rule[key])
            del rule[key]
    return rule

def validate_rule_paths(sched: schedule.Schedule) -> schedule.Schedule:
    """A validator to be run after schedule creation to ensure
    each path contains at least one rule with a temperature expression.
    A ValueError is raised when this check fails."""

    for path in sched.unfold():
        if path.is_final and not list(path.rules_with_temp):
            raise ValueError(
                "No temperature specified for any rule along the path {}."
                .format(path)
            )

    return sched


########## MISCELLANEOUS

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
TIME_SCHEMA = vol.Schema(vol.All(
    vol.Match(util.TIME_REGEXP),
    util.parse_time_string,
))
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
TEMP_EXPRESSION_MODULES_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Extra: TEMP_EXPRESSION_MODULE_SCHEMA,
    },
))


########## THERMOSTATS

THERMOSTAT_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "friendly_name": str,
        vol.Optional("delta", default=0): vol.Any(float, int),
        vol.Optional("min_temp", default=None): vol.Any(
            vol.All(TEMP_SCHEMA, vol.NotIn([expr.Temp(expr.OFF)])),
            None,
        ),
        vol.Optional("max_temp", default=None): vol.Any(
            vol.All(TEMP_SCHEMA, vol.NotIn([expr.Temp(expr.OFF)])),
            None,
        ),
        vol.Optional("off_temp", default=expr.OFF): TEMP_SCHEMA,
        vol.Optional("set_temp_retries", default=10):
            vol.All(int, vol.Range(min=-1)),
        vol.Optional("set_temp_retry_interval", default=30):
            vol.All(int, vol.Range(min=1)),
        vol.Optional("supports_opmodes", default=True): bool,
        vol.Optional("supports_temps", default=True): bool,
        vol.Optional("opmode_heat", default="heat"): str,
        vol.Optional("opmode_off", default="off"): str,
        vol.Optional(
            "opmode_heat_service", default="climate/set_operation_mode"
        ): str,
        vol.Optional(
            "opmode_off_service", default="climate/set_operation_mode"
        ): str,
        vol.Optional("opmode_heat_service_attr", default="operation_mode"):
            vol.Any(str, None),
        vol.Optional("opmode_off_service_attr", default="operation_mode"):
            vol.Any(str, None),
        vol.Optional("opmode_state_attr", default="operation_mode"): str,
        vol.Optional(
            "target_temp_service", default="climate/set_temperature"
        ): str,
        vol.Optional("target_temp_service_attr", default="temperature"): str,
        vol.Optional("target_temp_state_attr", default="temperature"): str,
        vol.Optional(
            "current_temp_state_attr", default="current_temperature"
        ): vol.Any(str, None),
    },
))


########## WINDOW SENSORS

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


########## SCHEDULES

SCHEDULE_RULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    schedule_rule_pre_hook,
    {
        "rules": lambda v: SCHEDULE_SCHEMA(v),  # type: ignore  # pylint: disable=unnecessary-lambda
        "value": vol.Any(TEMP_SCHEMA, TEMP_EXPRESSION_SCHEMA),
        vol.Optional("name", default=None): vol.Any(str, None),
        vol.Optional("start", default=None): vol.Any(TIME_SCHEMA, None),
        vol.Optional("end", default=None): vol.Any(TIME_SCHEMA, None),
        vol.Optional("end_plus_days", default=None):
            vol.Any(vol.All(int, vol.Range(min=0)), None),
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
    build_schedule,
))

SCHEDULE_SNIPPETS_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Extra: vol.All(
            SCHEDULE_SCHEMA,
            validate_rule_paths,
        ),
    },
))


########## ROOMS

ROOM_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "friendly_name": str,
        vol.Optional("replicate_changes", default=True): bool,
        vol.Optional("reschedule_delay", default=0):
            vol.All(int, vol.Range(min=0)),
        vol.Optional("thermostats", default=dict): DICTS_IN_DICT_SCHEMA,
        vol.Optional("window_sensors", default=dict): DICTS_IN_DICT_SCHEMA,
        vol.Optional("schedule", default=list): vol.All(
            SCHEDULE_SCHEMA,
            validate_rule_paths,
        ),
    },
))


########## STATISTICS

STATS_ZONE_ROOM_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        # More parameters may be added here in the future.
    },
))

STATS_ZONE_PARAM_THERMOSTAT_SETTINGS_ADDIN = {
    vol.Optional("thermostat_factors", default=dict): vol.All(
        lambda v: v or {},
        {
            vol.Extra: vol.All(vol.Any(float, int),
                               vol.Range(min=0), min_included=False),
        },
    ),
    vol.Optional("thermostat_weights", default=dict): vol.All(
        lambda v: v or {},
        {
            vol.Extra: vol.All(vol.Any(float, int), vol.Range(min=0)),
        },
    ),
}

STATS_ZONE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "friendly_name": str,
        vol.Optional("rooms", default=dict): vol.All(
            lambda v: v or {},
            {vol.Extra: STATS_ZONE_ROOM_SCHEMA},
        ),
        vol.Optional("parameters", default=dict): vol.All(
            lambda v: v or {},
            {
                "temp_delta": vol.All(
                    lambda v: v or {},
                    util.mixin_dict({
                        vol.Optional("off_value", default=0): vol.Any(
                            float, int, None
                        ),
                    }, STATS_ZONE_PARAM_THERMOSTAT_SETTINGS_ADDIN),
                ),
            },
        ),
    },
))


########## MAIN CONFIG SCHEMA

CONFIG_SCHEMA = vol.Schema(vol.All(
    vol.Schema({
        vol.Optional("heaty_id", default="default"): str,
        vol.Optional("master_switch", default=None):
            vol.Any(ENTITY_ID_SCHEMA, None),
        vol.Optional("master_off_temp", default=expr.OFF): TEMP_SCHEMA,
        vol.Optional("window_open_temp", default=expr.OFF): TEMP_SCHEMA,
        vol.Optional("reschedule_at_startup", default=True): bool,
        vol.Optional("untrusted_temp_expressions", default=False): bool,
        vol.Optional("temp_expression_modules", default=dict):
            TEMP_EXPRESSION_MODULES_SCHEMA,
        vol.Optional("thermostat_defaults", default=dict):
            lambda v: v or {},
        vol.Optional("window_sensor_defaults", default=dict):
            lambda v: v or {},
        vol.Optional("schedule_prepend", default=list): vol.All(
            SCHEDULE_SCHEMA,
            validate_rule_paths,
        ),
        vol.Optional("schedule_append", default=list): vol.All(
            SCHEDULE_SCHEMA,
            validate_rule_paths,
        ),
        vol.Optional("schedule_snippets", default=dict):
            SCHEDULE_SNIPPETS_SCHEMA,
        vol.Optional("rooms", default=dict): vol.All(
            lambda v: v or {},
            {vol.Extra: ROOM_SCHEMA},
        ),
        vol.Optional("statistics", default=dict): vol.All(
            lambda v: v or {},
            {vol.Extra: STATS_ZONE_SCHEMA},
        ),
    }, extra=True),
    config_post_hook,
))
