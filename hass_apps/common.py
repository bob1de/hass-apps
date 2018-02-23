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


# types of log messages, used for determining the prefix
LOG_PREFIX_NONE = ""
LOG_PREFIX_STATUS = "---"
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

        self.log("{} v{} initialization started"
                 .format(self.Meta.name, self.Meta.version))

        if callable(self.Meta.config_schema):
            self.log("Validating the app's configuration.", level="DEBUG")
            cfg = copy.deepcopy(self.args)
            # Make the app object available during config validation.
            cfg["_app"] = self
            self.cfg = self.Meta.config_schema(cfg)  # pylint: disable=not-callable

        self.initialize_inner()

        self.log("Initialization done")

    def initialize_inner(self) -> None:
        """Overwrite this stub to do the real initialization of the
        particular app."""

        pass

    def set_app_state(
            self, entity_id: str, state: T.Dict[str, T.Any]
    ) -> None:
        """A wrapper to make the new appdaemon.AppDaemon.set_app_state
        available under the appdaemon 2 interface."""

        if self._is_ad3:
            self.AD.set_app_state(entity_id, state)
        else:
            super().set_app_state(entity_id, state)  # pylint: disable=no-member
