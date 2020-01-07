Generic Actor Version 2
=======================

The ``generic2`` actor can be used for controlling different types of entities like
numbers or media players, even those having multiple adjustable attributes such as
roller shutters with tilt and position.

It works by defining a set of values and, for each of these values, what services
have to be called in order to reach the state represented by that value.

Instead of a single value such as ``"on"`` or ``"off"``, you may also generate a
tuple of multiple values like ``(50, 75)`` or ``("on", 10)`` in your schedule rules,
where each slot in that tuple corresponds to a different attribute of the entity.

If you want to see how this actor type can be used, have a look at the
:doc:`../switch/index`.


Configuration
-------------

.. include:: ../config.rst.inc


Supported Values
----------------

Every value that has been configured in the ``values`` section of the actor
configuration may be returned from a schedule.

Examples:

::

    - v: "on"
    - x: "-40 if is_on(...) else Next()"

As soon as you configure multiple slots (attributes to be controlled), a list or
tuple with a value for each attribute is expected. The order is the same in which
the slots were specified in the configuration.

Examples:

::

    - v: ['on', 20]
    - x: "(-40, 'something') if is_on(...) else Next()"

.. note::

   When specifying the values ``on`` and ``off``, enclose them in quotes
   as shown above to inform the YAML parser you don't mean the booleans
   ``True`` and ``False`` instead.
