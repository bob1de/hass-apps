#!/usr/bin/env python3


import os
from setuptools import find_packages, setup

from hass_apps import __version__


def read_file(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name = "hass_apps",
    version = __version__,
    description = "Some useful apps for AppDaemon.",
    long_description = read_file("README.rst"),
    url = "https://github.com/efficiosoft/hass-apps",
    author = "Robert Schindler",
    author_email = "r.schindler@efficiosoft.com",
    license = "Apache 2.0",
    packages = find_packages("."),
    package_data = {
        "hass_apps": ["data/*", "*/data/*"],
    },
    install_requires = [
        "appdaemon >= 2.1.12",
        "voluptuous >= 0.10.5",
    ],
    zip_safe = False,
)
