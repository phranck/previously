"""The software that can be put on the machine, and where it comes from.

A catalog of what somebody might want on a NeXT beside its system: the
developer CD, tools, applications and games. Each entry names the address it is
downloaded from and what that file is, so a download can refuse anything that
arrives as something else, and the systems it is for, so a machine is offered
only what it can run.

Name, version and description are written in English and shown as they are in
every language, the way a viewer shows a file's name: what is out there about
this software is in English, and a translation of a product's name is a second
name for it.

The shipped list is checked by the same rules as an entry somebody adds,
because a download reads both the same way.
"""

import collections
import ipaddress
import re
import urllib.parse

from . import systems

#: The groups an entry can be in, in the order the Software folder lists them,
#: and the folder each is shown as. A folder's name is shown as it is in every
#: language, as every other name in the File Viewer is.
FOLDERS = {
    "developer": "Developer",
    "tools": "Tools",
    "applications": "Applications",
    "games": "Games",
}
GROUPS = tuple(FOLDERS)

#: What an entry can be: a CD image, which goes into the machine's CD-ROM drive,
#: or a file of any other kind.
KINDS = ("disc", "file")

#: The digests an entry can be checked with, by how many hexadecimal digits
#: each has. SHA-1 because archive.org states it for every file it holds, and
#: SHA-256 for anywhere that states that instead.
DIGEST_DIGITS = {"sha1": 40, "sha256": 64}

#: What an identifier is made of. It is what a request names and what a
#: downloaded file is called, so it holds nothing a path or a URL reads as
#: anything but a name.
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")

#: The longest a name, a version, a description and an address may be. A name
#: and a version stand on one line of a window, and a description under them.
LONGEST_NAME = 80
LONGEST_VERSION = 20
LONGEST_DESCRIPTION = 500
LONGEST_ADDRESS = 2048

#: The most an entry may say it weighs. More than any CD holds, so an entry
#: claiming more is a mistake rather than a disc, and a download is held to it
#: while it is read.
LARGEST_BYTES = 1_000_000_000

#: One piece of software.
#:
#: `systems` are the identifiers of `systems.CATALOGUE` it runs on. `size`,
#: `algorithm` and `digest` are what the file at `address` is, and a download
#: refuses anything that arrives as something else.
Entry = collections.namedtuple(
    "Entry",
    "identifier name description group version systems address size algorithm digest kind")

#: Every entry this project ships.
CATALOGUE = (
    # Measured on 27 October 2026 from the item's own metadata on archive.org.
    Entry("nextstep-3.3-developer", "NeXTSTEP 3.3 Developer",
          "Compiler, Interface Builder, Project Builder and the documentation "
          "for NeXTSTEP 3.3.",
          "developer", "3.3", ("nextstep-3.3",),
          "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP_3.3_Developer.iso",
          403111936, "sha1", "268c66059c3c48df3bb4d2498785f2459bfa73cd", "disc"),
)

#: By identifier, which is what a request carries.
BY_IDENTIFIER = {entry.identifier: entry for entry in CATALOGUE}


def find(identifier):
    """The entry of that name.

    @param identifier - What a request asked for.
    @returns Entry, or None where nothing is called that.
    """
    return BY_IDENTIFIER.get(identifier)


def for_system(system):
    """What can be put on a machine running that system.

    @param system - An identifier of `systems.CATALOGUE`, or None where no
      system is booted.
    @returns list of Entry, in catalog order, empty where nothing is for it.
    """
    return [entry for entry in CATALOGUE if system in entry.systems]


def problems(entry):
    """Which fields of an entry break their rule.

    @param entry - An Entry.
    @returns list of field names, in the order Entry has them, empty where the
      entry is well formed.

    By field rather than as one verdict, so the window that edits an entry
    can say what is wrong beside the field it is wrong in. A digest is judged
    against its algorithm only where the algorithm is one this knows.
    """
    wrong = []
    if not IDENTIFIER.match(entry.identifier or ""):
        wrong.append("identifier")
    if not _is_line(entry.name, LONGEST_NAME):
        wrong.append("name")
    if not _is_text(entry.description, LONGEST_DESCRIPTION):
        wrong.append("description")
    if entry.group not in GROUPS:
        wrong.append("group")
    if not _is_line(entry.version, LONGEST_VERSION):
        wrong.append("version")
    if not entry.systems or any(systems.find(system) is None for system in entry.systems):
        wrong.append("systems")
    if not _is_address(entry.address):
        wrong.append("address")
    if not _is_size(entry.size):
        wrong.append("size")
    if entry.algorithm not in DIGEST_DIGITS:
        wrong.append("algorithm")
    elif not re.fullmatch("[0-9a-f]{%d}" % DIGEST_DIGITS[entry.algorithm], entry.digest or ""):
        wrong.append("digest")
    if entry.kind not in KINDS:
        wrong.append("kind")
    return wrong


def source(entry):
    """@returns str - The host an entry is downloaded from, which is what the
    Info window shows as where it comes from."""
    return urllib.parse.urlsplit(entry.address).hostname or ""


def described(entry):
    """One entry as the browser reads it.

    @param entry - An Entry.
    @returns dict, every field of the entry, `source` as the Info window shows
      where it comes from, and `for` as the names of the systems it is for,
      which is how a person reads `systems`.
    """
    return {
        **entry._asdict(),
        "systems": list(entry.systems),
        "for": [systems.find(system).name for system in entry.systems],
        "source": source(entry),
    }


def _is_text(value, longest):
    """@returns bool - Whether it is a string of at most that many characters
    with no control characters in it but line breaks."""
    return (isinstance(value, str) and len(value) <= longest
            and not any(ord(character) < 0x20 and character != "\n"
                        or ord(character) == 0x7f for character in value))


def _is_line(value, longest):
    """@returns bool - Whether it is one line of text, not empty and at most
    that many characters long."""
    return _is_text(value, longest) and bool(value.strip()) and "\n" not in value


def _is_size(value):
    """@returns bool - Whether it is a number of bytes an entry may weigh. A
    bool is an int to Python and is not a size to anybody."""
    return (isinstance(value, int) and not isinstance(value, bool)
            and 0 < value <= LARGEST_BYTES)


def _is_address(value):
    """Whether an entry may be downloaded from there.

    @param value - What the entry names.
    @returns bool

    https only, so what arrives is what the host sent. No name and password in
    it, because an entry is shown to everybody who opens it. And a host name
    rather than an address, because an address can be one inside this network,
    which an entry must not be able to point the Pi at; where a name resolves
    to is checked again when the download starts.
    """
    if not _is_line(value, LONGEST_ADDRESS) or any(character.isspace() for character in value):
        return False
    try:
        parts = urllib.parse.urlsplit(value)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return True
    return False
