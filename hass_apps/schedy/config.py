"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import typing as T

import datetime
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
            raise vol.Invalid("Couldn't compile expression: {}".format(repr(expr_raw)))

    kwargs = {
        "start_time": rule["start"][0],
        "start_plus_days": rule["start"][1],
        "end_time": rule["end"][0],
        "end_plus_days": rule["end"][1],
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
    cfg["schedule_prepend"].name = "prepend"
    cfg["schedule_append"].name = "append"
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
                        "No template named {} has been defined.".format(
                            repr(template_name)
                        )
                    )
                templates.append(template)

            _actor_data = {**actor_type.config_defaults}
            for template in reversed(templates):
                util.deep_merge_dicts(template, _actor_data)
            actor_data = vol.Schema(actor_type.config_schema_dict)(_actor_data)
            actors[actor_name] = actor_data

        # complete the room's schedule.
        rules = []
        if cfg["schedule_prepend"].rules:
            rules.append(schedule.SubScheduleRule(cfg["schedule_prepend"]))
        if room_data["schedule"].rules:
            room_data["schedule"].name = "room-individual"
            rules.append(schedule.SubScheduleRule(room_data["schedule"]))
        if cfg["schedule_append"].rules:
            rules.append(schedule.SubScheduleRule(cfg["schedule_append"]))
        sched = schedule.Schedule(name=room_name, rules=rules)

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
                "statistical parameter {} is not available for this actor type".format(
                    param_type_name
                )
            )

        _param_data = {**param_type.config_defaults}
        util.deep_merge_dicts(param_data, _param_data)
        param_data = vol.Schema(param_type.config_schema_dict)(_param_data)

        param = param_type(param_name, param_data, cfg["_app"])
        stats_params.append(param)

    cfg["_app"].stats_params.extend(stats_params)

    return cfg


def schedule_rule_pre_hook(rule: dict) -> dict:
    """Copy value for the expression and value keys over from alternative names."""

    rule = rule.copy()
    util.normalize_dict_key(rule, "expression", "x")
    util.normalize_dict_key(rule, "value", "v")
    return rule


def validate_rule_paths(sched: schedule.Schedule) -> schedule.Schedule:
    """A validator to be run after schedule creation to ensure
    each path contains at least one rule with an expression or value.
    A ValueError is raised when this check fails."""

    for path in sched.unfolded:
        if path.is_final and not list(path.rules_with_expr_or_value):
            raise ValueError(
                "No expression or value specified along the path {}.".format(path)
            )

    return sched


########## MISCELLANEOUS


def build_range_spec_validator(  # type: ignore
    min_value: int, max_value: int
) -> vol.Schema:
    """Returns a validator for range specifications with the given
    min/max values."""

    return vol.All(
        vol.Any(int, str), lambda v: util.expand_range_spec(v, min_value, max_value)
    )


ENTITY_ID_VALIDATOR = vol.Match(r"^[A-Za-z_]+\.[A-Za-z0-9_]+$")
PARTIAL_DATE_SCHEMA = vol.Schema(
    {
        vol.Optional("year"): vol.All(int, vol.Range(min=1970, max=2099)),
        vol.Optional("month"): vol.All(int, vol.Range(min=1, max=12)),
        vol.Optional("day"): vol.All(int, vol.Range(min=1, max=31)),
    }
)
TIME_VALIDATOR = vol.All(vol.Match(util.TIME_REGEXP), util.parse_time_string)
RULE_TIME_VALIDATOR = vol.All(
    vol.Match(
        util.RULE_TIME_REGEXP, msg="correct format: [<HH>:<MM>[:<SS>]][{+-}<days>d]"
    ),
    util.parse_rule_time_string,
)

# This schema does no real validation and default value insertion,
# it just ensures a dictionary containing string keys and dictionary
# values is given.
DICTS_IN_DICT_SCHEMA = vol.Schema(
    vol.All(lambda v: v or {}, {util.CONF_STR_KEY: vol.All(lambda v: v or {}, dict)})
)


def parse_watched_entity_str(value: str) -> T.Dict[str, T.Any]:
    """Parses the alternative <entity>:<attributes>:<mode> strings."""

    obj = {}  # type: T.Dict[str, T.Any]
    spl = [part.strip() for part in value.split(":")]
    if spl:
        part = spl.pop(0)
        if part:
            obj["entity"] = part
    if spl:
        part = spl.pop(0)
        if part:
            obj["attributes"] = [_part.strip() for _part in part.split(",")]
    if spl:
        part = spl.pop(0)
        if part:
            obj["mode"] = part
    return obj


