#!/usr/bin/env python3

"""Automated installer script for hass-apps."""

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import time
from distutils.version import StrictVersion


APPS = (
    "heaty",
    "motion_light",
)
BASE_URL = "https://raw.githubusercontent.com/efficiosoft/hass-apps/master/"
DOCS_URL = "https://hass-apps.readthedocs.io/en/stable/"
OSI_FILENAME = "one_step_installer.py"
MIN_PYVERSION = StrictVersion("3.5")
SUPPORTED_PLATFORMS = ("linux",)


def fatal(*args):
    """Passes the supplied arguments to logging.error() and exits."""

    logging.error(*args)
    sys.exit(1)

def read(prompt, default=None):
    """Reads a string from stdin."""

    if default is None:
        prompt = "{}: ".format(prompt)
    else:
        prompt = "{} [leave empty for {}]: ".format(prompt, repr(default))

    while True:
        data = input(prompt).strip()
        if data:
            return data
        if default is not None:
            return default


def install():  # pylint: disable=too-many-statements
    """Install hass-apps."""

    # try to detect whether this could be an upgrade
    path = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(path, "venv")):
        default_dest_dir = path
    else:
        default_dest_dir = os.path.abspath("appdaemon")

    while True:
        dest_dir = read("Destination directory", default_dest_dir)
        dest_dir = os.path.abspath(dest_dir)
        logging.info("Installing to %s.", repr(dest_dir))
        if read("Is this correct? (y/n)") != "y":
            continue

        try:
            if os.path.exists(dest_dir):
                logging.info("Installation directory already exists, "
                             "I'll keep it's contents.")
            else:
                logging.info("Creating installation directory.")
                os.makedirs(dest_dir)

            venv_dir = os.path.join(dest_dir, "venv")
            if os.path.exists(venv_dir):
                logging.info("The sub-directory for the virtualenv %s "
                             "already exists.", repr(venv_dir))
                logging.info("It normally only contains the installed "
                             "software and no user data.")
                logging.info("This usually means that hass-apps is already "
                             "installed there.")
                if read("Remove it and re-install the latest version? (y/n)") != "y":
                    logging.info("Ok, not re-installing.")
                    logging.info("Maybe you just want to run the "
                                 "configuration assistant?")
                    if read("Just run the config assistant (y/n)") == "y":
                        return dest_dir, venv_dir
                    logging.info("Then choose another location please.")
                    continue
                logging.info("Removing the 'venv' sub-directory.")
                shutil.rmtree(venv_dir)

            logging.info("Creating virtualenv at %s.", repr(venv_dir))
            import venv
            venv.create(venv_dir, with_pip=True)
        except OSError as err:
            logging.error(err)
        else:
            break

    import shlex
    activate = shlex.quote(os.path.join(venv_dir, "bin", "activate"))

    logging.info("Installing common packages.")
    cmd = ["sh", "-c", ". {}; pip install --upgrade pip setuptools wheel"
           .format(activate)]
    while True:
        if subprocess.call(cmd) != 0:
            logging.error("The pip call seems to have failed.")
            if read("Retry? (y/n)", "y") != "y":
                fatal("Then I'll give up here.")
            continue
        break

    logging.info("Installing hass-apps.")
    cmd = ["sh", "-c", ". {}; pip install --upgrade hass-apps"
           .format(activate)]
    while True:
        if subprocess.call(cmd) != 0:
            logging.error("The pip call seems to have failed.")
            if read("Retry? (y/n)", "y") != "y":
                fatal("Then I'll give up here.")
            continue
        break

    logging.info("")
    logging.info("The installation has finished.")
    logging.info("")
    return dest_dir, venv_dir


def configure(dest_dir):
    """Create configuration."""

    conf_dir = os.path.join(dest_dir, "conf")

    try:
        if os.path.exists(conf_dir):
            logging.info("The configuration directory %s already exists.",
                         repr(conf_dir))
            logging.info("I could back it up and create a fresh one.")
            if read("Create a fresh sample configuration? (y/n)") != "y":
                return None
            backup_dir = "{}.backup_{}" \
                         .format(conf_dir, time.strftime("%Y-%m-%d_%H-%M-%S"))
            logging.info("Moving %s to %s.", repr(conf_dir), repr(backup_dir))
            os.rename(conf_dir, backup_dir)
        else:
            logging.info("Do you want to have a sample configuration for "
                         "hass-apps and AppDaemon created in %s?",
                         repr(conf_dir))
            if read("Create a configuration? (y/n)", "y") != "y":
                return None
        logging.info("Creating configuration directories and files.")
        os.makedirs(conf_dir)
        apps_dir = os.path.join(conf_dir, "apps")
        os.makedirs(apps_dir)
        with open(os.path.join(conf_dir, "appdaemon.yaml"), "w") as file:
            file.write("# Place your AppDaemon configuration here.\n"
                       "#\n"
                       "# See https://appdaemon.readthedocs.io/en/stable/"
                       "INSTALL.html#configuration for samples.\n")
    except OSError as err:
        logging.error(err)
        return None

    logging.info("I'm now fetching sample configuration files for the "
                 "apps you'd like to use.")
    files = [
        ("hass_apps/data/hass_apps_loader.py",
         os.path.join("apps", "hass_apps_loader.py")),
    ]
    for app in APPS:
        if read("Do you want to use the app {}? (y/n)".format(app), "n") == "y":
            files.append(
                ("docs/apps/{}/sample-apps.yaml".format(app),
                 os.path.join("apps", "{}.yaml".format(app))),
            )

    logging.info("Downloading configuration files.")
    import urllib.request
    for url, filename in files:
        while True:
            try:
                url = urllib.request.urljoin(BASE_URL, url)
                filename = os.path.join(conf_dir, filename)
                urllib.request.urlretrieve(url, filename=filename)
            except OSError as err:
                logging.error(err)
                if read("Retry? (y/n)", "y") != "y":
                    logging.warning("Ok, leaving you back with an incomplete "
                                    "configuration!")
                    return None
            else:
                break

    logging.info("")
    logging.info("The sample configuration has been set up.")
    logging.info("")
    return conf_dir


