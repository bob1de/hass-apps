"""
This module implements a binary on/off switch, derived from the generic actor.
"""

from .generic import GenericActor


class SwitchActor(GenericActor):
    """A binary on/off switch actor for Schedy."""

    name = "switch"
    config_defaults = {
        **GenericActor.config_defaults,
        "attributes": [
            {
                "attribute": "state",
                "values": {
                    "on": {"service": "homeassistant/turn_on"},
                    "off": {"service": "homeassistant/turn_off"},
                },
            }
        ],
    }
