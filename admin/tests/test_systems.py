"""The library of systems, and where each of them comes from.

Nothing here reaches the network. What is tested is the table itself and the
two questions asked of it: where a system is fetched from, and whether one is
already on this machine. Both are what the privileged helper acts on, and both
are wrong in ways nothing else would notice: an address that leads somewhere
else, or a disk that is here and is not recognised, which costs two gigabytes
and half an hour.
"""

import os

import pytest

from previously import systems


def test_there_are_six_and_they_are_the_ones_measured():
    """Six prepared systems, from NeXTSTEP 2.2 to OPENSTEP 4.2. A seventh
    turning up here without its size and digest measured is the thing this
    catches."""
    assert len(systems.CATALOGUE) == 6
    assert [system.identifier for system in systems.CATALOGUE] == [
        "nextstep-2.2", "nextstep-3.0", "nextstep-3.2", "nextstep-3.3",
        "openstep-4.0", "openstep-4.2"]


def test_every_system_says_exactly_what_its_archive_is():
    """The size and the digest are what the helper holds an arriving file to,
    so one left out is a system that installs whatever arrives."""
    for system in systems.CATALOGUE:
        assert system.size > 20_000_000, system.identifier
        assert len(system.digest) == 40, system.identifier
        assert set(system.digest) <= set("0123456789abcdef"), system.identifier
        assert system.file.endswith(".7z"), system.identifier


def test_the_default_is_one_of_them():
    """It is what comes with the emulator when nobody chooses, so a name that
    is not in the table would set a fresh machine up with no system at all."""
    assert systems.find(systems.DEFAULT) is not None


def test_nothing_is_called_the_same_thing_twice():
    assert len({system.identifier for system in systems.CATALOGUE}) == 6
    assert len({system.item for system in systems.CATALOGUE}) == 6


def test_an_unknown_name_is_nothing_rather_than_an_error():
    assert systems.find("nextstep-9.9") is None
    assert systems.find(None) is None


def test_the_address_is_built_from_the_table():
    """Written once here rather than six times in the table, and quoted,
    because every one of these file names carries spaces."""
    address = systems.address(systems.find("nextstep-3.3"))

    assert address.startswith("https://archive.org/download/")
    assert " " not in address
    assert address.endswith("Nextstep%203.3%20HD%20Image%20With%20Previous.7z")


@pytest.mark.parametrize("url", [
    "https://archive.org/download/x/y.7z",
    "https://ia600504.us.archive.org/12/items/x/y.7z",
])
def test_a_redirect_that_stays_on_the_archive_is_allowed(url):
    """archive.org answers a download by sending the caller to whichever node
    holds the item, so following redirects is not optional."""
    assert systems.from_our_archive(url) is True


@pytest.mark.parametrize("url", [
    "http://archive.org/download/x/y.7z",
    "https://archive.org.example.com/x",
    "https://example.com/x",
    "file:///etc/passwd",
    "",
])
def test_a_redirect_that_leaves_it_is_not(url):
    """Whoever answers the first request chooses where the second one goes, so
    a redirect is checked exactly as the first address was."""
    assert systems.from_our_archive(url) is False


# -- what is already on the machine ---------------------------------------


def test_a_disk_fetched_by_this_tool_is_found(tmp_path):
    """One file per system, named after the system, which is the whole reason
    a disk is renamed on the way in."""
    system = systems.find("nextstep-3.3")
    disk = tmp_path / "nextstep-3.3.dd"
    disk.write_bytes(b"x")

    assert systems.disk_in(tmp_path, system) == disk


def test_a_disk_install_sh_left_behind_is_found_too(tmp_path):
    """That script unpacks the archive as it comes, which leaves the disk
    inside a folder named after the archive. A machine set up that way is one
    to recognise rather than to fetch a second copy for."""
    system = systems.find("nextstep-3.3")
    folder = tmp_path / "Nextstep 3.3 HD Image With Previous"
    folder.mkdir()
    (folder / "Rev_3.3_v74.BIN").write_bytes(b"a rom")
    disk = folder / "NS33_2GB.dd"
    disk.write_bytes(b"")
    # Made by truncating rather than by writing, so the test does not put half
    # a gigabyte on somebody's machine to check a size.
    os.truncate(disk, systems.SMALLEST_DISK_BYTES)

    assert systems.disk_in(tmp_path, system) == disk


def test_the_small_files_in_that_folder_are_not_disks(tmp_path):
    """Those archives carry ROM images, a Windows binary and a text file, and
    none of them comes near half a gigabyte."""
    system = systems.find("nextstep-3.3")
    folder = tmp_path / "Nextstep 3.3 HD Image With Previous"
    folder.mkdir()
    (folder / "Previous.exe").write_bytes(b"x" * 1024)

    assert systems.disk_in(tmp_path, system) is None


def test_a_folder_with_nothing_in_it_has_no_systems(tmp_path):
    assert systems.here(tmp_path) == {}
    assert systems.disk_in(tmp_path / "not-there", systems.CATALOGUE[0]) is None


def test_what_is_here_is_listed_by_name(tmp_path):
    (tmp_path / "nextstep-3.3.dd").write_bytes(b"x")
    (tmp_path / "openstep-4.2.dd").write_bytes(b"x")

    assert sorted(systems.here(tmp_path)) == ["nextstep-3.3", "openstep-4.2"]


def test_room_is_asked_of_a_folder_that_is_not_there_yet(tmp_path):
    """A fresh machine has no disks folder, and what has to be known before one
    is made is whether there is room to make it."""
    free = systems.room_beside(tmp_path / "nextstep" / "deeper")

    assert free is not None
    assert free > 0


def test_a_fetch_needs_room_for_the_disk_and_the_archive(tmp_path):
    """Measured rather than guessed: the 3.3 disk is 2,012,774,400 bytes on the
    reference machine, and the archive sits beside it whilst it unpacks."""
    assert systems.ROOM_BYTES > systems.UNPACKED_BYTES
    assert systems.ROOM_BYTES > max(
        system.size for system in systems.CATALOGUE) + systems.UNPACKED_BYTES
