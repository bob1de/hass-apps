Writing Schedules
=================

A schedule controls the state of actors in a room over time. It consists
of a set of rules. What these rules define is dependent upon the type
of actor. Our examples here use the ``thermostat`` actor type and hence
define temperatures.

Each rule must at least define a value:

::

    schedule:
    - value: 16

This schedule would just always set the temperature to ``16``
degrees, nothing else. Of course, schedules wouldn't make a lot
sense if they couldn't do more than that.

For ``value``, there is a shortcut ``v`` to make rules more
compact. We'll use that from now on.


Scheduling Based on Time of the Day
-----------------------------------

Here is another one:

::

    schedule:
    - v: 21.5
      start: "7:00"
      end: "22:00"
      name: Fancy Rule
    - v: 16

This schedule shares the 16 degrees rule with the previous one,
but additionally, it got a new rule at the top. The new first rule
overwrites the second and will set a temperature of ``21.5`` degrees,
but only from 7.00 am to 10.00 pm. This is because it's placed before
the 16 degrees-rule and Schedy evaluates rules from top to bottom. From
10.00 pm to next day 7.00 am, the ``16`` degrees do still apply.

That's how schedules work. The first matching rule wins and determines
the value to set. Consequently, you should design your schedules with
the most specific rules at the top and gradually generalize to wider
time frames towards the bottom. Finally, there should be a fallback
rule without time constraints at all to ensure you have no time slot
left without a value defined for.

The ``name`` parameter we specified here is completely optional and
doesn't influence how the rule is interpreted. A rule's name is shown
in logs and may be useful for troubleshooting.

For more fine-grained control, you may also specify seconds in addition to
hour and minute. ``22:00:30`` means 10.00 pm + 30 seconds, for instance.


Rules Spanning Multiple Days
----------------------------

Now let's come back to the 16-degrees rule we wrote above and figure
out why that actually counts as a fallback for the whole day. Here's
the rule we have so far.

::

    - v: 16

If you omit the ``start`` parameter, Schedy assumes that you mean midnight
(``00:00``) and fills that in for you. When ``end`` is not specified,
Schedy sets ``00:00`` for it as well. That's what we did for this
rule. However, a rule that ends the same moment it starts at wouldn't
make sense. We expect it to count for the whole day instead.

In order to express what we actually want, there's another parameter named
``end_plus_days`` to tell Schedy how many midnights there are between
the start and end time. As we didn't specify this parameter explicitly,
it's value is determined by Schedy. If the end time of the rule is prior
or equal to its start time, ``end_plus_days`` is assumed to be
``1``, otherwise ``0``.

.. note::

   The value of ``end_plus_days`` can't be negative, meaning you can't
   span a rule backwards in time. Only positive integers and ``0``
   are allowed.

.. note::

   You don't need to care about setting ``end_plus_days`` yourself,
   unless one of your rules should span more than 24 hours, requiring
   ``end_plus_days: 2`` or greater.

Having written out what Schedy assumes automatically would result in
the following rule, which behaves exactly identical to what we begun with.

::

    - { v: 16,   start: "0:00", end: "0:00", end_plus_days: 1 }

Note how the rule has been rewritten to take just a single line. This is
no special feature of Schedy, it's rather normal YAML. But writing rules
this way is often more readable, especially if you need to create multiple
similar ones which, for instance, only differ in weekdays, time or value.

You can now write rules that span midnights, but you still can't create
schedules based on, for instance, the days of the week. Let's do that
next.


Constraints
-----------

::

    schedule:
    - v: 22
      weekdays: 1-5
      start: "7:00"
      end: "22:00"

    - v: 22
      weekdays: 6,7
      start: "7:45"

    - v: 15

With your knowledge so far, this should be self-explanatory. The only
new parameter is ``weekdays``, which is a so called constraint.

Constraints can be used to limit the starting days on which the rule is
considered. There are a number of these constraints, namely:

