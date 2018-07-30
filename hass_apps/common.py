"""
Common helpers and functionality used by all apps.
"""

import typing as T

import copy

try:
    from appdaemon.plugins.hass import hassapi
except ImportError:
    from appdaemon import appapi
    AppBase = appapi.AppDaemon
    _IS_AD3 = False
else:
    AppBase = hassapi.Hass
    _IS_AD3 = True


# prefixes for log messages
LOG_PREFIX_NONE = ""
LOG_PREFIX_STATUS = "---"
LOG_PREFIX_ALERT = "***"
LOG_PREFIX_WARNING = "!!!"
LOG_PREFIX_INCOMING = "-->"
LOG_PREFIX_OUTGOING = "<--"


class App(AppBase):
    """
    This is a sub-class of hassapi.Hass (for appdaemon >= 3.0.0) or
    appapi.AppDaemon (for appdaemon < 3.0.0) which adds some common
    functionality. It's used by all apps included in hass_apps.
    """

    # will be True for appdaemon >= 3, False otherwise
    _is_ad3 = _IS_AD3

    class Meta:
        """
        A class holding information about the app such as name and version.
        This information is used for logging, for instance.
        """

        name = "UNCONFIGURED"
        version = "0.0.0"
        config_schema = None  # type: T.Optional[T.Callable]

    def log(  # pylint: disable=arguments-differ
            self, msg: str, level: str = "INFO",
            prefix: T.Optional[str] = None
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

        alert("Welcome to {} (version {})!"
              .format(self.Meta.name, self.Meta.version))
        alert("")
        alert("This is an app from the hass-apps package.")
        alert("  DOCS: https://hass-apps.readthedocs.io/en/stable/")
        alert("")
        alert("If you like this app and want to honor the effort put "
              "into it,")
        alert("please consider a donation.")
        alert("  DONATE: https://hass-apps.readthedocs.io/en/stable/#donations")
        alert("Thank you very much and enjoy {}!".format(self.Meta.name))
        alert("")

        if callable(self.Meta.config_schema):
            self.log("Validating the app's configuration.", level="DEBUG")
            cfg = copy.deepcopy(self.args)
            # Make the app object available during config validation.
            cfg["_app"] = self
            self.cfg = self.Meta.config_schema(cfg)  # pylint: disable=not-callable

        self.initialize_inner()

        alert("Initialization done.")

    def initialize_inner(self) -> None:
        """Overwrite this stub to do the real initialization of the
        particular app."""

        pass
