"""The privileged helper, without any privilege.

Nothing here runs a command, fetches anything or touches a real machine. What
is tested is everything that decides what root will do: what a request is
allowed to say, what a step writes into a file, and what happens to the steps
already taken when one of them fails. That last one is the whole design, and
the only part whose being wrong costs somebody a machine they cannot boot.

The world outside the module is replaced, which for this module means `run`.
Every command goes through it, so a test that replaces it sees the argument
list for everything root would have done.
"""

import configparser
import datetime
import errno
import json
import os
import pathlib
import subprocess
import types

import pytest

from conftest import settings_for
from previously import config, machines, setup, systems


@pytest.fixture(autouse=True)
def system_files(tmp_path, monkeypatch):
    """The console's files and the autologin, in the test's own directory, so
    that no test reaches into /etc or /usr however it goes wrong.

    And a machine systemd runs, which is what every test is about unless it
    asks for one nothing has booted. Neither depends on the machine running the
    suite, which may be a Mac."""
    units = tmp_path / "etc" / "systemd" / "system"
    monkeypatch.setattr(setup, "SYSTEM_UNITS", units)
    monkeypatch.setattr(setup, "AUTOLOGIN", units / (setup.GETTY + ".d") / "autologin.conf")
    monkeypatch.setattr(setup, "CONSOLE_SCRIPT",
                        tmp_path / "usr" / "local" / "libexec" / "previously-console")
    monkeypatch.setattr(setup, "CONSOLE_PAM", tmp_path / "etc" / "pam.d" / "previously-console")
    booted = tmp_path / "booted" / "run" / "systemd" / "system"
    booted.mkdir(parents=True)
    monkeypatch.setattr(setup, "BOOTED", booted)


@pytest.fixture
def not_booted(system_files, tmp_path, monkeypatch):
    """A machine nothing has booted, which is an image being set up in pi-gen's
    chroot: it mounts an empty /run of its own."""
    monkeypatch.setattr(setup, "BOOTED", tmp_path / "chroot" / "run" / "systemd" / "system")


@pytest.fixture
def commands(monkeypatch):
    """Every command the helper would run, recorded instead of run.

    @returns the list, which a test can also make fail by appending a name to
      `refuse`.
    """
    class Commands(list):
        refuse = ()
        #: What a command answers with, by its last argument, for the few steps
        #: that ask something rather than do something. `dpkg-deb -f x Package`
        #: is the one, and its last argument is the field being asked for.
        answers = {}

        def __call__(self, command, seconds=None, heard=None):
            self.append(command)
            if command[0] in self.refuse:
                raise setup.Refused("setup.command-failed",
                                    command=command[0], code=1)
            # A command that reports how far it has got reports it once, so a
            # test can see where the report goes.
            if heard is not None:
                heard(42.0)
            return self.answers.get(command[-1], "")

    answer = Commands()
    monkeypatch.setattr(setup, "run", answer)
    monkeypatch.setattr(setup, "installed", lambda package: False)
    # The packages on the machine running the suite are not the card's, so
    # dpkg is read as having nothing to say unless a test says otherwise.
    monkeypatch.setattr(setup, "_packages_here", lambda: {})
    return answer


class Nobody:
    """An owner that owns nothing, for the steps that write into a home.

    The real one reads a user out of the service's unit and chowns what it
    writes. Neither is available to a test, and neither is what any of these
    tests is about.
    """

    def __init__(self, home):
        self.name = "test"
        self.uid = os.getuid()
        self.gid = os.getgid()
        self.group = "test"
        self.home = home

    def owns(self, path):
        pass

    def directory(self, path):
        missing = [place for place in [path, *path.parents]
                   if not place.exists()]
        for place in reversed(missing):
            place.mkdir()
        return missing

    def write(self, path, text, mode=0o644):
        path.write_text(text, encoding="utf-8")


def work_in(tmp_path, job="install", system="nextstep-3.3",
            machine="nextcube-turbo", steps=()):
    """A run, pointed entirely at the test's own directory."""
    return setup.Work(
        job, steps or setup.JOBS[job], Nobody(tmp_path / "home"),
        systems.find(system) if system else None,
        machines.find(machine),
        settings_for(tmp_path, disks=str(tmp_path / "home" / "nextstep")),
        into=tmp_path / "progress")


# -- what a request may say ----------------------------------------------


def test_a_request_is_read_and_taken_away(tmp_path):
    """Taken away first, so the path unit watching for it does not start the
    helper again the moment it finishes."""
    request = tmp_path / "setup"
    request.write_text(json.dumps({"do": "install"}), encoding="utf-8")

    assert setup.taken(request) == {"do": "install"}
    assert not request.exists()


def test_a_request_that_is_not_there_is_nothing(tmp_path):
    assert setup.taken(tmp_path / "never-written") is None


@pytest.mark.parametrize("written", ["not json", "[1, 2, 3]", '"a string"', ""])
def test_a_request_that_cannot_be_read_is_nothing_and_still_goes(tmp_path, written):
    """Left lying there it would start this again, and again."""
    request = tmp_path / "setup"
    request.write_text(written, encoding="utf-8")

    assert setup.taken(request) is None
    assert not request.exists()


def test_a_link_left_in_place_of_a_request_is_not_followed(tmp_path):
    """The directory it sits in belongs to an unprivileged user, so a link
    there would otherwise have root read whatever it pointed at, and this
    program reports what it could not understand."""
    secret = tmp_path / "secret"
    secret.write_text(json.dumps({"do": "install"}), encoding="utf-8")
    request = tmp_path / "setup"
    request.symlink_to(secret)

    assert setup.taken(request) is None
    assert secret.exists(), "read through the link and took the target away"


def test_a_request_larger_than_three_names_is_refused(tmp_path):
    """Everything one can say is three names. Anything past that is not the
    tool talking."""
    request = tmp_path / "setup"
    request.write_text(" " * (setup.LARGEST_REQUEST + 1), encoding="utf-8")

    assert setup.taken(request) is None


def test_every_name_in_a_request_is_looked_up():
    job, steps, system, machine, backup = setup.asked_for(
        {"do": "install", "system": "nextstep-3.3", "machine": "nextstation"})

    assert job == "install"
    assert steps == setup.JOBS["install"]
    assert system.identifier == "nextstep-3.3"
    assert machine.identifier == "nextstation"
    assert backup is None


def test_a_request_with_no_machine_gets_the_cube_with_the_turbo_board():
    """Neither the one-liner nor the Installer window names a machine, so both
    end up with the same one."""
    machine = setup.asked_for({"do": "install"})[3]

    assert machine.identifier == setup.DEFAULT_MACHINE
    assert machine.identifier in machines.BY_IDENTIFIER


def test_a_request_with_no_system_names_none():
    """Which is how the emulator is installed on its own."""
    system = setup.asked_for({"do": "install", "system": None})[2]

    assert system is None


@pytest.mark.parametrize("named", [12, ["a", "list"], "x" * 300])
def test_a_copy_named_by_something_that_is_not_a_name_is_refused(named):
    """It is matched against the listing of one folder when the step runs, and
    a name longer than any file can have is one nothing will match. Refusing it
    here is refusing it before anything is switched off for it."""
    with pytest.raises(setup.Refused) as refused:
        setup.asked_for({"do": "restore", "system": "nextstep-3.3",
                         "backup": named})

    assert refused.value.told["reason"] == "setup.no-such-copy"


@pytest.mark.parametrize("request_, reason", [
    ({}, "setup.no-such-job"),
    ({"do": "rm -rf /"}, "setup.no-such-job"),
    ({"do": "install", "system": "../../etc/passwd"}, "setup.no-such-system"),
    ({"do": "install", "system": "https://example.com/x.7z"}, "setup.no-such-system"),
    ({"do": "install", "machine": "amiga-2000"}, "setup.no-such-machine"),
])
def test_a_name_that_is_not_in_a_table_refuses_the_whole_request(request_, reason):
    """Nothing in a request is a path, a URL or a command, so there is nothing
    to get right beyond looking a name up and refusing the rest."""
    with pytest.raises(setup.Refused) as refused:
        setup.asked_for(request_)

    assert refused.value.told["reason"] == reason


def test_a_job_named_on_the_command_line_is_carried_out(tmp_path, monkeypatch,
                                                        capsys):
    """Which is how an image is set up in pi-gen's chroot, where no tool runs to
    leave a request. How the run ended is printed for the build's log."""
    ran = []

    def carried_out(work):
        ran.append(work)
        work.ends(True)
        return True

    monkeypatch.setattr(setup.Owner, "from_unit",
                        classmethod(lambda cls: Nobody(tmp_path / "home")))
    monkeypatch.setattr(setup.Settings, "load",
                        classmethod(lambda cls, home=None: settings_for(tmp_path)))
    monkeypatch.setattr(setup, "carry_out", carried_out)

    assert setup.main(["install", "nextstep-3.3"]) == 0
    work, = ran

    assert work.job == "install"
    assert work.steps == setup.JOBS["install"]
    assert work.system.identifier == "nextstep-3.3"
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_a_name_on_the_command_line_is_looked_up_as_a_requests_is(monkeypatch,
                                                                  capsys):
    monkeypatch.setattr(setup, "carry_out",
                        lambda work: pytest.fail("carried it out anyway"))

    assert setup.main(["install", "../../etc/passwd"]) == 1
    assert json.loads(capsys.readouterr().out)["failed"]["reason"] == \
        "setup.no-such-system"


# -- the order of the work, and what happens when it fails ----------------


def test_the_steps_are_taken_in_order(tmp_path, monkeypatch):
    taken = []
    monkeypatch.setattr(setup, "STEPS",
                        {name: (lambda work, name=name: taken.append(name))
                         for name in setup.STEPS})
    work = work_in(tmp_path, steps=("host", "tools", "archive"))

    assert setup.carry_out(work) is True
    assert taken == ["host", "tools", "archive"]
    assert work.reading()["ok"] is True
    assert work.reading()["done"] == 3


def test_a_failing_step_reverses_the_ones_before_it_backwards(tmp_path, monkeypatch):
    """Backwards, so each step is reversed in a world that still looks the way
    it did when that step ran."""
    undone = []

    def records(work):
        work.undoes(lambda step=work.step: undone.append(step))

    def fails(work):
        work.undoes(lambda: undone.append("half of archive"))
        raise setup.Refused("setup.command-failed", command="apt-get", code=100)

    monkeypatch.setattr(setup, "STEPS",
                        {"host": records, "tools": records, "archive": fails})
    work = work_in(tmp_path, steps=("host", "tools", "archive"))

    assert setup.carry_out(work) is False
    assert undone == ["half of archive", "tools", "host"]


def test_a_failure_says_which_step_and_what_was_put_back(tmp_path, monkeypatch):
    def records(work):
        work.undoes(lambda: None)

    def fails(work):
        raise setup.Refused("setup.no-room", name="NeXTSTEP 3.3", free=1,
                            needed=2)

    monkeypatch.setattr(setup, "STEPS",
                        {"host": records, "tools": records, "system": fails})
    work = work_in(tmp_path, steps=("host", "tools", "system"))

    setup.carry_out(work)
    said = work.reading()

    assert said["ok"] is False
    assert said["failed"]["step"] == "system"
    assert said["failed"]["reason"] == "setup.no-room"
    assert said["failed"]["name"] == "NeXTSTEP 3.3"
    assert said["undone"] == ["tools", "host"]


def test_an_undo_that_is_refused_still_lets_the_run_end(tmp_path, monkeypatch):
    """Putting a package back runs apt-get, and apt-get can fail. A run that
    stopped there would never write its end, and every later request would be
    refused as one too many while it seemed to be running. So the undo that
    failed is left out of what was put back, and the walk carries on."""
    undone = []

    def records(work):
        work.undoes(lambda step=work.step: undone.append(step))

    def put_back_refuses(work):
        def refuses():
            raise setup.Refused("setup.command-failed", command="apt-get",
                                code=100)
        work.undoes(refuses)

    def fails(work):
        raise setup.Refused("setup.no-room", name="NeXTSTEP 3.3", free=1,
                            needed=2)

    monkeypatch.setattr(setup, "STEPS", {
        "host": records, "tools": put_back_refuses, "system": fails})
    work = work_in(tmp_path, steps=("host", "tools", "system"))

    assert setup.carry_out(work) is False
    said = json.loads((work.into / setup.PROGRESS).read_text(encoding="utf-8"))

    assert said["finished_at"] is not None
    assert said["failed"]["reason"] == "setup.no-room"
    assert said["undone"] == ["host"]
    assert undone == ["host"]


def test_a_step_that_fails_with_a_file_error_is_reversed_and_ends(tmp_path, monkeypatch):
    """A card that fills up fails a step that writes, and what it raises is a
    file error rather than a refusal. Let through, it ended the program before
    the run wrote its end, nothing was put back, and every later request was
    refused as one too many until the next boot."""
    undone = []

    def records(work):
        work.undoes(lambda step=work.step: undone.append(step))

    def fails(work):
        work.undoes(lambda: undone.append("half of sound"))
        raise OSError(errno.ENOSPC, "No space left on device",
                      "/etc/wireplumber/wireplumber.conf.d/50-nextstep.conf")

    monkeypatch.setattr(setup, "STEPS", {"host": records, "sound": fails})
    work = work_in(tmp_path, steps=("host", "sound"))

    assert setup.carry_out(work) is False
    said = json.loads((work.into / setup.PROGRESS).read_text(encoding="utf-8"))

    assert said["finished_at"] is not None
    assert said["failed"]["step"] == "sound"
    assert said["failed"]["reason"] == "setup.file-error"
    assert "No space left on device" in said["failed"]["error"]
    assert said["undone"] == ["sound", "host"]
    assert undone == ["half of sound", "host"]


