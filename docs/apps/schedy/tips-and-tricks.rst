Tips & Tricks
=============

The purpose of this page is to collect useful configuration snippets and
tips for using Schedy in various (maybe not so common) usage scenarios.


Schedule Rules with Dynamic Start and End Times
-----------------------------------------------

The start and end time of a schedule rule are always static. They can't
be computed by something like expressions at runtime. However, there is
a trick you can utilize in order to get start and end times which are
based on the state of entities in Home Assistant.

Let's assume you've got two entities, ``input_number.start_hour`` and
``input_number.end_hour``. Then you could write a schedule rule without
the ``start`` and ``end`` fields set, resulting in it always being valid.
As the value for ``x``, you configure an expression like the following.

::

    "on" if time.hour >= float(state("input_number.start_hour")) and time.hour <= float(state("input_number.end_hour")) else Skip()

What this does is quite simple. It sets the value to "on" if the
current hour is between the values configured by the two entities we
introduced. If it's not, the rule is ignored and processing continues
at the next rule, as always.

There is still one thing missing in order to make this work properly. You
need to notify Schedy about state changes of the used entities by firing
an event. How that's done is described at the end of `this example
<expressions.html#example-inlining-expressions-into-schedules>`_.

You could now make the temperature configurable via an
``input_number.day_temperature`` entity as well.

Now let's put this all together into a valid schedule rule:

::

    - v: state("input_number.day_temperature") if time.hour >= float(state("input_number.start_hour")) and time.hour <= float(state("input_number.end_hour")) else Skip()


Reacting to Changes of the Scheduled Value
------------------------------------------

For each room, a sensor entity named ``sensor.schedy_<app name>_room_<room
name>_scheduled_value`` is created in Home Assistant. This sensor will
always hold the scheduled value for the room. Reacting to changes of
it's value is possible with normal Home Assistant automations.
