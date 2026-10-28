"""Filling in a software entry from where the software is kept.

Somebody who has found a package on archive.org has its address and nothing
else, and everything else an entry needs is something archive.org already
says: the file's size and digest, what it is, and a description of the item
it belongs to. So an address is read by an adapter for the place it names, and
what the adapter learns fills the entry's fields. The systems it is for, its
group and its version are left to whoever adds it, because no archive says
those in a form anything could read.

An adapter is one class with two methods, and archive.org is the one there is.
Another place gets its own when somebody wants software from there.

Nothing from the answer is trusted. It is a third party's, so every value is
checked for type and length before it fills a field, and one that breaks its
rule is left out rather than filled in, which leaves that field to whoever adds
the entry.
"""

import html.parser
import json
import re
import urllib.error
import urllib.parse

from . import covers, fetching, software, systems
from .answers import told

#: How long archive.org may take to answer, which measured about one second
#: from a Pi on 27 October 2026.
TIMEOUT_SECONDS = 20

#: The most an answer about one item may be. NeXTSTEP33CISC's is 5642 bytes,
#: and an item of thousands of files is a few hundred kilobytes; anything past
#: this is not an answer about an item.
LONGEST_ANSWER = 4 * 1024 * 1024

#: What a floppy disk image is at most, 2.88 MB. archive.org calls a disk
#: image an ISO Image whatever its size, and one this small is no CD.
LARGEST_FLOPPY_BYTES = 2_949_120

#: The suffixes of a CD image, whatever archive.org calls the file.
DISC_SUFFIXES = (".iso", ".cdr", ".toast")


class Refused(Exception):
    """An address this cannot read, with what to tell the browser."""

    def __init__(self, reason, **values):
        super().__init__(reason)
        self.said = told(reason, **values)


class ArchiveOrg:
    """archive.org, which describes every item and every file in it at
    `https://archive.org/metadata/<item>`.

    An address names an item as `/details/<item>` or `/download/<item>`, and a
    file in it after that. The file's name is matched against the item's own
    list rather than used as given, so nothing typed into an address reaches
    the request but the item's identifier.
    """

    HOSTS = systems.ARCHIVE_HOSTS
    METADATA = "https://archive.org/metadata/%s"
    DOWNLOAD = "https://archive.org/download/%s/%s"

    #: What an item's identifier is made of, which the catalog knows as well,
    #: because it reads an entry's page out of its address.
    ITEM = software.ARCHIVE_ITEM

    #: The kinds of file archive.org keeps about an item rather than in it.
    NOT_CONTENT = ("Metadata", "Archive BitTorrent", "Item Tile", "JPEG Thumb")

    #: The kinds of picture a cover can be, as archive.org names them.
    PICTURES = ("JPEG", "PNG", "GIF")

    def handles(self, parts):
        """@returns bool - Whether the address is on archive.org itself."""
        return parts.hostname in ("archive.org", "www.archive.org")

    def look_up(self, parts, read):
        """What archive.org says about the item or the file the address names.

        @param parts - The address, as urllib.parse.urlsplit leaves it.
        @param read - Reads an address and answers its bytes.
        @returns dict, told("lookup.found", fields=...) where the address names
          a file or the item holds one worth having, and told("lookup.choose",
          files=...) where it holds several.
        @raises Refused
        """
        steps = [urllib.parse.unquote(step) for step in parts.path.split("/")]
        if len(steps) < 3 or steps[1] not in ("details", "download") \
                or not self.ITEM.match(steps[2]):
            raise Refused("lookup.not-an-item")
        item = steps[2]
        named = "/".join(steps[3:]) or None

        try:
            answer = json.loads(read(self.METADATA % item))
        except ValueError:
            raise Refused("lookup.unreadable") from None
        if answer == {}:
            raise Refused("lookup.no-such-item", item=item)
        files = answer.get("files") if isinstance(answer, dict) else None
        if not isinstance(files, list):
            raise Refused("lookup.unreadable")

        offered = [one for one in files if self._worth_having(one)]
        if named is not None:
            chosen = next((one for one in offered if one["name"] == named), None)
            if chosen is None:
                raise Refused("lookup.no-such-file", file=named)
        elif len(offered) == 1:
            chosen = offered[0]
        elif offered:
            return told("lookup.choose", files=[self._offer(item, one) for one in offered])
        else:
            raise Refused("lookup.nothing-to-offer", item=item)

        fields = self._fields(item, chosen, answer.get("metadata"))
        # The item's page rides along for the window, which shows View Origin
        # before the entry is kept. Kept, the page follows from its address.
        page = software.ARCHIVE_PAGE % item
        cover = self._cover(item, files, read)
        if cover is None:
            return told("lookup.found", fields=fields, page=page)
        address, picture = cover
        return told("lookup.found", fields={**fields, "cover": address},
                    picture=covers.data_address(picture), page=page)

    def _cover(self, item, files, read):
        """The thumbnail of the item's cover, where it has one.

        @param item - The item's identifier.
        @param files - Every file the item lists.
        @param read - Reads an address and answers its bytes.
        @returns (str, bytes), the thumbnail's address and the picture, or
          None. The picture whose name says front or cover is the cover,
          otherwise one that says folio, otherwise the first; its thumbnail is
          the one archive.org made of it.
        """
        pictures = [one for one in files if self._worth_having(one)
                    and one.get("format") in self.PICTURES]
        if not pictures:
            return None
        chosen = min(pictures, key=lambda one: self._rank(one["name"]))
        thumbnail = next((one for one in files if isinstance(one, dict)
                          and one.get("format") == "JPEG Thumb"
                          and one.get("original") == chosen["name"]
                          and isinstance(one.get("name"), str)), None)
        if thumbnail is None:
            return None
        address = self._address(item, thumbnail)
        picture = covers.fetched(address, read)
        return None if picture is None else (address, picture)

    def _rank(self, name):
        """@returns int - How surely a picture of that name is the cover, the
        surest first."""
        lowered = name.lower()
        if "front" in lowered or "cover" in lowered:
            return 0
        return 1 if "folio" in lowered else 2

    def _worth_having(self, one):
        """@returns bool - Whether a file of the item is one somebody came for,
        rather than archive.org's own record of it."""
        return (isinstance(one, dict) and isinstance(one.get("name"), str)
                and one.get("source") == "original"
                and one.get("format") not in self.NOT_CONTENT)

    def _offer(self, item, one):
        """@returns dict - One file of an item as the choice shows it."""
        return {"name": one["name"], "size": _size(one.get("size")),
                "kind": self._kind(one), "address": self._address(item, one)}

    def _fields(self, item, one, about):
        """The entry's fields for one file, each one only where it passes its
        rule.

        @param item - The item's identifier.
        @param one - The file, as the item's answer lists it.
        @param about - The item's own metadata, or whatever arrived instead.
        @returns dict of field to value, out of software.FIELDS.
        """
        fields = {
            "name": _name_of(one["name"]),
            "address": self._address(item, one),
            "kind": self._kind(one),
            "algorithm": "sha1",
        }
        size = _size(one.get("size"))
        if size is not None:
            fields["size"] = size
        digest = one.get("sha1")
        if isinstance(digest, str) and re.fullmatch("[0-9a-f]{40}", digest):
            fields["digest"] = digest
        description = about.get("description") if isinstance(about, dict) else None
        if isinstance(description, str):
            fields["description"] = plain_text(description, software.LONGEST_DESCRIPTION)
        return fields

    def _kind(self, one):
        """@returns str - "disc" for a CD image and "file" for anything else."""
        size = _size(one.get("size")) or 0
        looks_like_a_disc = one["name"].lower().endswith(DISC_SUFFIXES) \
            or one.get("format") == "ISO Image"
        return "disc" if looks_like_a_disc and size > LARGEST_FLOPPY_BYTES else "file"

    def _address(self, item, one):
        """@returns str - Where the file is downloaded from."""
        return self.DOWNLOAD % (item, urllib.parse.quote(one["name"]))


