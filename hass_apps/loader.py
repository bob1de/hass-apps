"""
This module contains code that dynamically scans for available apps
at module load time. For all apps found, a loader is generated which,
when called, imports the particular app and behaves like the app
class itself. The loaders are made available as module attributes
under the same name the corresponding app classes would have
(e.g. HeatyApp).
The __all__ list is populated with these loaders, hence a wildcard
import will fetch them all.
"""

import typing as T
import types

import importlib
import os
import sys


def _import_app_module(package: str) -> types.ModuleType:
    mod_name = "{}.app".format(package)
    if __package__:
        mod_name = "{}.{}".format(__package__, mod_name)
    return importlib.import_module(mod_name)

def _build_app_loader(app_package: str, app_class_name: str) -> T.Callable:
    def _proxy_loader(*args, **kwargs):  # type: ignore
        app_mod = _import_app_module(app_package)
        app_class = getattr(app_mod, app_class_name)
        return app_class(*args, **kwargs)

    return _proxy_loader

def _generate_app_loaders() -> T.Iterable[T.Tuple[str, T.Callable]]:
    """Scans for apps and yields tuples of the app class name and a
    deferred loader for each app found."""

    dirpath = os.path.realpath(os.path.dirname(__file__))
    for name in os.listdir(dirpath):
        path = os.path.join(dirpath, name)
        if not os.path.isdir(path) or \
           not os.path.isfile(os.path.join(path, "app.py")):
            continue
        parts = [part.capitalize() for part in name.split("_")]
        attr = "{}App".format("".join(parts))
        loader = _build_app_loader(name, attr)
        yield attr, loader


# make app loaders available as module attributes
__all__ = []
for _attr, _loader in _generate_app_loaders():
    setattr(sys.modules[__name__], _attr, _loader)
    __all__.append(_attr)
