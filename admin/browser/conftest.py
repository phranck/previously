"""The real service and a real browser, for what only a browser can show.

Layout is the browser's, so a scroller that reads the wrong size or misses a
change can only be caught in one. These run in Safari Technology Preview
through its own `safaridriver`, which drives a browser of its own beside any
Safari that is open, and against the service itself, started here with a home
and a state directory of its own under the test's temporary directory.

They drive a browser, so they are not part of `make check`. `make browser`
runs them, and they skip where Safari Technology Preview or Selenium is not
there, which is every machine but a Mac set up for it.
"""

import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from previously import discs, systems

webdriver = pytest.importorskip("selenium.webdriver")

ADMIN = pathlib.Path(__file__).resolve().parent.parent
SAFARI = pathlib.Path("/Applications/Safari Technology Preview.app/Contents/MacOS/safaridriver")

#: Large enough that the desk lays out as on a desktop rather than a phone.
WINDOW = {"width": 1700, "height": 1150}

#: How long the service may take to answer after it is started.
START_SECONDS = 15


def free_port():
    """@returns int, a port nothing on this machine is listening on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="session")
def service(tmp_path_factory):
    """The service, serving the built interface, until the session ends.

    @returns str, the address it answers on.

    Every path it reads or writes is under one temporary directory, so it
    touches nothing of this machine's, and it is told which by a configuration
    file rather than by anything it would not also read on a Pi.
    """
    root = tmp_path_factory.mktemp("service")
    home = root / "home"
    for place in (".config/previous", ".config/previously", "nextstep",
                  "Previously/Documents/Pictures"):
        (home / place).mkdir(parents=True, exist_ok=True)
    # A disk and a disc, so the File Viewer holds what it holds on a machine
    # that is set up. Disks and Discs are left out of it until something is
    # in them, and an empty file is enough for the service to list either.
    disks = home / "nextstep"
    (disks / systems.disk_name(systems.find(systems.DEFAULT))).touch()
    discs.folder(disks).mkdir()
    (discs.folder(disks) / "tools.iso").touch()
    port = free_port()
    config = root / "config.ini"
    config.write_text("\n".join([
        "[service]",
        "address = 127.0.0.1",
        "port = %d" % port,
        "previous_config = %s" % (home / ".config/previous/previous.cfg"),
        "machines_file = %s" % (home / ".config/previously/machines.json"),
        "documents = %s" % (home / "Previously"),
        "disks = %s" % (home / "nextstep"),
        "state_directory = %s" % (root / "state"),
        "runtime_directory = %s" % (root / "run"),
        "setup_directory = %s" % (root / "setup"),
        "password_file = %s" % (root / "state" / "password"),
        ""]), encoding="utf-8")
    for place in ("state", "run", "setup"):
        (root / place).mkdir()

    started = subprocess.Popen(
        [sys.executable, "-c",
         "import pathlib, sys\n"
         "from previously.password import Password\n"
         "from previously.server import serve\n"
         "from previously.settings import Settings\n"
         "settings = Settings.load(pathlib.Path(sys.argv[1]))\n"
         "serve(settings, Password(settings.password_file))\n",
         str(config)],
        cwd=ADMIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    address = "http://127.0.0.1:%d/" % port
    try:
        deadline = time.monotonic() + START_SECONDS
        while True:
            try:
                urllib.request.urlopen(address + "api/health", timeout=1)
                break
            except OSError:
                if time.monotonic() > deadline or started.poll() is not None:
                    pytest.fail("the service did not start on %s" % address)
                time.sleep(0.2)
        yield address
    finally:
        started.terminate()
        started.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    """Safari Technology Preview, driven by its own safaridriver.

    Remote automation is switched on in it already; a session that fails has
    another cause, and `log show --last 2m --predicate 'process CONTAINS
    "safaridriver"'` names it.
    """
    if not SAFARI.exists():
        pytest.skip("Safari Technology Preview is not installed")
    options = webdriver.safari.options.Options()
    options.use_technology_preview = True
    driving = webdriver.safari.service.Service(executable_path=str(SAFARI))
    driver = webdriver.Safari(options=options, service=driving)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    try:
        driver.set_window_rect(x=0, y=0, **WINDOW)
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def desk(service, browser):
    """The desk on a first visit, with nothing remembered from the last test.

    @returns the driver, on the page.
    """
    browser.get(service)
    browser.execute_script("localStorage.clear()")
    browser.get(service)
    browser.execute_script("document.querySelector('nx-ask').close?.(true)")
    return browser