def test_a_run_says_which_steps_actually_did_something(tmp_path, monkeypatch):
    """A run where every step finds its work already done is right and is over
    in a second, and without this the window can only say "finished" to
    somebody who saw nothing happen."""
    def does(work):
        work.undoes(lambda: None)

    monkeypatch.setattr(setup, "STEPS", {
        "host": lambda work: None, "tools": does, "archive": lambda work: None})
    work = work_in(tmp_path, steps=("host", "tools", "archive"))

    setup.carry_out(work)

    assert work.reading()["changed"] == ["tools"]


def test_a_run_that_changed_nothing_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "STEPS",
                        {name: (lambda work: None) for name in setup.STEPS})
    work = work_in(tmp_path, steps=("host", "tools"))

    setup.carry_out(work)

    assert work.reading()["ok"] is True
    assert work.reading()["changed"] == []


def test_a_step_that_changed_nothing_is_not_undone(tmp_path, monkeypatch):
    """A step that skips what it finds already done records nothing, so a later
    failure never takes away what the machine already had."""
    monkeypatch.setattr(setup, "STEPS", {
        "host": lambda work: None,
        "tools": lambda work: (_ for _ in ()).throw(
            setup.Refused("setup.no-such-command", command="apt-get")),
    })
    work = work_in(tmp_path, steps=("host", "tools"))

    setup.carry_out(work)

    assert work.reading()["undone"] == []


def test_what_it_is_doing_is_readable_while_it_runs(tmp_path, monkeypatch):
    """Minutes rather than seconds, so this is a window somebody leaves open
    and comes back to."""
    progress = tmp_path / "progress" / setup.PROGRESS

    def looks(work):
        work.through(512, 60508875, setup.FETCHING)
        said = json.loads(progress.read_text(encoding="utf-8"))
        assert said["step"] == "system"
        assert said["part"] == {"done": 512, "of": 60508875,
                                "doing": setup.FETCHING}
        assert said["finished_at"] is None

    monkeypatch.setattr(setup, "STEPS", {"system": looks})
    setup.carry_out(work_in(tmp_path, steps=("system",)))

    assert json.loads(progress.read_text(encoding="utf-8"))["ok"] is True


def test_the_record_says_what_was_asked_for(tmp_path):
    said = work_in(tmp_path, job="fetch").reading()

    assert said["do"] == "fetch"
    assert said["system"] == "nextstep-3.3"
    assert said["machine"] == "nextcube-turbo"
    assert said["of"] == len(setup.JOBS["fetch"])


# -- the steps that write files -------------------------------------------


def test_a_fresh_configuration_names_the_disk_and_the_machine(tmp_path, commands):
    work = work_in(tmp_path)
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"x")

    setup.STEPS["configuration"](work)
    written = work.settings.previous_config.read_text(encoding="utf-8")

    assert "szImageName0 = %s" % disk in written
    assert "bDiskInserted0 = TRUE" in written
    # The machine, exactly as the editor would write it.
    assert "nMachineType = 1" in written
    assert "bTurbo = TRUE" in written
    assert "nCpuFreq = 33" in written


def test_a_fresh_machine_boots_without_the_rom_printing_its_tests(tmp_path, commands):
    """Previous fills a key that is left out with its own default, and its
    default for `bVerbose` is true, which has the ROM monitor print the whole
    power-on test before NeXTSTEP draws anything. A NeXT out of the box shows
    its boot panel instead, so the key is written."""
    work = work_in(tmp_path)
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"x")

    setup.STEPS["configuration"](work)
    written = configparser.ConfigParser()
    written.optionxform = str
    written.read(work.settings.previous_config, encoding="utf-8")

    assert written["Boot"]["bVerbose"] == "FALSE"


def test_a_fresh_machine_boots_without_the_sound_out_test():
    """The machine's Boot key goes beside the kiosk's two rather than in place
    of them, as its Screen keys do."""
    written = configparser.ConfigParser()
    written.optionxform = str
    written.read_string(setup._written(
        machines.find("nextcube-turbo"),
        pathlib.Path("/home/next/nextstep/nextstep-3.3.dd"),
        pathlib.Path("/home/next/.cache/previously")))

    assert dict(written["Boot"]) == {"nBootDevice": "1", "bVerbose": "FALSE",
                                     "bEnableSoundTest": "FALSE"}


def test_a_fresh_machine_with_a_board_is_shown_on_it():
    """The kiosk's Screen keys and the machine's share one section, and the
    machine's must not take the kiosk's place."""
    written = configparser.ConfigParser()
    written.optionxform = str
    written.read_string(setup._written(
        machines.find("nextcube-turbo-dimension"),
        pathlib.Path("/home/next/nextstep/nextstep-3.3.dd"),
        pathlib.Path("/home/next/.cache/previously")))

    assert written["Screen"]["bFullScreen"] == "TRUE"
    assert written["Screen"]["nMode"] == "0"
    assert written["Screen"]["nSingleModeSlot"] == "2"


def test_a_fresh_configuration_sends_a_grab_where_the_admin_reads_it(tmp_path, commands):
    """Previous writes a grab into its printer's directory, which is the home
    unless the file names another, and the admin may not write in the home."""
    work = work_in(tmp_path)
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"x")

    setup.STEPS["configuration"](work)
    written = configparser.ConfigParser()
    written.optionxform = str
    written.read(work.settings.previous_config, encoding="utf-8")

    assert written["Printer"]["szPrintToFileName"] == str(
        work.owner.home / setup.WORK_DIRECTORY)
    assert written["Printer"]["bPrinterConnected"] == "FALSE"


def test_a_configuration_that_is_already_there_is_left_alone(tmp_path, commands):
    """A machine somebody has built is theirs, and this is the step that would
    write over it."""
    work = work_in(tmp_path)
    work.settings.previous_config.parent.mkdir(parents=True, exist_ok=True)
    work.settings.previous_config.write_text("[System]\nnMachineType = 2\n")

    setup.STEPS["configuration"](work)

    assert "nMachineType = 2" in work.settings.previous_config.read_text()


def test_the_folder_a_picture_goes_in_is_made(tmp_path, commands):
    """Made whether or not there is a system, because Grab files a screenshot
    there and systemd skips a writable path that is absent."""
    work = work_in(tmp_path, system=None)

    setup.STEPS["configuration"](work)

    assert (work.settings.documents / "Documents" / "Pictures").is_dir()


def test_the_console_is_moved_off_the_screen_rather_than_added_to():
    """Of two `console=tty` arguments the kernel uses the first, and
    /dev/console goes with it (Documentation/admin-guide/serial-console.rst),
    which would leave what is written to /dev/console on tty1, the one on
    screen."""
    assert setup._quietened("console=tty1 root=/dev/mmcblk0p2 rw\n").startswith(
        "console=tty3 root=/dev/mmcblk0p2 rw")


def test_a_command_line_with_no_console_gets_one():
    assert setup._quietened("root=/dev/mmcblk0p2 rw\n").startswith("console=tty3 ")


def test_everything_that_draws_on_the_screen_is_silenced():
    quietened = setup._quietened("console=tty1 root=/dev/mmcblk0p2 rw\n")

    for argument in setup.QUIET_ARGUMENTS:
        assert argument in quietened
    assert quietened.endswith("\n")
    assert len(quietened.splitlines()) == 1, "the kernel reads one line"


@pytest.fixture
def boot_files(tmp_path, monkeypatch):
    """The two boot files, as a fresh card has them, and the file that holds
    the kernel's console level, in the test's own directory."""
    boot = tmp_path / "boot" / "firmware"
    boot.mkdir(parents=True)
    monkeypatch.setattr(setup, "CMDLINE", boot / "cmdline.txt")
    monkeypatch.setattr(setup, "CONFIG_TXT", boot / "config.txt")
    monkeypatch.setattr(setup, "PRINTK", tmp_path / "etc" / "sysctl.d" / setup.PRINTK.name)
    setup.CMDLINE.write_text("console=tty1 root=/dev/mmcblk0p2 rw\n", encoding="utf-8")
    setup.CONFIG_TXT.write_text("[all]\n", encoding="utf-8")


def held_level():
    """@returns list of str, the settings the file holding the kernel's
    console level makes, without its comments."""
    return [line for line in setup.PRINTK.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")]


def test_the_kernel_stays_as_quiet_as_its_command_line_says(tmp_path, boot_files):
    """Raspberry Pi OS sets `kernel.printk = 3 4 1 3` in 98-rpi.conf once
    systemd runs, and the kernel's `Undervoltage detected!` stood over the boot
    picture on next5 on 24.10.2026. This file sorts after that one, and the
    kernel takes 0 there (`sysctl -w` on next5)."""
    work = work_in(tmp_path)
    work.at("quiet", 7)

    setup.STEPS["quiet"](work)

    assert "loglevel=%d" % setup.QUIET_LOGLEVEL in setup.CMDLINE.read_text().split()
    assert held_level() == ["kernel.printk = %d 4 1 3" % setup.QUIET_LOGLEVEL]
    assert setup.PRINTK.parent.name == "sysctl.d"
    assert setup.PRINTK.name > "98-rpi.conf"


def test_quieting_the_boot_is_undone_with_the_level(tmp_path, boot_files):
    """A later step that fails walks this one back, and the board then boots
    as it did before."""
    work = work_in(tmp_path)
    work.at("quiet", 7)
    was = setup.CMDLINE.read_text()

    setup.STEPS["quiet"](work)
    work.reverse()

    assert setup.CMDLINE.read_text() == was
    assert not setup.PRINTK.exists()


def test_a_loud_boot_lets_the_kernel_speak_again(tmp_path, boot_files):
    setup.STEPS["quiet"](work_in(tmp_path))

    setup.STEPS["loud"](work_in(tmp_path, job="remove"))

    assert "loglevel=%d" % setup.QUIET_LOGLEVEL not in setup.CMDLINE.read_text().split()
    assert not setup.PRINTK.exists()


def test_the_package_keeps_a_board_quiet_that_was_made_quiet_before(boot_files):
    """A board set up before this version has `loglevel=0` on its command line
    and nothing holding the level after it, so the package brings it up to
    date on every install and upgrade."""
    setup.CMDLINE.write_text(setup._quietened(setup.CMDLINE.read_text()), encoding="utf-8")

    assert setup.refresh_quiet() is True
    assert held_level() == ["kernel.printk = %d 4 1 3" % setup.QUIET_LOGLEVEL]
    assert setup.refresh_quiet() is False, "wrote a current file a second time"


@pytest.mark.parametrize("card", ["loud", "without a command line"])
def test_the_package_leaves_a_loud_board_loud(boot_files, card):
    """Making the boot quiet is setting the board up, which is the install
    job's, and a board somebody made loud again stays that way."""
    if card == "without a command line":
        setup.CMDLINE.unlink()

    assert setup.refresh_quiet() is False
    assert not setup.PRINTK.exists()


@pytest.fixture
def console(monkeypatch, commands):
    """What systemd says about the console's unit, and whether an emulator
    runs, as a test sets them.

    @returns a namespace whose `enabled`, `active` and `guest` a test changes
      in place. All three start out false, which is a machine whose console has
      never been switched on.
    """
    state = types.SimpleNamespace(enabled=False, active=False, guest=False,
                                  shutdown_picture=True)
    monkeypatch.setattr(setup, "unit_state", lambda unit: (
        ("enabled" if state.enabled else "disabled") if unit == setup.CONSOLE else ""))
    monkeypatch.setattr(setup, "unit_active", lambda unit: (
        (unit == setup.CONSOLE and state.active)
        or (unit == setup.SHUTDOWN_PICTURE and state.shutdown_picture)))
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: state.guest)
    return state


def console_unit(owner):
    """@returns configparser.ConfigParser, the console's unit as it is
    written, read the way its sections and keys are laid out."""
    unit = configparser.ConfigParser(interpolation=None)
    unit.optionxform = str
    unit.read_string(setup._console_unit(owner))
    return unit


def a_profile_console(owner):
    """Gives the owner the console an older setup wrote: a fenced block in
    `~/.profile` and the autologin that runs it.

    @returns str, what the profile held before the block, which is what it is
      to hold once the console has moved over.
    """
    owner.home.mkdir(parents=True, exist_ok=True)
    (owner.home / setup.PROFILE).write_text(
        "export EDITOR=vi\n\n%s\ncage -- /usr/bin/previous\n%s\n"
        % (setup.AUTOSTART_OPENS, setup.AUTOSTART_CLOSES), encoding="utf-8")
    setup.AUTOLOGIN.parent.mkdir(parents=True, exist_ok=True)
    setup.AUTOLOGIN.write_text(
        "[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin next %I $TERM\n",
        encoding="utf-8")
    return "export EDITOR=vi\n"


