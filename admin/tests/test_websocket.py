"""The frame format, held against RFC 6455 rather than against itself.

What a browser sends is decided by the standard and not by this service, so
the examples here are the standard's own where it gives one, and bytes written
out by hand where it does not.
"""

import io
import struct

import pytest

from previously import websocket


class Sender:
    """Something to send into, which keeps what it was given."""

    def __init__(self):
        self.sent = b""

    def sendall(self, data):
        self.sent += data


def masked(opcode, payload, key=b"\x37\xfa\x21\x3d", final=True):
    """One frame as a client sends it.

    @param opcode - What kind of frame.
    @param payload - bytes.
    @param key - The four bytes it is masked with.
    @param final - Whether this is the last frame of its message.
    @returns bytes
    """
    head = bytes([(0x80 if final else 0) | opcode])
    length = len(payload)
    if length < 126:
        head += bytes([0x80 | length])
    elif length < (1 << 16):
        head += bytes([0x80 | 126]) + struct.pack("!H", length)
    else:
        head += bytes([0x80 | 127]) + struct.pack("!Q", length)
    hidden = bytes(byte ^ key[index % 4] for index, byte in enumerate(payload))
    return head + key + hidden


def connection(*frames):
    """A connection with those frames waiting to be read."""
    return websocket.Connection(io.BytesIO(b"".join(frames)), Sender())


# -- the handshake -------------------------------------------------------


def test_the_key_is_answered_the_way_the_standard_says():
    """The example in RFC 6455 section 1.3, which is what a browser checks
    the answer against."""
    assert websocket.accepts("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_what_the_client_offered_to_speak():
    assert websocket.offered("previously, abc123") == ["previously", "abc123"]
    assert websocket.offered("") == []
    assert websocket.offered(None) == []


@pytest.mark.parametrize("headers, asking", [
    ({"Connection": "Upgrade", "Upgrade": "websocket"}, True),
    ({"Connection": "keep-alive, Upgrade", "Upgrade": "WebSocket"}, True),
    ({"Connection": "Upgrade"}, False),
    ({"Upgrade": "websocket"}, False),
    ({}, False),
])
def test_only_a_request_that_says_both_is_asking_for_a_socket(headers, asking):
    assert websocket.wants_a_socket(headers) is asking


# -- what arrives --------------------------------------------------------


def test_a_text_frame_arrives_as_what_was_sent():
    socket = connection(masked(websocket.TEXT, "häuser".encode("utf-8")))

    kind, data = socket.receive()

    assert kind == websocket.TEXT
    assert data.decode("utf-8") == "häuser"


def test_a_message_split_across_frames_is_put_back_together():
    """What a large paste arrives as."""
    socket = connection(masked(websocket.TEXT, b"one ", final=False),
                        masked(websocket.CONTINUATION, b"two ", final=False),
                        masked(websocket.CONTINUATION, b"three"))

    assert socket.receive() == (websocket.TEXT, b"one two three")


@pytest.mark.parametrize("length", [125, 126, 70000])
def test_every_way_a_length_is_written(length):
    """Seven bits, then two bytes, then eight, which is where a frame reader
    usually goes wrong."""
    payload = b"x" * length
    socket = connection(masked(websocket.BINARY, payload))

    assert socket.receive() == (websocket.BINARY, payload)


def test_a_ping_is_answered_and_not_handed_up():
    socket = connection(masked(websocket.PING, b"are you there"),
                        masked(websocket.BINARY, b"ls\n"))

    assert socket.receive() == (websocket.BINARY, b"ls\n")
    assert socket.sender.sent == bytes([0x80 | websocket.PONG, 13]) + b"are you there"


def test_a_goodbye_ends_it():
    socket = connection(masked(websocket.CLOSE, b""))

    with pytest.raises(websocket.Closed):
        socket.receive()


def test_a_frame_that_was_not_masked_is_refused():
    """Every frame from a client is masked, and one that is not is not a
    browser."""
    socket = websocket.Connection(io.BytesIO(bytes([0x81, 3]) + b"abc"), Sender())

    with pytest.raises(websocket.Closed):
        socket.receive()


def test_a_frame_larger_than_this_holds_is_refused():
    head = bytes([0x82, 0x80 | 127]) + struct.pack("!Q", websocket.LARGEST_MESSAGE + 1)
    socket = websocket.Connection(io.BytesIO(head), Sender())

    with pytest.raises(websocket.Closed):
        socket.receive()


def test_a_message_grown_past_the_limit_by_its_parts_is_refused():
    """Each frame within the limit, the message past it."""
    piece = b"x" * 60000
    frames = [masked(websocket.BINARY, piece, final=False) for _ in range(20)]
    socket = connection(*frames)

    with pytest.raises(websocket.Closed):
        socket.receive()


def test_the_other_side_going_mid_frame_ends_it():
    socket = websocket.Connection(io.BytesIO(bytes([0x81])), Sender())

    with pytest.raises(websocket.Closed):
        socket.receive()


# -- what goes -----------------------------------------------------------


@pytest.mark.parametrize("length, head", [
    (5, bytes([0x82, 5])),
    (200, bytes([0x82, 126]) + struct.pack("!H", 200)),
    (70000, bytes([0x82, 127]) + struct.pack("!Q", 70000)),
])
def test_what_a_server_sends_is_never_masked(length, head):
    socket = connection()

    socket.send(b"x" * length)

    assert socket.sender.sent == head + b"x" * length


def test_text_goes_as_text():
    """The length is of the bytes rather than of the characters, which is why
    the word here has an umlaut in it."""
    socket = connection()

    socket.send("größer")

    said = "größer".encode("utf-8")
    assert len(said) == 8
    assert socket.sender.sent == bytes([0x81, len(said)]) + said


def test_goodbye_is_said_once():
    socket = connection()

    socket.close()
    socket.close()

    assert socket.sender.sent == bytes([0x80 | websocket.CLOSE, 0])


# -- what a text frame means ---------------------------------------------


@pytest.mark.parametrize("text, means", [
    ('{"resize": [40, 100]}', {"resize": [40, 100]}),
    ("not json at all", {}),
    ("[1, 2, 3]", {}),
    ('"a string"', {}),
])
def test_text_is_read_as_what_it_says_about_the_session(text, means):
    assert websocket.message(text) == means
