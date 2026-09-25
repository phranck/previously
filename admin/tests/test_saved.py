"""The configurations somebody saved.

The eleven are a set to go back to and cannot be changed, so everything here is
about the other set: what it is kept as, what a name may be, and what happens to
the file when something goes wrong halfway.
"""

import json

import pytest

from previously import machines, saved


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


def keep(tmp_path, name="Meine Kiste", **wanted):
    """Saves one, and fails the test where it was refused."""
    finished, said = saved.save(tmp_path, name, a_station(**wanted))
    assert finished, said
    return said


# -- reading --------------------------------------------------------------


def test_nothing_is_saved_until_something_is(tmp_path):
    """The ordinary state of a machine nobody has saved anything on, which is
    not an error and not an empty file either."""
    assert saved.read(tmp_path) == ()
    assert not (tmp_path / saved.FILE).exists()


def test_no_state_directory_means_nothing_is_saved(tmp_path):
    assert saved.read(None) == ()


def test_what_was_saved_comes_back_as_a_machine(tmp_path):
    keep(tmp_path)
    kept, = saved.read(tmp_path)

    assert kept.name == "Meine Kiste"
    # The name is the identifier, so there is no second thing to keep in step.
    assert kept.identifier == "Meine Kiste"
    assert kept.kind == machines.NEXTSTATION
    assert kept.turbo is True
    assert kept.colour is True
    assert kept.banks == (32, 32, 32, 32)


def test_they_come_back_in_the_order_they_were_saved(tmp_path):
    for name in ["One", "Two", "Three"]:
        keep(tmp_path, name)

    assert [machine.name for machine in saved.read(tmp_path)] == \
        ["One", "Two", "Three"]


