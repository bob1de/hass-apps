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
