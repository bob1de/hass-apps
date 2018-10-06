Actors
======

Schedy supports controlling different types of actors such as thermostats
or switches.

You first need to specify the desired actor type at the top level of
Schedy's configuration:

::

    actor_type: <name of actor type>

Then go on and add actors to your rooms. The available configuration
parameters and supported values for scheduling are explained on the
actor-specific pages.

.. note:: 

   You have to decide for one actor type per instance of Schedy you
   run. If you need to control different types of actors, create an
   instance of Schedy for each, like so.

   ::

       schedy_lights:
         module: hass_apps_loader
         class: SchedyApp
         actor_type: switch
         # ...

       schedy_heating:
         module: hass_apps_loader
         class: SchedyApp
         actor_type: thermostat
         # ...

   Of course, the same room names may then be used in each of these app
   instances, since they run completely independent of each other.

Currently, the following actor types are available:

.. toctree::
   :glob:
   :maxdepth: 1

   */index


Common Settings
---------------

There are some settings common among all available actor types.

.. literalinclude:: common-config.yaml
   :language: yaml
