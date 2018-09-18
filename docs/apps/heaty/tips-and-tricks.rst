Tips & Tricks
=============

The purpose of this page is to collect useful configuration snippets
and tips for configuring Heaty in various (maybe not so common) usage
scenarios.


Using Heaty without Schedules
-----------------------------

Schedules are not mandatory when using Heaty. It is perfectly valid to
use Heaty just for controlling temperatures in rooms manually while
still benefitting from other features like the open window detection.

To do so, just leave out everything that is related to schedules in
your ``apps.yaml``.


Using Ordinary Switches as Thermostats
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


Schedule Rules with Dynamic Start and End Times
-----------------------------------------------

The start and end time of a schedule rule are always static. They can't be
computed by something like temperature expressions at runtime. However,
there is a trick you can utilize in order to get start and end times
which are based on the state of entities in Home Assistant.

Let's assume you've got two entities, ``input_number.start_hour`` and
``input_number.end_hour``. Then you could write a schedule rule without
the ``start`` and ``end`` fields set, resulting in it always being valid.
As the value for ``v``, you configure a temperature expression like
the following:

::

    20 if time.hour >= float(state("input_number.start_hour")) and time.hour <= float(state("input_number.end_hour")) else Skip()

What this does is quite simple. It sets the temperature to 20 degrees
if the current hour is between the values configured by the two entities
we introduced. If it's not, the rule is ignored and processing continues
at the next rule, as always.

There is still one thing missing in order to make this work properly. You
need to notify Heaty about state changes of the used entities by firing
an event. How that's done is described at the end of `this example
<temperature-expressions.html#example-use-of-an-external-module>`_.

You could now make the temperature configurable via an
``input_number.day_temperature`` entity as well.

Now let's put this all together into a valid schedule rule:

::

    - v: state("input_number.day_temperature") if time.hour >= float(state("input_number.start_hour")) and time.hour <= float(state("input_number.end_hour")) else Skip()


Reacting to Changes of the Scheduled Temperature
------------------------------------------------

For each room, a sensor entity named
``sensor.heaty_<heaty_id>_room_<room_name>_scheduled_temp`` is created in
Home Assistant. This sensor will always hold the scheduled temperature
for the room. Reacting to changes of it's value is possible with normal
Home Assistant automations.
