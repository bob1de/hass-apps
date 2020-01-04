Switch
======

The ``switch`` actor is used to control binary on/off switches. Internally, it's a
:doc:`../generic/index`, but with a much simpler configuration, namely none at all.

.. note::

   It calls the generic ``homeassistant.turn_on`` and
   ``homeassistant.turn_off`` services and hence can as well be used
   for other entity types supporting to be turned on and off this
   way. However, they need to provide ``"on"`` and ``"off"`` as their
   ``state``.

   Especially, this is true for ``input_boolean`` and ``light`` entities.

For completeness, this is the configuration you had to use if you wanted to build
this switch actor out of the :doc:`../generic/index` yourself:

.. literalinclude:: generic-config.yaml
   :language: yaml


Supported Values
----------------

You need to return the strings ``"on"`` or ``"off"`` from your schedules
for the switch actor to work. It's that simple.
