"""The covers the Pi keeps for software entries.

A cover is a thumbnail archive.org made of an item's front, a few kilobytes.
The Pi fetches it once, keeps it in its state directory and hands it out
itself, so a browser that opens the admin asks nobody but the Pi. A picture is
kept only where its first bytes are those of a JPEG, a PNG or a GIF, and only
up to a ceiling, because what arrives is a third party's.

Each kept picture is named by its entry and a stamp of the cover's address, so
an entry whose cover changes fetches the new one and drops the old one, and a
removed entry takes its picture with it.
"""

import base64
import os
import re
import urllib.error

from . import fetching, software

#: Where the pictures are kept, inside the service's state directory.
FOLDER = "covers"

#: The most a cover may be. archive.org's thumbnails are 5 to 10 kilobytes,
#: measured on 28 October 2026, and anything past this is not a thumbnail.
LARGEST_COVER = 256 * 1024

#: How long archive.org may take to answer for one.
TIMEOUT_SECONDS = 20

#: The first bytes of each kind of picture, and the type it is handed out as.
MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def kind_of(body):
    """@returns str or None - The type of picture the bytes begin as, or None
    where they begin as nothing this keeps."""
    return next((kind for magic, kind in MAGIC if body.startswith(magic)), None)


def data_address(body):
    """@returns str or None - The picture as an address the page can show
    without asking for it, or None where it is no picture."""
    kind = kind_of(body)
    if kind is None:
        return None
    return "data:%s;base64,%s" % (kind, base64.b64encode(body).decode("ascii"))


def fetched(address, read):
    """A cover from archive.org, where it is one.

    @param address - Where the thumbnail is.
    @param read - Reads an address and answers its bytes.
    @returns bytes, or None where it could not be had or is no picture, or is
      larger than LARGEST_COVER. Not having a cover is an entry without one,
      not a failure.
    """
    try:
        body = read(address)
    except (urllib.error.URLError, OSError):
        return None
    if not isinstance(body, bytes) or len(body) > LARGEST_COVER or kind_of(body) is None:
        return None
    return body


def reading():
    """@returns A reader that asks archive.org for a cover, reaching only
    `software.COVER_HOSTS` and reading no more than one byte past the
    ceiling."""
    def read(url):
        with fetching.opened(url, software.COVER_HOSTS, TIMEOUT_SECONDS) as answer:
            return answer.read(LARGEST_COVER + 1)
    return read


def cover_of(state_directory, entry, read=None):
    """An entry's cover, from what is kept or else from archive.org.

    @param state_directory - pathlib.Path of the service's state directory.
    @param entry - A software.Entry.
    @param read - Reads an address; `reading()` where none is given.
    @returns (bytes, str), the picture and its type, or None where the entry
      has no cover or it cannot be had now. One that could not be had is asked
      for again next time.
    """
    if not entry.cover:
        return None
    kept = _folder(state_directory) / _name(entry.identifier, entry.cover)
    try:
        body = kept.read_bytes()
    except OSError:
        body = None
    if body is not None and kind_of(body) is not None:
        return body, kind_of(body)

    body = fetched(entry.cover, read or reading())
    if body is None:
        return None
    forget(state_directory, entry.identifier)
    beside = kept.with_name(kept.name + ".new")
    try:
        kept.parent.mkdir(parents=True, exist_ok=True)
        beside.write_bytes(body)
        os.replace(beside, kept)
    except OSError:
        beside.unlink(missing_ok=True)
    return body, kind_of(body)


def forget(state_directory, identifier):
    """Takes away whatever picture is kept for an entry.

    @param state_directory - pathlib.Path of the service's state directory.
    @param identifier - The entry's identifier.

    Matched exactly, because an identifier may hold a dot, and one entry's
    name must not reach another's picture.
    """
    pattern = re.compile(re.escape(identifier) + r"\.[0-9a-f]{12}")
    try:
        found = list(_folder(state_directory).iterdir())
    except OSError:
        return
    for path in found:
        if pattern.fullmatch(path.name):
            path.unlink(missing_ok=True)


def _folder(state_directory):
    """@returns pathlib.Path - Where the covers are kept."""
    return state_directory / FOLDER


def _name(identifier, cover):
    """@returns str - What an entry's kept cover is called."""
    return "%s.%s" % (identifier, software.stamp(cover))
