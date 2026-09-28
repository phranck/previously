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

        def __call__(self, command, seconds=None):
            self.append(command)
            if command[0] in self.refuse:
                raise setup.Refused("setup.command-failed",
                                    command=command[0], code=1)
            return ""

    answer = Commands()
    monkeypatch.setattr(setup, "run", answer)
    monkeypatch.setattr(setup, "installed", lambda package: False)
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


def test_a_request_with_no_machine_gets_the_one_install_sh_writes():
    """The cube with the turbo board, so a machine set up through the browser
    and one set up through the script are the same machine."""
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


def test_what_it_is_doing_is_readable_whilst_it_runs(tmp_path, monkeypatch):
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

    assert "exec cage -- /usr/bin/previous" in profile.read_text()

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


def test_a_copy_is_not_taken_whilst_the_machine_runs(card, monkeypatch):
    """A copy taken whilst NeXTSTEP is writing is a torn file system: it looks
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


def test_nothing_is_put_back_whilst_the_machine_runs(card, monkeypatch):
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


def test_how_far_a_copy_has_got_is_readable_whilst_it_runs(card):
    """Two gigabytes on a card is minutes, so this is a window somebody leaves
    open and comes back to."""
    setup.carry_out(card)

    said = json.loads(
        (card.into / setup.PROGRESS).read_text(encoding="utf-8"))

    assert said["ok"] is True
    assert said["step"] == "copy"
    assert said["of"] == 1


# -- what may be fetched, and from where ----------------------------------


@pytest.mark.parametrize("newurl", [
    "https://example.com/x.7z",
    "http://archive.org/x.7z",
])
def test_a_redirect_off_the_archive_ends_the_fetch(newurl):
    """Whoever answers the first request chooses where the second one goes."""
    import urllib.error

    handler = setup._OnlyOurArchive()

    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(None, None, 302, "Found", {}, newurl)


def test_the_emulator_comes_from_the_one_archive_it_comes_from():
    """Pinned so that only Previous comes from it, because that archive carries
    more than Previous and could otherwise replace packages of Debian's."""
    assert setup.REPOSITORY_URL.startswith("https://")
    assert setup.REPOSITORY_HOST in setup.REPOSITORY_URL


# -- who owns what it writes ----------------------------------------------


def test_the_owner_is_read_out_of_the_service_unit(tmp_path, monkeypatch):
    """Rather than named a second time here. The unit is where it is decided,
    and a helper that disagreed with it would write into the wrong home."""
    import pwd

    me = pwd.getpwuid(os.getuid()).pw_name
    unit = tmp_path / "previously.service"
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
