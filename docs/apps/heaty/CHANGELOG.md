# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).


## Unreleased

### Fixed

### Security

### Added
* Added a result type for temperature expressions called ``Abort()``
  which has the same effect ``Break()`` had until now.
* For each room, a sensor entity named
  ``sensor.heaty_<heaty_id>_room_<room_name>_scheduled_temp`` gets
  created in Home Assistant. This sensor's state is updated with the
  scheduled temperature whenever it changes.
* Added a new boolean configuration option ``reschedule_at_startup``
  which defaults to ``true``. When it's disabled and Heaty starts,
  the scheduled temperature won't be applied until the next time the
  result of schedule evaluation changes.
* Added a per thermostat setting named ``off_temp`` to allow overwriting
  the value to send for ``OFF``.

### Changed
* The ``Break()`` result type for temperature expressions now only
  breaks the innermost sub-schedule, unless a value greater than ``1``
  is passed as its ``levels`` parameter. See the docs for a thorough
  description.
* At startup, Heaty now fetches the last known scheduled temperatures
  from the ``..._scheduled_temp`` sensor entities it created before. This
  has the effect that thermostats which have been changed manually aren't
  forced back to the schedule when AppDaemon is restarted.
* The ``temp`` parameter of schedule rule definitionss has been renamed
  to ``value`` with the shortcut ``v``. The previous name will continue
  to work until 0.18.0.
* The ``temp`` parameter of the ``heaty_set_temp`` event has been renamed
  to ``value`` with the shortcut ``v``. The previous name will continue
  to work until 0.18.0.

### Deprecated
* 0.18.0: The previous name ``temp`` for the ``value`` parameter of
  schedule rule definitions will be removed.
* 0.18.0: The previous name ``temp`` for the ``value`` parameter of the
  ``heaty_set_temp`` event will be removed.

### Removed
* Removed the ``SkipSubSchedule()`` result type for temperature
  expressions. It's purpose is now covered by the enhanced ``Break()``.


## 0.16.0 - 2018-08-24

### Added
* Temperature expressions of rules in sub-schedules may now return
  ``None``, which causes the next anchestor rule's ``temp`` value to
  be used instead. Read the docs to learn how this can help you with
  schedule creation.
* Added a plausibility check for the ``current_temp_state_attr``
  thermostat config parameter.

### Changed
* When the end time of a schedule rule is prior or equal to its start
  time, ``end_plus_days`` now gets increased by ``1``,no matter what it
  has been set to explicitly. The magical incrementing when ``end`` was
  unset is now gone. The docs have been updated accordingly.

### Removed
* The former name ``Ignore`` for the temperature expression result type
  now called ``Skip`` has been removed.


## 0.15.0 - 2018-08-01

### Fixed
* Added documentation for the ``current_temp_state_attr`` option to the
  sample configuration file.

### Added
* The ``current_temp_state_attr`` option can now be set to ``null``
  in order to disable fetching of current temperature completely.
* Added a new special result type called ``SkipSubSchedule`` for
  temperature expressions of rules that have sub-schedules attached
  to them.
* Schedule rules got a new optional ``name`` parameter to make them
  easily recognizable in logs.

### Changed
* Changed the default values of ``opmode_heat`` and ``opmode_off``
  to lower-case ``"heat"`` and ``"off"``, respectively, since Home
  Assistant 0.73 seems to have unified them.
* Changed the name of the ``Ignore`` result type for temperature
  expressions to ``Skip`` to be more meaningful. Its behaviour
  stays unchanged. The old name will continue to work for now.

### Deprecated
* 0.16.0: The former name ``Ignore`` for the ``Skip`` result type,
  which is still provided as a fallback, will be removed.


## 0.14.0 - 2018-07-07

### Fixed
* Fixed a bug that caused unnecessary re-sending of commands to ordinary
  switches that don't support setting a target temperature.

### Added
* The ``heaty_id`` of the target instance can now be passed when emitting
  events from inside Home Assistant in order to let only one particular
  instance of Heaty receive the event, in case there is more than one
  running at the same time.
* It is now possible to optionally specify seconds for ``start`` and
  ``end`` times in schedule rules in addition to hours and minutes. The
  format is HH:MM:SS. However, the known HH:MM will still work as before
  and imply a value of 00 for seconds.
* New helper functions have been added to the evaluation environment of
  time expressions for convenience:
  * ``state(entity_id)``: a shortcut for ``app.get_state(entity_id)``
  * ``is_on(entity_id)``: returns ``True`` if the state of the given entity
    is ``"on"`` (case-insensitive)
  * ``is_off(entity_id)``: returns ``True`` if the state of the given entity
    is ``"off"`` (case-insensitive)
* A new configuration option ``window_open_temp`` has been added with a
  default of ``OFF`` to configure the temperature that should be set
  when a window is opened.
* A new component for collecting statistics has been added. With so-called
  statistical zones, it is possible to get some statistics reported
  back to Home Assistant, where one could then react to changing
  parameters of your heating system with simple automationss.
  ([more information](statistics.html))
