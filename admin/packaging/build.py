#!/usr/bin/env python3
"""Builds the Debian package this tool installs as.

    python3 packaging/build.py [--into DIRECTORY]

It lays the files out the way they will sit on the machine, writes the control
file, and calls dpkg-deb. That is the whole of it, and it is deliberate: this
package copies Python, static files, nine unit files, two udev rules, one
tmpfiles entry, one rpi-swap drop-in, one cursor theme, two pictures and two
scripts for the initramfs into place. Nothing is compiled, nothing is patched
and nothing is generated at install time, so the debhelper machinery would be
a build system around a copy.

The release is `previously.server.RELEASE` and is read from there rather than
written down again here. A package built between two releases carries that
release and the commit it came from, because a machine has to be able to say
which build it is running, and `version_from` below says how the two go
together. What it settles on is written into the package as well, so the tool
reports the version dpkg knows it by rather than a second answer of its own.
"""

import argparse
import pathlib
import re
import shutil
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ADMIN = HERE.parent

# The boot picture is read with the service's own PNG reader, which is the
# standard library and nothing else, so the build needs no image library. The
# scripts for the initramfs take the names of what they read from the drawer
# and the setup, which say them once. The service sits beside this script
# rather than being installed, so it goes on the path by hand.
sys.path.insert(0, str(ADMIN))
from previously import png, setup, splash  # noqa: E402

#: What the package is called, which is what the service, its directory under
#: /usr/lib and its state under /var/lib are already called.
NAME = "previously"

#: Nothing here is compiled: Python on the standard library, static files, and
#: xterm in web/vendor. A package that names an architecture it does not need
#: is one that cannot be installed on anything else for no reason.
ARCHITECTURE = "all"

#: What the service shells out to, and where each is used. A dependency that
#: is missing shows up as a feature that quietly does nothing, so they are
#: declared rather than discovered.
#:
#:   python3          the service itself
#:   xwayland         the X server the console has Previous draw through,
#:                    which cage starts only where it is installed
#:   openssh-client   the login behind the terminal, in terminal.Session
#:   procps           pgrep and ps, which say whether the emulator runs
DEPENDS = ["python3 (>= 3.11)", "xwayland", "openssh-client", "procps", "systemd"]

#: The emulator this administers. A recommendation rather than a dependency,
#: because it comes from an archive this package knows nothing about, and an
#: installation that cannot find it should still put the tool in place.
RECOMMENDS = ["previous"]

#: Where everything goes. The service reads these paths from its own settings,
#: and settings.py is what decides them; these are the same paths written as
#: the layout of a package.
LIB = "usr/lib/" + NAME
UNITS = "lib/systemd/system"
CONFIG = "etc/" + NAME

#: What lets the service make its virtual keyboard. /dev/uinput belongs to
#: root alone, and the service runs as the emulator's owner with this group
#: added in its unit. It takes two files, as systemd's own static nodes do in
#: its 50-udev-default.rules and static-nodes-permissions.conf: until the
#: module is loaded, /dev/uinput is a node kmod-static-nodes made at boot,
#: which udev does not know and no rule reaches, so tmpfiles gives it its
#: rights; once the module is loaded, the rule gives the device the same ones.
#: Under /usr/lib, because files there are the packages' and /etc is the
#: administrator's.
UDEV_RULE = "usr/lib/udev/rules.d/60-" + NAME + "-uinput.rules"
TMPFILES = "usr/lib/tmpfiles.d/" + NAME + ".conf"
UINPUT_GROUP = "input"

#: What starts the boot picture: a rule that wants an instance of the drawing
#: unit for every framebuffer that appears, by its name. By the name rather
#: than by the path, because vc4's sits at /sys/devices/platform/gpu on a Pi 4
#: and at /sys/devices/platform/axi/axi:gpu on a Pi 5. The rule leaves the
#: firmware's framebuffer out, `splash.FIRMWARE_FRAMEBUFFER`: vc4 replaces it
#: within a second at another mode, so a picture drawn there flashes up and
#: goes before the one that stays.
SPLASH_RULE = "usr/lib/udev/rules.d/60-" + NAME + "-splash.rules"

