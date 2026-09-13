"""Who may change something.

The tests that matter here are the negative ones. A token that accepts the
right value is easy; what has to hold is that it accepts nothing else, and
that a service without one refuses rather than waves things through.
"""

import os
import stat

from previously.token import TOKEN_BYTES, Token


def test_a_token_is_made_where_there_is_none(tmp_path):
    path = tmp_path / "token"
    token = Token.load(path)

    assert token is not None
    assert path.exists()
    # Hex, so two characters per byte.
    assert len(token.value) == TOKEN_BYTES * 2


def test_an_existing_token_is_kept(tmp_path):
    """Making a new one on every start would mean typing it in again after
    every restart, which is how a secret becomes a nuisance and then a habit
    of turning it off."""
    path = tmp_path / "token"
    first = Token.load(path)
    second = Token.load(path)

    assert first.value == second.value


def test_the_file_is_not_readable_by_everybody(tmp_path):
    path = tmp_path / "token"
    Token.load(path)

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o640
    assert not mode & stat.S_IROTH


def test_an_empty_file_is_replaced_rather_than_trusted(tmp_path):
    """A truncated write leaves a file that exists and says nothing, and an
    empty secret would match an empty header."""
    path = tmp_path / "token"
    path.write_text("")

    token = Token.load(path)

    assert token.value != ""
    assert len(token.value) == TOKEN_BYTES * 2


def test_a_directory_that_cannot_be_written_gives_no_token(tmp_path):
    """Refusing every change is the safe direction to fail in."""
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    try:
        assert Token.load(locked / "token") is None
    finally:
        os.chmod(locked, 0o700)


def test_the_right_value_matches(tmp_path):
    token = Token.load(tmp_path / "token")
    assert token.matches(token.value) is True


def test_nothing_else_matches(tmp_path):
    token = Token.load(tmp_path / "token")

    assert token.matches("") is False
    assert token.matches(None) is False
    assert token.matches("wrong") is False
    # A prefix of the real one, which a comparison that stops early would
    # treat as closer than a wrong one of the same length.
    assert token.matches(token.value[:-1]) is False
    assert token.matches(token.value + "a") is False
