Getting started
===============

Installation
------------

In order to use one or more of the included apps, please install the
whole ``hass_apps`` package. Don't worry, only the apps you configure
will be loaded.

The minimum required Python version is 3.5. If you are unsure what you
have installed, run ``python3 --version``. If your version of Python is
recent enough, you may continue with installing.

Install from PyPi:

::

    pip3 install hass_apps

Or clone the GitHub repository to get even the latest changes:

::

    git clone https://github.com/efficiosoft/hass_apps
    cd hass_apps
    pip3 install . --upgrade


A note for hass.io users
~~~~~~~~~~~~~~~~~~~~~~~~

Currently, it's not possible to create a plug & play add-on for hass.io
containing hass-apps, because it needs to be installed into AppDaemon's
container.

The only actions needed in order to install under hass.io are:

1. Install the appdaemon add-on.
2. Copy the ``hass_apps`` folder and the file
   ``hass_apps/data/hass_apps_loader.py`` into the ``apps`` directory of
   your AppDaemon container. This is also the only thing you need to do
   when upgrading to a newer version of hass-apps.
3. Continue with the configuration as normal.


Configuration
-------------

1. Get yourself a nice cup of coffee or tea. You'll surely need it.
2. Copy the file ``hass_apps/data/hass_apps_loader.py`` into your
   AppDaemon's ``apps`` directory. This is just a stub which imports
   the real app's code.
3. Pick one or more apps you want to use.
4. Copy the contents of ``docs/apps/<some_app>/sample-apps.yaml``
   to your ``apps.yaml`` file and adapt it as necessary. The example
   files also contain documentation comments explaining what the
   different settings mean.
   The sample configuration can also be found in the HTML docs for
   each individual app and copied from there.
5. AppDaemon should have noticed the changes made to ``apps.yaml`` and
   restart its apps automatically.

You're done!


Upgrade
-------

Simply pull upgrades from PyPi:

::

    pip3 install --upgrade hass_apps

Or, if you installed from the git repository:

::

    cd /path/to/your/clone/of/the/repository
    git pull
    pip3 install . --upgrade

Note that AppDaemon doesn't detect changes in the imported modules
automatically and needs to be restarted manually after an upgrade.
