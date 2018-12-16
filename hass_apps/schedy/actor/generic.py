"""
This module implements the generic actor.
"""

import typing as T

import voluptuous as vol

from ... import common
from .base import ActorBase


ALLOWED_VALUE_TYPES = (float, int, str, type(None))

VALUE_DEF_SCHEMA = vol.Schema(vol.All(
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
        vol.Optional("value_parameter", default=None):
            vol.Any(str, None),
    },
))

WILDCARD_VALUE_SCHEMA = vol.Schema(vol.All(
    vol.Coerce(str), str.lower, "_other_",
))


class GenericActor(ActorBase):
    """A configurable, generic actor for Schedy that can control multiple
    attributes at once."""

    name = "generic"
    config_schema_dict = {
        **ActorBase.config_schema_dict,
        vol.Optional("attributes", default=list): vol.All(
            lambda v: v or [],
            [
                vol.All(
                    lambda v: v or {},
                    {
                        vol.Optional("attribute", default=None):
                            vol.Any(str, None),
                        vol.Optional("values", default=dict): vol.All(
                            lambda v: v or {},
                            {
                                vol.Any(
                                    WILDCARD_VALUE_SCHEMA, *ALLOWED_VALUE_TYPES
                                ): VALUE_DEF_SCHEMA,
                            },
                        ),
                    },
                ),
            ],
        ),
    }

    def _get_value_cfg(self, index: int, value: str) -> T.Any:
        """Returns the value configuration for given attribute index
        and value or None, if unknown. _other_ is respected as well."""

        try:
            return self.cfg["attributes"][index]["values"][value]
        except KeyError:
            return self.cfg["attributes"][index]["values"].get("_other_")

    def do_send(self) -> None:
        """Executes the services configured for self._wanted_value."""

        value = self._wanted_value
        if len(self.cfg["attributes"]) == 1:
            value = (value,)

        for index in range(len(self.cfg["attributes"])):
            cfg = self._get_value_cfg(index, value[index])
            service = cfg["service"]
            service_data = cfg["service_data"].copy()
            if cfg["include_entity_id"]:
                service_data.setdefault("entity_id", self.entity_id)
            if cfg["value_parameter"] is not None:
                service_data.setdefault(cfg["value_parameter"], value[index])

            self.log("Calling service {}, data = {}."
                     .format(repr(service), repr(service_data)),
                     level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
            self.app.call_service(service, **service_data)

    def filter_set_value(self, value: T.Any) -> T.Any:
        """Checks whether the actor supports this value."""

        if not isinstance(value, tuple):
            value = (value,)
        if len(value) != len(self.cfg["attributes"]):
            self.log("The value {} has not the expected number of items ({})."
                     .format(repr(value), len(self.cfg["attributes"])),
                     level="ERROR")
            return None

        _value = []
        for index, item in enumerate(value):
            if self._get_value_cfg(index, item) is None:
                self.log("VALUe {} for slot {} is not known by this "
                         "generic actor, ignoring request to set it."
                         .format(repr(item), index),
                         level="ERROR")
                return None
            _value.append(item)

        return value[0] if len(_value) == 1 else tuple(_value)

    def notify_state_changed(self, attrs: dict) -> T.Any:
        """Is called when the entity's state changes."""

        items = []  # type: T.List[T.Any]
        for cfg in self.cfg["attributes"]:
            attr = cfg["attribute"]
            if attr is None:
                # write-only slot, can never be determined
                items.append(None)
                continue
            state = attrs.get(attr)
            self.log("Attribute {} is {}."
                     .format(repr(attr), repr(state)),
                     level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
            if state is None:
                self.log("Ignoring state of None.", level="DEBUG")
                return None
            items.append(state)
        return items[0] if len(items) == 1 else tuple(items)

    @staticmethod
    def validate_value(value: T.Any) -> T.Any:
        """Converts lists to tuples."""

        if isinstance(value, list):
            items = tuple(value)
        elif isinstance(value, tuple):
            items = value
        else:
            items = (value,)

        for index, item in enumerate(items):
            if not isinstance(item, ALLOWED_VALUE_TYPES):
                raise ValueError(
                    "Value {} for slot {} must be of one of these types: {}"
                    .format(repr(item), index, ALLOWED_VALUE_TYPES)
                )

        return items[0] if len(items) == 1 else items
