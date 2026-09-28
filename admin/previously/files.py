"""What Previously shows as a filesystem, which is not one.

Nothing here is on the card. These are the things this tool has, arranged the
way NeXTSTEP arranged things, because a person choosing between eleven machines
and three applications is choosing in a place rather than reading a list.

    Previously          the root, drawn as a home the way NeXTSTEP drew one
      Apps
        Config Editor.app
        Grab.app
        Installer.app
        Preferences.app
        Preview.app
        Terminal.app
      Documents
        Pictures        the one real place here, holding the screenshots
      Machines
        System          the eleven this project ships, which cannot be changed
        User            what somebody saved, and only once there is something

Documents is the exception and is read off the card, because a picture is a
file and files change. These are looked at here rather than in NeXTSTEP, so
they are PNG, which is what a browser reads and what keeps a screen's edges
and lettering sharp.

The whole thing is small enough to hand over at once, so there is one route and
the browser walks it. Paths are written the way they read, with slashes, and
they are what a request names when it wants one particular place.

A viewer shows names, so everything here is named once and read the same in
every language: the folders, the bundles, the machines and Previously itself.
NeXTSTEP did that too, and its own installations are the evidence. `/NextApps`
in a German one holds `Preferences.app` and `Terminal.app`, exactly as an
English one does, and the Workspace shows the directory called `Apps` under
that name.

What an application is called in words is the other half, and NeXTSTEP did
translate that: the same application titled its window `Präferenzen`. So an
application carries the name of a string as well, and that name is used
wherever it is spoken rather than where its bundle is shown.
"""

import datetime
import pathlib

from . import config, machines, saved, systems

#: What the root is called and what it wears. NeXTSTEP drew a person's own
#: directory as a house, and this is the one place everything here lives in.
#: The name is the tool's own and is not translated.
ROOT = "Previously"
HOME_ICON = "home"

#: Where the real part of this tree stands, as the viewer reads it. The same
#: two steps are the path under the directory the service is configured with,
#: so what is on the screen says where the file is.
DOCUMENTS = "/Documents"
PICTURES = "/Documents/Pictures"

#: Where the disks stand, beside the machines rather than inside them. A disk
#: and a machine are two things: one is what the hardware is, the other is what
#: is installed on it, and either can be changed without the other.
DISKS = "/Disks"

#: And where the copies of them stand, inside Disks rather than beside them: a
#: folder holding both is one where the thing that runs and the thing that is
#: kept look alike.
BACKUPS = "/Disks/Backups"

#: What a disk wears. It is a hard disk, so it wears the one NeXTSTEP drew for
#: a hard disk. What it arrived as is not what it is.
DISK_ICON = "winchester"

#: Which set a machine belongs to. The eleven this project ships cannot be
#: changed, and everything somebody saved can, so every machine says which it is
#: and the browser does not have to read that out of a path.
SYSTEM = "system"
USER = "user"

#: A folder, and the four applications, by the pictures they carry. Three wear
#: what NeXTSTEP drew for them, Grab included: NeXT shipped an application for
#: taking a picture of the screen and called it that, and this one carries its
#: name and its camera. The editor has no face of its own, so it wears what
#: NeXTSTEP drew for an application that brought none.
FOLDER_ICON = "folder"
DEFAULT_APP_ICON = "defaultAppIcon"
GRAB_ICON = "Grab"
#: What the Installer wears. NeXT shipped an application for putting software
#: on a machine and taking it off again and called it Installer, and this one
#: does the same job for the emulator and the systems it runs, so it carries
#: that name and the open package that bundle drew.
INSTALLER_ICON = "Installer"
PREFERENCES_ICON = "Preferences"
TERMINAL_ICON = "Terminal"

#: What Preview wears. Its bundle held no icon file, so the picture it drew for
#: a document is what the application went by.
PREVIEW_ICON = "tiff"

