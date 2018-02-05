"""
Common helpers and functionality used by all apps.
"""

try:
    from appdaemon.plugins.hass import hassapi
except ImportError:
    from appdaemon import appapi
    AppBase = appapi.AppDaemon
    _IS_AD3 = False
else:
    AppBase = hassapi.Hass
    _IS_AD3 = True


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

    def set_app_state(self, entity_id, state):
        """A wrapper to make the new appdaemon.AppDaemon.set_app_state
        available under the appdaemon 2 interface."""

        if self._is_ad3:
            return self.AD.set_app_state(entity_id, state)
        return super(App, self).set_app_state(entity_id, state)  # pylint: disable=no-member
