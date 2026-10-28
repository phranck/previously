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

What is changed on the Pi lives in one file in the service's own state
directory, laid over the shipped list: an entry added, a shipped entry edited,
and a shipped entry removed. The shipped list stays as it came with the
package, so an update brings its new entries and every change made here
survives it, and an edited or removed shipped entry can always be brought back.
`saved.py` keeps the configurations somebody saved the same way.
"""

import collections
import hashlib
import ipaddress
import json
import os
import re
import urllib.parse

from . import fetching, systems
from .answers import told

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
LONGEST_VERSION = 40
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
#: refuses anything that arrives as something else. `cover` is the address of
#: a thumbnail of its cover on archive.org, or empty.
Entry = collections.namedtuple(
    "Entry",
    "identifier name description group version systems address size algorithm digest kind cover")

#: Every entry this project ships.
CATALOGUE = (
    # Measured on 27 October 2026 from the item's own metadata on archive.org.
    Entry("nextstep-3.3-developer", "NeXTSTEP 3.3 Developer",
          "Compiler, Interface Builder, Project Builder and the documentation "
          "for NeXTSTEP 3.3.",
          "developer", "3.3", ("nextstep-3.3",),
          "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP_3.3_Developer.iso",
          403111936, "sha1", "268c66059c3c48df3bb4d2498785f2459bfa73cd", "disc",
          "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP%20CD%20Folio_thumb.jpg"),
)

#: Where the page asks for an entry's cover, which the Pi fetches from
#: archive.org once and hands out itself after that.
COVER_ROUTE = "/api/software/cover"

#: The hosts a cover may come from, which are the ones the adapter reads.
ARCHIVE_HOSTS = systems.ARCHIVE_HOSTS

#: What an item's identifier on archive.org is made of, and where its page is.
#: An item is downloaded from `/download/<item>/<file>` and described at
#: `/details/<item>`, so the page of an entry follows from its address.
ARCHIVE_ITEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
ARCHIVE_PAGE = "https://archive.org/details/%s"

#: By identifier, which is what a request carries.
BY_IDENTIFIER = {entry.identifier: entry for entry in CATALOGUE}

#: The fields the browser sends for an entry: all of them but the identifier,
#: which follows from the name when an entry is added and never changes after.
FIELDS = tuple(field for field in Entry._fields if field != "identifier")

#: What the file of changes is called, in the service's state directory.
OVERLAY = "software.json"

#: What that file says about itself, so a later format can tell itself apart.
FILE_VERSION = 1

#: What is changed on the Pi: the entries added or edited, in the order they
#: were first written, and the identifiers of the shipped entries removed.
Overlay = collections.namedtuple("Overlay", "entries removed")
NOTHING_CHANGED = Overlay((), ())


class NotReadable(Exception):
    """The file of changes is there and cannot be read as this format.

    Every change refuses while it is, because writing would destroy whatever
    could not be read, and the shipped list is offered in the meantime.
    """


def find(identifier, path=None):
    """The entry of that name, as the catalog lists it on this Pi.

    @param identifier - What a request asked for.
    @param path - pathlib.Path of the file of changes, or None for the shipped
      list alone.
    @returns Entry, or None where nothing is called that.
    """
    return next((entry for entry in catalogue(path) if entry.identifier == identifier), None)


def for_system(system, path=None):
    """What can be put on a machine running that system.

    @param system - An identifier of `systems.CATALOGUE`, or None where no
      system is booted.
    @param path - pathlib.Path of the file of changes, or None for the shipped
      list alone.
    @returns list of Entry, in catalog order, empty where nothing is for it.
    """
    return [entry for entry in catalogue(path) if system in entry.systems]


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
    if not (isinstance(entry.identifier, str) and IDENTIFIER.match(entry.identifier)):
        wrong.append("identifier")
    if not _is_line(entry.name, LONGEST_NAME):
        wrong.append("name")
    if not _is_text(entry.description, LONGEST_DESCRIPTION):
        wrong.append("description")
    if entry.group not in GROUPS:
        wrong.append("group")
    # Plenty of software names no version, so none is no fault, and one is
    # written however the software writes it.
    if not (entry.version == "" or _is_line(entry.version, LONGEST_VERSION)):
        wrong.append("version")
    if not (isinstance(entry.systems, tuple) and entry.systems
            and all(isinstance(system, str) and systems.find(system) is not None
                    for system in entry.systems)):
        wrong.append("systems")
    if not _is_address(entry.address):
        wrong.append("address")
    if not _is_size(entry.size):
        wrong.append("size")
    if not (isinstance(entry.algorithm, str) and entry.algorithm in DIGEST_DIGITS):
        wrong.append("algorithm")
    elif not (isinstance(entry.digest, str)
              and re.fullmatch("[0-9a-f]{%d}" % DIGEST_DIGITS[entry.algorithm], entry.digest)):
        wrong.append("digest")
    if entry.kind not in KINDS:
        wrong.append("kind")
    if not (entry.cover == "" or _is_on_the_archive(entry.cover)):
        wrong.append("cover")
    return wrong


def source(entry):
    """@returns str - The host an entry is downloaded from, which is what the
    Info window shows as where it comes from."""
    return urllib.parse.urlsplit(entry.address).hostname or ""


def described(entry):
    """One entry as the browser reads it.

    @param entry - An Entry.
    @returns dict, every field of the entry, `source` as the Info window shows
      where it comes from, `for` as the names of the systems it is for, which
      is how a person reads `systems`, `picture` as where the page gets its
      cover, or None where it has none, and `page` as the archive.org page
      View Origin opens, or "" where it has none.
    """
    return {
        **entry._asdict(),
        "systems": list(entry.systems),
        "for": [systems.find(system).name for system in entry.systems],
        "source": source(entry),
        "picture": picture_of(entry),
        "page": page_of(entry.address),
    }


def page_of(address):
    """The archive.org page of the item a file is downloaded from.

    @param address - Where an entry is downloaded from.
    @returns str, `https://archive.org/details/<item>` for an address
      `https://archive.org/download/<item>/<file>`, and "" for any other.

    The item is part of the address, so every entry downloaded from
    archive.org has its page, whether its address was dropped or typed in.
    """
    if not isinstance(address, str) or not fetching.allowed(address, ARCHIVE_HOSTS):
        return ""
    steps = urllib.parse.urlsplit(address).path.split("/")
    if len(steps) < 4 or steps[1] != "download" or not ARCHIVE_ITEM.match(steps[2]):
        return ""
    return ARCHIVE_PAGE % steps[2]


def picture_of(entry):
    """Where the page gets an entry's cover.

    @param entry - An Entry.
    @returns str, the cover route with the entry and a stamp of the cover's
      address, or None where it has no cover. The stamp makes a changed cover
      a new address, so no browser goes on showing the one before.
    """
    if not entry.cover:
        return None
    return "%s?%s" % (COVER_ROUTE, urllib.parse.urlencode(
        {"entry": entry.identifier, "v": stamp(entry.cover)}))


def stamp(cover):
    """@returns str - Twelve hexadecimal digits that change with the cover's
    address."""
    return hashlib.sha1(cover.encode("utf-8")).hexdigest()[:12]


def overlay_in(state_directory):
    """@returns pathlib.Path - Where the file of changes is kept, in the
    service's state directory."""
    return state_directory / OVERLAY


