"""
This module contains the Loader class for hass_apps which is meant to
be instantiated and inserted into sys.modules under a desired name.
The Loader instance may then be used by AppDaemon to load any app
included with hass_apps. This mitigates a limitation of Appdaemon,
which can't load apps from submodules.
"""

import importlib
import os
import re
import sys


LOWER_UPPER_PATTERN = re.compile(r"([a-z])([A-Z])")


class Loader:
    """
    This class is a helper which translates attribute access into
    the app type from the submodule the requested attribute corresponds to.
    getattr(..., "FooApp") will, for instance, try to import
    __package__.foo.app and then return FooApp from the imported module.
    """

    def __getattr__(self, attr):
        if attr.endswith("App"):
            package = LOWER_UPPER_PATTERN.sub("\\1_\\2", attr[:-3]).lower()
            app_mod = _import_app_module(package)
            return getattr(app_mod, attr)
        raise AttributeError("no app named {} found".format(repr(attr)))


def _import_app_module(package):
    mod_name = "{}.app".format(package)
    if __package__:
        mod_name = "{}.{}".format(__package__, mod_name)
    return importlib.import_module(mod_name)

def load_all_apps():
    """Imports all apps and makes them available as module attributes."""

    dirpath = os.path.realpath(os.path.dirname(__file__))
    for name in os.listdir(dirpath):
        path = os.path.join(dirpath, name)
        if not os.path.isdir(path):
            continue
        try:
            app_mod = _import_app_module(name)
        except ImportError:
            pass
        else:
            attr = []
            for part in name.split("_"):
                attr.append(part.capitalize())
            attr = "{}App".format("".join(attr))
            setattr(sys.modules[__name__], attr, getattr(app_mod, attr))
