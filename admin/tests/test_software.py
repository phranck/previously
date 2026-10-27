"""The software catalog: what it offers, and what an entry has to be.

Every entry names an address on somebody else's server, and later a fetch
refuses anything that arrives as other than the entry says. So the entries are
held here to the shape that fetch relies on, and the shipped list is held to it
like any entry somebody adds.
"""

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
    )
    fields.update(changed)
    return software.Entry(**fields)


def test_a_well_formed_entry_has_no_problems():
    assert software.problems(an_entry()) == []


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
