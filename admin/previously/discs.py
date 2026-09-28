"""The media that go beside the system, rather than instead of it.

A system is a disk and the machine boots it. Developer Tools, applications and
whatever else somebody wants inside NeXTSTEP are media: they go on a free SCSI
slot beside the disk that is running, write protected, and NeXTSTEP mounts them
the way it mounted a CD on the bus.

They are files somebody puts on the Pi rather than anything this tool fetches.
The six systems are a known set with measured sizes and digests, and these are
not: a NeXT CD is somebody's own copy of media they have, and a list of
addresses for them would be a list this tool cannot stand behind. So the folder
is shown, what is in it is offered, and what is not in it is said plainly.

**NeXT's own CDs are not ISO 9660.** They carry a variation of 4.3BSD FFS, so
an ISO 9660 image mounts nowhere in NeXTSTEP however good it is. That one is
worth catching, because it is the mistake somebody makes with the first image
they try, and an image that is silently not mounted teaches nothing.
"""

import pathlib

#: Where they live, beside the disks in the same home. A folder of its own,
#: because a disc and a disk are two kinds of thing and a folder holding both
#: is one where they look alike.
DISCS = "discs"

#: What Previous calls a CD on the bus, from the `SCSI_DEVTYPE` enumeration in
#: its src/includes/configuration.h, which counts none, hard disk, CD and
#: floppy from zero.
CD = "2"
NOTHING = "0"

#: Where ISO 9660 says so about itself: the first volume descriptor sits in the
#: seventeenth sector of 2048 bytes, and its second field is this.
ISO_SIGNATURE = b"CD001"
ISO_AT = 0x8001

#: What a disc image is called. Anything, because these are somebody's own
#: files, and the suffixes NeXT media actually arrive as.
SUFFIXES = (".iso", ".img", ".dd", ".raw", ".cdr")


def folder(disks):
    """@param disks - pathlib.Path the disk images live in.
    @returns pathlib.Path of the folder discs live in, beside them."""
    return pathlib.Path(disks) / DISCS


def here(disks):
    """Every disc somebody has put on this machine.

    @param disks - pathlib.Path the disk images live in.
    @returns list of pathlib.Path, by name, and empty where the folder is not
      there. A folder nobody has made is the ordinary state of a machine
      nobody has put a disc on.
    """
    try:
        found = [path for path in folder(disks).iterdir()
                 if path.is_file() and path.suffix.lower() in SUFFIXES]
    except OSError:
        return []
    return sorted(found, key=lambda path: path.name.lower())


def find(disks, name):
    """The disc of that name.

    @param disks - pathlib.Path the disk images live in.
    @param name - What arrived in a request.
    @returns pathlib.Path, or None where nothing of that name is there.

    Matched against the listing rather than joined onto a path, so a name
    carrying separators asks for a file that is not in the answer. Nothing that
    arrives from a browser reaches the filesystem as a path.
    """
    for path in here(disks):
        if path.name == name:
            return path
    return None


def is_iso_9660(path):
    """Whether this image says it is ISO 9660.

    @param path - pathlib.Path of the image.
    @returns bool. False where it cannot be read, because a file that cannot be
      read is not a file this can say anything about.

    A positive test and nothing more. An image that says ISO 9660 will mount
    nowhere in NeXTSTEP, which is worth saying before somebody waits for it. An
    image that says nothing may still be anything at all, and this claims
    nothing about those.
    """
    try:
        with open(path, "rb") as image:
            image.seek(ISO_AT)
            return image.read(len(ISO_SIGNATURE)) == ISO_SIGNATURE
    except OSError:
        return False
