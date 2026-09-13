#!/bin/sh
# Makes a certificate this machine signs for itself, for every name it answers to.
#
#   sudo /usr/lib/previously/self-signed-certificate.sh
#   sudo /usr/lib/previously/self-signed-certificate.sh pi.fritz.box 192.168.1.50
#
# For the ordinary case: a Pi on a home network, with whatever name its owner
# gave it and no domain anybody else can look up. No public authority issues a
# certificate for such a name, because there is nothing for them to verify, so
# this is the only certificate such a machine can have.
#
# It encrypts the connection, which is what keeps the token off the wire. It
# proves nothing about who is answering, so the browser warns once and the
# person who typed the address decides. That is the whole of the trade.
#
# Nothing here is written down in advance. Every name comes from what the
# machine reports about itself, so this works on a Pi called anything at all.
# Names and addresses given as arguments are added to those.

set -eu

SERVICE_USER="${SERVICE_USER:-next}"
TARGET="${TARGET:-/etc/previously/tls}"
UNIT="previously.service"

# 825 days. Apple enforces that as a hard ceiling on macOS and iOS for every
# server certificate, whoever issued it, so a longer one is refused outright
# rather than merely warned about.
DAYS=825

if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl is needed and is not installed" >&2
    exit 1
fi

# Said here rather than left to fail halfway through, where the message would
# be about whichever step got there first.
if [ "$(id -u)" -ne 0 ]; then
    echo "this writes to $TARGET and restarts $UNIT, so run it with sudo" >&2
    exit 1
fi

# -- every name this machine answers to ----------------------------------

short_name="$(hostname)"

collect_names() {
    # The short name, and the same name under .local, which is what multicast
    # DNS answers and therefore what most people type.
    echo "$short_name"
    echo "$short_name.local"

    # What the resolver makes of it, which on a network whose router serves a
    # domain is something like cube.fritz.box. Both of these repeat themselves
    # and each other, so the whole list is deduplicated below.
    hostname -f 2>/dev/null || true
    hostname -A 2>/dev/null | tr ' ' '\n' || true

    # Anything the caller added.
    for extra in "$@"; do
        echo "$extra"
    done
}

collect_addresses() {
    hostname -I 2>/dev/null | tr ' ' '\n' || true
}

# -- sort them into what openssl wants -----------------------------------

subject_alternative_names=""

add_entry() {
    entry="$1"
    [ -n "$entry" ] || return 0

    case "$entry" in
        # An IPv6 address is the only thing here that contains a colon, and an
        # IPv4 one is digits and dots with nothing else in it.
        *:*) kind="IP" ;;
        *[!0-9.]*) kind="DNS" ;;
        *) kind="IP" ;;
    esac

    candidate="$kind:$entry"
    case ",$subject_alternative_names," in
        *",$candidate,"*) return 0 ;;
    esac

    if [ -z "$subject_alternative_names" ]; then
        subject_alternative_names="$candidate"
    else
        subject_alternative_names="$subject_alternative_names,$candidate"
    fi
}

for name in $(collect_names "$@"); do
    add_entry "$name"
done
for address in $(collect_addresses); do
    add_entry "$address"
done

if [ -z "$subject_alternative_names" ]; then
    echo "this machine reports no name and no address to make a certificate for" >&2
    exit 1
fi

# -- make it ------------------------------------------------------------

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Elliptic curve rather than RSA, because generating one is instant on a Pi and
# every browser has accepted P-256 for a decade.
openssl req -x509 -nodes -days "$DAYS" \
    -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
    -keyout "$work/privkey.pem" -out "$work/fullchain.pem" \
    -subj "/CN=$short_name" \
    -addext "subjectAltName=$subject_alternative_names" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" \
    2>/dev/null

mkdir -p "$TARGET"

# install sets the mode as it writes, so the key is never on disk readable by
# everybody, not even for the moment between being written and being chmod-ed.
install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0644 \
    "$work/fullchain.pem" "$TARGET/fullchain.pem"
install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0640 \
    "$work/privkey.pem" "$TARGET/privkey.pem"

echo "certificate written to $TARGET, good for $DAYS days, covering:"
echo "$subject_alternative_names" | tr ',' '\n' | sed 's/^/  /'
echo
echo "now name it in /etc/previously/config.ini:"
echo "  certificate = $TARGET/fullchain.pem"
echo "  private_key = $TARGET/privkey.pem"

if systemctl is-enabled --quiet "$UNIT" 2>/dev/null; then
    systemctl restart "$UNIT"
    echo
    echo "$UNIT restarted"
fi
