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
import subprocess

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


# -- which build a package is --------------------------------------------


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
    """The source already says 1.0.0 whilst the newest tag is still the release
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
