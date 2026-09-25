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

import pytest

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


def test_the_unit_opens_the_directory_they_live_in(unit):
    """ProtectHome leaves the home read only, so without this entry the first
    save fails and the file the service is configured with can never be written.
    """
    opened = re.findall(r"^ReadWritePaths=-?(\S+)", unit, re.M)

    assert any(path.endswith("/" + where_they_live()) for path in opened), opened


def test_the_package_creates_that_directory(build):
    """systemd skips a ReadWritePaths entry whose path is absent, so the entry
    above is worth nothing until the directory exists. Nothing the service does
    can create it: by the time it runs, the home is already read only."""
    postinst = build.POSTINST % {
        "name": build.NAME, "service": build.SERVICE, "units": build.UNITS}

    assert "install -d" in postinst
    assert where_they_live() in postinst


def test_the_package_asks_the_unit_who_the_user_is(build):
    """Rather than naming them a second time. The unit is where it is decided,
    and a package that disagreed with it would create the directory in the wrong
    home and leave the right one read only."""
    postinst = build.POSTINST % {
        "name": build.NAME, "service": build.SERVICE, "units": build.UNITS}

    assert "s/^User=//p" in postinst
    assert "getent passwd" in postinst


def test_purging_the_package_leaves_the_home_alone(build):
    """What it removes is what this service owns: its state directory and its own
    configuration. The configurations somebody saved are in their home, beside
    the emulator's configuration and the disk image, and removing this tool is
    not removing the machines they built with it."""
    postrm = build.POSTRM % {"name": build.NAME, "service": build.SERVICE}

    for line in postrm.splitlines():
        if line.strip().startswith("rm -rf"):
            assert "/home" not in line, line
            assert "~" not in line, line