def read(path):
    """What is changed on this Pi.

    @param path - pathlib.Path of the file of changes, or None.
    @returns Overlay, empty where there is no file.
    @raises NotReadable - The file is there and is not this format, or holds an
      entry that breaks a rule. Nothing writes such an entry, so one there was
      written by hand, and a download must not read it.
    """
    if path is None:
        return NOTHING_CHANGED
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return NOTHING_CHANGED
    except (OSError, ValueError) as error:
        raise NotReadable(str(error)) from error

    entries = found.get("entries") if isinstance(found, dict) else None
    removed = found.get("removed") if isinstance(found, dict) else None
    if not isinstance(entries, list) or not isinstance(removed, list):
        raise NotReadable("%s holds no list of entries and of what was removed" % path)
    if not all(isinstance(identifier, str) for identifier in removed):
        raise NotReadable("%s names something removed by other than its identifier" % path)

    kept = []
    for values in entries:
        # An entry written before covers existed has none. One written by a
        # build of 28 October 2026 carries a page, which is dropped, because
        # the page follows from the address.
        if isinstance(values, dict):
            values = {"cover": "", **values}
            values.pop("page", None)
        if not isinstance(values, dict) or set(values) != set(Entry._fields):
            raise NotReadable("%s holds an entry with other fields than an entry has" % path)
        entry = _entry(values["identifier"], values)
        wrong = problems(entry)
        if wrong:
            raise NotReadable("%s holds %s with %s that break their rules"
                              % (path, entry.identifier, ", ".join(wrong)))
        kept.append(entry)
    return Overlay(tuple(kept), tuple(removed))


