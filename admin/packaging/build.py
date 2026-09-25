#!/usr/bin/env python3
"""Builds the Debian package this tool installs as.

    python3 packaging/build.py [--into DIRECTORY]

It lays the files out the way they will sit on the machine, writes the control
file, and calls dpkg-deb. That is the whole of it, and it is deliberate: this
package copies Python, static files and five unit files into place. Nothing is
compiled, nothing is patched and nothing is generated at install time, so the
debhelper machinery would be a build system around a copy.

The version is `previously.server.VERSION` and is read from there rather than
written down again here. A package whose version disagrees with what the tool
reports is one nobody can ask a useful question about.
"""

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ADMIN = HERE.parent

#: What the package is called, which is what the service, its directory under
#: /usr/lib and its state under /var/lib are already called.
NAME = "previously"

#: Nothing here is compiled: Python on the standard library, static files, and
#: xterm in web/vendor. A package that names an architecture it does not need
#: is one that cannot be installed on anything else for no reason.
ARCHITECTURE = "all"

#: What the service shells out to, and where each is used. A dependency that
#: is missing shows up as a feature that quietly does nothing, so they are
#: declared rather than discovered.
#:
#:   python3          the service itself
#:   xdotool          the keys that reach the emulator, in screen.press
#:   imagemagick      the picture of the screen, in grab.photographed
#:   openssh-client   the login behind the terminal, in terminal.Session
#:   procps           pgrep and ps, which say whether the emulator runs
DEPENDS = ["python3 (>= 3.11)", "xdotool", "imagemagick", "openssh-client",
           "procps", "systemd"]

#: The emulator this administers. A recommendation rather than a dependency,
#: because it comes from an archive this package knows nothing about, and an
#: installation that cannot find it should still put the tool in place.
RECOMMENDS = ["previous"]

#: Where everything goes. The service reads these paths from its own settings,
#: and settings.py is what decides them; these are the same paths written as
#: the layout of a package.
LIB = "usr/lib/" + NAME
UNITS = "lib/systemd/system"
CONFIG = "etc/" + NAME

#: The unit files, and which of them is the service itself. The other four are
#: how the board is switched off and restarted without this service holding
#: any privilege: it leaves a file in its runtime directory and a path unit
#: running as root does the one thing that file means.
SERVICE = NAME + ".service"
UNIT_FILES = (SERVICE,
              NAME + "-poweroff.path", NAME + "-poweroff.service",
              NAME + "-reboot.path", NAME + "-reboot.service")


def version():
    """@returns str, the version the tool reports about itself.

    Read out of the source rather than imported, because importing it would
    mean the build needs whatever the service imports, and a build should not.
    """
    source = (ADMIN / NAME / "server.py").read_text(encoding="utf-8")
    found = re.search(r'^VERSION = "([^"]+)"', source, re.M)
    if not found:
        raise SystemExit("no VERSION in server.py")
    return found.group(1)


def control(size):
    """@param size - How many kilobytes the package installs.
    @returns str, the control file.
    """
    return "".join(line + "\n" for line in [
        "Package: " + NAME,
        "Version: " + version(),
        "Architecture: " + ARCHITECTURE,
        "Maintainer: phranck <phranck@layered.work>",
        "Depends: " + ", ".join(DEPENDS),
        "Recommends: " + ", ".join(RECOMMENDS),
        "Section: admin",
        "Priority: optional",
        "Homepage: https://github.com/phranck/previously",
        "Installed-Size: %d" % size,
        "Description: Web admin for the Previous emulator",
        " Configures and watches a NeXT machine running under Previous, from a",
        " browser, in an interface built to look like the machine it configures.",
        " Runs as the user who owns the emulator and never as root.",
    ])


#: Run after the files are in place. Only what dpkg does not do itself:
#: systemd has to be told the units exist, the one directory the service cannot
#: create for itself is made, and the service is started so that installing it is
#: enough to have it.
POSTINST = """#!/bin/sh
set -e

if [ "$1" = configure ]; then
    # Where the configurations somebody saves are kept, in the home of whoever
    # owns the emulator. ProtectHome leaves the rest of that home read only, and
    # systemd skips a ReadWritePaths entry whose path is absent, so this has to
    # exist before the service starts or the first save refuses. The user and the
    # group are read out of the unit rather than named again here, because the
    # unit is where they are decided.
    #
    # It does not fail the installation. A directory that cannot be made leaves a
    # service that runs and refuses to save, saying why, which is a better state
    # to hand somebody than a package dpkg has left half configured.
    user=$(sed -n 's/^User=//p' /%(units)s/%(service)s)
    group=$(sed -n 's/^Group=//p' /%(units)s/%(service)s)
    if [ -n "$user" ] && [ -n "$group" ]; then
        home=$(getent passwd "$user" | cut -d: -f6)
        if [ -n "$home" ] && [ -d "$home" ]; then
            install -d -o "$user" -g "$group" -m 0700 "$home/.config/%(name)s" || true
        fi
    fi

    systemctl daemon-reload
    systemctl enable --now %(service)s
    # These act for the service without it holding any privilege, so they are
    # part of it rather than something to switch on separately.
    systemctl enable --now %(name)s-poweroff.path %(name)s-reboot.path
fi
"""

