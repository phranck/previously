"""The service's own configuration."""

import textwrap

from nextstep_admin.settings import DEFAULTS, Settings


def test_a_missing_file_gives_a_working_configuration(tmp_path):
    """The package has to install into a running state rather than into a file
    somebody has to edit first."""
    settings = Settings.load(tmp_path / "absent.ini")

    assert settings.port == int(DEFAULTS["port"])
    assert settings.address == DEFAULTS["address"]
    assert settings.kiosk_unit == DEFAULTS["kiosk_unit"]


def test_a_file_naming_one_key_names_one_key(tmp_path):
    """Anything the file does not say keeps its default, so a change is one
    line rather than a copy of everything."""
    path = tmp_path / "config.ini"
    path.write_text("[service]\nport = 9000\n")

    settings = Settings.load(path)

    assert settings.port == 9000
    assert settings.address == DEFAULTS["address"]


def test_the_home_shorthand_is_expanded(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text(textwrap.dedent("""
        [service]
        previous_config = ~/somewhere/previous.cfg
        """))

    settings = Settings.load(path)

    assert "~" not in str(settings.previous_config)
    assert settings.previous_config.is_absolute()
