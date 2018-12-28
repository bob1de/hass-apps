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
    - x: "22 if is_on('switch.take_a_bath') else Skip()"
    - v: 19

Last step is to tell Schedy to watch for changes of the state of
``switch.take_a_bath``, so that it can re-evaluate the schedule of the
bathroom when the switch is toggled. We add the following to the room's configuration:

::

    watched_entities:
    - "switch.take_a_bath"

We're done! Now, whenever we toggle the ``take_a_bath`` switch, the
schedule is re-evaluated and our first schedule rule executes. The
rule is evaluating our custom expression, checking the state of the
``take_a_bath`` switch and, if it's enabled, causes the temperature to
be set to 22 degrees. However, if the switch is off, the rule is ignored
completely due to the ``Skip()`` we return in that case and the second
rule is processed, which always evaluates to 19 degrees.

What's so nice about these ``... if ... else ...`` expressions in Python
is that they're almost always self-explanatory. We'll use them extensively
in the following examples.


Use of ``Add()`` and ``Skip()``
-------------------------------

This is something I once used in my own heating configuration at home:

::

    schedule_prepend:
    - x: "Add(-3) if is_on('input_boolean.absent') else Skip()"
    watched_entities:
    - "input_boolean.absent"

What does this? Well, the first thing we see is that the rule is placed
inside the ``schedule_prepend`` section. That means, it is valid for
every room and always the first rule being evaluated.

I've defined an ``input_boolean`` called ``absent`` in Home
Assistant. Whenever I leave the house, this gets enabled. If I return,
it's turned off again. In order for Schedy to notice the toggling, I
added it to the global ``watched_entities`` configuration.

Now let's get back to the schedule rule. When it evaluates, it checks the
state of ``input_boolean.absent``. If the switch is turned on, it
evaluates to ``Add(-3)``, otherwise to ``Skip()``.

``Add(-3)`` is a so-called :doc:`postprocessor <postprocessors>`. Think
of it as a temporary value that is remembered and used later, after a
real result was found.

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
      vacation:
      - { v: 21, start: "08:30", end: "23:00" }
      - { v: 16 }

Now, we include the snippet into a room's schedule:

::

    schedule:
    - x: "IncludeSchedule(schedule_snippets['vacation']) if is_on('input_boolean.vacation') else Skip()"
    # when not in vacation mode, have the normal per-room schedule
    - { v: 21, start: "07:00", end: "21:30", weekdays: 1-5 }
    - { v: 21, start: "08:00", end: "23:00", weekdays: 6-7 }
    - { v: 16 }

    watched_entities:
    - "input_boolean.vacation"

It turns out that you could have done the exact same without including
a snippet by adding the vacation rules directly to the room's schedule,
but doing it this way makes the configuration more readable, easier
to maintain and avoids redundancy in case you want to include the
``vacation`` snippet into other rooms as well.

Other use cases for ``IncludeSchedule`` are selecting different schedules
based on presence (maybe even long holidays vs. short absence) or
weather sensors.

.. note::

   Splitting up schedules doesn't bring any extra power to Schedy's
   scheduling capabilities, but it can make configurations much more
   readable as they grow.


What to Use ``Break()`` for
---------------------------

When in a sub-schedule, returning ``Break()`` from an expression will
skip the remaining rules of that sub-schedule and continue evaluation
after it. You can use it together with ``Skip()`` to create a conditional
sub-schedule, for instance. Again, we assume to write a schedule for
the thermostat actor type.

::

    schedule:
    - v: 20
      rules:
      - x: "Skip() if is_on('input_boolean.include_sub_schedule') else Break()"
      - { start: "07:00", end: "09:00" }
      - { start: "12:00", end: "22:00" }
      - v: 17
     - v: "OFF"

    watched_entities:
    - "input_boolean.include_sub_schedule"

The rules 2-4 of the sub-schedule will only be respected when
``input_boolean.include_sub_schedule`` is on. Otherwise, evaluation
continues with the last rule, setting the value to ``OFF``.

.. note::

   Since ``schedule_prepend``, a room's individual schedule and
   ``schedule_append`` are just sub-schedules chained internally,
   returning ``Break()`` from a top-level rule of one of these three
   sections causes evaluation to be continued with the next section.

The actual definition of this result type is ``Break(levels=1)``,
which means that you may optionally pass a parameter called ``levels``
to ``Break()``. This parameter controls how many levels of nested
sub-schedules to break out of. The implicit default value ``1`` will
only abort the innermost sub-schedule (the one currently in). However,
you may want to directly abort its parent schedule as well by returning
``Break(2)``. In the above example, this would actually break the room's
schedule and hence continue evaluating the ``schedule_append`` section.


What to Use ``Abort()`` for
---------------------------

The ``Abort`` return type is most useful for disabling Schedy's scheduling
mechanism depending on the state of entities. You might implement on/off
switches for disabling the schedules with it, like so:

::

    schedule_prepend:
    - name: global schedule on/off switch
      x: "Abort() if is_off('input_boolean.schedy') else Skip()"
    - name: per-room schedule on/off switch
      x: "Abort() if is_off('input_boolean.schedy_room_' + room_name) else Skip()"

    # These should trigger a re-evaluation in every room.
    watched_entities:
    - "input_boolean.schedy"

    # And for these it is sufficient to re-evaluate the corresponding room only.
    rooms:
      living:
        watched_entities:
        - "input_boolean.schedy_room_living"
      kitchen:
        watched_entities:
        - "input_boolean.schedy_room_kitchen"

As soon as ``Abort()`` is returned, schedule evaluation is aborted and
the value stays unchanged.


Using the Generic ``Postprocess()`` Postprocessor
-------------------------------------------------

The ``Postprocess()`` :doc:`postprocessor <postprocessors>` lets you
alter the result of scheduling in arbitrary ways. It takes a callable
which is then called with the result as its argument and should return
the eventually altered result.

In this example, we use ``Postprocess()`` with lambda closures (in-line
functions that generate their return value with only a single expression)
to limit the scheduled value to the range from ``16`` to ``22``. This
could be useful for a temperature, for instance.

::

    - x: "Postprocess(lambda result: max(16, result))"
    - x: "Postprocess(lambda result: min(result, 22))"

You could of course have done this with a single postprocessor as well.

::

    - x: "Postprocess(lambda result: max(16, min(result, 22)))"

Instead of lambda closures, normal functions may also be used. Here is
an identically behaving, quite verbose implementation.

::

    - x: |
        def limit(r):
            if r < 16:
                return 16
            if r > 22:
                return 22
            return r

        result = Postprocess(limit)

Here's another one which actually behaves like ``Add(-3)``.

::

    - x: "Postprocess(lambda result: result - 3)"

.. note::

   As you know, evaluation stops at the first rule generating a
   result. Hence you need to ensure the rules returning postprocessors are
   placed before the rules that generate the results to be postprocessed,
   not after them.