#: Where the package keeps swap in memory, as a drop-in rpi-swap reads while the
#: machine starts. Under /usr/lib, because swap.conf(5) leaves /etc to the
#: machine's administrator, and named to sort before the names its own examples
#: use, since the drop-in sorted last wins and an administrator's should.
SWAP = "usr/lib/rpi/swap.conf.d/50-" + NAME + ".conf"

#: What that drop-in says. rpi-swap's default keeps a file of up to two
#: gigabytes on the card as well, and on an eight gigabyte card that is the room
#: a system's disk needs. The helper says a restart gives that room back where
#: the mechanism is one of `setup.WITHOUT_A_FILE`, and `tests/test_packaging.py`
#: holds the two together.
SWAP_DROP_IN = (
    "# Written by the previously package. Swap stays in memory: rpi-swap's\n"
    "# default also keeps a file of up to 2 GB on the card, and on an 8 GB card\n"
    "# that is the room a NeXTSTEP disk needs. A drop-in that sorts after this\n"
    "# one, such as /etc/rpi/swap.conf.d/80-mine.conf, overrides it.\n"
    "[Main]\n"
    "Mechanism=zram\n")

#: A cursor theme that shows nothing, at the path `setup.CURSORS` hands cage
#: as its XCURSOR_PATH. cage loads its pointer from the theme `default` under
#: the name `left_ptr`, and `default` is the newer name for the same pointer.
CURSORS = "usr/share/" + NAME + "/cursors"
CURSOR_NAMES = ("left_ptr", "default")

#: The Xcursor format's type for an image chunk, as libXcursor and wlroots
#: read it, and the size cage asks its theme for.
XCURSOR_IMAGE = 0xFFFD0002
CURSOR_SIZE = 24

#: The pictures the Pi shows while it starts and while it shuts down, a pair
#: for every board the admin knows, by where the package keeps each as the TGA
#: previously/splash.py draws from, and the PNG design/mark.py fetches from
#: previous.li for it. The names are `splash.stems()`. Beside this script
#: rather than among the interface's pictures, because the admin does not show
#: them and serves nothing it does not show.
SPLASHES = {"%s/%s.tga" % (str(splash.PICTURE_DIRECTORY).lstrip("/"), stem): HERE / (stem + ".png")
            for stem in splash.stems()}

#: The TGA image type for uncompressed true colour, and the bit of its
#: descriptor that says the rows run from the top. `splash.picture` reads that
#: type at 24 bits with that bit set and nothing else, so the drawer needs no
#: decoder and takes the rows in the order they go onto the screen.
TGA_TRUE_COLOUR = 2
TGA_FROM_THE_TOP = 0x20

#: What brings the boot picture forward to the first moment the Pi can show
#: anything after its firmware: a hook that puts vc4 and a frame of the
#: picture into the initramfs, and a script that draws the frame once the root
#: is mounted. Under /usr/share, which initramfs-tools(7) reads for packages,
#: so /etc/initramfs-tools stays the administrator's. On next5 on 24.10.2026
#: vc4 had the screen at 0.99 s from the initramfs rather than at 3.60 s from
#: the root, and a frame drawn there stood unchanged until cage.
INITRAMFS_HOOK = "usr/share/initramfs-tools/hooks/" + NAME
INITRAMFS_SCRIPT = "usr/share/initramfs-tools/scripts/local-bottom/" + NAME

#: Where a hook reads initramfs-tools' helpers from, `force_load` among them,
#: which adds a module and loads it before init-premount.
HOOK_FUNCTIONS = "/usr/share/initramfs-tools/hook-functions"

#: Where in the initramfs the hook lays the picture out, and which framebuffer
#: it is for, as sysfs and /dev name it.
INITRAMFS_PICTURE = "/" + NAME
FRAMEBUFFER = "fb0"
SCREEN = "/sys/class/graphics/" + FRAMEBUFFER
SCREEN_DEVICE = "/dev/" + FRAMEBUFFER

