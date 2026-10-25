"""The one-liner, held against the helper it hands the machine to.

`install.sh` installs the admin tool and then asks its privileged helper for
everything else, the same job the Installer window asks for. It runs before the
tool exists on the machine, so it cannot import anything from it, and it names a
few things a second time: where the request goes, where the progress is read,
which system a fresh machine gets, and what each step is called on the screen.
These tests are what keeps those in step with the side that decides them.
"""

import json
import os
import pathlib
import re
import subprocess

import pytest

from previously import kiosk, setup, systems
from previously.settings import DEFAULTS
from test_strings import catalogue

SCRIPT_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "install.sh"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")
LIBRARY_BUILD = (SCRIPT_PATH.parent / "admin" / "display" / "build.sh").read_text(
    encoding="utf-8")


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


@pytest.mark.parametrize("arguments", [[], ["--update-admin"]])
def test_the_password_is_asked_before_anything_else_is_printed(tmp_path, arguments):
    """sudo writes its prompt to the terminal itself, so a prompt that comes
    after the banner breaks into what the script shows. Here sudo refuses,
    which ends the run at the prompt, so whatever was printed by then is
    everything that came before it."""
    tools = tmp_path / "bin"
    tools.mkdir()
    sudo = tools / "sudo"
    sudo.write_text("#!/bin/sh\nexit 1\n")
    sudo.chmod(0o755)

    ran = subprocess.run(
        ["bash", str(SCRIPT_PATH), *arguments], capture_output=True, text=True,
        timeout=30, check=False,
        env=dict(os.environ, PATH="%s:%s" % (tools, os.environ["PATH"]),
                 TMPDIR=str(tmp_path), NO_COLOR="1"))

    assert ran.returncode == 1, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == [
        "  The next steps need sudo.",
        "  ✗ sudo did not let this run.",
    ]


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


# -- a second run --------------------------------------------------------


#: Stand-ins for what the script asks the machine, each reading and writing
#: the state the test sets up in $STATE.
STAND_INS = {
    "sudo": 'case "$1" in -n|-v) exit 0 ;; esac\nexec env "$@"\n',
    # Installing the package makes its version the one that is here.
    "apt-get": 'echo "$*" >> "$STATE/apt-get"\n'
               'case " $* " in *" install "*) cp "$STATE/newest" "$STATE/here" ;; esac\n',
    "dpkg-query": '[ -f "$STATE/here" ] || exit 1\n'
                  'case "$*" in *Status*) echo "install ok installed" ;; '
                  '*) cat "$STATE/here" ;; esac\n',
    "dpkg-deb": 'cat "$STATE/newest"\n',
    # Enough of dpkg's ordering for versions made of numbers and dots.
    "dpkg": 'exec python3 -c \'import sys; key = lambda version: tuple('
            'int(part) for part in version.split(".")); '
            'sys.exit(0 if key(sys.argv[1]) > key(sys.argv[3]) else 1)\' "$2" "$3" "$4"\n',
    "curl": 'while [ $# -gt 0 ]; do\n'
            '  if [ "$1" = -o ]; then shift; echo package > "$1"; fi\n'
            '  shift\ndone\n',
    # Records what it was asked to build, and fails on a Pi with no compiler.
    "make": 'echo "make $*" >> "$STATE/built"\n[ ! -f "$STATE/no-compiler" ]\n',
    # One answer per call, out of $STATE/states, and inactive once they run out.
    "systemctl": 'if [ -s "$STATE/states" ]; then\n'
                 '  head -n 1 "$STATE/states"\n'
                 '  sed -i.before 1d "$STATE/states"\n'
                 'else\n  echo inactive\nfi\nexit 3\n',
}


def with_the_script(tmp_path, snippet, here=None, newest="1.9.0", states=(),
                    status=0):
    """Runs shell with install.sh's functions defined and the machine stood in for.

    @param snippet - What to run once the functions are there.
    @param here - The version of the admin tool installed, or None for none.
    @param newest - The version the fetched package carries.
    @param states - What `systemctl is-active` answers, one call after another.
    @param status - The status the run has to end with.
    @returns (subprocess.CompletedProcess, list of str): what the run said, with
      a line `undo: <what>` for each entry on the undo record after it, and
      every call apt-get received.
    """
    tools = tmp_path / "bin"
    tools.mkdir()
    for name, body in STAND_INS.items():
        (tools / name).write_text("#!/bin/sh\n" + body, encoding="utf-8")
        (tools / name).chmod(0o755)

    state = tmp_path / "state"
    state.mkdir()
    (state / "newest").write_text(newest, encoding="utf-8")
    if here:
        (state / "here").write_text(here, encoding="utf-8")
    (state / "states").write_text("".join(line + "\n" for line in states),
                                  encoding="utf-8")

    # The script without the call to main, so sourcing it defines everything
    # and runs nothing. Beside nothing, so it fetches the package as a run off
    # the network does.
    functions = tmp_path / "functions.sh"
    functions.write_text(SCRIPT[:SCRIPT.rindex('main "$@"')], encoding="utf-8")

    ran = subprocess.run(
        ["bash", "-c", 'source "$1"; LOG="$(mktemp)"; %s; COMPLETED=true; '
                       'for what in "${UNDO_WHAT[@]}"; do echo "undo: $what"; done'
         % snippet, "_", str(functions)],
        capture_output=True, text=True, timeout=30, check=False,
        env=dict(os.environ, PATH="%s:%s" % (tools, os.environ["PATH"]),
                 TMPDIR=str(tmp_path), STATE=str(state), NO_COLOR="1"))
    assert ran.returncode == status, ran.stdout + ran.stderr
    called = state / "apt-get"
    return ran, (called.read_text(encoding="utf-8").splitlines()
                 if called.exists() else [])


