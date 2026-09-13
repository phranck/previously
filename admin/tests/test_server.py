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

from conftest import settings_for
from previously import server
from previously.token import HEADER, Token


@pytest.fixture
def service(tmp_path, readable_config):
    """A running service on a port the system picks, torn down afterwards."""
    server.Handler.settings = settings_for(tmp_path)
    server.Handler.token = Token.load(tmp_path / "token")
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


# -- what a request may do -----------------------------------------------


def post(url, token=None):
    """Sends a POST, with the token where one is given."""
    request = urllib.request.Request(url, data=b"{}", method="POST")
    if token is not None:
        request.add_header(HEADER, token)
    with urllib.request.urlopen(request, timeout=5) as answer:
        return answer.status, answer.read()


def test_reading_needs_no_token(service):
    """Knowing which machine is configured costs nothing, so it is open."""
    for route in ["/api/health", "/api/status"]:
        status, _, _ = fetch(service + route)
        assert status == 200


def test_changing_anything_without_the_token_is_refused(service):
    with pytest.raises(urllib.error.HTTPError) as raised:
        post(service + "/api/anything")
    assert raised.value.code == 403


def test_a_wrong_token_is_refused(service):
    with pytest.raises(urllib.error.HTTPError) as raised:
        post(service + "/api/anything", token="not the token")
    assert raised.value.code == 403


def test_the_right_token_gets_past_the_check(service):
    """Past the check and into a route that does not exist yet, which is a 404
    rather than a 403. The difference is the whole point of the test."""
    with pytest.raises(urllib.error.HTTPError) as raised:
        post(service + "/api/anything", token=server.Handler.token.value)
    assert raised.value.code == 404


def test_a_service_without_a_token_refuses_every_change(service):
    kept = server.Handler.token
    server.Handler.token = None
    try:
        with pytest.raises(urllib.error.HTTPError) as raised:
            post(service + "/api/anything", token="anything at all")
        assert raised.value.code == 403
    finally:
        server.Handler.token = kept


def test_the_token_route_says_whether_one_is_right(service):
    status, _, body = fetch(service + "/api/token")
    assert status == 200
    assert json.loads(body)["valid"] is False

    request = urllib.request.Request(service + "/api/token")
    request.add_header(HEADER, server.Handler.token.value)
    with urllib.request.urlopen(request, timeout=5) as answer:
        assert json.loads(answer.read())["valid"] is True


# -- what gets into the journal ------------------------------------------


def handler_without_a_request():
    """A handler that never got as far as parsing anything.

    Built without __init__, because that method is where the standard library
    reads the socket and handles the whole request, and what is under test here
    is one method rather than a request.

    It carries client_address and nothing else, which is the real state: that
    one is set before the request is read, and path only after it parses.
    """
    handler = server.Handler.__new__(server.Handler)
    handler.client_address = ("10.0.0.23", 54321)
    return handler


def test_a_request_that_never_parsed_is_logged_rather_than_raising(capsys):
    """parse_request is what sets path, so anything failing before that reaches
    the logger without one. Reading it there is what put twenty tracebacks in
    the journal on the Pi."""
    handler = handler_without_a_request()

    handler.log_error("code %d, message %s", 400, "Bad request version")

    assert "Bad request version" in capsys.readouterr().err


def test_log_message_survives_a_request_that_never_parsed(capsys):
    """The same attribute, reached the other way. log_message is handed to a
    library that decides when to call it, so it has no business assuming how
    far the request got."""
    handler = handler_without_a_request()

    handler.log_message("something happened")

    # Whether it prints is the other tests' business. Not raising is this one's.


def test_a_static_file_is_not_logged(capsys):
    """The whole reason the override exists: a page load is a dozen files and
    a kiosk should not write a line for each."""
    handler = handler_without_a_request()
    handler.path = "/nextstep.css"

    handler.log_message("%s", "GET /nextstep.css")

    assert capsys.readouterr().err == ""


def test_an_api_request_is_logged(capsys):
    handler = handler_without_a_request()
    handler.path = "/api/status"

    handler.log_message("%s", "GET /api/status")

    assert "/api/status" in capsys.readouterr().err


def test_an_error_is_logged_even_on_a_connection_that_served_a_file(capsys):
    """path survives from one request to the next on a keep-alive connection,
    so a malformed second request would be filtered out by its predecessor's
    path. Errors do not go through that filter at all."""
    handler = handler_without_a_request()
    handler.path = "/index.html"

    handler.log_error("code %d, message %s", 400, "Bad request syntax")

    assert "Bad request syntax" in capsys.readouterr().err


# -- changing the machine ------------------------------------------------


def test_the_catalogue_is_open(service):
    """Which machines exist costs nothing to know, so it reads like the rest."""
    status, _, body = fetch(service + "/api/machines")
    names = [machine["id"] for machine in json.loads(body)["machines"]]

    assert status == 200
    assert "nextcube-turbo" in names
    assert len(names) == len(set(names))


def test_changing_the_machine_needs_the_token(service):
    request = urllib.request.Request(
        service + "/api/machine", data=b'{"machine": "nextcube"}', method="POST")
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=5)
    assert raised.value.code == 403


def test_a_request_that_is_not_readable_is_refused_before_anything_happens(service):
    request = urllib.request.Request(
        service + "/api/machine", data=b"this is not json", method="POST")
    request.add_header(HEADER, server.Handler.token.value)

    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=5)
    assert raised.value.code == 400


def test_a_machine_that_does_not_exist_is_refused(service):
    request = urllib.request.Request(
        service + "/api/machine", data=b'{"machine": "amiga-2000"}', method="POST")
    request.add_header(HEADER, server.Handler.token.value)

    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=5)
    assert raised.value.code == 409
    assert "keine Maschine" in json.loads(raised.value.read())["reason"]