#: Run before the files go. Stopping first, because a unit whose files are
#: removed underneath it is one systemd cannot stop afterwards.
PRERM = """#!/bin/sh
set -e

if [ "$1" = remove ] || [ "$1" = upgrade ]; then
    systemctl disable --now %(service)s || true
    systemctl disable --now %(name)s-poweroff.path %(name)s-reboot.path || true
fi
"""

#: Run after the files have gone. Purge is where "leaves nothing behind"
#: belongs: the state this service wrote itself, which is its token and the
#: digest of its last write, and its own configuration. Remove keeps both, which
#: is the whole difference between the two and why somebody would choose one.
#:
#: What purge does not touch is anything in somebody's home. The configurations
#: they saved are in `~/.config/previously`, along with the emulator's own
#: configuration and the disk image, and removing this tool is not removing the
#: machines they built with it.
#:
#: There is no user to remove. This service runs as the user who owns the
#: emulator rather than as one of its own.
POSTRM = """#!/bin/sh
set -e

systemctl daemon-reload || true

if [ "$1" = remove ] || [ "$1" = purge ]; then
    # Whatever ended up in the program directory that dpkg does not own, which
    # is Python's compiled modules where anything ran without
    # PYTHONDONTWRITEBYTECODE. dpkg leaves the directory standing for them, so
    # this is what makes removal complete.
    rm -rf /usr/lib/%(name)s
fi

if [ "$1" = purge ]; then
    rm -rf /var/lib/%(name)s /etc/%(name)s
fi
"""


def lay_out(into):
    """Puts every file where it will sit on the machine.

    @param into - pathlib.Path of the directory to build in, which is emptied
      first so a second build cannot inherit a file from the first.
    """
    if into.exists():
        shutil.rmtree(into)

    # The service and the pages it serves. __pycache__ is whatever the last
    # test run left and has no business in a package.
    shutil.copytree(ADMIN / NAME, into / LIB / NAME,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ADMIN / "web", into / LIB / "web",
                    ignore=shutil.ignore_patterns("__pycache__"))

    (into / UNITS).mkdir(parents=True, exist_ok=True)
    for unit in UNIT_FILES:
        shutil.copy(HERE / unit, into / UNITS / unit)

    (into / CONFIG).mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "config.ini", into / CONFIG / "config.ini")


def write_control(into):
    """Writes DEBIAN/control and the three scripts, and makes them runnable."""
    debian = into / "DEBIAN"
    debian.mkdir(parents=True, exist_ok=True)

    kilobytes = sum(path.stat().st_size for path in into.rglob("*")
                    if path.is_file()) // 1024
    (debian / "control").write_text(control(kilobytes), encoding="utf-8")

    # Changed by hand on a running machine and never overwritten by an
    # upgrade, which is what conffiles means.
    (debian / "conffiles").write_text("/%s/config.ini\n" % CONFIG, encoding="utf-8")

    words = {"name": NAME, "service": SERVICE, "units": UNITS}
    for script, body in [("postinst", POSTINST), ("prerm", PRERM),
                         ("postrm", POSTRM)]:
        path = debian / script
        path.write_text(body % words, encoding="utf-8")
        path.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--into", default=str(HERE / "build"),
                        help="where to lay the files out and write the .deb")
    where = parser.parse_args().into

    if shutil.which("dpkg-deb") is None:
        raise SystemExit("dpkg-deb is not here: brew install dpkg, or build "
                         "this on the machine it is for")

    tree = pathlib.Path(where) / NAME
    lay_out(tree)
    write_control(tree)

    package = pathlib.Path(where) / ("%s_%s_%s.deb" % (NAME, version(), ARCHITECTURE))
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build",
                    str(tree), str(package)], check=True)
    print("wrote %s" % package)


if __name__ == "__main__":
    sys.exit(main())
