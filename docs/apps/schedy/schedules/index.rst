Schedules
=========

A schedule controls the state of actors in a room. In its simplest form,
this means specifying which state should be set at which times statically,
like in a timetable.

However, this is not flexible enough for more sophisticated needs, which
is why schedules can be extended with dynamic rules, turning them into
Python scripts that can, for instance, access the state of Home Assistant
entities easily.

To get started, begin with static schedules. Once you feel comfortable
writing them, you may proceed to dynamic expressions.


.. toctree::
   :caption: The Basics for Writing Schedules
   :maxdepth: 2

   basics


.. toctree::
   :caption: Turning Schedules into Powerful Scripts
   :maxdepth: 2

   expressions/index
