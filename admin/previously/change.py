"""Changing which machine the emulator is, without leaving it unable to start.

One job, and it is the risky one. Previous reads previous.cfg when it starts
and never again, so a change made underneath a running emulator does nothing
until it restarts, and the person watching has no way to tell. And a machine it
cannot run leaves a black screen with SSH as the only way back, which is the
one outcome this must not produce.

Previous does not write the file back of its own accord, neither when it exits
nor when its own dialogue closes. Only "Save Config" in that dialogue writes,
and that asks for a filename first. So what somebody sets in the dialogue holds
for that session and is gone at the next start unless they save it, and nothing
here can see it in the meantime.

So the order is fixed: shut the guest down properly, copy the file, write, let
it come back, and watch long enough to know that it did. Anything that does not
come back is put straight back the way it was.
"""

import time

from . import config, kiosk, machines, screen

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

    # So that the file can later say whether it is still the one we left. It is
    # noted even where nothing changed, because the file is ours either way.
    config.note_written(settings.previous_config, settings.state_directory)

    kiosk.start(settings.runtime_directory)

    if not _stayed_up(sleep):
        return False, _rolled_back(settings, machine, sleep)

    # The emulator running is not the machine running. A configuration Previous
    # cannot make sense of leaves the process up and the screen blank, and the
    # screen is the only place that difference shows.
    if screen.looks_alive() is False:
        return False, _rolled_back(settings, machine, sleep, blank=True)

    if changed:
        return True, "%s läuft, %d Zeilen geändert" % (machine.name, changed)
    return True, "%s war schon eingestellt" % machine.name


def _rolled_back(settings, machine, sleep, blank=False):
    """Puts the previous configuration back and says so.

    @param blank - Whether the machine is sitting there with nothing on its
      screen, which decides whether the emulator has to be got out of the way.
    @returns str, what to tell the user.
    """
    why = "zeigt nichts auf dem Bildschirm" if blank else "kam nicht hoch"

    backup = settings.previous_config.with_suffix(
        settings.previous_config.suffix + ".bak")
    try:
        settings.previous_config.write_bytes(backup.read_bytes())
    except OSError as error:
        return ("%s %s, und die vorherige Konfiguration liess sich "
                "nicht zurückschreiben: %s. Die Maschine ist über SSH zu "
                "erreichen." % (machine.name, why, error))

    # Previous reads its configuration when it starts and never again, so a
    # file put back underneath a running emulator changes nothing until that
    # emulator goes. Where it exited by itself the console has already started
    # it again; where it is sitting at a blank screen it has to be told.
    if blank and not kiosk.quit_emulator(sleep=sleep):
        return ("%s %s, die vorherige Konfiguration steht wieder in der Datei, "
                "aber der Emulator liess sich nicht beenden. Das ist über SSH "
                "nachzusehen." % (machine.name, why))

    if _stayed_up(sleep):
        return ("%s %s. Die vorherige Konfiguration steht wieder "
                "in der Datei und die Maschine läuft wie zuvor." % (machine.name, why))

    return ("%s %s, und auch mit der vorherigen Konfiguration "
            "läuft nichts. Das ist über SSH nachzusehen." % (machine.name, why))


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
