Basic Helpers
=============

``app``
-------

``app: SchedyApp``

There is an object available under the name ``app`` which represents
the ``appdaemon.plugins.hass.hassapi.Hass`` object of Schedy. You could,
for instance, retrieve values of input sliders via the normal AppDaemon
API.


``room_name``
-------------

``room_name: str``

A string representing the name of the room the expression is evaluated
for as set in Schedy's configuration (not the friendly name).


``schedule_snippets``
---------------------

``schedule_snippets: Dict[str, Schedule]``

A dictionary containing all configured schedule snippets, indexed by
their name for use with ``IncludeSchedule()``.


``round_to_step``
-----------------

``round_to_step(value: Union[float, int], step: Union[float, int], decimal_places: int = None) -> Union[float, int]``

Round the value to the nearest step and, optionally, the given number
of decimal places.

Examples:

::
    round_to_step(34, 25) == 25
    round_to_step(0.665, 0.2, 1) == 0.6"""
