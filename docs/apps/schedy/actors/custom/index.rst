Custom Actor
============

The ``custom`` actor can be used if maximum control and flexibility
is required, as it allows you to write custom hooks (pieces of
Python code) that link schedule results to entity states. In fact,
you could even implement advanced types like the `thermostat actor
<../thermostat/index.html>`_ with this one.

While this actor is probably not for daily use, it gives you the power
you need when implementing something really fancy.

.. note::

   When you're extensively using the custom actor type for something
   that could be interesting to other people as well, please consider
   filing your idea as an issue on GitHub to maybe get it included in
   Schedy natively. Thank you!


Configuration
-------------

.. include:: ../config_intro

.. literalinclude:: config.yaml
   :language: yaml


Supported Values
----------------

The custom actor doesn't limit the values your schedules can
generate. Anything that your ``send`` hook accepts is fine. With the
optional ``filter_value`` hook you may preprocess the values before they
are stored and get passed into ``send``.
