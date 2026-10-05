"""The one-liner, held against the helper it hands the machine to.

`install.sh` installs the admin tool and then asks its privileged helper for
everything else, the same job the Installer window asks for. It runs before the
tool exists on the machine, so it cannot import anything from it, and it names a
few things a second time: where the request goes, where the progress is read,
which system a fresh machine gets, and what each step is called on the screen.
These tests are what keeps those in step with the side that decides them.
"""

import json
import pathlib
import re

import pytest

from previously import kiosk, setup, systems
from previously.settings import DEFAULTS
from test_strings import catalogue

SCRIPT = (pathlib.Path(__file__).resolve().parent.parent.parent
          / "install.sh").read_text(encoding="utf-8")


def constant(name):
    """@returns str, what install.sh declares `readonly NAME="..."` as."""
    found = re.search(r'^readonly %s="([^"]*)"$' % name, SCRIPT, re.M)
    assert found, "install.sh declares no %s" % name
    return found.group(1)


def labels(function):
    """@returns dict, the cases of one of install.sh's label functions."""
    body = re.search(r"^%s\(\) \{\n(.*?)\n\}" % function, SCRIPT, re.M | re.S)
    assert body, "install.sh has no %s" % function
    return dict(re.findall(r'^\s+([a-z-]+)\) echo "([^"]*)" ;;$', body.group(1), re.M))


def test_the_request_goes_where_the_helper_is_started_from():
    """The path unit fires on this name in the tool's runtime directory, and a
    request written anywhere else is one nothing answers."""
    assert constant("RUNTIME_DIR") == DEFAULTS["runtime_directory"]
    assert constant("REQUEST") == "${RUNTIME_DIR}/" + kiosk.SETUP_REQUEST


def test_the_progress_is_read_where_the_helper_writes_it():
    assert constant("PROGRESS") == str(setup.OUR_DIRECTORY / setup.PROGRESS)


def test_the_owner_is_read_where_the_package_writes_it():
    """The script checks it runs as the tool's user before it writes into
    that user's runtime directory, and it reads who that is where the helper
    does."""
    assert constant("OWNER_FILE") == str(setup.OWNER_FILE)


def test_a_fresh_machine_gets_the_system_the_installer_offers_first():
    assert constant("SYSTEM") == systems.DEFAULT


def test_the_script_knows_the_steps_in_the_order_the_helper_takes_them():
    """Steps that find their work done pass quicker than the script looks, so
    it closes the ones it missed from its own list. A list in another order
    would close them out of order or not at all."""
    listed = re.search(r"^readonly INSTALL_STEPS=\(([^)]*)\)$", SCRIPT, re.M)
    assert listed, "install.sh lists no INSTALL_STEPS"

    assert tuple(listed.group(1).split()) == setup.JOBS["install"]


def test_the_request_is_one_the_helper_takes():
    """Built by printf in the script, so it is read back out of the script and
    handed to the helper's own reading of a request."""
    written = re.search(r"printf '(\{\"do\".*?\})' \"\$SYSTEM\"", SCRIPT)
    assert written, "install.sh writes no request"
    request = json.loads(written.group(1).replace("%s", constant("SYSTEM")))

    job, steps, system, machine, backup = setup.asked_for(request)

    assert job == "install"
    assert system.identifier == systems.DEFAULT
    assert machine.identifier == setup.DEFAULT_MACHINE
    assert backup is None


@pytest.mark.parametrize("step", setup.JOBS["install"])
def test_every_step_is_called_what_the_installer_window_calls_it(step):
    """Somebody who watched the one-liner and then opens the Installer window
    reads the same name for the same step."""
    assert labels("step_label").get(step) == catalogue("en")["setup.step." + step]


@pytest.mark.parametrize("doing", setup.DOINGS)
def test_every_part_of_a_step_is_said_as_the_installer_window_says_it(doing):
    assert labels("doing_label").get(doing) \
        == catalogue("en")["installer.doing." + doing]
