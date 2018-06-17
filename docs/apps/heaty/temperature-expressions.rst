Temperature Expressions
=======================

Heaty accepts so called temperature expressions in schedules or when
manually setting a temperature via the ``heaty_set_temp`` event.

Temperature expressions are a powerful way of expressing a temperature
in relation to anything you can think of. This power comes from the fact
that temperature expressions are just normal Python expressions which
are evaluated at runtime. When Heaty parses its configuration, all
temperature expressions are pre-compiled to make their later evaluation
more performant.

Temperature expressions must evaluate to an object of type
``ResultBase``. However, you should always return one of its sub-types.

Such an object can be created like ``Result(19)`` or ``Result(OFF)``.
If your expression evaluates to an ``int``, ``float`` or ``str`` type,
Heaty converts it to a ``Result`` automatically for convenience.

An object of one of the following sub-types of ``ResultBase`` can be
returned to influence the way your result is treated.

* ``Add(value)``, which causes ``value`` to be added to the result of
  a consequent rule. This is continued until a rule evaluates to a
  final ``Result``.
* ``Break()``, which causes schedule lookup to be aborted immediately.
  The temperature will not be changed in this case.
* ``Ignore()``, which causes the rule to be treated as if it doesn't
  exist at all. If one exists, the next rule is evaluated in this case.
* ``IncludeSchedule(schedule)``, which evaluates the given schedule
  object. See below for an example on how to use this.
* ``Result(value)``: just the final result which will be used as the
  temperature. Schedule lookup is aborted at this point.

If you want to turn the thermostats in a room off, there is a special
value available under the name ``OFF``. Just return that.

There is an object available under the name ``app`` which represents
the ``appdaemon.plugins.hass.hassapi.Hass`` object of Heaty. You could,
for instance, retrieve values of input sliders via the normal
AppDaemon API.

Beside the return types like ``Add``, ``Break``, ``Ignore`` etc.
the following global variables are available inside temperature
expressions:

* ``app``: the ``appdaemon.plugins.hass.hassapi.Hass`` object
* ``room_name``: the name of the room the expression is evaluated for
  as configured in Heaty's configuration (not the friendly name)
* ``schedule_snippets``: a dictionary containing all configured schedule
  snippets, indexed by their name
* ``now``: a ``datetime.datetime`` object containing the current date
  and time
* ``date``: a shortcut for ``now.date()``
* ``time``: a shortcut for ``now.time()``
* ``datetime``: Python's ``datetime`` module
* ``state(entity_id)``: a shortcut for ``app.get_state(entity_id)``
* ``is_on(entity_id)``: returns ``True`` if the state of the given entity
  is ``"on"`` (case-insensitive)
* ``is_off(entity_id)``: returns ``True`` if the state of the given entity
  is ``"off"`` (case-insensitive)


Using Code from Custom Modules
------------------------------

You can easily make your own code available inside temperature
expressions by importing custom modules. Modules that should be
available in your expressions have to be specified in the configuration
like so:

::

    temp_expression_modules:
      math:
      time:
        as: _time
      my_custom_module:

This will make the modules ``math`` and ``time`` from Python's standard
library available, as well as ``my_custom_module``. However, the
``time`` module will be made accessible under the name ``_time`` to
prevent the variable ``time``, which is included by Heaty anyway, from
being overwritten.


Examples
--------

Example: Use of an External Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Imagine you have a module which makes some more complex decisions
based on the current state. We call it ``my_mod``. This could look
as follows:

::

    # This module gives us access to Ignore as well as all other
    # ResultBase sub-types and OFF.
    from hass_apps.heaty import expr

    def get_temp(room_name, app):
        if room_name == "bath":
            if app.get_state("switch.take_a_bath") == "on":
                return 22
        return expr.Ignore()

Save the code as ``my_mod.py`` somewhere Python can find it.
The easiest way is to store it inside AppDaemon's ``apps`` directory.

Add the module to your ``temp_expression_modules`` config as
explained before.

Now, we write two new schedule rules for the bath room (note their
order):

::

    schedule:
    - temp: my_mod.get_temp(room_name, app)
    - temp: 19

Last step is to write a simple Home Assistant automation to emit a
re-schedule event whenever the state of ``switch.take_a_bath`` changes.

::

    - alias: "Re-schedule when switch.take_a_bath is toggled"
      trigger:
      - platform: state
        entity_id: switch.take_a_bath
      action:
      - event: heaty_reschedule
        event_data:
          room_name: bath

We're done! Now, whenever we toggle the ``take_a_bath`` switch, the
schedules are re-evaluated and our first schedule rule executes.
The rule invokes our custom function, passing to it the room's name
and the ``appdaemon.plugins.hass.hassapi.Hass`` object. Our custom
function checks the state of the ``take_a_bath`` switch and, if it's
enabled, causes the temperature to be set to 22 degrees. However, if the
switch is off or we called it for a room it actually has no clue about,
the rule is ignored completely.

If that happens, the second rule is processed, which always evaluates
to 19 degrees.

You should be able to extend the ``get_temp`` function to include
functionality for other rooms now as well.