#: Where a boot script writes into the kernel's log, which is the one log
#: there is before systemd.
KERNEL_LOG = "/dev/kmsg"

#: The header initramfs-tools(7) asks of every hook and boot script, which
#: answers what each needs to run first. These two need nothing.
INITRAMFS_HEADER = """PREREQ=""
prereqs()
{
    echo "$PREREQ"
}

case $1 in
prereqs)
    prereqs
    exit 0
    ;;
esac
"""

#: The hook, run whenever an initramfs is built.
INITRAMFS_HOOK_TEXT = """#!/bin/sh
# Written by the previously package. Brings vc4 into the initramfs, so it
# takes the screen within a second of the kernel's start rather than when udev
# loads it from the root, and lays the boot picture out for the screen as it
# is now, for the package's script in local-bottom to draw. Neither asks about
# the console: that script asks the root while the board starts.
%(header)s

. %(functions)s

# A kernel that is not a Raspberry Pi's has no vc4, and asking for a module
# that is not there fails the whole initramfs.
if [ -n "$(find "${MODULESDIR}" -name 'vc4.ko*' -print -quit 2>/dev/null)" ]; then
    force_load vc4
fi

# Not fatal: a board without a screen has no framebuffer to lay the picture
# out for, and the picture then comes when systemd draws it.
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/%(lib)s python3 -m previously.splash \\
    %(framebuffer)s --into "${DESTDIR}%(picture)s" || true
"""

#: The boot script, run in the initramfs once the root is mounted at
#: ${rootmnt}, which is the first moment the root can say whether the console
#: is switched on.
INITRAMFS_SCRIPT_TEXT = """#!/bin/sh
# Written by the previously package. Draws the boot picture the package's hook
# laid out, where the root has the console switched on and fb0 is vc4's and
# still the screen the frame was laid out for. Elsewhere it leaves the screen
# to previously-splash@.service, which asks for the same link once systemd
# runs and draws on a screen of any size.
%(header)s

console="${rootmnt}%(console)s"
picture=%(picture)s
screen=%(screen)s
device=%(device)s
log=%(log)s

said() { cat "$1" 2>/dev/null; }

# The link is absolute, as systemctl makes it, so from here it points nowhere
# and only its being there says anything. A screen that is not there, or an
# initramfs the hook laid no picture out in, says nothing that matches.
[ -L "$console" ] || exit 0
[ "$(said "$screen/name")" != "%(firmware)s" ] || exit 0
now="$(said "$screen/virtual_size") $(said "$screen/bits_per_pixel")"
now="$now $(said "$screen/stride") $(said "$screen/pan")"
[ "$now" = "$(said "$picture/%(geometry)s")" ] || exit 0
cat "$picture/%(frame)s" > "$device" || exit 0
# At the kernel's info level, which no console level this boot sets lets onto
# the screen, so it is read with `journalctl -k` and nowhere else.
echo "<6>previously: the boot picture is drawn from the initramfs" > "$log"
exit 0
"""

#: What git adds to the description of a tree that has something uncommitted
#: in it, and therefore what the version of such a build ends in. A package
#: that claims a commit it was not built from is worse than one that says it
#: was built from something nobody can look up.
MODIFIED = ".modified"

#: Where the version this was built as is written, inside the package, so that
#: a running service can say which build it is. The service reads it beside
#: its own modules and falls back to the release where there is none.
VERSION_FILE = "version.txt"

#: The unit files, and which of them is the service itself. Six of the others
#: are how the machine is changed without this service holding any privilege:
#: it leaves a file in its runtime directory and a path unit running as root
#: acts on it. Two of those do one exact command each, and the third installs.
#: The last two draw the pictures: the boot picture, started by SPLASH_RULE,
#: and the shutdown picture, which the console's unit wants.
SERVICE = NAME + ".service"
SPLASH_UNIT = NAME + "-splash@.service"
SHUTDOWN_SPLASH_UNIT = NAME + "-splash-shutdown.service"
UNIT_FILES = (SERVICE,
              NAME + "-poweroff.path", NAME + "-poweroff.service",
              NAME + "-reboot.path", NAME + "-reboot.service",
              NAME + "-setup.path", NAME + "-setup.service",
              SPLASH_UNIT, SHUTDOWN_SPLASH_UNIT)

