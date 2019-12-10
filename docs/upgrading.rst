Upgrading
=========

As with every software, hass-apps and its dependencies need to be upgraded
regularly in order to get the latest fixes, security updates, feature
additions and enhancements that are incorporated every now and then.


Upgrade in Hass.io or Docker
----------------------------

When you followed the tutorial for
:ref:`getting-started/installation-in-hassio`
or :ref:`getting-started/installation-in-docker` and decided for
automatic upgrading, you don't need to do anything. Just ensure that
your configuration stays compatible with the new hass-apps versions
and restart the AppDaemon container (or the add-on in case of hass.io)
from time to time.

If you explicitly decided for a specific version of hass-apps, change
the version number in the ``requirements.txt`` file you once created
(or the add-on settings) to the latest one and restart AppDaemon.


Upgrade Manually
----------------

When you've installed hass-apps using the :ref:`getting-started/manual-installation`
method, simply repeat the procedure from step 3 onwards in order to upgrade.

.. note::

   AppDaemon doesn't detect changes in the imported modules automatically and needs
   to be restarted manually for the upgrade to take effect.
