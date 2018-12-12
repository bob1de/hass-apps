# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).


## Unreleased

### Fixed

### Security

### Added

### Changed
* The rules configured as ``schedule_prepend``, the individual room's
  schedule and those configured as ``schedule_append`` are now combined
  into the final room's schedule as three separate sub-schedules. This
  implies that ``Break()``, when returned from the top level, will
  now only break the individual section of the schedule it stands
  in. ``Break()`` in a ``schedule_prepend`` section will e.g. only cause
  the remaining rules of the ``schedule_prepend`` section to be skipped
  and continue with the individual room's schedule. Use ``Abort()``
  (recommended) or ``Break(2)`` to achieve the old behaviour.

### Deprecated

### Removed


## 0.1.1 - 2018-12-11

### Changed
* Lowered delay after which a schedy_reschedule event is processed from
  3 to 1 second.


## 0.1.0 - 2018-12-09

### Added
* Initial release.
