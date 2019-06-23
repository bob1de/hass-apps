"""
This module implements the custom actor.
"""

import types
import typing as T

import voluptuous as vol

from .. import util
from .base import ActorBase


class CustomActor(ActorBase):
    """A fully customizable actor for Schedy."""

    name = "custom"
    config_schema_dict = {
        **ActorBase.config_schema_dict,
        vol.Required("send_hook"): vol.All(str, util.compile_expression),
        "state_hook": vol.All(str, util.compile_expression),
        "filter_value_hook": vol.All(str, util.compile_expression),
        vol.Optional("config", default=dict): vol.All(lambda v: v or {}, dict),
    }

    def _exec_script(self, expr: types.CodeType, env: T.Dict[str, T.Any]) -> T.Any:
        """evaluates the given expression and returns the value of
        result or None, if unset or an error occured."""

        env = {**env}
        env.setdefault("entity_id", self.entity_id)
        env.setdefault("config", self.cfg["config"])
        env.setdefault("app", self.app)
        env.setdefault("actor", self)

        try:
            exec(expr, env)  # pylint: disable=exec-used
        except Exception as err:  # pylint: disable=broad-except
            self.log(
                "Error while evaluating expression: {}".format(repr(err)), level="ERROR"
            )
            return None
        return env.get("result")

    def do_send(self) -> None:
        """Executes the configured send script for self._wanted_value."""

        self.log("Executing send script.", level="DEBUG")
        env = {"value": self._wanted_value}
        self._exec_script(self.cfg["send_hook"], env)

    def filter_set_value(self, value: T.Any) -> T.Any:
        """Executes the configured filter_value script."""

        if "filter_value_hook" in self.cfg:
            env = {"value": value}
            result = self._exec_script(self.cfg["filter_value_hook"], env)
            self.log(
                "Filter rewrote value {} to {}.".format(repr(value), repr(result)),
                level="WARNING",
            )
            return result
        return value

    def notify_state_changed(self, attrs: dict) -> T.Any:
        """Is called when the entity's state changes."""

        if "state_hook" not in self.cfg:
            return None

        env = {"state": attrs}
        value = self._exec_script(self.cfg["state_hook"], env)
        self.log(
            "State {} resulted in a value of {}.".format(repr(attrs), repr(value)),
            level="DEBUG",
        )
        if value is None:
            self.log("Ignoring value of None.", level="DEBUG")
            return None
        return value
