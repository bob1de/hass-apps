Upgrading
=========

1. First, ``cd`` into and activate your virtualenv.

   ::

       cd ~/ad
       source bin/activate

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

It is possible to switch between an installation done from PyPi and a
manual installation from the git repository.

To go from a git-based installation to the latest stable release from
PyPi, remove the ``hass_apps`` directory that contains your working
copy of the git repository with a simple ``rm -rf
path/to/your/virtualenv/hass-apps`` and follow the `installation guide`_
from step 3 onwards.

For switching from PyPi to git, just follow the `installation guide`_
from step 3 onwards.

.. _`installation guide`: getting-started.html#installation
