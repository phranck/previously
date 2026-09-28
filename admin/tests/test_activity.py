"""The readings a live monitor draws, which are all differences.

Every figure in `activity.py` is what has changed since the last reading, so
these tests hand it two `/proc` directories in turn and check what it makes of
the pair. The counters below are the kernel's own shape: a `cpu` line whose
fields are user, nice, system, idle, iowait and the rest, in that order.
"""

import os

import pytest

from previously import activity, screen


@pytest.fixture(autouse=True)
def forget():
    """Each test starts where a service that has just come up starts."""
    activity.forget()
    yield
    activity.forget()


def proc(monkeypatch, tmp_path, cores, loadavg="0.50 0.40 0.30 1/200 1234\n"):
    """A `/proc` of this test's own.

    @param monkeypatch - What points the module at it, so the real one is back
      the moment the test ends.
    @param tmp_path - Where to build it.
    @param cores - One (busy, idle) pair per core, in ticks.
    @param loadavg - What `/proc/loadavg` says.
    @returns The directory.
    """
    stat = ["cpu  0 0 0 0 0 0 0 0 0 0"]
    for number, (busy, idle) in enumerate(cores):
        # user, nice, system, idle, iowait, and four more the kernel writes.
        stat.append("cpu%d %d 0 0 %d 0 0 0 0 0"
                    % (number, busy, idle))
    (tmp_path / "stat").write_text("\n".join(stat) + "\n", encoding="utf-8")
    (tmp_path / "loadavg").write_text(loadavg, encoding="utf-8")

    monkeypatch.setattr(activity, "STAT", tmp_path / "stat")
    monkeypatch.setattr(activity, "LOADAVG", tmp_path / "loadavg")
    monkeypatch.setattr(activity, "PROCESSES", tmp_path)
    return tmp_path


def a_process(tmp_path, pid, name, ticks=0, started_at=0, pages=0):
    """One process in that `/proc`, in the shape the kernel writes."""
    where = tmp_path / str(pid)
    where.mkdir(exist_ok=True)
    (where / "comm").write_text(name + "\n", encoding="utf-8")
    # The name is in brackets, and everything this reads is counted from the
    # closing one. utime and stime are the twelfth and thirteenth fields after
    # it, and starttime the twentieth.
    after = ["0"] * 30
    after[activity.UTIME_FIELD] = str(ticks)
    after[activity.STIME_FIELD] = "0"
    after[activity.STARTTIME_FIELD] = str(started_at)
    (where / "stat").write_text("%d (%s) S %s\n" % (pid, name, " ".join(after)),
                                encoding="utf-8")
    (where / "statm").write_text("0 %d 0 0 0 0 0\n" % pages, encoding="utf-8")
    return where


def test_the_first_reading_has_nothing_to_compare_against(monkeypatch, tmp_path):
    """A counter is a total since the board started, so one reading says
    nothing about now. Saying None beats drawing a bar from a figure about
    last Tuesday."""
    proc(monkeypatch, tmp_path, [(100, 900), (200, 800)])

    assert activity.readings()["cores"] is None


def test_a_core_that_was_busy_half_the_time_reads_fifty(monkeypatch, tmp_path):
    proc(monkeypatch, tmp_path, [(100, 900)])
    activity.readings()
    proc(monkeypatch, tmp_path, [(150, 950)])

    assert activity.readings()["cores"] == [50.0]


def test_every_core_is_measured_on_its_own(monkeypatch, tmp_path):
    """One bar per core is the whole point: a machine with one core pinned and
    three idle is a different machine from one at a quarter everywhere."""
    proc(monkeypatch, tmp_path, [(0, 1000), (0, 1000), (0, 1000), (0, 1000)])
    activity.readings()
    proc(monkeypatch, tmp_path, [(100, 1000), (0, 1100), (0, 1100), (0, 1100)])

    assert activity.readings()["cores"] == [100.0, 0.0, 0.0, 0.0]


def test_two_readings_at_the_same_moment_are_not_a_division_by_zero(monkeypatch, tmp_path):
    """Two browsers asking together, or a machine whose counters have not
    moved. Nothing has happened, which is 0 rather than a failure."""
    proc(monkeypatch, tmp_path, [(100, 900)])
    activity.readings()

    assert activity.readings()["cores"] == [0.0]


