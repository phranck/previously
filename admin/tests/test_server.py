"""The HTTP layer.

Tested through a real server on a real socket rather than by calling the
handler's methods, because what matters is what reaches a browser: the status
line, the headers and the body.
"""

import json
import threading
import http.server
import urllib.error
import urllib.parse
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
    assert payload["configuration"]["model"] == "NeXTcube"
    assert payload["configuration"]["turbo"] is True
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


def machines_in(tree):
    """@returns The machines anywhere in the tree, by identifier."""
    found = {}
    for entry in tree.get("entries", []):
        if entry.get("kind") == "machine":
            found[entry["id"]] = entry
        else:
            found.update(machines_in(entry))
    return found


def test_the_status_says_which_of_the_eleven_the_file_is(service):
    """So the viewer marks the machine that is really running rather than the
    one whose name the file happens to carry."""
    _, _, body = fetch(service + "/api/status")
    answer = json.loads(body)

    assert "catalogue" in answer["configuration"]


def test_the_tree_is_open(service):
    """What this tool holds costs nothing to know, so it reads like the rest."""
    status, _, body = fetch(service + "/api/files")
    tree = json.loads(body)

    assert status == 200
    assert tree["name"] == "Previously"
    assert [entry["name"] for entry in tree["entries"]] == [
        "Apps", "Documents", "Machines"]


def test_the_eleven_sit_in_a_folder_that_cannot_be_written(service):
    _, _, body = fetch(service + "/api/files")
    tree = json.loads(body)
    machines_folder = next(e for e in tree["entries"] if e["name"] == "Machines")
    system = next(e for e in machines_folder["entries"] if e["name"] == "System")

    assert system["writable"] is False
    assert len(system["entries"]) == 11
    assert system["entries"][0]["path"] == "/Machines/System/next-computer"


def test_there_is_no_user_folder_until_something_is_in_it(service):
    """An empty folder would promise something that is not there."""
    _, _, body = fetch(service + "/api/files")
    tree = json.loads(body)
    machines_folder = next(e for e in tree["entries"] if e["name"] == "Machines")

    assert [entry["name"] for entry in machines_folder["entries"]] == ["System"]


def test_every_machine_says_which_case_it_is_in(service):
    """The viewer draws a picture per machine before anything is running, so
    the case travels with the entry rather than being read out of the name."""
    _, _, body = fetch(service + "/api/files")
    cases = {identifier: machine["enclosure"]
             for identifier, machine in machines_in(json.loads(body)).items()}

    assert cases["nextcube-turbo"] == "cube"
    assert cases["nextstation-color"] == "station"
    assert set(cases.values()) == {"cube", "station"}


def test_the_applications_are_there_and_say_what_they_open(service):
    _, _, body = fetch(service + "/api/files")
    tree = json.loads(body)
    apps = next(e for e in tree["entries"] if e["name"] == "Apps")

    assert [entry["name"] for entry in apps["entries"]] == [
        "Config Editor.app", "Grab.app", "Preferences.app", "Preview.app",
        "Terminal.app"]
    assert [entry["opens"] for entry in apps["entries"]] == [
        "editor", "grab", "preferences", "preview", "terminal"]


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
    assert json.loads(raised.value.read())["reason"] == "machine.no-such"


# -- a picture of the emulated screen -------------------------------------


def test_a_picture_of_the_screen_needs_the_token(service, monkeypatch):
    """The one reading that does. Everything else this service tells is about
    the machine; a picture is about whoever is sitting at it."""
    monkeypatch.setattr(server.grab, "take",
                        lambda: pytest.fail("refused before it was taken"))

    with pytest.raises(urllib.error.HTTPError) as refused:
        fetch(service + "/api/screen")

    assert refused.value.code == 403


def test_the_picture_arrives_as_a_png(service, monkeypatch):
    monkeypatch.setattr(server.grab, "take", lambda: b"\x89PNG\r\n\x1a\npixels")
    request = urllib.request.Request(service + "/api/screen")
    request.add_header(HEADER, server.Handler.token.value)

    with urllib.request.urlopen(request, timeout=5) as answer:
        body = answer.read()
        assert answer.status == 200
        assert answer.headers["Content-Type"] == "image/png"
        assert answer.headers["Content-Length"] == str(len(body))
        assert answer.headers["Cache-Control"] == "no-store"
    assert body == b"\x89PNG\r\n\x1a\npixels"


def test_a_screen_that_cannot_be_read_says_so(service, monkeypatch):
    """Rather than sending an empty picture, which a browser draws as a
    broken one and nobody can tell from a black screen."""
    monkeypatch.setattr(server.grab, "take", lambda: None)
    request = urllib.request.Request(service + "/api/screen")
    request.add_header(HEADER, server.Handler.token.value)

    with pytest.raises(urllib.error.HTTPError) as failed:
        urllib.request.urlopen(request, timeout=5)

    assert failed.value.code == 503


def test_the_picture_is_kept_as_well_as_sent(service, tmp_path, monkeypatch):
    """A screenshot is a document. It goes into the folder the File Viewer
    shows as Documents/Pictures, where the emulated machine reaches it too."""
    monkeypatch.setattr(server.grab, "take", lambda: b"\x89PNG\r\n\x1a\npixels")
    request = urllib.request.Request(service + "/api/screen")
    request.add_header(HEADER, server.Handler.token.value)

    with urllib.request.urlopen(request, timeout=5) as answer:
        filed = answer.headers["X-Previously-Kept"]

    kept = tmp_path / "Previously" / "Documents" / "Pictures"
    assert [path.name for path in kept.iterdir()] == [filed]
    assert (kept / filed).stat().st_size > 0


