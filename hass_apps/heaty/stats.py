"""
This module implements the StatisticsZone class for collecting statistics.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    # pylint: disable=cyclic-import,unused-import
    from .app import HeatyApp
    from .room import Room

from .. import common
from . import util


class _WeightedValue:
    """A measured value having a weight for proper average calculation."""

    def __init__(self, value: float, weight: float) -> None:
        self.value = value
        self.weight = weight

    def __repr__(self) -> str:
        return "{}(weight={})" \
               .format(util.format_sensor_value(self.value), self.weight)


class StatisticsZone:
    """A zone (group of rooms) used for collecting statistical data."""

    def __init__(self, name: str, cfg: T.Dict, app: "HeatyApp") -> None:
        self.name = name
        self.cfg = cfg
        self.app = app
        self.rooms = []  # type: T.List[Room]
        self._stats_timer = None  # type: T.Optional[uuid.UUID]

    def __repr__(self) -> str:
        return "<StatisticsZone {}>".format(self.name)

    def __str__(self) -> str:
        return "SZ:{}".format(self.cfg.get("friendly_name", self.name))

    def _collect_temp_delta(self, cfg: dict) -> T.List[_WeightedValue]:
        off_value = cfg["off_value"]
        values = []
        for room in self.rooms:
            for therm in room.thermostats:
                weight = cfg["thermostat_weights"].get(therm.entity_id, 1)
                if weight == 0:
                    # ignore this thermostat
                    continue

                if therm.current_temp is None or \
                   therm.current_target_temp is None or \
                   therm.current_temp.is_off or \
                   therm.current_target_temp.is_off:
                    if off_value is None:
                        # thermostats that are off should be excluded
                        continue
                    temp_delta = float(off_value)
                else:
                    temp_delta = float(therm.current_target_temp -
                                       therm.current_temp)
                    factor = cfg["thermostat_factors"].get(therm.entity_id, 1)
                    temp_delta *= factor
                value = _WeightedValue(temp_delta, weight)
                self.log("Value for {} in {} is {}".format(therm, room, value),
                         level="DEBUG")
                values.append(value)
        return values

    def _do_update_stats(self) -> None:
        """Writes the zone statistics to Home Assistant."""

        self._stats_timer = None

        if not self.cfg["parameters"]:
            self.log("No parameters configured, nothing to update.",
                     level="DEBUG")
            return

        params = {}  # type: T.Dict[str, T.List[_WeightedValue]]
        for param in self.cfg["parameters"]:
            self.log("Collecting {}".format(param),
                     level="DEBUG")
            cfg = self.cfg["parameters"][param]
            params[param] = getattr(self, "_collect_{}".format(param))(cfg)

        fmt = util.format_sensor_value
        for param, values in params.items():
            _min = fmt(min([v.value for v in values]) if values else 0)
            _avg = fmt(sum([v.value * v.weight for v in values]) /
                       sum([v.weight for v in values]) if values else 0)
            _max = fmt(max([v.value for v in values]) if values else 0)
            self.log("{} (min/avg/max): {} / {} / {}"
                     .format(param, _min, _avg, _max),
                     level="DEBUG")
            self._set_sensor("min_{}".format(param), _min)
            self._set_sensor("avg_{}".format(param), _avg)
            self._set_sensor("max_{}".format(param), _max)

    def _set_sensor(self, param: str, state: T.Any) -> None:
        """Updates the sensor for given parameter in HA."""

        entity_id = "sensor.heaty_{}_zone_{}_{}" \
                    .format(self.app.cfg["heaty_id"], self.name, param)
        self.log("Setting state of {} to {}."
                 .format(repr(entity_id), repr(state)),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
        self.app.set_state(entity_id, state=state)

    def initialize(self) -> None:
        """Fetches the Room objects and sets up internal data structures
        before triggering an initial statistics update."""

        self.log("Initializing statistics zone (name={})."
                 .format(repr(self.name)),
                 level="DEBUG")

        if not self.cfg["parameters"]:
            self.log("No parameters configured.", level="WARNING")

        for room_name in self.cfg["rooms"]:
            room = self.app.get_room(room_name)
            if room is None:
                self.log("Room named '{}' not found, not adding it to "
                         "statistics zone."
                         .format(room_name),
                         level="ERROR")
                continue
            self.rooms.append(room)
            for therm in room.thermostats:
                self.log("Listening for temperature changes of {} in {}."
                         .format(therm, room),
                         level="DEBUG")
                therm.events.on("current_temp_changed",
                                lambda *a, **kw: self.update_stats())
                therm.events.on("target_temp_changed",
                                lambda *a, **kw: self.update_stats())

        if not self.rooms:
            self.log("No rooms configured.", level="WARNING")

        self.update_stats()

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the zone to log messages."""
        msg = "[{}] {}".format(self, msg)
        self.app.log(msg, *args, **kwargs)

    def update_stats(self) -> None:
        """Registers a timer for sending statistics to HA in 3 seconds."""

        if self._stats_timer:
            self.log("Statistics update  pending already.",
                     level="DEBUG")
            return

        self.log("Going to update statistics in 3 seconds.",
                 level="DEBUG")
        self._stats_timer = self.app.run_in(
            lambda *a: self._do_update_stats(), 3
        )
