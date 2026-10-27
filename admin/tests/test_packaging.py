"""The unit and the package, held against what the service expects of them.

Three files name the directory the saved configurations live in: the default in
`settings.py`, the `ReadWritePaths=` entry in the unit that lets the service
write there, and the `install` line in `postinst` that creates it. A machine
where those three disagree looks exactly like one where they agree, right up to
the first save, which then fails with a read only filesystem and a path nobody
was looking at. Nothing else here can catch that.
"""

import importlib.util
import pathlib
import re
import shutil
import struct
import subprocess
import types

import pytest

from previously import server
from previously.settings import DEFAULTS

#: Where the packaging lives, beside the service rather than inside it.
PACKAGING = pathlib.Path(__file__).resolve().parent.parent / "packaging"


#: The machine numbers an ELF header gives at byte 18, from elf.h: the Pi's
#: processor and a PC's.
EM_AARCH64 = 183
EM_X86_64 = 62


def elf_library(machine):
    """@returns bytes, the 64-byte header of a 64-bit little-endian shared
    library for that machine, which is all the build reads of one."""
    identity = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    return identity + struct.pack("<HH", 3, machine) + bytes(44)


@pytest.fixture(scope="module")
def build(tmp_path_factory):
    """`packaging/build.py`, imported by path.

    It is a script beside the package rather than a module of it, so there is
    nothing to import by name. What is wanted from it is the maintainer scripts
    it writes, which are constants in it.

    The library that shows Previous sharp is built in a container beside the
    source and not kept in the repository, so the build takes a stand-in for
    one built for the Pi.
    """
    spec = importlib.util.spec_from_file_location("build", PACKAGING / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    library = tmp_path_factory.mktemp("display") / "pixel-exact.so"
    library.write_bytes(elf_library(EM_AARCH64))
    module.SHARP_DISPLAY_BUILT = library
    return module


@pytest.fixture(scope="module")
def unit():
    """The service unit, as text."""
    return (PACKAGING / "previously.service").read_text(encoding="utf-8")


def where_they_live():
    """@returns str, the directory the configurations live in, under the home.

    Read off the one setting that decides it, so this test measures the other two
    against the service rather than against a value written down here.
    """
    configured = DEFAULTS["machines_file"]
    assert configured.startswith("~/"), configured
    return str(pathlib.PurePosixPath(configured[2:]).parent)


def test_the_setting_points_into_the_home():
    """Not under /var/lib, because a purge takes that away and the machines
    somebody built are theirs rather than this service's."""
    assert DEFAULTS["machines_file"].startswith("~/")
    assert not DEFAULTS["machines_file"].startswith("/var")


def test_the_unit_opens_the_directory_they_live_in(build):
    """ProtectHome leaves the home read only, so without this entry the first
    save fails and the file the service is configured with can never be written.
    The entries are in the owner file, because the home is the owner's.
    """
    postinst = build.scripts()["postinst"]

    assert where_they_live() in build.WRITABLE_IN_HOME
    assert "ReadWritePaths=-$home/" + where_they_live() in postinst


def test_the_owner_can_write_everywhere_the_service_writes(build):
    """Four places in the home, each read off what decides it: the emulator's
    configuration, the saved machines, the documents and the directory the
    emulator runs in. One missing is a write that fails with a read only
    filesystem on the day it is first tried."""
    from previously import setup

    def in_the_home(configured):
        return str(pathlib.PurePosixPath(configured[2:]))

    wanted = {
        str(pathlib.PurePosixPath(in_the_home(DEFAULTS["previous_config"])).parent),
        where_they_live(),
        in_the_home(DEFAULTS["documents"]),
        setup.WORK_DIRECTORY,
    }

    assert wanted == set(build.WRITABLE_IN_HOME)


def test_the_package_creates_that_directory(build):
    """systemd skips a ReadWritePaths entry whose path is absent, so the entry
    above is worth nothing until the directory exists. Nothing the service does
    can create it: by the time it runs, the home is already read only."""
    postinst = build.scripts()["postinst"]

    assert "install -d" in postinst
    assert where_they_live() in postinst


def test_the_package_makes_a_missing_config_directory_the_owners(build):
    """install makes a missing parent as root's. On an image the home has no
    ~/.config yet, and pi-gen then closes the first user's ~/.config to
    everybody but its owner, which left root holding it and Previous unable
    to read its own configuration on next4 on 24.10.2026."""
    postinst = build.scripts()["postinst"]

    parent = postinst.index('[ -d "$home/.config" ] || install -d -o "$owner" -g "$group"')

    assert parent < postinst.index('"$home/.config/%s"' % build.NAME)


def test_an_image_starts_the_console_again_once_cloud_init_is_through(build):
    """cloud-init renames the first user through userconf-pi, which ends in
    cancel-rename, and that starts getty@tty1 on its own, in a job of its own
    that pushed the console's start out of the first boot of an image on
    next4 on 24.10.2026. Started again after cloud-init and before the getty,
    the console's conflict stops the getty before it ever runs."""
    from previously import setup

    unit = (PACKAGING / build.FIRST_BOOT_UNIT).read_text(encoding="utf-8").splitlines()
    before = next(line for line in unit if line.startswith("Before=")).split("=", 1)[1].split()

    assert "ConditionFirstBoot=yes" in unit
    assert "ConditionPathExists=%s" % setup.CONSOLE_SWITCHED_ON in unit
    assert "After=cloud-init-network.service" in unit
    assert {setup.CONSOLE, setup.GETTY} <= set(before)
    assert "ExecStart=/usr/bin/systemctl --no-block start %s" % setup.CONSOLE in unit
    assert build.FIRST_BOOT_UNIT in build.UNIT_FILES
    assert build.FIRST_BOOT_UNIT in units_on(build.scripts()["postinst"], "enable")
    assert build.FIRST_BOOT_UNIT in build.scripts()["prerm"]


def test_the_package_runs_as_the_user_the_card_was_made_with(build):
    """The Imager asks for a user name and creates that user first, so it is
    the one with UID 1000, whatever it is called. A machine that already has an
    owner file keeps the user in it, so an upgrade never moves the tool into
    somebody else's home. No name of the package's own comes into it."""
    from previously import setup

    postinst = build.scripts()["postinst"]

    kept = postinst.index("/" + build.OWNER_FILE)
    first = postinst.index("getent passwd %d" % setup.FIRST_UID)

    assert kept < first
    assert not re.search(r"getent passwd [a-z]", build.FIND_OWNER)
    assert "User=$owner" in postinst
    assert "Group=$group" in postinst


def test_a_card_with_nobody_to_run_as_is_refused_before_anything_lands(build):
    """Before the files are unpacked rather than after, so a refusal leaves
    nothing half configured. The question is asked the same way in both
    scripts, because they are filled from one statement of it."""
    preinst = build.scripts()["preinst"]

    assert build.FIND_OWNER in preinst
    assert build.FIND_OWNER in build.scripts()["postinst"]
    assert 'if [ -z "$owner" ]' in preinst
    assert "exit 1" in preinst


def units_on(script, verb):
    """@returns set of str, the units a maintainer script hands
    `systemctl <verb>`, over every line that does."""
    found = set()
    for line in script.splitlines():
        named = re.match(r"^\s*systemctl %s (.+)$" % verb, line)
        if named:
            found.update(named.group(1).split())
    return found


def test_the_package_starts_nothing_where_systemd_does_not_run(build):
    """An image is set up in pi-gen's chroot, where systemd runs nothing and
    the systemctl of Raspberry Pi OS trixie refuses `enable --now` outright,
    which failed the package there. Everything is switched on, and started only
    where systemd runs the machine, as `setup.booted` asks it."""
    from previously import setup

    postinst = build.scripts()["postinst"]
    starting = re.search(r"^    if \[ -d (\S+) \]; then\n        systemctl start (.*)\n    fi$",
                         postinst, re.M)

    assert not re.search(r"^\s*systemctl .*--now", postinst, re.M)
    assert starting and starting.group(1) == str(setup.BOOTED)
    assert set(starting.group(2).split()) == {build.SERVICE, *build.WATCHERS}
    assert units_on(postinst, "enable") == {build.SERVICE, *build.WATCHERS,
                                            build.INITRAMFS_TIMER, build.OWNER_UNIT,
                                            build.FIRST_BOOT_UNIT}


def a_getent(tmp_path, users):
    """A getent that knows these users alone, by name and by UID.

    @param users - dict of name to UID.
    @returns pathlib.Path of the directory it is in, for the front of PATH.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    lines = "".join('  %s|%s) echo "%s:x:%d:%d::/home/%s:/bin/sh" ;;\n'
                    % (name, uid, name, uid, uid, name) for name, uid in users.items())
    getent = bin_dir / "getent"
    getent.write_text('#!/bin/sh\ncase "$2" in\n%s  *) exit 2 ;;\nesac\n' % lines,
                      encoding="utf-8")
    getent.chmod(0o755)
    return bin_dir


@pytest.mark.parametrize("written, users, expected", [
    ("[Service]\nUser=kept\n", {"chosen": 1000}, "kept"),
    ("", {"another": 1001, "chosen": 1000}, "chosen"),
    # The name phranck's own machines run under, which once came first.
    ("", {"next": 1001, "chosen": 1000}, "chosen"),
    ("", {}, ""),
])
def test_who_the_tool_runs_as(build, tmp_path, written, users, expected):
    """The statement itself, run by a shell, with getent answering for the
    users the case names and the owner file put somewhere a test can write.
    Another user beside the first one changes nothing, whatever it is
    called."""
    owner_file = tmp_path / "owner.conf"
    if written:
        owner_file.write_text(written, encoding="utf-8")

    snippet = build.FIND_OWNER.replace("/" + build.OWNER_FILE, str(owner_file))
    finished = subprocess.run(
        ["sh", "-c", snippet + 'printf "%s" "$owner"'],
        capture_output=True, text=True, check=True,
        env={"PATH": "%s:/usr/bin:/bin" % a_getent(tmp_path, users)})

    assert finished.stdout == expected


def test_the_service_never_starts_without_its_owner(unit, build):
    """The unit names nobody, so where the owner file is missing it would run
    as root. It does not start at all instead."""
    assert not re.search(r"^User=", unit, re.M)
    assert "ConditionPathExists=/" + build.OWNER_FILE in unit


def test_the_helper_reads_the_owner_where_the_package_writes_it(build):
    from previously import setup

    assert "/" + build.OWNER_FILE == str(setup.OWNER_FILE)


def test_the_owner_is_followed_before_the_service_and_the_console_start(build):
    """Raspberry Pi OS's cloud-init renames the first user before
    sysinit.target, and the service and the console run as the owner after
    basic.target, so a unit ordered before both finds the new name and points
    them at it before either starts."""
    from previously import setup

    unit = (PACKAGING / build.OWNER_UNIT).read_text(encoding="utf-8")
    before = re.search(r"^Before=(.*)$", unit, re.M).group(1).split()

    assert build.SERVICE in before
    assert setup.CONSOLE in before
    assert "ConditionPathExists=/" + build.OWNER_FILE in unit.splitlines()
    assert re.search(r'^ExecStart=/usr/bin/python3 -c '
                     r'"from previously import setup; setup\.follow_owner\(\)"$', unit, re.M)
    assert build.OWNER_UNIT in build.UNIT_FILES
    assert build.OWNER_UNIT in units_on(build.scripts()["postinst"], "enable")
    assert build.OWNER_UNIT in build.scripts()["prerm"]


@pytest.mark.parametrize("users, follows", [
    ({"chosen": 1000}, True),
    ({"kept": 1000}, False),
], ids=["renamed", "there"])
def test_python_starts_only_where_the_owner_has_gone(build, tmp_path, users, follows):
    """The unit stands in front of the service and the console at every boot,
    so the question is asked in the shell, and a boot whose owner is there
    starts no Python at all. systemd reads `$$` as one dollar sign."""
    unit = (PACKAGING / build.OWNER_UNIT).read_text(encoding="utf-8")
    condition = re.search(r"^ExecCondition=/bin/sh -c '(.*)'$", unit, re.M).group(1)
    owner_file = tmp_path / "owner.conf"
    owner_file.write_text("[Service]\nUser=kept\n", encoding="utf-8")

    finished = subprocess.run(
        ["sh", "-c", condition.replace("$$", "$").replace("/" + build.OWNER_FILE,
                                                          str(owner_file))],
        env={"PATH": "%s:/usr/bin:/bin" % a_getent(tmp_path, users)}, check=False)

    assert (finished.returncode == 0) is follows


def test_purging_removes_the_owner_file(build):
    postrm = build.scripts()["postrm"]
    purging = postrm[postrm.index('"$1" = purge'):]

    assert str(pathlib.PurePosixPath("/" + build.OWNER_FILE).parent) in purging


def test_purging_the_package_leaves_the_home_alone(build):
    """What it removes is what this service owns: its state directory and its own
    configuration. The configurations somebody saved are in their home, beside
    the emulator's configuration and the disk image, and removing this tool is
    not removing the machines they built with it."""
    for line in build.scripts()["postrm"].splitlines():
        if line.strip().startswith("rm -rf"):
            assert "/home" not in line, line
            assert "~" not in line, line


def test_every_unit_the_package_names_is_beside_it(build):
    """A unit named in the list and absent from the directory is a package that
    installs half of what it promises, and dpkg says nothing about it."""
    for unit in build.UNIT_FILES:
        assert (PACKAGING / unit).is_file(), unit


def test_the_package_switches_on_every_watcher_it_ships(build):
    """A path unit that is not enabled watches nothing, and the request it was
    meant to answer sits in the runtime directory for ever."""
    watching = {unit for unit in build.UNIT_FILES if unit.endswith(".path")}

    assert set(build.WATCHERS) == watching
    postinst = build.scripts()["postinst"]
    prerm = build.scripts()["prerm"]
    for unit in watching:
        assert unit in postinst, unit
        assert unit in prerm, unit


@pytest.mark.parametrize("action", ["reboot", "poweroff"])
def test_the_board_goes_down_without_a_wall_message(action):
    """systemd writes its wall message onto the console's tty1, where it stood
    over the boot picture for two seconds before a reboot on next4 on
    24.10.2026."""
    unit = (PACKAGING / ("previously-%s.service" % action)).read_text(encoding="utf-8")

    assert re.findall(r"^ExecStart=(.*)$", unit, re.M) == [
        "/usr/bin/systemctl --no-wall %s" % action]


def test_the_privileged_helper_watches_where_the_service_writes(build):
    """Three files have to agree about one path: the setting the service writes
    the request through, the `PathExists=` the watcher fires on, and the name
    the helper reads. A machine where they disagree looks exactly like one where
    they agree, right up to the first installation, which then never starts."""
    from previously import kiosk

    watching = (PACKAGING / "previously-setup.path").read_text(encoding="utf-8")
    wanted = "%s/%s" % (DEFAULTS["runtime_directory"], kiosk.SETUP_REQUEST)

    assert "PathExists=%s" % wanted in watching


def test_the_helper_keeps_what_it_wrote_after_it_stops(build):
    """The last thing it wrote is the answer to how the run went, and a runtime
    directory systemd empties when the unit stops takes that answer with it."""
    unit = (PACKAGING / "previously-setup.service").read_text(encoding="utf-8")

    assert "RuntimeDirectory=previously-setup" in unit
    assert "RuntimeDirectoryPreserve=yes" in unit


def test_the_helper_writes_where_the_service_reads(build):
    """Root's own directory rather than the service's, because a file root wrote
    into a directory an unprivileged user owns could be replaced by a link to
    somewhere else between one write and the next."""
    from previously import setup

    unit = (PACKAGING / "previously-setup.service").read_text(encoding="utf-8")
    named = DEFAULTS["setup_directory"]

    assert str(setup.OUR_DIRECTORY) == named
    assert "RuntimeDirectory=%s" % named.rsplit("/", 1)[-1] in unit
    assert named != DEFAULTS["runtime_directory"]


# -- the keyboard that reaches the emulator --------------------------------


def test_the_package_gives_the_virtual_keyboard_to_a_group(build, tmp_path):
    """/dev/uinput belongs to root alone until a rule says otherwise, and the
    service is not root."""
    build.lay_out(tmp_path / "tree")

    rule = (tmp_path / "tree" / build.UDEV_RULE).read_text(encoding="utf-8")
    lines = [line for line in rule.splitlines() if line and not line.startswith("#")]

    assert lines == ['KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="%s", MODE="0660", '
                     'OPTIONS+="static_node=uinput"' % build.UINPUT_GROUP]


def test_the_node_made_before_the_module_loads_gets_the_same_rights(build, tmp_path):
    """/dev/uinput is a static node until the module is loaded: made at boot by
    kmod-static-nodes with root's rights alone, and unknown to udev, so no rule
    reaches it. systemd gives its own static nodes their rights in tmpfiles as
    well, and so does this. Found on a Pi 4 and a Pi 5 on 23.10.2026, where
    the rule alone left the node at crw------- root root."""
    build.lay_out(tmp_path / "tree")

    entries = (tmp_path / "tree" / build.TMPFILES).read_text(encoding="utf-8")
    lines = [line for line in entries.splitlines() if line and not line.startswith("#")]

    assert lines == ["z /dev/uinput 0660 - %s -" % build.UINPUT_GROUP]


def test_the_service_runs_with_the_group_the_keyboard_belongs_to(build, unit):
    """The rule and the unit are two files, and this is what holds them to one
    group."""
    assert re.findall(r"^SupplementaryGroups=(\S+)", unit, re.M) == [build.UINPUT_GROUP]


def test_the_package_gives_the_node_its_rights_before_starting(build):
    """/dev/uinput was made at boot, before the rule and the entry were there,
    and the service opens it as soon as it starts."""
    postinst = build.scripts()["postinst"]

    given = postinst.index("systemd-tmpfiles --create /" + build.TMPFILES)
    reloaded = postinst.index("udevadm control --reload-rules")

    assert given < postinst.index("systemctl start")
    assert reloaded < postinst.index("systemctl start")


def test_the_package_needs_neither_xdotool_nor_imagemagick(build):
    assert "xdotool" not in build.DEPENDS
    assert "imagemagick" not in build.DEPENDS


def test_the_service_binds_nothing_from_tmp(unit):
    """Its keys go through the kernel now, so the X server's socket is none of
    its business."""
    assert not re.findall(r"^BindReadOnlyPaths=", unit, re.M)


def pixels_of(cursor):
    """@param cursor - bytes of an Xcursor file.
    @returns list of int, the ARGB pixels of its one image.

    Read as libXcursor's format lays it out: a header with the number of table
    entries, the table naming each chunk's type and position, and an image
    chunk with its own header before the pixels.
    """
    magic, header, _, entries = struct.unpack_from("<4sIII", cursor)
    assert magic == b"Xcur" and entries == 1
    kind, _, position = struct.unpack_from("<III", cursor, header)
    assert kind == 0xFFFD0002, "the one entry is an image"
    chunk, _, _, _, width, height = struct.unpack_from("<6I", cursor, position)
    return list(struct.unpack_from("<%dI" % (width * height), cursor, position + chunk))


def test_the_package_brings_a_pointer_nobody_sees(build, tmp_path):
    """cage sets its own pointer whenever a mouse arrives, and it then stands
    beside NeXTSTEP's, which draws its pointer itself. The theme cage loads its
    pointer from holds a transparent pixel under both names cage asks for."""
    build.lay_out(tmp_path)
    theme = tmp_path / build.CURSORS / "default" / "cursors"

    for name in ("left_ptr", "default"):
        pixels = pixels_of((theme / name).read_bytes())
        assert pixels and all(pixel >> 24 == 0 for pixel in pixels), name


def test_the_console_and_the_package_name_the_same_pointer_theme(build):
    from previously import setup

    assert "/" + build.CURSORS == setup.CURSORS


def test_the_package_puts_the_sharp_display_library_where_the_console_loads_it(build, tmp_path):
    from previously import setup

    build.lay_out(tmp_path)

    assert ((tmp_path / setup.SHARP_DISPLAY.lstrip("/")).read_bytes()
            == build.SHARP_DISPLAY_BUILT.read_bytes())


def test_the_package_takes_no_library_built_for_another_processor(build, tmp_path, monkeypatch):
    """A library the Pi cannot load is passed over by the loader with a line in
    the journal, so the picture would be soft again without anybody seeing why.
    A build on a PC makes exactly such a library."""
    elsewhere = tmp_path / "pixel-exact.so"
    elsewhere.write_bytes(elf_library(EM_X86_64))
    monkeypatch.setattr(build, "SHARP_DISPLAY_BUILT", elsewhere)

    with pytest.raises(SystemExit, match="arm64"):
        build.lay_out(tmp_path / "package")


def test_the_package_takes_no_missing_library(build, tmp_path, monkeypatch):
    monkeypatch.setattr(build, "SHARP_DISPLAY_BUILT", tmp_path / "absent.so")

    with pytest.raises(SystemExit, match="display/build.sh"):
        build.lay_out(tmp_path / "package")


def test_the_package_is_for_the_machines_the_setup_installs_onto(build):
    """It carries a library compiled for the Pi, and the setup refuses any
    other machine already."""
    from previously import setup

    assert build.ARCHITECTURE == setup.ARCHITECTURE


def test_the_package_brings_the_x_server_previous_draws_through(build):
    """The console tells Previous to draw through X first, and cage starts an
    X server only where Xwayland is installed. The cage in the Raspberry Pi
    archive does not bring it along, so the package does."""
    assert "xwayland" in build.DEPENDS


# -- the boot picture ----------------------------------------------------


def test_the_package_carries_the_pictures_pixel_for_pixel(build, tmp_path):
    """Each TGA is written from the PNG design/mark.py fetches, and the drawer
    reads it back. Every pixel has to arrive as the PNG holds it, turned from
    red, green and blue into the blue, green and red a TGA stores."""
    from previously import png, splash

    build.lay_out(tmp_path / "tree")
    for tga, source in build.SPLASHES.items():
        width, height, pixels = splash.picture((tmp_path / "tree" / tga).read_bytes())
        wide, high, lines = png.rgb(source.read_bytes())

        assert (width, height) == (wide, high), tga
        turned = b"".join(bytes(line[at + 2 - channel] for at in range(0, len(line), 3)
                                for channel in range(3)) for line in lines)
        assert pixels == turned, tga


def test_the_drawer_reads_the_pictures_where_the_package_puts_them(build, monkeypatch):
    """For every board the service knows, both pictures are where the drawer
    looks on that board."""
    from previously import hardware, splash

    for board in set(hardware.BOARDS.values()):
        monkeypatch.setattr(splash.hardware, "board", lambda board=board: board)
        for kind in splash.KINDS:
            assert str(splash.picture_of(kind)).lstrip("/") in build.SPLASHES, (board, kind)


def test_the_package_has_both_pictures_for_every_board_the_service_knows(build):
    """previous.li draws them for the boards its own site/splash.py names, and
    it cannot read hardware.BOARDS, so this is what holds the two lists to one
    another. A board without its pictures would leave the package build without
    a file to turn into a TGA."""
    from previously import hardware, splash

    for board in set(hardware.BOARDS.values()):
        for kind in splash.KINDS:
            assert (PACKAGING / (splash.stem(kind, board) + ".png")).is_file(), (board, kind)
    assert splash.FALLBACK_BOARD in hardware.BOARDS.values()


def test_the_shutdown_picture_is_drawn_after_the_console_has_stopped(build):
    """systemd stops units in the reverse of the order it started them, so a
    unit ordered before the console stops after it, once cage has given the
    screen back. The console wants it, which is what starts it at all."""
    from previously import setup

    unit = (PACKAGING / build.SHUTDOWN_SPLASH_UNIT).read_text(encoding="utf-8").splitlines()
    owner = types.SimpleNamespace(name="next", uid=1000, home=pathlib.Path("/home/next"))
    console = setup._console_unit(owner)
    wants = re.search(r"^Wants=(.*)$", console, re.M).group(1).split()

    assert build.SHUTDOWN_SPLASH_UNIT == setup.SHUTDOWN_PICTURE
    assert setup.SHUTDOWN_PICTURE in wants
    assert "Before=%s" % setup.CONSOLE in unit
    assert "RemainAfterExit=yes" in unit
    assert "ExecStop=-/usr/bin/python3 -m previously.splash fb0 shutdown" in unit
    assert build.SHUTDOWN_SPLASH_UNIT in build.UNIT_FILES


def test_every_framebuffer_that_appears_gets_the_picture(build, tmp_path):
    """By its name rather than by its path, because vc4's framebuffer sits at
    /sys/devices/platform/gpu on a Pi 4 and at /sys/devices/platform/axi/axi:gpu
    on a Pi 5, read on 24.10.2026. The firmware's is left out: vc4 replaced it
    within a second on next4, and the picture drawn there flashed up and went
    before the one that stays."""
    build.lay_out(tmp_path / "tree")
    rule = (tmp_path / "tree" / build.SPLASH_RULE).read_text(encoding="utf-8")
    lines = [line for line in rule.splitlines() if line and not line.startswith("#")]

    assert lines == ['ACTION=="add", SUBSYSTEM=="graphics", KERNEL=="fb[0-9]*", '
                     'ATTR{name}!="simple", TAG+="systemd", '
                     'ENV{SYSTEMD_WANTS}+="previously-splash@%k.service"']
    assert build.SPLASH_UNIT == "previously-splash@.service"
    assert build.SPLASH_UNIT in build.UNIT_FILES


def test_the_picture_is_drawn_only_where_the_console_is_switched_on(build):
    """A machine whose console was taken away again shows its login prompt, and
    a picture over it would stand there for good. The condition is the link
    `systemctl enable` makes for the console, so the two name one place."""
    from previously import setup

    unit = (PACKAGING / build.SPLASH_UNIT).read_text(encoding="utf-8")
    owner = types.SimpleNamespace(name="next", uid=1000, home=pathlib.Path("/home/next"))
    console = setup._console_unit(owner)

    assert re.search(r"^WantedBy=multi-user\.target$", console, re.M)
    assert setup.CONSOLE_SWITCHED_ON == (setup.SYSTEM_UNITS / "multi-user.target.wants"
                                         / setup.CONSOLE)
    assert "ConditionPathExists=%s" % setup.CONSOLE_SWITCHED_ON in unit.splitlines()


def test_the_drawer_runs_as_nobody_in_particular(build):
    """It writes the framebuffer and nothing else, and the framebuffer belongs
    to the video group."""
    unit = (PACKAGING / build.SPLASH_UNIT).read_text(encoding="utf-8")

    assert "DynamicUser=yes" in unit.splitlines()
    assert "SupplementaryGroups=video" in unit.splitlines()
    assert not re.search(r"^User=", unit, re.M)


# -- the boot picture from the initramfs ------------------------------------


def test_initramfs_tools_finds_what_the_package_brings(build, tmp_path):
    """initramfs-tools(7) reads hooks from /usr/share/initramfs-tools/hooks and
    boot scripts from /usr/share/initramfs-tools/scripts, which is the part of
    it that belongs to packages. local-bottom runs once the root is mounted."""
    build.lay_out(tmp_path / "tree")

    for path, directory in ((build.INITRAMFS_HOOK, "usr/share/initramfs-tools/hooks/"),
                            (build.INITRAMFS_SCRIPT,
                             "usr/share/initramfs-tools/scripts/local-bottom/")):
        assert path.startswith(directory)
        assert (tmp_path / "tree" / path).stat().st_mode & 0o111, path


def hook_run(build, tmp_path, with_vc4):
    """Runs the package's hook as mkinitramfs would, with hook-functions and
    python3 standing in for the real ones.

    @param with_vc4 - Whether the kernel the initramfs is built for has vc4.
    @returns (str, str): what force_load was asked for, and what python3 was
      run with, its PYTHONPATH first.
    """
    build.lay_out(tmp_path / "tree")
    destination = tmp_path / "initramfs"
    destination.mkdir()
    modules = tmp_path / "modules"
    (modules / "kernel" / "drivers" / "gpu" / "drm" / "vc4").mkdir(parents=True)
    if with_vc4:
        (modules / "kernel" / "drivers" / "gpu" / "drm" / "vc4" / "vc4.ko.xz").touch()
    functions = tmp_path / "hook-functions"
    functions.write_text('force_load() { echo "$@" >> "%s/loaded"; }\n' % tmp_path,
                         encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python3"
    python.write_text('#!/bin/sh\necho "$PYTHONPATH $*" > "%s/python"\n' % tmp_path,
                      encoding="utf-8")
    python.chmod(0o755)

    hook = (tmp_path / "tree" / build.INITRAMFS_HOOK).read_text(encoding="utf-8")
    subprocess.run(["sh", "-c", hook.replace(build.HOOK_FUNCTIONS, str(functions))],
                   check=True, env={"PATH": "%s:/usr/bin:/bin" % bin_dir,
                                    "DESTDIR": str(destination),
                                    "MODULESDIR": str(modules), "version": "6.18"})
    loaded = tmp_path / "loaded"
    return (loaded.read_text(encoding="utf-8").strip() if loaded.exists() else "",
            (tmp_path / "python").read_text(encoding="utf-8").strip())


def test_the_initramfs_brings_vc4_up_and_lays_the_picture_out(build, tmp_path):
    """vc4 is loaded in the initramfs, which on next5 on 24.10.2026 had it take
    the screen at 0.99 s rather than at 3.60 s, and the picture is laid out
    for the screen as it is, into the place the script draws it from."""
    loaded, python = hook_run(build, tmp_path, with_vc4=True)

    assert loaded == "vc4"
    assert python == "/%s -m previously.splash fb0 --into %s%s" % (
        build.LIB, tmp_path / "initramfs", build.INITRAMFS_PICTURE)


def test_an_initramfs_for_a_kernel_without_vc4_is_built_all_the_same(build, tmp_path):
    """A kernel that is not a Raspberry Pi's has no vc4, and asking for it
    would fail the whole initramfs."""
    loaded, _ = hook_run(build, tmp_path, with_vc4=False)

    assert loaded == ""


#: What the screen was when the frame was laid out, in the four fields the
#: script reads from sysfs.
LAID_OUT_FOR = {"virtual_size": "4,2", "bits_per_pixel": "32", "stride": "16",
                "pan": "0,0"}

#: What /proc/device-tree/compatible holds on a Pi 5 and on a Pi 4: the names
#: one after another, each ending in a null.
A_PI_5 = b"raspberrypi,5-model-b\0brcm,bcm2712\0"
A_PI_4 = b"raspberrypi,4-model-b\0brcm,bcm2711\0"


def bottom_run(build, tmp_path, console=True, name="vc4drmfb", screen=None,
               laid_out=True, booted_on=A_PI_5):
    """Runs the package's script in local-bottom against a root, a sysfs, a
    device tree and a framebuffer that are files in the test's directory.

    @param console - Whether the root has the console switched on.
    @param name - What sysfs calls fb0.
    @param screen - What sysfs says fb0 is, LAID_OUT_FOR where left out, and
      False where there is no fb0 at all.
    @param laid_out - Whether the initramfs carries a frame at all. One that
      does was laid out on a Pi 5.
    @param booted_on - What the device tree of the board it boots says.
    @returns (bytes, str, bool): what fb0 holds afterwards, what the script
      wrote into the kernel's log, and whether it left word that the initramfs
      wants building again.
    """
    from previously import hardware, setup, splash

    root = tmp_path / "root"
    if console:
        link = root / str(setup.CONSOLE_SWITCHED_ON).lstrip("/")
        link.parent.mkdir(parents=True)
        # Absolute, as `systemctl enable` makes it, and so pointing nowhere from
        # inside the initramfs.
        link.symlink_to(setup.SYSTEM_UNITS / setup.CONSOLE)
    picture = tmp_path / "picture"
    picture.mkdir()
    if laid_out:
        (picture / splash.FRAME).write_bytes(b"the boot picture")
        var = [0] * 40
        var[0:4] = [4, 2, 4, 2]
        var[6] = 32
        var[8:16] = [16, 8, 0, 8, 8, 0, 0, 8]
        fix = splash.FIX_SCREENINFO.pack(b"vc4drmfb", 0, 32, 0, 0,
                                         splash.FB_VISUAL_TRUECOLOR, 0, 0, 0, 16,
                                         0, 0, 0, 0, 0, 0)
        (picture / splash.GEOMETRY).write_text(
            splash.geometry(splash.Screen(splash.VAR_SCREENINFO.pack(*var), fix)),
            encoding="utf-8")
        (picture / splash.BOARD).write_bytes(A_PI_5)
    sysfs = tmp_path / "sys"
    sysfs.mkdir()
    if screen is not False:
        for field, value in {"name": name, **(screen or LAID_OUT_FOR)}.items():
            (sysfs / field).write_text(value + "\n", encoding="utf-8")
    tree = tmp_path / "compatible"
    tree.write_bytes(booted_on)
    device = tmp_path / "fb0"
    device.write_bytes(b"what the console left")
    log = tmp_path / "kmsg"
    log.touch()
    stale = tmp_path / "run" / "stale"
    stale.parent.mkdir()

    script = (tmp_path / "tree" / build.INITRAMFS_SCRIPT).read_text(encoding="utf-8")
    for constant, here in ((build.SCREEN, sysfs), (build.INITRAMFS_PICTURE, picture),
                           (build.SCREEN_DEVICE, device), (build.KERNEL_LOG, log),
                           (str(hardware.COMPATIBLE), tree), (build.STALE, stale)):
        assert script.count("=%s\n" % constant) == 1, constant
        script = script.replace("=%s\n" % constant, "=%s\n" % here)
    subprocess.run(["sh", "-c", script], check=True,
                   env={"PATH": "/usr/bin:/bin", "rootmnt": str(root)})
    return device.read_bytes(), log.read_text(encoding="utf-8"), stale.exists()


@pytest.fixture
def laid_out_tree(build, tmp_path):
    build.lay_out(tmp_path / "tree")


def test_the_initramfs_draws_the_picture_once_the_root_is_mounted(
        build, tmp_path, laid_out_tree):
    """Read as sysfs gives it and compared with what splash.geometry wrote, so
    the two say a screen the same way, on the board the frame was laid out on.
    The kernel's log says so at its info level, which no console level of this
    boot lets onto the screen."""
    shown, logged, stale = bottom_run(build, tmp_path)

    assert shown == b"the boot picture"
    assert logged.startswith("<6>previously: ")
    assert not stale


@pytest.mark.parametrize("case", [
    {"console": False},
    {"name": "simple"},
    {"screen": False},
], ids=["console off", "the firmware's", "no screen"])
def test_the_initramfs_leaves_the_screen_alone(build, tmp_path, laid_out_tree, case):
    """Where the console is off, previously-splash@.service draws nothing
    either and the login prompt comes, and a picture over it would stand there.
    Where fb0 is still the firmware's, vc4 is about to take the screen. Where
    there is no screen, there is nothing to lay a picture out for, and building
    the initramfs again would find nothing either."""
    assert bottom_run(build, tmp_path, **case) == (b"what the console left", "", False)


@pytest.mark.parametrize("case", [
    {"screen": {**LAID_OUT_FOR, "virtual_size": "8,2"}},
    {"screen": {**LAID_OUT_FOR, "pan": "0,2"}},
    {"laid_out": False},
    {"booted_on": A_PI_4},
], ids=["another screen", "panned", "no frame", "another board"])
def test_the_initramfs_asks_to_be_built_again_where_its_picture_does_not_fit(
        build, tmp_path, laid_out_tree, case):
    """The frame would land torn or show another board's picture, so the
    drawer systemd starts draws instead, and the word left in /run has the
    initramfs built again for the screen and the board there are. On next5 on
    24.10.2026 a monitor plugged in after the boot made fb0 1024 by 768, where
    the boot makes it 1024 by 600."""
    assert bottom_run(build, tmp_path, **case) == (b"what the console left", "", True)


def test_the_initramfs_is_built_again_once_the_emulator_has_booted(build):
    """Two minutes after the boot, by which time the emulator has started and
    fb0 has the size the boot gave it, at the lowest priority, and only where
    the script left word, so a board whose picture fits does nothing. %v is
    the running kernel's release, as `uname -r` says it (systemd.unit(5))."""
    service = (PACKAGING / build.INITRAMFS_UNIT).read_text(encoding="utf-8").splitlines()
    timer = (PACKAGING / build.INITRAMFS_TIMER).read_text(encoding="utf-8").splitlines()

    assert "ConditionPathExists=%s" % build.STALE in service
    assert "ExecStart=/usr/sbin/update-initramfs -u -k %v" in service
    assert "Nice=19" in service
    assert "IOSchedulingClass=idle" in service
    assert "OnBootSec=2min" in timer
    assert "WantedBy=timers.target" in timer
    assert {build.INITRAMFS_UNIT, build.INITRAMFS_TIMER} <= set(build.UNIT_FILES)
    assert build.INITRAMFS_TIMER in units_on(build.scripts()["postinst"], "enable")
    assert build.INITRAMFS_TIMER in build.scripts()["prerm"]


def test_the_initramfs_asks_what_the_drawer_asks(build, tmp_path, laid_out_tree):
    """The console's link on the root, which is the condition
    previously-splash@.service starts on, so the two draw on the same
    machines."""
    from previously import setup

    script = (tmp_path / "tree" / build.INITRAMFS_SCRIPT).read_text(encoding="utf-8")

    assert "${rootmnt}%s" % setup.CONSOLE_SWITCHED_ON in script


def test_the_package_builds_the_initramfs_of_the_kernel_the_board_runs(build):
    """initramfs-tools' own trigger runs `update-initramfs -u`, which builds the
    newest kernel's alone, and on Raspberry Pi OS that is 6.18.50+rpt-rpi-v8,
    the Pi 4's, on a Pi 5 as well (`linux-version sort` on next5 on
    24.10.2026). On removal it is built again without the hook, which has gone
    with the package."""
    postinst = build.scripts()["postinst"]
    postrm = build.scripts()["postrm"]
    built = 'update-initramfs -u -k "$(uname -r)" || true'

    assert postinst.index("refresh_console") < postinst.index(built)
    assert postinst.index(built) < postinst.index("systemctl enable")
    removing = re.search(r'^if \[ "\$1" = remove \]; then\n(.*?)^fi$', postrm, re.M | re.S)
    assert removing and built in removing.group(1)


def test_the_package_brings_the_console_up_to_date(build, tmp_path):
    """On every install and upgrade, whichever way the package arrived, with
    the helper module the package has just put in place and for the user it
    has just written down."""
    build.lay_out(tmp_path)
    postinst = build.scripts()["postinst"]

    found = re.search(r"PYTHONPATH=(\S+) python3 -c '(.*?)' \"\$owner\"", postinst,
                      re.S)
    assert found, "postinst does not bring the console up to date"
    where, program = found.groups()
    assert (tmp_path / where.lstrip("/") / "previously" / "setup.py").is_file()
    assert "setup.refresh_console(setup.Owner(sys.argv[1]))" in program
    assert postinst.index("User=$owner") < found.start()


def test_the_package_leaves_out_what_this_version_leaves_out(build):
    """On every install and upgrade, in a program of its own, so a machine set
    up before starts as lean as a new one and a unit that cannot be switched
    off holds nothing else back."""
    postinst = build.scripts()["postinst"]

    programs = re.findall(r"python3 -c '(.*?)' \"\$owner\"", postinst, re.S)
    services = [program for program in programs
                if "setup.refresh_services(setup.Owner(sys.argv[1]))" in program]

    assert len(services) == 1, "postinst does not leave out what this version leaves out"
    assert "refresh_console" not in services[0]


def test_the_package_brings_the_emulator_configuration_up_to_date(build):
    """On every install and upgrade, so a machine set up before Previous was
    told where to write its grabs stops leaving them in the home. A program of
    its own, so a console that cannot be brought up to date does not hold the
    configuration back."""
    postinst = build.scripts()["postinst"]

    programs = re.findall(r"python3 -c '(.*?)' \"\$owner\"", postinst, re.S)
    configuration = [
        program for program in programs
        if "setup.refresh_configuration(setup.Owner(sys.argv[1]))" in program]

    assert len(configuration) == 1, "postinst does not bring the configuration up to date"
    assert "refresh_console" not in configuration[0]
    assert postinst.index("User=$owner") < postinst.index("refresh_configuration")


# -- the archive Previous comes from -------------------------------------


#: The key that signs the Window Maker Live archive, as gpg names it. apt takes
#: an index from the archive or from its copy only with this signature on it.
ARCHIVE_FINGERPRINT = "C40423E642122B755120F8CC963E4C2E2B830BAD"


def test_the_package_carries_the_key_that_signs_the_archive(build, tmp_path):
    """Carried rather than fetched, because a network that cannot reach the
    archive cannot reach its key either. Checked with gpg where it is here,
    because what makes a key this one is its fingerprint."""
    from previously import setup

    gpg = shutil.which("gpg")
    if gpg is None:
        pytest.skip("gpg is not on this machine")

    build.lay_out(tmp_path / "tree")
    carried = (tmp_path / "tree" / build.LIB / build.NAME
               / setup.REPOSITORY_KEY_SHIPPED.name)
    keyring = tmp_path / "gnupg"
    keyring.mkdir(mode=0o700)
    said = subprocess.run(
        [gpg, "--homedir", str(keyring), "--show-keys", "--with-colons",
         str(carried)],
        capture_output=True, text=True, check=True).stdout

    fingerprints = [line.split(":")[9] for line in said.splitlines()
                    if line.startswith("fpr:")]
    assert ARCHIVE_FINGERPRINT in fingerprints


def test_the_package_brings_the_archive_source_up_to_date(build):
    """On every install and upgrade, so a machine whose archive stops
    answering reaches the copy as soon as the tool is updated. A program of
    its own, so a console that cannot be brought up to date does not hold the
    source back."""
    postinst = build.scripts()["postinst"]

    programs = re.findall(r"python3 -c '(.*?)'", postinst, re.S)
    archive = [program for program in programs
               if "setup.refresh_archive()" in program]

    assert len(archive) == 1, "postinst does not bring the archive source up to date"
    assert "refresh_console" not in archive[0]


def test_the_package_keeps_a_quiet_boot_quiet(build):
    """On every install and upgrade, so a board made quiet before the kernel's
    console level was held keeps the kernel's messages off its screen. A
    program of its own, so a console that cannot be brought up to date does not
    hold it back."""
    postinst = build.scripts()["postinst"]

    programs = re.findall(r"python3 -c '(.*?)'", postinst, re.S)
    quiet = [program for program in programs if "setup.refresh_quiet()" in program]

    assert len(quiet) == 1, "postinst does not keep a quiet boot quiet"
    assert "refresh_console" not in quiet[0]


# -- swap ----------------------------------------------------------------


def test_the_package_keeps_swap_off_the_card(build, tmp_path):
    """rpi-swap's default keeps a file of up to two gigabytes on the card for
    swap, which on an eight gigabyte card is the room a system's disk needs.
    The package sets a mechanism without a file, and it is one the helper
    counts on giving that room back at the next boot, so the two cannot say
    different things about the same card."""
    from previously import setup

    build.lay_out(tmp_path / "tree")
    written = (tmp_path / "tree" / build.SWAP).read_text(encoding="utf-8")
    mechanism = re.search(r"^Mechanism=(\S+)$", written, re.M)

    assert build.SWAP.startswith("usr/lib/rpi/swap.conf.d/")
    assert build.SWAP.endswith(".conf")
    assert re.search(r"^\[Main\]$", written, re.M)
    assert mechanism and mechanism.group(1) in setup.WITHOUT_A_FILE


# -- the login behind the Terminal ---------------------------------------


def test_the_terminal_may_log_in_with_a_password_over_the_loopback(build, tmp_path):
    """The Terminal's SSH client offers a password and nothing else, and
    Raspberry Pi Imager's choice of keys alone has cloud-init write
    `PasswordAuthentication no` for every address, which refused every login
    with "Permission denied (publickey)" on next4 and next5 on 27.10.2026. A
    Match block in a drop-in ends with its file (sshd -T on OpenSSH 10.0 on
    next5), so the network stays as the Imager left it."""
    from previously import terminal

    build.lay_out(tmp_path / "tree")
    written = (tmp_path / "tree" / build.SSHD_DROP_IN).read_text(encoding="utf-8")
    lines = [line.strip() for line in written.splitlines()
             if line.strip() and not line.startswith("#")]

    assert build.SSHD_DROP_IN.startswith("etc/ssh/sshd_config.d/")
    assert build.SSHD_DROP_IN.endswith(".conf")
    assert lines[0].startswith("Match Address ")
    assert terminal.SSH_HOST in lines[0].split(" ", 2)[2].split(",")
    assert lines[1:] == ["PasswordAuthentication yes"]


def test_sshd_reads_the_drop_in_when_it_comes_and_when_it_goes(build, tmp_path):
    """sshd reads its configuration when it starts and when it is reloaded,
    so a drop-in nobody reloads it for changes nothing until the next boot.
    It is not a conffile, so removing the package takes it away as well, and
    the loopback is closed to passwords again."""
    postinst = build.scripts()["postinst"]
    postrm = build.scripts()["postrm"]
    reloaded = "systemctl try-reload-or-restart %s || true" % build.SSHD_UNIT
    build.lay_out(tmp_path / "tree")
    build.write_control(tmp_path / "tree")
    conffiles = (tmp_path / "tree" / "DEBIAN" / "conffiles").read_text(encoding="utf-8")

    assert reloaded in postinst
    removing = re.search(r'^if \[ "\$1" = remove \]; then\n(.*?)^fi$', postrm, re.M | re.S)
    assert removing and reloaded in removing.group(1)
    assert "/" + build.SSHD_DROP_IN not in conffiles.splitlines()


# -- which build a package is --------------------------------------------


def test_the_package_is_called_what_the_update_looks_for(build):
    """Two places name it: the build, which writes it into the control file, and
    the module that asks dpkg what is installed and hands `apt-get` a file. They
    cannot be derived from one another, because one runs on a laptop and the other
    on the Pi, so this is what holds them together. A disagreement would leave the
    Raspberry Pi window asking about a package that is not there, finding no
    version, and offering no update to anybody, for ever and without a word."""
    from previously import release

    assert build.NAME == release.PACKAGE


def test_the_asset_a_release_carries_is_the_one_the_update_fetches(build):
    """The workflows rename the versioned package the build writes to one fixed
    name, so that a single address is always the newest one. Four places name
    it, and a fifth would be one too many: the workflow that attaches it, the
    one that puts it into the image, the script that installs onto a fresh
    machine, and the module the tool's own update fetches it with. The name
    does not follow the package's architecture, because every installed
    version fetches exactly this name."""
    from previously import release

    workflows = PACKAGING.parent.parent / ".github" / "workflows"
    script = (PACKAGING.parent.parent / "install.sh").read_text(encoding="utf-8")
    built = "%s_*_%s.deb" % (build.NAME, build.ARCHITECTURE)

    for name in ("release.yml", "image.yml"):
        workflow = (workflows / name).read_text(encoding="utf-8")
        assert built in workflow, name
        assert release.ASSET in workflow, name
    assert release.ASSET in script


def test_the_image_names_the_copy_of_cmdline_the_setup_keeps():
    """pi-gen fills the root partition into cmdline.txt alone, and the image's
    own step fills it into the copy the setup keeps for the remove job. A copy
    of another name would keep ROOTDEV and not boot once it is put back."""
    from previously import setup

    repository = PACKAGING.parent.parent
    step = (repository / "image" / "export-image" / "04-set-partuuid-previously"
            / "00-run.sh").read_text(encoding="utf-8")
    copy = setup.CMDLINE.with_suffix(setup.CMDLINE.suffix + setup.BACKUP)

    assert 'backup="${ROOTFS_DIR}%s"' % copy in step
    assert '"${ROOTFS_DIR}%s"' % setup.CMDLINE in step


def test_the_release_is_read_off_the_service(build):
    """One place holds it, and the package is numbered from there rather than
    from a second copy that would drift."""
    assert build.release() == server.RELEASE


def test_a_tagged_release_is_itself(build):
    """Nothing added, because there is nothing to tell apart: this is the
    release."""
    assert build.version_from("1.0.0", "v1.0.0-0-g2f250d5") == "1.0.0"


def test_a_build_after_the_release_stands_above_it(build):
    """The count rises with every commit, so dpkg can order two builds, and
    the commit says which tree each of them was."""
    assert build.version_from("1.0.0", "v1.0.0-42-g2f250d5") == "1.0.0+42.g2f250d5"


def test_a_build_on_the_way_to_a_release_stands_below_it(build):
    """The source already says 1.0.0 while the newest tag is still the release
    before it, so this is a build towards 1.0.0 rather than after it."""
    assert build.version_from("1.0.0", "v0.1.3-42-g2f250d5") == "1.0.0~42.g2f250d5"


def test_an_uncommitted_change_is_named(build):
    """A package that claims a commit it was not built from is worse than one
    that says nobody can look it up."""
    assert build.version_from("1.0.0", "v1.0.0-0-g2f250d5.modified") \
        == "1.0.0+0.g2f250d5.modified"
    assert build.version_from("1.0.0", "v1.0.0-7-g2f250d5.modified") \
        == "1.0.0+7.g2f250d5.modified"


@pytest.mark.parametrize("description", ["", "not what git says", "v1.0.0"])
def test_a_tree_git_cannot_describe_is_the_bare_release(build, description):
    """A checkout with no git, no tags, or an answer this does not know is a
    build nobody can trace, and saying so by carrying no commit is honest."""
    assert build.version_from("1.0.0", description) == "1.0.0"


def test_the_versions_are_ordered_the_way_they_are_meant_to_be(build):
    """The whole reason for the count and for which separator is used. Checked
    with dpkg itself where it is here, because the ordering is its rule rather
    than ours."""
    dpkg = shutil.which("dpkg")
    if dpkg is None:
        pytest.skip("dpkg is not on this machine")

    towards = build.version_from("1.0.0", "v0.1.3-42-g2f250d5")
    release = build.version_from("1.0.0", "v1.0.0-0-g2f250d5")
    after = build.version_from("1.0.0", "v1.0.0-7-g2f250d5")
    later = build.version_from("1.0.0", "v1.0.0-12-g9ab3f01")

    for older, newer in [(towards, release), (release, after), (after, later)]:
        finished = subprocess.run(
            [dpkg, "--compare-versions", older, "lt", newer], check=False)
        assert finished.returncode == 0, "%s should sort below %s" % (older, newer)


def test_the_package_carries_the_version_it_was_built_as(build, tmp_path):
    """Otherwise the window that shows the version still cannot tell two builds
    apart, which is the whole point of having one."""
    build.lay_out(tmp_path / "tree")

    kept = (tmp_path / "tree" / build.LIB / build.NAME / build.VERSION_FILE)

    assert kept.read_text(encoding="utf-8").strip() == build.package_version()


def test_the_service_reports_what_the_package_says(tmp_path, monkeypatch):
    """The file is read beside the modules rather than passed in, because the
    service is started by systemd and has nothing to pass it."""
    monkeypatch.setattr(server, "__file__", str(tmp_path / "server.py"))
    (tmp_path / "version.txt").write_text("1.0.0+42.g2f250d5\n", encoding="utf-8")

    assert server._packaged_as() == "1.0.0+42.g2f250d5"


def test_a_checkout_reports_the_release(tmp_path, monkeypatch):
    """Which is what it is: a tree nobody packaged."""
    monkeypatch.setattr(server, "__file__", str(tmp_path / "server.py"))

    assert server._packaged_as() == ""