def test_a_saved_configuration_is_settled_when_it_is_read(tmp_path):
    """A file can be edited by hand, and Previous corrects what it finds at
    every start. So what is read here is the machine that would actually run
    rather than what somebody typed."""
    (tmp_path / saved.FILE).write_text(json.dumps({
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

    kept, = saved.read(tmp_path)

    assert kept.colour is False
    # Rounded up to the next size a plain machine takes.
    assert kept.banks == (4, 0, 0, 0)


def test_a_file_that_cannot_be_read_says_so_rather_than_answering_empty(tmp_path):
    """An empty answer would read as nothing having been saved, which is the one
    thing it must not say about a file that is there."""
    (tmp_path / saved.FILE).write_text("{not json at all", encoding="utf-8")

    with pytest.raises(saved.NotReadable):
        saved.read(tmp_path)


def test_a_file_of_the_wrong_shape_is_not_read(tmp_path):
    (tmp_path / saved.FILE).write_text('{"version": 1}', encoding="utf-8")

    with pytest.raises(saved.NotReadable):
        saved.read(tmp_path)


def test_a_configuration_without_a_name_is_not_read(tmp_path):
    """Everything else is corrected rather than refused, because settled()
    decides which values a machine may hold. A name is the one thing nothing can
    be corrected into."""
    (tmp_path / saved.FILE).write_text(json.dumps({
        "version": saved.VERSION,
        "machines": [{"kind": 2, "banks": [16, 16, 0, 0]}],
    }), encoding="utf-8")

    with pytest.raises(saved.NotReadable):
        saved.read(tmp_path)


def test_one_is_found_by_its_identifier(tmp_path):
    keep(tmp_path, "Meine Kiste")

    assert saved.find(tmp_path, "Meine Kiste").name == "Meine Kiste"
    assert saved.find(tmp_path, "Nothing of that name") is None
    assert saved.find(tmp_path, "nextcube-turbo") is None


# -- what a name may be ---------------------------------------------------


def test_a_name_is_needed(tmp_path):
    for nothing in ["", "   ", None]:
        finished, said = saved.save(tmp_path, nothing, a_station())
        assert finished is False
        assert said["reason"] == "saved.name-needed"


def test_a_name_is_trimmed(tmp_path):
    keep(tmp_path, "  Meine Kiste  ")
    kept, = saved.read(tmp_path)

    assert kept.name == "Meine Kiste"


def test_a_name_that_nobody_can_read_the_end_of_is_refused(tmp_path):
    finished, said = saved.save(tmp_path, "N" * (saved.LONGEST_NAME + 1), a_station())

    assert finished is False
    assert said["reason"] == "saved.name-too-long"
    assert said["most"] == saved.LONGEST_NAME


def test_a_name_holding_a_separator_is_refused(tmp_path):
    """The way to it is /Machines/User/<name>, so a separator would read as
    another folder and the way back would lead somewhere that is not there."""
    finished, said = saved.save(tmp_path, "Machines/Mine", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-has-a-separator"


def test_a_name_holding_a_control_character_is_refused(tmp_path):
    finished, said = saved.save(tmp_path, "Meine\nKiste", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-has-a-control-character"


def test_a_name_that_is_taken_is_refused(tmp_path):
    keep(tmp_path, "Meine Kiste")

    finished, said = saved.save(tmp_path, "Meine Kiste", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-taken"
    assert len(saved.read(tmp_path)) == 1


def test_two_names_that_differ_only_in_case_are_one_name(tmp_path):
    """Two icons on a shelf that nobody can tell apart."""
    keep(tmp_path, "Meine Kiste")

    finished, said = saved.save(tmp_path, "meine kiste", a_station())

    assert finished is False
    assert said["reason"] == "saved.name-taken"


def test_a_name_one_of_the_eleven_already_carries_is_refused(tmp_path):
    """The shelf would show two things called the same, and one machine would
    shadow the other wherever one is looked up by name."""
    for taken in ["NeXTcube Turbo", "nextcube-turbo"]:
        finished, said = saved.save(tmp_path, taken, a_station())
        assert finished is False, taken
        assert said["reason"] == "saved.name-taken"


# -- saving over one that was open ----------------------------------------


def test_saving_in_place_keeps_one_configuration(tmp_path):
    """The editor opened a User configuration, so what it saves replaces that
    one rather than standing beside it."""
    keep(tmp_path, "Meine Kiste")

    finished, said = saved.save(
        tmp_path, "Meine Kiste", a_station(turbo=False, banks=[8, 8, 8, 8]),
        replacing="Meine Kiste")

    assert finished is True, said
    kept, = saved.read(tmp_path)
    assert kept.turbo is False
    assert kept.banks == (8, 8, 8, 8)


def test_saving_in_place_under_a_new_name_keeps_one_configuration(tmp_path):
    keep(tmp_path, "Meine Kiste")

    finished, said = saved.save(tmp_path, "Die andere", a_station(),
                                replacing="Meine Kiste")

    assert finished is True, said
    assert [machine.name for machine in saved.read(tmp_path)] == ["Die andere"]


def test_saving_over_one_that_is_not_there_is_refused(tmp_path):
    finished, said = saved.save(tmp_path, "Meine Kiste", a_station(),
                                replacing="Gone")

    assert finished is False
    assert said["reason"] == "saved.no-such"
    assert saved.read(tmp_path) == ()


def test_a_configuration_opened_from_one_of_the_eleven_becomes_a_new_one(tmp_path):
    """Which is the whole of the difference: the eleven cannot be changed, so
    editing one is on its way to being a configuration of one's own."""
    keep(tmp_path, "Meine Kiste")

    finished, _ = saved.save(tmp_path, "Von einem System", a_station())

    assert finished is True
    assert len(saved.read(tmp_path)) == 2


# -- renaming and removing ------------------------------------------------


def test_one_can_be_renamed(tmp_path):
    keep(tmp_path, "Meine Kiste")

    finished, said = saved.rename(tmp_path, "Meine Kiste", "Die andere")

    assert finished is True
    assert said["reason"] == "saved.renamed"
    assert said["was"] == "Meine Kiste"
    kept, = saved.read(tmp_path)
    assert kept.name == "Die andere"
    assert kept.identifier == "Die andere"


def test_renaming_leaves_the_settings_alone(tmp_path):
    keep(tmp_path, "Meine Kiste", banks=[8, 8, 0, 0])
    before, = saved.read(tmp_path)

    saved.rename(tmp_path, "Meine Kiste", "Die andere")
    after, = saved.read(tmp_path)

    assert saved.as_values(after) == saved.as_values(before)


def test_renaming_to_a_name_that_is_taken_is_refused(tmp_path):
    keep(tmp_path, "One")
    keep(tmp_path, "Two")

    finished, said = saved.rename(tmp_path, "One", "Two")

    assert finished is False
    assert said["reason"] == "saved.name-taken"
    assert [machine.name for machine in saved.read(tmp_path)] == ["One", "Two"]


def test_renaming_one_to_what_it_is_already_called_is_not_a_clash(tmp_path):
    keep(tmp_path, "Meine Kiste")

    finished, _ = saved.rename(tmp_path, "Meine Kiste", "Meine Kiste")

    assert finished is True


def test_renaming_something_that_is_not_there_is_refused(tmp_path):
    finished, said = saved.rename(tmp_path, "Gone", "Meine Kiste")

    assert finished is False
    assert said["reason"] == "saved.no-such"


def test_one_can_be_removed(tmp_path):
    keep(tmp_path, "One")
    keep(tmp_path, "Two")

    finished, said = saved.remove(tmp_path, "One")

    assert finished is True
    assert said["reason"] == "saved.removed"
    assert said["name"] == "One"
    assert [machine.name for machine in saved.read(tmp_path)] == ["Two"]


def test_removing_something_that_is_not_there_is_refused(tmp_path):
    keep(tmp_path, "One")

    finished, said = saved.remove(tmp_path, "Gone")

    assert finished is False
    assert said["reason"] == "saved.no-such"
    assert len(saved.read(tmp_path)) == 1


def test_one_of_the_eleven_cannot_be_removed(tmp_path):
    """They are the set to go back to, and this list is not where they live."""
    finished, said = saved.remove(tmp_path, "nextcube-turbo")

    assert finished is False
    assert said["reason"] == "saved.no-such"


# -- what happens when the file is in the way -----------------------------


def test_nothing_is_changed_whilst_the_file_cannot_be_read(tmp_path):
    """Writing would destroy whatever could not be read, so every change refuses
    until somebody has looked at it."""
    broken = "{not json at all"
    (tmp_path / saved.FILE).write_text(broken, encoding="utf-8")

    for finished, said in [
        saved.save(tmp_path, "Meine Kiste", a_station()),
        saved.rename(tmp_path, "Meine Kiste", "Die andere"),
        saved.remove(tmp_path, "Meine Kiste"),
    ]:
        assert finished is False
        assert said["reason"] == "saved.not-readable"
    assert (tmp_path / saved.FILE).read_text(encoding="utf-8") == broken


def test_a_write_that_fails_leaves_the_file_as_it_was(tmp_path, monkeypatch):
    """It is written beside itself and moved into place, so a failure halfway
    holds no half a list."""
    keep(tmp_path, "Meine Kiste")
    before = (tmp_path / saved.FILE).read_text(encoding="utf-8")

    def refuse(*_):
        raise OSError("the card is full")

    monkeypatch.setattr(saved.os, "replace", refuse)
    finished, said = saved.save(tmp_path, "Die andere", a_station())

    assert finished is False
    assert said["reason"] == "saved.could-not-write"
    assert (tmp_path / saved.FILE).read_text(encoding="utf-8") == before
    assert list(tmp_path.glob(saved.FILE + ".new")) == []


def test_the_file_says_what_format_it_is(tmp_path):
    """So a later format has something to tell itself apart by."""
    keep(tmp_path, "Meine Kiste")
    written = json.loads((tmp_path / saved.FILE).read_text(encoding="utf-8"))

    assert written["version"] == saved.VERSION
    assert written["machines"][0]["name"] == "Meine Kiste"
    assert written["machines"][0]["banks"] == [32, 32, 32, 32]


def test_what_is_written_is_what_was_settled(tmp_path):
    """Not what was asked for. A file holding a choice the emulator corrects is
    a file whose name in the interface is not the machine that runs."""
    finished, _ = saved.save(tmp_path, "Ein Kubus",
                             a_station(kind=machines.NEXTCUBE, colour=True))
    assert finished is True

    written = json.loads((tmp_path / saved.FILE).read_text(encoding="utf-8"))
    assert written["machines"][0]["colour"] is False
