"""
This module implements the ActorBase parent class.
"""

import typing as T

if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from ..expression.helpers import HelperBase as ExpressionHelperBase
    from ..room import Room
    from ..stats import StatisticalParameter

import copy
import json
import observable
import voluptuous as vol

from ... import common
from ..room import sync_proxy


class ActorBase:
    """An actor to be controlled by Schedy."""

    name = "actor"
    config_defaults = {}  # type: T.Dict[T.Any, T.Any]
    config_schema_dict = {
        "friendly_name": str,
        vol.Optional("send_retries", default=10): vol.All(int, vol.Range(min=-1)),
        vol.Optional("send_retry_interval", default=30): vol.All(int, vol.Range(min=1)),
    }

    expression_helpers = []  # type: T.List[T.Type[ExpressionHelperBase]]

    stats_param_types = []  # type: T.List[T.Type[StatisticalParameter]]

    def __init__(self, entity_id: str, cfg: dict, room: "Room") -> None:
        self.entity_id = entity_id
        self.cfg = cfg
        self.room = room
        self.app = room.app
        self.events = observable.Observable()  # type: observable.Observable
        self.is_initialized = False

        self._current_value = None  # type: T.Any
        self._wanted_value = None  # type: T.Any

        self._gave_up_sending = False
        self._resending_timer = None  # type: T.Optional[uuid.UUID]

    def __repr__(self) -> str:
        return "<Actor {}>".format(str(self))

    def __str__(self) -> str:
        return "A:{}".format(self.cfg.get("friendly_name", self.entity_id))

    @staticmethod
    def _preprocess_state(state: T.Optional[dict]) -> dict:
        """Copies and flattens a state dict."""

        attrs = copy.deepcopy(state or {})
        attrs.update((attrs or {}).get("attributes", {}))
        return attrs

    @sync_proxy
    def _resending_cb(self, kwargs: dict) -> None:
        """This callback triggers the actual sending of a value to the
        actor. Expected members of kwargs are:
        - left_tries (after this round)"""

        self._resending_timer = None

        tries = self.cfg["send_retries"]
        left_tries = kwargs["left_tries"]
        if left_tries < tries:
            self.log(
                "Re-sending value due to unexpected or missing feedback.",
                level="WARNING",
            )

        self.log(
            "Setting value {} (left tries = {}).".format(
                self._wanted_value, left_tries
            ),
            level="DEBUG",
            prefix=common.LOG_PREFIX_OUTGOING,
        )
        self.do_send()

        if not left_tries:
            self.log(
                "Gave up sending value after {} tries.".format(tries), level="WARNING"
            )
            self._gave_up_sending = True
            return

        interval = self.cfg["send_retry_interval"]
        self.log("Re-sending in {} seconds.".format(interval), level="DEBUG")
        self._gave_up_sending = False
        self._resending_timer = self.app.run_in(
            self._resending_cb, interval, left_tries=left_tries - 1
        )

    @sync_proxy
    def _state_cb(
        self,
        entity: str,
        attr: str,
        old: T.Optional[dict],
        new: T.Optional[dict],
        kwargs: dict,
    ) -> None:
        """Is called when any of the actor's state attributes changes."""

        attrs = self._preprocess_state(new)

        previous_value = self._current_value
        new_value = self.notify_state_changed(  # pylint: disable=assignment-from-none
            attrs
        )
        if new_value is None:
            return

        if new_value == self._wanted_value:
            self.cancel_resending_timer()
            self._gave_up_sending = False

        if new_value != previous_value:
            self._current_value = new_value
            self.log(
                "Received value of {}.".format(repr(new_value)),
                prefix=common.LOG_PREFIX_INCOMING,
            )
            self.events.trigger("value_changed", self, new_value)

    def after_initialization(self) -> None:
        """Can be implemented to perform actions after actor initialization."""

    def cancel_resending_timer(self) -> None:
        """Cancels the re-sending timer for this actor, if one exists."""

        timer = self._resending_timer
        if timer is None:
            return
        self._resending_timer = None
        self.app.cancel_timer(timer)
        self.log("Cancelled re-sending timer.", level="DEBUG")

    def check_config_plausibility(self, state: dict) -> None:
        """Is called during initialization to warn the user about some
        possible common configuration mistakes. The entity's current
        state attributes dictionary is provided."""

    @property
    def current_value(self) -> T.Any:
        """Returns the value currently set at this actor."""

        return self._current_value

    @staticmethod
    def deserialize_value(value: str) -> T.Any:
        """Should deserialize a value generated by serialize_value().
        A ValueError should be raised in case of malformed data.
        This implementation uses JSON."""

        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError) as err:
            raise ValueError("invalid JSON data: {}".format(repr(err)))

    def do_send(self) -> None:
        """This method should implement the actual sending of
        self._wanted_value to the actor."""

    def filter_set_value(self, value: T.Any) -> T.Any:  # pylint: disable=no-self-use
        """Should be implemented to decide whether to set the given
        value on this actor or to alter it before setting.
        The return value is either the actual value to set or None,
        if nothing should be sent."""

        return value

    @property
    def gave_up_sending(self) -> bool:
        """Tells whether actor gave up sending and is still waiting for a receipt."""

        return self._gave_up_sending

    @property
    def is_sending(self) -> bool:
        """Tells whether the actor is currently waiting for a receipt."""

        return self._resending_timer is not None

    @property
    def is_synced(self) -> bool:
        """Tells whether the actor's current value is the wanted one and
        re-sending neither is in progress nor has failed."""

        return (
            not self._resending_timer
            and not self._gave_up_sending
            and self._current_value is not None
            and self._wanted_value is not None
            and self._current_value == self._wanted_value
        )

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the actor to log messages."""

        msg = "[{}] {}".format(self, msg)
        self.room.log(msg, *args, **kwargs)

    def notify_state_changed(  # pylint: disable=no-self-use,unused-argument
        self, attrs: dict
    ) -> T.Any:
        """Is called when the entity's state has changed with the new
        attributes dict as argument. It should return the new value or
        None, if undetectable."""

        return None

    def initialize(self) -> bool:
        """Should be called in order to register state listeners and
        timers.
        Returns whether initialization was successful."""

        self.log(
            "Initializing actor (entity_id={}, type={}).".format(
                repr(self.entity_id), repr(self.name)
            ),
            level="DEBUG",
        )

        self.log("Fetching initial state.", level="DEBUG")
        state = self.app.get_state(self.entity_id, attribute="all")
        if state is None:
            self.log(
                "State of entity {} is None, not initializing it now.".format(
                    repr(self.entity_id)
                ),
                level="WARNING",
            )
            return False
        self.check_config_plausibility(self._preprocess_state(state))
        # populate self._current_value etc. by simulating a
        # state change
        self._state_cb(self.entity_id, "all", state, state, {})

        self.log("Listening for state changes.", level="DEBUG")
        self.app.listen_state(self._state_cb, self.entity_id, attribute="all")

        self.after_initialization()

        self.is_initialized = True
        return True

    @staticmethod
    def serialize_value(value: T.Any) -> str:
        """Should serialize accepted values for this actor to str.
        A ValueError should be raised in case of not serializable data.
        This implementation uses JSON."""

        try:
            return json.dumps(value)
        except TypeError as err:
            raise ValueError("can't serialize to JSON: {}".format(err))

    def set_value(
        self, value: T.Any, force_resend: bool = False
    ) -> T.Tuple[bool, T.Any]:
        """Is called in order to change the actor's value. It isn't
        re-sent unless force_resend is True.
        It returns whether a value has been sent or not and the actual
        value now wanted by this actor."""

        value = self.filter_set_value(value)
        if value is None:
            return False, self._wanted_value

        self._wanted_value = value
        if not force_resend and self.is_synced:
            self.log(
                "Not sending value {} redundantly.".format(repr(value)), level="DEBUG"
            )
            return False, value

        self.cancel_resending_timer()
        self._resending_cb({"left_tries": self.cfg["send_retries"]})

        return True, value

    @staticmethod
    def validate_value(value: T.Any) -> T.Any:
        """Should validate the given value, which usually is the result
        of a custom expression, to ensure it's appropriate for this kind
        of actor. It may alter the value before returning it again.
        A ValueError should be raised when validation fails."""

        return value

    @property
    def wanted_value(self) -> T.Any:
        """Returns the value currently wanted for this actor."""

        return self._wanted_value

    @wanted_value.setter
    def wanted_value(self, value: T.Any) -> None:
        """Validates and manually sets the value wanted by this actor."""

        if value is not None:
            value = self.validate_value(value)
        self._wanted_value = value
