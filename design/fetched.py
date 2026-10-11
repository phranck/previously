"""Fetching a file that is shipped, and holding it to the sum it was read at.

A file arriving over the network comes from a machine nobody here owns, so
what is written into this repository is only ever the file that was read and
measured when its script was written. Both fonts.py and raspberrypi.py fetch
that way, and this is the one place it is done.
"""

import hashlib
import urllib.request


def download(url, expected, headers=None):
    """Downloads one file and checks it.

    @param url - Where it is.
    @param expected - Its SHA-256, as hex.
    @param headers - What to send beside the request, where the host wants
      something, such as a User-Agent.
    @returns bytes of the file.
    @raises SystemExit where what arrived is not what was measured.
    """
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request) as answer:
        body = answer.read()
    checked(url, body, expected)
    return body


def checked(name, body, expected):
    """Holds one file to its sum.

    @param name - What to call it in the complaint.
    @param body - bytes of the file.
    @param expected - Its SHA-256, as hex.
    @raises SystemExit where the two differ.
    """
    got = hashlib.sha256(body).hexdigest()
    if got != expected:
        raise SystemExit("%s is not the file this was written against:\n"
                         "  expected %s\n  got      %s" % (name, expected, got))