#: And what a picture wears, by its format. NeXTSTEP had no generic icon for a
#: picture: it drew one per format, a sheet with the name across the top and
#: the kind of content underneath. There was no PNG then, so design/makepng.py
#: draws that one in the same manner out of the same sheet.
PICTURE_ICONS = {".png": "png", ".tiff": "tiff", ".tif": "tiff"}

#: And what anything else in a folder wears: a sheet with lines on it, which is
#: what the Workspace drew for a file it knew nothing about.
OTHER_FILE_ICON = "defaultIcon"

#: Which files are pictures, and therefore wear the one and open in Preview.
PICTURE_SUFFIXES = (".png", ".tiff", ".tif", ".jpg", ".jpeg", ".gif")
PREFERENCES_ICON = "Preferences"
TERMINAL_ICON = "Terminal"

#: The applications, in the order a viewer sorts them. Each carries its
#: picture, the window it opens and the name of what it is called in words,
#: which is not what its bundle is called. The editor is #50, and until it
#: exists choosing it says so.
APPLICATIONS = (
    ("Config Editor.app", DEFAULT_APP_ICON, "editor", "app.config-editor"),
    ("Grab.app", GRAB_ICON, "grab", "app.grab"),
    ("Installer.app", INSTALLER_ICON, "installer", "app.installer"),
    ("Preferences.app", PREFERENCES_ICON, "preferences", "app.preferences"),
    ("Preview.app", PREVIEW_ICON, "preview", "app.preview"),
    ("Terminal.app", TERMINAL_ICON, "terminal", "app.terminal"),
)


def tree(machines_file=None, documents=None, disks=None, booting=None):
    """Everything Previously holds, as one place with places in it.

    @param machines_file - pathlib.Path of the file the configurations somebody
      saved are kept in. None means there are none.
    @param documents - pathlib.Path the real part of this tree stands in.
      None leaves Documents empty rather than leaving it out, so the place a
      picture goes is visible before the first one is taken.
    @param disks - pathlib.Path the disk images live in. None leaves the Disks
      folder out, the way User is left out until something is in it.
    @param booting - What `previous.cfg` says the machine boots, as the whole
      path, so the disk that is in force can be marked.
    @returns dict, a folder with `name`, `icon`, `path` and `entries`, and a
      `label` on the applications, which is what each is called in words.
    """
    return _folder(ROOT, "/", HOME_ICON, [
        _folder("Apps", "/Apps", FOLDER_ICON, [
            {
                "name": name,
                "label": label,
                "icon": icon,
                "path": "/Apps/" + name,
                "kind": "application",
                "opens": opens,
            }
            for name, icon, opens, label in APPLICATIONS
        ]),
        *_disk_folder(disks, booting),
        _folder("Documents", DOCUMENTS, FOLDER_ICON, [
            _folder("Pictures", PICTURES, FOLDER_ICON, pictures(documents)),
        ]),
        _folder("Machines", "/Machines", FOLDER_ICON, _machine_folders(machines_file)),
    ])


def _disk_folder(disks, booting):
    """The Disks folder, where there is one to show.

    @param disks - pathlib.Path the disk images live in, or None.
    @param booting - The whole path the configuration boots from, or None.
    @returns list holding one folder, or an empty one.

    Empty where nothing has been installed, the way User is absent until
    something is saved: a folder with nothing in it promises a place to put
    something, and nothing here puts a disk there but the Installer.
    """
    if disks is None:
        return []
    here = [_disk(system, path, booting)
            for system, path in sorted(systems.here(disks).items())]
    kept = _backups(disks)
    if kept:
        here.append(_folder("Backups", BACKUPS, FOLDER_ICON, kept))
    return [_folder("Disks", DISKS, FOLDER_ICON, here)] if here else []