def test_a_second_run_replaces_an_older_admin_tool(tmp_path):
    """The helper that sets the machine up is part of the tool, so a run that
    failed over a defect fixed since would fail the same way again with the
    tool it left behind."""
    ran, apt = with_the_script(tmp_path, "install_admin", here="1.8.0",
                               newest="1.9.0")

    assert "  ✓ The admin tool 1.8.0 replaced by 1.9.0" in ran.stdout.splitlines()
    assert [call for call in apt if " install " in call]
    assert "undo: remove the admin tool" not in ran.stdout, \
        "a rollback would take away the tool that was working"


def test_a_second_run_leaves_a_current_admin_tool_alone(tmp_path):
    ran, apt = with_the_script(tmp_path, "install_admin", here="1.9.0",
                               newest="1.9.0")

    assert "  ✓ The admin tool 1.9.0  already in place" in ran.stdout.splitlines()
    assert apt == []


def checkout(tmp_path):
    """Lays a checkout out beside the script, as on a Pi that runs it from one.

    @param tmp_path - Where the script is, and so where it looks for the checkout.
    @returns pathlib.Path, the directory the library is built in.
    """
    packaging = tmp_path / "admin" / "packaging"
    packaging.mkdir(parents=True)
    (packaging / "build.py").write_text(
        'import os\n'
        'with open(os.path.join(os.environ["STATE"], "built"), "a") as built:\n'
        '    built.write("package\\n")\n'
        'print("Built", "previously.deb")\n', encoding="utf-8")
    return tmp_path.resolve() / "admin" / "display"


def test_a_checkout_builds_the_library_before_the_package(tmp_path):
    """The package takes the library that shows Previous sharp from beside its
    source and refuses to be built without it, and the Pi is the machine it is
    compiled for."""
    display = checkout(tmp_path)

    ran, _ = with_the_script(tmp_path, 'fetch_admin_package; echo "$ADMIN_PACKAGE"')

    assert ran.stdout.splitlines() == ["previously.deb"]
    assert (tmp_path / "state" / "built").read_text(encoding="utf-8").splitlines() \
        == ["make -C %s pixel-exact.so" % display, "package"]


def test_a_checkout_on_a_pi_without_a_compiler_names_what_it_needs(tmp_path):
    display = checkout(tmp_path)

    ran, _ = with_the_script(
        tmp_path, 'touch "$STATE/no-compiler"; fetch_admin_package', status=1)

    assert ran.stdout.splitlines() == [
        "  ✗ Could not build the library that shows Previous sharp. "
        "Building it takes these packages: %s." % constant("LIBRARY_PACKAGES")]
    assert (tmp_path / "state" / "built").read_text(encoding="utf-8").splitlines() \
        == ["make -C %s pixel-exact.so" % display]


def test_the_packages_named_for_the_library_are_the_ones_it_is_built_with():
    """display/build.sh installs them in the container that builds the library
    for a release, and a Pi building it from a checkout needs the same."""
    installed = re.search(r"--no-install-recommends \\\n\s+([^>]+?) >", LIBRARY_BUILD)
    assert installed, "display/build.sh installs no packages"

    assert constant("LIBRARY_PACKAGES").split() == installed.group(1).split()


def test_a_run_already_under_way_is_waited_for(tmp_path):
    """One that an earlier run of the script handed over before it was
    stopped, or one the Installer window started. Replacing the tool under it
    or asking for a second job would have two apt runs at once."""
    ran, _ = with_the_script(tmp_path, "wait_for_a_run_under_way",
                             states=("activating", "activating"))

    assert ran.stdout.splitlines() == [
        "  ✓ The run already under way on the Pi has ended"]
    assert (tmp_path / "state" / "states").read_text(encoding="utf-8") == ""


def test_nothing_is_said_where_no_run_is_under_way(tmp_path):
    ran, _ = with_the_script(tmp_path, "wait_for_a_run_under_way")

    assert ran.stdout == ""


def test_both_ways_in_wait_before_they_touch_the_tool():
    main = re.search(r"^main\(\) \{\n(.*?)\n\}", SCRIPT, re.M | re.S)
    assert main, "install.sh has no main"

    assert re.findall(r"wait_for_a_run_under_way\n\s+(\w+)", main.group(1)) \
        == ["update_admin", "install_admin"]
