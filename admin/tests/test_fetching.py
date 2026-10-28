"""Where a fetch may go, and where it may be sent on to.

Nothing here reaches the network. What is tested is the rule itself, because it
is the one check standing between a privileged helper and an address somebody
else chose, and because it fails silently: a fetch that followed a redirect it
should not have still answers with a file.
"""

import urllib.error

import pytest

from previously import fetching

#: A set that has both a bare name and one whose subdomains count, which is what
#: both callers pass: archive.org serves items off its own nodes, and GitHub
#: serves a release asset off a host under githubusercontent.com.
HOSTS = ("api.github.com", "github.com", "githubusercontent.com")


@pytest.mark.parametrize("url", [
    "https://github.com/phranck/previously/releases/download/v1.0.0/x.deb",
    "https://api.github.com/repos/phranck/previously/releases/latest",
    "https://release-assets.githubusercontent.com/github-production/1/2",
])
def test_an_address_on_those_hosts_may_be_asked(url):
    assert fetching.allowed(url, HOSTS) is True


@pytest.mark.parametrize("url", [
    # The one a string test lets through, which is the whole reason the host is
    # parsed rather than searched for.
    "https://github.com.example.com/x.deb",
    "https://example.com/x.deb",
    # Plain HTTP, where the answer is whatever the network chose to send back.
    "http://github.com/x.deb",
    "file:///etc/passwd",
    "",
])
def test_anything_else_may_not(url):
    assert fetching.allowed(url, HOSTS) is False


@pytest.mark.parametrize("newurl", [
    "https://example.com/x.deb",
    "http://github.com/x.deb",
])
def test_a_redirect_off_those_hosts_ends_the_fetch(newurl):
    """Whoever answers the first request chooses where the second one goes, so
    every hop is checked as the first address was."""
    handler = fetching.OnlyThese(HOSTS)

    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(None, None, 302, "Found", {}, newurl)


def test_an_address_this_may_not_ask_is_refused_before_it_is_asked(monkeypatch):
    """The first address is checked as well, because both callers now pass one
    they were handed rather than one they wrote."""
    monkeypatch.setattr(
        fetching.urllib.request, "build_opener",
        lambda *handlers: pytest.fail("asked it anyway"))

    with pytest.raises(urllib.error.URLError):
        fetching.opened("https://example.com/x.deb", HOSTS, 1)


# -- addresses inside this network ---------------------------------------


def resolving_to(monkeypatch, *addresses):
    """Lets every host name resolve to these addresses, as getaddrinfo would
    answer for a TCP connection."""
    def answer(host, port, *rest, **named):
        return [(None, None, None, "", (address, port)) for address in addresses]
    monkeypatch.setattr(fetching.socket, "getaddrinfo", answer)


@pytest.mark.parametrize("addresses", [
    ("127.0.0.1",),
    ("10.0.0.5",),
    ("192.168.1.20",),
    ("169.254.1.1",),
    ("::1",),
    ("fd00::1",),
    ("fe80::1%eth0",),
    # One address inside is enough, because the connection may take any of them.
    ("207.241.224.2", "10.0.0.5"),
])
def test_a_host_that_resolves_into_this_network_is_not_public(monkeypatch, addresses):
    """An entry somebody typed in could otherwise point the Pi at the router or
    at itself."""
    resolving_to(monkeypatch, *addresses)
    assert fetching.public("https://downloads.example.org/x.iso") is False


def test_a_host_that_resolves_only_into_the_internet_is_public(monkeypatch):
    resolving_to(monkeypatch, "207.241.224.2", "2620:0:9c0:200::2")
    assert fetching.public("https://archive.org/download/x/x.iso") is True


def test_an_address_literal_is_not_public(monkeypatch):
    """Named by a number, which no download of the catalog is."""
    monkeypatch.setattr(fetching.socket, "getaddrinfo",
                        lambda *asked, **named: pytest.fail("resolved it anyway"))
    assert fetching.public("https://207.241.224.2/x.iso") is False


def test_a_host_that_does_not_resolve_is_not_public(monkeypatch):
    def answer(*asked, **named):
        raise fetching.socket.gaierror("no such host")
    monkeypatch.setattr(fetching.socket, "getaddrinfo", answer)
    assert fetching.public("https://nowhere.example.org/x.iso") is False


def test_a_redirect_into_this_network_ends_the_fetch(monkeypatch):
    """The host is one of those allowed, and it resolves inside."""
    resolving_to(monkeypatch, "10.0.0.1")
    handler = fetching.OnlyThese(HOSTS, only_public=True)

    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(None, None, 302, "Found", {}, "https://github.com/x.deb")


def test_an_address_into_this_network_is_refused_before_it_is_asked(monkeypatch):
    resolving_to(monkeypatch, "192.168.1.1")
    monkeypatch.setattr(
        fetching.urllib.request, "build_opener",
        lambda *handlers: pytest.fail("asked it anyway"))

    with pytest.raises(fetching.NotAllowed):
        fetching.opened("https://github.com/x.deb", HOSTS, 1, only_public=True)
