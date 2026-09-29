"""A fetch that may only reach the hosts it was given.

Two things are downloaded onto this machine and both are checked the same way:
a prepared system from archive.org, and this tool's own package from GitHub. The
check lives here once, because a copy of it per caller is two rules that can
disagree and the disagreement would be invisible: a fetch that followed a
redirect it should not have still answers with a file.

A redirect is where the check has to be made again. Whoever answers the first
request chooses where the second one goes, so the address of every hop is
checked as the first one was, and an address that arrived in somebody else's
answer is checked before it is asked at all.
"""

import collections
import urllib.error
import urllib.parse
import urllib.request

#: What a fetch has to turn out to be.
#:
#: `name` is what a complaint about it calls the thing, `size` and `digest` are
#: what the file is, and `algorithm` names the digest because the two places
#: this fetches from state different ones: archive.org publishes a sha1 per item
#: and GitHub publishes a sha256 per release asset.
Expecting = collections.namedtuple("Expecting", "name size digest algorithm")


def allowed(url, hosts):
    """Whether one address may be asked.

    @param url - What to check, which is either one of ours, a redirect a fetch
      was handed, or an address that arrived inside somebody else's answer.
    @param hosts - Host names. Each matches itself and anything under it, so
      "archive.org" also allows "ia801604.us.archive.org".
    @returns bool

    Checked on the parsed host rather than on the string. A string test passes
    `https://archive.org.example.com/` and a parsed one does not.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        return False
    host = parsed.hostname or ""
    return any(host == name or host.endswith("." + name) for name in hosts)


class OnlyThese(urllib.request.HTTPRedirectHandler):
    """Refuses a redirect that leads off the hosts a fetch may reach.

    @param hosts - The host names, as `allowed` takes them.
    """

    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, request, fp, code, message, headers, newurl):
        if not allowed(newurl, self.hosts):
            raise urllib.error.HTTPError(
                newurl, code, "redirected somewhere this may not go", headers,
                fp)
        return super().redirect_request(request, fp, code, message, headers,
                                        newurl)


def opened(url, hosts, timeout, headers=None):
    """Asks for one address, refusing it and every redirect off these hosts.

    @param url - Where to ask.
    @param hosts - Which hosts this may reach, as `allowed` takes them.
    @param timeout - Seconds to wait.
    @param headers - What to send beside the request, or None.
    @returns The answer, as an open file the caller reads and closes.
    @raises urllib.error.URLError where the address is not one this may ask, and
      whatever urllib raises for everything else.

    The first address is checked as well as the redirects. Both callers now pass
    one they were handed rather than one they wrote: a download address comes out
    of the release GitHub describes, and whoever controls that answer would
    otherwise control where this goes.
    """
    if not allowed(url, hosts):
        raise urllib.error.URLError("not an address this may ask")
    request = urllib.request.Request(url, headers=headers or {})
    return urllib.request.build_opener(OnlyThese(hosts)).open(request,
                                                              timeout=timeout)
