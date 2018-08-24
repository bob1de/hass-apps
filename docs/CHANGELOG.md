# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).


## Unreleased

### Fixed

### Security

### Added

### Changed

### Deprecated

### Removed


## 0.20180824.1

### Fixed
* Fixed appdaemon dependency to version >= 3.0.0.


## 0.20180824.0

### Changed
* heaty v0.16.0

### Removed
* Removed AppDaemon 2.x support.


## [0.20180801.0] - 2018-08-01
[0.20180801.0]: https://github.com/efficiosoft/hass-apps/compare/v0.20180707.0...v0.20180801.0

### Added
* Added a script that automates the installation process and can be run
  with just one single command. See
  [here](getting-started.html#auto-install-assistant) for more
  information.

### Changed
* heaty v0.15.0

### Deprecated
* AppDaemon 2.x support will be dropped in a late August 2018
  release. Please switch to AppDaemon 3.x.


## [0.20180707.0] - 2018-07-07
[0.20180707.0]: https://github.com/efficiosoft/hass-apps/compare/v0.20180405.0...v0.20180707.0

### Changed
* heaty v0.14.0
* No longer using broken ``set_app_state()`` feature of AppDaemon, hence
  AppDaemon 3.0.0+ should now work and blacklisting has been removed.

### Deprecated
* AppDaemon 2.x support will be dropped in a late August 2018
  release. Please switch to AppDaemon 3.x.


## [0.20180405.0] - 2018-04-05
[0.20180405.0]: https://github.com/efficiosoft/hass-apps/compare/v0.20180325.0...v0.20180405.0

### Changed
* heaty v0.13.0


## [0.20180325.0] - 2018-03-25
[0.20180325.0]: https://github.com/efficiosoft/hass-apps/compare/v0.20180310.1...v0.20180325.0

### Fixed
* Fixed wrong path to sample configuration files in docs/apps/index.rst.

### Added
* Blacklisted AppDaemon version 3.0.0 in requirements. (#12)

### Changed
* heaty v0.12.4


## [0.20180310.1] - 2018-03-10
[0.20180310.1]: https://github.com/efficiosoft/hass_apps/compare/v0.20180310.0...v0.20180310.1

### Changed
* Fixed old project name in setup.py left over by mistake.


## [0.20180310.0] - 2018-03-10
[0.20180310.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180307.0...v0.20180310.0

### Changed
* heaty v0.12.3
* Switched project name from hass_apps to hass-apps


## [0.20180307.0] - 2018-03-07
[0.20180307.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180305.0...v0.20180307.0

### Changed
* heaty v0.12.2


## [0.20180305.0] - 2018-03-05
[0.20180305.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180302.0...v0.20180305.0

### Changed
* heaty v0.12.1


## [0.20180302.0] - 2018-03-02
[0.20180302.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180221.0...v0.20180302.0

### Changed
* heaty v0.12.0
* Require voluptuous >= 0.11.1.
* It is now strongly recommended to install in a separate virtualenv to
  avoid conflicts in versions of dependency packages that are needed by
  both hass_apps and Home Assistant. The Getting started section has
  been updated accordingly.


## [0.20180221.0] - 2018-02-21
[0.20180221.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180218.0...v0.20180221.0

### Changed
* motion_light v0.1.1
* Ported docs, sample configurations and changelogs to sphinx +
  readthedocs.org.


## [0.20180218.0] - 2018-02-18
[0.20180218.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180209.0...v0.20180218.0

### Changed
* heaty v0.11.0


## [0.20180209.0] - 2018-02-09
[0.20180209.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180205.2...v0.20180209.0

### Changed
* heaty v0.10.2


## [0.20180205.2] - 2018-02-05
[0.20180205.2]: https://github.com/efficiosoft/hass_apps/compare/v0.20180205.1...v0.20180205.2

### Fixed
* Fixed wrong AppDaemon version in requirements.


## [0.20180205.1] - 2018-02-05
[0.20180205.1]: https://github.com/efficiosoft/hass_apps/compare/v0.20180205.0...v0.20180205.1

### Changed
* heaty v0.10.1


## [0.20180205.0] - 2018-02-05
[0.20180205.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180203.0...v0.20180205.0

### Fixed
* Added missing release dates to CHANGELOG.md

### Added
* Added CHANGELOG.md and LICENSE to Python source package.
* Added appdaemon 3 support alongside the old appdaemon 2

### Changed
* heaty v0.10.0


## [0.20180203.0] - 2018-02-03
[0.20180203.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180202.1...v0.20180203.0

### Changed
* heaty v0.9.4


## [0.20180202.1] - 2018-02-02
[0.20180202.1]: https://github.com/efficiosoft/hass_apps/compare/v0.20180202.0...v0.20180202.1

### Changed
* heaty v0.9.3


## [0.20180202.0] - 2018-02-02
[0.20180202.0]: https://github.com/efficiosoft/hass_apps/compare/v0.20180201.0...v0.20180202.0

### Changed
* heaty v0.9.2


## 0.20180201.0 - 2018-02-01

### Added
- Begin using CHANGELOG.md
