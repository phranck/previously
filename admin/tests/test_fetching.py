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
