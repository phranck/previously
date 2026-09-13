"""The HTTP layer.

Tested through a real server on a real socket rather than by calling the
handler's methods, because what matters is what reaches a browser: the status
line, the headers and the body.
"""

import json
import threading
import http.server
import urllib.error
import urllib.request

import pytest

from nextstep_admin import server
from nextstep_admin.settings import Settings


@pytest.fixture
def service(tmp_path):
    """A running service on a port the system picks, torn down afterwards."""
    config_file = tmp_path / "previous.cfg"
    config_file.write_text(
        "[System]\nnMachineType = 1\nbTurbo = TRUE\nnCpuLevel = 4\n"
        "nCpuFreq = 33\n\n[Memory]\nnMemoryBankSize0 = 64\n"
    )
    settings = Settings({
        "address": "127.0.0.1",
        "port": "0",
        "previous_config": str(config_file),
        "kiosk_unit": "does-not-exist.service",
    })

    server.Handler.settings = settings
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def fetch(url):
    with urllib.request.urlopen(url, timeout=5) as answer:
        return answer.status, answer.headers, answer.read()


def test_health_says_whether_the_configuration_can_be_read(service):
    status, headers, body = fetch(service + "/api/health")

    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    payload = json.loads(body)
    assert payload["config_readable"] is True
    assert payload["version"] == server.VERSION


def test_health_reports_an_unreadable_configuration_rather_than_failing(service, tmp_path):
    server.Handler.settings.previous_config = tmp_path / "gone.cfg"
    status, _, body = fetch(service + "/api/health")

    assert status == 200
    assert json.loads(body)["config_readable"] is False


def test_status_carries_the_machine_and_whether_it_runs(service):
    status, _, body = fetch(service + "/api/status")
    payload = json.loads(body)

    assert status == 200
    assert payload["configuration"]["machine"] == "NeXTcube Turbo"
    # The unit in the fixture does not exist, so this is the false case.
    assert payload["running"] is False
    assert payload["uptime_seconds"] is None


def test_nothing_is_cached(service):
    """Every answer is about right now, and a cached one is a wrong one."""
    _, headers, _ = fetch(service + "/api/status")
    assert headers["Cache-Control"] == "no-store"


def test_the_python_version_is_not_announced(service):
    _, headers, _ = fetch(service + "/api/health")
    assert "Python" not in headers.get("Server", "")


def test_an_unknown_path_is_a_404(service):
    with pytest.raises(urllib.error.HTTPError) as raised:
        fetch(service + "/does-not-exist")
    assert raised.value.code == 404


@pytest.mark.parametrize("route", [
    "/../settings.py",
    "/../../etc/passwd",
    "/..%2f..%2fetc%2fpasswd",
    "//etc/passwd",
])
def test_a_request_cannot_climb_out_of_the_web_directory(service, route):
    """A path in a request is a string from the network, so `..` in it is a
    question about which file rather than a typing mistake."""
    try:
        status, _, _ = fetch(service + route)
    except urllib.error.HTTPError as error:
        assert error.code == 404
    else:
        assert status == 404


def test_safe_path_refuses_to_leave_its_root(tmp_path):
    (tmp_path / "inside.txt").write_text("here")
    assert server.safe_path(tmp_path, "/inside.txt") is not None
    assert server.safe_path(tmp_path, "/../outside.txt") is None
    assert server.safe_path(tmp_path, "/a/../../outside.txt") is None


def test_an_empty_path_means_the_index(tmp_path):
    assert server.safe_path(tmp_path, "/").name == "index.html"
