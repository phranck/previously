#!/bin/sh
# Builds the playground Previous for the Pi in a throwaway Debian trixie
# container for arm64, so it links against the SDL and libpng the Pi runs,
# and leaves the binary as ~/.cache/previously-playground/pi-build/Previous.
#
#     pi_build.sh
#
# The source is the svn working copy beside the other playground state,
# mounted read-only; the build happens inside the container and is gone with
# it. built-against.txt records the two library versions, to compare with
# `dpkg -l libsdl3-0 libpng16-16t64` on the Pi.
set -eu

playground="$HOME/.cache/previously-playground"
out="$playground/pi-build"
mkdir -p "$out"

docker run --rm --platform linux/arm64 \
    -v "$playground/previous-trunk:/src:ro" -v "$out:/out" \
    debian:trixie sh -ec '
        apt-get update > /out/apt.log 2>&1
        apt-get install -y --no-install-recommends cmake ninja-build gcc g++ libsdl3-dev libpng-dev zlib1g-dev >> /out/apt.log 2>&1
        dpkg-query -W libsdl3-dev libpng-dev > /out/built-against.txt
        cmake -S /src -B /tmp/b -G Ninja -DCMAKE_BUILD_TYPE=Release > /out/cmake.log 2>&1
        ninja -C /tmp/b > /out/ninja.log 2>&1
        cp /tmp/b/src/previous /out/Previous
    '
ls -la "$out/Previous"
cat "$out/built-against.txt"
