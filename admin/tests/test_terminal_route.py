"""Who gets a shell, and who is refused one.

Tested over a real socket, speaking the handshake by hand, because what is
worth knowing is what the service answers a browser rather than what its
methods return. A shell is the widest thing this tool hands out, so every
refusal here is a test of its own.
"""

import base64
import http.server
import socket
import threading
import time

import pytest

from conftest import settings_for
from previously import server, terminal, websocket
from previously.token import Token

#: What a browser puts in Sec-WebSocket-Key, which is sixteen random bytes.
KEY = base64.b64encode(b"0123456789abcdef").decode("ascii")


@pytest.fixture
def service(tmp_path, readable_config):
    """A running service, and the token it will accept."""
    server.Handler.settings = settings_for(tmp_path)
    server.Handler.token = Token.load(tmp_path / "token")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address, server.Handler.token.value
    httpd.shutdown()
    httpd.server_close()


def ask(address, protocols=None, upgrade=True, key=KEY):
    """Asks for a terminal, the way a browser does.

    @param address - Where the service is.
    @param protocols - What to offer to speak, or None to offer nothing.
    @param upgrade - Whether to ask for an upgrade at all.
    @param key - What to put in Sec-WebSocket-Key.
    @returns tuple of (the status line, the open socket).
    """
    connection = socket.create_connection(address, timeout=5)
    lines = ["GET /api/terminal HTTP/1.1", "Host: %s:%d" % address]
    if upgrade:
        lines += ["Upgrade: websocket", "Connection: Upgrade",
                  "Sec-WebSocket-Version: 13"]
        if key:
            lines.append("Sec-WebSocket-Key: " + key)
    if protocols:
        lines.append("Sec-WebSocket-Protocol: " + ", ".join(protocols))
    connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
    status = b""
    while b"\r\n" not in status:
        piece = connection.recv(1)
        if not piece:
            break
        status += piece
    return status.decode("ascii", "replace").strip(), connection


def rest_of_the_headers(connection):
    """Reads to the end of the headers and returns them as one string."""
    text = b""
    while b"\r\n\r\n" not in text:
        piece = connection.recv(1)
        if not piece:
            break
        text += piece
    return text.decode("ascii", "replace")


def test_a_request_that_is_not_an_upgrade_is_not_a_terminal(service):
    address, token = service

    status, connection = ask(address, [websocket.PROTOCOL, token], upgrade=False)
    connection.close()

    assert "400" in status


def test_a_request_offering_another_protocol_is_refused(service):
    """The first protocol says what this is; anything else is not a browser
    of ours and does not get as far as the token."""
    address, token = service

    status, connection = ask(address, ["chat", token])
    connection.close()

    assert "400" in status


def test_a_request_without_a_key_is_refused(service):
    address, token = service

    status, connection = ask(address, [websocket.PROTOCOL, token], key=None)
    connection.close()

    assert "400" in status


def test_the_handshake_needs_no_token(service):
    """What is behind this socket is the machine's own SSH server, so whoever
    connects proves who they are to that rather than to this service."""
    address, _ = service

    status, connection = ask(address, [websocket.PROTOCOL])
    headers = rest_of_the_headers(connection)
    connection.close()

    # HTTP/1.1 rather than the 1.0 this handler answers everything else in,
    # because a browser refuses a handshake that is not.
    assert status == "HTTP/1.1 101 Switching Protocols"
    assert websocket.accepts(KEY) in headers
    assert "Sec-WebSocket-Protocol: " + websocket.PROTOCOL in headers


def test_a_browser_that_says_nothing_is_given_up_on(service, monkeypatch):
    """Otherwise connecting and saying nothing holds the one session there is,
    which needs no token and no shell to do."""
    monkeypatch.setattr(terminal, "FIRST_WORD_SECONDS", 1)
    address, _ = service

    _, connection = ask(address, [websocket.PROTOCOL])
    rest_of_the_headers(connection)
    connection.settimeout(6)
    ended = b""
    try:
        while True:
            piece = connection.recv(64)
            if not piece:
                break
            ended += piece
    except OSError:
        pass
    connection.close()

    # A close frame, or the socket simply gone. Either way the session is not
    # being held any more.
    assert ended == b"" or ended[0] & 0x0F == websocket.CLOSE


@pytest.mark.parametrize("first", [
    b'{"login": "-oProxyCommand=something"}',
    b'{"login": "root; rm -rf /"}',
    b'{"login": ""}',
    b'{"nothing": "of use"}',
    b"not json at all",
])
def test_a_first_word_that_is_not_a_login_name_opens_nothing(service, first):
    """The name becomes an argument to the SSH client, so one beginning with a
    dash would be read as an option rather than as a person."""
    address, _ = service

    _, connection = ask(address, [websocket.PROTOCOL])
    rest_of_the_headers(connection)
    connection.sendall(said(first))
    connection.settimeout(6)
    try:
        answer = connection.recv(64)
    except OSError:
        answer = b""
    connection.close()

    assert answer == b"" or answer[0] & 0x0F == websocket.CLOSE


def test_one_session_at_a_time(service):
    """A second browser would get a second session the first cannot see."""
    address, _ = service

    first_status, first = ask(address, [websocket.PROTOCOL])
    rest_of_the_headers(first)
    second_status, second = ask(address, [websocket.PROTOCOL])
    first.close()
    second.close()

    assert "101" in first_status
    assert "409" in second_status


def test_the_next_browser_gets_a_session_once_the_first_has_gone(service):
    """The lock is released when the session ends, or the tool hands out one
    session and never another."""
    address, _ = service

    _, first = ask(address, [websocket.PROTOCOL])
    rest_of_the_headers(first)
    first.close()

    status = "not asked"
    deadline = time.monotonic() + terminal.GOODBYE_SECONDS + 8
    while time.monotonic() < deadline:
        status, second = ask(address, [websocket.PROTOCOL])
        second.close()
        if "101" in status:
            break
        time.sleep(0.2)

    assert "101" in status


def said(data, opcode=websocket.TEXT):
    """What the browser sends, which is always a masked frame."""
    key = b"\x01\x02\x03\x04"
    head = bytes([0x80 | opcode, 0x80 | len(data)]) + key
    return head + bytes(byte ^ key[index % 4] for index, byte in enumerate(data))