def test_the_console_is_written_and_taken_away_again(tmp_path, commands, console):
    work = work_in(tmp_path)
    work.at("autostart", 9)

    setup.STEPS["autostart"](work)

    files = setup._console_files(work.owner)
    for path, (text, mode) in files.items():
        assert path.read_text(encoding="utf-8") == text
        assert path.stat().st_mode & 0o777 == mode, path
    assert ["systemctl", "enable", setup.CONSOLE] in commands
    assert work.changed == ["autostart"]

    console.enabled = console.active = True
    setup.STEPS["no-autostart"](work)

    assert not any(path.exists() for path in files)
    assert not setup._login_barrier(work.owner).parent.exists()
    assert ["systemctl", "disable", setup.CONSOLE] in commands
    assert ["systemctl", "stop", setup.CONSOLE] in commands


def test_a_console_is_written_once(tmp_path, commands, console):
    """Asking for an installation a second time changes nothing the second
    time, so a later failure has nothing of this step's to put back."""
    setup.STEPS["autostart"](work_in(tmp_path))
    console.enabled = True
    del commands[:]
    again = work_in(tmp_path)
    again.at("autostart", 9)

    setup.STEPS["autostart"](again)

    assert again.changed == []
    assert commands == []


def test_an_emulator_that_is_running_keeps_its_console_when_it_is_removed(
        tmp_path, commands, console):
    """Stopping the unit would take the guest down with whatever it had not
    written. systemd does not start a unit again whose file has gone by the time
    it ends, so the files can go now and the console with the emulator."""
    work = work_in(tmp_path, job="remove")
    setup.STEPS["autostart"](work)
    console.enabled = console.active = console.guest = True

    setup.STEPS["no-autostart"](work)

    assert ["systemctl", "stop", setup.CONSOLE] not in commands
    assert not (setup.SYSTEM_UNITS / setup.CONSOLE).exists()


def test_the_console_does_not_wait_for_the_network(tmp_path):
    """It waits for logind, which opens its session, and for nothing that
    waits for the network. getty@tty1 was ordered after the network through
    systemd-user-sessions.service, and that was 8.5 s on a Pi 4."""
    unit = console_unit(Nobody(tmp_path))
    after = unit["Unit"]["After"].split()

    assert "systemd-logind.service" in after
    assert "network.target" not in after
    assert "systemd-user-sessions.service" not in after
    assert unit["Service"]["Type"] == "exec"


def test_the_console_takes_the_first_screen_from_the_getty(tmp_path):
    """The conflict takes getty@tty1 out of the boot, which a Pi 5 showed on
    24.10.2026: it never started."""
    unit = console_unit(Nobody(tmp_path))

    assert unit["Unit"]["Conflicts"] == setup.GETTY
    assert setup.GETTY in unit["Unit"]["After"].split()
    assert unit["Service"]["TTYPath"] == "/dev/" + setup.TTY
    assert unit["Service"]["StandardInput"] == "tty-fail"


def test_the_console_stays_out_of_utmp(tmp_path):
    """systemd's wall message before a reboot goes to every terminal utmp
    lists. With the console in utmp it stood on the screen of a Pi 5 after the
    guest had shut down, and systemd.exec(5) creates no entry where no
    identifier is set."""
    service = console_unit(Nobody(tmp_path))["Service"]

    assert "UtmpIdentifier" not in service
    assert "UtmpMode" not in service


def test_the_console_leaves_the_terminal_as_it_is(tmp_path):
    """The boot picture stands on tty1 until cage takes the screen, and
    resetting or clearing the terminal takes the picture with it. On next4 on
    24.10.2026 the picture stood from vc4's framebuffer at 9.7 s through the
    console's start at 14.2 s until cage's mode at 23.9 s."""
    service = console_unit(Nobody(tmp_path))["Service"]

    assert "TTYReset" not in service
    assert "TTYVTDisallocate" not in service


def test_the_console_never_gives_up_on_the_emulator(tmp_path):
    """An emulator that ends at once ends the console with it. systemd's start
    limit would stop the console for good after five of those within ten
    seconds, and nothing but root starts it again."""
    unit = console_unit(Nobody(tmp_path))

    assert unit["Unit"]["StartLimitIntervalSec"] == "0"
    assert unit["Service"]["Restart"] == "always"


def test_the_console_runs_as_the_owner_through_its_own_pam_service(tmp_path):
    owner = Nobody(tmp_path)
    service = console_unit(owner)["Service"]

    assert service["User"] == owner.name
    assert service["ExecStart"] == str(setup.CONSOLE_SCRIPT)
    assert service["PAMName"] == setup.CONSOLE_PAM.name


def test_the_session_opens_before_logins_are_permitted(tmp_path):
    """Opening the session waits for the owner's user manager, and systemd
    holds that back until logins are permitted, after the network. On a Pi 5
    cage started at 6.71 s with the early session alone and at 4.36 s with the
    barrier lifted as well."""
    owner = Nobody(tmp_path)
    barrier = setup._login_barrier(owner)

    assert "session  required pam_systemd.so class=user-early" in \
        setup._console_pam().splitlines()
    assert barrier.parent.name == "user@%d.service.d" % owner.uid
    assert barrier.name == "10-login-barrier.conf"
    # Empty apart from comments, because it takes the place of systemd's own
    # file of that name and an ordering written here would put one back.
    assert all(line.startswith("#")
               for line in setup.LOGIN_BARRIER_TEXT.splitlines())


def test_a_console_in_the_profile_is_moved_over(tmp_path, commands, console):
    work = work_in(tmp_path)
    kept = a_profile_console(work.owner)

    setup.STEPS["autostart"](work)

    assert (work.owner.home / setup.PROFILE).read_text() == kept
    assert not setup.AUTOLOGIN.parent.exists()
    assert (setup.SYSTEM_UNITS / setup.CONSOLE).exists()


def test_a_console_in_the_profile_stays_while_an_emulator_runs_on_it(
        tmp_path, commands, console):
    """The profile's console is what brings the next emulator up when the
    admin restarts it. Without it the restart would end at a login prompt."""
    console.guest = True
    work = work_in(tmp_path)
    a_profile_console(work.owner)
    was = (work.owner.home / setup.PROFILE).read_text()

    setup.STEPS["autostart"](work)

    assert (work.owner.home / setup.PROFILE).read_text() == was
    assert setup.AUTOLOGIN.exists()
    assert (setup.SYSTEM_UNITS / setup.CONSOLE).exists()


def test_the_profile_console_goes_once_the_unit_runs_the_emulator(
        tmp_path, commands, console):
    """Which is how a machine looks after the boot that handed it over."""
    console.guest = console.active = console.enabled = True
    work = work_in(tmp_path)
    kept = a_profile_console(work.owner)

    setup.STEPS["autostart"](work)

    assert (work.owner.home / setup.PROFILE).read_text() == kept
    assert not setup.AUTOLOGIN.exists()


def test_moving_over_can_be_undone(tmp_path, commands, console):
    """A later step that fails walks every one of them backwards, and this
    one has to leave the console the way it found it."""
    work = work_in(tmp_path)
    a_profile_console(work.owner)
    was = (work.owner.home / setup.PROFILE).read_text()
    autologin = setup.AUTOLOGIN.read_text()
    work.at("autostart", 9)

    setup.STEPS["autostart"](work)
    work.reverse()

    assert (work.owner.home / setup.PROFILE).read_text() == was
    assert setup.AUTOLOGIN.read_text() == autologin
    assert not any(path.exists() for path in setup._console_files(work.owner))
    assert not setup._login_barrier(work.owner).parent.exists()
    assert ["systemctl", "disable", setup.CONSOLE] in commands


def start_line(owner):
    """@returns list of str, the words of the line in the console's script
    that starts the emulator, which the console has in one place."""
    script = setup._console_script(owner)
    lines = [line for line in script.splitlines()
             if "/usr/bin/previous" in line and not line.startswith("#")]
    assert len(lines) == 1, "the console starts Previous in one place"
    return lines[0].split()


def test_previous_draws_through_x_before_wayland(tmp_path):
    """Previous grabs the mouse when it is clicked, and under Wayland SDL needs
    pointer constraints for that, which cage does not offer: on next5 the mouse
    stopped reaching NeXTSTEP shortly after the first click. Xwayland holds the
    grab itself. Wayland comes second, so a machine without an X server still
    starts its emulator."""
    words = start_line(Nobody(tmp_path))
    drivers = next(word for word in words if word.startswith("SDL_VIDEO_DRIVER="))

    assert drivers.split("=", 1)[1].split(",") == ["x11", "wayland"]


def test_cage_takes_its_pointer_from_the_packages_theme(tmp_path):
    """cage sets its own pointer whenever a mouse arrives, and the package's
    theme makes that one invisible."""
    words = start_line(Nobody(tmp_path))

    assert "XCURSOR_PATH=" + setup.CURSORS in words[:words.index("cage")]


def test_previous_takes_its_pointer_from_the_systems_theme(tmp_path):
    """The invisible theme is cage's alone. Previous hides the pointer itself
    while NeXTSTEP runs, and its own dialog shows the pointer SDL loads from
    the theme its environment names, which must not be the invisible one."""
    words = start_line(Nobody(tmp_path))
    env = words.index("env")

    assert words.index("cage") < env
    assert words[env + 1:env + 3] == ["-u", "XCURSOR_PATH"]


def test_previous_alone_starts_with_the_library_that_shows_it_sharp(tmp_path):
    """The library stands in front of SDL, so it means something only in the
    program that draws through SDL. cage and Xwayland start without it."""
    words = start_line(Nobody(tmp_path))

    previous = words[words.index("--") + 1:]
    assert previous[0] == "env" and previous[-1] == "/usr/bin/previous"
    assert "LD_PRELOAD=" + setup.SHARP_DISPLAY in previous
    assert not any(word.startswith("LD_PRELOAD=") for word in words[:words.index("cage")])


def run_the_console(tmp_path, monkeypatch, cage_exits):
    """Runs the console's script the way its unit does, with a cage that ends
    at once and a sleep that only writes down how long it was asked to wait.

    @param cage_exits - The status cage ends with.
    @returns (int, list of str, str): the script's status, every wait asked
      for, and what the crash file holds.
    """
    runtime = tmp_path / "run"
    runtime.mkdir()
    monkeypatch.setattr(setup, "RUNTIME", str(runtime))
    monkeypatch.setattr(setup, "HOLD", str(runtime / "hold"))
    monkeypatch.setattr(setup, "CRASHES", str(runtime / "crashes"))
    tools = tmp_path / "bin"
    tools.mkdir()
    slept = tmp_path / "slept"
    for name, body in (("cage", "exit %d" % cage_exits),
                       ("sleep", 'echo "$1" >> %s' % slept)):
        (tools / name).write_text("#!/bin/sh\n%s\n" % body, encoding="utf-8")
        (tools / name).chmod(0o755)
    owner = Nobody(tmp_path / "home")
    owner.home.mkdir()
    script = tmp_path / "previously-console"
    script.write_text(setup._console_script(owner), encoding="utf-8")

    finished = subprocess.run(
        ["sh", str(script)], env={"PATH": "%s:/usr/bin:/bin" % tools},
        capture_output=True, text=True, check=False)
    crashes = runtime / "crashes"
    return (finished.returncode,
            slept.read_text().split() if slept.exists() else [],
            crashes.read_text() if crashes.exists() else "")


def test_an_emulator_that_ends_badly_is_written_down_and_waited_for(tmp_path, monkeypatch):
    """systemd starts the console again the moment it ends, so an emulator
    that cannot start would otherwise be tried as fast as systemd can start a
    process."""
    status, slept, crashes = run_the_console(tmp_path, monkeypatch, 3)

    assert status == 3
    assert crashes.split()[-1] == "3"
    assert slept == [str(setup.CRASH_PAUSE_SECONDS)]


def test_an_emulator_that_ends_well_ends_the_console_at_once(tmp_path, monkeypatch):
    status, slept, crashes = run_the_console(tmp_path, monkeypatch, 0)

    assert status == 0
    assert slept == []
    assert crashes == ""


def test_the_first_console_asks_who_is_there_where_nothing_holds_it(
        tmp_path, commands, console):
    setup.STEPS["no-autologin"](work_in(tmp_path, job="remove"))

    assert ["systemctl", "start", setup.GETTY] in commands


def test_no_getty_is_put_under_an_emulator_that_still_runs(tmp_path, commands, console):
    """A getty on that terminal would take it from under the emulator, so the
    prompt comes with the next boot."""
    console.active = True

    setup.STEPS["no-autologin"](work_in(tmp_path, job="remove"))

    assert ["systemctl", "start", setup.GETTY] not in commands


@pytest.fixture
def units(monkeypatch, tmp_path):
    """The board's units by the state `systemctl is-enabled` names, each of
    the left-out ones switched on unless a test says otherwise, and the two
    files that keep cloud-init away somewhere the test can see them.

    @returns dict of unit to state, which a test changes in place.
    """
    states = {unit: "enabled" for unit in setup.LEFT_OUT}
    monkeypatch.setattr(setup, "unit_state", lambda unit: states.get(unit, ""))
    (tmp_path / "cloud").mkdir()
    monkeypatch.setattr(setup, "CLOUD_INIT_OFF", tmp_path / "cloud" / "cloud-init.disabled")
    monkeypatch.setattr(setup, "CLOUD_INIT_ONCE",
                        tmp_path / "lib" / "cloud" / "scripts" / "per-once" / "cloud-init-off")
    return states


