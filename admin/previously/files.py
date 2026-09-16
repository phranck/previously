"""What Previously shows as a filesystem, which is not one.

Nothing here is on the card. These are the things this tool has, arranged the
way NeXTSTEP arranged things, because a person choosing between eleven machines
and three applications is choosing in a place rather than reading a list.

    Previously          the root, drawn as a home the way NeXTSTEP drew one
      Apps
        Config Editor.app
        Preferences.app
        Screenshot.app
        Terminal.app
      Machines
        System          the eleven this project ships, which cannot be changed
        User            what somebody saved, and only once there is something

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

from . import config, machines

#: What the root is called and what it wears. NeXTSTEP drew a person's own
#: directory as a house, and this is the one place everything here lives in.
#: The name is the tool's own and is not translated.
ROOT = "Previously"
HOME_ICON = "home"

#: A folder, and the four applications, by the pictures they carry. Two wear
#: what NeXTSTEP drew for them. The editor and the screenshot taker have no
#: face of their own, so both wear what NeXTSTEP drew for an application that
#: brought none: it had no picture for either, having had neither application.
FOLDER_ICON = "folder"
DEFAULT_APP_ICON = "defaultAppIcon"
PREFERENCES_ICON = "Preferences"
TERMINAL_ICON = "Terminal"

#: The applications, in the order a viewer sorts them. Each carries its
#: picture, the window it opens and the name of what it is called in words,
#: which is not what its bundle is called. The editor is #50, and until it
#: exists choosing it says so.
APPLICATIONS = (
    ("Config Editor.app", DEFAULT_APP_ICON, "editor", "app.config-editor"),
    ("Preferences.app", PREFERENCES_ICON, "preferences", "app.preferences"),
    ("Screenshot.app", DEFAULT_APP_ICON, "screenshot", "app.screenshot"),
    ("Terminal.app", TERMINAL_ICON, "terminal", "app.terminal"),
)


def tree(state_directory=None):
    """Everything Previously holds, as one place with places in it.

    @param state_directory - pathlib.Path the service keeps its own state in,
      where a User configuration would live. None means there are none.
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
        _folder("Machines", "/Machines", FOLDER_ICON, _machine_folders(state_directory)),
    ])


def _machine_folders(state_directory):
    """System, and User where there is anything in it.

    An empty User folder would be a promise of something that is not there, so
    it appears with its first configuration and not before.
    """
    folders = [_folder("System", "/Machines/System", FOLDER_ICON,
                       [_machine(machine, "/Machines/System") for machine in machines.CATALOGUE],
                       writable=False)]

    saved = user_machines(state_directory)
    if saved:
        folders.append(_folder("User", "/Machines/User", FOLDER_ICON, saved))
    return folders


def user_machines(state_directory):
    """The configurations somebody saved.

    @param state_directory - Where the service keeps what it owns.
    @returns list, empty until saving one is built.

    Saving is not built yet, so this is empty and the User folder is therefore
    not there. What it will hold, and in what form, is decided in #71.
    """
    return []


def _machine(machine, in_folder):
    """One machine as an entry of the place it sits in.

    @param machine - A machines.Machine.
    @param in_folder - The path of the folder holding it.
    @returns dict, the machine described as config.read describes the running
      one, with where it is and what it is called added.
    """
    settings = machines.settings_for(machine)
    entry = config.describe(settings["System"], settings["Memory"], settings["Dimension"])
    entry["id"] = machine.identifier
    # The catalogue's own name, which carries the Nitro that the file cannot:
    # to Previous that is a clock and nothing else.
    entry["name"] = machine.name
    entry["path"] = "%s/%s" % (in_folder, machine.identifier)
    entry["kind"] = "machine"
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