* Thermostats now have a ``current_temp_state_attr`` setting which
  defaults to ``"current_temperature"``. This specifies a state attribute
  used to fetch the real temperature as measured by the thermostat's
  temperature sensor. This data is used by the new statistics component.
* Schedule rules may now have a set of sub-rules. The sub-rules are only
  evaluated when the constraints of the parent rule passed before,
  so this can be used to group rules with equal or partially equal
  constraints together. The rule list goes into the ``rules`` parameter
  of the parent rule. The ``temp`` parameter has to be specified in the
  parent rule or in all child rules.
* Added a ``cancel_running_timer`` parameter to the ``heaty_reschedule``
  event. ([more information](events.html))

### Changed
* If the ``end`` time of a schedule rule is equal or prior to its
  ``start`` time and ``end_plus_days`` hasn't been set, ``end_plus_days:
  1`` is now assumed automatically.
* Whenever a room, thermostat etc. is mentioned in a log message, it
  now has a prefix that indicates the type of object it is. "R:Living"
  would, for instance, represent the room named "Living".
* The configuration option ``off_temp`` has been renamed to
  ``master_off_temp`` to be more meaningful.
* The thermostat configuration options ``temp_service``,
  ``temp_service_attr`` and ``temp_state_attr`` have been renamed
  to ``target_temp_service``, ``target_temp_service_attr`` and
  ``target_temp_state_attr`` to be more meaningful.
* Open window detection now sets the temperature to the value configured
  by the new ``window_open_temp`` option instead of using the value of
  ``master_off_temp`` (formerly ``off_temp``).
* The ``heaty_reschedule`` event now only triggers a re-scheduling
  when there is no re-schedule timer running already. In order to get
  the previous behaviour, specify ``cancel_running_timer: true`` in the
  event data explicitly. ([more information](events.html))

### Removed
* Removed experimental state publishing to AppDaemon because the
  implementation was nasty and it wasn't used anyway.


## 0.13.0 - 2018-04-05

### Added
* Added ``max_temp`` setting for thermostats. (#14)
* Added ``supports_temps`` setting for thermostats which don't support
  setpoints. (#15)
* Added support for ordinary switches that are no climate entities. (#16)

### Changed
* The known thermostat settings ``opmode_service`` and
  ``opmode_service_attr`` were split up into ``opmode_heat_service``,
  ``opmode_off_service``, ``opmode_heat_service_attr`` and
  ``opmode_off_service_attr``. The default values remain the same. More
  info can be found in #16.


## 0.12.4 - 2018-03-25

### Fixed
* Schedule snippets now get compiled again. (#13)

### Added
* Support for different time formats (07:40 = 7:40) (#9)


## 0.12.3 - 2018-03-10

### Added
* Added section about prerequisites to docs.


## 0.12.2 - 2018-03-07

### Fixed
* Fixed a bug that prevented the temperature from being restored after
  window has been closed. (#8)


## 0.12.1 - 2018-03-05

### Fixed
* Omitting ``off_temp`` in the configuration works again. (#7)


## 0.12.0 - 2018-03-02

### Fixed
* Fixed a bug which let state publishing fail on AppDaemon 3.

### Added
* Thermostats and window sensors can now also have friendly names.

### Changed
* Improved code quality:
  * Restructured Heaty into submodules.
  * Added type-hints
  * Substantial parts of Heaty's core have been rewritten.


## 0.11.0 - 2018-02-18

### Added
* Added plausibility checks pointing the user to possible mistakes in
  the configuration by warning messages during initialization of Heaty.
* Added support for thermostats that don't support operation modes via
  the new per-thermostat ``supports_opmodes`` config flag.

### Changed
* If the ``end`` time of a schedule rule is before its ``start`` time
  and ``end_plus_days`` hasn't been set, ``end_plus_days: 1`` is now
  assumed automatically.
* Added compatibility with appdaemon 3.0.0b3 and removed compatibility
  with 3.0.0b2.


## 0.10.2 - 2018-02-09

### Fixed
* Fixed error when turning master switch off due to a wrong default
  value for off_temp.
* Fixed race condition when switching back to previous temperature before
  the thermostat reported the last change back.

### Changed
* Default value for ``off_temp`` (``"OFF"``) is now upper-case for
  consistency reasons, lower-case ``"off"`` will still work.


## 0.10.1 - 2018-02-05

### Fixed
* Fixed issue that lead to endless re-sending with AppDaemon 3.
* thermostat_defaults and window_sensor_defaults are now handled correctly.


## 0.10.0 - 2018-02-05

### Added
* Added appdaemon 3 support alongside the old appdaemon 2


## 0.9.4 - 2018-02-03

### Added
* Added ``start_date`` and ``end_date`` constraints for schedule rules.


## 0.9.3 - 2018-02-02

### Fixed
* Fixed wrong version number


## 0.9.2 - 2018-02-02

### Fixed
* Fixed error when not setting ``schedule:``, ``schedule_prepend:`` and
  ``schedule_append:`` due to voluptuous not validating default values.


## 0.9.1 - 2018-02-01

### Added
- Begin using CHANGELOG.md
