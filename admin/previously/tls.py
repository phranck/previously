"""Serving over HTTPS.

This module knows about a certificate and a key on disk and nothing else. It
does not speak to a certificate authority, does not renew anything and has no
idea who issued what it loads. Getting a certificate is the operator's job and
differs with every DNS provider; using one is the same everywhere.

Where no certificate is configured the service speaks plain HTTP, which is what
a fresh installation does. That is not a security decision left half made: a Pi
on a home network with no name of its own cannot have a certificate at all, and
refusing to start would leave such a machine with no admin tool rather than with
an unencrypted one.
"""

import ssl


class NotUsable(Exception):
    """A certificate was configured and cannot be used.

    Separate from "no certificate configured", which is not an error. This one
    stops the service, because the alternative is serving in the clear on a port
    somebody believes is encrypted.
    """


def context(certificate, private_key):
    """Builds the context the listening socket is wrapped in.

    @param certificate - Path to the certificate chain, or None. For a
      Let's Encrypt certificate this is fullchain.pem, which carries the
      intermediate the browser needs; cert.pem alone leaves clients to find it.
    @param private_key - Path to the matching private key, or None.
    @returns ssl.SSLContext, or None where neither is configured, in which case
      the service speaks plain HTTP.
    @raises NotUsable where one of the two is configured without the other, or
      where the pair cannot be loaded.

    Naming one without the other is refused rather than ignored, because both
    ways of ignoring it are wrong: dropping to HTTP hides the mistake behind a
    working service, and guessing the second path from the first invents a fact.
    """
    if certificate is None and private_key is None:
        return None
    if certificate is None or private_key is None:
        raise NotUsable(
            "a certificate needs both 'certificate' and 'private_key'; "
            "only %s is configured"
            % ("certificate" if certificate else "private_key")
        )

    answer = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # Stated rather than left to the default, so the floor is visible to whoever
    # reads this file and does not move underneath us with a Python upgrade.
    answer.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        answer.load_cert_chain(certfile=str(certificate), keyfile=str(private_key))
    except (OSError, ssl.SSLError) as error:
        raise NotUsable("cannot load %s with %s: %s"
                        % (certificate, private_key, error)) from error
    return answer
