Heaty
=====

A highly-configurable, comfortable to use Home Assistant / appdaemon app
that controls thermostats based on a schedule while still facilitating
manual intervention at any time.

These key features are implemented in Heaty. More are added continuously.

* Schedules (based on time, days of week/month, month, year)
* Separate schedule and settings for each room (multi-zone)
* Dynamic temperatures based on expressions written in Python
* Configurable re-scheduling after manual temperature adjustments
* Correction of inaccurate sensors by a per-thermostat delta
* Open window detection
* Re-sending until thermostat reports the change back (for unreliable networks)
* Master switch to turn off everything
* Logging
* Custom widgets for AppDaemon dashboards (WIP)

.. toctree::
   :caption: Contents:

   configuration
   writing-schedules
   temperature-expressions
   events


Using Heaty without schedules
-----------------------------

Schedules are not mandatory when using Heaty. It is perfectly valid to
use Heaty just for controlling temperatures in rooms manually while
still benefitting from other features like the open window detection.

To do so, just leave out everything that is related to schedules in
your ``apps.yaml``.
