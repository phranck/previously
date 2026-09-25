"""The configurations somebody saved, which are the User ones.

The eleven in `machines.py` are System configurations and cannot be changed, so
there is always a known set to go back to. Anything put together in the Config
Editor is a User configuration and is kept here under a name its owner gave it.

They live in one file in the service's own state directory, beside the token and
the note about the last write, because that directory survives a restart and a
package upgrade. One file rather than one per configuration: a name is not a
file name, so a file each would need a second answer to what a configuration is
called, and the two would drift the first time one was renamed.

Nothing here writes `previous.cfg`. Saving a configuration and running one are
two different acts, and the second is `change.py`, which is the one that has to
shut the guest down first.
"""

import json
import os

from . import machines
from .answers import told

#: Where they are kept, under the state directory.
FILE = "machines.json"

#: What the file says about itself. Nothing reads it yet, and it is written so
#: that a later format has something to tell itself apart by.
VERSION = 1

#: The most characters a name may hold. A name is read under an icon in the File
#: Viewer, where the tile is 96 pixels wide, so a longer one is a name nobody
#: sees the end of. It is a limit on what can be read rather than on what a file
#: can hold.
LONGEST_NAME = 48


class NotReadable(Exception):
    """The file holding them is there and cannot be read.

    Distinct from there being none, which is the ordinary state of a machine
    nobody has saved anything on. This one means something is in the way, and
    every change refuses whilst it is, because writing would destroy whatever
    could not be read.
    """


def as_machine(name, values):
    """One saved configuration as the rest of the service speaks of machines.

    @param name - What it is called.
    @param values - Its settings, as the file holds them and as the browser
      sends them. The same shape on purpose: what the editor posts is what gets
      written, so there is one description of a configuration rather than one
      per direction.
    @returns machines.Machine, settled, so a file somebody edited by hand comes
      back as the machine Previous would actually run.

    The name is the identifier as well. A second one would be a second thing to
    keep in step with it, and there is nothing for it to do: the eleven are
    looked up first wherever an identifier arrives, and a name that is one of
    theirs is refused when it is saved.
    """
    return machines.settled(machines.Machine(
        identifier=name,
        name=name,
        kind=_whole(values.get("kind"), machines.NEXTCUBE),
        turbo=bool(values.get("turbo")),
        nitro=bool(values.get("nitro")),
        colour=bool(values.get("colour")),
        dimension=bool(values.get("dimension")),
        banks=tuple(values.get("banks") or ()),
    ))


def as_values(machine):
    """One machine as the file holds it.

    @param machine - A machines.Machine.
    @returns dict without its name or its identifier, because the name is the
      key those two are built from and a second copy of it inside the entry
      would be the one that goes stale.
    """
    return {
        "kind": machine.kind,
        "turbo": machine.turbo,
        "nitro": machine.nitro,
        "colour": machine.colour,
        "dimension": machine.dimension,
        "banks": list(machine.banks),
    }


def read(state_directory):
    """Every configuration somebody saved, in the order they were saved.

    @param state_directory - pathlib.Path the service keeps its own state in, or
      None where it has none, which answers empty.
    @returns tuple of machines.Machine, settled.
    @raises NotReadable - The file is there and cannot be read as this format.
    """
    if state_directory is None:
        return ()

    path = state_directory / FILE
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except (OSError, ValueError) as error:
        raise NotReadable(str(error)) from error

    entries = found.get("machines") if isinstance(found, dict) else None
    if not isinstance(entries, list):
        raise NotReadable("%s holds no list of machines" % path)

    kept = []
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        # Structural only. Everything else is corrected rather than refused,
        # because settled() is what decides which values a machine may hold, and
        # a name is the one thing nothing can be corrected into.
        if not isinstance(name, str) or not name.strip():
            raise NotReadable("%s holds a configuration with no name" % path)
        kept.append(as_machine(name.strip(), entry))
    return tuple(kept)


def find(state_directory, identifier):
    """The saved configuration of that identifier.

    @param state_directory - Where they are kept.
    @param identifier - What a request carries, which for a saved configuration
      is its name.
    @returns machines.Machine, or None where nothing is called that. A System
      machine's identifier answers None here, because the eleven do not live in
      this list.
    @raises NotReadable
    """
    for machine in read(state_directory):
        if machine.identifier == identifier:
            return machine
    return None


