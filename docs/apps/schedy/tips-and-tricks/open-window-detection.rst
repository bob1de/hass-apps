Open Door or Window Detection
=============================

When using Schedy for heating control and you've got window sensors, you
might want to have the thermostats in a room turned off when a window
is opened. We can achieve this with a single additional schedule rule
and one automation in Home Assistant for an unlimited number of windows.

We assume that our window sensors are named
``binary_sensor.living_window_1`` and ``binary_sensor.living_window_2``
and report ``"on"`` as their state when the particular window is opened.

To make this solution scale to multiple windows in multiple rooms without
creating additional automations or rules, we add a new custom attribute
to our window sensors via the ``customize.yaml`` file that holds the
name of the Schedy room the sensor belongs to.

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

    - x: "Mark(OFF, Mark.OVERLAY) if not is_empty(filter_entities('binary_sensor', window_room=room_name, state='on')) else Skip()"

Now, we add an automation to re-evaluate the schedule when a window's
state changes. Replace ``schedy_heating`` with the name of your
instance of Schedy. In order to add more window sensors, just append
them to the ``entity_id`` list and set the ``window_room`` attribute in
``customize.yaml`` to the room the particular sensor belongs to.

::

    - alias: schedy heating open window detection
      trigger:
      - platform: state
        entity_id:
        - binary_sensor.living_window_1
        - binary_sensor.living_window_2
      condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
      action:
      - event: schedy_reschedule
        event_data_template:
          app_name: schedy_heating
          room: "{{ trigger.to_state.attributes['window_room'] }}"

That's it. Don't forget to restart Home Assistant after editing the files.
