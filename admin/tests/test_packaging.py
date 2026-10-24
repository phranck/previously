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


@pytest.fixture(scope="module")
def build():
    """`packaging/build.py`, imported by path.

    It is a script beside the package rather than a module of it, so there is
    nothing to import by name. What is wanted from it is the maintainer scripts
    it writes, which are constants in it.
    """
    spec = importlib.util.spec_from_file_location("build", PACKAGING / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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


def test_the_package_runs_as_the_user_the_card_was_made_with(build):
    """The Imager asks for a user name and creates that user first, so it is
    the one with UID 1000. A machine that already has an owner file keeps the
    user in it, and one that ran as next before keeps next, so an upgrade never
    moves the tool into somebody else's home."""
    postinst = build.scripts()["postinst"]

    kept = postinst.index("/" + build.OWNER_FILE)
    before = postinst.index("getent passwd next")
    first = postinst.index("getent passwd 1000")

    assert kept < before < first
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


@pytest.mark.parametrize("written, users, expected", [
    ("[Service]\nUser=kept\n", {"next": 1000}, "kept"),
    ("", {"next": 1001, "pi": 1000}, "next"),
    ("", {"pi": 1000}, "pi"),
    ("", {}, ""),
])
def test_who_the_tool_runs_as(build, tmp_path, written, users, expected):
    """The statement itself, run by a shell, with getent answering for the
    users the case names and the owner file put somewhere a test can write."""
    owner_file = tmp_path / "owner.conf"
    if written:
        owner_file.write_text(written, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    lines = "".join('  %s|%s) echo "%s:x:%d:%d::/home/%s:/bin/sh" ;;\n'
                    % (name, uid, name, uid, uid, name) for name, uid in users.items())
    getent = bin_dir / "getent"
    getent.write_text('#!/bin/sh\ncase "$2" in\n%s  *) exit 2 ;;\nesac\n' % lines,
                      encoding="utf-8")
    getent.chmod(0o755)

    snippet = build.FIND_OWNER.replace("/" + build.OWNER_FILE, str(owner_file))
    finished = subprocess.run(
        ["sh", "-c", snippet + 'printf "%s" "$owner"'],
        capture_output=True, text=True, check=True,
        env={"PATH": "%s:/usr/bin:/bin" % bin_dir})

    assert finished.stdout == expected


def test_the_service_never_starts_without_its_owner(unit, build):
    """The unit names nobody, so where the owner file is missing it would run
    as root. It does not start at all instead."""
    assert not re.search(r"^User=", unit, re.M)
    assert "ConditionPathExists=/" + build.OWNER_FILE in unit


def test_the_helper_reads_the_owner_where_the_package_writes_it(build):
    from previously import setup

    assert "/" + build.OWNER_FILE == str(setup.OWNER_FILE)


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

    assert given < postinst.index("systemctl enable --now")
    assert reloaded < postinst.index("systemctl enable --now")


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


def test_the_package_brings_the_x_server_previous_draws_through(build):
    """The console tells Previous to draw through X first, and cage starts an
    X server only where Xwayland is installed. The cage in the Raspberry Pi
    archive does not bring it along, so the package does."""
    assert "xwayland" in build.DEPENDS


# -- the boot picture ----------------------------------------------------


def test_the_package_carries_the_boot_picture_pixel_for_pixel(build, tmp_path):
    """The TGA is written from the PNG design/mark.py fetches, and the drawer
    reads it back. Every pixel has to arrive as the PNG holds it, turned from
    red, green and blue into the blue, green and red a TGA stores."""
    from previously import png, splash

    build.lay_out(tmp_path / "tree")
    width, height, pixels = splash.picture((tmp_path / "tree" / build.SPLASH).read_bytes())
    wide, high, lines = png.rgb(build.SPLASH_PICTURE.read_bytes())

    assert (width, height) == (wide, high)
    turned = b"".join(bytes(line[at + 2 - channel] for at in range(0, len(line), 3)
                            for channel in range(3)) for line in lines)
    assert pixels == turned


def test_the_drawer_reads_the_picture_where_the_package_puts_it(build):
    from previously import splash

    assert "/" + build.SPLASH == str(splash.PICTURE)


def test_every_framebuffer_that_appears_gets_the_picture(build, tmp_path):
    """By its name rather than by its path, because vc4's framebuffer sits at
    /sys/devices/platform/gpu on a Pi 4 and at /sys/devices/platform/axi/axi:gpu
    on a Pi 5, read on 24.10.2026."""
    build.lay_out(tmp_path / "tree")
    rule = (tmp_path / "tree" / build.SPLASH_RULE).read_text(encoding="utf-8")
    lines = [line for line in rule.splitlines() if line and not line.startswith("#")]

    assert lines == ['ACTION=="add", SUBSYSTEM=="graphics", KERNEL=="fb[0-9]*", '
                     'TAG+="systemd", ENV{SYSTEMD_WANTS}+="previously-splash@%k.service"']
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
    assert ("ConditionPathExists=%s" % (setup.SYSTEM_UNITS / "multi-user.target.wants"
                                        / setup.CONSOLE)) in unit.splitlines()


def test_the_drawer_runs_as_nobody_in_particular(build):
    """It writes the framebuffer and nothing else, and the framebuffer belongs
    to the video group."""
    unit = (PACKAGING / build.SPLASH_UNIT).read_text(encoding="utf-8")

    assert "DynamicUser=yes" in unit.splitlines()
    assert "SupplementaryGroups=video" in unit.splitlines()
    assert not re.search(r"^User=", unit, re.M)


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
    """The workflow renames the versioned package the build writes to one fixed
    name, so that a single address is always the newest one. Three places name
    it, and a fourth would be one too many: the workflow that attaches it, the
    script that installs onto a fresh machine, and the module the tool's own
    update fetches it with."""
    from previously import release

    repository = PACKAGING.parent.parent
    workflow = (repository / ".github" / "workflows"
                / "release.yml").read_text(encoding="utf-8")
    script = (repository / "install.sh").read_text(encoding="utf-8")

    assert release.ASSET == "%s_%s.deb" % (build.NAME, build.ARCHITECTURE)
    assert release.ASSET in workflow
    assert release.ASSET in script


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
