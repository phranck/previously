"""Who may change something, and how that is decided.

Reading is open. Anything on the home network may see which machine is
configured and whether it is running, because knowing that costs nothing.

Changing anything needs the password: writing a configuration, stopping the
emulator, taking a picture of the screen. Sitting at the machine and pressing
F12 needs physical access; being on the network does not, and that difference
is what this answers.

The password is chosen in the interface the first time somebody reaches an
unclaimed machine, and this file keeps nothing but a hash of it. A browser that
has given it holds a session rather than the secret, so what sits in the
browser opens this one machine for a month and is no use anywhere else.

Whoever is on the network when the machine is still unclaimed can claim it.
That window is the price of not fetching a secret over SSH, and the interface
says plainly while it is open.
"""

import hashlib
import hmac
import os
import secrets
import threading
import time

#: What a password may be. The floor is low enough for a tool on one's own
#: network and high enough that the limit below has something to protect; the
#: ceiling is there so that a body cannot ask this machine to hash a megabyte.
SMALLEST = 8
LARGEST = 128

#: How the hash is made. scrypt comes with Python, so this adds nothing to
#: install, and these three are its published interactive parameters: 16384
#: blocks of 8, which is 16 MB of memory per check, once per sign in.
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
HASH_BYTES = 32

#: Written into the file with the hash, so a file made by an older version is
#: still read by a newer one that has changed them.
STORED = "scrypt${n}${r}${p}${salt}${hash}"

#: The cookie a signed in browser carries, and how long one lasts. Long, because
#: this replaces a secret that was typed once and kept for good, and a month of
#: not being asked again is what makes that an improvement rather than a swap.
COOKIE = "previously_session"
SESSION_SECONDS = 30 * 24 * 60 * 60

#: 32 bytes as hex, which is 256 bits. What matters here is guessing rather
#: than collisions, and at that size neither is a strategy.
SESSION_BYTES = 32

#: How often a source may get the password wrong before it is refused for a
#: while. Ten is more than a person mistypes and far less than a machine needs.
WRONG_ATTEMPTS = 10
WRONG_WINDOW_SECONDS = 300


class Password:
    """The one secret this machine has, as a hash on disk.

    The file is read on every check rather than held in memory, so a machine
    whose password file has been removed is unclaimed from that moment. That is
    the whole of the recovery path, and it must not need a restart to take
    effect.
    """

    def __init__(self, path):
        """@param path - Where the hash is kept."""
        self.path = path

    @property
    def claimed(self):
        """@returns bool - Whether a password has been set on this machine."""
        return self._stored() is not None

    def set(self, value):
        """Writes a new password over whatever was there.

        @param value - What was typed.
        @returns bool - False where it is too short or too long, and then
          nothing is written.

        The mode is set on the file descriptor rather than afterwards, so the
        hash is never on disk world-readable, not even for the moment between
        being written and being chmod-ed.
        """
        if not acceptable(value):
            return False

        salt = secrets.token_bytes(SALT_BYTES)
        stored = STORED.format(
            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
            salt=salt.hex(), hash=_hashed(value, salt).hex())

        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(stored + "\n")
        return True

    def matches(self, offered):
        """Whether what was typed is this machine's password.

        @param offered - What the request carried, or None where it carried
          nothing.
        @returns bool - False on an unclaimed machine, because nothing is the
          password until one is set.

        Compared with compare_digest rather than ==, because a comparison that
        stops at the first wrong byte tells the caller how much of their guess
        was right, one byte at a time.
        """
        stored = self._stored()
        if stored is None or not offered:
            return False

        try:
            kind, n, r, p, salt, expected = stored.split("$")
        except ValueError:
            return False
        if kind != "scrypt":
            return False

        try:
            computed = _hashed(offered, bytes.fromhex(salt),
                               n=int(n), r=int(r), p=int(p))
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(computed.hex(), expected)

    def _stored(self):
        """@returns str - The line in the file, or None where there is none.

        A file that cannot be read leaves the machine unclaimed, which refuses
        every change. That is the safe direction to fail in.
        """
        try:
            line = self.path.read_text().strip()
        except OSError:
            return None
        return line or None


def acceptable(value):
    """@param value - What was typed. @returns bool - Whether it may be set."""
    return isinstance(value, str) and SMALLEST <= len(value) <= LARGEST


def _hashed(value, salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P):
    """@returns bytes - The hash of one password with one salt.

    The parameters are read back from the file rather than taken from here, so
    a hash written before they changed is still checked with the ones it was
    made with.
    """
    return hashlib.scrypt(value.encode("utf-8"), salt=salt,
                          n=n, r=r, p=p, dklen=HASH_BYTES)


class Sessions:
    """Which browsers are signed in.

    In memory, so a restart signs everybody out and nothing about who was here
    reaches the disk. A service that is restarted asks for the password again,
    which is one panel rather than the trip this whole change is about.

    Locked, because the server answers each request on a thread of its own.
    """

    def __init__(self, lasting=SESSION_SECONDS):
        """@param lasting - How long one is good for, in seconds."""
        self.lasting = lasting
        self.open_until = {}
        self.lock = threading.Lock()

    def open(self):
        """@returns str - A new session, good from now."""
        identifier = secrets.token_hex(SESSION_BYTES)
        with self.lock:
            self.open_until[identifier] = time.monotonic() + self.lasting
        return identifier

    def holds(self, identifier):
        """@param identifier - What the cookie carried, or None.
        @returns bool - Whether it is a session that has not run out."""
        if not identifier:
            return False
        with self.lock:
            until = self.open_until.get(identifier)
            if until is None:
                return False
            if until <= time.monotonic():
                del self.open_until[identifier]
                return False
        return True

    def forget(self, identifier):
        """Ends one session. @param identifier - Which."""
        with self.lock:
            self.open_until.pop(identifier, None)

    def forget_them_all(self):
        """Signs every browser out, which is what a new password means: the
        one that set it is given a fresh session, and anything else holding an
        old one has to give the new password."""
        with self.lock:
            self.open_until.clear()


class Attempts:
    """How often each source has got the password wrong lately.

    By source address and by nothing else, because there is one secret here and
    no accounts to count against. What this buys is that a machine on the
    network cannot work through a list of passwords at network speed, which is
    the one attack a hash alone does not answer.
    """

    def __init__(self, allowed=WRONG_ATTEMPTS, window=WRONG_WINDOW_SECONDS):
        """@param allowed - How many wrong answers a source gets.
        @param window - Over how many seconds they are counted."""
        self.allowed = allowed
        self.window = window
        self.wrong_at = {}
        self.lock = threading.Lock()

    def too_many(self, source):
        """@param source - The address the request came from.
        @returns bool - Whether this source is refused for now."""
        with self.lock:
            return len(self._recent(source)) >= self.allowed

    def wrong(self, source):
        """Counts one wrong answer. @param source - Where it came from."""
        with self.lock:
            recent = self._recent(source)
            recent.append(time.monotonic())
            self.wrong_at[source] = recent

    def forget(self, source):
        """Forgets a source's wrong answers, which a right one earns.

        @param source - Where the right answer came from.
        """
        with self.lock:
            self.wrong_at.pop(source, None)

    def _recent(self, source):
        """@returns list - That source's wrong answers inside the window.

        Called with the lock held. Anything older is dropped here rather than
        by a sweep of its own, so the record of a source that stops trying goes
        the next time it is looked at.
        """
        since = time.monotonic() - self.window
        return [at for at in self.wrong_at.get(source, []) if at > since]
