Open Door or Window Detection
=============================

When using Schedy for heating control and you've got window sensors, you
might want to have the thermostats in a room turned off when a window
is opened. We can achieve this with a single additional schedule rule
for an unlimited number of windows.

We assume that our window sensors for the ``living`` room are named
``binary_sensor.living_window_1`` and ``binary_sensor.living_window_2``
and report ``"on"`` as their state when the particular window is opened.

To make this solution scale to multiple windows in multiple rooms without
creating additional rules, we add a new custom attribute to our window
sensors via the ``customize.yaml`` file that holds the name of the Schedy
room the sensor belongs to.

::

    binary_sensor.living_window_1:
      window_room: living

    binary_sensor.living_window_2:
      window_room: living

Now, a new rule which overlais the temperature with ``OFF`` when a window
in the current room is open is added. We place it at the top of the
``schedule_prepend`` configuration section to have it applied to all
rooms as their first rule.

This code checks all ``binary_sensor`` entities found in Home Assistant
for a ``window_room`` attribute with the current room's name as its
value and a state of ``"on"``. This way it finds all window sensors of
the current room that report to be open. The ``is_empty()`` function is
used with the ``filter_entities()`` generator to have searching aborted as
soon as one open window is found rather than always checking all entities.
Feel free to break this single-line expression into multiple statements
if you prefer clarity over conciseness.

::

    - x: "Mark(OFF, Mark.OVERLAY) if not is_empty(filter_entities('binary_sensor', window_room=room_name, state='on')) else Next()"

Now, we add the window sensors to the ``watched_entities`` of the
``living`` room.

::

    watched_entities:
    - "binary_sensor.living_window_1"
    - "binary_sensor.living_window_2"

That's it. Don't forget to restart Home Assistant after editing
``customize.yaml``.
