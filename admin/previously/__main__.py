"""The entry point the systemd unit runs.

    python3 -m previously
"""

import sys

from .server import serve
from .settings import Settings
from .tls import NotUsable
from .token import Token


def main():
    """Loads the settings and serves until stopped."""
    settings = Settings.load()
    token = Token.load(settings.token_file)
    if token is None:
        # Not fatal: the service still answers everything that only reads, and
        # refuses everything that would change anything. Saying so here is the
        # one chance somebody has to notice.
        print("no token could be read or written; every change will be refused",
              file=sys.stderr)
    try:
        serve(settings, token)
    except KeyboardInterrupt:
        return 0
    except NotUsable as error:
        # A certificate is configured and unusable. Starting without it would
        # serve everything in the clear on a port somebody believes carries
        # TLS, so nothing is bound at all.
        print("certificate unusable, not starting: %s" % error, file=sys.stderr)
        return 1
    except OSError as error:
        # The common one by far is the port being taken, and a traceback for
        # that tells the reader less than the sentence does.
        print("cannot serve on %s:%d: %s" % (settings.address, settings.port, error),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
