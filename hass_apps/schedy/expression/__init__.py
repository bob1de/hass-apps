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

from . import helpers
from . import types  # pylint: disable=reimported


def build_expr_env(room: "Room", now: datetime.datetime) -> T.Dict[str, T.Any]:
    """This function builds and returns an environment usable as globals
    for the evaluation of an expression.
    It will add all members of the .types module's __all__ to the
    environment.
    Additionally, helpers provided by the .helpers module and the actor
    type will be constructed based on the Room object"""

    def _add_helper(helper_type: T.Type[helpers.HelperBase]) -> None:
        helper = helper_type(room, now)
        if helper.namespace:
            env[helper.namespace] = helper
        else:
            for member in dir(helper):
                if not member.startswith("_") and \
                   not hasattr(helpers.HelperBase, member):
                    env[member] = getattr(helper, member)

    env = {}  # type: T.Dict[str, T.Any]

    for member in types.__all__:
        env[member] = getattr(types, member)

    for member in dir(helpers):
        obj = getattr(helpers, member)
        if obj is not helpers.HelperBase and \
           isinstance(obj, type) and issubclass(obj, helpers.HelperBase):
            _add_helper(obj)

    assert room.app.actor_type is not None
    for helper_type in room.app.actor_type.expression_helpers:
        _add_helper(helper_type)

    return env

def eval_expr(
        expr: _types.CodeType, room: "Room", now: datetime.datetime,
        extra_env: T.Optional[T.Dict[str, T.Any]] = None
) -> T.Any:
    """This method evaluates the given expression. The evaluation result
    is returned. The items of the extra_env dict are added to the globals
    available during evaluation."""

    env = build_expr_env(room, now)
    if extra_env:
        env.update(extra_env)

    exec(expr, env)  # pylint: disable=exec-used
    return env.get("result")
