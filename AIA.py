#!/usr/bin/env python3
# pylint: disable=invalid-name

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
GH_OWNER = "efficiosoft"
GH_REPO = "hass-apps"
RAW_URL = "https://raw.githubusercontent.com/{}/{}/{}/" \
          .format(GH_OWNER, GH_REPO, "{}")
DOCS_URL = "https://hass-apps.readthedocs.io/en/stable/"
AIA_FILENAME = "AIA.py"
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


def install():  # pylint: disable=too-many-branches,too-many-statements
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
        if read("Is this correct? (y/n)", "y") != "y":
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
                logging.info("This usually means that hass-apps is already "
                             "installed there.")
                logging.info("You may either upgrade the existing "
                             "installation, remove it and re-install from "
                             "scratch or keep the current state.")
                logging.info("Even when re-installing, only the `venv` "
                             "sub-directory is going to be wiped. Your "
                             "configuration is always safe.")
                choice = None
                while choice not in ("u", "r", "k"):
                    choice = read("[u]pgrade, [r]e-install or [k]eep?", "u")
                if choice == "u":
                    break
                elif choice == "r":
                    logging.info("Removing the 'venv' sub-directory.")
                    shutil.rmtree(venv_dir)
                elif choice == "k":
                    logging.info("Ok, not upgrading.")
                    logging.info("Maybe you just want to run the "
                                 "configuration assistant?")
                    if read("Just run the config assistant (y/n)") == "y":
                        return dest_dir, venv_dir
                    logging.info("Then choose another location please.")
                    continue
                else:
                    continue

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

    logging.info("I could install additional packages from the Python "
                 "Package Index (PyPi) for you.")
    logging.info("This is only needed when you write own AppDaemon apps "
                 "that require third-party modules.")
    logging.info("Leave the default if you are unsure.")
    modules_filename = os.path.join(dest_dir, "requirements.txt")
    try:
        with open(modules_filename) as file:
            modules = file.read().split()
    except OSError:
        modules = []
    while True:
        default = " ".join(modules) if modules else "none"
        choice = read("Additional packages (space-separated) or 'none'",
                      default)
        modules = [] if choice == "none" else choice.split()
        try:
            if not modules:
                os.remove(modules_filename)
                break
            logging.info("Installing these additional packages:")
            logging.info("    %s", ", ".join(modules))
            if read("Is this correct? (y/n)", "y") != "y":
                continue
            cmd = ["sh", "-c", ". {}; pip install --upgrade {}"
                   .format(activate,
                           " ".join(shlex.quote(mod) for mod in modules))]
            if subprocess.call(cmd) != 0:
                logging.error("The pip call seems to have failed.")
                if read("Retry? (y/n)", "y") == "y":
                    continue
            with open(modules_filename, "w") as file:
                file.write("\n".join(modules))
        except OSError:
            pass
        break

    logging.info("")
    logging.info("The installation has finished.")
    logging.info("")
    return dest_dir, venv_dir


def configure(dest_dir, release_tag):
    """Create configuration."""

    conf_dir = os.path.join(dest_dir, "conf")

    try:
        if os.path.exists(conf_dir):
            logging.info("The configuration directory %s already exists.",
                         repr(conf_dir))
            logging.info("I could back it up and create a fresh one, "
                         "or you keep the existing.")
            if read("Create a fresh sample configuration? (y/n)", "n") != "y":
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
                url = urllib.request.urljoin(RAW_URL.format(release_tag), url)
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


def fetch_latest_release_tag():
    """Returns the git tag of the latest stable release."""

    logging.info("Fetching the list of releases.")

    import urllib.request
    url = "https://api.github.com/repos/{}/{}/tags".format(GH_OWNER, GH_REPO)
    try:
        with urllib.request.urlopen(url) as res:
            json_data = res.read().decode(res.headers.get_content_charset())
    except OSError as err:
        logging.error(err)
        fatal("Couldn't fetch the release list.")

    import json
    try:
        data = json.loads(json_data)
        assert isinstance(data, list)
        assert data
        assert "name" in data[0]
        release_tag = data[0]["name"]
    except AssertionError:
        fatal("The tag list is mis-formatted.")

    logging.info("The latest release is %s.", release_tag)
    return release_tag


def upgrade_installer(release_tag):
    """Upgrades the installer to the latest version and restart if necessary."""

    logging.info("Checking for a newer Auto-Install Assistant.")

    try:
        with open(__file__, "rb") as file:
            our_hash = hashlib.md5(file.read()).hexdigest()
    except OSError as err:
        logging.error(err)
        logging.warning("Ok, not upgrading the installer.")
        return

    import urllib.request
    aia_url = urllib.request.urljoin(RAW_URL.format(release_tag), AIA_FILENAME)
    while True:
        try:
            filename = urllib.request.urlretrieve(aia_url)[0]
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
        cmd = ["python3", filename, "--no-upgrade",
               "--release-tag={}".format(release_tag)]
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

    release_tag = None
    for arg in sys.argv[1:]:
        if arg.startswith("--release-tag="):
            release_tag = arg[14:]
    if not release_tag:
        release_tag = fetch_latest_release_tag()

    if "--no-upgrade" not in sys.argv[1:]:
        upgrade_installer(release_tag)

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
    logging.info("The version of hass-apps chosen is %s.", release_tag)
    logging.info("")

    dest_dir, venv_dir = install()

    conf_dir = configure(dest_dir, release_tag)

    aia_filename = os.path.join(dest_dir, AIA_FILENAME)
    try:
        assert os.path.samefile(__file__, aia_filename)
    except (AssertionError, OSError):
        logging.info("Copying the Auto-Install Assistant.")
        try:
            shutil.copy(__file__, aia_filename)
            os.chmod(aia_filename, 0o755)
        except OSError as err:
            logging.error(err)
            aia_filename = None

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
    if aia_filename:
        logging.info("Use the following command for upgrading:")
        logging.info("")
        logging.info("    %s", shlex.quote(aia_filename))
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
