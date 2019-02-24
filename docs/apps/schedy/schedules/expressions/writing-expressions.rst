Writing Expressions
===================

.. note::

   In contrast to plain values, which are denoted as ``value`` or ``v``,
   expressions have to be set as the ``expression`` (or ``x``) parameter
   of a schedule rule. And since expressions have to be strings, we
   enclose them in quotation marks to prevent the YAML parser from
   guessing, which may otherwise lead to obscure errors with certain
   expressions.

Expressions must return a kind of value the used actor type
understands. Take the thermostat actor as an example. It needs a
temperature value which can either be an integer (``19``) or floating
point value (``20.5``). What type of value an individual actor
needs is explained in the :doc:`chapter specific to the actor type
<../../actors/index>`.


Expressions vs. Statements
--------------------------

The string provided as the ``x`` parameter of a schedule rule is
treated as a simple Python expression. Each of the following is a valid
expression.

* ``5``
* ``True``
* ``'off'``
* ``17 if is_on('binary_sensor.absent') else Skip()``

Writing expressions that way is short and great for things like binary
decisions. However, there might be situations in which you need to make
more complex weightings that would get confusing when written as a single
line expression. That's why you may as well use whole statements.

As soon as the string given as an expression contains line-breaks,
it's treated as a series of whole statements rather than an expression. In
YAML, a schedule rule with such a multi-line expression can be denoted
as follows.

::

    - x: |
        a = 2
        b = 5
        result = a * b

The string is introduced by a ``|``, and all following lines need to be
indented by a custom (but consistent) number of spaces.

You may in fact write  arbitrary Python code in such a script, including
import statements and class or function definitions. The only requirement
is that at the end of the execution, the final result is stored in the
global ``result`` variable.

.. note::

   The string really has to consist of more than one line to be treated
   as a statement. The following example doesn't contain line-breaks
   and hence would be considered as an uncompilable expression.

   ::

       - x: |
           result = 42

   While this is a valid single-line expression and would compile just fine:

   ::

       - x: |
           42


Controlling the Evaluation Flow
-------------------------------

There are special types  available for creating objects you can return
from an expression in order to influence the way your schedule is
processed.

* ``Abort()``, which causes schedule lookup to be aborted immediately.
  The value will not be changed in this case.
* ``Break(levels=1)``, which causes lookup of one (or multiple nested)
  sub-schedule(s) to be aborted immediately. The evaluation will continue
  after the sub-schedule(s).
* ``IncludeSchedule(schedule)``, which dynamically inserts the given
  schedule object as a sub-schedule after the current rule.
* ``Inherit()``, which causes the value or expression of the nearest
  ancestor rule to be used as result for the current rule. See the next
  section for a more detailed explanation.
* ``Skip()``, which causes the rule to be treated as if it didn't exist
  at all. If one exists, the next rule is evaluated in this case.

For all of these types, :doc:`usage examples <examples>` are provided.