def the_command(commands, verb):
    """@returns list of str, the one `systemctl <verb>` command that was
    run, whole."""
    return next(command for command in commands
                if command[:2] == ["systemctl", verb])


def systemctl(commands, verb):
    """@returns list of str, the units one `systemctl <verb>` was given,
    without a flag such as `--now` that stands among them."""
    return [word for word in the_command(commands, verb)[2:]
            if not word.startswith("--")]


def test_what_nothing_here_needs_is_switched_off(tmp_path, commands, units):
    """Only what is on, so a unit somebody switched off before is not in the
    record of what this run did."""
    units["udisks2.service"] = "disabled"
    work = work_in(tmp_path)
    work.at("lean", 9)

    setup.STEPS["lean"](work)

    assert set(systemctl(commands, "disable")) == set(setup.LEFT_OUT) - {"udisks2.service"}
    assert setup.CLOUD_INIT_OFF.exists()


def test_the_apt_timers_that_run_for_nothing_are_switched_off(tmp_path, commands, units):
    """Both wake the Pi twice a day while NeXTSTEP runs, for a script that
    skips every step on the card as imaged. `LEFT_OUT` says why."""
    work = work_in(tmp_path)
    work.at("lean", 9)

    setup.STEPS["lean"](work)

    assert {"apt-daily.timer", "apt-daily-upgrade.timer"} <= set(
        systemctl(commands, "disable"))


def test_what_is_switched_off_is_stopped_as_well(tmp_path, commands, units):
    """`systemctl disable` on its own leaves a running unit running until the
    next boot."""
    work = work_in(tmp_path)
    work.at("lean", 9)

    setup.STEPS["lean"](work)

    assert "--now" in the_command(commands, "disable")


def test_an_image_switches_off_without_stopping(tmp_path, commands, units, not_booted):
    """Nothing runs in pi-gen's chroot, so there is nothing to stop, and what
    is switched off there never starts at the image's first boot."""
    work = work_in(tmp_path)
    work.at("lean", 9)

    setup.STEPS["lean"](work)

    assert "--now" not in the_command(commands, "disable")


def test_a_failed_run_switches_back_on_only_what_it_switched_off(
        tmp_path, commands, units, monkeypatch):
    units["udisks2.service"] = "disabled"

    def fails(work):
        raise setup.Refused("setup.command-failed", command="systemctl", code=1)

    monkeypatch.setattr(setup, "STEPS", dict(setup.STEPS, autostart=fails))
    work = work_in(tmp_path, steps=("lean", "autostart"))

    assert setup.carry_out(work) is False
    assert "udisks2.service" not in systemctl(commands, "enable")
    assert not setup.CLOUD_INIT_OFF.exists()


def test_removing_brings_back_what_was_left_out(tmp_path, commands, units):
    """Every left-out unit this system has, and none it does not."""
    for unit in units:
        units[unit] = "disabled"
    units["sshswitch.service"] = ""
    setup.CLOUD_INIT_OFF.touch()
    work = work_in(tmp_path, job="remove")
    work.at("full", 2)

    setup.STEPS["full"](work)

    assert set(systemctl(commands, "enable")) == set(setup.LEFT_OUT) - {"sshswitch.service"}
    assert not setup.CLOUD_INIT_OFF.exists()


def test_installing_leaves_out_and_removing_brings_back():
    assert "lean" in setup.JOBS["install"]
    assert "full" in setup.JOBS["remove"]


def test_an_image_keeps_cloud_init_for_its_first_boot(tmp_path, commands, units,
                                                      not_booted):
    """cloud-init applies what Raspberry Pi Imager set at the first boot, and
    an image is set up before that boot. So cloud-init switches itself off once
    that boot is through, with a script it runs once."""
    work = work_in(tmp_path)
    work.at("lean", 9)

    setup.STEPS["lean"](work)

    assert not setup.CLOUD_INIT_OFF.exists()
    assert setup.CLOUD_INIT_ONCE.stat().st_mode & 0o777 == 0o755
    assert work.changed == ["lean"]

    subprocess.run(["sh", str(setup.CLOUD_INIT_ONCE)], check=True)

    assert setup.CLOUD_INIT_OFF.exists()


def test_a_failed_image_takes_the_script_back(tmp_path, commands, units, not_booted):
    work = work_in(tmp_path)
    work.at("lean", 9)

    setup.STEPS["lean"](work)
    assert setup.CLOUD_INIT_ONCE.exists()
    work.reverse()

    assert not setup.CLOUD_INIT_ONCE.exists()


def test_removing_takes_the_script_away_from_a_machine_set_up_as_an_image(
        tmp_path, commands, units):
    """It ran at the first boot, and cloud-init does not run it again, but a
    removal leaves nothing of Previously's behind."""
    setup.CLOUD_INIT_ONCE.parent.mkdir(parents=True)
    setup.CLOUD_INIT_ONCE.write_text("#!/bin/sh\n", encoding="utf-8")
    setup.CLOUD_INIT_OFF.touch()

    setup.STEPS["full"](work_in(tmp_path, job="remove"))

    assert not setup.CLOUD_INIT_ONCE.exists()
    assert not setup.CLOUD_INIT_OFF.exists()


@pytest.mark.parametrize("set_up_with", ["unit", "profile"])
def test_the_package_leaves_out_the_same_on_a_machine_that_is_set_up(
        tmp_path, commands, units, set_up_with):
    """On every install and upgrade, so a machine set up before this version
    starts as lean as a new one, whichever console it has."""
    owner = Nobody(tmp_path / "home")
    if set_up_with == "unit":
        setup.SYSTEM_UNITS.mkdir(parents=True)
        (setup.SYSTEM_UNITS / setup.CONSOLE).write_text(setup._console_unit(owner))
    else:
        a_profile_console(owner)

    assert setup.refresh_services(owner) is True
    assert set(systemctl(commands, "disable")) == set(setup.LEFT_OUT)
    assert setup.CLOUD_INIT_OFF.exists()


def test_the_package_leaves_the_services_of_a_machine_without_a_console(
        tmp_path, commands, units):
    owner = Nobody(tmp_path / "home")
    owner.home.mkdir()

    assert setup.refresh_services(owner) is False
    assert commands == []


def test_the_package_moves_a_console_from_the_profile_over_and_starts_it(
        tmp_path, commands, console):
    """Nothing else would start the unit before the next boot, and the admin's
    stop and start talk to whichever console holds the screen."""
    owner = Nobody(tmp_path / "home")
    kept = a_profile_console(owner)

    assert setup.refresh_console(owner)
    assert (owner.home / setup.PROFILE).read_text() == kept
    assert not setup.AUTOLOGIN.exists()
    assert ["systemctl", "start", setup.CONSOLE] in commands


def test_the_package_leaves_an_emulator_running_on_the_profiles_console(
        tmp_path, commands, console):
    """An update from the browser runs while NeXTSTEP does. The next boot hands
    the screen to the unit."""
    console.guest = True
    owner = Nobody(tmp_path / "home")
    a_profile_console(owner)
    was = (owner.home / setup.PROFILE).read_text()

    assert setup.refresh_console(owner)
    assert (owner.home / setup.PROFILE).read_text() == was
    assert (setup.SYSTEM_UNITS / setup.CONSOLE).exists()
    assert ["systemctl", "start", setup.CONSOLE] not in commands


def test_the_package_brings_a_console_from_an_older_version_up_to_date(
        tmp_path, commands, console):
    """The console is generated, so a machine set up a year ago carries a
    year-old one. A running console is left running and takes the change up
    the next time it starts."""
    console.enabled = console.active = True
    owner = Nobody(tmp_path / "home")
    unit = setup.SYSTEM_UNITS / setup.CONSOLE
    unit.parent.mkdir(parents=True)
    unit.write_text("[Service]\nExecStart=/bin/false\n")

    assert setup.refresh_console(owner)
    assert unit.read_text() == setup._console_unit(owner)
    assert ["systemctl", "daemon-reload"] in commands
    assert not any(command[1] in ("start", "restart", "stop")
                   for command in commands if command[0] == "systemctl")


def test_the_package_gives_a_machine_without_a_console_none(tmp_path, commands, console):
    """Installing the tool is not setting the machine up. A console is written
    by the install job, and the package only keeps one that is there current."""
    owner = Nobody(tmp_path / "home")
    owner.home.mkdir()
    (owner.home / setup.PROFILE).write_text("export EDITOR=vi\n", encoding="utf-8")

    assert not setup.refresh_console(owner)
    assert not any(path.exists() for path in setup._console_files(owner))
    assert (owner.home / setup.PROFILE).read_text() == "export EDITOR=vi\n"
    assert not setup.refresh_console(Nobody(tmp_path / "nobody-home"))


def test_the_package_leaves_a_current_console_alone(tmp_path, commands, console):
    work = work_in(tmp_path)
    setup.STEPS["autostart"](work)
    console.enabled = console.active = True
    del commands[:]

    assert not setup.refresh_console(work.owner)
    assert commands == []


def test_the_package_starts_the_shutdown_picture_beside_a_running_console(
        tmp_path, commands, console):
    """The console pulls it in when it starts, and one that started before it
    wanted it would go down without the picture the next time."""
    work = work_in(tmp_path)
    setup.STEPS["autostart"](work)
    console.enabled = console.active = True
    console.shutdown_picture = False
    del commands[:]

    assert setup.refresh_console(work.owner)
    assert commands == [["systemctl", "start", setup.SHUTDOWN_PICTURE]]


def older_configuration(home, printer):
    """A configuration as an older version of `setup.py` wrote it, or as
    Previous's own "Save config" writes it, with that printer section."""
    path = home / ".config" / "previous" / "previous.cfg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[System]\nnMachineType = 1\n\n[Printer]\n%s\n" % printer)
    return path


def test_the_package_sends_the_grabs_of_an_older_configuration_to_the_admin(tmp_path):
    """On every install and upgrade, so a machine set up before the key was
    written stops leaving its grabs in the home."""
    owner = Nobody(tmp_path)
    path = older_configuration(tmp_path, "bPrinterConnected = FALSE")

    assert setup.refresh_configuration(owner, path)
    assert path.read_text() == (
        "[System]\nnMachineType = 1\n\n[Printer]\nbPrinterConnected = FALSE\n"
        "szPrintToFileName = %s\n" % (tmp_path / setup.WORK_DIRECTORY))


def test_a_configuration_that_names_the_home_is_sent_to_the_admin(tmp_path):
    """Previous's "Save config" writes every key, its default for this one
    among them, so a file naming the home is a file nobody chose a place in."""
    owner = Nobody(tmp_path)
    path = older_configuration(tmp_path, "szPrintToFileName = %s" % tmp_path)

    assert setup.refresh_configuration(owner, path)
    assert "szPrintToFileName = %s\n" % (tmp_path / setup.WORK_DIRECTORY) in path.read_text()


def test_a_place_somebody_chose_for_their_printouts_stays(tmp_path):
    owner = Nobody(tmp_path)
    path = older_configuration(tmp_path, "szPrintToFileName = /media/usb")
    was = path.read_text()

    assert not setup.refresh_configuration(owner, path)
    assert path.read_text() == was


def test_the_package_takes_a_rom_somebody_set_out_of_a_configuration(tmp_path):
    """Without the key Previous loads the ROM it ships for the machine. Set by
    hand to the NeXTdimension's ROM for a turbo board, it halted Previous's
    CPU on a Pi 5 on 23.10.2026."""
    owner = Nobody(tmp_path)
    path = older_configuration(
        tmp_path, "szPrintToFileName = %s" % (tmp_path / setup.WORK_DIRECTORY))
    path.write_text(path.read_text()
                    + "\n[ROM]\nszRomTurboFileName = /usr/share/previous/ND_step1_v43.BIN\n")

    assert setup.refresh_configuration(owner, path)
    assert "szRomTurboFileName" not in path.read_text()


def test_a_rom_is_taken_out_where_somebody_chose_a_place_for_printouts(tmp_path):
    """The place is theirs and stays. The ROM is not a choice anybody has."""
    owner = Nobody(tmp_path)
    path = older_configuration(tmp_path, "szPrintToFileName = /media/usb")
    path.write_text(path.read_text()
                    + "\n[ROM]\nszRomTurboFileName = /usr/share/previous/ND_step1_v43.BIN\n")

    assert setup.refresh_configuration(owner, path)
    written = path.read_text()
    assert "szPrintToFileName = /media/usb" in written
    assert "szRomTurboFileName" not in written


def test_the_package_gives_a_machine_without_a_configuration_none(tmp_path):
    """Writing one is setting the machine up, which is the install job's."""
    assert not setup.refresh_configuration(Nobody(tmp_path),
                                           tmp_path / "previous.cfg")
    assert not (tmp_path / "previous.cfg").exists()


def test_the_package_leaves_a_current_configuration_untouched(tmp_path):
    """Untouched rather than written again, because a file newer than the
    running machine is what the admin reports as a change nobody has tried."""
    owner = Nobody(tmp_path)
    path = older_configuration(
        tmp_path, "szPrintToFileName = %s" % (tmp_path / setup.WORK_DIRECTORY))
    os.utime(path, (0, 0))

    assert not setup.refresh_configuration(owner, path)
    assert path.stat().st_mtime == 0


# -- who wrote the configuration last ---------------------------------------


class Keeping(Nobody):
    """An owner that says which files were handed to it."""

    def __init__(self, home):
        super().__init__(home)
        self.given = []

    def owns(self, path):
        self.given.append(path)


