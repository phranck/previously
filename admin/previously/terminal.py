"""A shell session, on a pseudo terminal this process owns.

The service forks it, so the shell is exactly as able as the service: the same
user, and the same sandbox the unit puts around it. That means a shell which
reads the machine and writes almost nothing, which is the escape hatch this
tool can honestly offer. Anything beyond it is what SSH is for.

One session at a time, because a person at one browser is what this is for and
a second one would be a second shell nobody is watching.
"""

import fcntl
import os
import pty
import signal
import struct
import termios
import threading
import time

from . import websocket

#: What is run, unless the user's own shell says otherwise. Read from the
#: environment the way login does, because a person's shell is their business.
FALLBACK_SHELL = "/bin/sh"

#: What the shell is told it is. A terminal that claims more than the browser
#: draws leaves programs painting things nobody sees, and xterm is what the
#: emulator on the other side actually is.
TERM = "xterm-256color"

#: How long the shell is given to leave after being asked, before it is made
#: to. A shell that ignores a hangup is a shell that has stopped listening.
GOODBYE_SECONDS = 2

#: How much is read from the terminal at once.
MOUTHFUL = 4096


class Session:
    """One shell on one pseudo terminal."""

    def __init__(self, rows=24, columns=80, shell=None, environment=None):
        """Forks the shell and keeps the terminal's end of it.

        @param rows - How tall the browser's terminal is.
        @param columns - How wide.
        @param shell - What to run. The user's own by default.
        @param environment - What it runs with, for tests. The service's own
          by default, with TERM set to what the browser draws.

        Everything the child will need is decided here, before the fork, so
        that the child does one thing and that thing is exec. Python warns
        that forking a process which has threads can leave the child waiting
        on a lock another thread held, and this service has threads: it
        answers each request in one. The window is what makes that likely or
        not, and there is nothing in this child's window but the exec itself.

        `pty.fork` rather than a subprocess, because it gives the shell a
        session and a controlling terminal, and without those Ctrl+C is a
        character rather than an interruption. Where that window ever turns
        out to be too much, the answer is a small process forked before the
        first thread exists, which hands out terminals over a socket.
        """
        self.rows = rows
        self.columns = columns
        command = shell or os.environ.get("SHELL") or FALLBACK_SHELL
        # A login shell, so a person gets their own prompt and their own path
        # rather than whatever the service was started with.
        argv = [command, "-l"]
        values = dict(environment or os.environ, TERM=TERM)

        self.ended = False
        self.pid, self.descriptor = pty.fork()
        if self.pid == 0:
            try:
                os.execve(command, argv, values)
            except BaseException:
                # Anything that goes wrong has to end the child here. An
                # exception would unwind into a second copy of the server,
                # holding the same socket.
                os._exit(1)
        self.resize(rows, columns)

    def read(self):
        """What the shell has said.

        @returns bytes, or b"" once there is nothing more, which is the shell
          having gone.
        """
        try:
            return os.read(self.descriptor, MOUTHFUL)
        except OSError:
            return b""

    def write(self, data):
        """What the person typed.

        @param data - bytes for the shell.
        @returns bool, False once the shell has gone.
        """
        try:
            os.write(self.descriptor, data)
            return True
        except OSError:
            return False

    def resize(self, rows, columns):
        """Tells the terminal how large the browser's window is.

        @param rows - Lines.
        @param columns - Characters across.

        Without this the shell believes it is 24 by 80 whatever the window
        does, and anything that draws itself, from a prompt with a right edge
        to a pager, is drawn in the wrong place.
        """
        self.rows = max(1, int(rows))
        self.columns = max(1, int(columns))
        size = struct.pack("HHHH", self.rows, self.columns, 0, 0)
        try:
            fcntl.ioctl(self.descriptor, termios.TIOCSWINSZ, size)
        except OSError:
            pass

    def close(self):
        """Ends the shell and everything it started.

        The hangup goes to the whole process group rather than to the shell
        alone, because what a person left running is the shell's children and
        a signal to the shell would leave them holding the terminal.

        The shell is ended before the terminal is closed, and that order is
        the whole of it. Another thread is waiting in a read on this
        descriptor, and closing a descriptor somebody is blocked on does not
        wake them on Linux: the read stays where it is and the number can be
        handed to the next file this service opens. What does wake them is the
        shell going, because the terminal then has nothing on the other end.

        Twice is once. Whichever side notices first ends the session, and the
        other arrives here a moment later.
        """
        if self.ended:
            return
        self.ended = True
        self._signal(signal.SIGHUP)
        if not self._gone(GOODBYE_SECONDS):
            self._signal(signal.SIGKILL)
            self._gone(GOODBYE_SECONDS)
        try:
            os.close(self.descriptor)
        except OSError:
            pass

    def _signal(self, which):
        """Sends one signal to the shell's whole group."""
        try:
            os.killpg(os.getpgid(self.pid), which)
        except OSError:
            pass

    def _gone(self, seconds):
        """Waits for the shell to be reaped.

        @returns bool, whether it has gone by then. Waiting in slices rather
          than blocking, because a shell that will not leave must not take the
          thread with it.
        """
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            try:
                reaped, _ = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                return True
            if reaped:
                return True
            time.sleep(0.05)
        return False


def attach(session, connection, reader=None):
    """Moves bytes between a shell and a browser until one of them goes.

    @param session - A Session.
    @param connection - A websocket.Connection.
    @param reader - What starts the thread that listens to the browser. For
      tests; the default starts a real one.

    Two directions and two threads, because each waits on something the other
    cannot see: this one waits on the terminal, and the other on the socket.
    Whichever ends first takes the session and the connection with it, which
    is what stops a shell being left running by a browser that was closed.
    """
    listening = (reader or _listener)(session, connection)
    try:
        while True:
            said = session.read()
            if not said:
                break
            connection.send(said)
    except (websocket.Closed, OSError):
        pass
    finally:
        session.close()
        connection.close()
        if listening is not None:
            listening.join(timeout=GOODBYE_SECONDS)


def _listener(session, connection):
    """Starts the thread that carries what the browser says to the shell."""
    thread = threading.Thread(target=listen, args=(session, connection),
                              name="terminal", daemon=True)
    thread.start()
    return thread


def listen(session, connection):
    """Carries what the browser says to the shell, until either goes.

    Binary is what the shell sees, so a keystroke and a paste arrive that way.
    Text is what the session is told, which today is how large the window has
    become, and never reaches the shell.
    """
    try:
        while True:
            kind, data = connection.receive()
            if kind == websocket.BINARY:
                if not session.write(data):
                    return
                continue
            said = websocket.message(data.decode("utf-8", "replace"))
            size = said.get("resize")
            if isinstance(size, list) and len(size) == 2:
                session.resize(size[0], size[1])
    except (websocket.Closed, OSError, ValueError):
        pass
    finally:
        # The other direction is waiting in a read on the terminal, and what
        # wakes it is the shell going rather than the descriptor closing. So
        # the browser having gone ends the session, and the session ending is
        # what the other side sees.
        session.close()
