The parameter calculates the minimum, average and maximum of all collected
values and adds them as ``min``, ``avg`` and ``max`` attributes to the
parameter entity.

Reacting to changes of the attributes can easily be done with the
``numeric_state`` trigger, together with a ``value_template`` like ``{{
state.attributes.max }}``  in Home Assistant.

Options provided because this is a ``MinAvgMaxParameter``:

* ``factors``: Specify a factor which an individual value should be
  multiplied with before adding it to the list of values. Note that this
  doesn't change the weighting of a value for calculating the average,
  it instead changes the value itself. The default factor is ``1``.

  ::

      factors:
        some_id: 1.5
	other_id: 2

* ``weights``: Specify how individual values should be weighted when
  calculating the average value. The default weight is ``1`` and a weight
  of ``0`` causes the value to be excluded completely.
  You may want to use this feature to indicate that some values are
  more or less important than others and have this fact reflected in
  the statistics.

  ::

      weights:
        some_id: 0.5
        other_id: 0
