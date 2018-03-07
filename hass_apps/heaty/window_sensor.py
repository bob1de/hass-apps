"""
This module implements the WindowSensor class.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    from . import room as _room

from .. import common
from . import util


class WindowSensor:
    """A sensor for Heaty's open window detection."""

    def __init__(self, entity_id: str, cfg: dict, room: "_room.Room") -> None:
        self.entity_id = entity_id
        self.cfg = cfg
        self.room = room
        self.app = room.app

    def __repr__(self) -> str:
        return "<WindowSensor {}, {}>".format(
            str(self), "open" if self.is_open() else "closed"
        )

    def __str__(self) -> str:
        return self.cfg.get("friendly_name", self.entity_id)

    @util.modifies_state
    def _state_cb(
            self, entity: str, attr: str,
            old: T.Optional[dict], new: T.Optional[dict],
            kwargs: dict
    ) -> None:
        """Is called when the window sensor's state has changed.
        This method handles the window open/closed detection and
        performs actions accordingly."""

        action = "opened" if self.is_open() else "closed"
        self.log("State is now {}.".format(new),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
        self.room.log("Window has been {}.".format(action),
                      prefix=common.LOG_PREFIX_INCOMING)

        if not self.app.master_switch_enabled():
            self.log("Master switch is off, ignoring window event.")
            return

        if action == "opened":
            # turn heating off, but store the original temperature
            self.room.check_for_open_window()
        elif not self.room.get_open_windows():
            # all windows closed
            # restore temperature from before opening the window
            orig_temp = self.room.wanted_temp
            # could be None if we didn't know the temperature before
            # opening the window
            if orig_temp is None:
                self.log("Restoring temperature from schedule.",
                         level="DEBUG")
                self.room.set_scheduled_temp()
            else:
                self.log("Restoring temperature to {}.".format(orig_temp),
                         level="DEBUG")
                self.room.set_temp(orig_temp, scheduled=False)

    def initialize(self) -> None:
        """Should be called in order to register state listeners and
        timers."""

        self.log("Registering window sensor state listener, delay = {}."
                 .format(self.cfg["delay"]),
                 level="DEBUG")
        self.app.listen_state(self._state_cb, self.entity_id,
                              duration=self.cfg["delay"])

    def is_open(self) -> bool:
        """Returns whether the sensor reports open or not."""

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
