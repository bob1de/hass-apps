"""
This module implements the generic actor.
"""

import typing as T

import copy

import voluptuous as vol

from ... import common
from .base import ActorBase


ALLOWED_VALUE_TYPES = (bool, float, int, str, type(None))
ALLOWED_VALUE_TYPES_T = T.Union[  # pylint: disable=invalid-name
    bool, float, int, str, None
]
WILDCARD_ATTRIBUTE_VALUE = "*"


class Generic2Actor(ActorBase):
    """A configurable, generic actor for Schedy that can control multiple
    attributes at once."""

    name = "generic2"
    config_schema_dict = {
        **ActorBase.config_schema_dict,
        vol.Optional("attributes", default=None): vol.All(
            vol.DefaultTo(list),
            [
                vol.All(
                    vol.DefaultTo(dict),
                    {vol.Optional("attribute", default=None): vol.Any(str, None)},
                )
            ],
        ),
        vol.Optional("values", default=None): vol.All(
            vol.DefaultTo(list),
            [
                vol.All(
                    vol.DefaultTo(dict),
                    {
                        vol.Required("value"): vol.All(
                            [vol.Any(*ALLOWED_VALUE_TYPES)], vol.Coerce(tuple),
                        ),
                        vol.Optional("calls", default=None): vol.All(
                            vol.DefaultTo(list),
                            [
                                vol.All(
                                    vol.DefaultTo(dict),
                                    {
                                        vol.Required("service"): vol.All(
                                            str, lambda v: v.replace(".", "/", 1)
                                        ),
                                        vol.Optional("data", default=None): vol.All(
                                            vol.DefaultTo(dict), dict
                                        ),
                                        vol.Optional(
                                            "include_entity_id", default=True
                                        ): bool,
                                    },
                                )
                            ],
                        ),
                    },
                )
            ],
            # Sort by number of attributes (descending) for longest prefix matching
            lambda v: sorted(v, key=lambda k: -len(k["value"])),
        ),
        vol.Optional("ignore_case", default=False): bool,
    }

    def _find_value_cfg(self, value: T.Tuple) -> T.Any:
        """Returns the config matching given value or ValueError if none found."""
        for value_cfg in self.cfg["values"]:
            _value = value_cfg["value"]
            if len(_value) != len(value):
                continue
            for idx, attr_value in enumerate(_value):
                if attr_value not in (WILDCARD_ATTRIBUTE_VALUE, value[idx]):
                    break
            else:
                return value_cfg
        raise ValueError("No configuration for value {!r}".format(value))

    def _populate_service_data(self, data: T.Dict, fmt: T.Dict[str, T.Any]) -> None:
        """Fills in placeholders in the service data definition."""
        # pylint: disable=too-many-nested-blocks
        memo = [data]  # type: T.List[T.Union[T.Dict, T.List]]
        while memo:
            obj = memo.pop()
            if isinstance(obj, dict):
                _iter = obj.items()  # type: T.Iterable[T.Tuple[T.Any, T.Any]]
            elif isinstance(obj, list):
                _iter = enumerate(obj)
            else:
                continue
            for key, value in _iter:
                if isinstance(value, str):
                    try:
                        formatted = value.format(fmt)
                        # Convert special values to appropriate type
                        if formatted == "None":
                            obj[key] = None
                        elif formatted == "True":
                            obj[key] = True
                        elif formatted == "False":
                            obj[key] = False
                        else:
                            try:
                                _float = float(formatted)
                                _int = int(formatted)
                            except ValueError:
                                # It's a string value
                                obj[key] = formatted
                            else:
                                # It's an int or float
                                obj[key] = _int if _float == _int else _float
                    except (IndexError, KeyError, ValueError) as err:
                        self.log(
                            "Couldn't format service data {!r} with values "
                            "{!r}: {!r}, omitting data.".format(value, fmt, err),
                            level="ERROR",
                        )
                elif isinstance(value, (dict, list)):
                    memo.append(value)

    def do_send(self) -> None:
        """Executes the configured services for self._wanted_value."""
        value = self._wanted_value
        # Build formatting data with values of all attributes
        fmt = {"entity_id": self.entity_id}
        for idx in range(len(self.cfg["attributes"])):
            fmt["attr{}".format(idx + 1)] = value[idx] if idx < len(value) else None

        for call_cfg in self._find_value_cfg(value)["calls"]:
            service = call_cfg["service"]
            data = copy.deepcopy(call_cfg["data"])
            self._populate_service_data(data, fmt)
            if call_cfg["include_entity_id"]:
                data.setdefault("entity_id", self.entity_id)
            self.log(
                "Calling service {}, data = {}.".format(repr(service), repr(data)),
                level="DEBUG",
                prefix=common.LOG_PREFIX_OUTGOING,
            )
            self.app.call_service(service, **data)

    def filter_set_value(self, value: T.Tuple) -> T.Any:
        """Checks whether the actor supports this value."""
        if self.cfg["ignore_case"]:
            value = tuple(v.lower() if isinstance(v, str) else v for v in value)
        try:
            self._find_value_cfg(value)
        except ValueError:
            self.log(
                "Value {!r} is not known by this actor.".format(value), level="ERROR"
            )
            return None
        return value

    def notify_state_changed(self, attrs: dict) -> T.Any:
        """Is called when the entity's state changes."""
        items = []
        for attr_cfg in self.cfg["attributes"]:
            attr = attr_cfg["attribute"]
            if attr is None:
                self.log("Ignoring state change (write-only attribute).", level="DEBUG")
                return None
            state = attrs.get(attr)
            self.log(
                "Attribute {!r} is {!r}.".format(attr, state),
                level="DEBUG",
                prefix=common.LOG_PREFIX_INCOMING,
            )
            if self.cfg["ignore_case"] and isinstance(state, str):
                state = state.lower()
            items.append(state)

        tpl = tuple(items)
        # Goes from len(tpl) down to 0
        for size in range(len(tpl), -1, -1):
            value = tpl[:size]
            try:
                self._find_value_cfg(value)
            except ValueError:
                continue
            return value

        self.log(
            "Received state {!r} which is not configured as a value.".format(items),
            level="WARNING",
        )
        return None

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
                    "Value {!r} for {}. attribute must be of one of these types: "
                    "{}".format(item, index + 1, ALLOWED_VALUE_TYPES)
                )
        return items
