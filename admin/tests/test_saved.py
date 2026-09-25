"""The configurations somebody saved.

The eleven are a set to go back to and cannot be changed, so everything here is
about the other set: what it is kept as, what a name may be, and what happens to
the file when something goes wrong halfway.
"""

import json

import pytest

from previously import machines, saved


@pytest.fixture
def machines_file(tmp_path):
    """Where a test keeps its saved configurations.

    A file rather than a directory, and its own per test, because the real one is
    in somebody's home and no test has any business near it.
    """
    return tmp_path / "machines.json"


def a_station(**wanted):
    """The settings of a machine, as the browser sends them and the file holds
    them.

    @param wanted - Whatever this test is about.
    @returns dict
    """
    values = {
        "kind": machines.NEXTSTATION,
        "turbo": True,
        "nitro": False,
        "colour": True,
        "dimension": False,
        "banks": [32, 32, 32, 32],
    }
    values.update(wanted)
    return values


def keep(machines_file, name="Meine Kiste", **wanted):
    """Saves one, and fails the test where it was refused."""
    finished, said = saved.save(machines_file, name, a_station(**wanted))
    assert finished, said
    return said


# -- reading --------------------------------------------------------------


def test_nothing_is_saved_until_something_is(machines_file):
    """The ordinary state of a machine nobody has saved anything on, which is
    not an error and not an empty file either."""
    assert saved.read(machines_file) == ()
    assert not machines_file.exists()


def test_no_state_directory_means_nothing_is_saved(machines_file):
    assert saved.read(None) == ()


def test_what_was_saved_comes_back_as_a_machine(machines_file):
    keep(machines_file)
    kept, = saved.read(machines_file)

    assert kept.name == "Meine Kiste"
    # The name is the identifier, so there is no second thing to keep in step.
    assert kept.identifier == "Meine Kiste"
    assert kept.kind == machines.NEXTSTATION
    assert kept.turbo is True
    assert kept.colour is True
    assert kept.banks == (32, 32, 32, 32)


def test_they_come_back_in_the_order_they_were_saved(machines_file):
    for name in ["One", "Two", "Three"]:
        keep(machines_file, name)

    assert [machine.name for machine in saved.read(machines_file)] == \
        ["One", "Two", "Three"]


def test_a_saved_configuration_is_settled_when_it_is_read(machines_file):
    """A file can be edited by hand, and Previous corrects what it finds at
    every start. So what is read here is the machine that would actually run
    rather than what somebody typed."""
    machines_file.write_text(json.dumps({
        "version": saved.VERSION,
        "machines": [{
            "name": "Hand written",
            "kind": machines.NEXTCUBE,
            # A cube has no colour of its own and Previous forces the flag off.
            "colour": True,
            "turbo": False,
            "banks": [3, 0, 0, 0],
        }],
    }), encoding="utf-8")

    kept, = saved.read(machines_file)

    assert kept.colour is False
    # Rounded up to the next size a plain machine takes.
    assert kept.banks == (4, 0, 0, 0)


def test_a_file_that_cannot_be_read_says_so_rather_than_answering_empty(machines_file):
    """An empty answer would read as nothing having been saved, which is the one
    thing it must not say about a file that is there."""
    machines_file.write_text("{not json at all", encoding="utf-8")

    with pytest.raises(saved.NotReadable):
        saved.read(machines_file)


def test_a_file_of_the_wrong_shape_is_not_read(machines_file):
    machines_file.write_text('{"version": 1}', encoding="utf-8")

    with pytest.raises(saved.NotReadable):
        saved.read(machines_file)


def test_a_configuration_without_a_name_is_not_read(machines_file):
    """Everything else is corrected rather than refused, because settled()
    decides which values a machine may hold. A name is the one thing nothing can
    be corrected into."""
    machines_file.write_text(json.dumps({
        "version": saved.VERSION,
        "machines": [{"kind": 2, "banks": [16, 16, 0, 0]}],
    }), encoding="utf-8")

    with pytest.raises(saved.NotReadable):
        saved.read(machines_file)


def test_one_is_found_by_its_identifier(machines_file):
    keep(machines_file, "Meine Kiste")

    assert saved.find(machines_file, "Meine Kiste").name == "Meine Kiste"
    assert saved.find(machines_file, "Nothing of that name") is None
    assert saved.find(machines_file, "nextcube-turbo") is None