def test_a_kept_picture_is_in_the_tree(service, tmp_path, monkeypatch):
    monkeypatch.setattr(server.grab, "take", lambda: b"\x89PNG\r\n\x1a\npixels")
    request = urllib.request.Request(service + "/api/screen")
    request.add_header(HEADER, server.Handler.token.value)
    with urllib.request.urlopen(request, timeout=5) as answer:
        filed = answer.headers["X-Previously-Kept"]

    _, _, body = fetch(service + "/api/files")
    tree = json.loads(body)
    documents = next(e for e in tree["entries"] if e["name"] == "Documents")
    pictures = next(e for e in documents["entries"] if e["name"] == "Pictures")

    assert [entry["name"] for entry in pictures["entries"]] == [filed]
    assert pictures["entries"][0]["kind"] == "picture"
    assert pictures["entries"][0]["path"] == "/Documents/Pictures/" + filed


def test_documents_is_there_before_anything_is_in_it(service):
    """The place a picture goes is visible before the first one is taken,
    rather than appearing once something lands in it."""
    _, _, body = fetch(service + "/api/files")
    tree = json.loads(body)
    documents = next(e for e in tree["entries"] if e["name"] == "Documents")

    assert [entry["name"] for entry in documents["entries"]] == ["Pictures"]
    assert documents["entries"][0]["entries"] == []


# -- one kept picture -----------------------------------------------------


def kept_picture(tmp_path, name="Screen 2026-09-16 08.00.00.png",
                 content=b"\x89PNG\r\n\x1a\nkept"):
    """Puts a picture where the service keeps them, as Grab would have."""
    where = tmp_path / "Previously" / "Documents" / "Pictures"
    where.mkdir(parents=True, exist_ok=True)
    (where / name).write_bytes(content)
    return name


def ask_for(service, name):
    """Asks for one picture by name, with the token."""
    request = urllib.request.Request(
        service + "/api/picture?name=" + urllib.parse.quote(name))
    request.add_header(HEADER, server.Handler.token.value)
    return urllib.request.urlopen(request, timeout=5)


def test_a_kept_picture_is_served(service, tmp_path):
    name = kept_picture(tmp_path)

    with ask_for(service, name) as answer:
        assert answer.status == 200
        assert answer.headers["Content-Type"] == "image/png"
        assert answer.read() == b"\x89PNG\r\n\x1a\nkept"


def test_a_picture_needs_the_token(service, tmp_path):
    """Same reason as the route that takes one: it shows whoever was sitting
    at that machine."""
    name = kept_picture(tmp_path)

    with pytest.raises(urllib.error.HTTPError) as refused:
        fetch(service + "/api/picture?name=" + urllib.parse.quote(name))

    assert refused.value.code == 403


@pytest.mark.parametrize("asked", [
    "../../../etc/passwd",
    "..%2f..%2ftoken",
    "/etc/passwd",
    "",
    "nothing-of-that-name.png",
])
def test_nothing_outside_the_pictures_folder_is_served(service, tmp_path, asked):
    """The name is read as a name, so everything up to the last separator is
    thrown away and what is left is looked for in that one folder."""
    kept_picture(tmp_path)

    with pytest.raises(urllib.error.HTTPError) as refused:
        ask_for(service, asked)

    assert refused.value.code == 404


def test_a_file_that_is_not_a_picture_is_not_served(service, tmp_path):
    """Preview opens pictures, so that is what this hands out, whatever else
    somebody has put in the folder."""
    kept_picture(tmp_path, name="notes.txt", content=b"not a picture")

    with pytest.raises(urllib.error.HTTPError) as refused:
        ask_for(service, "notes.txt")

    assert refused.value.code == 404


# -- taking a picture away ------------------------------------------------


def ask_to_delete(service, name, with_token=True):
    """Asks for one picture to go, the way the page does."""
    request = urllib.request.Request(
        service + "/api/picture/delete",
        data=json.dumps({"name": name}).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    if with_token:
        request.add_header(HEADER, server.Handler.token.value)
    return urllib.request.urlopen(request, timeout=5)


def test_a_picture_can_be_deleted(service, tmp_path):
    name = kept_picture(tmp_path)
    where = tmp_path / "Previously" / "Documents" / "Pictures"

    with ask_to_delete(service, name) as answer:
        assert answer.status == 200
        assert json.loads(answer.read())["ok"] is True
    assert list(where.iterdir()) == []


def test_deleting_needs_the_token(service, tmp_path):
    name = kept_picture(tmp_path)
    where = tmp_path / "Previously" / "Documents" / "Pictures"

    with pytest.raises(urllib.error.HTTPError) as refused:
        ask_to_delete(service, name, with_token=False)

    assert refused.value.code == 403
    assert (where / name).is_file(), "refused and deleted it anyway"


@pytest.mark.parametrize("asked", [
    "../../../etc/passwd",
    "/etc/passwd",
    "",
    "nothing-of-that-name.png",
])
def test_nothing_outside_the_pictures_folder_is_deleted(service, tmp_path, asked):
    """The name is read as a name, so a request naming a path asks for that
    name inside the one folder, where it is not."""
    name = kept_picture(tmp_path)
    where = tmp_path / "Previously" / "Documents" / "Pictures"

    with pytest.raises(urllib.error.HTTPError) as refused:
        ask_to_delete(service, asked)

    assert refused.value.code == 404
    assert (where / name).is_file()


def test_a_file_that_is_not_a_picture_is_not_deleted(service, tmp_path):
    """Nothing else in that folder is this service's to delete."""
    kept_picture(tmp_path, name="notes.txt", content=b"not a picture")
    where = tmp_path / "Previously" / "Documents" / "Pictures"

    with pytest.raises(urllib.error.HTTPError) as refused:
        ask_to_delete(service, "notes.txt")

    assert refused.value.code == 404
    assert (where / "notes.txt").is_file()
