"""
This module implements a binary on/off switch, derived from the generic actor.
"""

from .generic2 import Generic2Actor


class SwitchActor(Generic2Actor):
    """A binary on/off switch actor."""

    name = "switch"
    config_defaults = {
        **Generic2Actor.config_defaults,
        "attributes": [{"attribute": "state"}],
        "values": [
            {"value": ["on"], "calls": [{"service": "homeassistant.turn_on"}]},
            {"value": ["off"], "calls": [{"service": "homeassistant.turn_off"}],},
        ],
        "ignore_case": True,
    }
