"""
Common helpers and functionality used by all apps.
"""

import typing as T

import copy

import voluptuous as vol
import voluptuous.humanize  # pylint: disable=unused-import

from appdaemon.plugins.hass import hassapi
from appdaemon.utils import __version__ as AD_VERSION


# prefixes for log messages
LOG_PREFIX_NONE = ""
LOG_PREFIX_STATUS = "---"
LOG_PREFIX_ALERT = "***"
LOG_PREFIX_WARNING = "!!!"
LOG_PREFIX_INCOMING = "-->"
LOG_PREFIX_OUTGOING = "<--"


class App(hassapi.Hass):  # type: ignore
    """
    This is a sub-class of hassapi.Hass which adds some common
    functionality. It's used by all apps included in hass_apps.
    """

    class Meta:
        """
        A class holding information about the app such as name and version.
        This information is used for logging, for instance.
        """

        name = "UNCONFIGURED"
        version = "0.0.0"
        config_schema = None  # type: T.Optional[T.Callable]

    def log(  # pylint: disable=arguments-differ
        self, msg: str, level: str = "INFO", prefix: T.Optional[str] = None
    ) -> None:
        """Wrapper around super().log() which changes the log level
        from DEBUG to INFO if debug config option is enabled.
        It also adds an appropriate prefix to the log message."""

        level = level.upper()
        if level == "DEBUG" and self.args and self.args.get("debug"):
            level = "INFO"

        if prefix is None:
            if level in ("DEBUG", "INFO"):
                prefix = LOG_PREFIX_STATUS
            elif level in ("WARNING", "ERROR"):
                prefix = LOG_PREFIX_WARNING

        if prefix:
            msg = "{} {}".format(prefix, msg)

        super().log(msg, level=level)

    def initialize(self) -> None:
        """Parses the configuration and logs that initialization
        started/finished. The real work should be done in
        initialize_inner()."""

        # pylint: disable=attribute-defined-outside-init

        def alert(*args: T.Any, **kwargs: T.Any) -> None:
            kwargs["prefix"] = LOG_PREFIX_ALERT
            self.log(*args, **kwargs)

        alert(
            "Welcome to {} {}, running on AppDaemon {}.".format(
                self.Meta.name, self.Meta.version, AD_VERSION
            )
        )
        alert("")
        alert("This is an app from the hass-apps package.")
        alert("  DOCS: https://hass-apps.readthedocs.io/en/stable/")
        alert("")
        alert("You like this app, want to honor the effort put into")
        alert("it, ensure continuous development and support?")
        alert("Then please consider making a donation.")
        alert("  DONATE: https://hass-apps.readthedocs.io/en/stable/#donations")
        alert("Thank you very much and enjoy {}!".format(self.Meta.name))
        alert("")

        if callable(self.Meta.config_schema):
            self.log("Validating the app's configuration.", level="DEBUG")
            cfg = copy.deepcopy(self.args)
            # Make the app object available during config validation.
            cfg["_app"] = self
            try:
                self.cfg = self.Meta.config_schema(cfg)  # pylint: disable=not-callable
            except vol.Invalid as err:
                msg = vol.humanize.humanize_error(cfg, err)
                self.log("Configuration error: {}".format(msg), level="ERROR")
                self.log("Not initializing this app.", level="ERROR")
                return

        self.initialize_inner()

        alert("Initialization done.")

    def initialize_inner(self) -> None:
        """Overwrite this stub to do the real initialization of the
        particular app."""
