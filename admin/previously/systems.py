"""The systems that can be put on this machine, and where they come from.

Six disks are prepared and ready to boot, from NeXTSTEP 2.2 to OPENSTEP 4.2.
Each is a two gigabyte disk holding an installed system, packed into an archive
of a few tens of megabytes: a disk that size is mostly zeros, which is why 1.87
gigabytes travel as 58.

This module is the whole of what may be fetched. The helper that does the
fetching holds no address of its own and takes none from a request, so a system
is asked for by name and the name is looked up here. That is what makes the
privileged half unable to be pointed anywhere else.

Previous emulates 68k hardware, so the Intel builds of OPENSTEP are not here
whatever they are called on archive.org: one would download, unpack and never
boot.
"""

import collections
import os
import urllib.parse

from . import fetching

#: Where the archives are kept, and the one host anything here is fetched from.
#: `ARCHIVE_HOSTS` is what a fetch may reach, as `fetching.allowed` takes it, so
#: the one name also covers whichever node holds the item: archive.org answers a
#: download with a redirect to one of those.
ARCHIVE = "https://archive.org/download"
ARCHIVE_HOSTS = ("archive.org",)

#: What archive.org states about each item, and therefore what a fetch of one is
#: checked with. Beside the table that holds those digests rather than at the
#: place the check happens, because it is a fact about this archive.
ALGORITHM = "sha1"

#: What one of these disks comes to once it is unpacked. Measured on the
#: reference machine: `NS33_2GB.dd` is 2,012,774,400 bytes. All six are two
#: gigabyte disks, so this is what each of them costs on the card.
UNPACKED_BYTES = 2_012_774_400

#: What is left over after anything large is written, so that a card filling up
#: is a refusal in front rather than a write stopping half way through.
SPARE_BYTES = 500_000_000

#: What has to be free before a system is fetched: the disk, the archive beside
#: it while it unpacks, and that margin.
ROOM_BYTES = UNPACKED_BYTES + SPARE_BYTES

#: The least a file in one of these archives can be and still be the disk. The
#: rest of what they carry is ROM images, a Windows binary and a text file, and
#: none of those comes near this.
SMALLEST_DISK_BYTES = 512 * 1024 * 1024

#: What a disk image is called once it is here. The identifier, so the file
#: says which system it holds rather than `NS33_2GB.dd`.
DISK_SUFFIX = ".dd"

#: Where the copies of those disks are kept, inside the folder they are copies
#: of. A folder holding both the thing that runs and the thing that is kept is
#: one where the two look alike.
BACKUPS = "backups"

#: One prepared system.
#:
#: `item` and `file` are what archive.org calls it, which together make the
#: address. `size` and `digest` are what that file is, measured on
#: 28 September 2026 from the item's own metadata, and the helper refuses
#: anything that arrives as something else.
System = collections.namedtuple("System", "identifier name item file size digest")

#: Every system that can be fetched, oldest first.
CATALOGUE = (
    System("nextstep-2.2", "NeXTSTEP 2.2",
           "nextstep-2.2-hd-image-with-previous.-7z",
           "Nextstep 2.2 HD Image With Previous.7z",
           23459626, "08bfba677ba7752a84ca9278a2fb3a6e2e7143de"),
    System("nextstep-3.0", "NeXTSTEP 3.0",
           "nextstep-3.0-hd-image-with-previous.-7z",
           "Nextstep 3.0 HD Image With Previous.7z",
           25500729, "bbdc5d1b2c5a7b4c36ebb04875c409a102fc76db"),
    System("nextstep-3.2", "NeXTSTEP 3.2",
           "nextstep-3.2-hd-image-with-previous.-7z",
           "Nextstep 3.2 HD Image With Previous.7z",
           39160503, "c1eb7db454707c134f5351115c9a4d53058f4813"),
    System("nextstep-3.3", "NeXTSTEP 3.3",
           "nextstep-3.3-hd-image-with-previous.-7z",
           "Nextstep 3.3 HD Image With Previous.7z",
           60508875, "504f587e140de5a907de40dc3c0b3a8419d3b026"),
    System("openstep-4.0", "OPENSTEP 4.0",
           "openstep-4.0-hd-image-with-previous.-7z",
           "Openstep 4.0 HD Image With Previous.7z",
           74558432, "0521fd7e2e3954757699efd2e96d3f6895532fd1"),
    System("openstep-4.2", "OPENSTEP 4.2",
           "openstep-4.2-hd-image-with-previous.-7z",
           "Openstep 4.2 HD Image With Previous.7z",
           75010299, "580f900a630ea2b5e4b38ed652582b749705f21c"),
)

