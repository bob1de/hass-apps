"""
This module implements the custom actor.
"""

import types
import typing as T

import re
import voluptuous as vol

from ... import common
from .. import util
from .base import ActorBase


CONFIG_SCHEMA = vol.Schema({
    "filter_value": vol.All(
        str,
        util.compile_expression,
    ),
    "send": vol.All(
        str,
        util.compile_expression,
    ),
    "state_to_value": vol.All(
        str,
        util.compile_expression,
    ),
    vol.Optional("config", default=dict): vol.All(
        lambda v: v or {},
        dict,
    ),
}, extra=True)


class CustomActor(ActorBase):
    """A fully customizable actor for Schedy."""

    name = "custom"
    config_schema = CONFIG_SCHEMA

    def _exec_script(
            self, expr: types.CodeType, env: T.Dict[str, T.Any]
    ) -> T.Any:
        """evaluates the given expression and returns the value of
        result or None, if unset or an error occured."""

        env = env.copy()
        env.setdefault("app", self.app)
        env.setdefault("config", self.cfg["config"])
        env.setdefault("re", re)

        try:
            exec(expr, env)  # pylint: disable=exec-used
        except Exception as err:  # pylint: disable=broad-except
            self.log("Error while evaluating expression: {}"
                     .format(repr(err)),
                     level="ERROR")
            return None
        return env.get("result")

    def do_send(self) -> None:
        """Executes the configured send script for self.wanted_value."""

        self.log("Executing send script.",
                 level="DEBUG")
        env = {"value": self.wanted_value}
        self._exec_script(self.cfg["send"], env)

    def filter_set_value(self, value: T.Any) -> T.Any:
        """Executes the configured filter_value script."""

        if "send" not in self.cfg:
            self.log("Actor doesn't support sending because of missing "
                     "send script.",
                     level="DEBUG")
            return None

        if "filter_value" in self.cfg:
            env = {"value": value}
            result = self._exec_script(self.cfg["filter_value"], env)
            self.log("Filter rewrote value {} to {}."
                     .format(repr(value), repr(result)),
                     level="WARNING")
            return result
        return value

    def notify_state_changed(self, attrs: dict) -> None:
        """Is called when the entity's state changes."""

        if "state_to_value" not in self.cfg:
            return

        env = {"state": attrs}
        value = self._exec_script(self.cfg["state_to_value"], env)
        self.log("State {} resulted in a value of {}."
                 .format(repr(attrs), repr(value)),
                 level="DEBUG")
        if value is None:
            self.log("Ignoring value of None.", level="DEBUG")
            return

        if value != self.current_value:
            self.log("Received value of {}."
                     .format(repr(value)),
                     prefix=common.LOG_PREFIX_INCOMING)
            self.current_value = value
            self.events.trigger("value_changed", self, value)
