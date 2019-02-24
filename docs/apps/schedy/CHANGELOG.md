# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).


## Unreleased

### Fixed

### Security

### Added

### Changed

### Deprecated

### Removed


## 0.4.0 - 2019-02-24

### Fixed
* Fixed name of ``value_parameter`` setting for generic actor in docs.
* Schedules were re-evaluated when the value of a not watched attribute
  of a watched entity changes.

### Added
* Added new result marker ``OVERLAY_REVERT_ON_NO_RESULT`` to cancel an
  overlay when the schedule produces no result.
* Result markers can now be added by postprocessors as well.

### Changed
* The wanted value of a room is not sent to actors at startup when
  ``replicate_changes`` has been disabled in the room's configuration.

### Removed
* The old name ``schedy_reschedule`` for the ``schedy_reevaluate``
  event has been removed.


## 0.3.0 - 2019-01-05

### Fixed
* It's no longer possible to create cycles when including schedules. The
  backwards resolution of rule values still works, it just treats
  ``IncludeSchedule()`` results for schedules already on the stack as
  if they were ``Inherit()`` and hence ignores them.
* The ``filter_entities()`` state helper returned no entities in certain
  cases.

### Added
* Schedy can now re-evaluate schedules automatically when the state of
  entities changes. See the new ``watched_entities`` settings.
* Range specifications for constraints can now be inverted by prepending
  them with ``!``.
* Added the ``Inherit()`` result type to inherit the parent rule's
  value. ``None`` will continue to work as well, but ``Inherit()``
  is more explanatory and thus preferred.
* When an expression fails to evaluate, the traceback is now logged.

### Changed
* Various small improvements of the examples for using expressions.
* The ``schedy_reschedule`` event has been renamed to
  ``schedy_reevaluate``. The old name will cease to work in version 0.4.
* The documentation for writing schedules has been restructured.

### Deprecated
* 0.4: The old name ``schedy_reschedule`` for the ``schedy_reevaluate``
  event will be removed.

### Removed
* The old name ``Negate`` for the ``Invert`` postprocessor has been
  removed.
* The ``And`` and ``Or`` postprocessors habe been removed. Use the generic
  ``Postprocess`` instead.


## 0.2.0 - 2018-12-23

**Merry Christmas to all users of hass-apps! Thank you for putting your
trust in Schedy.**

### Fixed
* All expressions of schedule rules specified in the YAML configuration
  should be enclosed in quotes to force the parser to treat them as
  strings. A note has been added to the documentation and all examples
  were updated accordingly.

### Added
* Added the ``Postprocess`` postprocessor that can be used to post-process
  the scheduling result in a completely custom way.

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
* The generic actor has been reworked to support controlling multiple
  attributes at once. Its configuration schema has changed as well, so
  please consult the documentation for migrating.
* Preliminary results are now called postprocessors. Syntax and names
  stay unchanged.
* The ``Negate`` postprocessor has been renamed to ``Invert``. The old
  name will cease to work in version 0.3.

### Deprecated
* 0.3: The old name ``Negate`` for the ``Invert`` postprocessor will
  be removed.
* 0.3: The ``And`` and ``Or`` postprocessors will be removed. Use the
  generic ``Postprocess`` instead.


## 0.1.1 - 2018-12-11

### Changed
* Lowered delay after which a schedy_reschedule event is processed from
  3 to 1 second.


## 0.1.0 - 2018-12-09

### Added
* Initial release.
