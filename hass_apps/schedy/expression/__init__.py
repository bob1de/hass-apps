"""
Module containing functionality to evaluate expressions.
"""

import types as _types
import typing as T

if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from .. import schedule
    from ..room import Room

import datetime
import inspect

from . import helpers
from . import types  # pylint: disable=reimported


def build_expr_env(room: "Room", now: datetime.datetime) -> T.Dict[str, T.Any]:
    """This function builds and returns an environment usable as globals
    for the evaluation of an expression.
    It will add all members of the .types module's __all__ to the
    environment.
    Additionally, helpers provided by the .helpers module and the actor
    type will be constructed based on the Room object"""

    env = {}  # type: T.Dict[str, T.Any]
    for member_name in types.__all__:
        env[member_name] = getattr(types, member_name)

    helper_types = []
    for member_name, member in inspect.getmembers(helpers):
        if (
            member is not helpers.HelperBase
            and isinstance(member, type)
            and issubclass(member, helpers.HelperBase)
        ):
            helper_types.append(member)

    assert room.app.actor_type is not None
    helper_types.extend(room.app.actor_type.expression_helpers)

    helper_types.sort(key=lambda t: t.order)
    for helper_type in helper_types:
        room.log(
            "Initializing expression helper: {}, order = {}".format(
                helper_type.__name__, helper_type.order
            ),
            level="DEBUG",
        )
        helper = helper_type(room, now, env)
        helper.update_environment()

    return env


def eval_expr(expr: _types.CodeType, env: T.Dict[str, T.Any]) -> T.Any:
    """This method evaluates the given expression. The evaluation result
    is returned. The items of the env dict are added to the globals
    available during evaluation."""

    env = {**env}
    exec(expr, env)  # pylint: disable=exec-used
    return env.get("result")
