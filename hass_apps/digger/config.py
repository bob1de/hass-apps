"""
This module contains the CONFIG_SCHEMA for validation with voluptuous.
"""

import datetime

import voluptuous as vol


def ensure_divisibility(value: int, divisor: int) -> int:
    """Raises vol.Invalid when value isn't divisible by divisor, returns
    value otherwise."""

    if value % divisor == 0:
        return value
    raise vol.Invalid("{} isn't divisible by {}".format(value, divisor))


CONFIG_SCHEMA = vol.Schema({
    vol.Optional("fetch_step", default=1440): vol.All(
        int, vol.Range(min=0), lambda v: datetime.timedelta(minutes=v),
    ),
    vol.Optional("fetch_tries", default=3): vol.All(int, vol.Range(min=1)),
    vol.Optional("listen_proactively", default=True): bool,
    vol.Optional("keep_number", default=10): vol.All(int, vol.Range(min=0)),
    vol.Optional("prune_old", default=60): vol.All(
        int, vol.Range(min=0), lambda v: ensure_divisibility(v, 5),
        lambda v: datetime.timedelta(minutes=v),
    ),
    vol.Optional("prune_unused", default=60): vol.All(
        int, vol.Range(min=0), lambda v: ensure_divisibility(v, 5),
        lambda v: datetime.timedelta(minutes=v),
    ),
}, extra=vol.ALLOW_EXTRA)
