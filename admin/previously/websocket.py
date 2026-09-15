"""A WebSocket, out of the standard library.

The service takes no dependencies, which is what lets it start on a machine
with no network and inside the package build. A WebSocket is a handshake and a
frame format, both written down in RFC 6455, and both fit here: hashlib and
base64 answer the first, struct the second.

What it does not do is what this service does not need. No extensions, no
compression, no fragmenting of what it sends, and one message at a time.
"""

import base64
import hashlib
import json
import struct

#: The string RFC 6455 has a server append to the key before hashing it. It is
#: not a secret and not a check on anybody: it is there so that a cache or a
#: proxy which knows nothing about WebSockets cannot produce the right answer
#: by accident.
MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

#: What a frame can be. Only these; anything else is a protocol this service
#: does not speak and the connection goes.
CONTINUATION = 0x0
TEXT = 0x1
BINARY = 0x2
CLOSE = 0x8
PING = 0x9
PONG = 0xA

#: The most one message may carry. A terminal's keystrokes are bytes at a
#: time and a paste is kilobytes, so anything past this is not a person typing
#: and the service refuses to hold it in memory.
LARGEST_MESSAGE = 1 << 20

#: What the browser and this service agree to speak, and where the token
#: rides. A browser cannot put a header on a WebSocket, and the token may not
#: be in a URL, so it travels as the second protocol offered.
PROTOCOL = "previously"


class Closed(Exception):
    """The other side has gone, or has said something this cannot answer."""


def accepts(key):
    """The answer to a client's key.

    @param key - What the request carried in Sec-WebSocket-Key.
    @returns str, the value for Sec-WebSocket-Accept.
    """
    digest = hashlib.sha1((key + MAGIC).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def offered(header):
    """What the client offered to speak.

    @param header - The Sec-WebSocket-Protocol header, or None.
    @returns list of str, in the order they were offered.
    """
    if not header:
        return []
    return [part.strip() for part in header.split(",") if part.strip()]


def wants_a_socket(headers):
    """Whether this request is asking to become a WebSocket.

    @param headers - The request's headers.
    @returns bool

    Both parts are checked, because a header that says Upgrade without saying
    which upgrade is not this.
    """
    connection = (headers.get("Connection") or "").lower()
    upgrade = (headers.get("Upgrade") or "").lower()
    return "upgrade" in connection and upgrade == "websocket"


class Connection:
    """One WebSocket, over a socket that is already connected.

    Reading and writing are separated so that two threads can use one
    connection: a terminal has to send what the shell says whilst it is
    waiting for what the person types, and neither may wait for the other.
    """

    def __init__(self, stream, sender):
        """
        @param stream - Something with read(n), for what arrives.
        @param sender - Something with sendall(bytes), for what goes.
        """
        self.stream = stream
        self.sender = sender
        self.open = True

    def receive(self):
        """The next message.

        @returns tuple of (opcode, bytes), where the opcode is TEXT or BINARY.
        @raises Closed - The other side has gone, or the frame is one this
          does not speak.

        A ping is answered here rather than handed up, because nothing above
        this would do anything else with it. A message split into several
        frames is put back together, which a large paste arrives as.
        """
        kind = None
        message = b""
        while True:
            final, opcode, payload = self._frame()

            if opcode == CLOSE:
                raise Closed("the other side said goodbye")
            if opcode == PING:
                self._send(PONG, payload)
                continue
            if opcode == PONG:
                continue

            if opcode in (TEXT, BINARY):
                kind = opcode
            elif opcode != CONTINUATION or kind is None:
                raise Closed("a frame this does not speak: %d" % opcode)

            message += payload
            if len(message) > LARGEST_MESSAGE:
                raise Closed("a message larger than this holds")
            if final:
                return kind, message

    def send(self, data, opcode=BINARY):
        """Sends one message.

        @param data - bytes, or str which is sent as text.
        @param opcode - BINARY or TEXT.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
            opcode = TEXT
        self._send(opcode, data)

    def close(self):
        """Says goodbye, once, and stops sending.

        Whatever goes wrong whilst saying it is the other side having gone
        already, which is the thing being said.
        """
        if not self.open:
            return
        self.open = False
        try:
            self._send(CLOSE, b"")
        except OSError:
            pass

    def _frame(self):
        """Reads one frame.

        @returns tuple of (final, opcode, payload)
        @raises Closed

        A frame from a client is always masked, which RFC 6455 requires so
        that a proxy cannot be fooled into reading the payload as a request of
        its own. One that is not masked is not a browser and is refused.
        """
        head = self._exactly(2)
        final = bool(head[0] & 0x80)
        opcode = head[0] & 0x0F
        masked = bool(head[1] & 0x80)
        length = head[1] & 0x7F

        if length == 126:
            length = struct.unpack("!H", self._exactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._exactly(8))[0]
        if length > LARGEST_MESSAGE:
            raise Closed("a frame larger than this holds")
        if not masked:
            raise Closed("a frame from a client that was not masked")

        key = self._exactly(4)
        payload = self._exactly(length)
        return final, opcode, bytes(byte ^ key[index % 4]
                                    for index, byte in enumerate(payload))

    def _send(self, opcode, payload):
        """Writes one frame, unmasked, which is what a server sends."""
        head = bytes([0x80 | opcode])
        length = len(payload)
        if length < 126:
            head += bytes([length])
        elif length < (1 << 16):
            head += bytes([126]) + struct.pack("!H", length)
        else:
            head += bytes([127]) + struct.pack("!Q", length)
        self.sender.sendall(head + payload)

    def _exactly(self, count):
        """@returns exactly that many bytes, or raises Closed."""
        data = b""
        while len(data) < count:
            piece = self.stream.read(count - len(data))
            if not piece:
                raise Closed("the other side stopped mid-frame")
            data += piece
        return data


def message(text):
    """What a text frame carried, as what it means.

    @param text - The frame's payload.
    @returns dict, empty where it was not an object this understands.

    Text is how the browser says something about the session rather than to
    it, so it is read here and never passed to the shell.
    """
    try:
        found = json.loads(text)
    except (ValueError, TypeError):
        return {}
    return found if isinstance(found, dict) else {}
