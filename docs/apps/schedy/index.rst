Schedy
======

Schedy is a highly-configurable, comfortable to use multi-purpose
scheduler for Home Assistant that controls different types of actors
such as switches and thermostats based on powerful rules while still
facilitating manual intervention at any time.

The goal is to provide an easy solution for conventional scheduling
(e.g. by time of day and day of week) while leaving advanced users plenty
of room for customization with arbitrarily complex rules.

.. note::

   Excited? A :doc:`tutorial` is provided for getting up and running quickly.

These key features are implemented in Schedy. More are added continuously.

* Schedules (based on time, days of week/month, month, year and more)
* Multiple schedules for different purposes, occasions or seasons
* One schedule can control a group of actors at once
* Unlimited number of actor groups (Schedy calls them rooms), each having
  its own schedule
* Configurable re-scheduling after manual adjustments
* Optional synchronization of manual changes among all actors in a room
* Dynamic values based on expressions written in Python, allowing for
  arbitrarily complex rules that can consider any information available
  to Home Assistant
* Event-driven system enables external control by ordinary Home Assistant
  events
* Re-sending until actors report a change back (for unreliable networks)
* Collection of individually configurable statistical parameters regarding
  Schedy's operation
* Configurable logging

The scenarios for which you might need a scheduler are numerous. Here
are just some ideas:

* advanced heating setup based on day, time, presence etc.
* motion, daylight and time-triggered lights
* controlling roller shutters based on time, sun and wind conditions
* morning and good night routines for different weekdays
* ... and much more

This documentation is written for both beginners that want to get
started with Schedy and advanced users needing a reference book for
implementing complex scenarios.

In order to get started, it is recommended to read the :doc:`chapter about
the concept <concept>` first and then proceed to the :doc:`tutorial`.


.. toctree::
   :caption: Contents:
   :maxdepth: 1

   concept
   tutorial
   configuration
   actors/index
   schedules/index
   events
   statistics/index
   tips-and-tricks/index
   CHANGELOG
