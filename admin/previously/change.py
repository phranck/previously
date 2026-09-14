"""Changing which machine the emulator is, without leaving it unable to start.

One job, and it is the risky one. Previous writes previous.cfg from memory when
it exits, so a change made underneath a running emulator is lost. And a machine
it cannot run leaves a black screen with SSH as the only way back, which is the
one outcome this must not produce.

So the order is fixed: shut the guest down properly, copy the file, write, let
it come back, and watch long enough to know that it did. Anything that does not
come back is put straight back the way it was.
"""

import time

from . import config, kiosk, machines

#: How long to wait for the emulator to appear after the hold comes off. The
#: console looks every two seconds, and the emulator takes a moment to open its
#: window, so this is generous rather than tight.
RETURN_TIMEOUT_SECONDS = 30

#: How long it then has to stay up. A configuration Previous cannot run makes
#: it exit at once, and the console starts it again, so a machine that is
#: broken looks exactly like one that is running unless somebody waits.
SETTLE_SECONDS = 10


def to_machine(identifier, settings, sleep=None):
    """Makes the emulated machine the one named, and makes sure it still runs.

    @param identifier - Which machine, as machines.CATALOGUE names them.
    @param settings - Settings, for the configuration path and the state
      directory.
    @param sleep - Injected so a test does not wait in real time.
    @returns (bool, str). The second is what to tell the user either way.
    """
    sleep = sleep or time.sleep

    machine = machines.find(identifier)
    if machine is None:
        return False, "es gibt keine Maschine namens %r" % identifier

    stopped, reason = kiosk.stop(settings.runtime_directory, sleep=sleep)
    if not stopped:
        return False, reason

    try:
        config.back_up(settings.previous_config)
        changed = config.write(
            settings.previous_config, machines.settings_for(machine))
    except config.NotReadable as error:
        # Nothing was written, so there is nothing to undo. Let it come back as
        # whatever it was rather than leaving the machine switched off for a
        # reason the user did not ask for.
        kiosk.start(settings.runtime_directory)
        return False, str(error)

    kiosk.start(settings.runtime_directory)

    if not _stayed_up(sleep):
        return False, _rolled_back(settings, machine, sleep)

    if changed:
        return True, "%s läuft, %d Zeilen geändert" % (machine.name, changed)
    return True, "%s war schon eingestellt" % machine.name


def _rolled_back(settings, machine, sleep):
    """Puts the previous configuration back and says so.

    @returns str, what to tell the user.

    The hold is already off, so the console starts the emulator again by itself
    with whatever the file now says. Nothing has to be switched on here.
    """
    backup = settings.previous_config.with_suffix(
        settings.previous_config.suffix + ".bak")
    try:
        settings.previous_config.write_bytes(backup.read_bytes())
    except OSError as error:
        return ("%s kam nicht hoch, und die vorherige Konfiguration liess sich "
                "nicht zurückschreiben: %s. Die Maschine ist über SSH zu "
                "erreichen." % (machine.name, error))

    if _stayed_up(sleep):
        return ("%s kam nicht hoch. Die vorherige Konfiguration steht wieder "
                "in der Datei und die Maschine läuft wie zuvor." % machine.name)

    return ("%s kam nicht hoch, und auch mit der vorherigen Konfiguration "
            "läuft nichts. Das ist über SSH nachzusehen." % machine.name)


def _stayed_up(sleep):
    """Whether the emulator came back and is still there a while later.

    @param sleep - How to wait.
    @returns bool

    Two questions rather than one. A configuration Previous cannot run makes it
    exit at once, and the waiting console starts it again, so asking only
    whether something is running would see a restart loop and call it success.
    The age of the process is what tells the two apart.
    """
    for _ in range(RETURN_TIMEOUT_SECONDS):
        if kiosk.emulator_is_running():
            break
        sleep(1)
    else:
        return False

    sleep(SETTLE_SECONDS)
    age = kiosk.emulator_uptime_seconds()
    return age is not None and age >= SETTLE_SECONDS
