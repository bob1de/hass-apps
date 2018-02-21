Welcome to hass_apps's documentation!
=====================================


Some useful apps and snippets to empower Home Assistant and AppDaemon
even more.


Apps
----

All apps for AppDaemon can be found inside the ``hass_apps`` directory
of this repository. Each includes a sample configuration in the file
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
   :maxdepth: 2
   :caption: Contents:

   getting-started


Roadmap
-------

Currently, the following enhancements are planned.

* [General] Restructure docs and move them to readthedocs.org.
* [Heaty] Restructure core parts to make maintaining easier.


Donations
---------

I work on this project in my spare time, as most free software developers
do. And of course, I enjoy this work a lot. There is no and will never be
a need to pay anything for using my software.

However, if you want to donate me a cup of coffee, a beer in the evening,
my monthly hosting fees or anything else embellishing my day a little
more, that would be awesome. If you decide doing so, I want to thank you
very much! But please be assured that I'm not presuming anybody to donate,
it's entirely your choice.

|paypal|

.. |paypal| image:: https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif
   :target: https://www.paypal.me/RSchindler

| ETH: 0xa424975a19903F7A6253bA00D5C3F28fACff3C6B
| ZEC: t1RKFyt4qqtqdYfprf8HZoDHRNLNzhe35ED



Indices and tables
==================

.. * :ref:`genindex`
   * :ref:`modindex`

* :ref:`search`