def state_noting(tmp_path, path):
    """The service's state directory, holding a note of the file as it is."""
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    config.note_written(path, state)
    return state


def test_a_fresh_configuration_is_noted_as_previouslys(tmp_path, commands):
    """Otherwise a machine that has just been set up reads as changed from
    outside, and says so, before anybody has touched it."""
    work = work_in(tmp_path)
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"x")

    setup.STEPS["configuration"](work)

    assert config.written_by_us(work.settings.previous_config,
                                work.settings.state_directory) is True


def test_the_note_belongs_to_the_service_not_to_root(tmp_path):
    """The helper and postinst run as root, and the service has to be able to
    write its next note over this one."""
    owner = Keeping(tmp_path)
    path = older_configuration(tmp_path, "bPrinterConnected = FALSE")
    state = state_noting(tmp_path, path)

    setup.refresh_configuration(owner, path, state)

    assert state / config.RECEIPT in owner.given


def test_a_refresh_keeps_a_file_of_previouslys_its_own(tmp_path):
    owner = Nobody(tmp_path)
    path = older_configuration(tmp_path, "bPrinterConnected = FALSE")
    state = state_noting(tmp_path, path)

    assert setup.refresh_configuration(owner, path, state)
    assert config.written_by_us(path, state) is True


def test_a_change_from_outside_stays_one_through_a_refresh(tmp_path):
    """An update must not make a hand edit look like Previously's own."""
    owner = Nobody(tmp_path)
    path = older_configuration(tmp_path, "bPrinterConnected = FALSE")
    state = state_noting(tmp_path, path)
    path.write_text(path.read_text() + "\n[Sound]\nbEnableSound = FALSE\n")

    assert setup.refresh_configuration(owner, path, state)
    assert config.written_by_us(path, state) is False


def test_a_file_never_noted_is_taken_as_previouslys_once(tmp_path):
    """A machine set up before every write was noted holds no note at all.
    There is nothing to compare against, and reading it as changed from
    outside would put the notice on every one of them."""
    owner = Nobody(tmp_path)
    path = older_configuration(
        tmp_path, "szPrintToFileName = %s" % (tmp_path / setup.WORK_DIRECTORY))
    state = tmp_path / "state"
    state.mkdir()

    setup.refresh_configuration(owner, path, state)

    assert config.written_by_us(path, state) is True


def test_an_installation_ends_with_the_machine_running(tmp_path, commands, monkeypatch):
    """Everything up to here leaves a machine that is installed and shows
    nothing, because a getty has held the first console since before any of it
    existed. So the console is started, and the hold that would stop it
    starting the emulator goes first."""
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: False)
    hold = tmp_path / "hold"
    hold.touch()
    monkeypatch.setattr(setup, "HOLD", str(hold))
    work = work_in(tmp_path)
    work.at("start", len(setup.JOBS["install"]))

    setup.STEPS["start"](work)

    assert not hold.exists()
    assert ["systemctl", "restart", setup.CONSOLE] in commands
    assert work.changed == ["start"]


def test_a_machine_that_is_already_running_is_not_restarted(tmp_path, commands,
                                                            monkeypatch):
    """Restarting the console under a running guest costs whatever that guest
    had not written, so asking for an installation a second time leaves the
    machine somebody is using alone."""
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: True)
    hold = tmp_path / "hold"
    hold.touch()
    monkeypatch.setattr(setup, "HOLD", str(hold))
    work = work_in(tmp_path)
    work.at("start", len(setup.JOBS["install"]))

    setup.STEPS["start"](work)

    assert hold.exists()
    assert commands == []
    assert work.changed == []


def test_an_image_starts_its_console_at_its_first_boot(tmp_path, commands,
                                                       monkeypatch, not_booted):
    """systemd runs nothing in pi-gen's chroot, so there is nothing to start.
    The console's unit is switched on by then, and the first boot starts it."""
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: False)
    work = work_in(tmp_path)
    work.at("start", len(setup.JOBS["install"]))

    setup.STEPS["start"](work)

    assert commands == []
    assert work.changed == []


# -- the disk a machine boots ---------------------------------------------


def test_the_disk_the_machine_boots_is_not_taken_away(tmp_path, commands):
    """Which disk it boots is one line in previous.cfg, so that file is read
    rather than guessed at."""
    work = work_in(tmp_path)
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"x")
    work.settings.previous_config.parent.mkdir(parents=True, exist_ok=True)
    work.settings.previous_config.write_text("szImageName0 = %s\n" % disk)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["no-system"](work)

    assert refused.value.told["reason"] == "setup.system-in-use"
    assert disk.is_file(), "refused and removed it anyway"


def test_a_disk_nothing_boots_can_be_taken_away(tmp_path, commands):
    work = work_in(tmp_path)
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"x")

    setup.STEPS["no-system"](work)

    assert not disk.exists()


def test_a_system_that_is_not_here_cannot_be_taken_away(tmp_path, commands):
    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["no-system"](work_in(tmp_path))

    assert refused.value.told["reason"] == "setup.system-is-not-here"


def test_a_system_that_is_already_here_is_not_fetched_again(tmp_path, commands, monkeypatch):
    """Two gigabytes and half an hour, for a disk that is already on the
    card."""
    monkeypatch.setattr(setup, "_fetched",
                        lambda *a, **k: pytest.fail("fetched it anyway"))
    work = work_in(tmp_path)
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"x")

    setup.STEPS["system"](work)


def test_no_system_named_means_the_emulator_on_its_own(tmp_path, commands, monkeypatch):
    monkeypatch.setattr(setup, "_fetched",
                        lambda *a, **k: pytest.fail("fetched it anyway"))
    setup.STEPS["system"](work_in(tmp_path, system=None))


@pytest.fixture
def a_system_arrives(monkeypatch):
    """A fetch that brings nothing, an unpack that leaves a disk of the
    smallest size a disk has, and a card with room for it."""
    def unpacked(archive, into, work):
        disk = into / "NS33_2GB.dd"
        disk.write_bytes(b"")
        os.truncate(disk, systems.SMALLEST_DISK_BYTES)

    monkeypatch.setattr(setup, "_fetched", lambda *a, **k: None)
    monkeypatch.setattr(setup, "_unpacked", unpacked)
    monkeypatch.setattr(systems, "room_beside", lambda where: None)


def test_a_disk_is_kept_as_only_what_it_holds(tmp_path, commands, a_system_arrives):
    """Most of a disk of two gigabytes is zeros, and once they are holes they
    take no room on the card, nor in an image built from one."""
    work = work_in(tmp_path)
    work.at("system", 5)

    setup.STEPS["system"](work)

    disk = work.settings.disks / systems.disk_name(work.system)
    assert disk.is_file()
    assert ["fallocate", "--dig-holes", str(disk)] in commands


def test_a_disk_that_cannot_lose_its_zeros_is_kept_whole(
        tmp_path, commands, a_system_arrives):
    commands.refuse = ("fallocate",)
    work = work_in(tmp_path)

    setup.STEPS["system"](work)

    assert (work.settings.disks / systems.disk_name(work.system)).is_file()


def leftover_of_a_fetch(disks):
    """What a fetch cut short leaves: its folder, with half a disk in it,
    which nothing lists and the room check counts as used.

    @returns pathlib.Path of the folder.
    """
    left = disks / (systems.FETCHING_PREFIX + "x1y2z3")
    left.mkdir(parents=True, exist_ok=True)
    (left / "NS33_2GB.dd").write_bytes(b"half of it")
    return left


def test_what_a_fetch_cut_short_left_goes_with_the_next_fetch(
        tmp_path, commands, a_system_arrives):
    """A folder of up to two gigabytes, left by a power cut or a stopped
    helper, that no listing shows and that the room check counted as used
    from then on."""
    work = work_in(tmp_path)
    left = leftover_of_a_fetch(work.settings.disks)

    setup.STEPS["system"](work)

    assert not left.exists()
    assert (work.settings.disks / systems.disk_name(work.system)).is_file()


def test_what_an_interrupted_run_left_goes_with_any_job(tmp_path, monkeypatch):
    """The helper only runs for a job, so the next job of any kind is the
    moment a card that was interrupted is clean again."""
    monkeypatch.setattr(setup, "STEPS", {"nothing": lambda work: None})
    work = work_in(tmp_path, steps=("nothing",))
    left = leftover_of_a_fetch(work.settings.disks)

    assert setup.carry_out(work) is True
    assert not left.exists()


def test_what_an_interrupted_run_left_counts_as_room(tmp_path, monkeypatch):
    """The service asks the same question before it leaves a request, and it
    cannot remove what root left. A leftover as large as the room a system
    needs would otherwise keep every fetch refused for good."""
    monkeypatch.setattr(systems, "room_beside", lambda where: 1024)
    work = work_in(tmp_path)
    left = leftover_of_a_fetch(work.settings.disks)
    os.truncate(left / "NS33_2GB.dd", systems.ROOM_BYTES)

    setup.room_for(("system",), work.system, work.settings.disks)


def test_a_card_with_no_room_is_said_so_before_anything_is_fetched(
        tmp_path, commands, monkeypatch):
    """A card that fills up during an unpack leaves a half written image and a
    person with no idea why."""
    monkeypatch.setattr(systems, "room_beside", lambda where: 1024)
    monkeypatch.setattr(setup, "_fetched",
                        lambda *a, **k: pytest.fail("fetched it anyway"))

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["system"](work_in(tmp_path))

    assert refused.value.told["reason"] == "setup.no-room"
    assert refused.value.told["free"] == 1024


def test_a_card_too_small_for_the_system_is_refused_in_the_first_step(
        tmp_path, commands, monkeypatch):
    """The steps in front of the system put minutes of packages on the card,
    and a refusal at the system step takes every one of them off again. The
    first step changes nothing, so that is where a card that is too small is
    refused. `install.sh` leaves its request without asking the service, so
    the service refusing first does not cover it."""
    taken = []
    monkeypatch.setattr(setup, "STEPS", {
        **setup.STEPS,
        **{name: (lambda work, name=name: taken.append(name))
           for name in setup.STEPS if name != "host"}})
    monkeypatch.setattr(setup, "_release", lambda: setup.RELEASE)
    commands.answers = {"--print-architecture": setup.ARCHITECTURE}
    # Room for the disk and its margin, and none for the packages in front.
    monkeypatch.setattr(systems, "room_beside", lambda where: systems.ROOM_BYTES)
    work = work_in(tmp_path)

    assert setup.carry_out(work) is False
    said = work.reading()

    assert taken == []
    assert said["step"] == "host"
    assert said["failed"]["reason"] == "setup.no-room"
    assert said["undone"] == []


@pytest.mark.parametrize("job,in_front", [
    ("install", setup.TOOLS_BYTES + setup.EMULATOR_BYTES),
    ("fetch", setup.TOOLS_BYTES),
])
def test_the_room_for_a_system_counts_the_packages_in_front_of_it(
        tmp_path, commands, monkeypatch, job, in_front):
    """A system is fetched after the tools, and in an installation after the
    emulator as well, so what their packages take is gone from the card by
    the time the disk is unpacked."""
    monkeypatch.setattr(systems, "room_beside", lambda where: 1024)

    with pytest.raises(setup.Refused) as refused:
        setup.room_for(setup.JOBS[job], systems.find("nextstep-3.3"), tmp_path)

    assert refused.value.told["needed"] == systems.ROOM_BYTES + in_front
    assert refused.value.told["free"] == 1024


def test_packages_that_are_here_take_no_more_room(tmp_path, monkeypatch):
    """Which is how the system step finds it, since the packages are in by
    then."""
    monkeypatch.setattr(setup, "installed", lambda package: True)
    monkeypatch.setattr(systems, "room_beside", lambda where: systems.ROOM_BYTES)

    setup.room_for(setup.JOBS["install"], systems.find("nextstep-3.3"), tmp_path)


@pytest.mark.parametrize("job,system", [
    ("forget", "nextstep-3.3"),
    ("install", None),
    ("update", None),
])
def test_a_run_that_fetches_no_system_needs_no_room(tmp_path, commands,
                                                    monkeypatch, job, system):
    monkeypatch.setattr(systems, "room_beside", lambda where: 0)

    setup.room_for(setup.JOBS[job], systems.find(system) if system else None,
                   tmp_path)


def test_a_system_that_is_already_here_needs_no_room(tmp_path, commands,
                                                     monkeypatch):
    monkeypatch.setattr(systems, "room_beside", lambda where: 0)
    (tmp_path / "nextstep-3.3.dd").write_bytes(b"x")

    setup.room_for(setup.JOBS["install"], systems.find("nextstep-3.3"), tmp_path)


@pytest.fixture
def swap_file(tmp_path, monkeypatch):
    """A swap file beside the disks, and rpi-swap answering about it.

    @returns a function taking the mechanism rpi-swap is set to, or None where
      nothing sets one, and answering with the room the file takes.
    """
    swap = tmp_path / "swap"
    swap.write_bytes(b"\1" * 1024 * 1024)

    def set_to(mechanism):
        said = "path='%s'" % swap
        if mechanism:
            said = "mechanism='%s'\n%s" % (mechanism, said)
        monkeypatch.setattr(setup, "_said", lambda command: (
            said if command[0] == "rpi-systemd-config" else ""))
        return swap.stat().st_blocks * setup.STAT_BLOCK_BYTES

    return set_to