def _backups(disks):
    """The copies that have been made, newest first.

    @param disks - pathlib.Path the disk images live in.
    @returns list, empty where none has been made.

    They stand in a folder of their own inside Disks rather than beside the
    disks, because a folder holding both is one where the thing that runs and
    the thing that is kept look alike. A copy of a disk is a disk, so it wears
    the same picture; where it is says which of the two it is.
    """
    return [
        {
            # The file's own name, which is what a request names and what the
            # helper matches against the listing of that folder.
            "id": path.name,
            "name": _a_copy_called(path, system),
            "icon": DISK_ICON,
            "path": "%s/%s" % (BACKUPS, path.name),
            "kind": "backup",
            # Which system it is a copy of, so putting it back knows which disk
            # it belongs over without reading the name again in the browser.
            "system": system.identifier if system else None,
            "bytes": _size_of(path),
        }
        for path, system in systems.copies_in(disks)
    ]


def _a_copy_called(path, system):
    """What one copy is called on the screen.

    @param path - pathlib.Path of the copy.
    @param system - The System it is a copy of, or None where its name says
      nothing this knows.
    @returns str

    The system and the moment, which is what tells two copies apart. The
    seconds are in the file's name so that two copies made in one minute are
    two files, and they are left off here because nobody reads them.
    """
    identifier, _, when = path.stem.partition(" ")
    return "%s %s" % (system.name if system else identifier,
                      when.rsplit(".", 1)[0] if when else "")


def _disk(identifier, path, booting):
    """One disk as an entry of the folder it sits in.

    @param identifier - Which system it holds, as systems.CATALOGUE names it.
    @param path - pathlib.Path of the image on the card.
    @param booting - The whole path the configuration boots from, or None.
    @returns dict

    It wears a hard disk, because that is what it is. A system is not drawn as
    a disc here for the same reason a machine wears the drawing its own boot
    ROM makes of it: the picture says what the thing is rather than how it
    arrived.
    """
    system = systems.find(identifier)
    return {
        "id": identifier,
        "name": system.name if system else identifier,
        "icon": DISK_ICON,
        "path": "%s/%s" % (DISKS, identifier),
        "kind": "disk",
        # Which one the machine is set to boot. Compared whole, because two
        # disks can be called the same thing in different folders.
        "booting": booting is not None and str(path) == str(booting),
        "bytes": _size_of(path),
    }


