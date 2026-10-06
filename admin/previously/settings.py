"""What the service itself is configured with.

Read from /etc/previously/config.ini, with defaults that work unconfigured
so the package installs into a running state rather than into a file to edit.
"""

import configparser
import os
import pathlib

CONFIG_FILE = pathlib.Path("/etc/previously/config.ini")

#: What this service keeps between one start and the next. The unit creates it
#: through StateDirectory=, and its hardening leaves everything else read-only.
STATE_DIRECTORY = "/var/lib/previously"

#: What it keeps only while the machine is up. A tmpfs, created by the unit
#: through RuntimeDirectory= and empty again at every boot, which is what the
#: hold file needs: a machine that has just started should run its emulator,
#: whoever switched it off before the last shutdown.
RUNTIME_DIRECTORY = "/run/previously"

#: Where the privileged helper says what it is doing. Root's own directory
#: rather than the one above, because this service may not write there: a file
#: root wrote into a directory an unprivileged user owns could be replaced by a
#: link to somewhere else between one write and the next. This service only
#: reads it.
SETUP_DIRECTORY = "/run/previously-setup"

#: Everything a fresh installation runs on. The emulator's configuration lives
#: in the home of whoever owns it, which is the user this service runs as, so
#: the default is expressed relative to that rather than to a name.
DEFAULTS = {
    "address": "0.0.0.0",
    "port": "8810",
    "previous_config": "~/.config/previous/previous.cfg",
    # Where the configurations somebody saved are kept. In the home rather than
    # under /var/lib, because they are theirs: what this service keeps under
    # /var/lib is its own, which is the password and the note about its last write,
    # and a purge of the package takes that with it. It must not take away the
    # machines somebody built. Beside the emulator's own configuration, which is
    # what they are about.
    "machines_file": "~/.config/previously/machines.json",
    # Where the Previously tree is a real one. Everything else the File Viewer
    # shows is described in files.py and exists nowhere, but a picture is a
    # file. In the emulator owner's home, which is the user this service runs
    # as, so it needs nothing but its own permission to write there.
    "documents": "~/Previously",
    # Where the disk images live, one per system that is on this machine. In
    # the same home, because a disk is the person's: purging this package must
    # not take away two gigabytes they waited for. It is also where a disk
    # unpacked straight from its archive lands, so such a machine has its disk
    # here already.
    "disks": "~/nextstep",
    "kiosk_unit": "getty@tty1.service",
    "state_directory": STATE_DIRECTORY,
    "runtime_directory": RUNTIME_DIRECTORY,
    "setup_directory": SETUP_DIRECTORY,
    # A hash of the password somebody chose in the interface, which is what a
    # request proves before it may change anything. State the service maintains
    # itself, so /var/lib rather than /etc, which holds what an administrator
    # writes. It has to survive a reboot, so it is not in the runtime directory
    # beside the hold file. Removing it leaves the machine unclaimed, and the
    # next browser to arrive sets a new password.
    "password_file": STATE_DIRECTORY + "/password",
}


def _path(value, home=None):
    """A configured path with ~ expanded.

    @param value - What the file said.
    @param home - Whose home ~ means. Left out it is the user running this,
      which is right for the service and wrong for the privileged helper: that
      one runs as root and has to read the same file as the person who owns
      the emulator, whose home is not root's.
    @returns pathlib.Path
    """
    written = value.strip()
    if home is not None and written.startswith("~"):
        return pathlib.Path(home) / written.lstrip("~/")
    return pathlib.Path(os.path.expanduser(written))


class Settings:
    """The service's own configuration, read once at startup.

    Attributes come from the file where it has them and from DEFAULTS where it
    does not, so a file naming one key is a file naming one key rather than a
    file that has to repeat everything.
    """

    def __init__(self, values, home=None):
        self.address = values["address"]
        self.port = int(values["port"])
        self.previous_config = _path(values["previous_config"], home)
        self.machines_file = _path(values["machines_file"], home)
        self.documents = _path(values["documents"], home)
        self.disks = _path(values["disks"], home)
        self.kiosk_unit = values["kiosk_unit"]
        self.state_directory = _path(values["state_directory"], home)
        self.runtime_directory = _path(values["runtime_directory"], home)
        self.setup_directory = _path(values["setup_directory"], home)
        self.password_file = _path(values["password_file"], home)

    @classmethod
    def load(cls, path=CONFIG_FILE, home=None):
        """Reads the file, falling back to the defaults for anything missing.

        @param path - Where to look. A path that is not there is not an error:
          the defaults are a working configuration on their own.
        @param home - Whose home a path beginning with ~ means. The service
          leaves this out, because it runs as that person. The privileged
          helper runs as root and passes theirs.
        @returns Settings
        """
        parser = configparser.ConfigParser()
        parser.read_dict({"service": DEFAULTS})
        if path.exists():
            parser.read(path)
        return cls(parser["service"], home)

    def __repr__(self):
        return "Settings(address=%r, port=%d, previous_config=%r)" % (
            self.address, self.port, str(self.previous_config)
        )
