"""Looking for a newer release and a newer Previous, and whether the Pi does it
on its own."""

from previously import updates


def keeper(asked, name, asked_at):
    """A stand-in for `release.published` or `archive.offered` that remembers
    being told to ask."""
    def answer(check=False):
        if check:
            asked.append(name)
        return None if asked_at is None else {"version": "1", "asked_at": asked_at}
    return answer


def test_what_is_known_is_asked_again_once_it_is_an_hour_old(monkeypatch):
    asked = []
    monkeypatch.setattr(updates.release, "published", keeper(asked, "release", 0.0))
    monkeypatch.setattr(updates.archive, "offered",
                        keeper(asked, "archive", updates.FRESH_SECONDS))

    updates.look_again(now=updates.FRESH_SECONDS)

    assert asked == ["release"]


def test_what_was_never_learned_is_asked_for(monkeypatch):
    asked = []
    monkeypatch.setattr(updates.release, "published", keeper(asked, "release", None))
    monkeypatch.setattr(updates.archive, "offered", keeper(asked, "archive", None))

    updates.look_again(now=1.0)

    assert asked == ["release", "archive"]


def test_looking_now_asks_both_whatever_is_known(monkeypatch):
    """The button in Preferences asks at once, even where what is known is a
    minute old."""
    asked = []
    monkeypatch.setattr(updates.release, "published", keeper(asked, "release", 1.0))
    monkeypatch.setattr(updates.archive, "offered", keeper(asked, "archive", 1.0))

    updates.look_now()

    assert asked == ["release", "archive"]


def test_a_pi_nobody_told_looks_on_its_own(tmp_path):
    assert updates.automatic(tmp_path) is True


def test_the_choice_is_kept(tmp_path):
    updates.choose(tmp_path, False)
    assert updates.automatic(tmp_path) is False

    updates.choose(tmp_path, True)
    assert updates.automatic(tmp_path) is True


def test_a_choice_that_cannot_be_read_is_read_as_looking(tmp_path):
    """Looking is what a Pi does until somebody says otherwise, and a file
    nobody can read is nobody saying so."""
    (tmp_path / updates.CHOICE).write_text("{not json", encoding="utf-8")

    assert updates.automatic(tmp_path) is True


def test_the_watch_asks_nothing_while_the_pi_is_told_not_to_look(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(updates, "look_again", lambda: asked.append(True))

    def one_tick(seconds):
        raise StopIteration

    monkeypatch.setattr(updates.time, "sleep", one_tick)
    updates.choose(tmp_path, False)
    try:
        updates._watching(tmp_path)
    except StopIteration:
        pass
    assert asked == []

    updates.choose(tmp_path, True)
    try:
        updates._watching(tmp_path)
    except StopIteration:
        pass
    assert asked == [True]
