"""What more than one test file needs.

Settings takes a complete set of values, because filling gaps in the
constructor would put the defaults in a second place and the two would drift.
Tests therefore start from DEFAULTS and override what they care about, which is
what this helper is for.
"""

import pathlib

import pytest

from previously.settings import DEFAULTS, Settings

#: Where the interface is written, which is not where it is served from. The
#: tests read the sources, because that is what somebody edits; what ships is
#: built out of them and is held to them by test_web.py.
INTERFACE = pathlib.Path(__file__).resolve().parent.parent / "interface"


def page_source():
    """Everything this application's own code is written in, as one text.

    @returns str

    The interface is one module per subject under `interface/app/`, and a test
    that asked only `app.js` would read the twenty lines that start the page
    and none of what it starts.
    """
    modules = sorted((INTERFACE / "app").glob("*.js"))
    return "\n".join(path.read_text(encoding="utf-8")
                     for path in [INTERFACE / "app.js", *modules])


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
        "password_file": str(tmp_path / "password"),
        "runtime_directory": str(tmp_path),
        # Where the disks would be and where the privileged helper would say
        # what it is doing. Both into the test's own directory, because the
        # defaults are a real folder in somebody's home and a real one under
        # /run, and a test has no business reading either.
        "disks": str(tmp_path / "nextstep"),
        # Not `setup`, because the runtime directory above is this same one and
        # the request the helper reads is a file of that name in it.
        "setup_directory": str(tmp_path / "setup-progress"),
        # Both into the test's own directory, because what the service keeps in
        # them is real on the machine running the suite: the note about its last
        # write, and the configurations somebody saved.
        "state_directory": str(tmp_path),
        "machines_file": str(tmp_path / "machines.json"),
    })
    values.update({key: str(value) for key, value in overrides.items()})
    return Settings(values)


@pytest.fixture(autouse=True)
def nothing_remembered_about_packages():
    """What dpkg, apt and GitHub last said, thrown away before and after every
    test.

    The service keeps both answers for a while, because the Installer window
    asks twice a second and the Raspberry Pi window every five seconds. Between
    two tests it would be one test's machine answering another test's question.
    """
    from previously import release, setup

    setup.forget()
    release.forget()
    yield
    setup.forget()
    release.forget()


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