#: Who the tool runs as, written by postinst as a drop-in beside the unit. The
#: user is whoever the card was made with, so it is decided on the machine
#: rather than in the package, and the unit names nobody. `setup.OWNER_FILE` is
#: the same path as the helper reads it.
OWNER_FILE = "etc/systemd/system/" + SERVICE + ".d/owner.conf"

#: The places in that person's home the service may write, which ProtectHome
#: otherwise forbids, each as a path under the home.
#:
#: Previous keeps its configuration in the first, and this tool's job is to
#: change it: the directory rather than the file, because the copy made before
#: every write is a second file beside the first.
#:
#: The second holds the configurations somebody saved, which are theirs rather
#: than this service's and therefore live in their home: a purge takes the
#: state directory with it and must not take their machines. postinst creates
#: it, because systemd skips an entry whose path is absent, which would leave
#: the first save refusing.
#:
#: The third is where the emulator runs and where its configuration has a
#: screen grab land, which this service reads and removes again.
#:
#: The fourth is the real part of the Previously tree, which the File Viewer
#: shows as Documents/Pictures. Grab writes a screenshot there and Preview
#: reads it back.
WRITABLE_IN_HOME = (".config/previous", ".config/previously",
                    ".cache/previously", "Previously")

#: Finds who the tool runs as: the user in an owner file already there, so an
#: upgrade keeps it; otherwise next, which every machine set up before there
#: was an owner file ran as; otherwise the user with UID 1000, which is the one
#: Raspberry Pi Imager creates. One statement, filled into preinst and postinst
#: alike, so the two cannot answer differently.
FIND_OWNER = (
    "    owner=$(sed -n 's/^User=//p' /%s 2>/dev/null || true)\n"
    "    if [ -z \"$owner\" ] && getent passwd next >/dev/null; then owner=next; fi\n"
    "    if [ -z \"$owner\" ]; then owner=$(getent passwd 1000 | cut -d: -f1); fi\n"
    % OWNER_FILE)

#: Which of those are switched on when the package is installed. A path unit
#: costs nothing while nothing is asked of it: it watches for one file and
#: starts its service when that file appears.
WATCHERS = (NAME + "-poweroff.path", NAME + "-reboot.path",
            NAME + "-setup.path")


def release():
    """@returns str, the release this tree belongs to.

    Read out of the source rather than imported, because importing it would
    mean the build needs whatever the service imports, and a build should not.
    """
    source = (ADMIN / NAME / "server.py").read_text(encoding="utf-8")
    found = re.search(r'^RELEASE = "([^"]+)"', source, re.M)
    if not found:
        raise SystemExit("no RELEASE in server.py")
    return found.group(1)


