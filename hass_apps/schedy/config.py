"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import typing as T

import voluptuous as vol

from . import actor, schedule, util
from .room import Room


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
        "expr_raw": rule.get("expression"),
        "value": rule.get("value"),
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

    actor_type = cfg["actor_type"]

    # Build room objects.
    rooms = []
    for room_name, room_data in cfg["rooms"].items():
        actors = {}

        # copy defaults from templates and validate the actors
        for actor_name, actor_data in room_data["actors"].items():
            template_name = actor_data.get("template", "default")
            try:
                template = cfg["actor_templates"][template_name]
            except KeyError:
                raise vol.ValueInvalid(
                    "No template named {} has been defined."
                    .format(repr(template_name))
                )
            util.deep_merge_dicts(template, actor_data)
            actor_data = ACTOR_SCHEMA(actor_data)
            actor_data = actor_type.config_schema(actor_data)
            actors[actor_name] = actor_data

        # complete the room's schedule.
        sched = cfg["schedule_prepend"] + room_data["schedule"] + \
                cfg["schedule_append"]
        sched.name = room_name

        del room_data["actors"]
        del room_data["schedule"]

        room = Room(room_name, room_data, cfg["_app"])
        rooms.append(room)

        # Create actor objects and attach to room.
        for actor_name, actor_data in actors.items():
            _actor = actor_type(actor_name, actor_data, room)
            room.actors.append(_actor)

        room.schedule = sched

    del cfg["rooms"], cfg["schedule_prepend"], cfg["schedule_append"]
    cfg["_app"].actor_type = actor_type
    cfg["_app"].rooms = rooms

    return cfg

def schedule_rule_pre_hook(rule: dict) -> dict:
    """Copy value for the value key over from alternative names."""

    rule = rule.copy()
    replacements = {"v":"value", "x":"expression"}
    for key, replacement in replacements.items():
        if key in rule:
            rule.setdefault(replacement, rule[key])
            del rule[key]
    return rule

def validate_rule_paths(sched: schedule.Schedule) -> schedule.Schedule:
    """A validator to be run after schedule creation to ensure
    each path contains at least one rule with an expression or value.
    A ValueError is raised when this check fails."""

    for path in sched.unfold():
        if path.is_final and not list(path.rules_with_expr_or_value):
            raise ValueError(
                "No expression or value specified along the path {}."
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

# This schema does no real validation and default value insertion,
# it just ensures a dictionary containing dictionaries is returned.
DICTS_IN_DICT_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {vol.Extra: vol.All(lambda v: v or {}, dict)},
))

EXPRESSION_MODULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "as": PYTHON_VAR_SCHEMA,
    },
))
EXPRESSION_MODULES_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Extra: EXPRESSION_MODULE_SCHEMA,
    },
))


########## ACTORS

ACTOR_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    vol.Schema({
        "friendly_name": str,
        vol.Optional("send_retries", default=10):
            vol.All(int, vol.Range(min=-1)),
        vol.Optional("send_retry_interval", default=30):
            vol.All(int, vol.Range(min=1)),
    }, extra=True),
))


########## SCHEDULES

SCHEDULE_RULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    schedule_rule_pre_hook,
    {
        "rules": lambda v: SCHEDULE_SCHEMA(v),  # type: ignore  # pylint: disable=unnecessary-lambda
        "expression": str,
        "value": object,
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
        vol.Optional("actors", default=dict): DICTS_IN_DICT_SCHEMA,
        vol.Optional("schedule", default=list): vol.All(
            SCHEDULE_SCHEMA,
            validate_rule_paths,
        ),
    },
))


########## MAIN CONFIG SCHEMA

CONFIG_SCHEMA = vol.Schema(vol.All(
    vol.Schema({
        vol.Optional("reschedule_at_startup", default=True): bool,
        vol.Optional("expressions_from_events", default=False): bool,
        vol.Optional("expression_modules", default=dict):
            EXPRESSION_MODULES_SCHEMA,
        vol.Required("actor_type"): vol.All(
            vol.Any(*map(lambda a: a.name, actor.get_actor_types())),
            lambda n: {a.name: a for a in actor.get_actor_types()}[n],
        ),
        vol.Optional("actor_templates", default=dict): vol.All(
            DICTS_IN_DICT_SCHEMA,
            lambda v: v.setdefault("default", {}) and False or v,
        ),
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
    }, extra=True),
    config_post_hook,
))
