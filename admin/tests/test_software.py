"""The software catalog: what it offers, and what an entry has to be.

Every entry names an address on somebody else's server, and later a fetch
refuses anything that arrives as other than the entry says. So the entries are
held here to the shape that fetch relies on, and the shipped list is held to it
like any entry somebody adds.
"""

import json
import pathlib
import tempfile

import pytest

from previously import software, systems


def an_entry(**changed):
    """@returns software.Entry, a well formed one with what is given changed."""
    fields = dict(
        identifier="nextstep-3.3-developer",
        name="NeXTSTEP 3.3 Developer",
        description="Compiler, Interface Builder, Project Builder and the documentation.",
        group="developer",
        version="3.3",
        systems=("nextstep-3.3",),
        address="https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP_3.3_Developer.iso",
        size=403111936,
        algorithm="sha1",
        digest="268c66059c3c48df3bb4d2498785f2459bfa73cd",
        kind="disc",
        cover="https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP%20CD%20Folio_thumb.jpg",
    )
    fields.update(changed)
    return software.Entry(**fields)


def test_a_well_formed_entry_has_no_problems():
    assert software.problems(an_entry()) == []


def test_an_entry_without_a_version_is_well_formed():
    """Plenty of items name none, nebula-se among them, so a version is
    checked only where one is given."""
    assert software.problems(an_entry(version="")) == []
    assert software.problems(an_entry(version=None)) == ["version"]


@pytest.mark.parametrize("entry", software.CATALOGUE, ids=lambda entry: entry.identifier)
def test_every_shipped_entry_is_well_formed(entry):
    """The shipped list is held to the same rules as an entry somebody adds,
    because a fetch reads both the same way."""
    assert software.problems(entry) == []


def test_the_shipped_list_starts_with_the_developer_cd():
    entry = software.find("nextstep-3.3-developer")

    assert entry is not None
    assert entry.kind == "disc"
    assert entry.systems == ("nextstep-3.3",)
    assert entry.size == 403111936


def test_no_two_shipped_entries_share_an_identifier():
    identifiers = [entry.identifier for entry in software.CATALOGUE]

    assert len(identifiers) == len(set(identifiers))


@pytest.mark.parametrize("changed, problem", [
    ({"identifier": "Has Spaces"}, "identifier"),
    ({"identifier": ""}, "identifier"),
    ({"name": ""}, "name"),
    ({"name": "x" * 81}, "name"),
    ({"name": "two\nlines"}, "name"),
    ({"description": "x" * 501}, "description"),
    ({"group": "music"}, "group"),
    ({"version": "3.3 final release candidate edition"}, "version"),
    ({"version": "3.3 beta"}, "version"),
    ({"version": "x" * 33}, "version"),
    ({"systems": ()}, "systems"),
    ({"systems": ("nextstep-9.9",)}, "systems"),
    ({"address": "http://archive.org/download/x/y.iso"}, "address"),
    ({"address": "https://user:secret@archive.org/download/x/y.iso"}, "address"),
    ({"address": "https://192.168.1.10/y.iso"}, "address"),
    ({"address": "https://[::1]/y.iso"}, "address"),
    ({"address": "https://archive.org/" + "x" * 2048}, "address"),
    ({"size": 0}, "size"),
    ({"size": True}, "size"),
    ({"size": software.LARGEST_BYTES + 1}, "size"),
    ({"algorithm": "md5"}, "algorithm"),
    ({"digest": "268c6605"}, "digest"),
    ({"digest": "Z" * 40}, "digest"),
    ({"algorithm": "sha256"}, "digest"),
    ({"kind": "floppy"}, "kind"),
    # What a file written by hand can hold, and JSON can carry.
    ({"identifier": 5}, "identifier"),
    ({"group": ["tools"]}, "group"),
    ({"systems": (["nextstep-3.3"],)}, "systems"),
    ({"algorithm": ["sha1"]}, "algorithm"),
    ({"digest": 5}, "digest"),
    ({"kind": ["disc"]}, "kind"),
    # A cover comes from archive.org, which is the one place the Pi fetches
    # one from, and from nowhere else.
    ({"cover": "https://example.org/front.jpg"}, "cover"),
    ({"cover": "http://archive.org/download/x/front_thumb.jpg"}, "cover"),
    ({"cover": "https://archive.org.example.com/x.jpg"}, "cover"),
    ({"cover": None}, "cover"),
])
def test_a_field_that_breaks_its_rule_is_named(changed, problem):
    """Each rule is about the one field, so what is wrong can be said next to
    it in the window that edits an entry."""
    assert software.problems(an_entry(**changed)) == [problem]


