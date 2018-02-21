Apps
====

All apps for AppDaemon can be found inside the ``hass_apps`` directory
of the repository. Each includes a sample configuration in the file
``doc/apps.yaml.example``.

Currently, the following apps are included:

* `heaty`_:  A highly-configurable, comfortable to use Home Assistant /
  appdaemon app that controls thermostats based on a schedule while still
  facilitating manual intervention at any time.
* **motion_light**:  This app can turn devices on/off according to the
  state of sensors.
  The most obvious use case is controlling lights when motion sensors
  report motion, but other scenarios are imaginable as well. Delays and
  constraints can be configured freely for each individual sensor.

.. _heaty: hass_apps/heaty/doc/README.rst



.. toctree::
   :glob:
   :hidden:

   */index