WATCHED_ENTITY_SCHEMA = vol.Schema(
    vol.All(
        lambda v: v or {},
        vol.Any(vol.All(str, parse_watched_entity_str), object),
        {
            vol.Required("entity"): ENTITY_ID_VALIDATOR,
            vol.Optional("attributes", default="state"): vol.Any(
                vol.All(str, lambda v: [v]), [str]
            ),
            vol.Optional("mode", default="reevaluate"): vol.Any(
                "reevaluate", "reset", "ignore"
            ),
        },
    )
)
WATCHED_ENTITIES_SCHEMA = vol.Schema(
    vol.All(lambda v: v or [], [WATCHED_ENTITY_SCHEMA])
)


########## SCHEDULES

SCHEDULE_RULE_SCHEMA = vol.Schema(
    vol.All(
        lambda v: v or {},
        schedule_rule_pre_hook,
        {
            "rules": lambda v: SCHEDULE_SCHEMA(  # type: ignore  # pylint: disable=unnecessary-lambda
                v
            ),
            "expression": str,
            "value": object,
            vol.Optional("name", default=None): vol.Any(str, None),
            vol.Optional("start", default=(None, None)): vol.Any(
                RULE_TIME_VALIDATOR, (None,)
            ),
            vol.Optional("end", default=(None, None)): vol.Any(
                vol.All(
                    RULE_TIME_VALIDATOR,
                    (
                        None,
                        datetime.time,
                        vol.Range(min=0, msg="end time can't be shifted backwards"),
                    ),
                ),
                (None,),
            ),
            vol.Optional("years"): build_range_spec_validator(1970, 2099),
            vol.Optional("months"): build_range_spec_validator(1, 12),
            vol.Optional("days"): build_range_spec_validator(1, 31),
            vol.Optional("weeks"): build_range_spec_validator(1, 53),
            vol.Optional("weekdays"): build_range_spec_validator(1, 7),
            vol.Optional("start_date"): PARTIAL_DATE_SCHEMA,
            vol.Optional("end_date"): PARTIAL_DATE_SCHEMA,
        },
        build_schedule_rule,
    )
)

SCHEDULE_SCHEMA = vol.Schema(
    vol.All(lambda v: v or [], [SCHEDULE_RULE_SCHEMA], build_schedule)
)

SCHEDULE_SNIPPETS_SCHEMA = vol.Schema(
    vol.All(lambda v: v or {}, {util.CONF_STR_KEY: SCHEDULE_SCHEMA})
)


########## ROOMS

ROOM_SCHEMA = vol.Schema(
    vol.All(
        lambda v: v or {},
        {
            "friendly_name": str,
            vol.Optional("allow_manual_changes", default=True): bool,
            vol.Optional("replicate_changes", default=True): bool,
            vol.Optional("rescheduling_delay", default=0): vol.All(
                vol.Any(float, int), vol.Range(min=0)
            ),
            vol.Optional("actors", default=dict): DICTS_IN_DICT_SCHEMA,
            vol.Optional("watched_entities", default=None): WATCHED_ENTITIES_SCHEMA,
            vol.Optional("schedule", default=list): vol.All(
                SCHEDULE_SCHEMA, validate_rule_paths
            ),
        },
    )
)


########## STATISTICS

STATISTICAL_PARAMETER_BASE_SCHEMA = vol.Schema({vol.Required("type"): str}, extra=True)


########## MAIN CONFIG SCHEMA

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        vol.Schema(
            {
                vol.Optional("reset_at_startup", default=False): bool,
                vol.Optional("expressions_from_events", default=False): bool,
                vol.Optional("expression_environment", default=None): vol.Any(
                    str, None
                ),
                vol.Required("actor_type"): vol.All(
                    vol.Any(*map(lambda a: a.name, actor.get_actor_types())),
                    lambda n: {a.name: a for a in actor.get_actor_types()}[n],
                ),
                vol.Optional("actor_templates", default=dict): DICTS_IN_DICT_SCHEMA,
                vol.Optional("watched_entities", default=dict): WATCHED_ENTITIES_SCHEMA,
                vol.Optional("schedule_prepend", default=list): vol.All(
                    SCHEDULE_SCHEMA, validate_rule_paths
                ),
                vol.Optional("schedule_append", default=list): vol.All(
                    SCHEDULE_SCHEMA, validate_rule_paths
                ),
                vol.Optional(
                    "schedule_snippets", default=dict
                ): SCHEDULE_SNIPPETS_SCHEMA,
                vol.Optional("rooms", default=dict): vol.All(
                    lambda v: v or {}, {util.CONF_STR_KEY: ROOM_SCHEMA}
                ),
                vol.Optional("statistics", default=dict): DICTS_IN_DICT_SCHEMA,
            },
            extra=True,
        ),
        config_post_hook,
    )
)
