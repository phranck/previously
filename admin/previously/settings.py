"""What the service itself is configured with.

Read from /etc/previously/config.ini, with defaults that work unconfigured
so the package installs into a running state rather than into a file to edit.
"""

import configparser
import os
import pathlib

CONFIG_FILE = pathlib.Path("/etc/previously/config.ini")

#: Everything a fresh installation runs on. The emulator's configuration lives
#: in the home of whoever owns it, which is the user this service runs as, so
#: the default is expressed relative to that rather than to a name.
DEFAULTS = {
    "address": "0.0.0.0",
    "port": "8088",
    "previous_config": "~/.config/previous/previous.cfg",
    "kiosk_unit": "getty@tty1.service",
    # The secret a request carries before it may change anything. State the
    # service generates and maintains itself, so /var/lib rather than /etc,
    # which holds what an administrator writes. The unit creates the directory
    # through StateDirectory= and leaves /etc read-only, so a token under /etc
    # could never be written at all.
    "token_file": "/var/lib/previously/token",
    # Empty means plain HTTP. A machine reachable only as cube.local cannot
    # have a certificate, because no public authority issues for a name in
    # .local, so an installation that has not been given a real name of its own
    # has nothing to put here.
    "certificate": "",
    "private_key": "",
}


def _path(value):
    """A configured path with ~ expanded.

    @param value - What the file said.
    @returns pathlib.Path
    """
    return pathlib.Path(os.path.expanduser(value.strip()))


def _path_or_none(value):
    """A configured path, or None where the key is empty.

    @param value - What the file said, which for an unset key is "".
    @returns pathlib.Path or None

    An empty key and an absent key mean the same thing, which matters because
    commenting a key out and clearing it are both things people do.
    """
    return _path(value) if value.strip() else None


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
        self.token_file = _path(values["token_file"])
        self.certificate = _path_or_none(values["certificate"])
        self.private_key = _path_or_none(values["private_key"])

    @property
    def scheme(self):
        """"https" where a certificate is configured, "http" where none is.

        @returns str, for building the address the service prints and the page
          reports, so neither states a protocol of its own.
        """
        return "https" if self.certificate else "http"

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
