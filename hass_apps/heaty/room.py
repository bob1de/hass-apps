"""
This module implements the Room class.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from .app import HeatyApp
    from .thermostat import Thermostat

import datetime

from .. import common
from . import expr, schedule, util
from .window_sensor import WindowSensor


class Room:
    """A room to be controlled by Heaty."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str, cfg: dict, app: "HeatyApp") -> None:
        self.name = name
        self.cfg = cfg
        self.app = app
        self.thermostats = []  # type: T.List[Thermostat]
        self.window_sensors = []  # type: T.List[WindowSensor]
        self.schedule = None  # type: T.Optional[schedule.Schedule]

        self.wanted_temp = None  # type: T.Optional[expr.Temp]
        self.scheduled_temp = None  # type: T.Optional[expr.Temp]
        self.reschedule_timer = None  # type: T.Optional[uuid.UUID]

    def __repr__(self) -> str:
        return "<Room {}>".format(str(self))

    def __str__(self) -> str:
        return "R:{}".format(self.cfg.get("friendly_name", self.name))

    def _get_sensor(self, param: str) -> T.Any:
        """Returns the state value of the sensor for given parameter in HA."""

        entity_id = "sensor.heaty_{}_room_{}_{}" \
                    .format(self.app.cfg["heaty_id"], self.name, param)
        self.log("Querying state of {}."
                 .format(repr(entity_id)),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
        state = self.app.get_state(entity_id)
        self.log("= {}".format(repr(state)),
                 level="DEBUG", prefix=common.LOG_PREFIX_INCOMING)
        return state

    def _reschedule_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a re-schedule timer fires."""

        self.log("Re-schedule timer fired.",
                 level="DEBUG")

        self.reschedule_timer = None

        # invalidate cached temp
        self.scheduled_temp = None

        self.apply_schedule()

    def _schedule_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a schedule timer fires."""

        self.log("Schedule timer fired.",
                 level="DEBUG")
        self.apply_schedule()

    def _set_sensor(self, param: str, state: T.Any) -> None:
        """Updates the sensor for given parameter in HA."""

        entity_id = "sensor.heaty_{}_room_{}_{}" \
                    .format(self.app.cfg["heaty_id"], self.name, param)
        self.log("Setting state of {} to {}."
                 .format(repr(entity_id), repr(state)),
                 level="DEBUG", prefix=common.LOG_PREFIX_OUTGOING)
        self.app.set_state(entity_id, state=state)

    def apply_schedule(
            self, send: bool = True, force_resend: bool = False
    ) -> None:
        """Sets the temperature that is configured for the current
        date and time. If the master switch is turned off, this won't
        do anything.
        This method won't re-schedule if a re-schedule timer runs.
        It will also detect when the result hasn't changed compared to
        the last run and prevent re-setting the temperature in that case.
        If send is False, only the records will be updated without
        actually setting the thermostats.
        If force_resend is True and the temperature didn't change,
        it is sent to the thermostats anyway.
        In case of an open window, temperature is cached and not sent."""

        if not self.app.require_master_is_on():
            return

        if self.reschedule_timer:
            # don't schedule now, wait for the timer instead
            self.log("Not scheduling now due to a running re-schedule "
                     "timer.",
                     level="DEBUG")
            return

        self.log("Applying room's schedule.",
                 level="DEBUG")

        result = self.get_scheduled_temp()
        if result is None:
            self.log("No suitable temperature found in schedule.",
                     level="DEBUG")
            return

        temp = result[0]
        if temp == self.scheduled_temp and not force_resend:
            self.log("Result didn't change, not setting it again.",
                     level="DEBUG")
            return

        self.scheduled_temp = temp
        self._set_sensor("scheduled_temp", temp.serialize())

        if not send:
            self.log("Not setting the temperature due to send = False.",
                     level="DEBUG")
            return

        if self.get_open_windows():
            self.log("Caching and not setting temperature due to an "
                     "open window.")
            self.wanted_temp = temp
        else:
            self.set_temp(temp, scheduled=True, force_resend=force_resend)

    def cancel_reschedule_timer(self) -> bool:
        """Cancels the reschedule timer for this room, if one
        exists. Returns whether a timer has been cancelled."""

        timer = self.reschedule_timer
        if timer is None:
            return False

        self.app.cancel_timer(timer)
        self.reschedule_timer = None
        self.log("Cancelled re-schedule timer.", level="DEBUG")
        return True

    def check_for_open_window(self) -> bool:
        """Checks whether a window is open in this room and,
        if so, turns the heating off there. The value stored in
        self.wanted_temp is restored after the heating
        has been turned off. It returns True if a window is open,
        False otherwise."""

        if self.get_open_windows():
            # window is open, turn heating off
            orig_temp = self.wanted_temp
            open_temp = self.app.cfg["window_open_temp"]
            if orig_temp != open_temp:
                self.log("Setting heating to {} due to an open window."
                         .format(open_temp),
                         prefix=common.LOG_PREFIX_OUTGOING)
                self.set_temp(open_temp, scheduled=False)
                self.wanted_temp = orig_temp
            return True
        return False

    def eval_temp_expr(
            self, temp_expr: expr.ExprType
    ) -> T.Union[expr.ResultBase, None, Exception]:
        """This is a wrapper around expr.eval_temp_expr that adds the
        room_name to the evaluation environment, as well as all configured
        temp_expression_modules. It also catches any exception is raised
        during evaluation. In this case, the caught Exception object
        is returned."""

        extra_env = {
            "room_name": self.name,
        }

        try:
            return expr.eval_temp_expr(temp_expr, self.app, extra_env=extra_env)
        except Exception as err:  # pylint: disable=broad-except
            self.log("Error while evaluating temperature expression: "
                     "{}".format(repr(err)),
                     level="ERROR")
            return err

    def eval_schedule(
            self, sched: schedule.Schedule, when: datetime.datetime
    ) -> T.Optional[T.Tuple[expr.Temp, schedule.Rule]]:
        """Evaluates a schedule, computing the temperature for the time
        the given datetime object represents. The temperature and the
        matching rule are returned.
        If no temperature could be found in the schedule (e.g. all
        rules evaluate to Skip()), None is returned."""

        def insert_paths(
                paths: T.List[schedule.RulePath], first_index: int,
                path_prefix: schedule.RulePath,
                rules: T.Iterable[schedule.Rule]
        ) -> None:
            """Helper to append each single of a set of rules to a commmon
            path prefix and insert the resulting paths into a list."""

            for rule in rules:
                path = path_prefix.copy()
                path.add(rule)
                paths.insert(first_index, path)
                first_index += 1

        def log(
                msg: str, path: schedule.RulePath,
                *args: T.Any, **kwargs: T.Any
        ) -> None:
            """Wrapper around self.log that prefixes spaces to the
            message based on the length of the rule path."""

            prefix = " " * 3 * max(0, len(path.rules) - 1) + "\u251c\u2500"
            self.log("{} {}".format(prefix, msg), *args, **kwargs)

        self.log("Assuming it to be {}.".format(when),
                 level="DEBUG")

        rules = list(sched.get_matching_rules(when))
        self.log("{} / {} rules of {} are currently valid."
                 .format(len(rules), len(sched.rules), sched),
                 level="DEBUG")

        result_sum = expr.Add(0)
        temp_expr_cache = {}  # type: T.Dict[expr.ExprType, T.Union[expr.ResultBase, None, Exception]]
        paths = []  # type: T.List[schedule.RulePath]
        insert_paths(paths, 0, schedule.RulePath(sched), rules)
        path_idx = 0
        while path_idx < len(paths):
            path = paths[path_idx]
            path_idx += 1

            log("{}".format(path), path, level="DEBUG")

            last_rule = path.rules[-1]
            if isinstance(last_rule, schedule.SubScheduleRule):
                _rules = list(last_rule.sub_schedule.get_matching_rules(when))
                log("{} / {} rules of {} are currently valid."
                    .format(len(_rules), len(last_rule.sub_schedule.rules),
                            last_rule.sub_schedule),
                    path, level="DEBUG")
                insert_paths(paths, path_idx, path, _rules)
                continue

            result = None
            rules_with_temp = path.rules_with_temp
            for rule in reversed(rules_with_temp):
                # for mypy only
                assert rule.temp_expr is not None and \
                       rule.temp_expr_raw is not None
                if rule.temp_expr_raw in temp_expr_cache:
                    result = temp_expr_cache[rule.temp_expr_raw]
                    log("=> {}  [cache-hit]".format(repr(result)),
                        path, level="DEBUG")
                else:
                    result = self.eval_temp_expr(rule.temp_expr)
                    temp_expr_cache[rule.temp_expr_raw] = result
                    log("=> {}".format(repr(result)),
                        path, level="DEBUG")
                if result is not None:
                    break

            if result is None:
                if rules_with_temp:
                    log("All temperature expressions returned None, "
                        "skipping rule.",
                        path, level="WARNING")
                else:
                    log("No temperature definition found, skipping rule.",
                        path, level="WARNING")
            elif isinstance(result, Exception):
                log("Evaluation failed, skipping rule.",
                    path, level="DEBUG")
            elif isinstance(result, expr.AddibleMixin):
                result_sum += result
                if isinstance(result_sum, expr.Result):
                    self.log("Final result: {}".format(result_sum.value),
                             level="DEBUG")
                    return result_sum.value, last_rule
            elif isinstance(result, expr.Abort):
                break
            elif isinstance(result, expr.Break):
                prefix_size = max(0, len(path.rules) - result.levels)
                prefix = path.rules[:prefix_size]
                while path_idx < len(paths) and \
                      paths[path_idx].root_schedule == path.root_schedule and \
                      paths[path_idx].rules[:prefix_size] == prefix:
                    del paths[path_idx]
            elif isinstance(result, expr.IncludeSchedule):
                _rules = list(result.schedule.get_matching_rules(when))
                log("{} / {} rules of {} are currently valid."
                    .format(len(_rules), len(result.schedule.rules),
                            result.schedule),
                    path, level="DEBUG")
                insert_paths(paths, path_idx,
                             schedule.RulePath(result.schedule), _rules)

        self.log("Found no result.", level="DEBUG")
        return None

    def get_open_windows(self) -> T.List[WindowSensor]:
        """Returns a list of window sensors in this room which
        currently report to be open,"""

        return list(filter(lambda sensor: sensor.is_open, self.window_sensors))

    def get_scheduled_temp(
            self,
    ) -> T.Optional[T.Tuple[expr.Temp, schedule.Rule]]:
        """Computes and returns the temperature that is configured for
        the current date and time. The second return value is the rule
        which generated the result.
        If no temperature could be found in the schedule (e.g. all
        rules evaluate to Skip()), None is returned."""

        if self.schedule is None:
            return None
        return self.eval_schedule(self.schedule, self.app.datetime())

    def initialize(self) -> None:
        """Should be called after all schedules, thermostats and window
        sensors have been added in order to register state listeners
        and timers."""

        self.log("Initializing room (name={})."
                 .format(repr(self.name)),
                 level="DEBUG")

        _scheduled_temp = self._get_sensor("scheduled_temp")
        try:
            self.scheduled_temp = expr.Temp(_scheduled_temp)
        except ValueError:
            self.log("Last scheduled temperature is unknown.",
                     level="DEBUG")
        else:
            self.log("Last scheduled temperature was {}."
                     .format(self.scheduled_temp),
                     level="DEBUG")

        # initialize all thermostats first to fetch their states,
        # then listen to the target_temp_changed event
        for therm in self.thermostats:
            therm.initialize()
        for therm in self.thermostats:
            therm.events.on(
                "target_temp_changed", self.notify_target_temp_changed
            )

        for wsensor in self.window_sensors:
            wsensor.initialize()
            wsensor.events.on("open_close", self.notify_window_action)

        if self.schedule:
            times = self.schedule.get_scheduling_times()
            self.log("Registering scheduling timers at: {{{}}}"
                     .format(", ".join([str(_time) for _time in times])),
                     level="DEBUG")
            for _time in times:
                self.app.run_daily(self._schedule_timer_cb, _time)
        else:
            self.log("No schedule configured.", level="DEBUG")

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the room to log messages."""
        msg = "[{}] {}".format(self, msg)
        self.app.log(msg, *args, **kwargs)

    def notify_set_temp_event(
            self, temp_expr: expr.ExprType, force_resend: bool = False,
            reschedule_delay: T.Union[float, int, None] = None
    ) -> None:
        """Handles a heaty_set_temp event for this room."""

        self.log("heaty_set_temp event received, temperature: {}"
                 .format(repr(temp_expr)))
        self.set_temp_manually(temp_expr, force_resend=force_resend,
                               reschedule_delay=reschedule_delay)

    def notify_target_temp_changed(
            self, therm: "Thermostat", temp: expr.Temp,
    ) -> None:
        """Should be called when the temperature has been changed
        externally by manual adjustment at a thermostat."""

        if self.get_open_windows():
            # After window has been opened and heating turned off,
            # thermostats usually report to be off, but we don't
            # care to not mess up self.wanted_temp and prevent
            # replication.
            return

        if not therm.cfg["supports_temps"]:
            # dumb switches don't trigger change replication
            return

        if not self.app.master_is_on():
            return

        neutral_temp = temp - therm.cfg["delta"]

        if self.cfg["replicate_changes"] and len(self.thermostats) > 1:
            self.log("Propagating the change to all thermostats "
                     "in the room.",
                     prefix=common.LOG_PREFIX_OUTGOING)
            self.set_temp(neutral_temp, scheduled=False)

        if neutral_temp == self.wanted_temp:
            self.cancel_reschedule_timer()
        elif self.cfg["reschedule_delay"]:
            self.start_reschedule_timer(restart=True)

    def notify_window_action(self, sensor: WindowSensor, is_open: bool) -> None:  # pylint: disable=unused-argument
        """This method reacts on window opened/closed events.
        It handles the window open/closed detection and performs actions
        accordingly."""

        action = "opened" if is_open else "closed"
        self.log("Window has been {}.".format(action),
                 prefix=common.LOG_PREFIX_INCOMING)

        if not self.app.require_master_is_on():
            return

        if is_open:
            # turn heating off, but store the original temperature
            self.check_for_open_window()
        elif not self.get_open_windows():
            # all windows closed
            # restore temperature from before opening the window
            orig_temp = self.wanted_temp
            # could be None if we didn't know the temperature before
            # opening the window
            if orig_temp is None:
                self.log("Restoring temperature from schedule.",
                         level="DEBUG")
                self.apply_schedule()
            else:
                self.log("Restoring temperature to {}.".format(orig_temp),
                         level="DEBUG")
                self.set_temp(orig_temp, scheduled=False)

    def set_temp(
            self, target_temp: expr.Temp, scheduled: bool = False,
            force_resend: bool = False
    ) -> None:
        """Sets the given target temperature for all thermostats in the
        room. If scheduled is True, a disabled master switch prevents
        setting the temperature.
        Temperatures won't be send to thermostats redundantly unless
        force_resend is True."""

        if scheduled and not self.app.require_master_is_on():
            return

        self.log("Setting temperature to {}.  [{}{}]"
                 .format(target_temp,
                         "scheduled" if scheduled else "manual",
                         ", force re-sending" if force_resend else ""),
                 level="DEBUG")

        self.wanted_temp = target_temp

        changed = False
        for therm in self.thermostats:
            result = therm.set_temp(target_temp, force_resend=force_resend)
            changed = changed or bool(result)

        if changed:
            self.log("Temperature set to {}.  [{}]"
                     .format(target_temp,
                             "scheduled" if scheduled else "manual"),
                     prefix=common.LOG_PREFIX_OUTGOING)

    def set_temp_manually(
            self, temp_expr: expr.ExprType, force_resend: bool = False,
            reschedule_delay: T.Union[float, int, None] = None
    ) -> None:
        """Evaluates the given temperature expression and sets the result.
        If the master switch is turned off, this won't do anything.
        If force_resend is True and the temperature didn't
        change, it is sent to the thermostats anyway.
        An existing re-schedule timer is cancelled and a new one is
        started if re-schedule timers are configured. reschedule_delay,
        if given, overwrites the value configured for the room.
        In case of an open window, temperature is cached and not sent."""

        if not self.app.require_master_is_on():
            return

        result = self.eval_temp_expr(temp_expr)
        self.log("Evaluated temperature expression {} to {}."
                 .format(repr(temp_expr), repr(result)),
                 level="DEBUG")

        temp = None
        if isinstance(result, expr.IncludeSchedule):
            _result = self.eval_schedule(result.schedule, self.app.datetime())
            if _result is not None:
                temp = _result[0]
        elif isinstance(result, expr.Result):
            temp = result.value

        if temp is None:
            self.log("Ignoring temperature expression.")
            return

        if self.get_open_windows():
            self.log("Caching and not setting temperature due to an"
                     "open window.")
            self.wanted_temp = temp
        else:
            self.set_temp(temp, scheduled=False, force_resend=force_resend)

        self.start_reschedule_timer(reschedule_delay=reschedule_delay,
                                    restart=True)

    def start_reschedule_timer(
            self, reschedule_delay: T.Union[float, int, None] = None,
            restart: bool = False,
    ) -> bool:
        """This method registers a re-schedule timer according to the
        room's settings. reschedule_delay, if given, overwrites the value
        configured for the room. If there is a timer running already,
        no new one is started unless restart is set. The return value
        tells whether a timer has been started or not."""

        if not self.app.require_master_is_on():
            return False

        if self.reschedule_timer is not None:
            if restart:
                self.cancel_reschedule_timer()
            else:
                self.log("Re-schedule timer running already, starting no "
                         "second one.",
                         level="DEBUG")
                return False

        if reschedule_delay is None:
            reschedule_delay = self.cfg["reschedule_delay"]
        assert isinstance(reschedule_delay, (float, int))

        delta = datetime.timedelta(minutes=reschedule_delay)
        when = self.app.datetime() + delta
        self.log("Re-scheduling not before {} ({})."
                 .format(util.format_time(when.time()), delta))
        self.reschedule_timer = self.app.run_at(self._reschedule_timer_cb, when)

        return True
