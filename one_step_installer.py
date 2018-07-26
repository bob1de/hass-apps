#!/usr/bin/env python3

"""Automated installer script for hass-apps."""

import logging
import os
import shutil
import subprocess
import sys
from distutils.version import StrictVersion


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


def main():  # pylint: disable=too-many-branches,too-many-statements
    """Main process."""

    logging.basicConfig(format="[{levelname:^7s}]  {message}",
                        style="{", level=logging.INFO)

    logging.info("Welcome to the automated hass-apps installer!")
    logging.info("")
    logging.info("This installer will install the latest stable version "
                 "of hass-apps into a directory of your choice.")
    logging.info("")

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

    # create virtualenv
    while True:
        dest = os.path.abspath(os.path.join(".", "ad"))
        dest = read("Destination directory", dest)
        dest = os.path.abspath(dest)
        try:
            if os.path.exists(dest):
                logging.warning("%s already exists.", repr(dest))
                if read("Should I try to remove it? (y/n)", "n") != "y":
                    logging.info("Then choose another location please.")
                    continue
                shutil.rmtree(dest)
            logging.info("Creating virtualenv at %s.", repr(dest))
            import venv
            venv.create(dest, with_pip=True)
        except OSError as err:
            logging.error(err)
        else:
            break

    import shlex
    activate = shlex.quote(os.path.join(dest, "bin", "activate"))

    logging.info("Installing common packages.")
    cmd = ["sh", "-c", ". {}; pip install --upgrade pip setuptools wheel"
           .format(activate)]
    while True:
        if subprocess.call(cmd) != 0:
            logging.error("The pip call seems to have failed.")
            if read("Should I retry? (y/n)", "y") != "y":
                fatal("Then I'll give up here.")
            continue
        break

    logging.info("Installing hass-apps.")
    cmd = ["sh", "-c", ". {}; pip install --upgrade hass-apps"
           .format(activate)]
    while True:
        if subprocess.call(cmd) != 0:
            logging.error("The pip call seems to have failed.")
            if read("Should I retry? (y/n)", "y") != "y":
                fatal("Then I'll give up here.")
            continue
        break

    logging.info("")
    logging.info("has-apps has successfully been installed!")
    logging.info("")
    logging.info("You can run AppDaemon with the following command:")
    logging.info("")
    ad_cmd = shlex.quote(os.path.join(dest, "bin", "appdaemon"))
    logging.info("    %s", ad_cmd)
    logging.info("")
    logging.info("Please read http://hass-apps.readthedocs.io/en/stable/"
                 "getting-started.html#configuration for the next steps.")
    logging.info("")
    logging.info("Have fun!")
    logging.info("")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