def described():
    """@returns str, what git says this tree is, or "" where it cannot say.

    A package built from a checkout with no git, or from a tree with no tags
    in it, is the bare release. That is not an error: it is a build nobody can
    trace back to a commit, and saying so by carrying no commit is honest.
    """
    try:
        answer = subprocess.run(
            ["git", "describe", "--tags", "--match", "v*", "--long",
             "--dirty=" + MODIFIED],
            cwd=str(ADMIN), capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return answer.stdout.strip() if answer.returncode == 0 else ""


def version_from(release_, description):
    """The version a package built from this tree carries.

    @param release_ - What the source calls this release.
    @param description - What `git describe --long --dirty` said, or "".
    @returns str

    A release that has been tagged and built from that tag is itself, and
    every other build says how far it stands from a tag and which commit it
    is. The count is there because dpkg orders versions and a hash does not:
    without it apt cannot tell a newer build from an older one, and every
    install has to be forced past that. The commit is there because the count
    alone does not say which tree was built.

    Which separator is a decision about what happens next. `~` sorts below the
    release and `+` sorts above it, so a build made before the release is
    replaced by the release when it is cut, and one made after it replaces the
    release. Written the other way round, cutting a tag would reach a machine
    as a downgrade.
    """
    found = re.match(
        r"^v?(?P<tag>.+)-(?P<count>\d+)-g(?P<commit>[0-9a-f]+)"
        r"(?P<modified>%s)?$" % re.escape(MODIFIED), description)
    if not found:
        return release_

    steps = int(found.group("count"))
    modified = found.group("modified") or ""
    if found.group("tag") == release_ and not steps and not modified:
        return release_

    # Ahead of the tag this release is named by, or ahead of the release the
    # tag names. The first is a build after that release and the second is a
    # build on the way to one.
    towards = "+" if found.group("tag") == release_ else "~"
    return "%s%s%d.g%s%s" % (release_, towards, steps,
                             found.group("commit"), modified)


def package_version():
    """@returns str, what this build is called, everywhere it is named."""
    return version_from(release(), described())


def control(size):
    """@param size - How many kilobytes the package installs.
    @returns str, the control file.
    """
    return "".join(line + "\n" for line in [
        "Package: " + NAME,
        "Version: " + package_version(),
        "Architecture: " + ARCHITECTURE,
        "Maintainer: phranck <phranck@layered.work>",
        "Depends: " + ", ".join(DEPENDS),
        "Recommends: " + ", ".join(RECOMMENDS),
        "Section: admin",
        "Priority: optional",
        "Homepage: https://github.com/phranck/previously",
        "Installed-Size: %d" % size,
        "Description: Web admin for the Previous emulator",
        " Configures and watches a NeXT machine running under Previous, from a",
        " browser, in an interface built to look like the machine it configures.",
        " Runs as the user who owns the emulator and never as root.",
    ])


#: Run before the files are unpacked, to refuse a machine the tool cannot run
#: on at all.
PREINST = """#!/bin/sh
set -e

# Refuses a machine with nobody to run as, before anything is unpacked, so a
# refusal leaves nothing half configured. The question is the one postinst
# answers.
if [ "$1" = install ] || [ "$1" = upgrade ]; then
%(find_owner)s
    if [ -z "$owner" ]; then
        echo "Previously runs as the user Raspberry Pi Imager created," >&2
        echo "and this machine has no such user." >&2
        exit 1
    fi
fi
"""

#: Run after the files are in place. Only what dpkg does not do itself: who
#: the tool runs as is written down, systemd has to be told the units exist,
#: the one directory the service cannot create for itself is made, a console
#: and an archive source that are there are brought up to this version, and
#: the service is started so that installing it is enough to have it.
POSTINST = """#!/bin/sh
set -e

if [ "$1" = configure ]; then
    # Who the tool runs as, as a drop-in beside its unit, with the places in
    # that home it may write. preinst has already refused a machine where this
    # finds nobody.
%(find_owner)s
    group=$(id -gn "$owner")
    home=$(getent passwd "$owner" | cut -d: -f6)
    mkdir -p %(owner_dir)s
    {
        echo "[Service]"
        echo "User=$owner"
        echo "Group=$group"
%(writable)s    } > /%(owner_file)s

    # Where the configurations somebody saves are kept, in that home. systemd
    # skips a ReadWritePaths entry whose path is absent, so this has to exist
    # before the service starts or the first save refuses.
    #
    # It does not fail the installation. A directory that cannot be made leaves a
    # service that runs and refuses to save, saying why, which is a better state
    # to hand somebody than a package dpkg has left half configured.
    if [ -n "$home" ] && [ -d "$home" ]; then
        install -d -o "$owner" -g "$group" -m 0700 "$home/.config/%(name)s" || true
    fi

    # The console that starts the emulator, brought up to what this version of
    # the helper writes where the machine has one, and left out where it has
    # none. A console in ~/.profile is moved over to the console's unit. Here
    # rather than in any one way of updating, so the browser, a shell and apt
    # all leave the tool and its console in step. Not fatal: the console that is
    # there still starts the machine.
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/%(lib)s python3 -c '
import sys
from previously import setup
setup.refresh_console(setup.Owner(sys.argv[1]))
' "$owner" || true

    # What this version leaves out of the board's start, switched off where the
    # machine is set up, for the same reason. Not fatal: a unit left on only
    # costs a little time at the next boot.
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/%(lib)s python3 -c '
import sys
from previously import setup
setup.refresh_services(setup.Owner(sys.argv[1]))
' "$owner" || true

    # The emulator's configuration, brought up to where this version has it
    # write a screen grab and with no ROM named, for the same reason. Not fatal:
    # without it the Grab gives nothing, and a ROM is still taken out when the
    # admin next starts the emulator.
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/%(lib)s python3 -c '
import sys
from previously import setup
setup.refresh_configuration(setup.Owner(sys.argv[1]))
' "$owner" || true

    # The source Previous comes from, brought up to what this version of the
    # helper writes where the machine has one, for the same reason. Not fatal:
    # the source that is there still installs Previous wherever its archive
    # answers.
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/%(lib)s python3 -c '
from previously import setup
setup.refresh_archive()
' || true

    # The kernel's console held at the level a quiet boot's command line sets,
    # where the boot is quiet, for the same reason. Not fatal: without it a
    # message the kernel logs can stand over the boot picture.
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/%(lib)s python3 -c '
from previously import setup
setup.refresh_quiet()
' || true

    # The initramfs of the kernel this board runs, built again so it brings vc4
    # up and carries the boot picture as this version lays it out. Named by its
    # kernel, because initramfs-tools' own trigger builds the newest kernel's
    # alone, and on Raspberry Pi OS that is the Pi 4's on a Pi 5 as well. Not
    # fatal: without it vc4 and the picture come later in the boot.
    update-initramfs -u -k "$(uname -r)" || true

    # The rights for the virtual keyboard, given to /dev/uinput now, because it
    # was made at boot before the entry and the rule were there. Not fatal:
    # without them the service still starts, and only pressing the emulator's
    # keys fails.
    systemd-tmpfiles --create /%(tmpfiles)s || true
    udevadm control --reload-rules || true
    udevadm trigger --subsystem-match=misc --sysname-match=uinput || true

    systemctl daemon-reload
    systemctl enable --now %(service)s
    # These act for the service without it holding any privilege, so they are
    # part of it rather than something to switch on separately.
    systemctl enable --now %(watchers)s
fi
"""

#: Run before the files go. Stopping first, because a unit whose files are
#: removed underneath it is one systemd cannot stop afterwards.
PRERM = """#!/bin/sh
set -e

if [ "$1" = remove ] || [ "$1" = upgrade ]; then
    systemctl disable --now %(service)s || true
    systemctl disable --now %(watchers)s || true
fi
"""

#: Run after the files have gone. Purge is where "leaves nothing behind"
#: belongs: the state this service wrote itself, which is its password and the
#: digest of its last write, and its own configuration. Remove keeps both, which
#: is the whole difference between the two and why somebody would choose one.
#:
#: What purge does not touch is anything in somebody's home. The configurations
#: they saved are in `~/.config/previously`, along with the emulator's own
#: configuration and the disk image, and removing this tool is not removing the
#: machines they built with it.
#:
#: There is no user to remove. This service runs as the user who owns the
#: emulator rather than as one of its own.
POSTRM = """#!/bin/sh
set -e

systemctl daemon-reload || true

if [ "$1" = remove ] || [ "$1" = purge ]; then
    # Whatever ended up in the program directory that dpkg does not own, which
    # is Python's compiled modules where anything ran without
    # PYTHONDONTWRITEBYTECODE. dpkg leaves the directory standing for them, so
    # this is what makes removal complete.
    rm -rf /usr/lib/%(name)s
fi

if [ "$1" = remove ]; then
    # The initramfs of the kernel this board runs, built again without the hook
    # and the script, which have gone with the package, so the board draws no
    # picture of a tool that is not there.
    update-initramfs -u -k "$(uname -r)" || true
fi

if [ "$1" = purge ]; then
    rm -rf /var/lib/%(name)s /etc/%(name)s %(owner_dir)s
fi
"""


def lay_out(into):
    """Puts every file where it will sit on the machine.

    @param into - pathlib.Path of the directory to build in, which is emptied
      first so a second build cannot inherit a file from the first.
    """
    if into.exists():
        shutil.rmtree(into)

    # The service and the pages it serves. __pycache__ is whatever the last
    # test run left and has no business in a package.
    shutil.copytree(ADMIN / NAME, into / LIB / NAME,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ADMIN / "web", into / LIB / "web",
                    ignore=shutil.ignore_patterns("__pycache__"))

    # What this build is called, beside the modules that report it. Written
    # rather than left to the source, because the source names the release and
    # a build between two releases is more than that.
    (into / LIB / NAME / VERSION_FILE).write_text(
        package_version() + "\n", encoding="utf-8")

    (into / UNITS).mkdir(parents=True, exist_ok=True)
    for unit in UNIT_FILES:
        shutil.copy(HERE / unit, into / UNITS / unit)

    (into / CONFIG).mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "config.ini", into / CONFIG / "config.ini")

    # Written from the constant rather than shipped as files, so the group both
    # name is the group `tests/test_packaging.py` holds the unit to.
    (into / UDEV_RULE).parent.mkdir(parents=True, exist_ok=True)
    (into / UDEV_RULE).write_text(
        "# Written by the previously package. Lets the admin make the virtual\n"
        "# keyboard it presses the emulator's keys with.\n"
        'KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="%s", MODE="0660", '
        'OPTIONS+="static_node=uinput"\n' % UINPUT_GROUP, encoding="utf-8")
    (into / TMPFILES).parent.mkdir(parents=True, exist_ok=True)
    (into / TMPFILES).write_text(
        "# Written by the previously package. The same rights for /dev/uinput\n"
        "# before its module is loaded.\n"
        "z /dev/uinput 0660 - %s -\n" % UINPUT_GROUP, encoding="utf-8")
    (into / SPLASH_RULE).write_text(
        "# Written by the previously package. Draws the boot picture on a\n"
        "# framebuffer the moment it appears, apart from the firmware's.\n"
        'ACTION=="add", SUBSYSTEM=="graphics", KERNEL=="fb[0-9]*", '
        'ATTR{name}!="%s", TAG+="systemd", ENV{SYSTEMD_WANTS}+="%s"\n'
        % (splash.FIRMWARE_FRAMEBUFFER, SPLASH_UNIT.replace("@", "@%k")),
        encoding="utf-8")
    for path, text in initramfs_scripts().items():
        (into / path).parent.mkdir(parents=True, exist_ok=True)
        (into / path).write_text(text, encoding="utf-8")
        (into / path).chmod(0o755)

    (into / SWAP).parent.mkdir(parents=True, exist_ok=True)
    (into / SWAP).write_text(SWAP_DROP_IN, encoding="utf-8")

    theme = into / CURSORS / "default" / "cursors"
    theme.mkdir(parents=True, exist_ok=True)
    for name in CURSOR_NAMES:
        (theme / name).write_bytes(transparent_cursor())

    for tga, picture in SPLASHES.items():
        (into / tga).parent.mkdir(parents=True, exist_ok=True)
        (into / tga).write_bytes(splash_tga(picture))