#: What comes with the emulator where nobody chose otherwise, so that a machine
#: which has just been set up boots into a system rather than into a prompt
#: about what to do next. The last release NeXT made for its own hardware.
DEFAULT = "nextstep-3.3"

#: By identifier, which is what a request carries.
BY_IDENTIFIER = {system.identifier: system for system in CATALOGUE}


def find(identifier):
    """The system of that name.

    @param identifier - What a request asked for.
    @returns System, or None where nothing is called that. Unknown is not an
      error here: the caller decides what to say about it.
    """
    return BY_IDENTIFIER.get(identifier)


def address(system):
    """Where to fetch it from.

    @param system - A System.
    @returns str, an https address on ARCHIVE.

    Built here rather than written into the table, because the prefix is the
    same for all six and a table holding it six times is six chances to get one
    of them wrong.
    """
    return "%s/%s/%s" % (ARCHIVE, system.item,
                         urllib.parse.quote(system.file))


def expected(system):
    """What a fetch of this system has to turn out to be.

    @param system - A System.
    @returns fetching.Expecting

    Built here rather than at the fetch, so that the algorithm those digests are
    in stays beside the table holding them.
    """
    return fetching.Expecting(system.name, system.size, system.digest,
                              ALGORITHM)


def disk_name(system):
    """@returns str - What this system's disk image is called once it is here."""
    return system.identifier + DISK_SUFFIX


def disk_in(disks, system):
    """Where this system's disk is, or None where it is not here.

    @param disks - pathlib.Path of the folder the disks live in.
    @param system - A System.
    @returns pathlib.Path or None

    Two places, because `install.sh` got there first. It unpacks the archive as
    it comes, which leaves the disk inside a folder named after the archive, and
    a machine set up that way is one this must recognize rather than fetch a
    second copy for. Anything fetched from here is one file named after the
    system.
    """
    named = disks / disk_name(system)
    if named.is_file():
        return named

    beside = disks / system.file[:-len(".7z")]
    if beside.is_dir():
        for found in sorted(beside.iterdir()):
            if found.is_file() and found.stat().st_size >= SMALLEST_DISK_BYTES:
                return found
    return None


def here(disks):
    """Which systems are on this machine.

    @param disks - pathlib.Path of the folder the disks live in.
    @returns dict of identifier to the path of its disk.
    """
    found = {}
    for system in CATALOGUE:
        disk = disk_in(disks, system)
        if disk is not None:
            found[system.identifier] = disk
    return found


def backups_in(disks):
    """Where the copies of the disks are kept.

    @param disks - pathlib.Path of the folder the disks live in.
    @returns pathlib.Path

    Beside the disks rather than among them, because a folder holding both is
    one where the thing that runs and the thing that is kept look alike. It is
    in the same home for the same reason the disks are: a copy somebody waited
    ten minutes for is theirs.
    """
    return disks / BACKUPS


def copies_in(disks):
    """Every copy that has been made, newest first.

    @param disks - pathlib.Path of the folder the disks live in.
    @returns list of (path, System or None). The system is read off the name,
      and a copy whose name says nothing this knows still appears: it is on the
      card either way and hiding it would be hiding what is taking the room.
    """
    where = backups_in(disks)
    try:
        found = [path for path in where.iterdir()
                 if path.is_file() and path.suffix == DISK_SUFFIX]
    except OSError:
        return []
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return [(path, find(path.stem.split(" ", 1)[0])) for path in found]


def a_copy_of(system, when):
    """What a copy is called.

    @param system - The System it is a copy of.
    @param when - datetime of the moment it was made.
    @returns str

    The identifier first, so the system can be read back off the name by
    splitting at the first space, and the moment after it, because that is the
    one thing that tells two copies of the same system apart. Written in a form
    that sorts the way it reads, with periods where a clock has colons,
    which a filesystem takes and a colon is not worth arguing with.
    """
    return "%s %s%s" % (system.identifier,
                        when.strftime("%Y-%m-%d %H.%M.%S"), DISK_SUFFIX)


def room_beside(disks):
    """How much room there is for another one.

    @param disks - pathlib.Path of the folder the disks live in, which need not
      exist yet: the nearest place above it that does is on the same card.
    @returns int, free bytes, or None where nothing can be asked.

    Read from the file system rather than remembered, because what is free
    changes with everything else on the machine and a figure from five minutes
    ago is what lets an unpack stop half way through a disk image.
    """
    place = disks
    while not place.exists() and place != place.parent:
        place = place.parent
    try:
        stats = os.statvfs(place)
    except OSError:
        return None
    return stats.f_bavail * stats.f_frsize
