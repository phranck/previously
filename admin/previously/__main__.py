"""The entry point the systemd unit runs.

    python3 -m previously
"""

import sys

from .server import serve
from .settings import Settings


def main():
    """Loads the settings and serves until stopped."""
    settings = Settings.load()
    try:
        serve(settings)
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
