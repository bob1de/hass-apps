Events
======

Heaty introduces two new events it listens to:

* ``heaty_reschedule``: Trigger a re-scheduling of the temperature.
  Parameters are:

  * ``room_name``: the name of the room to re-schedule as defined in Heaty's configuration (not the ``friendly_name``) (optional, default: ``null``, which means all rooms)

* ``heaty_set_temp``: Sets a given temperature in a room.
  Parameters are:

  * ``room_name``: the name of the room as defined in Heaty's configuration (not the ``friendly_name``)
  * ``temp``: a temperature expression
  * ``force_resend``: whether to re-send the temperature to the thermostats even if it hasn't changed due to Heaty's records (optional, default: ``false``)
  * ``reschedule_delay``: a number of minutes after which Heaty should automatically switch back to the schedule (optional, default: the ``reschedule_delay`` set in Heaty's configuration for the particular room)

You can emit these events from your custom Home Assistant automations
or scripts in order to control Heaty's behaviour.

This is an example Home Assistant script that turns the heating in the
room named ``living`` to ``25.0`` degrees and switches back to the
regular schedule after one hour:

::

    - alias: Hot for one hour
      sequence:
      - event: heaty_set_temp
        event_data:
          room_name: living
          temp: 25.0
          reschedule_delay: 60
