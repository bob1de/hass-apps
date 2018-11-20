"""
This module implements a binary on/off switch, derived from the generic actor.
"""

from .generic import GenericActor


CONFIG_DEFAULTS = {
    "states": {
        "on": {
            "service": "homeassistant/turn_on",
        },
        "off": {
            "service": "homeassistant/turn_off",
        },
    },
}


class SwitchActor(GenericActor):
    """A binary on/off switch actor for Schedy."""

    name = "switch"
    config_defaults = CONFIG_DEFAULTS
