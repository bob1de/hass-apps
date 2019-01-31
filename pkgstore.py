#!/usr/bin/env python

import argparse
import copy
import functools
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile


PACKAGE_PARSER = argparse.ArgumentParser(add_help=False)
PACKAGE_PARSER.add_argument(
    "package", nargs="*",
    help="a requirement specifier, like a line of a requirements.txt file",
)
PACKAGE_PARSER.add_argument(
    "-r", "--requirements-file", action="append",
    help="use a requirements.txt file, can be specified multiple times",
)


def prepare_pkgstore(run):
    @functools.wraps(run)
    def wrapper(self, *args, **kwargs):
        self.log.debug("pip command: %s", repr(self.args.pip_command))
        self.log.debug("Additional pip args: %s", repr(self.args.pip_arg))
        if not self.args.pkgstore:
            self.args.pkgstore = os.path.join(
                os.getenv("HOME", "."), ".pypkgstore",
            )
        self.args.pkgstore = os.path.abspath(self.args.pkgstore)
        self.log.debug("pkgstore: %s", repr(self.args.pkgstore))
        self.args.filesdir = os.path.join(self.args.pkgstore, "files")
        if not os.path.isdir(self.args.filesdir):
            os.makedirs(self.args.filesdir)
        self.args.pkgstore_file = os.path.join(self.args.pkgstore, "pkg.json")
        if os.path.exists(self.args.pkgstore_file):
            with open(self.args.pkgstore_file) as file:
                self.args.pkgstore = json.load(file)
        else:
            self.args.pkgstore = {"packages": {}}
        old_pkgstore = copy.deepcopy(self.args.pkgstore)
        result = run(self, *args, **kwargs)
        if result == 0 and self.args.pkgstore != old_pkgstore:
            new_pkgstore_file = "{}.new".format(self.args.pkgstore_file)
            self.log.debug("Writing out modified pkgstore.")
            with open(new_pkgstore_file, "w") as file:
                json.dump(self.args.pkgstore, file, indent=4)
            os.rename(new_pkgstore_file, self.args.pkgstore_file)
        return result
    return wrapper


def prepare_package(run):
    @functools.wraps(run)
    def wrapper(self, *args, **kwargs):
        if not self.args.package:
            self.args.package = []
        for reqfile in self.args.requirements_file or []:
            self.args.package.append(
                "requirements://" + os.path.abspath(reqfile)
            )
        self.log.debug("Packages: %s", repr(self.args.package))
        return run(self, *args, **kwargs)
    return wrapper


class Action:
    action = ""
    description = ""
    parser = argparse.ArgumentParser(add_help=False)

    def __init__(self, args):
        self.args = args
        self.log = logging.getLogger(self.action)
        loglevel = self.args.loglevel.upper()
        self.log.setLevel(loglevel)
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(loglevel)
        formatter = logging.Formatter("[%(name)s] %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.log.addHandler(handler)

    def run(self):
        return 0


class EstablishAction(Action):
    action = "establish"
    description = "Establish or update a local store of files needed to " \
                  "install a package, including all dependencies."
    parser = argparse.ArgumentParser(
        parents=[PACKAGE_PARSER],
        add_help=False,
    )

    @prepare_pkgstore
    @prepare_package
    def run(self):
        result = 0
        for package in self.args.package:
            reqfile = None
            if package.startswith("requirements://"):
                reqfile = package[len("requirements://"):]

            self.log.info("Establishing store for %s ...", repr(package))
            store = self.args.pkgstore["packages"].get(package, {})
            tmpdir = tempfile.mkdtemp()
            self.log.info("Created temporary directory %s.", repr(tmpdir))

            try:
                self.log.info("Collecting packages ...")
                cmd = [
                    self.args.pip_command, "wheel",
                    *(self.args.pip_arg or ()),
                    "--wheel-dir", tmpdir,
                    "--find-links", self.args.filesdir,
                    "--no-deps",
                    *(["-r", reqfile] if reqfile else [package]),
                ]
                _result = subprocess.call(cmd)
                if _result != 0:
                    result = 1
                    continue
                store["roots"] = os.listdir(tmpdir)
                cmd = [
                    self.args.pip_command, "download",
                    *(self.args.pip_arg or ()),
                    "--dest", tmpdir,
                    "--find-links", self.args.filesdir,
                    *[os.path.join(tmpdir, root) for root in store["roots"]],
                ]
                _result = subprocess.call(cmd)
                if _result != 0:
                    result = 1
                    continue

                self.log.info("Copying packages to %s ...",
                              repr(self.args.filesdir))
                store["files"] = os.listdir(tmpdir)
                for file in store["files"]:
                    shutil.copy2(os.path.join(tmpdir, file), self.args.filesdir)
            finally:
                self.log.info("Removing temporary directory ...")
                shutil.rmtree(tmpdir)

            self.log.info("Registered roots %s for %s.",
                          repr(store["roots"]), repr(package))
            self.args.pkgstore["packages"][package] = store

        return result


class InstallAction(Action):
    action = "install"
    description = "Install a package from a previously established, local " \
                  "store of files."
    parser = argparse.ArgumentParser(
        parents=[PACKAGE_PARSER],
        add_help=False,
    )

    @prepare_pkgstore
    @prepare_package
    def run(self):
        roots = []
        for package in self.args.package:
            store = self.args.pkgstore["packages"].get(package)
            if not store:
                self.log.error("No record exists for package %s.",
                               repr(package))
                return 1
            roots.extend(store["roots"])

        self.log.info("Installing %s ...", repr(roots))
        cmd = [
            self.args.pip_command, "install",
            *(self.args.pip_arg or ()),
            "--find-links", self.args.filesdir,
            *(os.path.join(self.args.filesdir, root) for root in roots),
        ]
        result = subprocess.call(cmd)
        if result != 0:
            return 1
        return 0


ACTION_CLASSES = [
    EstablishAction,
    InstallAction,
]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-L", "--log-level", dest="loglevel", default="info",
        choices=["debug", "info", "warning", "error"],
        help="log level, default is 'info'",
    )
    parser.add_argument(
        "-p", "--pip-command", default="pip",
        help="name of the pip executable, default is 'pip'",
    )
    parser.add_argument(
        "--pip-arg", action="append",
        help="additional arguments to pass to the pip call, can be specified "
             "multiple times",
    )
    parser.add_argument(
        "-d", "--pkgstore-dir", dest="pkgstore",
        help="directory to store files in, default is '~/.pypkgstore'",
    )

    p_action = parser.add_subparsers(dest="action")
    p_action.required = True
    for cls in ACTION_CLASSES:
        action_parser = p_action.add_parser(
            cls.action, parents=[cls.parser], description=cls.description,
        )
        action_parser.set_defaults(cls=cls)

    args = parser.parse_args()
    action = args.cls(args)
    result = action.run()
    sys.exit(result)


if __name__ == "__main__":
    main()