def transparent_cursor():
    """@returns bytes, an Xcursor file holding one transparent pixel.

    Laid out as libXcursor and wlroots read it, all little endian: the file
    header with the magic, its own length, the version and one table entry;
    the entry with the chunk's type, its nominal size and where it starts; and
    the image chunk, whose header gives its length, type, nominal size,
    version, width, height, hot spot and delay before the pixels.
    """
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, 1)
    table = struct.pack("<III", XCURSOR_IMAGE, CURSOR_SIZE, len(header) + 12)
    image = struct.pack("<9I", 36, XCURSOR_IMAGE, CURSOR_SIZE, 1, 1, 1, 0, 0, 0)
    return header + table + image + struct.pack("<I", 0)


def splash_tga(picture):
    """@returns bytes, one of the SPLASHES as previously/splash.py reads it.

    @param picture - pathlib.Path of the PNG, in RGB at eight bits a sample.

    An 18 byte header and then every pixel as blue, green and red, without a
    colour map and without compression: the type at byte 2, the width and the
    height at bytes 12 to 15, the depth at byte 16 and the descriptor at byte
    17. The rows go in from the top, as the PNG holds them.
    """
    width, height, lines = png.rgb(picture.read_bytes())
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, TGA_TRUE_COLOUR, 0, 0, 0, 0, 0,
                         width, height, 24, TGA_FROM_THE_TOP)
    pixels = bytearray()
    for line in lines:
        turned = bytearray(len(line))
        turned[0::3], turned[1::3], turned[2::3] = line[2::3], line[1::3], line[0::3]
        pixels += turned
    return header + bytes(pixels)


