Generic Actor
=============

.. include:: /advanced-topic.rst.inc

The ``generic`` actor can be used for controlling different types of
entities like numbers or media players, even those having multiple
adjustable attributes such as roller shutters with tilt and position.

It works by defining a set of values and, for each of these values,
what service has to be called in order to reach the state represented
by that value. Together with a wildcard for undefined values, this is
a quite powerful mechanism.

Instead of a single value such as ``"on"`` or ``"off"``, you may also
generate a tuple with multiple values like ``(50, 75)`` or ``("on", 10)``
in your schedule rules, where each slot in that tuple corresponds to a
different attribute of the entity.


Configuration
-------------

.. include:: ../config.rst.inc


Supported Values
----------------

The generic actor can be used in two ways. When just a single attribute
should be controlled, every value for which a service has been configured
in the ``values`` section of the actor configuration may be returned
by a schedule. If you have the wildcard value ``_other_`` configured,
any value is accepted.

Examples:

::

    - v: "on"
    - x: -40 if is_on(...) else Skip()

As soon as you add multiple attributes to control, a list or tuple with
a value for each attribute is expected. The order is the same in which
the attributes were specified in the configuration.

Examples:

::

    - v: ["on", 20]
    - x: "(-40, 'something') if is_on(...) else Skip()"

.. note::

   When specifying the values ``on`` and ``off``, enclose them in quotes
   as shown above to inform the YAML parser you don't mean the booleans
   ``True`` and ``False`` instead.
