"""Taking a picture of the emulated screen.

The emulator is not here, so what is tested is everything around it: which file
counts as the picture, what happens to it afterwards, and what is answered when
there is no picture to be had. The one thing that cannot be faked, that the
shortcut reaches Previous at all, was measured on the machine and is written
down in the issue rather than pretended at here.
"""

import os
import pathlib
import re
import time

import pytest

from previously import grab

#: A PNG, as far as anything here is concerned.
PICTURE = grab.PNG_HEAD + b"and then some pixels" + grab.PNG_TAIL

#: Grabs Previous wrote on a Pi 5 on 23.10.2026, which `test_png.py` describes.
GRABS = pathlib.Path(__file__).resolve().parent / "grabs"


#: What the emulator's configuration is called in each test's directory.
CONFIGURATION = "previous.cfg"


@pytest.fixture
def where(tmp_path, monkeypatch):
    """A directory standing in for the one the emulator writes into, named in
    a configuration beside it the way `setup.py` names it on the Pi."""
    monkeypatch.setattr(grab.emulator, "pid", lambda: 1)
    (tmp_path / CONFIGURATION).write_text(
        "[Printer]\nszPrintToFileName = %s\n" % tmp_path)
    return tmp_path


def writes(where, name=None, content=PICTURE):
    """What the emulator does when the keys reach it."""
    def press(keys):
        (where / (name or "next_screen_000.png")).write_bytes(content)
        return True
    return press


def test_the_picture_is_the_file_the_emulator_just_wrote(where, monkeypatch):
    monkeypatch.setattr(grab.emulator, "press", writes(where))

    assert grab.grabbed(where / CONFIGURATION) == PICTURE


def test_the_picture_is_taken_away_once_it_has_been_read(where, monkeypatch):
    """A directory that fills up with these is this service's doing."""
    monkeypatch.setattr(grab.emulator, "press", writes(where))

    grab.grabbed(where / CONFIGURATION)

    assert list(where.glob(grab.GRAB_GLOB)) == []


def test_a_grab_that_was_already_there_is_not_this_picture(where, monkeypatch):
    """Previous counts its grabs up rather than overwriting, so an older one
    beside the new one is somebody else's and stays where it is."""
    older = where / "next_screen_000.png"
    older.write_bytes(grab.PNG_HEAD + b"an older one" + grab.PNG_TAIL)
    monkeypatch.setattr(grab.emulator, "press", writes(where, "next_screen_001.png"))

    picture = grab.grabbed(where / CONFIGURATION)

    assert picture == PICTURE
    assert older.exists()


def aged(path, seconds):
    """Makes a file look as if the emulator wrote it that many seconds ago."""
    then = time.time() - seconds
    os.utime(path, (then, then))


def test_a_grab_that_arrived_after_its_grab_gave_up_goes_with_the_next_one(
        where, monkeypatch):
    """The grab that asked for it answered with nothing once the timeout had
    passed, and to every grab after it the file is already there, so nothing
    else would ever remove it. Two stayed in ~/.cache/previously on a Pi 5 on
    23.10.2026 that way."""
    late = where / "next_screen_000.png"
    late.write_bytes(grab.PNG_HEAD + b"a late one" + grab.PNG_TAIL)
    aged(late, grab.GRAB_TIMEOUT_SECONDS + 1)
    monkeypatch.setattr(grab.emulator, "press", writes(where, "next_screen_001.png"))

    picture = grab.grabbed(where / CONFIGURATION)

    assert picture == PICTURE
    assert list(where.glob(grab.GRAB_GLOB)) == []


