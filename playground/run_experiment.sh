#!/bin/sh
# Boots a NeXTSTEP image in the playground build of Previous for a fixed time
# and leaves periodic grabs of the frame buffer behind.
#
#     run_experiment.sh <run> <seconds> [NAME=value ...]
#
# A run is a directory under ~/.cache/previously-playground/runs with its own
# home, so Previous reads that run's previous.cfg and nothing of the Mac's own,
# and a grabs directory that previous.cfg names as the place to print to. The
# environment pairs reach Previous as they are, which is how the playground
# build takes PREVIOUS_SCREEN_W, PREVIOUS_SCREEN_H and PREVIOUS_GRAB_EVERY.
set -eu

playground="$HOME/.cache/previously-playground"
run="$1"
seconds="$2"
shift 2

run_dir="$playground/runs/$run"
[ -d "$run_dir/home" ] || { echo "no run named $run under $playground/runs" >&2; exit 1; }
rm -f "$run_dir/grabs"/next_screen_*.png "$run_dir/grabs"/next_screen_*.tiff

env HOME="$run_dir/home" "$@" "$playground/build/src/Previous.app/Contents/MacOS/Previous" > "$run_dir/previous.log" 2>&1 &
previous_pid=$!
echo "run $run: Previous pid $previous_pid for $seconds s"
sleep "$seconds"
# SIGTERM becomes an SDL quit event, which Previous answers with a dialog
# that waits for a click, so the emulator is ended without asking.
kill -KILL "$previous_pid" 2>/dev/null || true
wait "$previous_pid" 2>/dev/null || true
ls "$run_dir/grabs" | tail -3
