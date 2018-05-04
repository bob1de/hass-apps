# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).


## Unreleased

### Fixed

### Security

### Added
* The ``heaty_id`` of the target instance can now be passed when emitting
  events from inside Home Assistant in order to let only one particular
  instance of Heaty receive the event, in case there is more than one
  running at the same time.

### Changed

### Deprecated

### Removed


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
