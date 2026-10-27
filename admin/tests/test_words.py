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

from previously import config, machines

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


@pytest.mark.parametrize("board, drawing", [
    ("pi4", "board-pi4"),
    ("pi5", "board-pi5"),
    ("cm4", "board-cm4"),
    ("cm5", "board-cm5"),
    # A board the service does not know, which wears the Pi 5.
    (None, "board-pi5"),
])
def test_the_board_wears_the_drawing_named_after_it(board, drawing):
    assert said({"call": "boardArt", "with": [board]}) == drawing


def test_room_a_restart_gives_back_is_said_in_sizes_as_well():
    sentence = said({"reason": "setup.no-room-until-restart",
                     "name": "NeXTSTEP 3.3", "free": 2_076_180_480,
                     "needed": 3_139_122_432, "back": 2_147_487_744})

    assert sentence == ("There is not enough room for NeXTSTEP 3.3 yet: it "
                        "needs 3.1 GB and 2.1 GB is free. Restarting the Pi "
                        "frees the 2.1 GB its swap file takes, so restart it "
                        "and try again.")


@pytest.mark.parametrize("machine", machines.CATALOGUE,
                         ids=lambda machine: machine.identifier)
def test_every_shipped_machine_is_named_as_the_info_window_names_it(machine):
    """A machine's name is shown as it is in every language, and the Info
    window and the Config Editor build their own out of the facts the service
    sends: the model, the turbo board, the color board, the Nitro and a
    NeXTdimension. The two stand on one screen, so the catalog's name is held
    to the form `nameOf` makes of what `config.describe` says of the machine."""
    settings = machines.settings_for(machine)
    described = config.describe(
        settings["System"], settings["Memory"], settings["Dimension"])

    assert said({"call": "nameOf", "with": [described]}) == machine.name
