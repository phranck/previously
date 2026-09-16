"""Taking a picture of the emulated screen.

The emulator is not here, so what is tested is everything around it: which file
counts as the picture, what happens to it afterwards, and what is answered when
there is no picture to be had. The one thing that cannot be faked, that the
shortcut reaches Previous at all, was measured on the machine and is written
down in the issue rather than pretended at here.
"""

import re

import pytest

from previously import grab

#: A PNG, as far as anything here is concerned.
PICTURE = grab.PNG_HEAD + b"and then some pixels" + grab.PNG_TAIL


@pytest.fixture
def where(tmp_path, monkeypatch):
    """A directory standing in for the one the emulator writes into."""
    monkeypatch.setattr(grab, "working_directory", lambda: tmp_path)
    return tmp_path


def writes(where, name=None, content=PICTURE):
    """What the emulator does when the keys reach it."""
    def press(keys):
        (where / (name or "next_screen_000.png")).write_bytes(content)
        return True
    return press


def test_the_picture_is_the_file_the_emulator_just_wrote(where, monkeypatch):
    monkeypatch.setattr(grab.screen, "press", writes(where))

    assert grab.grabbed() == PICTURE


def test_the_picture_is_taken_away_once_it_has_been_read(where, monkeypatch):
    """A directory that fills up with these is this service's doing."""
    monkeypatch.setattr(grab.screen, "press", writes(where))

    grab.grabbed()

    assert list(where.glob(grab.GRAB_GLOB)) == []


def test_a_grab_that_was_already_there_is_not_this_picture(where, monkeypatch):
    """Previous counts its grabs up rather than overwriting, so an older one
    beside the new one is somebody else's and stays where it is."""
    older = where / "next_screen_000.png"
    older.write_bytes(grab.PNG_HEAD + b"an older one" + grab.PNG_TAIL)
    monkeypatch.setattr(grab.screen, "press", writes(where, "next_screen_001.png"))

    picture = grab.grabbed()

    assert picture == PICTURE
    assert older.exists()


def test_nothing_comes_of_a_shortcut_that_was_not_sent(where, monkeypatch):
    monkeypatch.setattr(grab.screen, "press", lambda keys: False)

    assert grab.grabbed() is None


def test_nothing_comes_of_an_emulator_that_wrote_nothing(where, monkeypatch):
    """The key was sent and no file appeared, which is what a shortcut that
    reaches the wrong window looks like."""
    monkeypatch.setattr(grab, "GRAB_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(grab.screen, "press", lambda keys: True)

    assert grab.grabbed() is None


def test_nothing_comes_of_an_emulator_that_is_not_running(monkeypatch):
    monkeypatch.setattr(grab, "working_directory", lambda: None)
    monkeypatch.setattr(grab.screen, "press",
                        lambda keys: pytest.fail("nothing to press at"))

    assert grab.grabbed() is None


def test_a_grab_that_cannot_be_removed_is_still_the_picture(where, monkeypatch):
    """The emulator's own directory is one this service may not be able to
    write in, and a picture already read is a picture either way."""
    monkeypatch.setattr(grab.screen, "press", writes(where))
    monkeypatch.setattr(grab.pathlib.Path, "unlink",
                        lambda self, **how: (_ for _ in ()).throw(PermissionError()))

    assert grab.grabbed() == PICTURE


def test_the_window_is_photographed_when_the_grab_gives_nothing(monkeypatch):
    """The smaller picture, and the reason it is here."""
    monkeypatch.setattr(grab, "grabbed", lambda: None)
    monkeypatch.setattr(grab, "photographed", lambda: b"the window")

    assert grab.take() == b"the window"


def test_the_grab_is_preferred_to_the_photograph(monkeypatch):
    monkeypatch.setattr(grab, "grabbed", lambda: PICTURE)
    monkeypatch.setattr(grab, "photographed",
                        lambda: pytest.fail("the grab already answered"))

    assert grab.take() == PICTURE


def test_no_picture_at_all_is_an_honest_nothing(monkeypatch):
    monkeypatch.setattr(grab, "grabbed", lambda: None)
    monkeypatch.setattr(grab, "photographed", lambda: None)

    assert grab.take() is None


def test_a_directory_this_cannot_write_in_is_left_alone(where, monkeypatch):
    """A picture read and left on the disk is one this service put there, and
    at one per press the directory fills up. Where it cannot tidy up it does
    not grab at all, and the window is photographed instead."""
    monkeypatch.setattr(grab.os, "access", lambda path, mode: False)
    monkeypatch.setattr(grab.screen, "press",
                        lambda keys: pytest.fail("nowhere to put the picture"))

    assert grab.grabbed() is None


def test_a_picture_still_being_written_is_not_the_picture(where, monkeypatch):
    """The file exists from its first byte and the emulator goes on filling
    it. Measured on the machine: 32768 bytes of a 62287 byte grab, which a
    browser draws half of."""
    monkeypatch.setattr(grab, "GRAB_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(grab.screen, "press",
                        writes(where, content=grab.PNG_HEAD + b"half of it"))

    assert grab.grabbed() is None


def test_a_picture_is_whole_once_it_carries_its_last_chunk(where, monkeypatch):
    whole = grab.PNG_HEAD + b"pixels" + grab.PNG_TAIL
    monkeypatch.setattr(grab.screen, "press", writes(where, content=whole))

    assert grab.grabbed() == whole


def test_something_that_is_not_a_png_at_all_is_not_the_picture(where, monkeypatch):
    monkeypatch.setattr(grab, "GRAB_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(grab.screen, "press",
                        writes(where, content=b"not a picture" + grab.PNG_TAIL))

    assert grab.grabbed() is None


# -- keeping a picture ----------------------------------------------------


def test_a_picture_is_written_where_pictures_are_kept(tmp_path):
    kept = grab.keep(PICTURE, tmp_path / "Documents" / "Pictures")

    assert kept.read_bytes() == PICTURE
    assert kept.parent == tmp_path / "Documents" / "Pictures"


def test_a_picture_is_kept_as_it_was_taken(tmp_path):
    """These are looked at in the admin rather than in NeXTSTEP, so they are
    PNG, which is what a browser reads and what keeps a screen sharp."""
    kept = grab.keep(PICTURE, tmp_path)

    assert kept.suffix == ".png"
    assert kept.read_bytes() == PICTURE


def test_the_folder_is_made_where_it_is_not_there(tmp_path):
    """A fresh card has never been photographed, so the first picture is what
    creates the place it goes."""
    where = tmp_path / "Previously" / "Documents" / "Pictures"

    grab.keep(PICTURE, where)

    assert where.is_dir()


def test_a_picture_is_named_for_the_moment_it_was_taken(tmp_path):
    """Two pictures of the same screen are told apart by when they were
    taken, and by nothing else."""
    kept = grab.keep(PICTURE, tmp_path)

    assert re.fullmatch(r"Screen \d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}\.png", kept.name)


def test_a_folder_that_cannot_be_written_in_is_not_an_error(tmp_path):
    """The picture has been taken either way, and the browser gets it. Only
    the copy on the card is lost."""
    in_the_way = tmp_path / "Pictures"
    in_the_way.write_text("a file where the folder should be")

    assert grab.keep(PICTURE, in_the_way) is None
