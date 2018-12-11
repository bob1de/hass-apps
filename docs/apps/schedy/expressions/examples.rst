Examples
========

.. _schedy/expressions/examples/considering-the-state-of-entities:

Considering the State of Entities
---------------------------------

Let's say we use the thermostat actor type and have a switch
that should prepare our bathroom for taking a bath. It's name is
``switch.take_a_bath``. We write the following schedule for the room
``bathroom``.

::

    schedule:
    - x: 22 if is_on("switch.take_a_bath") else Skip()
    - v: 19

Last step is to write a simple Home Assistant automation to emit
a re-schedule event whenever the state of ``switch.take_a_bath``
changes. More about the available events and how to emit them is explained
in the chapter :doc:`../events`.

::

    - alias: "Re-schedule when switch.take_a_bath is toggled"
      trigger:
      - platform: state
        entity_id: switch.take_a_bath
      action:
      - event: schedy_reschedule
        event_data:
          app_name: <name of your schedy instance>
          room: bathroom

We're done! Now, whenever we toggle the ``take_a_bath`` switch, the
schedule is re-evaluated and our first schedule rule executes. The
rule is evaluating our custom expression, checking the state of the
``take_a_bath`` switch and, if it's enabled, causes the temperature to
be set to 22 degrees. However, if the switch is off, the rule is ignored
completely due to the ``Skip()`` we return in that case.

If that happens, the second rule is processed, which always evaluates
to 19 degrees.


Use of ``Add()`` and ``Skip()``
-------------------------------

This is a rule I once used in my own heating configuration at home:

::

    schedule_prepend:
    - x: Add(-3) if is_on("input_boolean.absent") else Skip()

What does this? Well, the first thing we see is that the rule is placed
inside the ``schedule_prepend`` section. That means, it is valid for
every room and always the first rule being evaluated.

I've defined an ``input_boolean`` called ``absent`` in Home
Assistant. Whenever I leave the house, this gets enabled. If I return,
it's turned off again. In order for Schedy to notice the toggling, I
added an automation to Home Assistant which fires a ``schedy_reschedule``
event. How that can be done has already been shown above.

Now let's get back to the schedule rule. When it evaluates, it checks the
state of ``input_boolean.absent``. If the switch is turned on, it
evaluates to ``Add(-3)``, otherwise to ``Skip()``.

As you know from above, ``Add(-3)`` is no final result yet. Think of it
as a temporary value that is remembered and used later.

Now, my regular schedule starts being evaluated, which, of course,
is different for every room. Rules are evaluated just as normal. If
one returns a result, that is used as the temperature and evaluation
stops. But wait, there was the ``Add(-3)``, wasn't it? Hence ``-3``
is now added to the final result.

With this minimal configuration effort, I added an useful away-mode
which throttles all thermostats in the house as soon as I leave.

Think of a device tracker that is able to report the distance between
you and your home. Having such one set up, you could even implement
dynamic throttling that slowly decreases as you near with almost zero
configuration effort.


Including Schedules Dynamically with ``IncludeSchedule()``
----------------------------------------------------------

The ``IncludeSchedule()`` result type for expressions can be used to
insert a set of schedule rules right at the position of the current
rule. This comes handy when a set of rules needs to be chosen depending
on the state of entities or is reused in multiple rooms.

.. note::

   If you just want to prevent yourself from repeating the same static
   constraints over and over for multiple consecutive rules that are used
   only once in your configuration, use the :ref:`sub-schedule feature
   <schedy/writing-schedules/rules-with-sub-schedules>` of the normal
   rule syntax instead.

You can reference any schedule defined under ``schedule_snippets`` in
the configuration, hence we create one to play with for our heating setup:

::

    schedule_snippets:
      summer:
      - { v: 20, start: "07:00", end: "22:00", weekdays: 1-5 }
      - { v: 20, start: "08:00", weekdays: 6-7 }
      - { v: 16 }

Now, we include the snippet into a room's schedule:

::

    schedule:
    - x: IncludeSchedule(schedule_snippets["summer"])
      months: 6-9
    - { v: 21, start: "07:00", end: "21:30", weekdays: 1-5 }
    - { v: 21, start: "08:00", end: "23:00", weekdays: 6-7 }
    - { v: 17 }

It turns out that you could have done the exact same without including
schedules by adding the ``months: 6-9`` constraint to all rules of the
summer snippet. But doing it this way makes the configuration a little
more readable.

However, you can also utilize the include functionality from inside
custom code. Just think of a function that selects different schedules
based on external criteria, such as weather sensors or presence detection.

.. note::

   Splitting up schedules doesn't bring any extra power to Schedy's
   scheduling capabilities, but it can make configurations much more
   readable as they grow.


What to Use ``Break()`` for
---------------------------

When in a sub-schedule, returning ``Break()`` from an expression will
skip the remaining rules of that sub-schedule and continue evaluation
after it. You can use it together with ``Skip()`` to create a conditional
sub-schedule, for instance.

::

    schedule:
    - v: 20
      rules:
      - x: Skip() if is_on("input_boolean.include_sub_schedule") else Break()
      - { start: "07:00", end: "09:00" }
      - { start: "12:00", end: "22:00" }
      - v: 17
     - v: "OFF"

The rules 2-4 of the sub-schedule will only be respected when
``input_boolean.include_sub_schedule`` is on. Otherwise, evaluation
continues with the last rule, setting the value to ``OFF`` (which only
exists with the thermostat actor type).

The actual definition of this result type is ``Break(levels=1)``,
which means that you may optionally pass a parameter called ``levels``
to ``Break()``. This parameter controls how many levels of nested
sub-schedules to break out of. The implicit default value ``1`` will
only abort the innermost sub-schedule (the one currently in). However,
you may want to directly abort its parent schedule as well by returning
``Break(2)``. In the above example, this would actually break the
top-level schedule and hence abort the entire schedule evaluation.

.. note::

   Returning ``Break()`` in the top-level schedule is equivalent to
   returning ``Abort()``.


What to Use ``Abort()`` for
---------------------------

The ``Abort`` return type is most useful for disabling Schedy's scheduling
mechanism depending on the state of entities. You might implement on/off
switches for disabling the schedules with it, like so:

::

    schedule_prepend:
    # global schedule on/off switch
    - x: Abort() if is_off("input_boolean.schedy") else Skip()
    # and, additionally, one per room
    - x: Abort() if is_off("input_boolean.schedy_room_" + room_name) else Skip()

As soon as ``Abort()`` is returned, schedule evaluation is aborted and
the value stays unchanged.
