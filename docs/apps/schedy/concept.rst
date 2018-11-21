The Concept
===========

What is Schedy?
---------------

Schedy is a multi-purpose scheduler for Home Assistant. Scheduling here
basically means linking time frames and/or state conditions to the state
of actors.

You may now ask: Why should I use a third-party solution when I have
automations in Home Assistant right at hand? Well, that's a legitimate
question. But have you ever tried to implement a flexible, easily
maintainable heating schedule with automations? If not, believe me,
that's no fun and will get really confusing sooner than later. Don't
get me wrong, automations are great and Schedy doesn't try to obsolete
them, but they simply aren't suited well for scheduling.


How it Works
------------

While reading this documentation and working with Schedy, you'll stumble
across different terms that you have to understand first.

An **actor** is something that can be controlled by Home Assistant. A
switch is an actor that can have the states ``on`` and ``off``, for
instance. A thermostat is one that can be set to different temperature
values or be turned off completely. There are far more possibilities
for what can be used as an actor in Schedy, but that's enough for now.

The purpose of a **schedule**, which usually consists of multiple
**schedule rules**, is to define what state actors should be in at which
times. Apart from the rich set of available constraints for specifying a
schedule rule's period of validity, Schedy's schedules do also support
**expressions** that can easily be written in-line in Python to let the
state of arbitrary Home Assistant entities influence the scheduled value,
allowing for decisions based on, for instance, presence.

Finally, Schedy operates on so-called rooms. A **room** is an unit with
a schedule and one or more actors that are controlled simultaneously by
that schedule.

That's basically it. Plug all these components together and you get a
really powerful scheduler that can satisfy both basic and advanced needs.
