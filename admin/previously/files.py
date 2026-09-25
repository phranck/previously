"""What Previously shows as a filesystem, which is not one.

Nothing here is on the card. These are the things this tool has, arranged the
way NeXTSTEP arranged things, because a person choosing between eleven machines
and three applications is choosing in a place rather than reading a list.

    Previously          the root, drawn as a home the way NeXTSTEP drew one
      Apps
        Config Editor.app
        Grab.app
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

from . import config, machines, saved

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
    ("Preferences.app", PREFERENCES_ICON, "preferences", "app.preferences"),
    ("Preview.app", PREVIEW_ICON, "preview", "app.preview"),
    ("Terminal.app", TERMINAL_ICON, "terminal", "app.terminal"),
)


def tree(state_directory=None, documents=None):
    """Everything Previously holds, as one place with places in it.

    @param state_directory - pathlib.Path the service keeps its own state in,
      where a User configuration would live. None means there are none.
    @param documents - pathlib.Path the real part of this tree stands in.
      None leaves Documents empty rather than leaving it out, so the place a
      picture goes is visible before the first one is taken.
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
        _folder("Documents", DOCUMENTS, FOLDER_ICON, [
            _folder("Pictures", PICTURES, FOLDER_ICON, pictures(documents)),
        ]),
        _folder("Machines", "/Machines", FOLDER_ICON, _machine_folders(state_directory)),
    ])


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


def _machine_folders(state_directory):
    """System, and User where there is anything in it.

    An empty User folder would be a promise of something that is not there, so
    it appears with its first configuration and not before.
    """
    folders = [_folder("System", "/Machines/System", FOLDER_ICON,
                       [_machine(machine, "/Machines/System", SYSTEM)
                        for machine in machines.CATALOGUE],
                       writable=False)]

    kept = user_machines(state_directory)
    if kept:
        folders.append(_folder("User", "/Machines/User", FOLDER_ICON, kept))
    return folders


def user_machines(state_directory):
    """The configurations somebody saved, as entries of the User folder.

    @param state_directory - Where the service keeps what it owns.
    @returns list, empty where nothing has been saved.

    A file that cannot be read answers empty here rather than raising, because
    this is one folder of a tree that also holds the applications, the pictures
    and the eleven, and none of those should go missing over it. Saying so is
    left to the moment somebody tries to change something, which `saved.py`
    refuses whilst the file is in the way.
    """
    try:
        kept = saved.read(state_directory)
    except saved.NotReadable:
        return []
    return [_machine(machine, "/Machines/User", USER) for machine in kept]


def _machine(machine, in_folder, in_set):
    """One machine as an entry of the place it sits in.

    @param machine - A machines.Machine.
    @param in_folder - The path of the folder holding it.
    @param in_set - SYSTEM or USER, which decides what may be done to it.
    @returns dict, the machine described as config.read describes the running
      one, with where it is, what it is called and which set it is in added.
    """
    settings = machines.settings_for(machine)
    entry = config.describe(settings["System"], settings["Memory"], settings["Dimension"])
    entry["id"] = machine.identifier
    # The catalogue's own name, which carries the Nitro that the file cannot:
    # to Previous that is a clock and nothing else. A saved configuration's name
    # is its own, and it is its identifier as well.
    entry["name"] = machine.name
    entry["path"] = "%s/%s" % (in_folder, machine.identifier)
    entry["kind"] = "machine"
    # Which set, so the browser knows whether this one can be renamed, removed
    # and written over without having to read its path.
    entry["set"] = in_set
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
