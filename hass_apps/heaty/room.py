"""
This module implements the Room class.
"""

import typing as T
if T.TYPE_CHECKING:
    # pylint: disable=cyclic-import,unused-import
    import uuid
    from . import app as _app
    from . import thermostat

import datetime

from .. import common
from . import expr, schedule, util, window_sensor


class Room:
    """A room to be controlled by Heaty."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name: str, cfg: dict, app: "_app.HeatyApp") -> None:
        self.name = name
        self.cfg = cfg
        self.app = app
        self.thermostats = []  # type: T.List[thermostat.Thermostat]
        self.window_sensors = []  # type: T.List[window_sensor.WindowSensor]
        self.schedule = None  # type: T.Optional[schedule.Schedule]

        self.wanted_temp = None  # type: T.Optional[expr.Temp]
        self.reschedule_timer = None  # type: T.Optional[uuid.UUID]
        self.current_schedule_temp = None  # type: T.Optional[expr.Temp]
        self.current_schedule_rule = None  # type: T.Optional[schedule.Rule]

    def __repr__(self) -> str:
        return "<Room {}>".format(str(self))

    def __str__(self) -> str:
        return self.cfg.get("friendly_name", self.name)

    @util.modifies_state
    def _reschedule_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a re-schedule timer fires."""

        self.log("Re-schedule timer fired.",
                 level="DEBUG")

        self.reschedule_timer = None

        # invalidate cached temp/rule
        self.current_schedule_temp = None
        self.current_schedule_rule = None

        self.set_scheduled_temp()

    def _schedule_timer_cb(self, kwargs: dict) -> None:
        """Is called whenever a schedule timer fires."""

        self.log("Schedule timer fired.",
                 level="DEBUG")
        self.set_scheduled_temp()

    def initialize(self) -> None:
        """Should be called after all schedules, thermostats and window
        sensors have been added in order to register state listeners
        and timers."""

        for therm in self.thermostats:
            therm.initialize()

        for wsensor in self.window_sensors:
            wsensor.initialize()

        if self.schedule:
            self.log("Creating schedule timers.", level="DEBUG")
            # We collect the times in a set first to avoid registering
            # multiple timers for the same time.
            times = set()  # type: T.Set[datetime.time]
            for rule in self.schedule.unfold():
                times.update((rule.start_time, rule.end_time))

            # Now register a timer for each time a rule starts or ends.
            for _time in times:
                self.log("Registering timer at {}.".format(_time),
                         level="DEBUG")
                self.app.run_daily(self._schedule_timer_cb, _time)

    def log(self, msg: str, *args: T.Any, **kwargs: T.Any) -> None:
        """Prefixes the room to log messages."""
        msg = "[{}] {}".format(self, msg)
        self.app.log(msg, *args, **kwargs)

    @util.modifies_state
    def set_temp(
            self, target_temp: expr.Temp, scheduled: bool = False,
            force_resend: bool = False
    ) -> None:
        """Sets the given target temperature for all thermostats in the
        room. If scheduled is True, a disabled master switch prevents
        setting the temperature.
        Temperatures won't be send to thermostats redundantly unless
        force_resend is True."""

        if scheduled and \
           not self.app.master_switch_enabled():
            return

        self.wanted_temp = target_temp

        changed = False
        for therm in self.thermostats:
            result = therm.set_temp(target_temp, force_resend=force_resend)
            changed = changed or bool(result)

        if changed:
            self.log("Temperature set to {}.  <{}>"
                     .format(target_temp,
                             "scheduled" if scheduled else "manual"),
                     prefix=common.LOG_PREFIX_OUTGOING)

    def eval_temp_expr(
            self, temp_expr: expr.EXPR_TYPE
    ) -> T.Optional[expr.ResultBase]:
        """This is a wrapper around expr.eval_temp_expr that adds the
        app object, the room name  and some helpers to the evaluation
        environment, as well as all configured
        temp_expression_modules. It also catches and logs any
        exception which is raised during evaluation. In this case,
        None is returned."""

        # use date/time provided by appdaemon to support time-traveling
        now = self.app.datetime()
        extra_env = {
            "app": self.app,
            "schedule_snippets": self.app.cfg["schedule_snippets"],
            "room_name": self.name,
            "now": now,
            "date": now.date(),
            "time": now.time(),
        }
        extra_env.update(self.app.temp_expression_modules)

        try:
            return expr.eval_temp_expr(temp_expr, extra_env=extra_env)
        except Exception as err:  # pylint: disable=broad-except
            self.log("Error while evaluating temperature expression: "
                     "{}".format(repr(err)),
                     level="ERROR")
            return None

    def eval_schedule(
            self, sched: schedule.Schedule, when: datetime.datetime
    ) -> T.Optional[T.Tuple[expr.Temp, schedule.Rule]]:
        """Evaluates a schedule, computing the temperature for the time
        the given datetime object represents. The temperature and the
        matching rule are returned.
        If no temperature could be found in the schedule (e.g. all
        rules evaluate to Ignore()), None is returned."""

        result_sum = expr.Add(0)
        rules = list(sched.matching_rules(when))
        idx = 0
        while idx < len(rules):
            rule = rules[idx]
            idx += 1

            result = self.eval_temp_expr(rule.temp_expr)
            self.log("Evaluated temperature expression {} to {}."
                     .format(repr(rule.temp_expr_raw), result),
                     level="DEBUG")

            if result is None:
                self.log("Skipping rule with faulty temperature "
                         "expression: {}"
                         .format(rule.temp_expr_raw))
                continue

            if isinstance(result, expr.Break):
                # abort, don't change temperature
                self.log("Aborting scheduling due to Break().",
                         level="DEBUG")
                return None

            if isinstance(result, expr.Ignore):
                self.log("Skipping this rule.",
                         level="DEBUG")
                continue

            if isinstance(result, expr.IncludeSchedule):
                self.log("Inserting sub-schedule.",
                         level="DEBUG")
                _rules = result.schedule.matching_rules(self.app.datetime())
                for _idx, _rule in enumerate(_rules):
                    rules.insert(idx + _idx, _rule)
                continue

            if isinstance(result, expr.AddibleMixin):
                result_sum += result

            if isinstance(result_sum, expr.Result):
                return result_sum.temp, rule

        return None

    def get_scheduled_temp(
            self,
    ) -> T.Optional[T.Tuple[expr.Temp, schedule.Rule]]:
        """Computes and returns the temperature that is configured for
        the current date and time. The second return value is the rule
        which generated the result.
        If no temperature could be found in the schedule (e.g. all
        rules evaluate to Ignore()), None is returned."""

        if self.schedule is None:
            return None
        return self.eval_schedule(self.schedule, self.app.datetime())

    def set_scheduled_temp(self, force_resend: bool = False) -> None:
        """Sets the temperature that is configured for the current
        date and time. If the master switch is turned off, this won't
        do anything.
        This method won't re-schedule if a re-schedule timer runs.
        It will also detect when neither the rule nor the result
        of its temperature expression changed compared to the last run
        and prevent re-setting the temperature in that case.
        If force_resend is True, and the temperature didn't
        change, it is sent to the thermostats anyway.
        In case of an open window, temperature is cached and not sent."""

        if not self.app.master_switch_enabled():
            return

        if self.reschedule_timer:
            # don't schedule now, wait for the timer instead
            self.log("Not scheduling now due to a running re-schedule "
                     "timer.",
                     level="DEBUG")
            return

        result = self.get_scheduled_temp()
        if result is None:
            self.log("No suitable temperature found in schedule.",
                     level="DEBUG")
            return

        temp, rule = result
        if temp == self.current_schedule_temp and \
           rule is self.current_schedule_rule and \
           not force_resend:
            # temp and rule didn't change, what means that the
            # re-scheduling wasn't necessary and was e.g. caused
            # by a daily timer which doesn't count for today
            return

        self.current_schedule_temp = temp
        self.current_schedule_rule = rule

        if self.get_open_windows():
            self.log("Caching and not setting temperature due to an "
                     "open window.")
            self.wanted_temp = temp
        else:
            self.set_temp(temp, scheduled=True, force_resend=force_resend)

    def set_manual_temp(
            self, temp_expr: expr.EXPR_TYPE, force_resend: bool = False,
            reschedule_delay: T.Union[float, int, None] = None
    ) -> None:
        """Evaluates the given temperature expression and sets the result.
        If the master switch is turned off, this won't do anything.
        If force_resend is True, and the temperature didn't
        change, it is sent to the thermostats anyway.
        An existing re-schedule timer is cancelled and a new one is
        started if re-schedule timers are configured. reschedule_delay,
        if given, overwrites the value configured for the room.
        In case of an open window, temperature is cached and not sent."""

        if not self.app.master_switch_enabled():
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
            temp = result.temp

        if temp is None:
            self.log("Ignoring temperature expression.")
            return

        if self.get_open_windows():
            self.log("Caching and not setting temperature due to an"
                     "open window.")
            self.wanted_temp = temp
        else:
            self.set_temp(temp, scheduled=False, force_resend=force_resend)

        self.update_reschedule_timer(reschedule_delay=reschedule_delay)

    @util.modifies_state
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

    def get_open_windows(self) -> T.List[window_sensor.WindowSensor]:
        """Returns a list of window sensors in this room which
        currently report to be open,"""

        _open = filter(lambda sensor: sensor.is_open(),
                       self.window_sensors)
        return list(_open)

    def check_for_open_window(self) -> bool:
        """Checks whether a window is open in this room and,
        if so, turns the heating off there. The value stored in
        self.wanted_temp is restored after the heating
        has been turned off. It returns True if a window is open,
        False otherwise."""

        if self.get_open_windows():
            # window is open, turn heating off
            orig_temp = self.wanted_temp
            off_temp = self.app.cfg["off_temp"]
            if orig_temp != off_temp:
                self.log("Turning heating off due to an open "
                         "window.",
                         prefix=common.LOG_PREFIX_OUTGOING)
                self.set_temp(off_temp, scheduled=False)
                self.wanted_temp = orig_temp
            return True
        return False

    def notify_set_temp_event(
            self, temp_expr: expr.EXPR_TYPE, force_resend: bool = False,
            reschedule_delay: T.Union[float, int, None] = None
    ) -> None:
        """Handles a heaty_set_temp event for this room."""

        self.log("heaty_set_temp event received, temperature: {}"
                 .format(repr(temp_expr)))
        self.set_manual_temp(temp_expr, force_resend=force_resend,
                             reschedule_delay=reschedule_delay)

    def notify_temp_changed(
            self, temp: expr.Temp, no_reschedule: bool = False
    ) -> None:
        """Should be called when the temperature has been changed
        externally, e.g. by manual adjustment at a thermostat.
        Setting no_reschedule prevents re-scheduling."""

        if self.get_open_windows():
            # After window has been opened and heating turned off,
            # thermostats usually report to be off, but we don't
            # care to not mess up self.wanted_temp and prevent
            # replication.
            return

        self.wanted_temp = temp

        if not self.app.master_switch_enabled():
            return

        if self.cfg["replicate_changes"] and len(self.thermostats) > 1 and \
           self.app.master_switch_enabled():
            self.log("Propagating the change to all thermostats "
                     "in the room.",
                     prefix=common.LOG_PREFIX_OUTGOING)
            self.set_temp(temp, scheduled=False)

        if not no_reschedule:
            self.update_reschedule_timer()

    @util.modifies_state
    def update_reschedule_timer(
            self, reschedule_delay: T.Union[float, int, None] = None,
            force: bool = False,
    ) -> None:
        """This method cancels an existing re-schedule timer first.
        Then, it checks if either force is set or the wanted
        temperature differs from the scheduled temperature. If
        so, a new timer is created according to the room's
        settings. reschedule_delay, if given, overwrites the value
        configured for the room."""

        self.cancel_reschedule_timer()

        if not self.app.master_switch_enabled():
            return

        if reschedule_delay is None:
            reschedule_delay = self.cfg["reschedule_delay"]

        wanted = self.wanted_temp
        result = self.get_scheduled_temp()
        if not reschedule_delay or \
           (not force and result and wanted == result[0]):
            return

        delta = datetime.timedelta(minutes=reschedule_delay)
        when = self.app.datetime() + delta
        self.log("Re-scheduling not before {} ({})."
                 .format(util.format_time(when.time()), delta))
        timer = self.app.run_at(self._reschedule_timer_cb, when)
        self.reschedule_timer = timer
