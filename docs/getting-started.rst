Getting started
===============

In order to use one or more of the included apps, please install the
whole ``hass-apps`` package. Don't worry, only the apps you configure
will be loaded.

The minimum required Python version is 3.5. If you are unsure what you
have installed, run ``python3 --version``. If your version of Python is
recent enough, you may continue with installing.


Installation
------------

It is strongly recommended to install hass-apps into a virtualenv, separated
even from Home Assistant in order to avoid conflicts with different versions
of dependency packages. These steps will guide you through the installation
process.

1. If you use a distribution like Debian or Ubuntu which doesn't ship
   ``venv`` with Python by default, install it first:

   ::

       sudo apt install python3-venv

2. Then, create and activate the virtualenv. We name it ``ad`` (which stands
   for AppDaemon) in this example and place it in the user's home directory.

   ::

       python3 -m venv ~/ad
       cd ~/ad
       source bin/activate

3. Now install some common packages.

   ::

       pip install --upgrade pip setuptools wheel

4. And finally, install hass-apps.

   a) Install from PyPi (preferred).

      ::

          pip install --upgrade hass-apps

   b) Or, as an alternative, clone the Git repository to get even the
      latest changes. But please keep in mind that this shouldn't be
      considered stable and isn't guaranteed to work all the time. Don't
      use the development version in production unless you have a good
      reason to do so.

      ::

          git clone https://github.com/efficiosoft/hass-apps
          cd hass-apps
          pip install . --upgrade


A note for hass.io users
~~~~~~~~~~~~~~~~~~~~~~~~

Currently, it's not possible to create a plug & play add-on for hass.io
containing hass-apps, because it needs to be installed into AppDaemon's
container, but there already is work in progress to make the installation
more seamless in the future.

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
