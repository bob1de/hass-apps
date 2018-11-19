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


.. _schedy/tips-and-tricks/open-door-or-window-detection:

Open Door or Window Detection
-----------------------------

When using Schedy for heating control and you've got window sensors, you
might want to have the thermostats in a room turned off when a window
is opened. We can achieve this with a single additional schedule rule
and one automation in Home Assistant for an unlimited number of windows.

We assume that our window sensors are named
``binary_sensor.living_window`` and ``binary_sensor.kids_window`` and
report ``"on"`` as their state when the particular window is opened.

To make this solution scale to multiple windows in multiple rooms without
creating additional automations or rules, we add a new custom attribute
to our window sensors via the ``customize.yaml`` file that holds the
name of the Schedy room the sensor belongs to.

::

    binary_sensor.living_window:
      window_room: living

    binary_sensor.kids_window:
      window_room: kids

Now, a new rule which overlais the temperature with ``OFF`` when a window
in the current room is open is added. We place it at the top of the
``schedule_prepend`` configuration section to have it applied to all
rooms as their first rule.
This code checks all ``binary_sensor`` entities found in Home Assistant
for a ``window_room`` attribute and, if present, compares the value
of that attribute to the name of the room for which the expression is
evaluated. This way it finds all window sensors for the current room
and can check whether one of them reports to be open.

::

    - x: |
        for s in state("binary_sensor"):
            if state(s, attribute="window_room") == room_name and is_on(s):
                result = Mark(OFF, Mark.OVERLAY)
                break
        else:
            result = Skip()

Now, we add an automation to re-evaluate the schedule when a window's
state changes. Replace ``schedy_heating`` with the name of your
instance of Schedy. In order to add more window sensors, just append
them to the ``entity_id`` list and set the ``window_room`` attribute in
``customize.yaml``.

::

    - alias: schedy heating open window detection
      trigger:
      - platform: state
        entity_id:
        - binary_sensor.living_window
        - binary_sensor.kids_window
      condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
      action:
      - event: schedy_reschedule
        event_data_template:
          app_name: schedy_heating
          room: "{{ trigger.to_state.attributes['window_room'] }}"

That's it. Don't forget to restart Home Assistant after editing the files.