def test_an_entry_for_a_system_is_offered_to_that_system_alone():
    """NEXTSTEP 3.3 Developer builds NEXTSTEP programs; OPENSTEP 4.x has its
    own development environment, so a package names the systems it is for."""
    offered = [entry.identifier for entry in software.for_system("nextstep-3.3")]

    assert "nextstep-3.3-developer" in offered
    assert software.for_system("openstep-4.2") == []
    assert software.for_system(None) == []


def test_every_group_has_a_folder_name():
    """A viewer shows names, so a group's folder is named once in English and
    read the same in every language."""
    assert set(software.FOLDERS) == set(software.GROUPS)
    assert all(name and name[0].isupper() for name in software.FOLDERS.values())


def test_the_systems_named_are_the_installers():
    """One list of systems, the Installer's, so a package cannot name a system
    nothing can boot."""
    entry = an_entry(systems=tuple(system.identifier for system in systems.CATALOGUE))

    assert software.problems(entry) == []


def a_package(**changed):
    """@returns dict, the fields of a well formed entry as the browser sends
    them, with what is given changed. No identifier, because it follows from
    the name."""
    values = dict(
        name="Emacs",
        description="The editor.",
        group="tools",
        version="21.4",
        systems=["nextstep-3.3", "openstep-4.2"],
        address="https://example.org/emacs.tar.gz",
        size=4_000_000,
        algorithm="sha256",
        digest="ab" * 32,
        kind="file",
        cover="",
    )
    values.update(changed)
    return values


def listed(path):
    """@returns list of identifiers, in the order the catalog lists them."""
    return [entry.identifier for entry in software.catalogue(path)]


def test_with_nothing_changed_the_catalog_is_the_shipped_list(tmp_path):
    assert software.catalogue(tmp_path / "software.json") == software.CATALOGUE


def test_an_added_entry_follows_the_shipped_ones(tmp_path):
    path = tmp_path / "software.json"

    ok, told = software.save(path, a_package())

    assert ok, told
    assert told == {"reason": "software.kept", "name": "Emacs"}
    assert listed(path) == ["nextstep-3.3-developer", "emacs"]
    assert software.find("emacs", path).systems == ("nextstep-3.3", "openstep-4.2")


def test_the_identifier_is_the_name_written_as_one(tmp_path):
    path = tmp_path / "software.json"

    software.save(path, a_package(name="OmniWeb 3.1 Pro"))

    assert listed(path)[-1] == "omniweb-3.1-pro"


def test_an_edited_shipped_entry_keeps_its_place_and_says_it_was_changed(tmp_path):
    path = tmp_path / "software.json"
    shipped = software.described(software.find("nextstep-3.3-developer"))
    values = {field: shipped[field] for field in software.FIELDS}
    values["description"] = "Changed."

    ok, _ = software.save(path, values, replacing="nextstep-3.3-developer")

    assert ok
    assert listed(path) == ["nextstep-3.3-developer"]
    assert software.find("nextstep-3.3-developer", path).description == "Changed."
    assert software.origins(path) == {"nextstep-3.3-developer": "changed"}


def test_a_removed_shipped_entry_is_gone_and_can_be_brought_back(tmp_path):
    path = tmp_path / "software.json"

    ok, told = software.remove(path, "nextstep-3.3-developer")

    assert ok
    assert told == {"reason": "software.removed", "name": "NeXTSTEP 3.3 Developer"}
    assert listed(path) == []
    assert [entry.identifier for entry in software.removed(path)] == ["nextstep-3.3-developer"]

    ok, told = software.restore(path, "nextstep-3.3-developer")

    assert ok
    assert told == {"reason": "software.restored", "name": "NeXTSTEP 3.3 Developer"}
    assert software.catalogue(path) == software.CATALOGUE
    assert software.removed(path) == ()


def test_an_edited_shipped_entry_can_be_brought_back_as_shipped(tmp_path):
    path = tmp_path / "software.json"
    shipped = software.described(software.find("nextstep-3.3-developer"))
    values = {field: shipped[field] for field in software.FIELDS}
    software.save(path, {**values, "version": "3.3-patched"}, replacing="nextstep-3.3-developer")

    ok, _ = software.restore(path, "nextstep-3.3-developer")

    assert ok
    assert software.catalogue(path) == software.CATALOGUE


def test_an_added_entry_is_removed_for_good(tmp_path):
    path = tmp_path / "software.json"
    software.save(path, a_package())

    ok, _ = software.remove(path, "emacs")

    assert ok
    assert listed(path) == ["nextstep-3.3-developer"]
    assert software.removed(path) == ()
    assert software.restore(path, "emacs") == (
        False, {"reason": "software.not-shipped", "asked": "emacs"})


def test_what_is_wrong_with_an_entry_is_said_field_by_field(tmp_path):
    path = tmp_path / "software.json"

    ok, told = software.save(path, a_package(address="http://example.org/x", size=0))

    assert not ok
    assert told == {"reason": "software.refused", "fields": ["address", "size"]}
    assert not path.exists()


