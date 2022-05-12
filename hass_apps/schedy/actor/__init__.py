"""
This package contains the various actor implementations.
"""

import typing as T

from .base import ActorBase
from .custom import CustomActor
from .generic import GenericActor
from .generic2 import Generic2Actor
from .switch import SwitchActor
from .thermostat import ThermostatActor
from .dualthermostat import DualThermostatActor


__all__ = [
    "ActorBase",
    "CustomActor",
    "GenericActor",
    "Generic2Actor",
    "SwitchActor",
    "ThermostatActor",
    "DualThermostatActor",
]


def get_actor_types() -> T.Iterable[T.Type[ActorBase]]:
    """Yields available actor classes."""

    globs = globals()
    for actor_class_name in __all__:
        actor_type = globs.get(actor_class_name)
        if (
            actor_type is not ActorBase
            and isinstance(actor_type, type)
            and issubclass(actor_type, ActorBase)
        ):
            yield actor_type