def catalogue(path=None):
    """Every entry as this Pi lists it: the shipped ones as they were changed
    here, without those removed here, then those added here.

    @param path - pathlib.Path of the file of changes, or None.
    @returns tuple of Entry. The shipped list alone where the file cannot be
      read, because a listing has nothing to do about that: the moment
      somebody changes something, the change refuses and says why.
    """
    return tuple(entry for entry, _ in _merged(_readable(path)))


def origins(path=None):
    """Which entries are not as shipped.

    @param path - pathlib.Path of the file of changes, or None.
    @returns dict of identifier to "changed" for a shipped entry edited here or
      "added" for one added here. A shipped entry as it came is not in it.
    """
    return {entry.identifier: origin for entry, origin in _merged(_readable(path))
            if origin != "shipped"}


def removed(path=None):
    """The shipped entries removed here, which can be brought back.

    @param path - pathlib.Path of the file of changes, or None.
    @returns tuple of Entry, as shipped, in the shipped order.
    """
    gone = _readable(path).removed
    return tuple(entry for entry in CATALOGUE if entry.identifier in gone)


def save(path, values, replacing=None):
    """Adds an entry, or writes over one.

    @param path - pathlib.Path of the file of changes.
    @param values - The entry's fields as the browser sends them, which are
      FIELDS and nothing else.
    @param replacing - The identifier of the entry being edited, or None to add
      one. An entry keeps its identifier when it is edited, because a file
      downloaded for it is named after that.
    @returns (bool, dict) as every other operation of this service answers.
    """
    try:
        overlay = read(path)
    except NotReadable as error:
        return False, told("software.not-readable", detail=str(error))

    if not isinstance(values, dict) or set(values) != set(FIELDS):
        return False, told("software.not-an-entry")

    listed = [entry.identifier for entry, _ in _merged(overlay)]
    if replacing is not None and replacing not in listed:
        return False, told("software.no-such", asked=replacing)

    name = values["name"].strip() if isinstance(values["name"], str) else values["name"]
    entry = _entry(replacing or _identifier_from(name), {**values, "name": name})
    # The identifier follows from the name, so a name that makes none is what
    # is wrong.
    wrong = list(dict.fromkeys("name" if field == "identifier" else field
                               for field in problems(entry)))
    if wrong:
        return False, told("software.refused", fields=wrong)
    if replacing is None and entry.identifier in listed + list(overlay.removed):
        return False, told("software.name-taken", name=name)

    entries = [kept for kept in overlay.entries if kept.identifier != entry.identifier]
    if entry != BY_IDENTIFIER.get(entry.identifier):
        at = next((index for index, kept in enumerate(overlay.entries)
                   if kept.identifier == entry.identifier), len(entries))
        entries.insert(at, entry)
    return _write(path, Overlay(tuple(entries), overlay.removed),
                  told("software.kept", name=name))