def test_a_core_that_appears_keeps_the_shape_of_the_answer(monkeypatch, tmp_path):
    """A core coming out of a sleep state has no figure of its own yet. The
    window keeps one bar per core rather than changing shape underneath
    somebody."""
    proc(monkeypatch, tmp_path, [(100, 900)])
    activity.readings()
    proc(monkeypatch, tmp_path, [(150, 950), (10, 90)])

    assert activity.readings()["cores"] == [50.0, 0.0]


def test_a_proc_that_cannot_be_read_answers_nothing(monkeypatch, tmp_path):
    proc(monkeypatch, tmp_path, [(100, 900)])
    activity.readings()
    monkeypatch.setattr(activity, "STAT", tmp_path / "gone")

    assert activity.readings()["cores"] is None


def test_the_load_averages_come_with_what_they_are_read_against(monkeypatch, tmp_path):
    """4.0 is a machine working flat out on four cores and one four times
    oversubscribed on one, so the count travels with the figures."""
    proc(monkeypatch, tmp_path, [(0, 1)], loadavg="1.25 0.75 0.50 2/300 900\n")

    load = activity.readings()["load"]

    assert load["one"] == 1.25
    assert load["five"] == 0.75
    assert load["fifteen"] == 0.50
    assert load["cores"] >= 1


def test_a_loadavg_that_is_not_there_is_not_invented(monkeypatch, tmp_path):
    proc(monkeypatch, tmp_path, [(0, 1)])
    monkeypatch.setattr(activity, "LOADAVG", tmp_path / "gone")

    assert activity.readings()["load"] is None


def test_the_emulator_is_found_by_its_own_name(monkeypatch, tmp_path):
    proc(monkeypatch, tmp_path, [(0, 1)])
    a_process(tmp_path, 41, "cage")
    a_process(tmp_path, 42, screen.EMULATOR, ticks=0, pages=1024)
    activity.readings()
    a_process(tmp_path, 42, screen.EMULATOR,
              ticks=activity.TICKS_PER_SECOND, pages=1024)

    emulator = activity.readings()["emulator"]

    assert emulator["memory_mb"] == 1024 * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024)
    assert emulator["cpu_percent"] is not None


def test_a_machine_with_no_emulator_says_so(monkeypatch, tmp_path):
    proc(monkeypatch, tmp_path, [(0, 1)])
    a_process(tmp_path, 41, "cage")

    assert activity.readings()["emulator"] is None


def test_a_machine_with_no_emulator_is_not_searched_every_second(monkeypatch, tmp_path):
    """Finding it means a read per process, which on a Pi 5 is 5.6 ms against
    the 0.07 ms everything else here comes to. A machine whose emulator is off
    stays off for minutes, so looking every few seconds is soon enough."""
    proc(monkeypatch, tmp_path, [(0, 1)])
    for number in range(50):
        a_process(tmp_path, 100 + number, "systemd")

    looked_at = []
    asking = activity._named

    def counted(pid):
        looked_at.append(pid)
        return asking(pid)

    monkeypatch.setattr(activity, "_named", counted)

    activity.readings()
    first = len(looked_at)
    activity.readings()

    assert first >= 50, "it never looked at all"
    assert len(looked_at) == first


def test_a_process_number_that_now_belongs_to_something_else_is_dropped(monkeypatch, tmp_path):
    """A number is reused the moment a process ends, and this one is kept
    between readings so the scan does not run every second. What makes that
    safe is asking the process what it calls itself."""
    proc(monkeypatch, tmp_path, [(0, 1)])
    a_process(tmp_path, 42, screen.EMULATOR)
    activity.readings()
    a_process(tmp_path, 42, "systemd-udevd")

    assert activity.readings()["emulator"] is None


def test_every_reading_is_answered_even_where_none_can_be_had(monkeypatch, tmp_path):
    """The window draws what it has and leaves the rest empty, the way the
    Raspberry Pi window does."""
    proc(monkeypatch, tmp_path, [])
    monkeypatch.setattr(activity, "STAT", tmp_path / "gone")
    monkeypatch.setattr(activity, "LOADAVG", tmp_path / "gone")

    assert set(activity.readings()) == {"cores", "load", "memory", "emulator"}
