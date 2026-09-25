"""The service's own configuration."""

import pathlib
import textwrap

from previously.settings import DEFAULTS, Settings

#: The file the package installs as `/etc/previously/config.ini`, which claims to
#: write every default out.
EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "packaging" / "config.ini"


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


def test_the_configurations_are_read_from_a_path_in_the_home():
    """Expanded like the emulator's own configuration, because that is where it
    sits: the two are one directory apart."""
    settings = Settings(dict(DEFAULTS))

    assert "~" not in str(settings.machines_file)
    assert settings.machines_file.is_absolute()
    assert settings.machines_file.parent.name == "previously"
    assert settings.machines_file.parent.parent == settings.previous_config.parent.parent


def test_the_example_configuration_writes_out_every_default():
    """`packaging/config.ini` says every key in it is the default, and it is what
    somebody reads to find out what there is to set. A key missing from it is a
    setting nobody knows about."""
    text = EXAMPLE.read_text(encoding="utf-8")
    named = {line.split("=", 1)[0].strip()
             for line in text.splitlines()
             if "=" in line and not line.lstrip().startswith("#")}

    assert sorted(set(DEFAULTS) - named) == []
