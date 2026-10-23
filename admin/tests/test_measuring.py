"""Reading what a measured boot left behind.

The Pi is not here, so what is tested is the reading: what systemd's summary
says, when a run of pictures stopped changing, and how much of a core each
thread used between two moments. The capture itself runs on a Pi and is
checked there.
"""

import importlib.util
import pathlib

import pytest
from PIL import Image

MEASURING = pathlib.Path(__file__).resolve().parent.parent / "measuring"


@pytest.fixture(scope="module")
def boot():
    """`measuring/boot.py`, imported by path, because it is a script beside
    the package rather than a module of it."""
    spec = importlib.util.spec_from_file_location("boot", MEASURING / "boot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def screen(*marks):
    """A 1120 by 832 screen of NeXT gray, with a black square at each mark.

    @param marks - (x, y, size) of each square.
    """
    picture = Image.new("L", (1120, 832), 0x55)
    for x, y, size in marks:
        picture.paste(0, (x, y, x + size, y + size))
    return picture


# -- systemd's summary ------------------------------------------------------


def test_the_summary_of_a_pi_5_is_read(boot):
    """As `systemd-analyze` printed it on next5.local on 22.10.2026."""
    figures = boot.startup(
        "Startup finished in 3.077s (kernel) + 25.254s (userspace) = 28.332s \n"
        "multi-user.target reached after 12.619s in userspace.\n")

    assert figures["kernel"] == pytest.approx(3.077)
    assert figures["userspace"] == pytest.approx(25.254)
    assert figures["multi_user"] == pytest.approx(3.077 + 12.619)


def test_a_span_of_minutes_is_read(boot):
    """As next4.local printed it the same day."""
    figures = boot.startup(
        "Startup finished in 4.372s (kernel) + 2min 7.783s (userspace) = 2min 12.156s \n"
        "multi-user.target reached after 1min 29.509s in userspace.\n")

    assert figures["userspace"] == pytest.approx(127.783)
    assert figures["multi_user"] == pytest.approx(4.372 + 89.509)


def test_milliseconds_are_thousandths(boot):
    assert boot.seconds_in("123ms") == pytest.approx(0.123)


def test_a_boot_still_under_way_has_no_figures(boot):
    figures = boot.startup("Bootup is not yet finished.\n")

    assert figures == {"kernel": None, "userspace": None, "multi_user": None}


# -- the pictures -----------------------------------------------------------


def test_pixels_that_differ_are_counted(boot):
    assert boot.changed_pixels(screen(), screen((10, 10, 4))) == 16


def test_the_first_picture_is_the_first_that_is_not_one_color(boot):
    frames = [(1.0, Image.new("L", (1120, 832), 0)), (2.0, screen()),
              (3.0, screen((10, 10, 4)))]

    assert boot.first_picture(frames) == 3.0


def test_the_screen_settles_with_its_last_real_change(boot):
    """The Workspace appearing is the last change that counts."""
    frames = [(1.0, screen()), (2.0, screen((100, 100, 200))),
              (3.0, screen((100, 100, 200), (500, 0, 300))),
              (4.0, screen((100, 100, 200), (500, 0, 300)))]

    assert boot.settled(frames) == 3.0


def test_the_clock_turning_over_is_not_the_boot(boot):
    """A minute in the dock changes a few digits, well under CLOCK_PIXELS."""
    workspace = ((100, 100, 200), (500, 0, 300))
    frames = [(1.0, screen()), (2.0, screen(*workspace)),
              (3.0, screen(*workspace)),
              (4.0, screen(*workspace, (1060, 70, 10)))]

    assert boot.settled(frames) == 2.0


def test_no_pictures_settle_nowhere(boot):
    assert boot.settled([]) is None


# -- the load -----------------------------------------------------------------


def sample(at, **ticks):
    """A sample whose threads and processes are named by their ticks."""
    entries = {str(number): [name, value]
               for number, (name, value) in enumerate(ticks.items())}
    return {"at": at, "threads": entries, "processes": entries}


def test_the_load_is_what_was_spent_over_how_long(boot):
    samples = [sample(10.0, previous=1000, CSocket=0),
               sample(20.0, previous=1950, CSocket=10)]

    assert boot.load(samples, "threads", 10.0, 20.0, 100) == {
        "previous": 95.0, "CSocket": 1.0}


def test_threads_that_share_a_name_are_added_up(boot):
    samples = [{"at": 0.0, "threads": {"1": ["CSocket", 0], "2": ["CSocket", 0]}},
               {"at": 10.0, "threads": {"1": ["CSocket", 50], "2": ["CSocket", 50]}}]

    assert boot.load(samples, "threads", 0.0, 10.0, 100) == {"CSocket": 10.0}


def test_the_boot_is_counted_from_the_emulators_start(boot):
    """A capture can come up after the emulator, and its first sample would
    then leave out the seconds before it. The emulator's threads started
    with nothing on a core, so their ticks count from its start."""
    samples = [sample(15.0, previous=300), sample(20.0, previous=800)]

    assert boot.load(samples, "threads", 12.0, 20.0, 100,
                     from_nothing=True) == {"previous": 100.0}


def test_the_kernels_workers_are_one_line(boot):
    """A worker's name carries its number and whatever queue it serves at
    that moment, which differ from one run to the next."""
    samples = [{"at": 0.0, "processes": {"1": ["kworker/u16:3-v3d_tfu", 0],
                                         "2": ["kworker/u16:0-v3d_render", 0]}},
               {"at": 10.0, "processes": {"1": ["kworker/u16:3-v3d_tfu", 20],
                                          "2": ["kworker/u16:0-events_unbound", 30]}}]

    assert boot.load(samples, "processes", 0.0, 10.0, 100) == {"kworker": 5.0}


def test_what_the_slices_take_away_is_always_listed(boot):
    """Xwayland and PipeWire are what #571 and #572 remove, so a report after
    them says 0 rather than leaving the line out, and cage is listed beside
    them."""
    runs = [{"processes_booting": {"previous": 130.0, "Xwayland": 0.0},
             "processes_idle": {"previous": 130.0, "Xwayland": 5.0}}]

    lines = boot._load_table("Process", runs, "processes", 1)

    assert "| `previous` | 130.0 | 130.0 |" in lines
    assert "| `Xwayland` | 0.0 | 5.0 |" in lines
    assert "| `cage` | 0.0 | 0.0 |" in lines
    assert "| `pipewire` | 0.0 | 0.0 |" in lines


def test_a_process_that_starts_on_the_way_counts_from_nothing(boot):
    """cage starts Xwayland only once Previous connects, which is after the
    first sample, and all of its time falls inside the span."""
    samples = [{"at": 0.0, "processes": {"1": ["cage", 10]}},
               {"at": 10.0, "processes": {"1": ["cage", 20], "2": ["Xwayland", 50]}}]

    assert boot.load(samples, "processes", 0.0, 10.0, 100) == {
        "cage": 1.0, "Xwayland": 5.0}


def test_samples_that_do_not_cover_the_span_say_nothing(boot):
    samples = [sample(10.0, previous=0)]

    assert boot.load(samples, "threads", 20.0, 30.0, 100) == {}


# -- talking to the Pi ----------------------------------------------------------


def test_python_on_the_pi_is_handed_its_program_whole(boot, monkeypatch):
    """On stdin rather than inside the command line, where the shell on the
    Pi takes a quote in the program for the end of it. A machine named with
    %r in single quotes stopped every run with a NeXTdimension that way."""
    asked = []
    monkeypatch.setattr(boot, "_run",
                        lambda command, given=None: asked.append((command, given)) or "")
    program = "print('nextcube-turbo-dimension')"

    boot._python("next@pi.local", program)

    command, given = asked[0]
    assert given == program
    assert program not in command[-1]


def test_a_machine_the_pi_refuses_stops_the_measurement(boot, monkeypatch):
    """Measuring on would measure the machine that was there before under the
    name of the one asked for. Seen on a Pi 5 on 23.10.2026, where the guest
    was still starting and did not shut down for the change."""
    monkeypatch.setattr(boot, "_ssh", lambda target, command, given=None, quiet=False: "")
    monkeypatch.setattr(
        boot, "_python",
        lambda target, program: '[false, {"reason": "guest.still-shutting-down"}]\n')

    with pytest.raises(RuntimeError, match="guest.still-shutting-down"):
        boot._switch("next@pi.local", "nextcube-turbo-dimension")


def a_pi(boot, monkeypatch, restart):
    """A Pi that answers `cat` with one boot id before the restart and another
    after it, and the restart itself with `restart`, a function of nothing
    that returns what it printed or raises."""
    boots = iter(["before\n", "", "after\n"])

    def run(command, given=None):
        if command[-1].startswith("cat "):
            return next(boots)
        return restart()

    monkeypatch.setattr(boot, "_run", run)
    monkeypatch.setattr(boot.time, "sleep", lambda seconds: None)


def test_a_board_that_restarts_before_it_answers_is_still_measured(boot, monkeypatch):
    """The board reboots the moment the request is written, and on a Pi 4 on
    23.10.2026 that took the SSH session down before Python had answered. The
    new boot id is what says the board came back."""
    def dropped():
        raise boot.subprocess.CalledProcessError(255, ["ssh"])

    a_pi(boot, monkeypatch, dropped)

    boot._reboot("next@pi.local")


def test_a_board_that_refuses_to_restart_stops_the_measurement(boot, monkeypatch):
    a_pi(boot, monkeypatch, lambda: '[false, {"reason": "guest.still-shutting-down"}]\n')

    with pytest.raises(RuntimeError, match="guest.still-shutting-down"):
        boot._reboot("next@pi.local")


# -- the capture's reading of /proc ------------------------------------------


@pytest.fixture(scope="module")
def capture():
    """`measuring/capture.py`, imported by path."""
    spec = importlib.util.spec_from_file_location("capture", MEASURING / "capture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stat(directory, number, name, utime, stime):
    """Writes a stat file the way the kernel does, the name in brackets."""
    entry = directory / str(number)
    entry.mkdir()
    fields = ["S"] + ["0"] * 10 + [str(utime), str(stime)] + ["0"] * 30
    (entry / "stat").write_text("%d (%s) %s\n" % (number, name, " ".join(fields)))


def test_a_threads_time_is_both_kinds_of_ticks(capture, tmp_path):
    stat(tmp_path, 7, "previous", 900, 100)

    assert capture._ticks_under(tmp_path) == {"7": ["previous", 1000]}


def test_a_name_with_spaces_and_brackets_is_read_whole(capture, tmp_path):
    """Previous calls its processor thread "[Previous] 68k " with a space at
    the end, which is trimmed so two runs name it the same."""
    stat(tmp_path, 8, "[Previous] 68k ", 40, 2)

    assert capture._ticks_under(tmp_path) == {"8": ["[Previous] 68k", 42]}


def test_what_is_not_a_process_is_passed_over(capture, tmp_path):
    (tmp_path / "self").mkdir()
    stat(tmp_path, 9, "cage", 1, 1)

    assert capture._ticks_under(tmp_path) == {"9": ["cage", 2]}


def test_the_capture_leaves_itself_out(capture, tmp_path, monkeypatch):
    """It is not part of what is measured, and it is called python3 like the
    admin service, which is."""
    stat(tmp_path, 10, "python3", 5, 5)
    stat(tmp_path, 11, "python3", 7, 7)
    monkeypatch.setattr(capture, "PROCESSES", tmp_path)
    monkeypatch.setattr(capture.os, "getpid", lambda: 11)

    assert capture._processes() == {"10": ["python3", 10]}