Example: Inlining Temperature Expressions into Schedules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The previous example demonstrated how custom modules can be used in
schedules. However, for such a simple use case, there is a much shorter
way of achieving the same goal. The following schedule will have the
same effect, but without the use of any external Python module:

::

    schedule:
    - temp: 22 if is_on("switch.take_a_bath") else Ignore()
    - temp: 19

Basically, we inlined the Python code we previously placed in
``my_mod.py`` right into the schedule rule. This works because it is
just an ordinary expression and not a series of statements. If you know
a little Python, you'll probably be familiar with this way of writing
expressions. Often, it is easier and also more readable to include such
short ones directly into the rule instead of calling external code.

However, don't forget to add an automation to Home Assistant which
emits a ``heaty_reschedule`` event whenever ``switch.take_a_bath``
changes its state, just as shown in the previous example.


Example: Use of ``Add()`` and ``Ignore()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a rule I once used in my own Heaty configuration at home:

::

    schedule_prepend:
    - temp: Add(-3) if is_on("input_boolean.absent") else Ignore()

What does this? Well, the first thing we see is that the rule is placed
inside the ``schedule_prepend`` section. That means, it is valid for
every room and always the first rule being evaluated.

I've defined an ``input_boolean`` called ``absent`` in Home Assistant.
Whenever I leave the house, this gets enabled. If I return, it's turned
off again. In order for Heaty to notice the toggling, I added an
automation to Home Assistant which fires a ``heaty_reschedule`` event.
How that can be done has already been shown above.

Now let's get back to the schedule rule. When it evaluates, it checks the
state of ``input_boolean.absent``. If the switch is turned on, it
evaluates to ``Add(-3)``, otherwise to ``Ignore()``.

``Add(-3)`` is no final temperature yet. Think of it as a temporary
value that is remembered and used later.

Now, my regular schedule starts being evaluated, which, of course, is
different for every room. Rules are evaluated just as normal. If one
returns a ``Result``, that is used as the temperature and evaluation
stops. But wait, there was the ``Add(-3)``, wasn't it? Sure it was.
Hence ``-3`` is now added to the final result.

With this minimal configuration effort, I added an useful away-mode
which throttles all thermostats in the house as soon as I leave.

Think of a device tracker that is able to report the distance between
you and your home. Having such one set up, you could even implement
dynamic throttling that slowly decreases as you near with almost zero
configuration.


Example: Including Schedules Dynamically with ``IncludeSchedule()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``IncludeSchedule()`` return type for temperature expressions can
be used to insert a set of schedule rules right at the position of the
current rule. This comes handy when a set of rules should be chosen
depending on the state of entities or other complex calculations.

.. note::

   If you only want to prevent yourself from repeating the same static
   constraints for multiple rules, use the `sub-schedule feature
   <writing-schedules.html#rules-with-sub-schedules>`_ of the normal
   rule syntax instead.

You can reference any schedule defined under ``schedule_snippets`` in
the configuration, hence we create one to play with:

::

    schedule_snippets:
      summer:
      - { temp: 20, start: "07:00", end: "22:00", weekdays: 1-5 }
      - { temp: 20, start: "08:00", weekdays: 6-7 }
      - { temp: 16 }

Now, we include the snippet into a room's schedule:

::

    schedule:
    - temp: IncludeSchedule(schedule_snippets["summer"])
      months: 6-9
    - { temp: 21, start: "07:00", end: "21:30", weekdays: 1-5 }
    - { temp: 21, start: "08:00", end: "23:00", weekdays: 6-7 }
    - { temp: 17 }

It turns out that you could have done the exact same without including
schedules by adding the ``months: 6-9`` constraint to all rules of the
summer snippet. But doing it this way makes the configuration a little
more readable.

However, you can also utilize the include functionality from inside
custom code as shown in one of the previous examples. Just think of
a function that selects different schedules based on external criteria,
such as weather sensors or presence detection.

It has to be noted that splitting up schedules doesn't bring any extra
power to Heaty's scheduling capabilities, but it can make configurations
much more readable as they grow.


Example: What to Use ``Break()`` for
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``Break`` return type is most useful for disabling Heaty's
scheduling mechanism depending on the state of entities. You might
implement a schedule on/off switch with it, like so:

::

    schedule_prepend:
    - temp: Break() if is_off("input_boolean.heating_schedule") else Ignore()



Security Considerations
-----------------------

It has to be noted that temperature expressions are evaluated using
Python's ``eval()`` function. In general, this is not suited for code
originating from a source you don't trust completely, because such code
can potentially execute arbitrary commands on your system with the same
permissions and capabilities the AppDaemon process itself has.
That shouldn't be a problem for temperature expressions you write
yourself inside schedules.

This feature could however become problematic if an attacker somehow
is able to emit events on your Home Assistant's event bus. To prevent
temperature expressions from being accepted in the ``heaty_set_temp``
event, processing of such expressions is disabled by default and has
to be enabled explicitly by setting ``untrusted_temp_expressions: true``
in your Heaty configuration.