def test_a_field_nobody_asked_for_is_refused(tmp_path):
    path = tmp_path / "software.json"

    ok, told = software.save(path, {**a_package(), "identifier": "../../etc"})

    assert not ok
    assert told == {"reason": "software.not-an-entry"}
    assert not path.exists()


def test_a_name_that_is_taken_is_refused(tmp_path):
    """Compared as the identifier the name becomes, and against the shipped
    entries that were removed as well, so bringing one back cannot collide."""
    path = tmp_path / "software.json"
    software.remove(path, "nextstep-3.3-developer")

    ok, told = software.save(path, a_package(name="NeXTSTEP 3.3 developer"))

    assert not ok
    assert told == {"reason": "software.name-taken", "name": "NeXTSTEP 3.3 developer"}


def test_an_entry_keeps_its_identifier_when_it_is_renamed(tmp_path):
    """A downloaded file is named after the identifier, so it does not move."""
    path = tmp_path / "software.json"
    software.save(path, a_package())

    ok, _ = software.save(path, a_package(name="GNU Emacs"), replacing="emacs")

    assert ok
    assert listed(path) == ["nextstep-3.3-developer", "emacs"]
    assert software.find("emacs", path).name == "GNU Emacs"


def test_replacing_what_is_not_there_is_refused(tmp_path):
    ok, told = software.save(tmp_path / "software.json", a_package(), replacing="nothing")

    assert (ok, told) == (False, {"reason": "software.no-such", "asked": "nothing"})


def test_a_file_that_cannot_be_read_refuses_every_change_and_leaves_the_shipped_list(tmp_path):
    """Writing would destroy whatever could not be read, and the shipped list
    is still there to offer."""
    path = tmp_path / "software.json"
    path.write_text("{ not json", encoding="utf-8")

    ok, told = software.save(path, a_package())

    assert not ok
    assert told["reason"] == "software.not-readable"
    assert path.read_text(encoding="utf-8") == "{ not json"
    assert software.catalogue(path) == software.CATALOGUE


def test_an_entry_written_into_the_file_by_hand_is_held_to_the_same_rules(tmp_path):
    path = tmp_path / "software.json"
    path.write_text(
        '{"version": 1, "entries": [{"identifier": "x", "name": "X", "description": "",'
        ' "group": "tools", "version": "1", "systems": ["nextstep-3.3"],'
        ' "address": "https://10.0.0.1/x", "size": 1, "algorithm": "sha1",'
        ' "digest": "' + "a" * 40 + '", "kind": "file"}], "removed": []}',
        encoding="utf-8")

    with pytest.raises(software.NotReadable):
        software.read(path)
    assert software.catalogue(path) == software.CATALOGUE


def test_what_the_service_writes_it_reads_back_whole(tmp_path):
    """Through a restart, which is a second read of the same file."""
    path = tmp_path / "software.json"
    software.save(path, a_package())
    software.remove(path, "nextstep-3.3-developer")

    assert software.read(path) == software.read(path)
    assert listed(path) == ["emacs"]


def test_an_entry_without_a_cover_has_none():
    assert software.problems(an_entry(cover="")) == []


def test_an_entry_written_before_covers_is_read_as_one_without():
    """A file of changes from before the cover existed holds entries without
    the field, and they are entries without a cover rather than a file that
    cannot be read."""
    path = pathlib.Path(tempfile.mkdtemp()) / "software.json"
    path.write_text(json.dumps({"version": 1, "removed": [], "entries": [{
        "identifier": "emacs", "name": "Emacs", "description": "", "group": "tools",
        "version": "21.4", "systems": ["nextstep-3.3"],
        "address": "https://example.org/emacs.tar.gz", "size": 1, "algorithm": "sha1",
        "digest": "a" * 40, "kind": "file"}]}), encoding="utf-8")

    assert software.find("emacs", path).cover == ""


def test_the_shipped_developer_cd_wears_its_folio():
    assert software.find("nextstep-3.3-developer").cover == (
        "https://archive.org/download/NeXTSTEP33CISC/NeXTSTEP%20CD%20Folio_thumb.jpg")


def test_an_entry_with_a_cover_says_where_the_page_gets_it():
    """By the entry and a stamp of the cover's address, so a cover that
    changes is a new address and no browser keeps the old one."""
    described = software.described(an_entry())
    other = software.described(an_entry(cover=an_entry().cover.replace("Folio", "Back")))

    assert described["picture"].startswith("/api/software/cover?entry=nextstep-3.3-developer&v=")
    assert described["picture"] != other["picture"]
    assert software.described(an_entry(cover=""))["picture"] is None
