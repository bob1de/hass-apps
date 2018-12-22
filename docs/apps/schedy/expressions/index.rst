Expressions
===========

As an alternative to fixed values, Schedy accepts so called expressions
in schedule rules.

Expressions are a powerful way of expressing a value to be sent to
actors dynamically in relation to anything you can think of. This power
comes from the fact that expressions are just normal Python code which
is evaluated at runtime. All expressions are pre-compiled at startup to
make their later evaluation really performant.


.. toctree::
   :caption: Contents:
   :maxdepth: 1

   writing-expressions
   helpers/index
   postprocessors
   result-markers
   examples


Security Considerations
-----------------------

It has to be noted that expressions are evaluated using Python's
``exec()`` function. In general, this is not suited for code
originating from a source you don't trust completely, because such
code can potentially execute arbitrary commands on your system with
the same permissions and capabilities the AppDaemon process itself
has. That shouldn't be a problem for expressions you write yourself
inside schedules.

This feature could however become problematic if an attacker somehow
is able to emit events on your Home Assistant's event bus. To prevent
expressions from being accepted in the ``schedy_set_value`` event,
processing of such expressions is disabled by default and has to be
enabled explicitly by setting ``expressions_from_events: true`` in your
Schedy configuration.
