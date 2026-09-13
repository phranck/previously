"""Serving over HTTPS.

The certificate is made here rather than kept in the repository, so nothing
secret is committed and nothing expires in a year and takes the suite with it.
openssl is on every Debian, which is what this has to run on.
"""

import http.server
import shutil
import ssl
import subprocess
import threading
import urllib.error
import urllib.request

import pytest

from conftest import settings_for
from previously import server, tls
from previously.token import Token


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    """A self-signed certificate for localhost, and its key.

    @returns (certificate path, key path)

    Elliptic curve rather than RSA, because generating one is instant and this
    runs on a Pi.
    """
    if shutil.which("openssl") is None:
        pytest.skip("openssl is needed to make a certificate to test against")

    directory = tmp_path_factory.mktemp("tls")
    certificate = directory / "cert.pem"
    key = directory / "key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-nodes", "-days", "1",
        "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
        "-keyout", str(key), "-out", str(certificate),
        "-subj", "/CN=localhost",
        "-addext", "subjectAltName=DNS:localhost",
    ], check=True, capture_output=True)
    return certificate, key


def settings_with(tmp_path, pair=None):
    """Settings carrying a certificate, or none where pair is None.

    @param pair - (certificate path, key path), as the fixture returns it.
    """
    certificate, key = pair if pair else ("", "")
    return settings_for(tmp_path, certificate=certificate, private_key=key)


# -- what the settings make of it ----------------------------------------


def test_no_certificate_means_plain_http(tmp_path):
    """What a fresh installation does, and what a machine with no name of its
    own is stuck with."""
    settings = settings_with(tmp_path)

    assert settings.certificate is None
    assert settings.scheme == "http"
    assert tls.context(None, None) is None


def test_a_certificate_means_https(tmp_path, certificate):
    settings = settings_with(tmp_path, certificate)
    assert settings.scheme == "https"


def test_half_a_configuration_is_refused(certificate):
    """Dropping to HTTP here would hide the mistake behind a working service."""
    path, key = certificate

    with pytest.raises(tls.NotUsable):
        tls.context(path, None)
    with pytest.raises(tls.NotUsable):
        tls.context(None, key)


def test_a_certificate_that_cannot_be_read_is_refused(tmp_path, certificate):
    _, key = certificate

    with pytest.raises(tls.NotUsable):
        tls.context(tmp_path / "absent.pem", key)


def test_a_file_that_is_not_a_certificate_is_refused(tmp_path, certificate):
    _, key = certificate
    nonsense = tmp_path / "nonsense.pem"
    nonsense.write_text("this is not a certificate")

    with pytest.raises(tls.NotUsable):
        tls.context(nonsense, key)


def test_a_key_that_does_not_match_the_certificate_is_refused(tmp_path, certificate):
    """Two valid files that are not a pair, which is what a renewal writing one
    of the two would leave behind."""
    path, _ = certificate
    other_key = tmp_path / "other.pem"
    subprocess.run([
        "openssl", "genpkey", "-algorithm", "ec",
        "-pkeyopt", "ec_paramgen_curve:prime256v1", "-out", str(other_key),
    ], check=True, capture_output=True)

    with pytest.raises(tls.NotUsable):
        tls.context(path, other_key)


# -- what a browser actually gets ----------------------------------------


@pytest.fixture
def secure_service(tmp_path, certificate):
    """A running service that presents the certificate, torn down afterwards."""
    server.Handler.settings = settings_with(tmp_path, certificate)
    server.Handler.token = Token.load(tmp_path / "token")

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    httpd.socket = tls.context(*certificate).wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield "https://localhost:%d" % httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def test_a_verifying_client_gets_an_answer(secure_service, certificate):
    """Trusting nothing but this certificate, and checking the name against it,
    which is what a browser does. A test that skipped verification would prove
    only that something encrypted answered."""
    path, _ = certificate
    trusting = ssl.create_default_context(cafile=str(path))

    with urllib.request.urlopen(secure_service + "/api/health",
                                context=trusting, timeout=5) as answer:
        assert answer.status == 200


def test_the_wrong_certificate_is_not_trusted(secure_service, tmp_path):
    """The negative half of the test above. Without it, the one above would
    pass against any certificate at all."""
    stranger = tmp_path / "stranger.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-nodes", "-days", "1",
        "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
        "-keyout", str(tmp_path / "stranger-key.pem"), "-out", str(stranger),
        "-subj", "/CN=localhost",
    ], check=True, capture_output=True)
    distrusting = ssl.create_default_context(cafile=str(stranger))

    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(secure_service + "/api/health",
                               context=distrusting, timeout=5)


def test_plain_http_to_a_tls_port_is_dropped_without_taking_the_service_down(
        secure_service, certificate):
    """An old bookmark, in other words. The handshake fails inside get_request,
    where socketserver catches OSError, so the attempt goes nowhere and the
    next request still works.

    OSError rather than a narrower type, because where exactly the client gives
    up depends on how far the handshake got, and the claim being made is that
    it fails rather than that it fails in one particular way."""
    plain = secure_service.replace("https://", "http://")
    with pytest.raises(OSError):
        urllib.request.urlopen(plain + "/api/health", timeout=5)

    path, _ = certificate
    trusting = ssl.create_default_context(cafile=str(path))
    with urllib.request.urlopen(secure_service + "/api/health",
                                context=trusting, timeout=5) as answer:
        assert answer.status == 200
