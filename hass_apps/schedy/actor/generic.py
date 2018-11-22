"""
This module implements the generic actor.
"""

import typing as T

import voluptuous as vol

from ... import common
from .. import util
from .base import ActorBase


STATE_DEF_SCHEMA = vol.Schema(vol.All(
    lambda v: v or {},
    {
        vol.Required("service"): vol.All(
            str,
            lambda v: v.replace(".", "/", 1),
        ),
        vol.Optional("service_data", default=dict): vol.All(
            lambda v: v or {},
            dict,
        ),
        vol.Optional("include_entity_id", default=True): bool,
        vol.Optional("value_param", default=None): vol.Any(str, None),
    },
))

WILDCARD_STATE_NAME_SCHEMA = vol.Schema(vol.All(
    vol.Coerce(str), str.lower, "_other_",
))


class GenericActor(ActorBase):
    """A configurable, generic actor for Schedy."""

    name = "generic"
    config_schema_dict = {
        **ActorBase.config_schema_dict,
        vol.Optional("state_attr", default="state"): vol.Any(str, None),
        vol.Optional("states", default=dict): vol.All(
            lambda v: v or {},
            {
                vol.Any(WILDCARD_STATE_NAME_SCHEMA, util.CONF_STR_KEY):
                    STATE_DEF_SCHEMA,
            },
        ),
    }

    def _get_state_cfg(self, state: str) -> T.Any:
        """Returns the state configuration for given state or None,
        if unknown. _other_ is respected as well."""

        try:
            return self.cfg["states"][state]
        except KeyError:
            return self.cfg["states"].get("_other_")

    def do_send(self) -> None:
        """Executes the service configured for self._wanted_value."""

        cfg = self._get_state_cfg(self._wanted_value)
        service = cfg["service"]
        service_data = cfg["service_data"].copy()
        if cfg["include_entity_id"]:
            service_data.setdefault("entity_id", self.entity_id)
        if cfg["value_param"] is not None:
            service_data.setdefault(cfg["value_param"], self._wanted_value)

        self.log("Calling service {}, data = {}."
                 .format(repr(service), repr(service_data)),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
        self.app.call_service(service, **service_data)

    def filter_set_value(self, value: T.Any) -> T.Any:
        """Checks whether the actor supports this state."""

        value = str(value)
        if self._get_state_cfg(value) is not None:
            return value

        self.log("State {} is not known by this generic actor, "
                 "ignoring request to set it."
                 .format(repr(value)),
                 level="WARNING")
        return None

    def notify_state_changed(self, attrs: dict) -> T.Any:
        """Is called when the entity's state changes."""

        state_attr = self.cfg["state_attr"]
        if state_attr is None:
            return None
        state = attrs.get(state_attr)
        self.log("Attribute {} is {}."
                 .format(repr(state_attr), repr(state)),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
        if state is None:
            self.log("Ignoring state of None.", level="DEBUG")
            return None

        state = str(state)
        if not self.values_equal(state, self._current_value):
            self.log("Received state of {}."
                     .format(repr(state)),
                     prefix=common.LOG_PREFIX_INCOMING)
        return state

    @staticmethod
    def values_equal(a: T.Any, b: T.Any) -> bool:
        """Compares the string representations of a and b."""

        return str(a) == str(b)