#: Every place an address can be read from.
ADAPTERS = (ArchiveOrg(),)


def look_up(address, read=None):
    """The fields an address fills in, or the files to choose from.

    @param address - What somebody dropped or typed.
    @param read - Reads an address and answers its bytes; `reading` where none
      is given, which asks the network.
    @returns (bool, dict) as every other operation of this service answers.
    """
    if not isinstance(address, str) or len(address) > software.LONGEST_ADDRESS:
        return False, told("lookup.not-an-address")
    try:
        parts = urllib.parse.urlsplit(address.strip())
        host = parts.hostname
    except ValueError:
        return False, told("lookup.not-an-address")
    if parts.scheme != "https" or not host:
        return False, told("lookup.not-an-address")

    adapter = next((one for one in ADAPTERS if one.handles(parts)), None)
    if adapter is None:
        return False, told("lookup.no-adapter", host=host)
    try:
        return True, adapter.look_up(parts, read or reading(adapter.HOSTS))
    except Refused as refused:
        return False, refused.said
    except (urllib.error.URLError, OSError) as error:
        return False, told("lookup.unreachable", detail=str(error))


def reading(hosts):
    """@returns A reader that asks the network, reaching only those hosts and
    refusing an answer longer than LONGEST_ANSWER.

    @param hosts - The hosts it may reach, as `fetching.allowed` takes them.
    """
    def read(url):
        with fetching.opened(url, hosts, TIMEOUT_SECONDS,
                             headers={"Accept": "application/json"}) as answer:
            body = answer.read(LONGEST_ANSWER + 1)
        if len(body) > LONGEST_ANSWER:
            raise Refused("lookup.unreadable")
        return body
    return read


def _size(value):
    """@returns int or None - A size archive.org states, which it states as a
    string, where it is a whole number of bytes a catalog entry may weigh."""
    if isinstance(value, str) and re.fullmatch("[0-9]+", value):
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool) \
            and 0 < value <= software.LARGEST_BYTES:
        return value
    return None


def _name_of(file_name):
    """@returns str - What an entry for that file is called: its name without
    the suffix, with spaces for underscores."""
    stem = file_name.rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    return " ".join(stem.replace("_", " ").split())[:software.LONGEST_NAME]


class _Text(html.parser.HTMLParser):
    """Collects the text of a piece of HTML and nothing else.

    A line break and the edge of a block part words the way a space does,
    because archive.org writes descriptions in lines parted by `<br>`, and the
    last word of one line and the first of the next are two words.
    """

    PARTING = {"br", "p", "div", "li", "tr", "td", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pieces = []

    def handle_starttag(self, tag, attrs):
        if tag in self.PARTING:
            self.pieces.append(" ")

    def handle_endtag(self, tag):
        if tag in self.PARTING:
            self.pieces.append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        self.pieces.append(data)


def plain_text(markup, longest):
    """The text of a piece of HTML, as one paragraph.

    @param markup - What archive.org keeps as an item's description.
    @param longest - The most characters the text may have.
    @returns str, every run of white space one space, cut at the last word that
      fits and closed with an ellipsis where it was cut.
    """
    reader = _Text()
    reader.feed(markup)
    reader.close()
    text = " ".join("".join(reader.pieces).split())
    if len(text) <= longest:
        return text
    return text[:longest - 1].rsplit(" ", 1)[0] + "…"
