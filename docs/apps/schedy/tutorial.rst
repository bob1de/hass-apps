Tutorial
========

In this tutorial, you'll learn how to set up a basic heating schedule with some cool
features using Schedy.

.. note::

   You are highly recommended to read the :doc:`chapter about Schedy's conception
   <concept>` before proceeding.

This tutorial's purpose is to get up and running quickly, which is why explanations
aren't very detailed here, but the individual sections tell you where to read more
about particular features.

.. contents::


Objective
---------

The goal is to have Schedy control thermostats in a flat with four rooms, a **living
room**, a **bedroom** and two **kids rooms**. In the living room, there are two
radiators, hence we've got two thermostats there.

In each room, there's a window with window sensor attached. We want the heatings
in the particular room to be turned off when a window is opened and the previous
setting be restored when it's closed again.

Furthermore, we make some enhancements to our schedules, allowing for dynamic schedule
switching and more. Stay tuned!


Configuration Skeleton
----------------------

Our first step is to create a basic configuration which defines our rooms and actors
and save it as ``schedy_heating.yaml`` in AppDaemon's ``apps`` directory::

    schedy_heating:  # This is our app instance name.
      module: hass_apps_loader
      class: SchedyApp

      actor_type: thermostat

      rooms:

        living:
          actors:
            climate.living_1:
            climate.living_2:
          schedule:

        bed:
          actors:
            climate.bed_1:
          schedule:

        kids1:
          actors:
            climate.kids1_1:
          schedule:

        kids2:
          actors:
            climate.kids2_1:
          schedule:

During the following steps, only configuration changes and additions are shown. A
full sample configuration like it looks after all steps have been applied can be
found at the :ref:`end of this tutorial <schedy/tutorial/final-config>`.

You may also want to consult the :doc:`full reference <configuration>` of all
available settings.


Reading the Log
---------------

Schedy uses AppDaemon's regular logging functionality to inform you about what's
going on. How to access these logs depends on the way you set up AppDaemon, but by
default they're just printed to stdout. Consult AppDaemon's documentation for details.

You'll need to watch the log often as you proceed with this tutorial, so make sure
you know how to do it.


Configuring Some Heating Times
------------------------------

Obviously, schedules are the most powerful part of Schedy. Unfortunately, that means
they can get a little complex when advanced features are used heavily. This tutorial
just configures simple heating times, but you may need to have a comprehensive look
at the :doc:`chapter about schedules <schedules/index>` at some point.

We want to keep it simple for now. During nights or when no other temperature has
been configured, the heating should be turned off in all rooms.

As schedules are evaluated rule by rule from top to bottom until a matching rule was
found, we create a new rule as fallback at the end of each room's schedule. But wait,
that would be redundant! Fortunately, there is the ``schedule_append`` section we
can use to append something to the schedules of all rooms at once. This goes into
our config::

    schedule_append:
    - v: "OFF"

Now, each room gets its own heating times.

1. Living room::

       schedule:
       # We set different heating times for weekdays and weekends.
       - { v: 20, start: "06:00", end: "07:30", weekdays: 1-5 }
       - { v: 20, start: "15:00", end: "22:30", weekdays: 1-5 }
       - { v: 20, start: "08:00", end: "23:30", weekdays: 6-7 }

2. Bedroom::

       schedule:
       # The bedroom should always have 14 degrees to sleep well in there.
       - v: 14

3. Kids rooms::

       # We use the exact same schedule for both kids1 and kids2.
       schedule:
       - { v: 20, start: "06:00", end: "07:30", weekdays: 1-5 }
       - { v: 20, start: "15:00", end: "19:00", weekdays: 1-5 }
       - { v: 20, start: "07:30", end: "20:00", weekdays: 6-7 }

Now save the configuration and watch your new schedules in action. You can play
with the times of some rules and change them back and forth to verify Schedy applies
everything correctly.


Grouping Similar Rules Into Sub-Schedules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The schedules we created so far work fine, but they are quite verbose and
contain some redundancy. Let's utilize a cool feature of Schedy to get rid
of that redundancy and make our rules more concise: :ref:`sub-schedules
<schedy/schedules/basics/rules-with-sub-schedules>`.

The only rooms this really makes sense for are the living room and the kids rooms,
as they contain multiple rules with common properties (like ``v`` and ``weekdays``).

1. Living room::

       schedule:
       - v: 20
         rules:
         - weekdays: 1-5
           rules:
           - { start: "06:00", end: "07:30" }
           - { start: "15:00", end: "22:30" }
         - weekdays: 6-7
           rules:
           - { start: "08:00", end: "23:30" }

