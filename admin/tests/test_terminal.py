"""A shell on a pseudo terminal, and the two directions it is pumped in.

The session is tested against a real shell, because what is worth knowing is
whether a person typing gets an answer and whether what they left behind is
gone afterwards, and neither of those can be faked.

The pumping is tested without one, because what is worth knowing there is what
happens when a side goes away, and arranging that is easier with something
that can be told to.
"""

import os
import pathlib
import select
import time

import pytest

from previously import terminal, websocket

#: A shell that is on every machine this runs on, and which says little.
SHELL = "/bin/sh"

#: How long to wait for the shell to answer before calling it broken. It
#: answers in milliseconds; this is the difference between slow and gone.
PATIENCE = 10


def says(session, until, patience=PATIENCE):
    """Reads until the shell has said something, or until it is too late.

    @param session - A Session.
    @param until - The bytes being waited for.
    @param patience - Seconds.
    @returns bytes, everything read so far.

    Asked whether there is anything before reading, because a read on a
    terminal blocks until there is. A shell that says nothing would otherwise
    hold this in its first read and the deadline below would never be looked
    at again: measured in CI, where the suite sat in one test for ten minutes
    with a patience of ten seconds.
    """
    heard = b""
    deadline = time.monotonic() + patience
    while time.monotonic() < deadline:
        if select.select([session.descriptor], [], [], 0.05)[0]:
            heard += session.read()
            if until in heard:
                return heard
    return heard


def has_gone(session, patience=PATIENCE):
    """Waits for the shell to end.

    @returns bool, whether it had gone in time.

    Asked of the process rather than of the clock. How long a shell takes to
    leave is the machine's business, and a test that waits a fixed two seconds
    for it is one that passes where that is enough and fails where it is not.
    """
    deadline = time.monotonic() + patience
    while time.monotonic() < deadline:
        try:
            gone, _ = os.waitpid(session.pid, os.WNOHANG)
        except ChildProcessError:
            return True
        if gone:
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def session():
    """A shell, ended whatever the test does."""
    made = terminal.Session(shell=SHELL, environment={"PS1": "$ ", "PATH": os.environ["PATH"]})
    yield made
    made.close()


# -- a real shell ---------------------------------------------------------


@pytest.mark.skipif(not pathlib.Path(SHELL).exists(), reason="no " + SHELL)
def test_what_is_typed_is_answered(session):
    session.write(b"echo hallo-vom-pi\n")

    assert b"hallo-vom-pi" in says(session, b"hallo-vom-pi")


@pytest.mark.skipif(not pathlib.Path(SHELL).exists(), reason="no " + SHELL)
def test_the_shell_is_this_user_and_not_root(session):
    """The service runs as the emulator's owner and the shell is forked from
    it, so it is that user and nothing else. Worth a test rather than a
    comment, because the day it is not is the day it matters."""
    mine = str(os.getuid()).encode()
    session.write(b"id -u\n")

    # Past the echo of the line itself, which arrives first and holds no
    # answer, to what the shell says back.
    heard = says(session, b"\r\n" + mine)
    assert b"\r\n" + mine in heard


@pytest.mark.skipif(not pathlib.Path(SHELL).exists(), reason="no " + SHELL)
def test_the_shell_is_told_how_large_the_window_is(session):
    """Without this a shell believes it is 24 by 80 whatever the window does,
    and anything that draws itself is drawn in the wrong place."""
    session.resize(40, 100)
    session.write(b"stty size\n")

    assert b"40 100" in says(session, b"40 100")


@pytest.mark.skipif(not pathlib.Path(SHELL).exists(), reason="no " + SHELL)
def test_nothing_is_left_running_when_the_session_ends():
    """What a browser closing must not leave behind."""
    made = terminal.Session(shell=SHELL, environment={"PATH": os.environ["PATH"]})
    pid = made.pid

    made.close()

    with pytest.raises(OSError):
        # Signal zero asks whether it is there at all, and it is not.
        for _ in range(200):
            os.kill(pid, 0)
            time.sleep(0.01)


@pytest.mark.skipif(not pathlib.Path(SHELL).exists(), reason="no " + SHELL)
def test_a_shell_that_has_gone_says_nothing_more(session):
    session.write(b"exit\n")
    # Read what it says on the way out first, and only then ask whether it has
    # gone: a shell that nobody is reading from can be waiting to be read.
    says(session, b"nothing that will come", patience=2)

    assert has_gone(session), "the shell is still there"
    assert session.read() == b""
    assert session.write(b"ls\n") is False


# -- who is logging in ----------------------------------------------------


@pytest.mark.parametrize("name", ["next", "pi", "_service", "a", "user-2", "x" * 32])
def test_a_name_somebody_could_be_called(name):
    assert terminal.is_a_login_name(name) is True


@pytest.mark.parametrize("name", [
    "-oProxyCommand=something",   # read as an option rather than a person
    "root; rm -rf /",
    "Next",                       # a Unix login name is lower case
    "with space",
    "",
    None,
    42,
    "x" * 33,
])
def test_a_name_nobody_could_be_called(name):
    assert terminal.is_a_login_name(name) is False


