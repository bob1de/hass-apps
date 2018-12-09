#!/usr/bin/env python


import os
from setuptools import find_packages, setup

from hass_apps import __version__


def read_file(filename):
    """Returns content of the given file. Path must be relative to
    this file."""

    with open(os.path.join(os.path.dirname(__file__), filename)) as file:
        return file.read()


setup(
    name = "hass-apps",
    version = __version__,
    description = "A collection of useful apps for AppDaemon + "
                  "Home Assistant.",
    long_description = read_file("README.rst"),
    author = "Robert Schindler",
    author_email = "r.schindler@efficiosoft.com",
    url = "https://github.com/efficiosoft/hass-apps",
    license = "Apache 2.0",
    packages = find_packages("."),
    install_requires = [
        "appdaemon >= 3.0",
        "observable >= 1.0",
        "voluptuous >= 0.11",
    ],
    zip_safe = False,
)
