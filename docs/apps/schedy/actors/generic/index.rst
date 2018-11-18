Generic Actor
=============

.. include:: ../../advanced-topic.rst.snippet

The ``generic`` actor can be used for controlling different types of
entities such as switches, lights, numbers and media players.

It works by defining a set of states and, for each of these states,
what service has to be called in order to reach the state. Together with
a wildcard for undefined states, this is a quite powerful mechanism.


Configuration
-------------

.. include:: ../config-intro.rst.snippet

.. literalinclude:: config.yaml
   :language: yaml


Supported Values
----------------

Every state that has been configured in the ``states`` section of the
actor configuration may be returned by a schedule. If you have the
wildcard state ``_other_`` configured, any value is accepted.

.. note::

   When specifying the states ``on`` and ``off``, enclose them in quotes
   to inform the YAML parser that you don't mean the booleans ``true``
   and ``false`` instead.

.. note::

   Since Home Assistant sends states as strings, all state names you
   configure are converted to strings automatically. The values generated
   by your schedules are also converted to strings before they're looked
   up in the ``states`` configuration. This is normally nothing you
   should be worried about, so just take it as a notice.
