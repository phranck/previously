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

import json
import os
import pathlib
import re

import pytest

from conftest import settings_for
from previously import machines, setup, systems


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
    """Two console= arguments would leave the kernel writing to tty1 as well,
    which is the one on screen."""
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


def test_the_autostart_is_fenced_so_it_can_be_taken_out_again(tmp_path, commands):
    work = work_in(tmp_path)
    work.owner.home.mkdir(parents=True)
    profile = work.owner.home / setup.PROFILE
    profile.write_text("export EDITOR=vi\n", encoding="utf-8")

    setup.STEPS["autostart"](work)

    assert "cage -- /usr/bin/previous" in profile.read_text()

    setup.STEPS["no-autostart"](work)

    assert profile.read_text() == "export EDITOR=vi\n"


def test_an_autostart_that_is_already_there_is_not_written_twice(tmp_path, commands):
    work = work_in(tmp_path)
    work.owner.home.mkdir(parents=True)
    profile = work.owner.home / setup.PROFILE

    setup.STEPS["autostart"](work)
    once = profile.read_text()
    setup.STEPS["autostart"](work)

    assert profile.read_text() == once


def test_an_autostart_from_an_older_version_is_brought_up_to_date(tmp_path, commands):
    """The block is generated, so a machine set up a year ago carries a
    year-old console. The change that matters most is the one nobody would
    notice: the line that writes down a crash."""
    work = work_in(tmp_path)
    work.owner.home.mkdir(parents=True)
    profile = work.owner.home / setup.PROFILE
    profile.write_text(
        "export EDITOR=vi\n\n%s\nexec cage -- /usr/bin/previous\n%s\n"
        % (setup.AUTOSTART_OPENS, setup.AUTOSTART_CLOSES), encoding="utf-8")

    setup.STEPS["autostart"](work)
    written = profile.read_text()

    assert "exec cage" not in written
    assert "crashes" in written
    assert written.startswith("export EDITOR=vi\n")
    assert written.count(setup.AUTOSTART_OPENS) == 1


def test_bringing_it_up_to_date_can_be_undone(tmp_path, commands):
    """A later step that fails walks every one of them backwards, and this
    one has to leave the console the way it found it."""
    work = work_in(tmp_path)
    work.owner.home.mkdir(parents=True)
    profile = work.owner.home / setup.PROFILE
    was = ("export EDITOR=vi\n\n%s\nexec cage -- /usr/bin/previous\n%s\n"
           % (setup.AUTOSTART_OPENS, setup.AUTOSTART_CLOSES))
    profile.write_text(was, encoding="utf-8")

    work.at("autostart", 1)
    setup.STEPS["autostart"](work)
    work.reverse()

    assert profile.read_text() == was


def test_the_installer_and_this_write_the_same_autostart():
    """`install.sh` carries its own copy of these lines for `--update-admin`,
    which brings a console up to date without asking the helper for anything
    else. Two copies of one thing drift, and the drift would be a console that
    behaves differently depending on which of the two set the machine up. This
    is what says so.

    Character for character, comments included. Both sides replace a block that
    no longer says what they write, so a comment wrapped differently in the two
    is not cosmetic: it is the two rewriting each other every time a machine
    sees both, which is what happened while this compared only the lines that
    run.

    Compared as shell rather than as text. The installer writes its copy inside
    a heredoc, so every `$` in it is escaped and every backslash doubled, and it
    names paths by the variables it declared above. Both sides are put back into
    what the console will actually read, and then they have to be the same.
    """
    class Somebody:
        home = pathlib.Path("/home/next")

    installer = (pathlib.Path(__file__).resolve().parent.parent.parent
                 / "install.sh").read_text(encoding="utf-8")
    values = dict(re.findall(r'^readonly (\w+)="([^"]*)"$', installer, re.M))
    values["HOME"] = str(Somebody.home)

    def settled(text):
        """One variable at a time, until none is left: they are written in
        terms of each other, so HOLD_FILE is RUNTIME_DIR and a slash."""
        for _ in range(4):
            text = re.sub(r"\$\{(\w+)\}",
                          lambda found: values.get(found.group(1), found.group(0)),
                          text)
        return text

    block = re.search(r"(\$\{AUTOSTART_MARKER\}\n.*?\$\{AUTOSTART_END\})",
                      installer, re.S)
    assert block, "no autostart block in install.sh"
    theirs = settled(block.group(1).replace("\\$", "$").replace("\\\\", "\\"))
    ours = setup._autostart_block(Somebody()).strip("\n")

    assert theirs == ours


def test_an_installation_ends_with_the_machine_running(tmp_path, commands, monkeypatch):
    """Everything up to here leaves a machine that is installed and shows
    nothing, because the console has been at a login prompt since before any of
    it existed. So the console is restarted, and the hold that would stop it
    starting the emulator goes first."""
    monkeypatch.setattr(setup, "_the_guest_is_running", lambda: False)
    hold = tmp_path / "hold"
    hold.touch()
    monkeypatch.setattr(setup, "HOLD", str(hold))
    work = work_in(tmp_path)
    work.at("start", len(setup.JOBS["install"]))

    setup.STEPS["start"](work)

    assert not hold.exists()
    assert ["systemctl", "restart", work.settings.kiosk_unit] in commands
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


def test_the_emulator_comes_from_the_one_archive_it_comes_from():
    """Pinned so that only Previous comes from it, because that archive carries
    more than Previous and could otherwise replace packages of Debian's."""
    assert setup.REPOSITORY_URL.startswith("https://")
    assert setup.REPOSITORY_HOST in setup.REPOSITORY_URL


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