def _size_of(path):
    """@returns int - How much of the card it takes, or 0 where it cannot be
      read. A figure nobody can read is not worth an exception in a listing."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def pictures(documents):
    """The screenshots that have been kept.

    @param documents - pathlib.Path the tree's real part stands in, or None.
    @returns list, newest first, and empty where the directory is not there.

    Newest first because the reason to open this folder is almost always the
    last picture taken. A directory that does not exist is the ordinary state
    of a machine nobody has photographed yet, so it is an empty folder rather
    than an error.
    """
    where = picture_directory(documents)
    if where is None:
        return []
    try:
        found = [path for path in where.iterdir() if path.is_file()]
    except OSError:
        return []

    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return [
        {
            "name": path.name,
            "icon": _picture_icon(path),
            "path": PICTURES + "/" + path.name,
            "kind": "picture",
            "bytes": path.stat().st_size,
            "changed": datetime.datetime.fromtimestamp(
                path.stat().st_mtime, datetime.timezone.utc).isoformat(),
        }
        for path in found
    ]


def remove_picture(documents, name):
    """Takes one picture out of the folder pictures are kept in.

    @param documents - pathlib.Path the tree's real part stands in, or None.
    @param name - What the picture is called, as a name and not as a way to
      one. Everything up to the last separator is thrown away, so a request
      naming a path asks for that name inside this one folder.
    @returns bool, whether a picture of that name was there and has gone.

    Only a picture, and only one in that folder. Nothing else in there is this
    service's to delete, and a deletion is the one thing it cannot take back.
    """
    where = picture_directory(documents)
    if where is None or not name:
        return False

    wanted = where / pathlib.PurePosixPath(name).name
    if not (wanted.is_file() and is_a_picture(wanted)):
        return False
    try:
        wanted.unlink()
    except OSError:
        return False
    return True


def is_a_picture(path):
    """@param path - pathlib.Path or anything with a name.
    @returns bool, whether Preview would open it."""
    return pathlib.Path(path).suffix.lower() in PICTURE_SUFFIXES


def _picture_icon(path):
    """@param path @returns str, what that file wears in a viewer.

    A format with no icon of its own falls back to the one the Workspace drew
    for a file it knew nothing about, which is honest: nothing here claims a
    JPEG is a PNG.
    """
    return PICTURE_ICONS.get(path.suffix.lower(), OTHER_FILE_ICON)


def picture_directory(documents):
    """Where a picture is kept on the card.

    @param documents - pathlib.Path the tree's real part stands in, or None.
    @returns pathlib.Path, or None where nothing was configured.

    The path under `documents` mirrors the path in the viewer, so what somebody
    reads on the screen is where the file is.
    """
    if documents is None:
        return None
    return pathlib.Path(documents).joinpath(*PICTURES.strip("/").split("/"))


def _machine_folders(machines_file):
    """System, and User where there is anything in it.

    An empty User folder would be a promise of something that is not there, so
    it appears with its first configuration and not before.
    """
    folders = [_folder("System", "/Machines/System", FOLDER_ICON,
                       [_machine(machine, "/Machines/System", SYSTEM)
                        for machine in machines.CATALOGUE],
                       writable=False)]

    kept = user_machines(machines_file)
    if kept:
        folders.append(_folder("User", "/Machines/User", FOLDER_ICON, kept))
    return folders


def user_machines(machines_file):
    """The configurations somebody saved, as entries of the User folder.

    @param machines_file - pathlib.Path of the file they are kept in, which
      `settings.machines_file` decides.
    @returns list, empty where nothing has been saved.

    A file that cannot be read answers empty here rather than raising, because
    this is one folder of a tree that also holds the applications, the pictures
    and the eleven, and none of those should go missing over it. Saying so is
    left to the moment somebody tries to change something, which `saved.py`
    refuses whilst the file is in the way.
    """
    try:
        kept = saved.read(machines_file)
    except saved.NotReadable:
        return []
    return [_machine(machine, "/Machines/User", USER) for machine in kept]


def _machine(machine, in_folder, in_set):
    """One machine as an entry of the place it sits in.

    @param machine - A machines.Machine.
    @param in_folder - The path of the folder holding it.
    @param in_set - SYSTEM or USER, which decides what may be done to it.
    @returns dict, the machine described as config.read describes the running
      one, with where it is, what it is called, which set it is in and the
      configuration itself added.
    """
    settings = machines.settings_for(machine)
    entry = config.describe(settings["System"], settings["Memory"], settings["Dimension"])
    entry["id"] = machine.identifier
    # The catalogue's own name, which carries the Nitro that the file cannot:
    # to Previous that is a clock and nothing else. A saved configuration's name
    # is its own, and it is its identifier as well.
    entry["name"] = machine.name
    entry["path"] = "%s/%s" % (in_folder, machine.identifier)
    # What sort of entry this is, which is what `kind` means everywhere in the
    # tree. It writes over the machine type that describe() put there, so the
    # configuration below is where the editor reads a machine from.
    entry["kind"] = "machine"
    # Which set, so the browser knows whether this one can be renamed, removed
    # and written over without having to read its path.
    entry["set"] = in_set
    # Every setting it has, in the shape /api/machine/save takes. The
    # description above is what a person reads and leaves out anything two
    # machines do not differ by in words, so an editor opening on it alone would
    # start from a machine that is not this one.
    entry["configuration"] = saved.as_values(machine)
    return entry


def _folder(name, path, icon, entries, writable=True):
    """@returns dict describing a folder and what is in it."""
    return {
        "name": name,
        "icon": icon,
        "path": path,
        "kind": "folder",
        "writable": writable,
        "entries": entries,
    }
