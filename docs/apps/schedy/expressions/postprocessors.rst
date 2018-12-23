Postprocessing Results
======================

.. include:: /advanced-topic.rst.inc

There are situations in which it would come handy to post-process the
later result of scheduling in a specific way without knowing what that
result will actually be. One such situation for the thermostat actor type
could be lowering the temperature by a certain number of degrees when
nobody is home. For such needs, there is a concept called postprocessors.

In the evaluation environment, there are a number of types which, when
returned, tell Schedy you want to generate a postprocessor that is going
to alter the later result. Namely, there are:

* ``Add(x)`` to add a value ``x`` to the result.
* ``And(x)`` to combine the result with ``x`` by the ``and`` Python
  operator.  [deprecated]
* ``Multiply(x)`` to multiply the result with ``x``.
* ``Invert()`` to invert the result. This negates numbers, inverts boolean
  values and swaps the strings ``"on"`` and ``"off"`` for each other.
* ``Or(x)`` to combine the result with ``x`` by the ``or`` Python
  operator.  [deprecated]
* ``Postprocess(func)``, where ``func`` is a callable that takes the
  result as its only argument and returns the post-processed result. This
  can conveniently be used with lambda-closures .

When an expression results in such a postprocessor object, it is stored
until a subsequent rule returns some real result. Then, the stored
postprocessors are applied to that result one by one in the order they
were generated.