# -- what a name may be ---------------------------------------------------


def test_a_name_is_needed(machines_file):
    for nothing in ["", "   ", None]:
        finished, said = saved.save(machines_file, nothing, a_station())
        assert finished is False
        assert said["reason"] == "saved.name-needed"


def test_a_name_is_trimmed(machines_file):
    keep(machines_file, "  Meine Kiste  ")
    kept, = saved.read(machines_file)

    assert kept.name == "Meine Kiste"


def test_a_name_that_nobody_can_read_the_end_of_is_refused(machines_file):
    finished, said = saved.save(machines_file, "N" * (saved.LONGEST_NAME + 1), a_station())

    assert finished is False
    assert said["reason"] == "saved.name-too-long"
    assert said["most"] == saved.LONGEST_NAME


def test_a_name_holding_a_separator_is_refused(machines_file):
    """The way to it is /Machines/User/<name>, so a separator would read as
    another folder and the way back would lead somewhere that is not there."""
    finished, said = saved.save(machines_file, "Machines/Mine", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-has-a-separator"


def test_a_name_holding_a_control_character_is_refused(machines_file):
    finished, said = saved.save(machines_file, "Meine\nKiste", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-has-a-control-character"


def test_a_name_that_is_taken_is_refused(machines_file):
    keep(machines_file, "Meine Kiste")

    finished, said = saved.save(machines_file, "Meine Kiste", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-taken"
    assert len(saved.read(machines_file)) == 1


def test_two_names_that_differ_only_in_case_are_one_name(machines_file):
    """Two icons on a shelf that nobody can tell apart."""
    keep(machines_file, "Meine Kiste")

    finished, said = saved.save(machines_file, "meine kiste", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-taken"


def test_a_name_one_of_the_eleven_already_carries_is_refused(machines_file):
    """The shelf would show two things called the same, and one machine would
    shadow the other wherever one is looked up by name."""
    for taken in ["NeXTcube Turbo", "nextcube-turbo"]:
        finished, said = saved.save(machines_file, taken, a_station())
        assert finished is False, taken
        assert said["reason"] == "saved.name-taken"


# -- saving over one that was open ----------------------------------------


def test_saving_in_place_keeps_one_configuration(machines_file):
    """The editor opened a User configuration, so what it saves replaces that
    one rather than standing beside it."""
    keep(machines_file, "Meine Kiste")

    finished, said = saved.save(
        machines_file, "Meine Kiste", a_station(turbo=False, banks=[8, 8, 8, 8]),
        replacing="Meine Kiste")

    assert finished is True, said
    kept, = saved.read(machines_file)
    assert kept.turbo is False
    assert kept.banks == (8, 8, 8, 8)


def test_saving_in_place_under_a_new_name_keeps_one_configuration(machines_file):
    keep(machines_file, "Meine Kiste")

    finished, said = saved.save(machines_file, "Die andere", a_station(),
                                replacing="Meine Kiste")

    assert finished is True, said
    assert [machine.name for machine in saved.read(machines_file)] == ["Die andere"]


def test_saving_over_one_that_is_not_there_is_refused(machines_file):
    finished, said = saved.save(machines_file, "Meine Kiste", a_station(),
                                replacing="Gone")

    assert finished is False
    assert said["reason"] == "saved.no-such"
    assert saved.read(machines_file) == ()


def test_a_configuration_opened_from_one_of_the_eleven_becomes_a_new_one(machines_file):
    """Which is the whole of the difference: the eleven cannot be changed, so
    editing one is on its way to being a configuration of one's own."""
    keep(machines_file, "Meine Kiste")

    finished, _ = saved.save(machines_file, "Von einem System", a_station())

    assert finished is True
    assert len(saved.read(machines_file)) == 2


# -- renaming and removing ------------------------------------------------


def test_one_can_be_renamed(machines_file):
    keep(machines_file, "Meine Kiste")

    finished, said = saved.rename(machines_file, "Meine Kiste", "Die andere")

    assert finished is True
    assert said["reason"] == "saved.renamed"
    assert said["was"] == "Meine Kiste"
    kept, = saved.read(machines_file)
    assert kept.name == "Die andere"
    assert kept.identifier == "Die andere"


def test_renaming_leaves_the_settings_alone(machines_file):
    keep(machines_file, "Meine Kiste", banks=[8, 8, 0, 0])
    before, = saved.read(machines_file)

    saved.rename(machines_file, "Meine Kiste", "Die andere")
    after, = saved.read(machines_file)

    assert saved.as_values(after) == saved.as_values(before)


def test_renaming_to_a_name_that_is_taken_is_refused(machines_file):
    keep(machines_file, "One")
    keep(machines_file, "Two")

    finished, said = saved.rename(machines_file, "One", "Two")

    assert finished is False
    assert said["reason"] == "saved.name-taken"
    assert [machine.name for machine in saved.read(machines_file)] == ["One", "Two"]


def test_renaming_one_to_what_it_is_already_called_is_not_a_clash(machines_file):
    keep(machines_file, "Meine Kiste")

    finished, _ = saved.rename(machines_file, "Meine Kiste", "Meine Kiste")

    assert finished is True


def test_renaming_something_that_is_not_there_is_refused(machines_file):
    finished, said = saved.rename(machines_file, "Gone", "Meine Kiste")

    assert finished is False
    assert said["reason"] == "saved.no-such"


def test_one_can_be_removed(machines_file):
    keep(machines_file, "One")
    keep(machines_file, "Two")

    finished, said = saved.remove(machines_file, "One")

    assert finished is True
    assert said["reason"] == "saved.removed"
    assert said["name"] == "One"
    assert [machine.name for machine in saved.read(machines_file)] == ["Two"]


def test_removing_something_that_is_not_there_is_refused(machines_file):
    keep(machines_file, "One")

    finished, said = saved.remove(machines_file, "Gone")

    assert finished is False
    assert said["reason"] == "saved.no-such"
    assert len(saved.read(machines_file)) == 1


def test_one_of_the_eleven_cannot_be_removed(machines_file):
    """They are the set to go back to, and this list is not where they live."""
    finished, said = saved.remove(machines_file, "nextcube-turbo")

    assert finished is False
    assert said["reason"] == "saved.no-such"


# -- what happens when the file is in the way -----------------------------


def test_nothing_is_changed_whilst_the_file_cannot_be_read(machines_file):
    """Writing would destroy whatever could not be read, so every change refuses
    until somebody has looked at it."""
    broken = "{not json at all"
    machines_file.write_text(broken, encoding="utf-8")

    for finished, said in [
        saved.save(machines_file, "Meine Kiste", a_station()),
        saved.rename(machines_file, "Meine Kiste", "Die andere"),
        saved.remove(machines_file, "Meine Kiste"),
    ]:
        assert finished is False
        assert said["reason"] == "saved.not-readable"
    assert machines_file.read_text(encoding="utf-8") == broken


def test_a_write_that_fails_leaves_the_file_as_it_was(machines_file, monkeypatch):
    """It is written beside itself and moved into place, so a failure halfway
    holds no half a list."""
    keep(machines_file, "Meine Kiste")
    before = machines_file.read_text(encoding="utf-8")

    def refuse(*_):
        raise OSError("the card is full")

    monkeypatch.setattr(saved.os, "replace", refuse)
    finished, said = saved.save(machines_file, "Die andere", a_station())

    assert finished is False
    assert said["reason"] == "saved.could-not-write"
    assert machines_file.read_text(encoding="utf-8") == before
    assert list(machines_file.parent.glob(machines_file.name + ".new")) == []


def test_the_file_says_what_format_it_is(machines_file):
    """So a later format has something to tell itself apart by."""
    keep(machines_file, "Meine Kiste")
    written = json.loads(machines_file.read_text(encoding="utf-8"))

    assert written["version"] == saved.VERSION
    assert written["machines"][0]["name"] == "Meine Kiste"
    assert written["machines"][0]["banks"] == [32, 32, 32, 32]


def test_what_is_written_is_what_was_settled(machines_file):
    """Not what was asked for. A file holding a choice the emulator corrects is
    a file whose name in the interface is not the machine that runs."""
    finished, _ = saved.save(machines_file, "Ein Kubus",
                             a_station(kind=machines.NEXTCUBE, colour=True))
    assert finished is True

    written = json.loads(machines_file.read_text(encoding="utf-8"))
    assert written["machines"][0]["colour"] is False
