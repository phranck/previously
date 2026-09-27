"""The entry point the systemd unit runs.

    python3 -m previously
"""

import sys

from .password import Password
from .server import serve
from .settings import Settings


def main():
    """Loads the settings and serves until stopped."""
    settings = Settings.load()
    password = Password(settings.password_file)
    if not password.claimed:
        # Not a fault: a fresh installation has no password until somebody
        # opens the interface and chooses one. Saying so here is the one chance
        # anybody has to notice that the machine is still open to be claimed.
        print("no password is set; the first browser to arrive chooses one",
              file=sys.stderr)
    try:
        serve(settings, password)
    except KeyboardInterrupt:
        return 0
    except OSError as error:
        # The common one by far is the port being taken, and a traceback for
        # that tells the reader less than the sentence does.
        print("cannot serve on %s:%d: %s" % (settings.address, settings.port, error),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
