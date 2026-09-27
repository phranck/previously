"""Who may change something.

The tests that matter here are the negative ones. A password that accepts the
right value is easy; what has to hold is that it accepts nothing else, that a
machine with no password refuses rather than waves things through, and that a
source getting it wrong over and over is stopped.
"""

import os
import stat

import pytest

from previously.password import (
    LARGEST, SMALLEST, Attempts, Password, Sessions, acceptable,
)


@pytest.fixture
def secret(tmp_path):
    """A password nobody has set yet, at a path of this test's own."""
    return Password(tmp_path / "password")


# -- the secret itself ----------------------------------------------------


def test_a_fresh_machine_is_unclaimed(secret):
    """Which is what lets the first browser set a password without fetching
    anything from the Pi."""
    assert secret.claimed is False
    assert secret.matches("anything at all") is False


def test_what_was_set_is_what_matches(secret):
    assert secret.set("a good password") is True

    assert secret.claimed is True
    assert secret.matches("a good password") is True


def test_nothing_else_matches(secret):
    secret.set("a good password")

    assert secret.matches("") is False
    assert secret.matches(None) is False
    assert secret.matches("a good passwore") is False
    # A prefix of the real one, which a comparison that stopped early would
    # treat as closer than a wrong one of the same length.
    assert secret.matches("a good passwor") is False
    assert secret.matches("a good passwords") is False


def test_the_password_itself_is_not_on_disk(tmp_path, secret):
    """What is kept is a hash, so somebody who reads the file has the work of
    guessing rather than the password."""
    secret.set("a good password")

    kept = (tmp_path / "password").read_text()

    assert "a good password" not in kept
    assert kept.startswith("scrypt$")


def test_the_file_is_not_readable_by_everybody(tmp_path, secret):
    secret.set("a good password")

    mode = stat.S_IMODE((tmp_path / "password").stat().st_mode)
    assert mode == 0o640
    assert not mode & stat.S_IROTH


def test_a_new_password_replaces_the_old_one(secret):
    secret.set("the first one")
    secret.set("the second one")

    assert secret.matches("the first one") is False
    assert secret.matches("the second one") is True


def test_two_machines_with_the_same_password_keep_different_hashes(tmp_path):
    """A salt each, so one table of hashes cannot be tried against both."""
    one = Password(tmp_path / "one")
    other = Password(tmp_path / "other")

    one.set("a good password")
    other.set("a good password")

    assert (tmp_path / "one").read_text() != (tmp_path / "other").read_text()


@pytest.mark.parametrize("value", [
    "",
    "short",
    "x" * (SMALLEST - 1),
    "x" * (LARGEST + 1),
    None,
    12345678,
])
def test_a_password_that_is_not_one_is_refused(secret, value):
    """The ceiling matters as much as the floor: without it a body could ask
    this machine to hash a megabyte."""
    assert acceptable(value) is False
    assert secret.set(value) is False
    assert secret.claimed is False


def test_a_file_that_says_nothing_leaves_the_machine_unclaimed(tmp_path):
    """A truncated write leaves a file that exists and holds nothing, and an
    empty secret must not match an empty answer."""
    (tmp_path / "password").write_text("")

    secret = Password(tmp_path / "password")

    assert secret.claimed is False
    assert secret.matches("") is False


def test_a_file_that_cannot_be_read_leaves_the_machine_unclaimed(tmp_path):
    """Refusing every change is the safe direction to fail in."""
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o000)
    try:
        assert Password(locked / "password").claimed is False
    finally:
        os.chmod(locked, 0o700)


def test_a_file_written_by_something_else_matches_nothing(tmp_path):
    """Rather than raising at the one moment somebody is trying to get in."""
    (tmp_path / "password").write_text("whatever somebody put here")

    assert Password(tmp_path / "password").matches("whatever somebody put here") is False


def test_removing_the_file_unclaims_the_machine_at_once(tmp_path, secret):
    """The whole of the recovery path, and it must not need a restart: the file
    is read on every check rather than held from the start."""
    secret.set("a good password")

    (tmp_path / "password").unlink()

    assert secret.claimed is False
    assert secret.matches("a good password") is False


# -- who is signed in -----------------------------------------------------


def test_a_session_that_was_opened_is_held():
    sessions = Sessions()

    identifier = sessions.open()

    assert sessions.holds(identifier) is True


def test_nothing_else_is_held():
    sessions = Sessions()
    sessions.open()

    assert sessions.holds("not a session") is False
    assert sessions.holds("") is False
    assert sessions.holds(None) is False


def test_two_sessions_differ():
    sessions = Sessions()
    assert sessions.open() != sessions.open()


def test_a_session_that_has_run_out_is_not_held():
    sessions = Sessions(lasting=-1)

    assert sessions.holds(sessions.open()) is False


def test_a_session_can_be_ended():
    sessions = Sessions()
    identifier = sessions.open()

    sessions.forget(identifier)

    assert sessions.holds(identifier) is False


def test_a_new_password_ends_every_session():
    """So a password somebody should not have can be taken back."""
    sessions = Sessions()
    one, other = sessions.open(), sessions.open()

    sessions.forget_them_all()

    assert sessions.holds(one) is False
    assert sessions.holds(other) is False


# -- how often a guess may be made ----------------------------------------


def test_a_source_is_refused_after_too_many_wrong_answers():
    attempts = Attempts(allowed=3, window=300)

    for _ in range(3):
        assert attempts.too_many("10.0.0.23") is False
        attempts.wrong("10.0.0.23")

    assert attempts.too_many("10.0.0.23") is True


def test_one_source_guessing_does_not_refuse_another():
    attempts = Attempts(allowed=1, window=300)

    attempts.wrong("10.0.0.23")

    assert attempts.too_many("10.0.0.23") is True
    assert attempts.too_many("10.0.0.24") is False


def test_a_right_answer_forgets_what_came_before_it():
    attempts = Attempts(allowed=2, window=300)
    attempts.wrong("10.0.0.23")

    attempts.forget("10.0.0.23")
    attempts.wrong("10.0.0.23")

    assert attempts.too_many("10.0.0.23") is False


def test_wrong_answers_are_forgotten_once_the_window_has_passed():
    """Or one bad evening would lock a machine out for good."""
    attempts = Attempts(allowed=1, window=-1)

    attempts.wrong("10.0.0.23")

    assert attempts.too_many("10.0.0.23") is False