def initramfs_scripts():
    """The hook and the boot script for the initramfs, filled in.

    @returns dict of where each goes in the package to what it holds.

    The names they share with the drawer and the setup are filled in from
    there, so the frame the hook has laid out is the file the script looks for
    and the link the script asks the root about is the one systemctl makes.
    """
    words = {"header": INITRAMFS_HEADER.rstrip("\n"), "functions": HOOK_FUNCTIONS,
             "lib": LIB, "framebuffer": FRAMEBUFFER, "picture": INITRAMFS_PICTURE,
             "console": setup.CONSOLE_SWITCHED_ON, "screen": SCREEN,
             "device": SCREEN_DEVICE, "log": KERNEL_LOG, "frame": splash.FRAME,
             "geometry": splash.GEOMETRY, "firmware": splash.FIRMWARE_FRAMEBUFFER}
    return {INITRAMFS_HOOK: INITRAMFS_HOOK_TEXT % words,
            INITRAMFS_SCRIPT: INITRAMFS_SCRIPT_TEXT % words}


def scripts():
    """The four maintainer scripts, filled in.

    @returns dict of name to what goes into DEBIAN.

    Here rather than inside `write_control`, so the tests that read them are
    reading what the package carries instead of filling the same names in a
    second time and agreeing with themselves.
    """
    words = {"name": NAME, "service": SERVICE, "units": UNITS, "lib": LIB,
             "watchers": " ".join(WATCHERS), "tmpfiles": TMPFILES,
             "find_owner": FIND_OWNER.rstrip("\n"),
             "owner_file": OWNER_FILE,
             "owner_dir": "/" + str(pathlib.PurePosixPath(OWNER_FILE).parent),
             "writable": "".join('        echo "ReadWritePaths=-$home/%s"\n' % place
                                 for place in WRITABLE_IN_HOME)}
    return {"preinst": PREINST % words, "postinst": POSTINST % words,
            "prerm": PRERM % words, "postrm": POSTRM % words}


