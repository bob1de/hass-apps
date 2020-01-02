The Concept
===========

Schedy is a multi-purpose scheduler for Home Assistant.

When one thinks of a schedule, he usually imagines to configure values (such as
temperatures) for different times of the day and days of week. That's of course
possible with Schedy in a convenient manner, but it can do a lot more as well.

Scheduling here basically means linking time frames (and/or state conditions) to
the states actors should adopt.


Why not use Automations?
------------------------

You may now ask: Why should I use a third-party solution when I have automations
in Home Assistant right at hand? Well, that's a legitimate question. But have
you ever tried to implement a flexible, easily maintainable schedule for heating,
roller shutters or lights using plain automations? Maybe even one that cooperates
with presence or motion detection? If not, believe me, that's no fun and will get
really confusing sooner than later.

Besides this practical reasons why automations are not suited well for scheduling,
take a look at what automations really do: reacting to triggers. Triggers can be
described as events - they happen once, cause the automation to fire and are then
gone. Possible triggers could be "I get home" or "Someone turns on the TV". But if
you, for instance, start Home Assistant after the TV was already turned on, your
automation won't fire at all.

In contrast to automations, Schedy maps time (and optionally state) to state. Instead
of waiting for the events "It's 8.00pm" and ""Someone turns on the TV", Schedy checks
"Is it after 8.00pm?" and ""Is the TV turned on?" and, if so, ensures the corresponding
scheduled state, such as "Living room lights off" is in place.

.. note::

   Automations react to triggers (events/state changes), Schedy reacts to time
   and/or state..

Don't get me wrong, automations are great and Schedy doesn't try to obsolete them,
but they simply aren't suited well for scheduling.


How it Works
------------

While reading this documentation and working with Schedy, you'll stumble
across different terms that you have to understand first.

An **actor** is an entity that can be controlled by Home Assistant. A
switch is an actor that can have the states ``on`` and ``off``, for
instance. A thermostat is one that can be set to different temperature
values or be turned off completely. There are far more possibilities
for what can be used as an actor in Schedy, but that's enough for now.

The purpose of a **schedule**, which usually consists of multiple
**schedule rules**, is to define what state actors should be in at which
times. Apart from the rich set of available constraints for specifying
a schedule rule's period of validity, Schedy's schedules do also support
**expressions** that can easily be written in-line in Python to let the
state of arbitrary entities in Home Assistant influence the scheduled
value, allowing for decisions based on, for instance, presence or motion.

Finally, Schedy operates on so-called rooms. A **room** is an unit with
a schedule and one or more actors that are controlled simultaneously by
that schedule.

That's basically it. Plug all these components together and you get a
really powerful scheduler that can satisfy both basic and advanced needs.
The next chapter is a tutorial for getting Schedy up and running quickly.