def test_a_grab_that_gives_up_leaves_nothing_once_its_file_arrives(where, monkeypatch):
    """The whole of it: the keys land, nothing arrives in time, the emulator
    writes the file later all the same, and the grab after that takes it
    away with its own."""
    monkeypatch.setattr(grab, "GRAB_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(grab.emulator, "press", lambda keys: True)
    assert grab.grabbed(where / CONFIGURATION) is None

    late = where / "next_screen_000.png"
    late.write_bytes(PICTURE)
    aged(late, 1)
    monkeypatch.setattr(grab.emulator, "press", writes(where, "next_screen_001.png"))

    assert grab.grabbed(where / CONFIGURATION) == PICTURE
    assert list(where.glob(grab.GRAB_GLOB)) == []


def test_a_grab_under_the_name_just_swept_is_the_picture(where, monkeypatch):
    """Previous names a grab by the lowest number not taken, so the file the
    next grab writes takes the name of the one just swept. Counted before the
    sweep, that name read as already there, and four grabs on next4 on
    26.10.2026 answered nothing while their picture lay there whole."""
    stale = where / "next_screen_000.png"
    stale.write_bytes(grab.PNG_HEAD + b"swept" + grab.PNG_TAIL)
    aged(stale, grab.GRAB_TIMEOUT_SECONDS + 1)
    monkeypatch.setattr(grab.emulator, "press", writes(where, "next_screen_000.png"))

    picture = grab.grabbed(where / CONFIGURATION)

    assert picture == PICTURE
    assert list(where.glob(grab.GRAB_GLOB)) == []


def test_nothing_comes_of_a_shortcut_that_was_not_sent(where, monkeypatch):
    monkeypatch.setattr(grab.emulator, "press", lambda keys: False)

    assert grab.grabbed(where / CONFIGURATION) is None


def test_nothing_comes_of_an_emulator_that_wrote_nothing(where, monkeypatch):
    """The key was sent and no file appeared, which is what a shortcut that
    reaches the wrong window looks like."""
    monkeypatch.setattr(grab, "GRAB_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(grab.emulator, "press", lambda keys: True)

    assert grab.grabbed(where / CONFIGURATION) is None


def test_nothing_comes_of_an_emulator_that_is_not_running(where, monkeypatch):
    monkeypatch.setattr(grab.emulator, "pid", lambda: None)
    monkeypatch.setattr(grab.emulator, "press",
                        lambda keys: pytest.fail("nothing to press at"))

    assert grab.grabbed(where / CONFIGURATION) is None


def test_the_picture_is_looked_for_where_previous_is_told_to_write_it(
        where, monkeypatch):
    """Previous writes a grab into its printer's directory, which is the home
    unless its configuration names another. The directory it runs in has
    nothing to do with it. Measured on a Pi 4 and a Pi 5 on 22.10.2026: the
    emulator ran in ~/.cache/previously and wrote its grab into the home."""
    sent = where / "grabs"
    sent.mkdir()
    (where / CONFIGURATION).write_text("[Printer]\nszPrintToFileName = %s\n" % sent)
    monkeypatch.setattr(grab.emulator, "press", writes(sent))

    assert grab.grabbed(where / CONFIGURATION) == PICTURE
    assert list(sent.glob(grab.GRAB_GLOB)) == []


def test_a_configuration_that_names_no_directory_grabs_into_the_home(
        where, monkeypatch):
    """Which this service may not write in, so it asks nothing of the emulator
    and the home stays as it was."""
    home = where / "home"
    monkeypatch.setattr(grab.pathlib.Path, "home", lambda: home)
    (where / CONFIGURATION).write_text("[Printer]\nbPrinterConnected = FALSE\n")
    asked = []
    monkeypatch.setattr(grab.os, "access",
                        lambda path, mode: asked.append(path) or False)
    monkeypatch.setattr(grab.emulator, "press",
                        lambda keys: pytest.fail("the home would keep the picture"))

    assert grab.grabbed(where / CONFIGURATION) is None
    assert asked == [home]


def test_a_grab_that_cannot_be_removed_is_still_the_picture(where, monkeypatch):
    """The emulator's own directory is one this service may not be able to
    write in, and a picture already read is a picture either way."""
    monkeypatch.setattr(grab.emulator, "press", writes(where))
    monkeypatch.setattr(grab.pathlib.Path, "unlink",
                        lambda self, **how: (_ for _ in ()).throw(PermissionError()))

    assert grab.grabbed(where / CONFIGURATION) == PICTURE


def test_a_directory_this_cannot_write_in_is_left_alone(where, monkeypatch):
    """A picture read and left on the disk is one this service put there, and
    at one per press the directory fills up. Where it cannot tidy up it does
    not grab at all."""
    monkeypatch.setattr(grab.os, "access", lambda path, mode: False)
    monkeypatch.setattr(grab.emulator, "press",
                        lambda keys: pytest.fail("nowhere to put the picture"))

    assert grab.grabbed(where / CONFIGURATION) is None


def test_a_picture_still_being_written_is_not_the_picture(where, monkeypatch):
    """The file exists from its first byte and the emulator goes on filling
    it. Measured on the machine: 32768 bytes of a 62287 byte grab, which a
    browser draws half of."""
    monkeypatch.setattr(grab, "GRAB_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(grab.emulator, "press",
                        writes(where, content=grab.PNG_HEAD + b"half of it"))

    assert grab.grabbed(where / CONFIGURATION) is None


def test_a_picture_is_whole_once_it_carries_its_last_chunk(where, monkeypatch):
    whole = grab.PNG_HEAD + b"pixels" + grab.PNG_TAIL
    monkeypatch.setattr(grab.emulator, "press", writes(where, content=whole))

    assert grab.grabbed(where / CONFIGURATION) == whole


def test_something_that_is_not_a_png_at_all_is_not_the_picture(where, monkeypatch):
    monkeypatch.setattr(grab, "GRAB_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(grab.emulator, "press",
                        writes(where, content=b"not a picture" + grab.PNG_TAIL))

    assert grab.grabbed(where / CONFIGURATION) is None


# -- whether the screen shows anything ------------------------------------


def grabbing(monkeypatch, picture):
    """Lets the emulator answer a grab with these bytes, or with nothing."""
    monkeypatch.setattr(grab, "grabbed", lambda previous_config: picture)


def test_a_screen_with_something_on_it_is_alive(monkeypatch):
    grabbing(monkeypatch, (GRABS / "workspace.png").read_bytes())

    assert grab.looks_alive(CONFIGURATION) is True


def test_a_screen_in_color_is_read_as_well(monkeypatch):
    grabbing(monkeypatch, (GRABS / "dimension.png").read_bytes())

    assert grab.looks_alive(CONFIGURATION) is True


def test_a_screen_of_one_color_is_not(monkeypatch):
    """A machine that shows nothing. Grabbed on a Pi 5 on 23.10.2026 from a
    NeXTcube with NeXTdimension whose window showed the main screen while its
    console was on the board."""
    grabbing(monkeypatch, (GRABS / "blank.png").read_bytes())

    assert grab.looks_alive(CONFIGURATION) is False


def test_no_grab_means_no_reading(monkeypatch):
    """Not False: a screen that was not read is not a blank one."""
    grabbing(monkeypatch, None)

    assert grab.looks_alive(CONFIGURATION) is None


def test_a_grab_that_cannot_be_read_is_no_reading(monkeypatch):
    grabbing(monkeypatch, PICTURE)

    assert grab.looks_alive(CONFIGURATION) is None


def test_without_a_configuration_nothing_is_grabbed(monkeypatch):
    monkeypatch.setattr(grab, "grabbed",
                        lambda previous_config: pytest.fail("nowhere to look"))

    assert grab.looks_alive(None) is None


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
