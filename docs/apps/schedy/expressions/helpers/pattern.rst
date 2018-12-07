Pattern Helpers
===============

These helpers can be used to calculate values based on some pre-defined
patterns.


``pattern.linear``
------------------

``pattern.linear(start_value: Union[float, int], end_value: Union[float, int], percentage: Union[float, int]) -> float``

Calculate the value at a given ``percentage`` between ``start_value``
and ``end_value``. The borders can be crossed when ``percentage`` is
outside the range ``0..100``.
