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

When you've installed hass-apps using the
:ref:`getting-started/manual-installation` method, follow these steps
to upgrade it.

1. First, ``cd`` into ``~/appdaemon`` and activate your virtualenv.

   ::

       cd ~/appdaemon
       source venv/bin/activate

2. Upgrade common packages.

   ::

       pip install --upgrade pip setuptools wheel

3. Upgrade hass-apps.

   a) If you installed from PyPi:

      ::

          pip install --upgrade hass-apps

   b) Or, if you installed from the Git repository:

      ::

          cd hass-apps
          git pull
          pip install . --upgrade

Note that AppDaemon doesn't detect changes in the imported modules
automatically and needs to be restarted manually for the upgrade to
take effect.


Switching between PyPi and Git-based Installations
--------------------------------------------------

It is possible to switch between a manual installation done from PyPi
and a manual installation from the git repository.

To go from a git-based installation to the latest stable release from
PyPi, remove the ``hass_apps`` directory that contains your working copy
of the git repository with a simple ``rm -rf ~/appdaemon/hass-apps``
and follow the guide for :ref:`getting-started/manual-installation`
from step 3 onwards.

For switching from PyPi to git, just follow the guide for
:ref:`getting-started/manual-installation` from step 3 onwards.
