"""What more than one test file needs.

Settings takes a complete set of values, because filling gaps in the
constructor would put the defaults in a second place and the two would drift.
Tests therefore start from DEFAULTS and override what they care about, which is
what this helper is for.
"""

import pytest

from previously.settings import DEFAULTS, Settings


def settings_for(tmp_path, **overrides):
    """Settings for a test, bound to a port the system picks.

    @param tmp_path - The test's directory, which holds the previous.cfg this
      points at unless an override says otherwise.
    @param overrides - Any key of DEFAULTS, as the string a config file would
      carry, so "port": "0" rather than 0.
    @returns Settings
    """
    values = dict(DEFAULTS)
    values.update({
        "address": "127.0.0.1",
        "port": "0",
        "previous_config": str(tmp_path / "previous.cfg"),
        "documents": str(tmp_path / "Previously"),
        "kiosk_unit": "does-not-exist.service",
        "token_file": str(tmp_path / "token"),
        "runtime_directory": str(tmp_path),
        # Into the test's own directory, because what the service keeps here is
        # real on the machine running the suite: the note about the last write
        # and the configurations somebody saved both live in it.
        "state_directory": str(tmp_path),
    })
    values.update({key: str(value) for key, value in overrides.items()})
    return Settings(values)


@pytest.fixture
def readable_config(tmp_path):
    """A previous.cfg describing a machine, at the path settings_for expects.

    @returns pathlib.Path
    """
    path = tmp_path / "previous.cfg"
    path.write_text(
        "[System]\nnMachineType = 1\nbTurbo = TRUE\nnCpuLevel = 4\n"
        "nCpuFreq = 33\n\n[Memory]\nnMemoryBankSize0 = 64\n"
    )
    return path