2. Kids rooms::

       schedule:
       - v: 20
         rules:
         - weekdays: 1-5
           rules:
           - { start: "06:00", end: "07:30" }
           - { start: "15:00", end: "19:00" }
         - weekdays: 6-7
           rules:
           - { start: "07:30", end: "20:00" }

You see that the schedules didn't get shorter, but we now have a clear
hirarchy of rules and don't need to repeat ``v`` and ``weekdays`` over and over
anymore. Structuring your schedules this way is by no means required, but it does
increase readability and maintainability as your schedules get more complex. Some
sophisticated features can take even more advantage of sub-schedules, as you'll
see later.


Consolidating the Kids Rooms' Schedules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The schedules for both kids rooms are identical. It would be nice to
have the schedule only once. We use the :ref:`schedule snippets feature
<schedy/schedules/expressions/examples/includeschedule>` and create a schedule
snippet named ``"kids"``::

    schedule_snippets:
      kids:
      - v: 20
        rules:
        - weekdays: 1-5
          rules:
          - { start: "06:00", end: "07:30" }
          - { start: "15:00", end: "19:00" }
        - weekdays: 6-7
          rules:
          - { start: "07:30", end: "20:00" }

Now, we include that snippet in the schedules of the kids rooms::

    schedule:
    - x: "IncludeSchedule(schedule_snippets['kids'])"

Done!


Adding Window Sensors
---------------------

