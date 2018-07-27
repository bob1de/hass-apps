Upgrading
=========

As with every software, hass-apps and its dependencies need to be upgraded
regularly in order to get the latest fixes, security updates, feature
additions and enhancements that are incorporated every now and then.


Upgrade Using the One-Step Installer
------------------------------------

If you used the `One-Step Installer
<getting-started.html#one-step-installer>`_ for setting hass-apps up,
you can simply re-run it and specify the same location as you did when
installing. It'll then remove the old version and install a fresh
up-to-date copy of hass-apps for you. All configuration data in the
``conf`` sub-directory will of course be retained.


Upgrade Manually
----------------

1. First, ``cd`` into ``~/ad`` and activate your virtualenv.

   ::

       cd ~/ad
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

It is possible to switch between an installation done from PyPi and a
manual installation from the git repository.

To go from a git-based installation to the latest stable release from
PyPi, remove the ``hass_apps`` directory that contains your working
copy of the git repository with a simple ``rm -rf ~/ad/hass-apps``
and follow the `Installation Guide`_ from step 3 onwards.

For switching from PyPi to git, just follow the `Installation Guide`_
from step 3 onwards.

.. _`Installation Guide`: getting-started.html#installation
