Events
======

Heaty introduces two new events it listens for:

* ``heaty_reschedule``: Trigger a re-scheduling of the temperature.
  Parameters are:

  * ``room_name``: the name of the room to re-schedule as defined in
    Heaty's configuration (not the ``friendly_name``) (default: ``null``,
    which means all rooms)
  * ``cancel_running_timer``: When there is a re-schedule timer
    running already, Heaty delays the re-scheduling until that timer goes
    off. Set this parameter to ``true`` to cancel a potential timer and
    re-schedule immediately instead. (default: ``false``)

* ``heaty_set_temp``: Sets a given temperature in a room.
  Parameters are:

  * ``room_name``: the name of the room as defined in Heaty's
    configuration (not the ``friendly_name``)
  * ``temp``: a temperature expression
  * ``force_resend``: whether to re-send the temperature to the
    thermostats even if it hasn't changed due to Heaty's records (default:
    ``false``)
  * ``reschedule_delay``: a number of minutes after which Heaty should
    automatically switch back to the schedule (default: the
    ``reschedule_delay`` set in Heaty's configuration for the particular
    room)

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

In case you run multiple instances of Heaty in parallel, a ``heaty_id``
attribute can be added to the event's data in order to let only one
particular instance receive the event. When no ``heaty_id`` is specified,
all running instances will react to the event.