def test_a_swap_file_the_next_boot_removes_asks_for_that_boot(
        tmp_path, monkeypatch, swap_file):
    """rpi-swap removes the file at the next boot once it is set to keep swap
    in memory, and not before, so the room it holds is coming and is not yet
    there to unpack into. The setup does not restart a machine in the middle
    of a run, so it says that a restart is what it is waiting for."""
    back = swap_file("zram")
    monkeypatch.setattr(setup, "installed", lambda package: True)
    monkeypatch.setattr(systems, "room_beside",
                        lambda where: systems.ROOM_BYTES - back)

    with pytest.raises(setup.Refused) as refused:
        setup.room_for(setup.JOBS["install"], systems.find("nextstep-3.3"),
                       tmp_path)

    assert refused.value.told["reason"] == "setup.no-room-until-restart"
    assert refused.value.told["back"] == back
    assert refused.value.told["needed"] == systems.ROOM_BYTES


@pytest.mark.parametrize("mechanism,short", [
    # Nothing set is rpi-swap's own default, which keeps the file.
    (None, 0),
    ("zram+file", 0),
    # Set to go, and still not enough once it has.
    ("zram", 1),
])
def test_a_swap_file_that_stays_or_does_not_help_is_no_room(
        tmp_path, monkeypatch, swap_file, mechanism, short):
    back = swap_file(mechanism)
    monkeypatch.setattr(setup, "installed", lambda package: True)
    monkeypatch.setattr(systems, "room_beside",
                        lambda where: systems.ROOM_BYTES - back - short)

    with pytest.raises(setup.Refused) as refused:
        setup.room_for(setup.JOBS["install"], systems.find("nextstep-3.3"),
                       tmp_path)

    assert refused.value.told["reason"] == "setup.no-room"


def test_a_machine_without_rpi_swap_gives_nothing_back(tmp_path, monkeypatch):
    """Which is also how it answers where the tool that reads its settings is
    not there or says nothing."""
    monkeypatch.setattr(setup, "_said", lambda command: "")
    monkeypatch.setattr(setup, "installed", lambda package: True)
    monkeypatch.setattr(systems, "room_beside", lambda where: 1024)

    with pytest.raises(setup.Refused) as refused:
        setup.room_for(setup.JOBS["install"], systems.find("nextstep-3.3"),
                       tmp_path)

    assert refused.value.told["reason"] == "setup.no-room"


def test_what_apt_downloaded_is_cleared_once_the_packages_are_in(tmp_path,
                                                                 commands):
    """apt-get keeps every package it downloads, and the room they take is
    room a system's disk needs a few minutes later."""
    work = work_in(tmp_path)
    work.at("tools", 2)

    setup._packages(work, ["cage"])
    installing = next(index for index, command in enumerate(commands)
                      if "install" in command)

    assert ["apt-get", "clean"] in commands[installing:]


def test_the_sound_brings_pipewire_without_the_parts_nothing_uses(tmp_path, commands,
                                                                  monkeypatch):
    """Previous reaches PipeWire through SDL's own driver, so a plugin for ALSA
    programs and a server for PulseAudio programs have nobody to serve.
    wireplumber recommends the second, so apt is told to leave it out."""
    monkeypatch.setattr(setup, "SOUND_CONFIGURATION", tmp_path / "50-nextstep.conf")
    work = work_in(tmp_path)
    work.at("sound", 10)

    setup.STEPS["sound"](work)
    installing = next(command for command in commands if "install" in command)

    assert {"pipewire", "wireplumber", "pipewire-pulse-"} <= set(installing)
    assert "pipewire-alsa" not in installing
    assert "pipewire-pulse" not in installing


def test_removing_takes_the_speakers_volume_away_and_a_failed_run_puts_it_back(
        tmp_path, monkeypatch):
    """The sound step wrote the file, so Remove takes it back with everything
    else it undoes. A Pi that had Previously removed kept it before."""
    monkeypatch.setattr(setup, "SOUND_CONFIGURATION", tmp_path / "50-nextstep.conf")
    setup.SOUND_CONFIGURATION.write_text("the volume")
    work = work_in(tmp_path, job="remove")
    work.at("no-sound", 3)

    setup.STEPS["no-sound"](work)
    assert not setup.SOUND_CONFIGURATION.exists()
    assert work.changed == ["no-sound"]

    work.reverse()
    assert setup.SOUND_CONFIGURATION.read_text() == "the volume"


def test_a_machine_without_the_volume_file_has_nothing_to_take_away(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "SOUND_CONFIGURATION", tmp_path / "50-nextstep.conf")
    work = work_in(tmp_path, job="remove")
    work.at("no-sound", 3)

    setup.STEPS["no-sound"](work)

    assert work.changed == []


def test_removing_takes_the_sound_back_after_the_startup():
    """It joins the remove job behind the step that puts the startup back, so
    the two things the install job set up last are taken back first."""
    steps = setup.JOBS["remove"]

    assert steps.index("no-sound") == steps.index("loud") + 1


def test_a_cache_that_cannot_be_cleared_does_not_stop_the_step(tmp_path,
                                                               monkeypatch):
    """The packages are in either way, and the room the cache keeps is what the
    system step asks about before it fetches anything."""
    ran = []

    def run(command, seconds=None, heard=None):
        ran.append(command)
        if command == ["apt-get", "clean"]:
            raise setup.Refused("setup.command-failed", command="apt-get",
                                code=100)
        return ""

    monkeypatch.setattr(setup, "run", run)
    monkeypatch.setattr(setup, "installed", lambda package: False)
    monkeypatch.setattr(setup, "_packages_here", lambda: {})
    work = work_in(tmp_path)
    work.at("tools", 2)

    setup._packages(work, ["cage"])

    assert ["apt-get", "clean"] in ran
    assert work.changed == ["tools"]


def test_the_largest_file_in_an_archive_is_the_disk(tmp_path):
    """Those archives carry ROM images, a Windows binary and a text file
    besides."""
    (tmp_path / "Rev_3.3_v74.BIN").write_bytes(b"x" * 1024)
    disk = tmp_path / "NS33_2GB.dd"
    disk.write_bytes(b"")
    os.truncate(disk, systems.SMALLEST_DISK_BYTES)

    assert setup._disk_among(tmp_path, systems.find("nextstep-3.3")) == disk


def test_an_archive_with_no_disk_in_it_is_said_so(tmp_path):
    (tmp_path / "readme.txt").write_bytes(b"x")

    with pytest.raises(setup.Refused) as refused:
        setup._disk_among(tmp_path, systems.find("nextstep-3.3"))

    assert refused.value.told["reason"] == "setup.no-disk-in-the-archive"


# -- which version is here, and which the archive has ---------------------


@pytest.mark.parametrize("version,other,newer", [
    ("4.3-0wmlive1", "4.4-0wmlive1", True),
    ("4.4-0wmlive1", "4.4-0wmlive1", False),
    ("4.4-0wmlive1", "4.3-0wmlive1", False),
    # Debian's ordering is its own, and a string comparison calls this one the
    # wrong way round and offers a downgrade as an update.
    ("4.9", "4.10", True),
    ("4.10", "4.9", False),
    (None, "4.4", False),
    ("4.4", None, False),
])
def test_whether_one_version_is_newer_is_asked_of_dpkg(version, other, newer):
    assert setup.newer_than(version, other) is newer


def test_what_the_archive_offers_is_read_off_apt(monkeypatch):
    """`apt-cache policy` says what would actually be installed, which is what
    the window offers rather than what exists somewhere."""
    monkeypatch.setattr(setup, "_said", lambda command: (
        "previous:\n  Installed: 4.3-0wmlive1\n  Candidate: 4.4-0wmlive1\n"
        "  Version table:\n"))

    assert setup.newest_of("previous") == "4.4-0wmlive1"


def test_a_package_the_archive_does_not_have_offers_nothing(monkeypatch):
    monkeypatch.setattr(setup, "_said", lambda command: (
        "previous:\n  Installed: (none)\n  Candidate: (none)\n"))

    assert setup.newest_of("previous") is None


def test_nothing_at_all_from_apt_offers_nothing(monkeypatch):
    """A machine with no apt, or one where the archive is not configured."""
    monkeypatch.setattr(setup, "_said", lambda command: "")

    assert setup.newest_of("previous") is None


def test_what_dpkg_and_apt_said_is_kept_for_a_few_seconds(monkeypatch):
    """The window asks twice a second while it is open, and those three
    commands are the most expensive thing behind that route."""
    asked = []
    monkeypatch.setattr(setup, "installed", lambda package: True)
    monkeypatch.setattr(setup, "version_of",
                        lambda package: asked.append(package) or "4.4")
    monkeypatch.setattr(setup, "newest_of", lambda package: "4.4")

    setup.emulator()
    setup.emulator()

    assert len(asked) == 1


def test_what_was_remembered_is_thrown_away_when_something_is_installed(monkeypatch):
    """A run that installs or removes the emulator changes every one of those
    answers, and the window asks again the instant it finishes."""
    asked = []
    monkeypatch.setattr(setup, "installed", lambda package: True)
    monkeypatch.setattr(setup, "version_of",
                        lambda package: asked.append(package) or "4.4")
    monkeypatch.setattr(setup, "newest_of", lambda package: "4.4")

    setup.emulator()
    setup.forget()
    setup.emulator()

    assert len(asked) == 2


def test_what_is_remembered_cannot_be_changed_from_outside(monkeypatch):
    """It is handed out as a copy, so a caller that writes into the answer does
    not write into what the next caller is given."""
    monkeypatch.setattr(setup, "installed", lambda package: True)
    monkeypatch.setattr(setup, "version_of", lambda package: "4.4")
    monkeypatch.setattr(setup, "newest_of", lambda package: "4.4")

    setup.emulator()["here"] = "nonsense"

    assert setup.emulator()["here"] is True


# -- a copy of a disk, and the copy put back ------------------------------


@pytest.fixture
def quiet(monkeypatch):
    """A machine with nothing running on it, which is what a copy needs."""
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: False)


@pytest.fixture
def card(tmp_path, quiet):
    """A card with one system's disk on it, and the run that acts on it."""
    work = work_in(tmp_path, job="back-up")
    disk = work.settings.disks / "nextstep-3.3.dd"
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"a whole system" * 100)
    return work


def test_a_copy_is_named_after_the_system_and_the_moment(card):
    setup.STEPS["copy"](card)

    copies = systems.copies_in(card.settings.disks)
    (path, system), = copies

    assert system.identifier == "nextstep-3.3"
    assert path.name.startswith("nextstep-3.3 20")
    assert path.read_bytes() == (card.settings.disks / "nextstep-3.3.dd").read_bytes()


def test_a_copy_is_not_taken_while_the_machine_runs(card, monkeypatch):
    """A copy taken while NeXTSTEP is writing is a torn file system: it looks
    like a disk and fails on the first boot in a way nobody can debug."""
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: True)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["copy"](card)

    assert refused.value.told["reason"] == "setup.machine-is-running"
    assert systems.copies_in(card.settings.disks) == []


def test_a_copy_that_will_not_fit_is_said_so_first(card, monkeypatch):
    """What a copy costs and what is left is said before it starts, because a
    card that fills up half way leaves a file that looks like a disk."""
    monkeypatch.setattr(systems, "room_beside", lambda where: 1024)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["copy"](card)

    assert refused.value.told["reason"] == "setup.no-room"
    assert systems.copies_in(card.settings.disks) == []


def test_a_copy_of_a_system_that_is_not_here_is_refused(tmp_path, quiet):
    work = work_in(tmp_path, job="back-up")
    work.settings.disks.mkdir(parents=True)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["copy"](work)

    assert refused.value.told["reason"] == "setup.system-is-not-here"


def test_a_copy_is_written_back_over_its_disk(card):
    setup.STEPS["copy"](card)
    (copy, _), = systems.copies_in(card.settings.disks)
    disk = card.settings.disks / "nextstep-3.3.dd"
    disk.write_bytes(b"an evening of work")

    card.backup = copy.name
    setup.STEPS["put-back"](card)

    assert disk.read_bytes() == copy.read_bytes()
    # And the copy is still there, because putting one back is not spending it.
    assert copy.is_file()


@pytest.mark.parametrize("named", [
    None,
    "../../etc/passwd",
    "nothing-of-that-name.dd",
    "/etc/passwd",
])
def test_a_copy_that_is_not_in_that_folder_is_refused(card, named):
    """The name arrives from a browser, so it is matched against the listing of
    one folder rather than joined onto a path. A name carrying separators asks
    for a file that is not in the answer."""
    setup.STEPS["copy"](card)
    disk = card.settings.disks / "nextstep-3.3.dd"
    before = disk.read_bytes()
    card.backup = named

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["put-back"](card)

    assert refused.value.told["reason"] == "setup.no-such-copy"
    assert disk.read_bytes() == before


def test_nothing_is_put_back_while_the_machine_runs(card, monkeypatch):
    setup.STEPS["copy"](card)
    (copy, _), = systems.copies_in(card.settings.disks)
    card.backup = copy.name
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: True)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["put-back"](card)

    assert refused.value.told["reason"] == "setup.machine-is-running"


