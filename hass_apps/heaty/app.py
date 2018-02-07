"""
A highly-configurable, comfortable to use Home Assistant / appdaemon app
that controls thermostats based on a schedule while still facilitating
manual intervention at any time.
"""

import datetime
import importlib

from .. import common
from . import __version__, config, expr, util


__all__ = ["HeatyApp"]


def modifies_state(func):
    """This decorator calls update_publish_state_timer() after the
    method decorated with it ran. It may only be used for non-static
    methods of the Heaty class, because it fetches the Heaty object
    from the method's arguments."""

    def _new_func(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.update_publish_state_timer()
        return result

    _new_func.__name__ = func.__name__
    _new_func.__doc__ = func.__doc__
    _new_func.__dict__.update(func.__dict__)
    return _new_func


class HeatyApp(common.App):
    """The Heaty app class for AppDaemon."""

    # pylint: disable=too-many-public-methods

    class Meta(common.App.Meta):
        # pylint: disable=missing-docstring
        name = "heaty"
        version = __version__
        config_schema = config.CONFIG_SCHEMA

    def __init__(self, *args, **kwargs):
        self.cfg = None
        self.publish_state_timer = None
        self.temp_expression_modules = {}
        super(HeatyApp, self).__init__(*args, **kwargs)

    @modifies_state
    def initialize_inner(self):
        """Parses the configuration, initializes all timers, state and
        event callbacks and sets temperatures in all rooms according
        to the configured schedules."""

        # pylint: disable=too-many-branches,too-many-locals,too-many-statements

        heaty_id = self.cfg["heaty_id"]
        self.log("--- Heaty id is: {}".format(repr(heaty_id)))
        heaty_id_kwargs = {}
        if heaty_id != "default":
            heaty_id_kwargs["heaty_id"] = heaty_id

        self.log("--- Importing modules for temperature expressions.",
                 level="DEBUG")
        for mod_name, mod_data in self.cfg["temp_expression_modules"].items():
            as_name = util.escape_var_name(mod_data.get("as", mod_name))
            self.log("--- Importing module {} as {}."
                     .format(repr(mod_name), repr(as_name)),
                     level="DEBUG")
            try:
                mod = importlib.import_module(mod_name)
            except Exception as err:  # pylint: disable=broad-except
                self.error("!!! Error while importing module {}: {}"
                           .format(repr(mod_name), repr(err)))
                self.error("!!! Module won't be available.")
            else:
                self.temp_expression_modules[as_name] = mod

        self.log("--- Getting current temperatures from thermostats.")
        for room_name, room in self.cfg["rooms"].items():
            for therm_name in room["thermostats"]:
                # fetch initial state from thermostats
                state = self.get_state(therm_name, attribute="all")
                if state is None:
                    # unknown entity
                    self.log("!!! State for thermostat {} is None, "
                             "ignoring it.".format(therm_name))
                    continue
                # provide compatibility with appdaemon 3
                if self._is_ad3:
                    state = {"attributes": state}
                # populate therm["current_temp"] by simulating a state change
                self.thermostat_state_cb(therm_name, "all", state, state,
                                         {"room_name": room_name,
                                          "no_reschedule": True})
                # only consider one thermostat per room
                break

        self.log("--- Registering event listener for heaty_reschedule.",
                 level="DEBUG")
        self.listen_event(self.reschedule_event_cb, "heaty_reschedule",
                          **heaty_id_kwargs)

        self.log("--- Registering event listener for heaty_set_temp.",
                 level="DEBUG")
        self.listen_event(self.set_temp_event_cb, "heaty_set_temp",
                          **heaty_id_kwargs)

        self.log("--- Creating schedule timers.", level="DEBUG")
        for room_name, room in self.cfg["rooms"].items():
            # we collect the times in a set first to avoid registering
            # multiple timers for the same time
            times = set()
            for rule in room["schedule"].unfold():
                times.update((rule.start_time, rule.end_time))

            # now register a timer for each time a rule starts or ends
            for _time in times:
                self.log("--- [{}] Registering timer at {}."
                         .format(room["friendly_name"], _time),
                         level="DEBUG")
                self.run_daily(self.schedule_timer_cb, _time,
                               room_name=room_name)

        self.log("--- Registering thermostat state listeners.", level="DEBUG")
        for room_name, room in self.cfg["rooms"].items():
            for therm_name in room["thermostats"]:
                self.log("--- [{}] Registering state listener for {}."
                         .format(room["friendly_name"], therm_name),
                         level="DEBUG")
                self.listen_state(self.thermostat_state_cb, therm_name,
                                  attribute="all", room_name=room_name)

        self.log("--- Registering window sensor state listeners.",
                 level="DEBUG")
        for room_name, room in self.cfg["rooms"].items():
            for sensor_name, sensor in room["window_sensors"].items():
                self.log("--- [{}] Registering state listener for {}, "
                         "delay {}.".format(
                             room["friendly_name"], sensor_name,
                             sensor["delay"]),
                         level="DEBUG")
                self.listen_state(self.window_sensor_cb, sensor_name,
                                  duration=sensor["delay"],
                                  room_name=room_name)

        master_switch = self.cfg["master_switch"]
        if master_switch:
            self.log("--- Registering state listener for {}."
                     .format(master_switch),
                     level="DEBUG")
            self.listen_state(self.master_switch_cb, master_switch)

        if self.master_switch_enabled():
            for room_name in self.cfg["rooms"]:
                if not self.check_for_open_window(room_name):
                    self.set_scheduled_temp(room_name)
        else:
            self.log("--- Master switch is off, not setting temperatures "
                     "initially.")

    @modifies_state
    def master_switch_cb(self, entity, attr, old, new, kwargs):
        """Is called when the master switch is toggled.
        If turned on, it sets the scheduled temperatures in all rooms.
        If switch is turned off, all re-schedule timers are cancelled
        and temperature is set to self.cfg["off_temp"] everywhere."""

        self.log("--> Master switch turned {}.".format(new))
        for room_name, room in self.cfg["rooms"].items():
            if new == "on":
                self.set_scheduled_temp(room_name)
            else:
                self.cancel_reschedule_timer(room_name)
                self.set_temp(room_name, self.cfg["off_temp"],
                              scheduled=False)
                # invalidate cached temp/rule
                room.pop("current_schedule_temp", None)
                room.pop("current_schedule_rule", None)

    def publish_state_timer_cb(self, kwargs):
        """Runs when a publish_state timer fires."""

        self.publish_state_timer = None
        self.publish_state()

    def schedule_timer_cb(self, kwargs):
        """Is called whenever a schedule timer fires."""

        room_name = kwargs["room_name"]
        room = self.cfg["rooms"][room_name]

        self.log("--- [{}] Schedule timer fired."
                 .format(room["friendly_name"]),
                 level="DEBUG")

        self.set_scheduled_temp(room_name)

    @modifies_state
    def reschedule_timer_cb(self, kwargs):
        """Is called whenever a re-schedule timer fires."""

        room_name = kwargs["room_name"]
        room = self.cfg["rooms"][room_name]

        self.log("--- [{}] Re-schedule timer fired."
                 .format(room["friendly_name"]),
                 level="DEBUG")

        try:
            del room["reschedule_timer"]
        except KeyError:
            pass

        # invalidate cached temp/rule
        room.pop("current_schedule_temp", None)
        room.pop("current_schedule_rule", None)

        self.set_scheduled_temp(room_name)

    def reschedule_event_cb(self, event, data, kwargs):
        """This callback executes when a heaty_reschedule event is received.
        data may contain a "room_name", which limits the re-scheduling
        to the given room."""

        if not self.master_switch_enabled():
            self.log("--- Ignoring re-schedule event because master "
                     "switch is off.",
                     level="WARNING")
            return

        room_name = data.get("room_name")
        if room_name:
            if room_name not in self.cfg["rooms"]:
                self.log("--- [{}] Ignoring heaty_reschedule event for "
                         "unknown room.".format(room_name),
                         level="WARNING")
                return
            room_names = [room_name]
        else:
            room_names = self.cfg["rooms"].keys()

        self.log("--> Re-schedule event received for rooms: {}"
                 .format(", ".join(room_names)))

        for room_name in room_names:
            # delay for 6 seconds to avoid re-scheduling multiple
            # times if multiple events come in shortly
            self.update_reschedule_timer(room_name, reschedule_delay=0.1,
                                         force=True)

    def set_temp_event_cb(self, event, data, kwargs):
        """This callback executes when a heaty_set_temp event is received.
        data must contain a "room_name" and a "temp", which may also
        be a temperature expression. "force_resend" is optional and
        False by default. If it is set to True, the temperature is
        re-sent to the thermostats even if it hasn't changed due to
        Heaty's records."""

        try:
            room_name = data["room_name"]
            temp_expr = data["temp"]
            reschedule_delay = data.get("reschedule_delay")
            if not isinstance(reschedule_delay, (type(None), float, int)):
                raise TypeError()
            if isinstance(reschedule_delay, (float, int)) and \
               reschedule_delay < 0:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            self.log("--- Ignoring heaty_set_temp event with invalid data: {}"
                     "room.".format(repr(data)),
                     level="WARNING")
            return

        if room_name not in self.cfg["rooms"]:
            self.log("--- [{}] Ignoring heaty_set_temp event for unknown "
                     "room.".format(room_name),
                     level="WARNING")
            return

        if not self.cfg["untrusted_temp_expressions"] and \
           expr.Temp.parse_temp(temp_expr) is None:
            self.log("--- [{}] Ignoring heaty_set_temp event with an "
                     "untrusted temperature expression. "
                     "(untrusted_temp_expressions = false)".format(room_name),
                     level="WARNING")
            return

        room = self.cfg["rooms"][room_name]
        self.log("--- [{}] heaty_set_temp event received, temperature: {}"
                 .format(room["friendly_name"], repr(temp_expr)))

        self.set_manual_temp(room_name, temp_expr,
                             force_resend=bool(data.get("force_resend")),
                             reschedule_delay=reschedule_delay)

    @modifies_state
    def thermostat_state_cb(self, entity, attr, old, new, kwargs):
        """Is called when a thermostat's state changes.
        This method fetches the set target temperature from the
        thermostat and sends updates to all other thermostats in
        the room."""

        room_name = kwargs["room_name"]
        room = self.cfg["rooms"][room_name]
        therm = room["thermostats"][entity]

        # make attribute access more robust
        old = (old or {}).get("attributes", {})
        new = (new or {}).get("attributes", {})

        opmode = new.get(therm["opmode_state_attr"])
        self.log("--> [{}] {}: attribute {} is {}"
                 .format(room["friendly_name"], entity,
                         therm["opmode_state_attr"], opmode),
                 level="DEBUG")

        if opmode is None:
            # don't consider this thermostat
            return
        elif opmode == therm["opmode_off"]:
            temp = expr.Temp("off")
        else:
            temp = new.get(therm["temp_state_attr"])
            self.log("--> [{}] {}: attribute {} is {}"
                     .format(room["friendly_name"], entity,
                             therm["temp_state_attr"], temp),
                     level="DEBUG")
            try:
                temp = expr.Temp(temp) - therm["delta"]
            except ValueError:
                # not a valid temperature, don't consider this thermostat
                return

        if temp == therm["current_temp"]:
            # nothing changed, hence no further actions needed
            return

        self.log("--> [{}] Received target temperature {} from thermostat."
                 .format(room["friendly_name"], repr(temp)))
        therm["current_temp"] = temp

        if temp == room["wanted_temp"]:
            # thermostat adapted to the temperature we set,
            # cancel any re-send timer
            self.cancel_resend_timer(room_name, entity)

        if temp.is_off() and \
           isinstance(room["wanted_temp"], expr.Temp) and \
           isinstance(therm["min_temp"], expr.Temp) and \
           not room["wanted_temp"].is_off() and \
           room["wanted_temp"] + therm["delta"] < \
           therm["min_temp"]:
            # The thermostat reported itself to be off, but the
            # expected temperature is outside the thermostat's
            # supported temperature range anyway. Hence the report
            # means no change and can safely be ignored.
            return
        if self.get_open_windows(room_name):
            # After window has been opened and heating turned off,
            # thermostats usually report to be off, but we don't
            # care to not mess up room["wanted_temp"] and prevent
            # replication.
            return

        if len(room["thermostats"]) > 1 and \
           room["replicate_changes"] and self.master_switch_enabled():
            self.log("<-- [{}] Propagating the change to all thermostats "
                     "in the room.".format(room["friendly_name"]))
            self.set_temp(room_name, temp, scheduled=False)
        else:
            # just update the records
            room["wanted_temp"] = temp

        # only re-schedule when no re-send timer is running and
        # re-scheduling is not disabled explicitly
        if not therm.get("resend_timer") and not kwargs.get("no_reschedule"):
            self.update_reschedule_timer(room_name)

    @modifies_state
    def window_sensor_cb(self, entity, attr, old, new, kwargs):
        """Is called when a window sensor's state has changed.
        This method handles the window open/closed detection and
        performs actions accordingly."""

        room_name = kwargs["room_name"]
        room = self.cfg["rooms"][room_name]
        action = "opened" if self.window_open(room_name, entity) else "closed"
        self.log("--> [{}] {}: state is now {}"
                 .format(room["friendly_name"], entity, new),
                 level="DEBUG")
        self.log("--> [{}] Window {}.".format(room["friendly_name"], action))

        if not self.master_switch_enabled():
            self.log("--- [{}] Master switch is off, ignoring window."
                     .format(room["friendly_name"]))
            return

        if action == "opened":
            # turn heating off, but store the original temperature
            self.check_for_open_window(room_name)
        elif not self.get_open_windows(room_name):
            # all windows closed
            # restore temperature from before opening the window
            orig_temp = room["wanted_temp"]
            # could be None if we don't knew the temperature before
            # opening the window
            if orig_temp is None:
                self.set_scheduled_temp(room_name)
            else:
                self.set_temp(room_name, orig_temp, scheduled=False)

    @modifies_state
    def set_temp(self, room_name, target_temp, scheduled=False,
                 force_resend=False):
        """Sets the given target temperature for all thermostats in the
        given room. If scheduled is True, disabled master switch
        prevents setting the temperature.
        Temperatures won't be send to thermostats redundantly unless
        force_resend is True."""

        room = self.cfg["rooms"][room_name]

        if scheduled and \
           not self.master_switch_enabled():
            return

        synced = all(map(lambda therm: target_temp == therm["current_temp"],
                         room["thermostats"].values()))
        if synced and not force_resend:
            return

        self.log("<-- [{}] Temperature set to {}.  <{}>"
                 .format(room["friendly_name"], target_temp,
                         "scheduled" if scheduled else "manual"))
        room["wanted_temp"] = target_temp

        for therm_name, therm in room["thermostats"].items():
            if target_temp == therm["current_temp"] and not force_resend and \
               "resend_timer" not in therm:
                self.log("--- [{}] Not sending temperature to {} "
                         "redundantly."
                         .format(room["friendly_name"], therm_name),
                         level="DEBUG")
                continue

            if target_temp.is_off():
                temp = None
                opmode = therm["opmode_off"]
            else:
                temp = target_temp + therm["delta"]
                if isinstance(therm["min_temp"], expr.Temp) and \
                   temp < therm["min_temp"]:
                    temp = None
                    opmode = therm["opmode_off"]
                else:
                    opmode = therm["opmode_heat"]

            left_retries = therm["set_temp_retries"]
            self.cancel_resend_timer(room_name, therm_name)
            timer = self.run_in(self.set_temp_resend_cb, 1,
                                room_name=room_name, therm_name=therm_name,
                                left_retries=left_retries,
                                opmode=opmode, temp=temp)
            therm["resend_timer"] = timer

    def set_temp_resend_cb(self, kwargs):
        """This callback sends the operation_mode and temperature to the
        thermostat. Expected values for kwargs are:
        - room_name and therm_name,
        - opmode and temp (incl. delta)
        - left_retries (after this round)"""

        room_name = kwargs["room_name"]
        therm_name = kwargs["therm_name"]
        opmode = kwargs["opmode"]
        temp = kwargs["temp"]
        left_retries = kwargs["left_retries"]
        room = self.cfg["rooms"][room_name]
        therm = room["thermostats"][therm_name]

        self.cancel_resend_timer(room_name, therm_name)

        self.log("<-- [{}] Setting {}: {}={}, {}={}, left retries={}"
                 .format(room["friendly_name"], therm_name,
                         therm["temp_service_attr"],
                         temp if temp is not None else "<unset>",
                         therm["opmode_service_attr"],
                         opmode,
                         left_retries),
                 level="DEBUG")

        attrs = {"entity_id": therm_name,
                 therm["opmode_service_attr"]: opmode}
        self.call_service(therm["opmode_service"], **attrs)
        if temp is not None:
            attrs = {"entity_id": therm_name,
                     therm["temp_service_attr"]: temp.value}
            self.call_service(therm["temp_service"], **attrs)

        if not left_retries:
            return

        interval = therm["set_temp_retry_interval"]
        self.log("--- [{}] Re-sending to {} in {} seconds."
                 .format(room["friendly_name"], therm_name, interval),
                 level="DEBUG")
        timer = self.run_in(self.set_temp_resend_cb, interval,
                            room_name=room_name, therm_name=therm_name,
                            left_retries=left_retries - 1,
                            opmode=opmode, temp=temp)
        therm["resend_timer"] = timer

    def eval_schedule(self, room_name, sched, when):  # pylint: disable=inconsistent-return-statements
        """Evaluates a schedule, computing the temperature for the time
        the given datetime object represents. The temperature and the
        matching rule are returned. The room name is only used for logging.
        If no temperature could be found in the schedule (e.g. all
        rules evaluate to Ignore()), None is returned."""

        room = self.cfg["rooms"][room_name]

        result_sum = expr.Add(0)
        rules = list(sched.matching_rules(when))
        idx = 0
        while idx < len(rules):
            rule = rules[idx]
            idx += 1

            result = self.eval_temp_expr(rule.temp_expr, room_name)
            self.log("--- [{}] Evaluated temperature expression {} "
                     "to {}."
                     .format(room["friendly_name"],
                             repr(rule.temp_expr_raw), result),
                     level="DEBUG")

            if result is None:
                self.log("--- Skipping rule with faulty temperature "
                         "expression: {}"
                         .format(rule.temp_expr_raw))
                continue

            if isinstance(result, expr.Break):
                # abort, don't change temperature
                self.log("--- [{}] Aborting scheduling due to Break()."
                         .format(room["friendly_name"]),
                         level="DEBUG")
                return None

            if isinstance(result, expr.Ignore):
                self.log("--- [{}] Skipping this rule."
                         .format(room["friendly_name"]),
                         level="DEBUG")
                continue

            if isinstance(result, expr.IncludeSchedule):
                self.log("--- [{}] Inserting sub-schedule."
                         .format(room["friendly_name"]),
                         level="DEBUG")
                _rules = result.schedule.matching_rules(self.datetime())
                for _idx, _rule in enumerate(_rules):
                    rules.insert(idx + _idx, _rule)
                continue

            result_sum += result

            if isinstance(result_sum, expr.Result):
                return result_sum.temp, rule

    def get_scheduled_temp(self, room_name):
        """Computes and returns the temperature that is configured for
        the current date and time in the given room. The second return
        value is the rule which generated the result.
        If no temperature could be found in the schedule (e.g. all
        rules evaluate to Ignore()), None is returned."""

        room = self.cfg["rooms"][room_name]
        return self.eval_schedule(room_name, room["schedule"],
                                  self.datetime())

    def set_scheduled_temp(self, room_name, force_resend=False):
        """Sets the temperature that is configured for the current
        date and time in the given room. If the master switch is
        turned off, this won't do anything.
        This method won't re-schedule if a re-schedule timer runs.
        It will also detect when neither the rule nor the result
        of its temperature expression changed compared to the last run
        and prevent re-setting the temperature in that case.
        If force_resend is True, and the temperature didn't
        change, it is sent to the thermostats anyway.
        In case of an open window, temperature is cached and not sent."""

        room = self.cfg["rooms"][room_name]

        if not self.master_switch_enabled():
            return

        if room.get("reschedule_timer"):
            # don't schedule now, wait for the timer instead
            self.log("--- [{}] Not scheduling now due to a running "
                     "re-schedule timer."
                     .format(room["friendly_name"]),
                     level="DEBUG")
            return

        result = self.get_scheduled_temp(room_name)
        if result is None:
            self.log("--- [{}] No suitable temperature found in schedule."
                     .format(room["friendly_name"]),
                     level="DEBUG")
            return

        temp, rule = result
        if temp == room.get("current_schedule_temp") and \
           rule is room.get("current_schedule_rule") and \
           not force_resend:
            # temp and rule didn't change, what means that the
            # re-scheduling wasn't necessary and was e.g. caused
            # by a daily timer which doesn't count for today
            return

        room["current_schedule_temp"] = temp
        room["current_schedule_rule"] = rule

        if self.get_open_windows(room_name):
            self.log("--- [{}] Caching and not setting temperature due "
                     "to an open window.".format(room["friendly_name"]))
            room["wanted_temp"] = temp
        else:
            self.set_temp(room_name, temp, scheduled=True,
                          force_resend=force_resend)

    def set_manual_temp(self, room_name, temp_expr, force_resend=False,
                        reschedule_delay=None):
        """Sets the temperature in the given room. If the master switch
        is turned off, this won't do anything.
        If force_resend is True, and the temperature didn't
        change, it is sent to the thermostats anyway.
        An existing re-schedule timer is cancelled and a new one is
        started if re-schedule timers are configured. reschedule_delay,
        if given, overwrites the value configured for the room.
        In case of an open window, temperature is cached and not sent."""

        if not self.master_switch_enabled():
            return

        room = self.cfg["rooms"][room_name]
        result = self.eval_temp_expr(temp_expr, room_name)
        self.log("--- [{}] Evaluated temperature expression {} "
                 "to {}."
                 .format(room["friendly_name"], repr(temp_expr),
                         repr(result)),
                 level="DEBUG")

        if isinstance(result, expr.IncludeSchedule):
            result = self.eval_schedule(room_name, result.schedule,
                                        self.datetime())
            if result is not None:
                result = result[0]

        if not isinstance(result, expr.Result):
            self.log("--- [{}] Ignoring temperature expression."
                     .format(room["friendly_name"]))
            return

        temp = result.temp

        if self.get_open_windows(room_name):
            self.log("--- [{}] Caching and not setting temperature due "
                     "to an open window.".format(room["friendly_name"]))
            room["wanted_temp"] = temp
        else:
            self.set_temp(room_name, temp, scheduled=False,
                          force_resend=force_resend)

        self.update_reschedule_timer(room_name,
                                     reschedule_delay=reschedule_delay)

    def eval_temp_expr(self, temp_expr, room_name):
        """This is a wrapper around expr.eval_temp_expr that adds the
        app object, the room name  and some helpers to the evaluation
        environment, as well as all configured
        temp_expression_modules. It also catches and logs any
        exception which is raised during evaluation. In this case,
        None is returned."""

        # use date/time provided by appdaemon to support time-traveling
        now = self.datetime()
        extra_env = {
            "app": self,
            "schedule_snippets": self.cfg["schedule_snippets"],
            "room_name": room_name,
            "now": now,
            "date": now.date(),
            "time": now.time(),
        }
        extra_env.update(self.temp_expression_modules)

        try:
            return expr.eval_temp_expr(temp_expr, extra_env=extra_env)
        except Exception as err:  # pylint: disable=broad-except
            self.error("!!! Error while evaluating temperature expression: "
                       "{}".format(repr(err)))

    @modifies_state
    def cancel_reschedule_timer(self, room_name):
        """Cancels the reschedule timer for the given room, if one
        exists. True is returned if a timer has been cancelled,
        False otherwise."""

        room = self.cfg["rooms"][room_name]

        try:
            timer = room.pop("reschedule_timer")
        except KeyError:
            return False

        self.log("--- [{}] Cancelling re-schedule timer."
                 .format(room["friendly_name"]),
                 level="DEBUG")
        self.cancel_timer(timer)
        return True

    def cancel_resend_timer(self, room_name, therm_name):
        """Cancel the resend timer for given room and thermostat name,
        if one exists."""

        room = self.cfg["rooms"][room_name]
        therm = room["thermostats"][therm_name]
        try:
            timer = therm.pop("resend_timer")
        except KeyError:
            pass
        else:
            self.cancel_timer(timer)
            self.log("--- [{}] Cancelled resend timer for {}."
                     .format(room["friendly_name"], therm_name),
                     level="DEBUG")

    def check_for_open_window(self, room_name):
        """Checks whether a window is open in the given room and,
        if so, turns the heating off there. The value stored in
        room["wanted_temp"] is restored after the heating
        has been turned off. It returns True if a window is open,
        False otherwise."""

        room = self.cfg["rooms"][room_name]
        if self.get_open_windows(room_name):
            # window is open, turn heating off
            orig_temp = room["wanted_temp"]
            off_temp = self.cfg["off_temp"]
            if orig_temp != off_temp:
                self.log("<-- [{}] Turning heating off due to an open "
                         "window.".format(room["friendly_name"]))
                self.set_temp(room_name, off_temp, scheduled=False)
                room["wanted_temp"] = orig_temp
            return True
        return False

    def window_open(self, room_name, sensor_name):
        """Returns True if the given sensor in the given room reports open,
        False otherwise."""

        sensor = self.cfg["rooms"][room_name]["window_sensors"][sensor_name]
        open_state = sensor["open_state"]
        states = []
        if isinstance(open_state, list):
            states.extend(open_state)
        else:
            states.append(open_state)
        return self.get_state(sensor_name) in states

    def get_open_windows(self, room_name):
        """Returns a list of windo sensors in the given room which
        currently report to be open,"""

        _open = filter(lambda sensor: self.window_open(room_name, sensor),
                       self.cfg["rooms"][room_name]["window_sensors"])
        return list(_open)

    def master_switch_enabled(self):
        """Returns the state of the master switch or True if no master
        switch is configured."""
        master_switch = self.cfg["master_switch"]
        if master_switch:
            return self.get_state(master_switch) == "on"
        return True

    def publish_state(self):
        """Publishes Heaty's current state to AppDaemon for use by
        dashboards."""

        # shortcuts to make expr.Temp and datetime.time objects json
        # serializable
        unpack_temp = lambda t: t.value if isinstance(t, expr.Temp) else t
        unpack_time = lambda t: t.strftime(util.TIME_FORMAT) \
                      if isinstance(t, datetime.time) else None

        self.log("<-- Publishing state to AppDaemon.", level="DEBUG")

        attrs = {
            "heaty_id": self.cfg["heaty_id"],
            "master_switch_enabled": self.master_switch_enabled(),
        }

        rooms = {}
        for room_name, room in self.cfg["rooms"].items():
            schedule = room["schedule"]
            now = self.datetime()
            next_schedule_datetime = schedule.next_schedule_datetime(now)
            if next_schedule_datetime:
                next_schedule_time = next_schedule_datetime.time()
            else:
                next_schedule_time = None

            rooms[room_name] = {
                "friendly_name": room["friendly_name"],
                "wanted_temp": unpack_temp(room["wanted_temp"]),
                "current_schedule_temp":
                unpack_temp(room.get("current_schedule_temp")),
                "next_schedule_time": unpack_time(next_schedule_time),
            }

            thermostats = {}
            for therm_name, therm in room["thermostats"].items():
                thermostats[therm_name] = {
                    "current_temp": unpack_temp(therm["current_temp"]),
                    "resend_timer": bool(therm.get("resend_timer")),
                }
            rooms[room_name]["thermostats"] = thermostats

            open_windows = self.get_open_windows(room_name)
            window_sensors = {}
            for sensor_name in room["window_sensors"]:
                window_sensors[sensor_name] = {
                    "open": sensor_name in open_windows,
                }
            rooms[room_name]["window_sensors"] = window_sensors
        attrs["rooms"] = rooms

        entity_id = "appdaemon.heaty_{}".format(self.cfg["heaty_id"])
        state = {"state": None, "attributes": attrs}
        self.set_app_state(entity_id, state)

    def update_publish_state_timer(self):
        """Sets the publish_state timer to fire in 1 second, if not
        running already."""

        self.log("--- Called update_publish_state_timer.", level="DEBUG")

        if not self.publish_state_timer:
            timer = self.run_in(self.publish_state_timer_cb, 1)
            self.publish_state_timer = timer

    @modifies_state
    def update_reschedule_timer(self, room_name, reschedule_delay=None,
                                force=False):
        """This method cancels an existing re-schedule timer first.
        Then, it checks if either force is set or the wanted
        temperature in the given room differs from the scheduled
        temperature. If so, a new timer is created according to
        the room's settings. reschedule_delay, if given, overwrites
        the value configured for the room."""

        self.cancel_reschedule_timer(room_name)

        if not self.master_switch_enabled():
            return

        room = self.cfg["rooms"][room_name]

        if reschedule_delay is None:
            reschedule_delay = room["reschedule_delay"]

        wanted = room["wanted_temp"]
        result = self.get_scheduled_temp(room_name)
        if not reschedule_delay or \
           (not force and result and wanted == result[0]):
            return

        delta = datetime.timedelta(minutes=reschedule_delay)
        when = self.datetime() + delta
        self.log("--- [{}] Re-scheduling not before {} ({})."
                 .format(room["friendly_name"],
                         util.format_time(when.time()), delta))
        timer = self.run_at(self.reschedule_timer_cb, when,
                            room_name=room_name)
        room["reschedule_timer"] = timer
