Writing schedules
=================

A schedule controls the temperature in a room over time. It consists
of a set of rules.

Each rule must define a temperature:

::

    schedule:
    - temp: 16

This schedule would just always set the temperature to ``16``
degrees, nothing else. Of course, schedules wouldn't make a lot
sense if they couldn't do more than that.

Basic scheduling based on time of the day
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is another one:

::

    schedule:
    - temp: 21.5
      start: "07:00"
      end: "22:00"

    - temp: 16

This schedule contains the same rule as the schedule before, but
additionally, it got a new one. The new rule overwrites the other
and will set a temperature of ``21.5`` degrees, but only from 7.00 am
to 10.00 pm. This is because it's placed before the ``16``-degrees-rule.
That is how Heaty schedules work. The first matching rule wins.

If you omit the ``start`` parameter, Heaty assumes that you mean
midnight (``00:00``) and fills that in for you.

When ``end`` is not specified, Heaty does two things. First, it sets
``00:00`` as value for ``end``. This alone wouldn't make sense,
because the resulting rule would stop being valid before it started.
To achieve the behaviour we'd expect, Heaty sets another attribute,
``end_plus_days: 1``. This means that the rule is valid up to the
time specified in the ``end`` field, but one day later than the
start. Cool, right?

Having done the same manually would result in the following schedule,
which behaves exactly like the previous one.

::

    schedule:
    - { temp: 21.5, start: "07:00", end: "22:00" }
    - { temp: 16,   start: "00:00", end: "00:00", end_plus_days: 1 }

Note how each rule has been rewritten to take just a single line.
This is no special feature of Heaty, it's rather normal YAML. But
writing rules this way is often more readable, especially if you
need to create multiple similar ones which, for instance, only
differ in weekdays, time or temperature.

Now we have covered the basics, but we can't create schedules based
on, for instance, the days of the week. Let's do that next.

Constraints
~~~~~~~~~~~

::

    schedule:
    - temp: 22
      weekdays: 1-5
      start: "07:00"
      end: "22:00"

    - temp: 22
      weekdays: 6,7
      start: "07:45"

    - temp: 15

With your knowledge so far, this should be self-explanatory. The only
new parameter is ``weekdays``, which is a so called constraint.

Constraints can be used to limit the days on which the rule is
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
is as follows. We call it range strings, and only integers are supported,
no decimal values.

* ``x-y`` where ``x < y``: range of numbers from ``x`` to ``y``,
  including ``x`` and ``y``
* ``a,b``: numbers ``a`` and ``b``
* ``a,b,x-y``: the previous two together
* ... and so on
* Any spaces are ignored.

All constraints you define need to be fulfilled for the rule to match.

With this knowledge, writing quite powerful Heaty schedules should be
easy and quick.

The next chapter deals with temperature expressions, which finally
give you the power to do whatever you can do with Python, right inside
your schedules.
