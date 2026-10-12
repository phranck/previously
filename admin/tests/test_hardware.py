"""Which board the service runs on.

The fixtures are the bytes the device tree holds: the names in `compatible`
each end in a null, and so does the model. The Pi 5's are the ones next.local
answered with on 12 October 2026.
"""

import re

import pytest

from conftest import INTERFACE
from previously import hardware

#: Where the drawings are, and the stylesheet that names them for the page.
PARTS = INTERFACE.parent / "web" / "parts"
KIT_STYLES = INTERFACE / "nextstep.css"


@pytest.fixture
def device_tree(monkeypatch, tmp_path):
    """Points the module at a device tree of the test's own and lets the test
    say what it holds.

    @returns A function taking the names of `compatible`, or None to leave the
      file out.
    """
    monkeypatch.setattr(hardware, "COMPATIBLE", tmp_path / "compatible")
    monkeypatch.setattr(hardware, "MODEL", tmp_path / "model")

    def holding(*names):
        (tmp_path / "compatible").write_bytes(b"".join(name.encode() + b"\x00" for name in names))

    return holding


def test_the_names_come_out_in_the_order_the_device_tree_gives_them(device_tree):
    device_tree("raspberrypi,5-model-b", "brcm,bcm2712")

    assert hardware.compatible() == ["raspberrypi,5-model-b", "brcm,bcm2712"]


def test_no_device_tree_names_nothing(device_tree):
    assert hardware.compatible() is None
    assert hardware.board() is None


def test_an_empty_compatible_names_nothing(device_tree):
    device_tree()

    assert hardware.compatible() is None


@pytest.mark.parametrize("names, board", [
    (("raspberrypi,4-model-b", "brcm,bcm2711"), "pi4"),
    (("raspberrypi,4-compute-module", "brcm,bcm2711"), "cm4"),
    (("raspberrypi,5-model-b", "brcm,bcm2712"), "pi5"),
    # A Compute Module 5 Lite carries the Compute Module 5's name.
    (("raspberrypi,5-compute-module", "brcm,bcm2712"), "cm5"),
])
def test_a_board_it_knows_is_named(device_tree, names, board):
    device_tree(*names)

    assert hardware.board() == board


@pytest.mark.parametrize("names", [
    ("raspberrypi,400", "brcm,bcm2711"),
    ("raspberrypi,500", "brcm,bcm2712"),
    ("raspberrypi,4-compute-module-s", "brcm,bcm2711"),
    ("radxa,rock-5b", "rockchip,rk3588"),
])
def test_a_board_it_does_not_know_is_not_named(device_tree, names):
    """Not even by the processor the list ends on: a Pi 400 has a Pi 4's chip
    and is not a Pi 4."""
    device_tree(*names)

    assert hardware.board() is None


def test_the_most_specific_name_it_knows_decides(device_tree):
    """A revision lists its own name before its family's, so an entry for the
    family covers every revision that comes after it."""
    device_tree("raspberrypi,5-model-b-rev2", "raspberrypi,5-model-b", "brcm,bcm2712")

    assert hardware.board() == "pi5"


def test_the_model_loses_the_null_it_ends_in(device_tree, tmp_path):
    (tmp_path / "model").write_bytes(b"Raspberry Pi 5 Model B Rev 1.1\x00")

    assert hardware.model() == "Raspberry Pi 5 Model B Rev 1.1"


def test_no_model_is_not_invented(device_tree):
    assert hardware.model() is None


@pytest.mark.parametrize("board", sorted(set(hardware.BOARDS.values())))
def test_every_board_it_names_has_a_drawing_the_page_can_reach(board):
    """The page shows the drawing named after the board, through a property
    the kit's stylesheet names. A board named here without both would stand in
    its window as an empty box."""
    assert (PARTS / f"board-{board}.svg").is_file()
    assert re.search(rf'--board-{board}: url\("parts/board-{board}\.svg"\);',
                     KIT_STYLES.read_text(encoding="utf-8"))