def write_control(into):
    """Writes DEBIAN/control and the four scripts, and makes them runnable."""
    debian = into / "DEBIAN"
    debian.mkdir(parents=True, exist_ok=True)

    kilobytes = sum(path.stat().st_size for path in into.rglob("*")
                    if path.is_file()) // 1024
    (debian / "control").write_text(control(kilobytes), encoding="utf-8")

    # Changed by hand on a running machine and never overwritten by an
    # upgrade, which is what conffiles means.
    (debian / "conffiles").write_text("/%s/config.ini\n" % CONFIG, encoding="utf-8")

    for script, body in scripts().items():
        path = debian / script
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--into", default=str(HERE / "build"),
                        help="where to lay the files out and write the .deb")
    where = parser.parse_args().into

    if shutil.which("dpkg-deb") is None:
        raise SystemExit("dpkg-deb is not here: brew install dpkg, or build "
                         "this on the machine it is for")

    tree = pathlib.Path(where) / NAME
    lay_out(tree)
    write_control(tree)

    package = pathlib.Path(where) / ("%s_%s_%s.deb"
                                     % (NAME, package_version(), ARCHITECTURE))
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build",
                    str(tree), str(package)], check=True)
    print("wrote %s" % package)


if __name__ == "__main__":
    sys.exit(main())