We're just following the :doc:`official guide for open window detection
<tips-and-tricks/open-window-detection>` here.

The rule which turns the heatings off when a window is open is placed in the
``schedule_prepend`` section::

    schedule_prepend:
    - x: "Mark(OFF, Mark.OVERLAY) if not is_empty(filter_entities('binary_sensor', state='on', window_room=room_name))"

Why that rule works as it does is explained in more detail in the guide linked above.

We now map our sensors to the rooms they belong to with help of ``customize.yaml``::

    binary_sensor.living_window_1:
      window_room: living
    binary_sensor.bed_window_1:
      window_room: bed
    binary_sensor.kids1_window_1:
      window_room: kids1
    binary_sensor.kids2_window_1:
      window_room: kids2

Adding more than one sensor per room would be very simple, as you can see.

Finally, we tell Schedy to re-evaluate the room's schedule when a sensor changes its
state. For that, we just add them to the ``watched_entities`` lists of the particular
rooms. Here is an example for ``living``, the others are analogous::

    watched_entities:
    - binary_sensor.living_window_1


Automatic Re-Scheduling After Manual Adjustments
------------------------------------------------

It would be cool to be able to change the temperature in a room unplanned and have
Schedy apply the regular schedule again after some period of time. For this purpose,
there is the ``rescheduling_delay`` setting that can be set per room.

Let's enable it in living room and bedroom and set it to two hours (120 minutes)::

    living:
      rescheduling_delay: 120
      # ...

    bed:
      rescheduling_delay: 120
      # ...


Stopping the Kids From Playing With the Thermostats
---------------------------------------------------

Our kids are still young and hit every button they can reach. Why not fix the
temperature in the kids rooms to what is dictated by the schedule? We disable
``allow_manual_changes`` and Schedy will revert any manual change as soon as it's
performed::

    kids1:
      allow_manual_changes: false
      # ...

    kids2:
      allow_manual_changes: false
      # ...


Switching Schedules as Needed
-----------------------------

Wouldnt it be nice to be able to switch the schedules when, for instance, we have
holidays and are home over the day? Nothing simpler than that with Schedy.

We add an ``input_select`` in Home Assistant::

    input_select:
      heating_mode:
        name: Heating Mode
        options:
        - Normal
        - Parents Home
        - All Home

Then, we adapt the schedules accordingly. The pattern we follow is :ref:`this one
<schedy/schedules/expressions/examples/conditional-sub-schedules>`, should you need
help understanding what's going on here.

1. Living room::

       schedule:
       - v: 20
         rules:
         - weekdays: 1-5
           rules:
           - rules:
             - x: "Skip() if state('input_select.heating_mode') == 'Normal' else Break()"
             - { start: "06:00", end: "07:30" }
             - { start: "15:00", end: "22:30" }
           - rules:
             - x: "Skip() if state('input_select.heating_mode') != 'Normal' else Break()"
             - { start: "08:00", end: "23:30" }
         - weekdays: 6-7
           rules:
           - { start: "08:00", end: "23:30" }

2. Kids rooms::

       schedule_snippets:
         kids:
         - v: 20
           rules:
           - weekdays: 1-5
             rules:
             - rules:
               - x: "Skip() if state('input_select.heating_mode') != 'All Home' else Break()"
               - { start: "06:00", end: "07:30" }
               - { start: "15:00", end: "19:00" }
             - rules:
               - x: "Skip() if state('input_select.heating_mode') == 'All Home' else Break()"
               - { start: "07:30", end: "20:00" }
           - weekdays: 6-7
             rules:
             - { start: "07:30", end: "20:00" }

Don't forget to add ``input_select.heating_mode`` to the list of entities watched
for state changes. Instead of adding it to all three concerned rooms, we simply add
it to the global list and have it count for all rooms::

    watched_entities:
    - input_select.heating_mode


Using ``expression_environment`` to Make Rules More Concise
-----------------------------------------------------------

We've got four schedule rules with expressions that all use
``state('input_select.heating_mode')`` to query the heating mode currently selected
from Home Assistant. This is quite repetitive and makes the rules long and unwieldy.

There is the ``expression_environment`` setting, which allows us to built custom Python
objects we can then use in all our rule expressions. We utilize this functionality
and create a new function, ``heating_mode()``::

    expression_environment: |
      def heating_mode():
          return state("input_select.heating_mode")

The individual rules then change to something like::

    - x: "Skip() if heating_mode() == 'All Home' else Break()"

The remaining ones are left to do for you.


.. _schedy/tutorial/final-config:

Final Configuration
-------------------

Here is the final outcome of our work as a full Schedy configuration.

::

    schedy_heating:  # This is our app instance name.
      module: hass_apps_loader
      class: SchedyApp

      actor_type: thermostat

      expression_environment: |
        def heating_mode():
            return state("input_select.heating_mode")

      schedule_snippets:
        kids:
        - v: 20
          rules:
          - weekdays: 1-5
            rules:
            - rules:
              - x: "Skip() if heating_mode() != 'All Home' else Break()"
              - { start: "06:00", end: "07:30" }
              - { start: "15:00", end: "19:00" }
            - rules:
              - x: "Skip() if heating_mode() == 'All Home' else Break()"
              - { start: "07:30", end: "20:00" }
          - weekdays: 6-7
            rules:
            - { start: "07:30", end: "20:00" }

      watched_entities:
      - input_select.heating_mode

      schedule_prepend:
      - x: "Mark(OFF, Mark.OVERLAY) if not is_empty(filter_entities('binary_sensor', state='on', window_room=room_name))"

      schedule_append:
      - v: "OFF"

      rooms:

        living:
          rescheduling_delay: 120
          actors:
            climate.living_1:
            climate.living_2:
          watched_entities:
          - binary_sensor.living_window_1
          schedule:
          - v: 20
            rules:
            - weekdays: 1-5
              rules:
              - rules:
                - x: "Skip() if heating_mode() == 'Normal' else Break()"
                - { start: "06:00", end: "07:30" }
                - { start: "15:00", end: "22:30" }
              - rules:
                - x: "Skip() if heating_mode() != 'Normal' else Break()"
                - { start: "08:00", end: "23:30" }
            - weekdays: 6-7
              rules:
              - { start: "08:00", end: "23:30" }

        bed:
          rescheduling_delay: 120
          actors:
            climate.bed_1:
          watched_entities:
          - binary_sensor.bed_window_1
          schedule:

        kids1:
          allow_manual_changes: false
          actors:
            climate.kids1_1:
          watched_entities:
          - binary_sensor.kids1_window_1
          schedule:
          - x: "IncludeSchedule(schedule_snippets['kids'])"

        kids2:
          allow_manual_changes: false
          actors:
            climate.kids2_1:
          watched_entities:
          - binary_sensor.kids2_window_1
          schedule:
          - x: "IncludeSchedule(schedule_snippets['kids'])"

And the Home Assistant part::

    customize:
      binary_sensor.living_window_1:
        window_room: living
      binary_sensor.bed_window_1:
        window_room: bed
      binary_sensor.kids1_window_1:
        window_room: kids1
      binary_sensor.kids2_window_1:
        window_room: kids2

    input_select:
      heating_mode:
        name: Heating Mode
        options:
        - Normal
        - Parents Home
        - All Home


Ok, And Now?
------------

Enjoy your new, powerful schedules! Consult the following chapters for more detailed
information on :doc:`creating advanced rules <schedules/index>`, :doc:`supported
actor types <actors/index>`, :doc:`events <events>` and :doc:`statistics collection
<statistics/index>`. The :doc:`tips-and-tricks/index` chapter may give you some more
inspiration after all.
