"""
This module implements a binary on/off switch, derived from the generic actor.
"""

import voluptuous as vol

from .generic import GenericActor


CONFIG_SCHEMA = vol.Schema(vol.All(
    lambda v: v.setdefault("states", {
        "on": {
            "service": "homeassistant/turn_on",
        },
        "off": {
            "service": "homeassistant/turn_off",
        },
    }) and False or v,
    GenericActor.config_schema,
))


class SwitchActor(GenericActor):
    """A binary on/off switch actor for Schedy."""

    name = "switch"
    config_schema = CONFIG_SCHEMA
