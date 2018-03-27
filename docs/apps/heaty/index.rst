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
   :maxdepth: 1

   configuration
   writing-schedules
   temperature-expressions
   events
   tips-and-tricks
   CHANGELOG


What can Heaty do, and what not?
--------------------------------

Often, people ask me whether Heaty can be used with their particular
heating setup. I always tend to repeat myself in these situations,
hence I want to explain here what the exact preconditions for using
Heaty actually are.

1. Heaty controls so-called rooms. However, a room doesn't have to be
   a real room inside of a building. Think of it as a zone in which the
   temperature should be the same everywhere.

2. You need at least one thermostat in each room you want to control.
   Such a thermostat must be recognized as a climate entity in Home
   Assistant, and setting the target temperature from the Home Assistant
   web interface should work reliably. Wall thermostats can be controlled
   the same way as radiator thermostats, as long as they fulfill these
   conditions as well. If you only have a switchable heater and an
   external temperature sensor, have a look at Home Assistant's `Generic
   Thermostat platform`_ to build a virtual thermostat first.

3. If your thermostat is used for both heating and cooling, there has
   to be an automatic operation mode which does heating/cooling based
   on the difference between current and target temperature. Heaty
   will only switch the operation mode between on and off (exact names
   can be configured) and set the target temperature according to the
   configured schedule.

4. Optionally, each room can have multiple door/window sensors
   configured. Opening a window will then turn off all thermostats in
   the particular room.

5. Heaty doesn't care about where your heating energy comes from. Whether
   that's a gas, oil, wood or solid fuel oven, solar energy or something
   fancy doesn't matter. This implies that Heaty won't control the energy
   source in any way. Especially, it won't turn the oven off when there
   is no radiator needing energy. Although doing so wouldn't be to easy
   depending on the energy source, I might implement such a feature in
   the future.

.. _`Generic Thermostat platform`: https://home-assistant.io/components/climate.generic_thermostat/

If you are happy with all these points and your setup fulfills them,
there should be nothing stopping you from integrating Heaty's great
scheduling capabilities into your home. If you have questions going
beyond what's explained above, feel free to ask.
