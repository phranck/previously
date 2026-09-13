"""What the board underneath is doing.

The fixtures are the exact strings the machine produced on 13 September 2026,
so what is parsed here is what actually comes out rather than what a format
description suggests.
"""

import pytest

from previously import pi


@pytest.fixture
def answers(monkeypatch):
    """Lets a test say what each command replies."""
    said = {}

    def ask(command):
        return said.get(tuple(command), "")

    monkeypatch.setattr(pi, "_ask", ask)
    return said


# -- temperature ---------------------------------------------------------


def test_the_temperature_comes_out_as_a_number(answers):
    """vcgencmd puts an apostrophe where a degree sign would go."""
    answers[("vcgencmd", "measure_temp")] = "temp=52.1'C"
    assert pi._temperature() == 52.1


def test_no_vcgencmd_means_no_temperature(answers):
    assert pi._temperature() is None


# -- throttling ----------------------------------------------------------


def test_a_quiet_board_reports_nothing(answers):
    answers[("vcgencmd", "get_throttled")] = "throttled=0x0"
    assert pi._throttling() == {"raw": 0, "now": [], "since_boot": []}


def test_what_this_machine_actually_said(answers):
    """0x50000 is what it read after a drive drew more than the port could
    give. Bit 16 and bit 18, both in the half that means since the last boot."""
    answers[("vcgencmd", "get_throttled")] = "throttled=0x50000"

    answer = pi._throttling()

    assert answer["now"] == []
    assert sorted(answer["since_boot"]) == ["Unterspannung", "gedrosselt"]


def test_something_happening_now_is_kept_apart_from_something_that_did(answers):
    """A problem now is a problem. One that happened once may have been the
    moment somebody plugged a drive in."""
    answers[("vcgencmd", "get_throttled")] = "throttled=0x50005"

    answer = pi._throttling()

    assert sorted(answer["now"]) == ["Unterspannung", "gedrosselt"]
    assert sorted(answer["since_boot"]) == ["Unterspannung", "gedrosselt"]


def test_every_bit_that_is_named_is_read(answers):
    answers[("vcgencmd", "get_throttled")] = "throttled=0xF000F"

    answer = pi._throttling()

    assert len(answer["now"]) == 4
    assert len(answer["since_boot"]) == 4


# -- the emulator --------------------------------------------------------


def test_the_emulator_is_read_from_ps(answers):
    """etimes, pcpu and rss, which is what the machine answered."""
    answers[("ps", "-o", "etimes=,pcpu=,rss=", "-C", "previous")] = "4823  135 321856"

    assert pi._emulator() == {
        "uptime_seconds": 4823, "cpu_percent": 135.0, "memory_mb": 314,
    }


def test_no_emulator_is_not_an_error(answers):
    assert pi._emulator() is None


def test_something_ps_could_not_answer_is_not_invented(answers):
    answers[("ps", "-o", "etimes=,pcpu=,rss=", "-C", "previous")] = "nonsense here too"
    assert pi._emulator() is None


# -- sound ---------------------------------------------------------------


def make_card(root, number, name, state):
    """A sound card as /proc/asound presents one."""
    card = root / ("card%d" % number)
    (card / "pcm0p" / "sub0").mkdir(parents=True)
    (card / "id").write_text(name + "\n")
    (card / "pcm0p" / "sub0" / "status").write_text(state + "\n")
    return card


def test_the_card_that_is_playing_is_the_one_reported(tmp_path, monkeypatch):
    """Three cards, and the one with a stream open is the answer."""
    make_card(tmp_path, 0, "UACDemoV10", "state: RUNNING")
    make_card(tmp_path, 1, "vc4hdmi0", "closed")
    make_card(tmp_path, 2, "vc4hdmi1", "closed")
    monkeypatch.setattr(pi, "SOUND_CARDS", tmp_path)

    assert pi._sound() == {"card": "UACDemoV10", "playing": True}


def test_silence_still_names_a_card(tmp_path, monkeypatch):
    """So the window can say where sound would go, rather than nothing."""
    make_card(tmp_path, 0, "UACDemoV10", "closed")
    make_card(tmp_path, 1, "vc4hdmi0", "closed")
    monkeypatch.setattr(pi, "SOUND_CARDS", tmp_path)

    assert pi._sound() == {"card": "UACDemoV10", "playing": False}


def test_a_card_without_a_playback_stream_is_still_listed(tmp_path, monkeypatch):
    """A capture-only device has no pcm0p at all."""
    card = tmp_path / "card0"
    card.mkdir()
    (card / "id").write_text("SomeMicrophone\n")
    monkeypatch.setattr(pi, "SOUND_CARDS", tmp_path)

    assert pi._sound() == {"card": "SomeMicrophone", "playing": False}


def test_no_cards_at_all(tmp_path, monkeypatch):
    monkeypatch.setattr(pi, "SOUND_CARDS", tmp_path)
    assert pi._sound() is None


# -- the rest ------------------------------------------------------------


def test_every_reading_is_answered_even_where_none_can_be_had(monkeypatch):
    """The window shows what it has and leaves the rest blank. It never fails
    as a whole because one file is missing."""
    monkeypatch.setattr(pi, "_ask", lambda _command: "")
    monkeypatch.setattr(pi, "SOUND_CARDS", pi.pathlib.Path("/does/not/exist"))

    answer = pi.readings()

    assert set(answer) == {
        "model", "uptime_seconds", "temperature_c", "throttling",
        "emulator", "sound", "disk", "memory",
    }
