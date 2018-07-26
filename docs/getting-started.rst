Getting Started
===============

Requirements
------------

Hass-apps is developed under GNU/Linux, but since there are no
platform-specific Python modules used it should run everywhere Python
and AppDaemon are available. However, we'll assume an installation under
GNU/Linux for the rest of this guide. Feel free to apply it to your own
operating system.

The minimum required Python version is 3.5. To find out what you have
installed, run ``python3 --version``. If your version of Python is recent
enough, you may continue with installing.


Installation
------------

In order to use one or more of the included apps, please install the
whole ``hass-apps`` package. Don't worry, only the apps you configure
will be loaded.

It is strongly recommended to install hass-apps into a virtualenv,
separated even from Home Assistant in order to avoid conflicts with
different versions of dependency packages.

Other huge benefits of the virtualenv installation are that you neither
need root privileges nor do you pollute your system.with numerous tiny
packages that are complicated to remove, should you sometime wish to
do so.

The following simple steps will guide you through the installation
process.

1. If you use a distribution like Debian or Ubuntu which doesn't ship
   ``venv`` with Python by default, install it first. Of course you do
   need root privileges for this particular step.

   ::

       sudo apt install python3-venv

2. Then, create the virtualenv. We name it ``ad`` (which stands for
   AppDaemon) in this example and place it in the user's home directory.

   ::

       python3 -m venv ~/ad

3. Activate the virtualenv.

   ::

       cd ~/ad
       source bin/activate

4. Now install some common packages.

   ::

       pip install --upgrade pip setuptools wheel

5. And finally, install hass-apps.

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


A Note for Hass.io Users
~~~~~~~~~~~~~~~~~~~~~~~~

Currently, it's not possible to create a plug & play add-on for hass.io
containing hass-apps, because it needs to be installed into AppDaemon's
container, but there already is work in progress to make the installation
more seamless in the future.

The only actions needed in order to install under hass.io are:

1. Install the appdaemon add-on.
2. Copy the ``hass_apps`` folder into the ``apps`` directory of your
   AppDaemon container. This is also the only thing you need to do when
   upgrading to a newer version of hass-apps.
3. Continue with the configuration as normal.


Configuration
-------------

1. Get yourself a nice cup of coffee or tea. You'll surely need it.
2. Copy the file ``hass_apps/data/hass_apps_loader.py`` into your
   AppDaemon's ``apps`` directory. This is just a stub which imports
   the real app's code.
3. Pick one or more apps you want to use.
4. Copy the contents of ``docs/apps/<some_app>/sample-apps.yaml`` to a
   new YAML file in your AppDaemon's ``apps`` directory and start editing
   it. Adapt the sample configuration as necessary. Documentary comments
   explaining what the different settings mean are included.
   The sample configuration can also be found in the HTML documentation
   for each individual app and copied from there.
5. AppDaemon should have noticed the changes made to ``apps.yaml`` and
   restart its apps automatically.

You're done, enjoy hass-apps!
