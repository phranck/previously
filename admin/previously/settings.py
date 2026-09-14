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

#: What it keeps only whilst the machine is up. A tmpfs, created by the unit
#: through RuntimeDirectory= and empty again at every boot, which is what the
#: hold file needs: a machine that has just started should run its emulator,
#: whoever switched it off before the last shutdown.
RUNTIME_DIRECTORY = "/run/previously"

#: Everything a fresh installation runs on. The emulator's configuration lives
#: in the home of whoever owns it, which is the user this service runs as, so
#: the default is expressed relative to that rather than to a name.
DEFAULTS = {
    "address": "0.0.0.0",
    "port": "2342",
    "previous_config": "~/.config/previous/previous.cfg",
    "kiosk_unit": "getty@tty1.service",
    "state_directory": STATE_DIRECTORY,
    "runtime_directory": RUNTIME_DIRECTORY,
    # The secret a request carries before it may change anything. State the
    # service maintains itself, so /var/lib rather than /etc, which holds what
    # an administrator writes. It has to survive a reboot, so it is not in the
    # runtime directory beside the hold file.
    "token_file": STATE_DIRECTORY + "/token",
}


def _path(value):
    """A configured path with ~ expanded.

    @param value - What the file said.
    @returns pathlib.Path
    """
    return pathlib.Path(os.path.expanduser(value.strip()))


class Settings:
    """The service's own configuration, read once at startup.

    Attributes come from the file where it has them and from DEFAULTS where it
    does not, so a file naming one key is a file naming one key rather than a
    file that has to repeat everything.
    """

    def __init__(self, values):
        self.address = values["address"]
        self.port = int(values["port"])
        self.previous_config = _path(values["previous_config"])
        self.kiosk_unit = values["kiosk_unit"]
        self.state_directory = _path(values["state_directory"])
        self.runtime_directory = _path(values["runtime_directory"])
        self.token_file = _path(values["token_file"])

    @classmethod
    def load(cls, path=CONFIG_FILE):
        """Reads the file, falling back to the defaults for anything missing.

        @param path - Where to look. A path that is not there is not an error:
          the defaults are a working configuration on their own.
        @returns Settings
        """
        parser = configparser.ConfigParser()
        parser.read_dict({"service": DEFAULTS})
        if path.exists():
            parser.read(path)
        return cls(parser["service"])

    def __repr__(self):
        return "Settings(address=%r, port=%d, previous_config=%r)" % (
            self.address, self.port, str(self.previous_config)
        )