def upgrade_installer():
    """Upgrades the installer to the latest version and restart if necessary."""

    logging.info("Checking for a newer One-Step Installer.")

    try:
        with open(__file__, "rb") as file:
            our_hash = hashlib.md5(file.read()).hexdigest()
    except OSError as err:
        logging.error(err)
        logging.warning("Ok, not upgrading the installer.")
        return

    import urllib.request
    osi_url = urllib.request.urljoin(BASE_URL, OSI_FILENAME)
    while True:
        try:
            filename = urllib.request.urlretrieve(osi_url)[0]
            with open(filename, "rb") as file:
                latest_hash = hashlib.md5(file.read()).hexdigest()
        except OSError as err:
            logging.error(err)
            if read("Retry? (y/n)", "y") != "y":
                logging.warning("Ok, not upgrading the installer.")
                return
        else:
            break

    if our_hash == latest_hash:
        logging.info("This is the latest version of the installer.")
        result = None
    else:
        logging.info("A new installer is available, running that instead.")
        cmd = ["python3", filename, "--no-upgrade"]
        try:
            result = subprocess.call(cmd)
        except KeyboardInterrupt:
            result = 1

    try:
        os.remove(filename)
    except OSError:
        pass

    if result is None:
        return
    sys.exit(result)


def main():  # pylint: disable=too-many-branches,too-many-statements
    """Main process."""

    logging.basicConfig(format="[{levelname:^7s}]  {message}",
                        style="{", level=logging.INFO)

    # check python version
    version = StrictVersion("{}.{}.{}".format(sys.version_info.major,
                                              sys.version_info.minor,
                                              sys.version_info.micro))
    if version < MIN_PYVERSION:
        fatal("The minimum required Python version is %s, yours is %s. "
              "Please upgrade Python and run this installer again.",
              MIN_PYVERSION, version)

    # check platform
    if sys.platform not in SUPPORTED_PLATFORMS:
        fatal("Your platform %s isn't supported by this installer. "
              "You could try to install hass-apps manually with the "
              "instructions from: "
              "http://hass-apps.readthedocs.io/en/stable/"
              "getting-started.html#manual-installation",
              repr(sys.platform))

    is_root = os.environ.get("USER") == "root"
    if is_root:
        logging.warning("You are running the installer as root. This is "
                        "neither required nor recommended.")
        if read("Are you sure you want to continue? (y/n)", "n") != "y":
            fatal("Aborting.")

    if len(sys.argv) != 2 or sys.argv[1] != "--no-upgrade":
        upgrade_installer()

    logging.info("")
    logging.info("")
    logging.info("Welcome to the automated hass-apps installer!")
    logging.info("")
    logging.info("This installer will install the latest stable version "
                 "of AppDaemon, bundled with hass-apps, to a directory "
                 "of your choice.")
    logging.info("It won't touch anything outside that directory or "
                 "pollute your system otherwise.")
    logging.info("")

    dest_dir, venv_dir = install()

    conf_dir = configure(dest_dir)

    osi_filename = os.path.join(dest_dir, OSI_FILENAME)
    try:
        assert os.path.samefile(__file__, osi_filename)
    except (AssertionError, OSError):
        logging.info("Copying the One-Step Installer.")
        try:
            shutil.copy(__file__, osi_filename)
            os.chmod(osi_filename, 0o755)
        except OSError as err:
            logging.error(err)
            osi_filename = None

    import shlex
    logging.info("")
    logging.info("Congratulations, you made your way through the installer!")
    logging.info("")
    ad_cmd = [os.path.join(venv_dir, "bin", "appdaemon"), "-c"]
    if conf_dir:
        logging.info("The configuration assistant has placed a number of "
                     "sample configuration files in %s.", conf_dir)
        logging.info("Please have a look and adapt them to your needs.")
        ad_cmd.append(conf_dir)
    else:
        logging.info("You decided not to complete the configuration assistant.")
        logging.info("Please create the configuration files for AppDaemon "
                     "and your desired apps manually.")
        ad_cmd.append("path_to_config_directory")
    logging.info("")
    logging.info("You can run AppDaemon with the following command:")
    logging.info("")
    logging.info("    %s", " ".join([shlex.quote(part) for part in ad_cmd]))
    logging.info("")
    logging.info("You may re-run this installer from time to time in "
                 "order to keep hass-apps up-to-date.")
    if osi_filename:
        logging.info("Use the following command for upgrading:")
        logging.info("")
        logging.info("    %s", shlex.quote(osi_filename))
    logging.info("")
    logging.info("If you experience any difficulties, have a look at the "
                 "documentation at:")
    logging.info("    %s", DOCS_URL)
    logging.info("")
    logging.info("Have fun!")
    logging.info("")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
