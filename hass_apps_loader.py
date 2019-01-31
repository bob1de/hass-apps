# Place this file in the root of your apps directory and copy
# pkgstore.py one level above this file, so that it resides beside
# the apps directory itself.
# The URL in the PACKAGES variable can be changed to e.g. "hass-apps"
# to install the stable version, or anything else.
# Finally, rename an eventually existing requirements.txt file to
# something like requirements.txt.ignore to have it no longer respected,
# if you use the hassio addon, remove any "python_packages" from the
# add-on config and restart AppDaemon.


import os
import subprocess
BASE = os.path.join(os.path.dirname(__file__), "..")
PKGSTORE = os.path.join(BASE, ".pypkgstore")
SCRIPT = [
    "python3", os.path.join(BASE, "pkgstore.py"),
    "-d", PKGSTORE, "-p", "pip3",
    "--pip-arg=--no-cache-dir",
    "--pip-arg=--disable-pip-version-check",
]
PACKAGES = [
    "wheel", "pip", "setuptools",
    "https://github.com/efficiosoft/hass-apps/archive/master.zip",
]
for pkg in PACKAGES:
    subprocess.call([*SCRIPT, "establish", pkg])
    subprocess.call([*SCRIPT, "--pip-arg=--upgrade", "install", pkg])


# This is just a stub which makes the app classes available for AppDaemon.
from hass_apps.loader import *