def test_a_copy_that_stops_half_way_leaves_the_disk_alone(card, monkeypatch):
    """It is written beside the disk and moved into place, so a card that fills
    up during the copy leaves the disk that was there rather than half of each.
    """
    setup.STEPS["copy"](card)
    (copy, _), = systems.copies_in(card.settings.disks)
    disk = card.settings.disks / "nextstep-3.3.dd"
    disk.write_bytes(b"an evening of work")
    before = disk.read_bytes()
    card.backup = copy.name

    def stops(source, into, work):
        into.write_bytes(b"half of it")
        raise setup.Refused("setup.cannot-copy", name="NeXTSTEP 3.3")

    monkeypatch.setattr(setup, "_copied_across", stops)

    with pytest.raises(setup.Refused):
        setup.STEPS["put-back"](card)

    assert disk.read_bytes() == before


def a_copy_cut_short(card, monkeypatch):
    """Starts a copy and kills it half way, as a power cut or a stopped helper
    does: half the file is written and nothing after that runs, not even the
    undo of the run."""
    def killed(source, into, work):
        into.write_bytes(b"half of it")
        raise SystemExit("killed")

    whole = setup._copied_across
    monkeypatch.setattr(setup, "_copied_across", killed)
    with pytest.raises(SystemExit):
        setup.STEPS["copy"](card)
    monkeypatch.setattr(setup, "_copied_across", whole)


def test_a_copy_cut_short_is_never_offered_to_be_put_back(card, monkeypatch):
    """The File Viewer and Put Back both list what `copies_in` finds, and half a
    disk written back over a whole one is the disk lost."""
    a_copy_cut_short(card, monkeypatch)

    assert systems.copies_in(card.settings.disks) == []


def test_what_a_copy_cut_short_left_goes_with_the_next_copy(card, monkeypatch):
    """Otherwise it would hold two gigabytes of the card for good, out of sight
    of everything that shows what takes the room.

    The two copies are a second apart, as they are on a machine, because two
    taken in the same second share a name and the second simply replaces the
    first."""
    seconds = iter(range(2))
    named = systems.a_copy_of
    monkeypatch.setattr(systems, "a_copy_of", lambda system, when: named(
        system, when + datetime.timedelta(seconds=next(seconds))))
    a_copy_cut_short(card, monkeypatch)

    setup.STEPS["copy"](card)

    backups = systems.backups_in(card.settings.disks)
    (copy, _), = systems.copies_in(card.settings.disks)
    assert sorted(path.name for path in backups.iterdir()) == [copy.name]
    assert copy.read_bytes() == (card.settings.disks / "nextstep-3.3.dd").read_bytes()


def leftovers_of_other_runs(card):
    """What interrupted runs leave on a card: a copy of another system cut
    short in `backups/`, and a put back cut short beside the disk.

    @returns list of pathlib.Path, each written.
    """
    disks = card.settings.disks
    backups = systems.backups_in(disks)
    backups.mkdir(parents=True, exist_ok=True)
    other = systems.find("openstep-4.2")
    left = [
        systems.unfinished(backups / systems.a_copy_of(
            other, datetime.datetime(2026, 1, 1, 10, 0, 0))),
        systems.coming_back(disks / "nextstep-3.3.dd"),
    ]
    for path in left:
        path.write_bytes(b"half of it")
    return left


def test_a_copy_takes_away_what_any_interrupted_run_left(card):
    """Of any system, because one whose disk is never copied again would
    otherwise keep two gigabytes of the card for good, and a put back cut
    short leaves as much beside its disk."""
    left = leftovers_of_other_runs(card)

    setup.STEPS["copy"](card)

    assert [path for path in left if path.exists()] == []
    assert len(systems.copies_in(card.settings.disks)) == 1


def test_a_put_back_takes_away_what_any_interrupted_run_left(card):
    setup.STEPS["copy"](card)
    (copy, _), = systems.copies_in(card.settings.disks)
    left = leftovers_of_other_runs(card)
    disk = card.settings.disks / "nextstep-3.3.dd"
    disk.write_bytes(b"an evening of work")
    card.backup = copy.name

    setup.STEPS["put-back"](card)

    assert [path for path in left if path.exists()] == []
    assert disk.read_bytes() == copy.read_bytes()


def test_how_far_a_copy_has_got_is_readable_while_it_runs(card):
    """Two gigabytes on a card is minutes, so this is a window somebody leaves
    open and comes back to."""
    setup.carry_out(card)

    said = json.loads(
        (card.into / setup.PROGRESS).read_text(encoding="utf-8"))

    assert said["ok"] is True
    assert said["step"] == "copy"
    assert said["of"] == 1


# -- this tool replacing itself -------------------------------------------


#: What the newest release comes back as, which is what `release.look` answers.
PUBLISHED = {
    "version": "1.0.1",
    "url": ("https://github.com/phranck/previously/releases/download/v1.0.1/"
            "previously_all.deb"),
    "size": 269770,
    "digest": "7298d28c17d560ad4cc97906ab35ffbe2795130457f8374375ef529bcdc293ad",
    "asked_at": 0.0,
}


@pytest.fixture
def a_release(tmp_path, monkeypatch, commands):
    """A published release, a version that is here, and a download that works.

    @returns the list of commands, as `commands` does, so a test can read what
      root would have run and make one of them fail.

    Nothing reaches the network and nothing writes outside the test's own
    directory: the package this leaves is whatever the fetch was told to write,
    and where it is written is inside `tmp_path` so a step that stops half way
    leaves nothing for pytest to clean up after.
    """
    monkeypatch.setattr(setup.release, "look", lambda: dict(PUBLISHED))
    monkeypatch.setattr(setup, "version_of", lambda package: "1.0.0")
    monkeypatch.setattr(setup, "newer_than",
                        lambda version, other: version != other)

    holding = tmp_path / "downloaded"
    monkeypatch.setattr(setup.tempfile, "mkdtemp",
                        lambda prefix=None: str(holding.mkdir() or holding))

    def fetched(url, into, work, hosts, expecting=None):
        into.write_bytes(b"a package")

    monkeypatch.setattr(setup, "_fetched", fetched)
    commands.answers = {"Package": "previously", "Version": "1.0.1"}
    return commands


def test_the_newest_release_is_fetched_and_then_installed(tmp_path, a_release):
    """The two steps together, because what the first leaves is what the second
    acts on and the point of splitting them is that the second is where the
    service goes away."""
    work = work_in(tmp_path, job="update-tool", system=None)

    setup.STEPS["tool-package"](work)
    package = work.tool / setup.release.ASSET

    assert package.read_bytes() == b"a package"

    setup.STEPS["newest-tool"](work)

    assert ["apt-get", "install", "-y", "-qq", str(package)] in a_release
    assert not work.tool.exists(), "the package was left on the card"


def test_nothing_is_fetched_where_this_is_already_the_newest(tmp_path, a_release,
                                                             monkeypatch):
    """Which is what the button being absent says in the window, and this is the
    same answer where somebody asks anyway."""
    monkeypatch.setattr(setup, "version_of", lambda package: "1.0.1")

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["tool-package"](work_in(tmp_path, job="update-tool",
                                            system=None))

    assert refused.value.told["reason"] == "setup.tool-is-current"


def test_a_github_that_cannot_be_asked_stops_it_before_anything_is_written(
        tmp_path, a_release, monkeypatch):
    def refuses():
        raise setup.release.Unreachable("no route to host")

    monkeypatch.setattr(setup.release, "look", refuses)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["tool-package"](work_in(tmp_path, job="update-tool",
                                            system=None))

    assert refused.value.told["reason"] == "setup.cannot-ask-about-releases"


def test_a_package_that_is_not_this_tool_never_reaches_apt(tmp_path, a_release):
    """The one check a digest cannot make. A digest proves the bytes are the
    bytes GitHub served, and this proves that what GitHub served is this tool."""
    a_release.answers = {"Package": "coreutils", "Version": "1.0.1"}
    work = work_in(tmp_path, job="update-tool", system=None)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["tool-package"](work)

    assert refused.value.told["reason"] == "setup.not-our-package"
    assert not any(command[0] == "apt-get" for command in a_release)


def test_a_package_of_another_version_never_reaches_apt(tmp_path, a_release):
    """Somebody was offered 1.0.1, so 1.0.1 is what may be installed. Anything
    else is a release that changed underneath the offer."""
    a_release.answers = {"Package": "previously", "Version": "0.9.0"}
    work = work_in(tmp_path, job="update-tool", system=None)

    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["tool-package"](work)

    assert refused.value.told["reason"] == "setup.not-that-version"
    assert refused.value.told["found"] == "0.9.0"
    assert not any(command[0] == "apt-get" for command in a_release)


def test_a_fetch_that_stopped_leaves_nothing_on_the_card(tmp_path, a_release):
    """The directory is on the record of what to undo as well as removed by the
    step that installs, so a run that stops between the two leaves neither a
    package nor a directory holding one."""
    work = work_in(tmp_path, job="update-tool", system=None)
    a_release.answers = {"Package": "previously", "Version": "0.9.0"}
    with pytest.raises(setup.Refused):
        setup.STEPS["tool-package"](work)

    work.reverse()

    assert not work.tool.exists()


def test_an_installation_that_failed_leaves_nothing_on_the_card(tmp_path,
                                                                a_release):
    """A failure leaves the tool that is here installed and running, which is the
    safe direction, and it must not also leave a quarter of a megabyte behind."""
    work = work_in(tmp_path, job="update-tool", system=None)
    setup.STEPS["tool-package"](work)
    a_release.refuse = ("apt-get",)

    with pytest.raises(setup.Refused):
        setup.STEPS["newest-tool"](work)

    assert not work.tool.exists()


def test_installing_with_nothing_fetched_is_refused(tmp_path, a_release):
    """Which cannot happen through a job, because the steps are in order. It is
    checked because the alternative is `apt-get install` on a path built from
    None."""
    with pytest.raises(setup.Refused) as refused:
        setup.STEPS["newest-tool"](work_in(tmp_path, job="update-tool",
                                           system=None))

    assert refused.value.told["reason"] == "setup.no-package-to-install"


def test_what_the_window_is_told_while_this_runs(tmp_path, a_release):
    """The whole reason the work is done by the helper rather than by the
    service: the record outlives the service being stopped and started, so this
    is what a page reads before and after."""
    work = work_in(tmp_path, job="update-tool", system=None)

    setup.STEPS["tool-package"](work)
    said = json.loads((work.into / setup.PROGRESS).read_text())

    assert said["do"] == "update-tool"
    assert said["part"]["doing"] == setup.CHECKING
    assert said["part"]["of"] == PUBLISHED["size"]

    setup.STEPS["newest-tool"](work)
    said = json.loads((work.into / setup.PROGRESS).read_text())

    assert said["part"]["doing"] == setup.INSTALLING


# -- what may be fetched, and from where ----------------------------------


@pytest.fixture
def archive_run(tmp_path, monkeypatch):
    """A run at the archive step, with the files of the archive's source in
    the test's own directory.

    @returns the run.
    """
    for name in ("REPOSITORY_KEY", "REPOSITORY_MIRRORS", "REPOSITORY_PINS",
                 "REPOSITORY_SOURCE"):
        monkeypatch.setattr(setup, name, tmp_path / "apt" / name.lower())
    work = work_in(tmp_path, job="update", system=None)
    work.at("archive", 1)
    return work


def paragraphs_of(path):
    """@returns list of dict, one per paragraph of a file in apt's deb822 form."""
    return [dict(line.split(": ", 1) for line in paragraph.splitlines())
            for paragraph in path.read_text(encoding="utf-8").split("\n\n")]


def test_apt_turns_to_the_copy_for_whatever_the_archive_does_not_hand_over(
        archive_run):
    """Some networks cannot reach the archive. apt asks the mirrors in the
    order of their priority, and the next one for every file the one before
    does not hand over, whatever it answered instead."""
    setup.STEPS["archive"](archive_run)

    mirrors = [line.split("\t") for line in setup.REPOSITORY_MIRRORS.read_text(
        encoding="utf-8").splitlines()]
    source, = paragraphs_of(setup.REPOSITORY_SOURCE)

    assert mirrors == [[setup.REPOSITORY_URL, "priority:1"],
                       [setup.REPOSITORY_COPY_URL, "priority:2"]]
    assert source["URIs"] == "mirror+file:%s" % setup.REPOSITORY_MIRRORS
    assert source["Signed-By"] == str(setup.REPOSITORY_KEY)
    assert setup.REPOSITORY_KEY.read_bytes() == \
        setup.REPOSITORY_KEY_SHIPPED.read_bytes()


def test_the_pins_hold_the_archive_and_its_copy_alike(archive_run):
    """The two are served from two hosts, so a pin on a host would leave the
    copy offering every package the archive carries, at the priority Debian's
    own have. Both serve the archive's Release, and with it its Origin."""
    setup.STEPS["archive"](archive_run)

    pins = [(paragraph["Package"], paragraph["Pin"], paragraph["Pin-Priority"])
            for paragraph in paragraphs_of(setup.REPOSITORY_PINS)]

    # What the first line of the archive's Release says.
    origin = "release o=wmlive.rumbero.org"
    assert pins == [("*", origin, "-1"), (setup.EMULATOR_PACKAGE, origin, "500")]


