"""
This module implements the WindowSensor class.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from .room import Room

import observable

from .. import common


class WindowSensor:
    """A sensor for Heaty's open window detection."""

    def __init__(self, entity_id: str, cfg: dict, room: "Room") -> None:
        super().__init__()
        self.entity_id = entity_id
        self.cfg = cfg
        self.room = room
        self.app = room.app
        self.events = observable.Observable()  # type: observable.Observable

    def __repr__(self) -> str:
        return "<WindowSensor {}, {}>".format(
            str(self), "open" if self.is_open else "closed"
        )

    def __str__(self) -> str:
        return "W:{}".format(self.cfg.get("friendly_name", self.entity_id))

    def _state_cb(
            self, entity: str, attr: str,
            old: T.Optional[dict], new: T.Optional[dict],
            kwargs: dict
    ) -> None:
        """Is called when the window sensor's state has changed.
        This method triggers the opened/closed event."""

        self.log("State is now {}.".format(new),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)

        self.events.trigger("open_close", self, self.is_open)

    def initialize(self) -> None:
        """Should be called in order to register state listeners and
        timers."""

        self.log("Initializing window sensor (entity_id={})."
                 .format(repr(self.entity_id)),
                 level="DEBUG")

        self.log("Listening for state changes (delay={})."
                 .format(self.cfg["delay"]),
                 level="DEBUG")
        self.app.listen_state(self._state_cb, self.entity_id,
                              duration=self.cfg["delay"])

    @property
    def is_open(self) -> bool:
        """Tells whether the sensor reports open or not."""

        open_state = self.cfg["open_state"]
        states = []
        if isinstance(open_state, list):
            states.extend(open_state)
        else:
            states.append(open_state)
        return self.app.get_state(self.entity_id) in states

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the window sensor to log messages."""
        msg = "[{}] {}".format(self, msg)
        self.room.log(msg, *args, **kwargs)
