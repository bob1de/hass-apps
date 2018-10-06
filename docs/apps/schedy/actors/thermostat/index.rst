Thermostat
==========

The ``thermostat`` actor is used to control the temperature of climate
entities.

Often, people ask me whether Schedy can be used with their particular
heating setup. I always tend to repeat myself in these situations,
hence I want to explain here what the exact preconditions for using
Schedy for heating control actually are.

1. You need at least one thermostat in each room you want to control.
   Such a thermostat must be recognized as a climate entity in Home
   Assistant, and setting the target temperature from the Home Assistant
   web interface should work reliably. Wall thermostats can be controlled
   the same way as radiator thermostats, as long as they fulfill these
   conditions as well. If you only have a switchable heater and an
   external temperature sensor, have a look at Home Assistant's `Generic
   Thermostat platform`_ to build a virtual thermostat first.

2. If your thermostat is used for both heating and cooling, there has
   to be an automatic operation mode which does heating/cooling based
   on the difference between current and set target temperature. Schedy
   will only switch the operation mode between on and off (exact names
   can be configured) and set the target temperature according to the
   configured schedule.

.. _`Generic Thermostat platform`: https://home-assistant.io/components/climate.generic_thermostat/

If you are happy with these points and your setup fulfills them, there
should be nothing stopping you from integrating Schedy's great scheduling
capabilities with your home's heating. You can then go on and create a
Schedy configuration with thermostat actors.


Configuration
-------------

.. include:: ../config-intro.rst.snippet

.. literalinclude:: config.yaml
   :language: yaml


Supported Values
----------------

Your schedules must generate valid temperature values. Those can be
integers (``20``) or floats (``21.5``). Strings are tried to be converted
to numbers automatically for you.

A special value is ``OFF``, which is an object available in the evaluation
environment when using the thermostat actor type. If this object is
returned from an expression, it will turn the thermostats off. The
equivalent for the ``OFF`` object to use when using plain values instead
of expressions is the string ``"OFF"`` (case-insensitive).

.. note::

   When working with the ``Add()`` preliminary result type and the final
   result is ``OFF``, it will stay ``OFF``, no matter what's being added
   to it.
