Heaty
=====

A highly-configurable, comfortable to use Home Assistant / appdaemon app
that controls thermostats based on a schedule while still facilitating
manual intervention at any time.

**Note:**
Heaty is still a young piece of software which likely contains some bugs.
Please keep that in mind when using it. Bug reports and suggestions are
always welcome. Use the GitHub Issues for this sort of feedback.


Features
--------

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


Using Heaty without schedules
-----------------------------

Schedules are not mandatory when using Heaty. It is perfectly valid to
use Heaty just for controlling temperatures in rooms manually while
still benefitting from other features like the open window detection.

To do so, just leave out everything that is related to schedules in
your ``apps.yaml``.


.. toctree::
   :hidden:

   writing-schedules
   temperature-expressions
   events
