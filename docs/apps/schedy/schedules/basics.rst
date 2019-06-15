The Basics: Static Schedules
============================

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
sense if they couldn't do more than this.

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

.. note::

   This is how schedules work. The first matching rule wins and determines
   the value to set. Consequently, you should design your schedules with
   the most specific rules at the top and gradually generalize to wider
   time frames towards the bottom. Finally, there should be a fallback
   rule without time restrictions at all to ensure you have no time slot
   left without a value defined for.

The ``name`` parameter we specified here is completely optional and
doesn't influence how the rule is interpreted. A rule's name is shown
in logs and may be useful for troubleshooting.

For more fine-grained control, you may also specify seconds in addition
to hour and minute. ``22:00:30`` means 10.00 pm + 30 seconds, for
instance. Spanning rules beyond midnight (``start`` >= ``end``) is
possible as well.

You can now write rules that specify the value over the day, but you
still can't create different schedules for, for instance, the days of
the week. Let's do this next.


.. _schedy/schedules/basics/constraints:

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

With your knowledge so far, this should be self-explanatory. The only new parameter is
``weekdays``, which is a so called constraint.

Constraints can be used to limit the days on which the rule should start to be
active. There are a number of these constraints, namely:

* ``years``: limit the years (e.g. ``years: 2016-2018``); only years from 1970 to
  2099 are supported
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

A date needs to fulfill all constraints you defined for a rule to be considered
active at that specific date.

The format used to specify values for the first five types of constraints is similar
to that of crontab files. We call it range specification, and only integers are
supported, no decimal values.

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

If an exclamation mark (``!``) is prepended to the range specification, its values are
inverted. For instance, the constraint ``weekdays: "!4-5,7"`` expands to ``weekdays:
1,2,3,6`` and ``months: "!3"`` is equivalent to ``months: 1-2,4-12``.

.. note::

   The ``!`` sign has a special meaning in YAML, hence inverted specifications have
   to be enclosed in quotes.


Rules Spanning Multiple Days
----------------------------

Now let's come back to the 16-degrees rule we wrote above and figure
out why that actually counts as a fallback for the whole day. Here's
the rule we have so far.

::

    - v: 16

If you omit the ``start`` parameter, Schedy assumes that you mean midnight
(``0:00``) and fills that in for you. When ``end`` is not specified
(as has been done here), Schedy sets ``0:00`` for it as well. However,
a rule that ends the same moment it starts at wouldn't make sense. We
expect it to count for the whole day instead.

In order to express what we actually want, we'd have to set ``end`` to ``"00:00+1d"``,
which tells Schedy that there is one midnight between the start and end times. For
convenience, Schedy automatically assumes one midnight between start and end when
you don't specify a number of days explicitly and the start time is prior or equal
to the end time, as in our case.

.. note::

   You don't need to care about setting ``+?d`` yourself unless one of your rules
   should span more than 24 hours, requiring ``+1d`` or greater.

Having written out what Schedy assumes automatically would result in
the following rule, which behaves exactly identical to what we begun with.

::

    - { v: 16, start: "0:00", end: "0:00+1d" }

.. note::

   The rule has been rewritten to take just a single line. This is no
   special feature of Schedy, it's rather normal YAML. But writing rules
   this way is often more readable, especially if you need to create
   multiple similar ones which, for instance, only differ in weekdays,
   time or value.

Let's get back to :ref:`schedy/schedules/basics/constraints` briefly. We know that
constraints limit the days on which a rule starts to be active. This explanation is
not correct in all cases, as you'll see now.

There are some days, such as the last day of a month, which can't be expressed
using constraints explicitly. To allow targeting such days anyway, the ``start``
parameter of a rule accepts a day shifting suffix as well. Your constraints are
checked for some date, but the rule starts being active some days earlier or later,
relative to the matching date.

Even though you can't specify the last day of a month, you can well specify the
1st. This rule is active on the last day of February from 6.00 pm to 10.00 pm,
no matter if in a leap year or not::

    - { v: 22, start: "18:00-1d", end: "22:00", days: 1, months: 3 }

This one even runs until March 1st, 10.00 pm::

    - { v: 22, start: "18:00-1d", end: "22:00+1d", days: 1, months: 3 }

As you noted, the day shift of ``start`` can be negative as well, but not that of
``end``, meaning your rules can't span backwards in time. This design decision was
made in order to keep rules readable and the evaluation algorithm simple. It neither
has a technical reason nor does it reduce the expressiveness of rules.


.. _schedy/schedules/basics/rules-with-sub-schedules:

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