def test_a_session_refuses_to_start_without_a_name():
    """The name becomes an argument to the SSH client, so this is checked
    where the client is started rather than only where the name arrives."""
    with pytest.raises(ValueError):
        terminal.Session(login="-oProxyCommand=something")


def test_the_first_word_says_who_is_logging_in_and_how_large_the_window_is():
    started = {}

    class Pretending:
        def __init__(self, **how):
            started.update(how)

    connection = Talking([(websocket.TEXT, b'{"login": "next", "size": [40, 100]}')])
    terminal.Session, keeping = Pretending, terminal.Session
    try:
        terminal.open_for(connection)
    finally:
        terminal.Session = keeping

    assert started == {"rows": 40, "columns": 100, "login": "next"}


def test_a_size_that_is_not_one_falls_back_to_the_ordinary(monkeypatch):
    started = {}
    monkeypatch.setattr(terminal, "Session", lambda **how: started.update(how))
    connection = Talking([(websocket.TEXT, b'{"login": "next", "size": "wide"}')])

    terminal.open_for(connection)

    assert started == {"rows": 24, "columns": 80, "login": "next"}


@pytest.mark.parametrize("first", [
    (websocket.BINARY, b'{"login": "next"}'),
    (websocket.TEXT, b'{"login": "-oProxyCommand=x"}'),
    (websocket.TEXT, b"not json"),
])
def test_nothing_is_started_for_a_first_word_this_does_not_trust(first, monkeypatch):
    monkeypatch.setattr(terminal, "Session", lambda **how: "started")

    assert terminal.open_for(Talking([first])) is None


def test_nothing_is_started_for_a_browser_that_says_nothing(monkeypatch):
    monkeypatch.setattr(terminal, "Session", lambda **how: "started")

    assert terminal.open_for(Talking([])) is None


# -- the two directions ---------------------------------------------------


class Pretend:
    """A session that says what it was given, and can be told to end."""

    def __init__(self, lines=None):
        self.lines = list(lines or [])
        self.written = b""
        self.size = None
        self.closed = False
        self.descriptor = os.open(os.devnull, os.O_RDONLY)

    def read(self):
        return self.lines.pop(0) if self.lines else b""

    def write(self, data):
        self.written += data
        return True

    def resize(self, rows, columns):
        self.size = (rows, columns)

    def close(self):
        self.closed = True
        try:
            os.close(self.descriptor)
        except OSError:
            pass


class Talking:
    """A connection with things waiting to be received."""

    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.sent = []
        self.closed = False

    def receive(self):
        if not self.messages:
            raise websocket.Closed("nothing more")
        return self.messages.pop(0)

    def send(self, data, opcode=websocket.BINARY):
        self.sent.append(data)

    def close(self):
        self.closed = True


def test_what_the_shell_says_reaches_the_browser():
    session = Pretend([b"one", b"two"])
    connection = Talking()

    terminal.attach(session, connection, reader=lambda *_: None)

    assert connection.sent == [b"one", b"two"]


def test_a_shell_that_ends_takes_the_connection_with_it():
    session = Pretend([b"goodbye"])
    connection = Talking()

    terminal.attach(session, connection, reader=lambda *_: None)

    assert session.closed and connection.closed


def test_what_the_browser_types_reaches_the_shell():
    session = Pretend()
    connection = Talking([(websocket.BINARY, b"ls -l\n")])

    terminal.listen(session, connection)

    assert session.written == b"ls -l\n"


def test_a_size_is_told_to_the_session_and_not_typed_at_it():
    session = Pretend()
    connection = Talking([(websocket.TEXT, b'{"resize": [30, 90]}')])

    terminal.listen(session, connection)

    assert session.size == (30, 90)
    assert session.written == b""


@pytest.mark.parametrize("said", [
    b"not json",
    b'{"resize": "wide"}',
    b'{"resize": [1]}',
    b'{"something": "else"}',
])
def test_a_text_frame_that_says_nothing_this_knows_is_ignored(said):
    session = Pretend()
    connection = Talking([(websocket.TEXT, said)])

    terminal.listen(session, connection)

    assert session.size is None
    assert session.written == b""


def test_a_browser_that_goes_away_ends_the_session():
    """What the other direction is waiting on is the shell, so the browser
    going has to end the session rather than only its descriptor. A close
    does not wake a thread that is blocked reading; the shell going does."""
    session = Pretend()
    connection = Talking()

    terminal.listen(session, connection)

    assert session.closed


@pytest.mark.skipif(not pathlib.Path(SHELL).exists(), reason="no " + SHELL)
def test_the_shell_is_ended_before_its_terminal_is_closed():
    """The order is the fix for a session that stayed open after the browser
    had gone: the reader waits on the terminal, and only the shell going wakes
    it."""
    made = terminal.Session(shell=SHELL, environment={"PATH": os.environ["PATH"]})
    order = []
    made._signal = lambda which, first=made._signal: (order.append("signal"), first(which))[1]
    closing = os.close

    def note(descriptor, first=closing):
        if descriptor == made.descriptor:
            order.append("close")
        return first(descriptor)

    terminal.os.close = note
    try:
        made.close()
    finally:
        terminal.os.close = closing

    assert order and order[0] == "signal"
    assert "close" in order
