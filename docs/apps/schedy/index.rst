Schedy
======

Schedy is a highly-configurable, comfortable to use multi-purpose
scheduler for Home Assistant that controls different types of actors
such as switches and thermostats based on powerful rules while still
facilitating manual intervention at any time.

These key features are implemented in Schedy. More are added continuously.

* Schedules (based on time, days of week/month, month, year and more)
* Separate schedule and settings for each room (multi-room)
* Dynamic values based on expressions written in Python
* Configurable re-scheduling after manual adjustments
* Re-sending until actors report the change back (for unreliable networks)
* Logging

This documentation is written for both beginners that want to get
started with Schedy and advanced users needing a reference book for
implementing complex scenarios.

In order to get started, it is recommended to read the `chapter about the
concept <concept.html>`_ first and then proceed to the following pages.

.. toctree::
   :caption: Contents:
   :maxdepth: 1

   concept
   configuration
   actors/index
   writing-schedules
   expressions
   events
   tips-and-tricks
   CHANGELOG
