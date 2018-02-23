"""
A simple app for connecting motion sensors to arbitrary entities
in Home Assistant, so that motion causes these entities to be turned
on or off.
"""

import typing as T

import voluptuous as vol

from .. import common
from . import __version__


CONSTRAINTS_SCHEMA = vol.Schema({
    vol.Extra: str,
})

CONTROL_SCHEMA = vol.Schema({
    vol.Optional("invert", default=False): bool,
})
CONTROLS_SCHEMA = vol.Schema({
    vol.Extra: lambda v: CONTROL_SCHEMA(v or {}),
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional("global_constraints", default=True): bool,
    vol.Optional("constraints", default=dict): lambda v: CONSTRAINTS_SCHEMA(v or {}),
    vol.Optional("on_state", default="on"): str,
    vol.Optional("on_delay", default=0): int,
    vol.Optional("off_delay", default=0): int,
    vol.Optional("controls", default=dict): lambda v: CONTROLS_SCHEMA(v or {}),
})
SENSORS_SCHEMA = vol.Schema({
    vol.Extra: lambda v: SENSOR_SCHEMA(v or {}),
})

CONFIG_SCHEMA = vol.Schema({
    vol.Optional("debug", default=False): bool,
    vol.Optional("constraints", default=dict): lambda v: CONSTRAINTS_SCHEMA(v or {}),
    vol.Optional("sensors", default=dict): lambda v: SENSORS_SCHEMA(v or {}),
}, extra=True)


class MotionLightApp(common.App):
    """
    A simple app for connecting motion sensors to arbitrary entities
    in Home Assistant, so that motion causes these entities to be turned
    on or off.
    """

    class Meta(common.App.Meta):
        # pylint: disable=missing-docstring
        name = "motion_light"
        version = __version__
        config_schema = CONFIG_SCHEMA

    def initialize_inner(self) -> None:
        """Parses the configuration and sets up state listeners."""

        # pylint: disable=attribute-defined-outside-init

        for sensor, sensor_data in self.cfg["sensors"].items():
            sensor_data["turned_on"] = False
            if sensor_data["global_constraints"]:
                for key, value in self.cfg["constraints"].items():
                    sensor_data["constraints"].setdefault(key, value)

        for sensor, sensor_data in self.cfg["sensors"].items():
            self.listen_state(self._sensor_state_cb, sensor,
                              new=sensor_data["on_state"],
                              duration=sensor_data["on_delay"],
                              **sensor_data["constraints"])
            self.listen_state(self._sensor_state_cb, sensor,
                              old=sensor_data["on_state"],
                              duration=sensor_data["off_delay"])

    def _sensor_state_cb(
            self, sensor: str, attr: str, old: T.Any, new: T.Any, kwargs: dict
    ) -> None:
        """Is called whenever a motion sensor changes between on and off."""

        sensor_data = self.cfg["sensors"][sensor]
        is_on = new == sensor_data["on_state"]

        self.log("[{}] Motion {}ed"
                 .format(sensor, "start" if is_on else "end"),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)

        if not is_on and not sensor_data["turned_on"]:
            # motion ended, but nothing has been turned on before
            # (e.g. due to constraints), hence nothing should be
            # turned off either
            self.log("[{}] Ignoring motion end because not turned on before."
                     .format(sensor),
                     level="DEBUG")
            return

        sensor_data["turned_on"] = is_on

        for entity, entity_data in sensor_data["controls"].items():
            turn_on = is_on ^ entity_data["invert"]
            self.log("Turning {} {}"
                     .format(entity, "on" if turn_on else "off"),
                     level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
            domain = self.split_entity(entity)[0]
            service = "{}/turn_{}".format(domain, "on" if turn_on else "off")
            self.call_service(service, entity_id=entity)
