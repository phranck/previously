"""A fetch that may only reach the hosts it was given.

Everything this machine fetches is checked the same way: a prepared system from
archive.org, this tool's own release and package from GitHub, the index of the
archive Previous comes from, and a CD image from the software catalog, whose
address may have been typed in and is therefore also kept out of this network.
The check lives here once, because a copy of it per caller is two rules that
can disagree and the disagreement would be invisible: a fetch that followed a
redirect it should not have still answers with a file.

A redirect is where the check has to be made again. Whoever answers the first
request chooses where the second one goes, so the address of every hop is
checked as the first one was, and an address that arrived in somebody else's
answer is checked before it is asked at all.
"""

import collections
import ipaddress
import socket
import threading
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


def public(url):
    """Whether an address's host is out on the internet rather than in here.

    @param url - What to check.
    @returns bool. False for a host named by an address literal, for one that
      does not resolve, and for one any of whose addresses is loopback,
      private, link-local or otherwise not meant to be reached across the
      internet.

    An address somebody typed into the catalog could otherwise point the Pi at
    the router, at another machine in the house, or at itself. Every address
    the host resolves to counts, because the connection may take any of them.
    """
    host = urllib.parse.urlparse(url).hostname or ""
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    try:
        found = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return False
    addresses = [ipaddress.ip_address(answer[4][0].split("%")[0]) for answer in found]
    return bool(addresses) and all(address.is_global for address in addresses)


class NotAllowed(urllib.error.URLError):
    """An address a fetch refused before asking it."""


class OnlyThese(urllib.request.HTTPRedirectHandler):
    """Refuses a redirect that leads off the hosts a fetch may reach.

    @param hosts - The host names, as `allowed` takes them.
    @param only_public - Whether a redirect must also lead out of this network,
      as `public` decides.
    """

    def __init__(self, hosts, only_public=False):
        self.hosts = hosts
        self.only_public = only_public

    def redirect_request(self, request, fp, code, message, headers, newurl):
        if not allowed(newurl, self.hosts) or (self.only_public and not public(newurl)):
            raise urllib.error.HTTPError(
                newurl, code, "redirected somewhere this may not go", headers,
                fp)
        return super().redirect_request(request, fp, code, message, headers,
                                        newurl)


def opened(url, hosts, timeout, headers=None, only_public=False):
    """Asks for one address, refusing it and every redirect off these hosts.

    @param url - Where to ask.
    @param hosts - Which hosts this may reach, as `allowed` takes them.
    @param timeout - Seconds to wait.
    @param headers - What to send beside the request, or None.
    @param only_public - Whether the address and every redirect must also lead
      out of this network, as `public` decides. Asked for an address somebody
      typed in, which no list of known hosts vouches for.
    @returns The answer, as an open file the caller reads and closes.
    @raises NotAllowed where the address is not one this may ask, and whatever
      urllib raises for everything else.

    The first address is checked as well as the redirects. A download address
    comes out of the release GitHub describes, so it is one this was handed
    rather than one it wrote, and whoever controls that answer would otherwise
    control where this goes.
    """
    if not allowed(url, hosts) or (only_public and not public(url)):
        raise NotAllowed("not an address this may ask")
    request = urllib.request.Request(url, headers=headers or {})
    return urllib.request.build_opener(OnlyThese(hosts, only_public)).open(
        request, timeout=timeout)


def in_the_background(lock, stamp, work, expected):
    """Runs one lookup in a thread, where the lock says none is running.

    @param lock - threading.Lock, the one lookup of that kind at a time.
    @param stamp - Writes down the moment, before the thread starts rather than
      after it finishes, because a floor under how often a host is asked is
      about attempts: a lookup that takes twenty seconds to time out is still a
      lookup that happened.
    @param work - The lookup, which keeps what it learns itself.
    @param expected - The exception class `work` raises where the host could not
      be asked or said something it does not understand.

    That failure is swallowed. What is known stays known, or stays unknown, and
    the reading says so by being absent. Anything else is a fault in this code
    and reaches the log the way any thread's exception does.
    """
    if not lock.acquire(blocking=False):
        return
    stamp()

    def asking():
        try:
            work()
        except expected:
            pass
        finally:
            lock.release()

    threading.Thread(target=asking, daemon=True).start()
