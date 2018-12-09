State Helpers
=============

These helpers can be used to retrieve the state of entities from Home
Assistant.


``is_on``
---------

``is_on(entity_id: str) -> bool``

Returns ``True`` if the state of the given entity is ``"on"``
(case-insensitive), ``False`` otherwise.


``is_off``
----------

``is_off(entity_id: str) -> bool``

Returns ``True`` if the state of the given entity is ``"off"``
(case-insensitive), ``False`` otherwise.

.. note::

   There is a difference between using ``is_off(...)`` and ``not
   is_on(...)``. These helper functions only compare the state of the
   specified entity to the values ``"off"`` and ``"on"``, respectively. If
   you want to treat a non-existing entity (which's state is returned as
   ``None``) as if it was ``"off"``, you have to use ``not is_on(...)``
   since ``is_off(...)`` would return ``False`` in this case.


``state``
---------

``state(entity_id: str, attribute: str = None) -> Any``

A shortcut for ``app.get_state(...)``.


``filter_entities``
-------------------

``filter_entities(entities: Union[str, List[str]] = None, **criteria: Any) -> Iterable[str]``

From a given set of entities, this function yields only those with a
state and/or attributes matching all given criteria.

Entities may either be specified as a single string (full entity id or
domain), a list of such strings, or as ``None``, which means all entities
found in Home Assistant.

Examples:

::

    # entities with a state of "on"
    for entity in filter_entities(state="on"):
        ...

    # binary_sensor and input_boolean entities having a room attribute with the value "living"
    for entity in filter_entities(["binary_sensor", "input_boolean"], room="living"):
        ...
