"""What the service's answers turn into, run rather than read.

`words.js` is where an answer from the service becomes a sentence, whichever
window it reaches. So node runs it against `words_page.mjs`, and this reads the
sentence that comes out.
"""

import json
import pathlib
import shutil
import subprocess

import pytest

#: The little page that lets node run it.
PAGE = pathlib.Path(__file__).resolve().parent / "words_page.mjs"


def said(answer):
    """@returns str - The English sentence the page makes of one answer."""
    if shutil.which("node") is None:
        pytest.skip("node is not on this machine")

    run = subprocess.run(
        ["node", str(PAGE)], input=json.dumps(answer), capture_output=True,
        text=True, timeout=30, check=False)
    assert run.returncode == 0, run.stderr
    return run.stdout.strip()


def test_a_card_with_no_room_is_said_in_sizes_a_person_reads():
    """The service sends bytes, because how a size is written is a question
    about the language it is read in. A run that failed and a request the
    service refused carry the same answer, so both read the same."""
    sentence = said({"reason": "setup.no-room", "name": "NeXTSTEP 3.3",
                     "free": 2_069_880_832, "needed": 3_283_261_670})

    assert sentence == ("There is not enough room for NeXTSTEP 3.3: "
                        "it needs 3.3 GB and 2.1 GB is free.")


@pytest.mark.parametrize("used, total, figure", [
    # A 4 GB Pi 5 reports 4049 MB, and that is the board it was sold as.
    (512, 4049, "0.5/4.0 GB"),
    (12345, 16218, "12.1/15.8 GB"),
    (300, 900, "300/900 MB"),
])
def test_memory_in_use_is_said_the_short_way(used, total, figure):
    """Activity Monitor writes it beside a row of lamps, where a five digit
    count of megabytes does not fit and does not read at a glance."""
    assert said({"call": "memoryInUse", "with": [used, total]}) == figure


def test_memory_that_was_not_read_is_said_as_nothing():
    assert said({"call": "memoryInUse", "with": [None, 4049]}) == "\N{EM DASH}"


@pytest.mark.parametrize("model, drawing", [
    # As the firmware names a running board, and as the device tree does.
    ("Raspberry Pi 4 Model B Rev 1.5", "board-pi4"),
    ("Raspberry Pi 5 Model B Rev 1.1", "board-pi5"),
    ("Raspberry Pi Compute Module 4 Rev 1.1", "board-cm4"),
    ("Raspberry Pi Compute Module 5 Rev 1.0", "board-cm5"),
    ("Raspberry Pi Compute Module 5 Lite Rev 1.0", "board-cm5"),
    # Boards none of the four drawings is of, which wear the Pi 5.
    ("Raspberry Pi 400 Rev 1.0", "board-pi5"),
    ("Raspberry Pi 500 Rev 1.0", "board-pi5"),
    ("Raspberry Pi Compute Module 4S Rev 1.0", "board-pi5"),
    ("Raspberry Pi 3 Model B Plus Rev 1.3", "board-pi5"),
    (None, "board-pi5"),
])
def test_the_board_wears_the_drawing_of_its_model(model, drawing):
    assert said({"call": "boardArt", "with": [model]}) == drawing


def test_room_a_restart_gives_back_is_said_in_sizes_as_well():
    sentence = said({"reason": "setup.no-room-until-restart",
                     "name": "NeXTSTEP 3.3", "free": 2_076_180_480,
                     "needed": 3_139_122_432, "back": 2_147_487_744})

    assert sentence == ("There is not enough room for NeXTSTEP 3.3 yet: it "
                        "needs 3.1 GB and 2.1 GB is free. Restarting the Pi "
                        "frees the 2.1 GB its swap file takes, so restart it "
                        "and try again.")