def remove(path, identifier):
    """Takes an entry out of the catalog.

    @param path - pathlib.Path of the file of changes.
    @param identifier - Which one.
    @returns (bool, dict)

    One added here is gone for good. A shipped one is written down as removed,
    because the shipped list cannot change, and can be brought back.
    """
    try:
        overlay = read(path)
    except NotReadable as error:
        return False, told("software.not-readable", detail=str(error))

    found = next((entry for entry, _ in _merged(overlay) if entry.identifier == identifier), None)
    if found is None:
        return False, told("software.no-such", asked=identifier)

    entries = tuple(kept for kept in overlay.entries if kept.identifier != identifier)
    gone = overlay.removed + ((identifier,) if identifier in BY_IDENTIFIER else ())
    return _write(path, Overlay(entries, gone), told("software.removed", name=found.name))


def restore(path, identifier):
    """Brings a shipped entry back as it was shipped, edited or removed.

    @param path - pathlib.Path of the file of changes.
    @param identifier - Which one.
    @returns (bool, dict)
    """
    try:
        overlay = read(path)
    except NotReadable as error:
        return False, told("software.not-readable", detail=str(error))

    shipped = BY_IDENTIFIER.get(identifier) if isinstance(identifier, str) else None
    if shipped is None:
        return False, told("software.not-shipped", asked=identifier)

    return _write(path,
                  Overlay(tuple(kept for kept in overlay.entries if kept.identifier != identifier),
                          tuple(gone for gone in overlay.removed if gone != identifier)),
                  told("software.restored", name=shipped.name))


def _readable(path):
    """@returns Overlay - What `read` answers, and nothing changed where the
    file cannot be read."""
    try:
        return read(path)
    except NotReadable:
        return NOTHING_CHANGED


def _merged(overlay):
    """The shipped list with the changes laid over it.

    @param overlay - An Overlay.
    @returns list of (Entry, origin), origin being "shipped", "changed" or
      "added": the shipped entries in their order, then the added ones in the
      order they were added.
    """
    changed = {entry.identifier: entry for entry in overlay.entries}
    merged = [(changed[shipped.identifier], "changed") if shipped.identifier in changed
              else (shipped, "shipped")
              for shipped in CATALOGUE if shipped.identifier not in overlay.removed]
    merged += [(entry, "added") for entry in overlay.entries
               if entry.identifier not in BY_IDENTIFIER]
    return merged


def _entry(identifier, values):
    """@returns Entry - One built from its fields, with its systems as a tuple
    where they came as a list, which is what JSON carries."""
    fields = {field: values[field] for field in FIELDS}
    if isinstance(fields["systems"], list):
        fields["systems"] = tuple(fields["systems"])
    return Entry(identifier=identifier, **fields)


def _identifier_from(name):
    """What an entry added under that name is identified by.

    @param name - Its name.
    @returns str, the name in lowercase with every run of anything but letters,
      digits and dots written as one hyphen, or "" where nothing is left.
    """
    if not isinstance(name, str):
        return ""
    return re.sub(r"[^a-z0-9.]+", "-", name.lower()).strip("-.")[:64].rstrip("-.")


def _write(path, overlay, said):
    """Writes the whole file of changes, or says why it could not.

    @param path - pathlib.Path of the file.
    @param overlay - Everything changed, as it is to be written.
    @param said - What to answer with where it worked.
    @returns (bool, dict)

    Written beside itself and moved into place, so a write that fails part way
    leaves the file as it was. The state directory is the service's own, which
    its unit creates.
    """
    beside = path.with_suffix(path.suffix + ".new")
    body = json.dumps({
        "version": FILE_VERSION,
        "entries": [{**entry._asdict(), "systems": list(entry.systems)}
                    for entry in overlay.entries],
        "removed": list(overlay.removed),
    }, ensure_ascii=False, indent=2) + "\n"
    try:
        beside.write_text(body, encoding="utf-8")
        os.replace(beside, path)
    except OSError as error:
        beside.unlink(missing_ok=True)
        return False, told("software.could-not-write", detail=str(error))
    return True, said


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


def _is_on_the_archive(value):
    """@returns bool - Whether it is an address an entry may hold, on one of
    ARCHIVE_HOSTS, which is where a cover is fetched from."""
    return _is_address(value) and fetching.allowed(value, ARCHIVE_HOSTS)