def save(state_directory, name, values, replacing=None):
    """Keeps a configuration under a name.

    @param state_directory - Where they are kept.
    @param name - What to call it.
    @param values - Its settings, as as_values writes them.
    @param replacing - The identifier of the configuration being edited, where
      one was. A configuration opened from one of the eleven has none and
      becomes a new entry; one opened from a User configuration replaces it,
      under the same name or a new one.
    @returns (bool, dict) as every other operation of this service answers.
    """
    try:
        kept = list(read(state_directory))
    except NotReadable as error:
        return False, told("saved.not-readable", detail=str(error))

    wanted = (name or "").strip()
    at = _place_of(kept, replacing)
    if replacing is not None and at is None:
        return False, told("saved.no-such", asked=replacing)

    refused = _why_not(wanted, kept, at)
    if refused is not None:
        return False, refused

    machine = as_machine(wanted, values)
    if at is None:
        kept.append(machine)
    else:
        kept[at] = machine

    return _write(state_directory, kept, told("saved.kept", name=wanted))


def rename(state_directory, identifier, name):
    """Gives a saved configuration another name, leaving its settings alone.

    @param state_directory - Where they are kept.
    @param identifier - Which one.
    @param name - What to call it now.
    @returns (bool, dict)
    """
    try:
        kept = list(read(state_directory))
    except NotReadable as error:
        return False, told("saved.not-readable", detail=str(error))

    at = _place_of(kept, identifier)
    if at is None:
        return False, told("saved.no-such", asked=identifier)

    wanted = (name or "").strip()
    refused = _why_not(wanted, kept, at)
    if refused is not None:
        return False, refused

    was = kept[at].name
    kept[at] = as_machine(wanted, as_values(kept[at]))
    return _write(state_directory, kept,
                  told("saved.renamed", name=wanted, was=was))


def remove(state_directory, identifier):
    """Takes a saved configuration away.

    @param state_directory - Where they are kept.
    @param identifier - Which one.
    @returns (bool, dict)

    What it was set to is gone with it. Nothing here touches `previous.cfg`, so
    a machine running that configuration goes on running it: the file the
    emulator reads is its own and this is only the list of what can be chosen.
    """
    try:
        kept = list(read(state_directory))
    except NotReadable as error:
        return False, told("saved.not-readable", detail=str(error))

    at = _place_of(kept, identifier)
    if at is None:
        return False, told("saved.no-such", asked=identifier)

    name = kept.pop(at).name
    return _write(state_directory, kept, told("saved.removed", name=name))


def _place_of(kept, identifier):
    """@returns Where that identifier sits in the list, or None."""
    if identifier is None:
        return None
    for at, machine in enumerate(kept):
        if machine.identifier == identifier:
            return at
    return None


def _why_not(name, kept, at):
    """Why that name cannot be used, or None where it can.

    @param name - The name, already stripped.
    @param kept - What is saved now.
    @param at - Which of them is being written, so its own name does not count
      as taken. None where a new one is being added.
    @returns dict as told() makes them, or None.
    """
    if not name:
        return told("saved.name-needed")
    if len(name) > LONGEST_NAME:
        return told("saved.name-too-long", most=LONGEST_NAME)
    if "/" in name:
        # The File Viewer's path to it is /Machines/User/<name>, so a separator
        # in the name would read as another folder and the way back would lead
        # somewhere that is not there.
        return told("saved.name-has-a-separator")
    if any(character < " " for character in name):
        return told("saved.name-has-a-control-character")

    for taken in _taken(kept, at):
        # Compared without case, because two names that differ only in it are
        # two icons on a shelf that nobody can tell apart.
        if taken.lower() == name.lower():
            return told("saved.name-taken", name=name)
    return None


def _taken(kept, at):
    """Every name a new one may not be.

    @param kept - What is saved now.
    @param at - The one being written, which does not count against itself.
    @returns list of str

    The eleven count twice over, by the name a person reads and by the
    identifier a request carries, because a saved configuration called after
    either of those would shadow it wherever one machine is looked up by name.
    """
    names = [machine.name for machine in machines.CATALOGUE]
    names += [machine.identifier for machine in machines.CATALOGUE]
    names += [machine.name for index, machine in enumerate(kept) if index != at]
    return names


def _write(state_directory, kept, said):
    """Writes the whole list, or says why it could not.

    @param state_directory - Where they are kept.
    @param kept - Every configuration, in order.
    @param said - What to answer with where it worked.
    @returns (bool, dict)

    Written beside itself and moved into place, so a write that fails part way
    leaves the file as it was rather than holding half a list. os.replace is
    atomic within one filesystem, and this one never leaves the state directory.
    """
    path = state_directory / FILE
    beside = path.with_suffix(path.suffix + ".new")
    body = json.dumps(
        {
            "version": VERSION,
            "machines": [
                {"name": machine.name, **as_values(machine)} for machine in kept
            ],
        },
        ensure_ascii=False, indent=2) + "\n"

    try:
        state_directory.mkdir(parents=True, exist_ok=True)
        beside.write_text(body, encoding="utf-8")
        os.replace(beside, path)
    except OSError as error:
        beside.unlink(missing_ok=True)
        return False, told("saved.could-not-write", detail=str(error))
    return True, said


def _whole(value, fallback):
    """@returns The value as an int, or the fallback where it is not one."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
