#!/bin/sh
# Copies a renewed certificate to where the service can read it.
#
# Run by the ACME client after every successful renewal, which is roughly every
# sixty days and never at a time anybody is watching. It has to work unattended
# or the site goes dark with an expired certificate.
#
# certbot:
#   certbot renew --deploy-hook /usr/lib/previously/certificate-hook.sh
# acme.sh:
#   acme.sh --install-cert -d <name> --reloadcmd /usr/lib/previously/certificate-hook.sh
#
# Why copy at all, rather than pointing the service at /etc/letsencrypt/live:
# the key there is readable by root alone, and this service is not root. It
# also sets ProtectSystem=strict, so reaching outside its own directories is
# not something to arrange around.

set -eu

SERVICE_USER="next"
TARGET="/etc/previously/tls"
UNIT="previously.service"

# certbot sets this; acme.sh does not, so it can be given as the first argument.
LINEAGE="${RENEWED_LINEAGE:-${1:-}}"

if [ -z "$LINEAGE" ]; then
    echo "no certificate directory given: set RENEWED_LINEAGE or pass it as an argument" >&2
    exit 1
fi

if [ ! -r "$LINEAGE/fullchain.pem" ] || [ ! -r "$LINEAGE/privkey.pem" ]; then
    echo "$LINEAGE holds no fullchain.pem and privkey.pem" >&2
    exit 1
fi

mkdir -p "$TARGET"

# install sets the mode as it writes, so the key is never on disk readable by
# everybody, not even for the moment between being written and being chmod-ed.
# Same reasoning as the token, and the same consequence if it is skipped.
install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0644 \
    "$LINEAGE/fullchain.pem" "$TARGET/fullchain.pem"
install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0640 \
    "$LINEAGE/privkey.pem" "$TARGET/privkey.pem"

# A restart rather than a reload, because the certificate is read once when the
# listening socket is wrapped and there is nothing in the service that would
# pick up a new one. It is down for a moment, at an hour nobody is looking.
if systemctl is-enabled --quiet "$UNIT" 2>/dev/null; then
    systemctl restart "$UNIT"
    echo "certificate installed and $UNIT restarted"
else
    echo "certificate installed; $UNIT is not enabled, so nothing was restarted"
fi
