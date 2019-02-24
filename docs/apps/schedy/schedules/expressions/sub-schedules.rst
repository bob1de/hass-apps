Expressions and Sub-Schedules
=============================

.. include:: /advanced-topic.rst.inc

In general, there is no difference between using plain values and advanced
expressions in both rules with a sub-schedule attached to them (so-called
sub-schedule rules) and the rules contained in these sub-schedules. But
with expressions, you gain a lot more flexibility.

As you know from :ref:`schedy/schedules/basics/rules-with-sub-schedules`,
rules of sub-schedules inherit their ``v`` parameter from the nearest
ancestor rule having it defined, should they miss an own one. Basically,
this is true for the ``x`` parameter as well.

With an expression as the ``x`` value of the rule inside a sub-schedule,
you get the flexibility to conditionally overwrite the ancestor rule's
value or expression. Should an expression return ``Inherit()``, the next
ancestor rule's value or expression is used. When compared to static
values, returning ``Inherit()`` is the equivalent of omitting the ``v``
parameter completely, but with the benefit of deciding dynamically about
whether to omit it or not.

The whole process can be described as follows. To find the result for
a particular rule inside a sub-schedule, the ``v``/``x`` parameters of
the rule and it's ancestor rules are evaluated from inside to outside
(from right to left when looking at the indentation of the YAML syntax)
until one results in something different to ``Inherit()``.

This even works accross the boundaries of a schedule snippet
included via ``IncludeSchedule()``, because snippets are inserted
as sub-schedules. However, ``Inherit()`` returned from inside of an
included schedule snippet could cause an infinite recursion under
some circumstances, which Schedy deals with by simply skipping
``IncludeSchedule()`` for a schedule snippet that's already on the
execution stack when searching for an ancestor rule to take the value
from. Examples illustrating this behaviour can be found :ref:`here
<schedy/schedules/expressions/examples/include-schedule/cycles>`.
