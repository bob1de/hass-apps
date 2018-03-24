Upgrading
=========

First, ``cd`` into and activate your virtualenv.

::

    cd ad
    source bin/activate

Now, simply pull upgrades from PyPi.

::

    pip install --upgrade pip setuptools wheel
    pip install --upgrade hass-apps

Or, if you installed from the git repository.

::

    cd hass-apps
    git pull
    pip install --upgrade pip setuptools wheel
    pip install . --upgrade

Note that AppDaemon doesn't detect changes in the imported modules
automatically and needs to be restarted manually after an upgrade.
