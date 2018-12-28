Motion-Triggered Lights
=======================

Scheduling lights is really easy with the ``switch`` actor type. Even
associating motion sensors isn't too complicated with just a single
additional schedule rule. The procedure is identical to that used for
:doc:`open-window-detection`, except that the ``binary_sensor`` entities
now report motion instead of open windows and the value needs to be set to
``"on"`` while motion is detected.

Let's assume the following:

1. You've got a room named ``entrance`` configured in Schedy with one
   or more lights as actors.

2. There'S a motion sensor ``binary_sensor.entrance_motion`` that switches
   to ``on`` when motion is detected.

Ok, let's get started.

1. Add a custom ``motion_room: entrance`` attribute to the
   ``binary_sensor.entrance_motion`` entity via ``customize.yaml``
   to tie the motion sensor to the Schedy room it belongs to.

2. Now, a new rule which overlais the value with ``"on"`` while a
   motion sensor of the current room reports motion is added. We place
   it at the top of the ``schedule_prepend`` configuration section to
   have it applied to all rooms as their first rule.

   ::

       - x: "Mark('on', Mark.OVERLAY) if not is_empty(filter_entities('binary_sensor', motion_room=room_name, state='on')) else Skip()"

3. Add the motion sensor to the ``watched_entities`` of the ``entrance`` room.

::

    watched_entities:
    - "binary_sensor.entrance_motion"

Try it out. As long as at least one of the motion sensors in a room
reports motion, the lights in that room should stay on.

If you also had brightness sensors in each room, you could now insert
another rule before the one we just added to fix the value to ``"off"``
when it's not dark enough in the particular room.
