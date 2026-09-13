"""Who may change something, and how that is decided.

Reading is open. Anything on the home network may see which machine is
configured and whether it is running, because knowing that costs nothing.

Changing anything needs a token: writing a configuration, stopping the
emulator, opening a shell. Sitting at the machine and pressing F12 needs
physical access; being on the network does not, and that difference is what
this answers.

The token is not a password and not a login. It is one secret for one machine,
read once over SSH and kept by the browser, which is proportionate to a tool
for the person whose Pi it is.
"""

import hmac
import os
import pathlib
import secrets

#: Where the token lives. Written by the package at installation, or by this
#: module on first start where no package put one there.
TOKEN_FILE = pathlib.Path("/etc/previously/token")

#: 32 bytes from the system's own source, hex encoded. Long enough that
#: guessing is not a strategy, short enough to type once.
TOKEN_BYTES = 32

#: The header a request carries it in. A header rather than a query parameter,
#: because a URL ends up in logs, in history and in whatever somebody pastes
#: into a chat window.
HEADER = "X-Previously-Token"


class Token:
    """The one secret this machine has.

    Loading is separated from checking so that a service which cannot read its
    own token fails at startup, where somebody sees it, rather than on the
    first request that needed it.
    """

    def __init__(self, value):
        self.value = value

    @classmethod
    def load(cls, path=TOKEN_FILE):
        """Reads the token, making one where there is none.

        @param path - Where to look.
        @returns Token, or None where the file can be neither read nor made.
          That is not fatal: a service with no token refuses every change,
          which is the safe direction to fail in.
        """
        try:
            if path.exists():
                value = path.read_text().strip()
                return cls(value) if value else cls._create(path)
            return cls._create(path)
        except OSError:
            return None

    @classmethod
    def _create(cls, path):
        """Writes a new token, readable by this service alone.

        The mode is set on the file descriptor rather than afterwards, so the
        token is never on disk world-readable, not even for the moment between
        being written and being chmod-ed.
        """
        value = secrets.token_hex(TOKEN_BYTES)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(value + "\n")
        return cls(value)

    def matches(self, offered):
        """Whether what a request carried is the token.

        @param offered - The header's value, or None where it carried none.
        @returns bool

        Compared with compare_digest rather than ==, because a comparison that
        stops at the first wrong character tells the caller how much of their
        guess was right, one character at a time.
        """
        if not offered:
            return False
        return hmac.compare_digest(self.value, offered)