* ``years``: limit the years (e.g. ``years: 2016 - 2018``
* ``months``: limit based on months of the year (e.g.
  ``months: 1-3, 10-12`` for Jan, Feb, Mar, Oct, Nov and Dec)
* ``days``: limit based on days of the month (e.g.
  ``days: 1-15, 22`` for the first half of the month + the 22nd)
* ``weeks``: limit based on the weeks of the year
* ``weekdays``: limit based on the days of the week, from 1 (Monday)
  to 7 (Sunday)
* ``start_date``: A date of the form ``{ year: 2018, month: 2, day: 3 }``
  before which the rule should not be considered. Any of the three fields
  may be omitted, in which case the particular field is populated with
  the current date at validation time.
  If an invalid date such as ``{ year: 2018, month: 2, day: 29 }`` is
  provided, the next valid date (namely 2018-03-01 in this case) is
  assumed.
* ``end_date``: A date of the form ``{ year: 2018, month: 2, day: 3 }``
  after which the rule should not be considered anymore. As with
  ``start_date``, any of the three fields may be omitted.
  If an invalid date such as ``{ year: 2018, month: 2, day: 29 }`` is
  provided, the nearest prior valid date (namely 2018-02-28 in this
  case) is assumed.

The format used to specify values for the first five types of constraints
is similar to that of crontab files. We call it range specification,
and only integers are supported, no decimal values.

* ``x``: the single number ``x``
* ``x-y`` where ``x < y``: range of numbers from ``x`` to ``y``,
  including ``x`` and ``y``
* ``x-y/z`` where ``x < y``: range of numbers from ``x`` to ``y``,
  including ``x`` and ``y``, going in steps of ``z``
* ``*``: range of all numbers
* ``*/z``: range of all numbers, going in steps of ``z``
* ``a,b``, where ``a`` and ``b`` are any of the previous: the numbers
  represented by ``a`` and ``b`` joined together
* ... and so on
* Any spaces are ignored.

All constraints you define need to be fulfilled for the rule to match.


.. _schedy/writing-schedules/rules-with-sub-schedules:

Rules with Sub-Schedules
------------------------

Imagine you need to turn on heating three times a day for one hour,
but only on working days from January to April. The obvious way of doing
this is to define four rules:

::

    schedule:
    - { v: 23, start: "06:00", end: "07:00", months: "1-4", weekdays: "1-5" }
    - { v: 20, start: "11:30", end: "12:30", months: "1-4", weekdays: "1-5" }
    - { v: 20, start: "18:00", end: "19:00", months: "1-4", weekdays: "1-5" }
    - { v: "OFF" }

But what if you want to extend the schedule to heat on Saturdays as
well? You'd end up changing this at three different places.

The more elegant way involves so-called sub-schedule rules. Look at this:

::

    schedule:
    - months: 1-4
      weekdays: 1-6
      rules:
      - { v: 23, start: "06:00", end: "07:00" }
      - { v: 20, start: "11:30", end: "12:30" }
      - { v: 20, start: "18:00", end: "19:00" }
    - v: "OFF"

The first, outer rule containing the ``rules`` parameter isn't considered
for evaluation itself. Instead, it's child rules - those defined under
``rules:`` - are considered, but only when the constraints of the parent
rule (``months`` and ``weekdays`` in this case) are fulfilled.

We can go even further and move the ``v: 20`` one level up, so that
it counts for all child rules which don't have their own ``v`` defined.

::

    schedule:
    - v: 20
      months: 1-4
      weekdays: 1-6
      rules:
      - { start: "06:00", end: "07:00", v: 23 }
      - { start: "11:30", end: "12:30" }
      - { start: "18:00", end: "19:00" }
    - v: "OFF"

Note how the ``v`` for a rule is chosen. To find the value to use for a
particular rule, the rule is first considered itself. In case it has no
own ``v`` defined, all sub-schedule rules that led to this rule are then
scanned for a ``v`` until one is found. When looking at the indentation
of the YAML, this lookup is done from right to left.

I've to admit that this was a small and well arranged example, but the
benefit becomes clearer when you start to write longer schedules, maybe
with separate sections for the different seasons.

With this knowledge, writing quite powerful Schedy schedules should be
easy and quick.

The next chapter deals with expressions, which finally give you the
power to do whatever you can do with Python, right inside your schedules.
