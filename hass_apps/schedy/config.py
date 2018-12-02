"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import typing as T

import traceback
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

    expr = None
    expr_raw = rule.get("expression")
    if expr_raw is not None:
        expr_raw = expr_raw.strip()
        try:
            expr = util.compile_expression(expr_raw)
        except SyntaxError:
            traceback.print_exc(limit=0)
            raise vol.Invalid(
                "Couldn't compile expression: {}".format(repr(expr_raw))
            )

    kwargs = {
        "start_time": rule["start"],
        "end_time": rule["end"],
        "end_plus_days": rule["end_plus_days"],
        "constraints": constraints,
        "expr": expr,
        "expr_raw": expr_raw,
        "value": rule.get("value"),
    }

    if "rules" in rule:
        return schedule.SubScheduleRule(rule["rules"], **kwargs)
    return schedule.Rule(**kwargs)

def build_schedule(rules: T.Iterable[schedule.Rule]) -> schedule.Schedule:
    """Returns a Scheedule containing the given Rule objects."""

    sched = schedule.Schedule()
    for rule in rules:
        sched.rules.append(rule)
    return sched

def config_post_hook(cfg: dict) -> dict:
    """Creates Room and other objects after config has been parsed."""

    # pylint: disable=too-many-locals

    # name schedule snippets
    for name, sched in cfg["schedule_snippets"].items():
        sched.name = name

    actor_type = cfg["actor_type"]

    # Build Room objects.
    rooms = []
    for room_name, room_data in cfg["rooms"].items():
        actors = {}

        # copy defaults from templates and validate the actors
        for actor_name, actor_data in room_data["actors"].items():
            if "default" in cfg["actor_templates"]:
                actor_data.setdefault("template", "default")
            templates = [actor_data]
            while "template" in templates[-1]:
                template_name = templates[-1].pop("template")
                try:
                    template = cfg["actor_templates"][template_name].copy()
                except KeyError:
                    raise vol.ValueInvalid(
                        "No template named {} has been defined."
                        .format(repr(template_name))
                    )
                templates.append(template)

            _actor_data = {
                **actor_type.config_defaults,
            }
            for template in reversed(templates):
                util.deep_merge_dicts(template, _actor_data)
            actor_data = vol.Schema(actor_type.config_schema_dict)(_actor_data)
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
    cfg["_app"].rooms.extend(rooms)

    # Build StatisticalParameter objects.
    stats_params = []
    param_types = {t.name: t for t in actor_type.stats_param_types}
    for param_name, param_data in cfg["statistics"].items():
        param_data = STATISTICAL_PARAMETER_BASE_SCHEMA(param_data)
        param_type_name = param_data.pop("type")
        try:
            param_type = param_types[param_type_name]
        except KeyError:
            raise ValueError(
                "statistical parameter {} is not available for this actor type"
                .format(param_type_name)
            )

        _param_data = {
            **param_type.config_defaults,
        }
        util.deep_merge_dicts(param_data, _param_data)
        param_data = vol.Schema(param_type.config_schema_dict)(_param_data)

        param = param_type(param_name, param_data, cfg["_app"])
        stats_params.append(param)

    cfg["_app"].stats_params.extend(stats_params)

    return cfg

def schedule_rule_pre_hook(rule: dict) -> dict:
    """Copy value for the value key over from alternative names."""

    rule = rule.copy()
    util.normalize_dict_key(rule, "expression", "x")
    util.normalize_dict_key(rule, "value", "v")
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

def build_range_spec_schema(min_value: int, max_value: int) -> vol.Schema:
    """Returns a Schema for validating range specifications with the
    given min/max constraints."""

    return vol.Schema(vol.All(
        vol.Any(int, str),
        lambda v: util.expand_range_spec(v, min_value, max_value),
    ))

ENTITY_ID_SCHEMA = vol.Schema(vol.Match(r"^[A-Za-z_]+\.[A-Za-z0-9_]+$"))
PYTHON_VAR_SCHEMA = vol.Schema(vol.Match(r"^[a-zA-Z_]+[a-zA-Z0-9_]*$"))
PARTIAL_DATE_SCHEMA = vol.Schema({
    vol.Optional("year"): vol.All(int, vol.Range(min=1970, max=2099)),
    vol.Optional("month"): vol.All(int, vol.Range(min=1, max=12)),
    vol.Optional("day"): vol.All(int, vol.Range(min=1, max=31)),
})
TIME_SCHEMA = vol.Schema(vol.All(
    vol.Match(util.TIME_REGEXP),
    util.parse_time_string,
))

# This schema does no real validation and default value insertion,
# it just ensures a dictionary containing string keys and dictionary
# values is given.
DICTS_IN_DICT_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {util.CONF_STR_KEY: vol.All(lambda v: v or {}, dict)},
))

EXPRESSION_MODULE_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "as": PYTHON_VAR_SCHEMA,
    },
))
EXPRESSION_MODULES_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {util.CONF_STR_KEY: EXPRESSION_MODULE_SCHEMA},
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
        vol.Optional("years"): build_range_spec_schema(1970, 2099),
        vol.Optional("months"): build_range_spec_schema(1, 12),
        vol.Optional("days"): build_range_spec_schema(1, 31),
        vol.Optional("weeks"): build_range_spec_schema(1, 53),
        vol.Optional("weekdays"): build_range_spec_schema(1, 7),
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
    {util.CONF_STR_KEY: SCHEDULE_SCHEMA},
))


########## ROOMS

ROOM_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        "friendly_name": str,
        vol.Optional("allow_manual_changes", default=True): bool,
        vol.Optional("replicate_changes", default=True): bool,
        vol.Optional("rescheduling_delay", default=0):
            vol.All(vol.Any(float, int), vol.Range(min=0)),
        vol.Optional("actors", default=dict): DICTS_IN_DICT_SCHEMA,
        vol.Optional("schedule", default=list): vol.All(
            SCHEDULE_SCHEMA,
            validate_rule_paths,
        ),
    },
))


########## STATISTICS

STATISTICAL_PARAMETER_BASE_SCHEMA = vol.Schema({
    vol.Required("type"): str,
}, extra=True)


########## MAIN CONFIG SCHEMA

CONFIG_SCHEMA = vol.Schema(vol.All(
    vol.Schema({
        vol.Optional("reset_at_startup", default=False): bool,
        vol.Optional("expressions_from_events", default=False): bool,
        vol.Optional("expression_modules", default=dict):
            EXPRESSION_MODULES_SCHEMA,
        vol.Required("actor_type"): vol.All(
            vol.Any(*map(lambda a: a.name, actor.get_actor_types())),
            lambda n: {a.name: a for a in actor.get_actor_types()}[n],
        ),
        vol.Optional("actor_templates", default=dict): DICTS_IN_DICT_SCHEMA,
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
            {util.CONF_STR_KEY: ROOM_SCHEMA},
        ),
        vol.Optional("statistics", default=dict): DICTS_IN_DICT_SCHEMA,
    }, extra=True),
    config_post_hook,
))
