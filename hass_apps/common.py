"""
Common helpers and functionality used by all apps.
"""

from appdaemon import appapi


class App(appapi.AppDaemon):
    """
    This is an extension of appdaemon.appapi.AppDaemon which adds some
    common functionality. It's used by all apps included in hass_apps.
    """

    class Meta:
        """
        A class holding information about the app such as name and version.
        This information is used for logging, for instance.
        """

        name = "UNCONFIGURED"
        version = "0.0.0"
        config_schema = None

    def log(self, msg, level="INFO"):
        """Wrapper around Appdaemon.log() which changes the log level
        from DEBUG to INFO if debug config option is enabled."""

        if level.upper() == "DEBUG" and self.args and self.args.get("debug"):
            level = "INFO"
        return super(App, self).log(msg, level=level)

    def initialize(self):
        """Parses the configuration and logs that initialization
        started/finished. The real work should be done in
        initialize_inner()."""

        # pylint: disable=attribute-defined-outside-init

        self.log("--- {} v{} initialization started"
                 .format(self.Meta.name, self.Meta.version))

        if self.Meta.config_schema is not None:
            # pylint: disable=not-callable
            self.cfg = self.Meta.config_schema(self.args)

        self.initialize_inner()

        self.log("--- Initialization done")

    def initialize_inner(self):
        """Overwrite this stub to do the real initialization of the
        particular app."""

        pass
