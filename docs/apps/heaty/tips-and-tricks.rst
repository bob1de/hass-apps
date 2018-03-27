Tips & Tricks
=============

The purpose of this page is to collect useful configuration snippets
and tips for configuring Heaty in various (maybe not so common) usage
scenarios.


Using Heaty without schedules
-----------------------------

Schedules are not mandatory when using Heaty. It is perfectly valid to
use Heaty just for controlling temperatures in rooms manually while
still benefitting from other features like the open window detection.

To do so, just leave out everything that is related to schedules in
your ``apps.yaml``.


Using ordinary switches as thermostats
--------------------------------------

Sometimes users want to control ordinary on/off switches instead of
climate entities as thermostats. While it is clear that such devices
can't be set to a target temperature, they can be turned on and off by
Heaty with a little configuration effort.

The configuration for such a switch could look as follows:

::

    switch.some_heater:
      supports_temps: false
      opmode_heat_service: switch/turn_on
      opmode_off_service: switch/turn_off
      opmode_heat_service_attr: null
      opmode_off_service_attr: null
      opmode_state_attr: state
      opmode_heat: "on"
      opmode_off: "off"

As always, the detailled description of each setting can be found in
the sample configuration.