def test_a_machine_set_up_for_the_archive_alone_is_brought_to_its_copy(
        archive_run):
    """Its source names the archive and its pins name the archive's host.
    Both are replaced, and a later step that fails puts both back."""
    was = {setup.REPOSITORY_KEY: setup.REPOSITORY_KEY_SHIPPED.read_bytes(),
           setup.REPOSITORY_SOURCE: (
               "Types: deb\nURIs: %s\n" % setup.REPOSITORY_URL).encode(),
           setup.REPOSITORY_PINS: b"Package: *\nPin: origin wmlive.rumbero.org\n"}
    setup.REPOSITORY_KEY.parent.mkdir(parents=True)
    for path, content in was.items():
        path.write_bytes(content)

    setup.STEPS["archive"](archive_run)

    assert "mirror+file:" in setup.REPOSITORY_SOURCE.read_text(encoding="utf-8")
    assert "release o=" in setup.REPOSITORY_PINS.read_text(encoding="utf-8")
    assert archive_run.changed == ["archive"]

    archive_run.reverse()

    assert {path: path.read_bytes() for path in was} == was
    assert not setup.REPOSITORY_MIRRORS.exists()


def test_an_archive_source_that_is_current_is_left_alone(tmp_path, archive_run):
    """Asking for an update twice changes nothing the second time, so a later
    failure has nothing of this step's to put back."""
    setup.STEPS["archive"](archive_run)
    again = work_in(tmp_path, job="update", system=None)
    again.at("archive", 1)

    setup.STEPS["archive"](again)

    assert again.changed == []


def test_the_package_brings_an_archive_source_up_to_date(archive_run):
    """The package does this on every install and upgrade, so a machine
    reaches the copy from the moment the tool is updated, before any job asks
    apt for anything."""
    setup.REPOSITORY_SOURCE.parent.mkdir(parents=True)
    setup.REPOSITORY_SOURCE.write_text(
        "Types: deb\nURIs: %s\n" % setup.REPOSITORY_URL, encoding="utf-8")

    assert setup.refresh_archive()
    assert setup.REPOSITORY_SOURCE.read_bytes() == \
        setup._archive_files()[setup.REPOSITORY_SOURCE]
    assert not setup.refresh_archive(), "wrote a current source a second time"


def test_the_package_gives_a_machine_without_the_archive_none(archive_run):
    """Installing the tool is not setting the machine up. The source is added
    by the install job, and the package only keeps one that is there
    current."""
    assert not setup.refresh_archive()
    assert not any(path.exists() for path in setup._archive_files())


def test_taking_the_emulator_away_takes_its_source_with_it(archive_run, commands):
    setup.STEPS["archive"](archive_run)

    setup.STEPS["no-emulator"](archive_run)

    assert not any(path.exists() for path in setup._archive_files())


# -- who owns what it writes ----------------------------------------------


def test_the_owner_is_read_out_of_the_owner_file(tmp_path, monkeypatch):
    """Rather than named a second time here. The package writes it down when
    it is installed, and a helper that disagreed with it would write into the
    wrong home."""
    import pwd

    me = pwd.getpwuid(os.getuid()).pw_name
    unit = tmp_path / "owner.conf"
    unit.write_text("[Service]\nUser=%s\nGroup=%s\n" % (me, me), encoding="utf-8")

    assert setup.Owner.from_unit(unit).name == me


@pytest.mark.parametrize("written", ["[Service]\nExecStart=/bin/true\n", ""])
def test_a_unit_that_does_not_say_who_owns_it_stops_the_work(tmp_path, written):
    unit = tmp_path / "previously.service"
    unit.write_text(written, encoding="utf-8")

    with pytest.raises(setup.Refused) as refused:
        setup.Owner.from_unit(unit)

    assert refused.value.told["reason"] == "setup.no-owner"


def test_a_unit_that_is_not_there_stops_the_work(tmp_path):
    with pytest.raises(setup.Refused):
        setup.Owner.from_unit(tmp_path / "never-installed.service")


# -- an owner under a new name --------------------------------------------


#: A user no machine running the suite has, which is what the owner file names
#: once Raspberry Pi OS has renamed the first user.
GONE = "previously-test-renamed-away"


@pytest.fixture
def renamed(tmp_path, monkeypatch, commands):
    """A machine set up for a user who has since been renamed: the owner file,
    the console and previous.cfg name the old name and the old home, and the
    files themselves have moved to the new home with the user, as userconf-pi
    moves them.

    @returns a namespace with the owner file, the old and the new home, the
      new owner, previous.cfg and the service's state directory.
    """
    old = tmp_path / "home" / GONE
    new = tmp_path / "home" / "test"
    owner = Nobody(new)
    monkeypatch.setattr(setup, "_first_user", lambda: owner)

    unit = tmp_path / "owner.conf"
    unit.write_text("[Service]\nUser=%s\nGroup=%s\n" % (GONE, GONE) + "".join(
        "ReadWritePaths=-%s/%s\n" % (old, place) for place in (
            ".config/previous", ".config/previously", setup.WORK_DIRECTORY,
            "Previously")), encoding="utf-8")

    was = types.SimpleNamespace(name=GONE, uid=owner.uid, home=old)
    for path, (text, mode) in setup._console_files(was).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    configuration = new / ".config" / "previous" / "previous.cfg"
    configuration.parent.mkdir(parents=True)
    configuration.write_text(
        "[HardDisk]\nszImageName0 = %s/nextstep/nextstep-3.3.dd\n"
        "szImageName1 = /media/usb/OPENSTEP.iso\n\n[Printer]\n"
        "szPrintToFileName = %s/%s\n" % (old, old, setup.WORK_DIRECTORY),
        encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    config.note_written(configuration, state)

    return types.SimpleNamespace(unit=unit, old=old, new=new, owner=owner,
                                 configuration=configuration, state=state)


def test_an_owner_who_was_renamed_is_followed(renamed, commands):
    """Raspberry Pi OS renames the first user at the first boot to the name set
    in Raspberry Pi Imager, and to pi where none is set, and rename-user does
    it later on request. The owner file, the console and previous.cfg then
    name a user and a home that are gone."""
    assert setup.follow_owner(renamed.unit, renamed.configuration, renamed.state)

    unit = renamed.unit.read_text(encoding="utf-8")
    assert "User=test\n" in unit
    assert "Group=test\n" in unit
    assert str(renamed.old) not in unit
    assert "ReadWritePaths=-%s/%s\n" % (renamed.new, setup.WORK_DIRECTORY) in unit

    console = (setup.SYSTEM_UNITS / setup.CONSOLE).read_text(encoding="utf-8")
    assert console == setup._console_unit(renamed.owner)
    assert setup.CONSOLE_SCRIPT.read_text(encoding="utf-8") == \
        setup._console_script(renamed.owner)

    written = renamed.configuration.read_text(encoding="utf-8")
    assert "szImageName0 = %s/nextstep/nextstep-3.3.dd\n" % renamed.new in written
    assert "szPrintToFileName = %s/%s\n" % (renamed.new, setup.WORK_DIRECTORY) in written
    assert "szImageName1 = /media/usb/OPENSTEP.iso\n" in written
    assert config.written_by_us(renamed.configuration, renamed.state)

    assert ["systemctl", "daemon-reload"] in commands


def test_a_configuration_changed_from_outside_stays_so_when_followed(renamed):
    """An owner who moved must not make a hand edit look like Previously's
    own."""
    renamed.configuration.write_text(
        renamed.configuration.read_text(encoding="utf-8")
        + "\n[Sound]\nbEnableSound = FALSE\n", encoding="utf-8")

    setup.follow_owner(renamed.unit, renamed.configuration, renamed.state)

    assert not config.written_by_us(renamed.configuration, renamed.state)


def test_an_owner_who_is_there_is_left_alone(renamed, commands):
    import pwd

    me = pwd.getpwuid(os.getuid()).pw_name
    renamed.unit.write_text(renamed.unit.read_text(encoding="utf-8").replace(
        "User=%s\n" % GONE, "User=%s\n" % me), encoding="utf-8")
    was = renamed.unit.read_text(encoding="utf-8")

    assert not setup.follow_owner(renamed.unit, renamed.configuration, renamed.state)
    assert renamed.unit.read_text(encoding="utf-8") == was
    assert commands == []


def test_without_a_first_user_there_is_nobody_to_follow(renamed, commands, monkeypatch):
    monkeypatch.setattr(setup, "_first_user", lambda: None)
    was = renamed.unit.read_text(encoding="utf-8")

    assert not setup.follow_owner(renamed.unit, renamed.configuration, renamed.state)
    assert renamed.unit.read_text(encoding="utf-8") == was
    assert commands == []


# -- running a command ----------------------------------------------------


def test_a_command_that_is_not_here_is_said_so():
    with pytest.raises(setup.Refused) as refused:
        setup.run(["there-is-no-such-program-here"])

    assert refused.value.told["reason"] == "setup.no-such-command"


def test_a_command_that_fails_is_said_so_with_its_code():
    with pytest.raises(setup.Refused) as refused:
        setup.run(["false"])

    assert refused.value.told["reason"] == "setup.command-failed"
    assert refused.value.told["code"] != 0


def test_a_command_that_works_answers_with_what_it_said():
    assert setup.run(["echo", "still here"]) == "still here"


def test_nothing_is_run_through_a_shell(tmp_path):
    """Every command is an argument list, so there is no shell to talk into
    doing anything else. This is what that looks like when tried."""
    with pytest.raises(setup.Refused):
        setup.run(["echo hello; touch %s" % (tmp_path / "escaped")])

    assert not (tmp_path / "escaped").exists()


def test_a_command_that_reports_its_progress_is_heard_as_it_goes():
    """dpkg's status lines carry a percentage, and every one is passed on.
    The download's lines and anything else apt writes are not."""
    import sys

    said = ("pmstatus:cage:20:Unpacking cage\n"
            "dlstatus:1:50:Retrieving file 1 of 2\n"
            "Reading package lists...\n"
            "pmstatus:cage:100:Installed cage\n")
    heard = []

    answer = setup.run([sys.executable, "-c", "print(%r, end='')" % said],
                       heard=heard.append)

    assert heard == [20.0, 100.0]
    assert answer.endswith("Installed cage")


def test_a_reporting_command_that_fails_is_said_so_with_its_code():
    with pytest.raises(setup.Refused) as refused:
        setup.run(["false"], heard=lambda percent: None)

    assert refused.value.told["reason"] == "setup.command-failed"


def test_a_reporting_command_that_stops_answering_is_ended():
    """A command that stops writing is the one a wait for its next line would
    never see end, so the clock ends it."""
    with pytest.raises(setup.Refused) as refused:
        setup.run(["sleep", "5"], seconds=1, heard=lambda percent: None)

    assert refused.value.told["reason"] == "setup.took-too-long"


def test_installing_packages_says_how_far_dpkg_has_got(tmp_path, commands):
    """A step that installs a hundred packages takes minutes, so the window
    and the one-liner are told the percentage as it comes."""
    work = work_in(tmp_path)
    work.at("tools", 1)

    setup._packages(work, ["cage"])

    installing = [command for command in commands if "install" in command]
    assert "APT::Status-Fd=1" in installing[0]
    assert work.part == {"done": 42, "of": 100, "doing": setup.INSTALLING}


@pytest.fixture
def dpkg_says(monkeypatch):
    """What dpkg has on the card before an installation and after it.

    @returns a function taking the readings in the order they are asked for,
      each a dict of package to the state dpkg names it in.
    """
    def says(*readings):
        answers = iter(readings)
        monkeypatch.setattr(setup, "_packages_here", lambda: next(answers))

    return says


@pytest.mark.parametrize("step", ["tools", "emulator"])
def test_putting_packages_back_takes_what_came_with_them(tmp_path, commands,
                                                         dpkg_says, step):
    """apt installs a package with whatever it depends on, and taking back
    only the ones that were named leaves the rest on the card. A failed
    installation on an eight gigabyte card gave back five megabytes that
    way."""
    dpkg_says({"libc6:arm64": "installed"},
              {"libc6:arm64": "installed", "previous": "installed",
               "libsdl3-0": "installed"})
    work = work_in(tmp_path)
    work.at(step, 2)

    setup.STEPS[step](work)
    del commands[:]
    work.reverse()

    assert commands == [["apt-get", "purge", "-y", "-qq",
                         "libsdl3-0", "previous"]]


def test_a_package_that_left_its_configuration_behind_gets_it_back(
        tmp_path, commands, dpkg_says):
    """One taken off earlier without its configuration files is installed
    again by the run, and putting the run back leaves those files where they
    were. Undoing never takes away what the machine already had."""
    dpkg_says({"cage": "config-files"},
              {"cage": "installed", "libwlroots": "installed"})
    work = work_in(tmp_path)
    work.at("tools", 2)

    setup.STEPS["tools"](work)
    del commands[:]
    work.reverse()

    assert commands == [["apt-get", "purge", "-y", "-qq", "libwlroots"],
                        ["apt-get", "remove", "-y", "-qq", "cage"]]


def test_without_an_answer_from_dpkg_the_named_packages_are_put_back(
        tmp_path, commands, dpkg_says):
    """An empty answer is dpkg not answering rather than a card with nothing
    on it, and reading it as the second would put back every package there
    is."""
    dpkg_says({}, {"cage": "installed", "libc6:arm64": "installed"})
    work = work_in(tmp_path)
    work.at("tools", 2)

    setup._packages(work, ["cage"])
    del commands[:]
    work.reverse()

    assert commands == [["apt-get", "remove", "-y", "-qq", "cage"]]
