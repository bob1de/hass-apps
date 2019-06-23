"""
This module implements various classes for collecting statistics.
"""

import typing as T

if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from .app import SchedyApp
    from .room import Room
    from .actor.base import ActorBase

import voluptuous as vol

from .. import common
from . import util


StatisticalValueType = T.Union[float, int, str]


class StatisticalParameter:
    """A parameter to be collected."""

    name = "dummy"
    config_defaults = {}  # type: T.Dict[T.Any, T.Any]
    config_schema_dict = {}  # type: T.Dict[T.Any, T.Any]

    # number of decimal places to round numeric values to,
    # None disables rounding
    round_places = None  # type: T.Optional[int]

    def __init__(self, name: str, cfg: T.Dict, app: "SchedyApp") -> None:
        self.name = name
        self.cfg = cfg
        self.app = app

        self.rooms = []  # type: T.List[Room]

        self._last_state = None  # type: T.Optional[T.Dict[str, StatisticalValueType]]
        self._update_timer = None  # type: T.Optional[uuid.UUID]

    def __repr__(self) -> str:
        return "<StatisticalParameter {}>".format(self.name)

    def __str__(self) -> str:
        return "SP:{}".format(self.name)

    def generate_entries(  # pylint: disable=no-self-use
        self
    ) -> T.Dict[str, StatisticalValueType]:
        """Should generate the entries to be added to the parameter."""

        return {}

    def _do_update(self) -> None:
        """Collects the statistics and writes them to Home Assistant."""

        self._update_timer = None

        attrs = self.generate_entries()

        if self.round_places is not None:
            for attr, value in attrs.items():
                if isinstance(value, (float, int)):
                    attrs[attr] = util.round_number(value, self.round_places)

        unchanged = attrs == self._last_state
        if unchanged:
            self.log("Unchanged HA state: attributes={}".format(attrs), level="DEBUG")
            return
        self.log(
            "Sending state to HA: attributes={}".format(attrs),
            level="DEBUG",
            prefix=common.LOG_PREFIX_OUTGOING,
        )

        entity_id = self._state_entity_id
        self.app.set_state(entity_id, state="", attributes=attrs)
        self._last_state = attrs

    @property
    def _state_entity_id(self) -> str:
        """Generates the entity id for storing this parameter's state as."""

        return "schedy_stats.{}_{}".format(self.app.name, self.name)

    def initialize(self) -> None:
        """Initializes state listeners and triggers an initial update."""

        self.log(
            "Initializing statistical parameter (name={}).".format(repr(self.name)),
            level="DEBUG",
        )

        self.initialize_listeners()

        self.update()

    def initialize_listeners(self) -> None:  # pylint: disable=no-self-use
        """Is called during initialization and should set up
        implementation-specific state listeners."""

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the parameter to log messages."""

        msg = "[{}] {}".format(self, msg)
        self.app.log(msg, *args, **kwargs)

    def update(self) -> None:
        """Registers a timer for sending statistics to HA in 3 seconds."""

        if self._update_timer:
            self.log("Statistics update  pending already.", level="DEBUG")
            return

        self.log("Going to update statistics in 3 seconds.", level="DEBUG")
        self._update_timer = self.app.run_in(lambda *a, **kw: self._do_update(), 3)

    def update_handler(
        self, *args: T.Any, **kwargs: T.Any  # pylint: disable=unused-argument
    ) -> None:
        """A convenience wrapper around self.update(), accepting any
        positional and wildcard argument. It is intended to be used
        with events that pass arguments to their handler we're not
        interested in."""

        self.update()


class RoomBasedParameter(StatisticalParameter):
    """A parameter having rooms associated."""

    config_schema_dict = {
        **StatisticalParameter.config_schema_dict,
        vol.Optional("rooms", default=dict): vol.All(
            lambda v: v or {},
            {
                util.CONF_STR_KEY: vol.Schema(
                    vol.All(
                        lambda v: v or {},
                        {
                            # no settings yet
                        },
                    )
                )
            },
        ),
    }

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)
        self.rooms = []  # type: T.List[Room]

    def initialize_listeners(self) -> None:
        """Adds all configured rooms to self.rooms."""

        for room_name in self.cfg["rooms"]:
            for room in self.app.rooms:
                if room.name == room_name:
                    self.rooms.append(room)
                    break
            else:
                raise ValueError(
                    "Room {} for statistical parameter {} not found.".format(
                        repr(room_name), repr(self.name)
                    )
                )
        if not self.cfg["rooms"]:
            # add all rooms if none are specified
            self.rooms.extend(self.app.rooms)


class AbstractValueCollectorMixin:
    """Abstract class for creating custom value collectors."""

    def collect_values(  # pylint: disable=no-self-use
        self
    ) -> T.Iterable[T.Tuple[T.Any, T.Union[float, int]]]:
        """Should collect the implementation-specific values from which
        entries are built. The first item of each tuple is an identifier
        for the value (e.g. an entity id of the entity it originated
        from), the second is the value."""

        return []


class ActorValueCollectorMixin(AbstractValueCollectorMixin, RoomBasedParameter):
    """Helps collecting a value per actor."""

    def collect_values(self) -> T.Iterable[T.Tuple[T.Any, T.Union[float, int]]]:
        """Calls self.collect_actor_value() for all actors of the
        associated rooms and returns the collected values."""

        values = []
        for room in self.rooms:
            for actor in filter(lambda a: a.is_initialized, room.actors):
                value = self.collect_actor_value(  # pylint: disable=assignment-from-none
                    actor
                )
                self.log(
                    "Value for {} in {} is {}.".format(actor, room, value),
                    level="DEBUG",
                )
                if value is not None:
                    values.append((actor.entity_id, value))
        return values

    def collect_actor_value(  # pylint: disable=no-self-use,unused-argument
        self, actor: "ActorBase"
    ) -> T.Union[float, int, None]:
        """Should generate a value for the given actor or None, if the
        actor should be excluded."""

        return None

    def initialize_actor_listeners(
        self, actor: "ActorBase"
    ) -> None:  # pylint: disable=no-self-use,unused-argument
        """Should initialize the appropriate state listeners for the
        given actor."""

    def initialize_listeners(self) -> None:
        """Calls self.initialize_actor_listeners() for each actor of the
        associated rooms."""

        super().initialize_listeners()

        for room in self.rooms:
            for actor in filter(lambda a: a.is_initialized, room.actors):
                self.initialize_actor_listeners(actor)


class MinAvgMaxParameter(AbstractValueCollectorMixin, StatisticalParameter):
    """A generic parameter implementation that automatically calculates
    min/avg/max entries based on all values collected. Weighting of
    individual values is supported as well.
    It needs an implementation of AbstractValueCollectorMixin mixed in
    to have a source for values."""

    config_schema_dict = {
        **StatisticalParameter.config_schema_dict,
        vol.Optional("factors", default=dict): vol.All(
            lambda v: v or {},
            {
                util.CONF_STR_KEY: vol.All(
                    vol.Any(float, int), vol.Range(min=0, min_included=False)
                )
            },
        ),
        vol.Optional("weights", default=dict): vol.All(
            lambda v: v or {},
            {util.CONF_STR_KEY: vol.All(vol.Any(float, int), vol.Range(min=0))},
        ),
    }

    def generate_entries(self) -> T.Dict[str, StatisticalValueType]:
        """Generates min/avg/max parameter entries."""

        plain_values = self.collect_values()
        values = []
        weighted_sum = 0.0
        weights_sum = 0.0
        for _id, value in plain_values:
            weight = self.cfg["weights"].get(_id, 1)
            if weight == 0:
                continue

            value *= self.cfg["factors"].get(_id, 1)
            values.append(value)
            weighted_sum += weight * value
            weights_sum += weight

        _min = min([v for v in values]) if values else 0.0
        _avg = weighted_sum / weights_sum if values else 0.0
        _max = max([v for v in values]) if values else 0.0
        return {"min": _min, "avg": _avg, "max": _max}
