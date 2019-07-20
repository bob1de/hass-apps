"""
An app helping to inspect historical entity state with ease.
"""

import typing as T

import collections
import copy
import datetime
import itertools
import threading
import urllib.parse

import requests

from .. import common
from . import __version__, config


__all__ = ["DiggerApp"]


StateType = T.Dict[str, T.Any]


class DiggerApp(common.App):
    """The Digger app class for AppDaemon."""

    class Meta(common.App.Meta):
        # pylint: disable=missing-docstring
        name = "digger"
        version = __version__
        config_schema = config.CONFIG_SCHEMA

    def __init__(self, *args: T.Any, **kwargs: T.Any) -> None:
        super().__init__(*args, **kwargs)

        self._states: T.List[StateType] = []
        self._lock = threading.RLock()
        self._not_digging = threading.Condition(self._lock)
        self._digging = 0
        self._pruned = True

    def _fetch_states(
            self, step: datetime.timedelta, tries: int,
            start: datetime.datetime = None, entity_id: str = None
    ) -> int:
        _end: T.Optional[datetime.datetime]
        if start:
            _start = start.astimezone()
            _end = _start + step
        else:
            _start = self.datetime().astimezone() - abs(step)
            _end = None

        self.log("Fetching states: step={}, tries={}, start={}, entity_id={}"
                 .format(step, tries, _start, repr(entity_id)),
                 level="DEBUG")

        namespace = self._get_namespace()
        cfg = self.AD.get_plugin(namespace).config
        if "cert_path" in cfg:
            cert_path = cfg["cert_path"]
        else:
            cert_path = False

        if "token" in cfg:
            headers = {'Authorization': "Bearer {}".format(cfg["token"])}
        elif "ha_key"  in cfg:
            headers = {'x-ha-access': cfg["ha_key"]}
        else:
            headers = {}

        min_start = _start
        max_end = None
        while tries:
            if _end:
                _start, _end = sorted((_start, _end))
                max_end = max(_end, max_end) if max_end else _end
            min_start = min(_start, min_start)

            self.log("  Polling from {} to {}."
                     .format(_start, _end or "open end"),
                     level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)

            apiurl = "{}/api/history/period/{}".format(
                cfg["ha_url"], _start.isoformat()
            )
            params = {}  # type: T.Dict[str, str]
            if entity_id:
                params["filter_entity_id"] = entity_id
            if _end:
                params["end_time"] = _end.isoformat()
            if params:
                apiurl += "?" + urllib.parse.urlencode(params)

            req = requests.get(apiurl, headers=headers, verify=cert_path)
            req.raise_for_status()
            states = req.json()
            if states:
                count = sum(len(_states) for _states in states)
                self.log("  {} states of {} entities fetched."
                         .format(count, len(states)),
                         level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
                self._insert_states(
                    itertools.chain(*states),
                    wildcard=not entity_id, start=min_start, end=max_end
                )
                return count

            if _end:
                _end += step
            else:
                _end = _start
            _start += step
            tries -= 1

        return 0

    def _insert_states(
            self, states: T.Iterable[StateType], wildcard: bool = False,
            start: datetime.datetime = None, end: datetime.datetime = None
    ) -> None:
        """Inserts the given states indexed and ordered by last_updated."""

        with self._lock:
            self._pruned = False

            store = self._states
            index = int(len(store) / 2)
            for state in states:
                state = copy.deepcopy(state)
                entity_id = state["entity_id"]
                when = self.convert_utc(state["last_updated"]).astimezone()
                start = min((start, when)) if start else when
                end = max((end, when)) if end else when
                state["_when"] = when
                state["_used"] = None
                state["-"] = None
                state["+"] = None
                state["--"] = None
                state["++"] = None
                max_index = len(store)
                while index > 0 and when < store[index]["_when"]:
                    index -= 1
                while index < max_index and when > store[index]["_when"]:
                    index += 1
                if index >= max_index or when != store[index]["_when"]:
                    store.insert(index, state)

            if not start or not end:
                # no states added
                return

            previous_state = None
            previous_entity_states: T.Dict[str, StateType] = {}
            for state in store:
                if state["_when"] < start:
                    # before start-end range, don't manipulate
                    continue
                if state["_when"] > end:
                    # states we know about are over
                    break

                entity_id = state["entity_id"]
                if wildcard:
                    if previous_state:
                        state["-"] = previous_state
                        previous_state["+"] = state  # pylint: disable=unsupported-assignment-operation
                        # hints are no longer needed
                        state.pop("|-", None)
                        previous_state.pop("+|", None)
                    else:
                        # first state within start-end range
                        first_from = state.get("|-")
                        if not first_from or first_from > start:
                            state["|-"] = start
                            print("tagging first_from", start)
                    previous_state = state

                previous_entity_state = previous_entity_states.get(entity_id)
                if previous_entity_state:
                    state["--"] = previous_entity_state
                    previous_entity_state["++"] = state
                    # hints are no longer needed
                    state.pop("|--", None)
                    previous_entity_state.pop("++|", None)
                else:
                    # first state for this entity within start-end range
                    first_from = state.get("|--")
                    if not first_from or first_from > start:
                        state["|--"] = start
                previous_entity_states[entity_id] = state

        if wildcard and previous_state:
            until = previous_state.get("+|")
            if not until or until < end:
                previous_state["+|"] = end  # pylint: disable=unsupported-assignment-operation
                print("tagging until", end)

        for entity_id, previous_entity_state in previous_entity_states.items():
            until = previous_entity_state.get("++|")
            if not until or until < end:
                previous_entity_state["++|"] = end

    def _listen_state_cb(
            self, entity_id: str, attribute: str, old: T.Optional[StateType],
            new: T.Optional[StateType], kwargs: T.Dict[str, T.Any]
    ) -> None:
        if not new:
            return

        self.log("Storing new state for {}: {}".format(repr(entity_id), new),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
        states = [new]
        if old:
            states.append(old)
        self._insert_states(states)

    def _prune_cb(self, kwargs: T.Dict[str, T.Any]) -> None:
        """Prunes data from the states store as configured by the policy."""

        if not self._states:
            return

        if self._pruned and not self.cfg["prune_old"] and \
           not self.cfg["prune_unused"]:
            return

        tokens = []
        keep_number = self.cfg["keep_number"]
        if keep_number:
            tokens.append("at least {} per entity".format(keep_number))
        keep_from = None
        if self.cfg["prune_old"]:
            keep_from = self.datetime().astimezone() - self.cfg["prune_old"]
            tokens.append("those newer than {}".format(keep_from))
        keep_used_after = None
        if self.cfg["prune_unused"]:
            keep_used_after = self.datetime().astimezone() - \
                              self.cfg["prune_unused"]
            tokens.append("those used after {}".format(keep_used_after))
        self.log("Pruning states, keeping {}.".format(", ".join(tokens)),
                 level="DEBUG")

        with self._lock:
            if self._digging:
                if not self._not_digging.wait(10):
                    self.log("Not pruning because of >10 seconds of "
                             "continuous digging.",
                             level="WARNING")
                    return

            size = len(self._states)
            indexes: T.Dict[str, T.List[int]] = collections.defaultdict(list)
            pruned: T.Dict[str, int] = collections.defaultdict(lambda: 0)
            for index, state in enumerate(reversed(self._states)):
                entity_id = state["entity_id"]
                skip_checks = (
                    not keep_number or len(indexes[entity_id]) >= keep_number,
                    not keep_from or state["_when"] < keep_from,
                    not keep_used_after or not state["_used"] or
                    state["_used"] < keep_used_after,
                )
                if all(skip_checks):
                    pruned[entity_id] += 1
                    continue
                indexes[entity_id].insert(0, size - index - 1)

            if pruned:
                store = []  # type: T.List[StateType]
                for index, state in enumerate(self._states):
                    entity_id = state["entity_id"]
                    _indexes = indexes[entity_id]
                    try:
                        _index = _indexes.index(index)
                    except ValueError:
                        continue

                    if not store:
                        state["-"] = None
                    elif state["-"] and state["-"] != store[-1]:
                        state["-"]["+"] = None
                        state["-"] = None

                    if not _index or \
                       state["--"] != self._states[_indexes[_index - 1]]:
                        state["--"] = None
                    if _index + 1 == len(_indexes) or \
                       state["++"] != self._states[_indexes[_index + 1]]:
                        state["++"] = None

                    store.append(state)
                self._states = store

            total_pruned = 0
            for entity_id, count in pruned.items():
                self.log("  {} / {} states of {} pruned."
                         .format(count, count + len(indexes[entity_id]),
                                 repr(entity_id)),
                         level="DEBUG")
                total_pruned += count
            self.log("  {} states of {} entities pruned in total."
                     .format(total_pruned, len(pruned)),
                     level="DEBUG")
            self._pruned = True

    def dig(  # pylint: disable=too-many-branches
            self, entity_id: str = None, start: datetime.datetime = None,
            interest: datetime.timedelta = None, backwards: bool = True
    ) -> T.Generator[StateType, None, None]:
        """Dig into the state history."""

        def _find_starting_state() -> T.Optional[StateType]:
            if entity_id:
                nav_key = "++"
            else:
                nav_key = "+"

            for state in self._states:
                if entity_id and entity_id != state["entity_id"]:
                    # invalid entity id
                    continue
                if state["_when"] > _start:
                    # state too new, give up searching
                    break

                until = state.get(until_key)
                if until and until >= _start:
                    # _start in range from _when to until -> valid
                    return state
                next_state = state[nav_key]
                if next_state and next_state["_when"] > _start:
                    # _start in time range from this to next state -> valid
                    return state

            return None

        if interest:
            fetch_step = interest
            fetch_tries = 1
        else:
            fetch_step = self.cfg["fetch_step"]
            fetch_tries = self.cfg["fetch_tries"]
        if backwards:
            fetch_step *= -1
            nav_key = "-"
        else:
            nav_key = "+"
        if entity_id:
            nav_key *= 2
            first_from_key = "|--"
            until_key = "++|"
        else:
            first_from_key = "|-"
            until_key = "+|"

        with self._lock:
            self._digging += 1

        try:
            _state = None
            if start:
                start = start.astimezone()
                _start = start
                _state = _find_starting_state()
            if not _state:
                self._fetch_states(fetch_step, fetch_tries, start, entity_id)
                if start:
                    if not backwards and not interest:
                        # also fill backwards to find the state at start time
                        self._fetch_states(
                            -fetch_step, fetch_tries, _start, entity_id  # pylint: disable=invalid-unary-operand-type
                        )
                    _state = _find_starting_state()
                    if not _state:
                        return
                else:
                    for _state in reversed(self._states):
                        if not entity_id or _state["entity_id"] == entity_id:
                            break
                    else:
                        # either self._states empty or no state for this entity
                        return
            state = _state

            while True:
                state["_used"] = self.datetime().astimezone()

                if interest and abs(start - state["_when"]) > interest:
                    return

                _state = state.copy()
                del _state["-"], _state["+"], _state["--"], _state["++"]
                yield _state

                with self._lock:
                    if not state[nav_key]:
                        if backwards:
                            fetch_start = state.get(first_from_key) or \
                                          state["_when"]
                        else:
                            fetch_start = state.get(until_key) or state["_when"]
                        fetched = self._fetch_states(
                            fetch_step, fetch_tries, fetch_start, entity_id
                        )
                        if not fetched:
                            return
                state = state[nav_key]
        finally:
            with self._lock:
                self._digging -= 1
                if not self._digging:
                    self._not_digging.notify()

    def initialize_inner(self) -> None:
        """Initializes the state listener."""

        if self.cfg["listen_proactively"]:
            self.log("Listening for state changes proactively.",
                     level="DEBUG")
            self.listen_state(self._listen_state_cb, attribute="all")

        if self.cfg["keep_number"] or self.cfg["keep_minutes"]:
            self.log("Prune policy: older than '{}', unused for '{}', "
                     "keep at least {} per entity"
                     .format(self.cfg["prune_old"], self.cfg["prune_unused"],
                             self.cfg["keep_number"]),
                     level="DEBUG")
            interval = 5 * 60
            self.run_every(
                self._prune_cb,
                self.datetime() + datetime.timedelta(seconds=interval),
                interval
            )

        print(next(self.dig(start=self.datetime()-datetime.timedelta(weeks=1))))

        for i, state in enumerate(self.dig("input_boolean.global_abwesend", self.datetime()-datetime.timedelta(weeks=1))):
            print(i, state)
            if i >= 3:
                break
