# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).


## Unreleased

### Fixed
* All expressions of schedule rules specified in the YAML configuration
  should be enclosed in quotes to force the parser to treat them as
  strings. A note has been added to the documentation and all examples
  were updated accordingly.

### Security

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

### Removed


## 0.1.1 - 2018-12-11

### Changed
* Lowered delay after which a schedy_reschedule event is processed from
  3 to 1 second.


## 0.1.0 - 2018-12-09

### Added
* Initial release.
