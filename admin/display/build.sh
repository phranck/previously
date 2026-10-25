#!/bin/sh
# Builds pixel-exact.so in Debian trixie, the system the Pi runs, so it links
# against the same SDL3 as the Previous it is loaded into. In a container of
# the host's own processor: on an arm64 Mac or an arm64 runner that is the
# Pi's, and anywhere else it is a build that only shows the source compiles,
# which packaging/build.py refuses to package.
#
#     display/build.sh
#
# The library is left beside its source, where packaging/build.py takes it.
set -eu

display="$(cd "$(dirname "$0")" && pwd)"

docker run --rm -e DEBIAN_FRONTEND=noninteractive -v "$display:/display" debian:trixie sh -ec '
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends \
        gcc make pkg-config libc6-dev libsdl3-dev > /dev/null
    make -C /display clean pixel-exact.so
'
