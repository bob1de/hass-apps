import sys

from hass_apps.loader import Loader

sys.modules[__name__] = Loader()
