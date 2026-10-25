#!/bin/sh
# Switches next5 between its own console and the playground console, which
# runs the playground build of Previous at 1024 by 600 from /tmp/playground.
#
#     pi_switch.sh on | off | status
#
# Both directions go through the admin's own kiosk module, so the guest is
# shut down properly before the console changes hands: stop() presses the
# power key and holds the emulator down, start() lifts the hold. In between,
# a systemd drop-in swaps the console's ExecStart, which is the one root step,
# done with the sudo password that ~/.secrets exports as SUDO_NEXT. The value
# goes to sudo on its standard input and nowhere else.
set -eu

host="next@next5.local"
drop_in_dir="/etc/systemd/system/previously-console.service.d"
drop_in="$drop_in_dir/playground.conf"
own_config="/home/next/.config/previous/previous.cfg"
test_config="/tmp/playground/home/.config/previous/previous.cfg"

sudo_password() {
    sed -n -e 's/^export SUDO_NEXT=//p' -e 's/^SUDO_NEXT=//p' "$HOME/.secrets" | head -1 | tr -d '"'"'"
}

as_root() {
    sudo_password | ssh "$host" "sudo -S -p '' sh -c '$1'"
}

kiosk_stop() {
    ssh "$host" "PYTHONPATH=/usr/lib/previously python3 -c 'import pathlib; from previously import kiosk; print(kiosk.stop(pathlib.Path(\"/run/previously\"), previous_config=pathlib.Path(\"$1\")))'"
}

kiosk_start() {
    ssh "$host" "PYTHONPATH=/usr/lib/previously python3 -c 'import pathlib; from previously import kiosk; print(kiosk.start(pathlib.Path(\"/run/previously\")))'"
}

case "${1:-status}" in
    on)
        kiosk_stop "$own_config"
        # The guest is down and its disk is clean at this moment, so the test
        # boots a clean copy and the Mac gets the same copy as its new master.
        ssh "$host" "cp /home/next/nextstep/nextstep-3.3.dd /home/next/nextstep/nextstep-3.3-playground.dd && echo 'clean copy made'"
        as_root "mkdir -p $drop_in_dir && printf \"[Service]\\nExecStart=\\nExecStart=/tmp/playground/console-test\\n\" > $drop_in && systemctl daemon-reload && systemctl restart previously-console"
        kiosk_start
        ;;
    off)
        kiosk_stop "$test_config"
        as_root "rm -f $drop_in && rmdir $drop_in_dir 2>/dev/null; systemctl daemon-reload && systemctl restart previously-console"
        kiosk_start
        ;;
    status)
        ssh "$host" "systemctl is-active previously-console; ls $drop_in 2>/dev/null || echo 'no drop-in'; pgrep -a -x previous || echo 'no emulator'; ls /run/previously/hold 2>/dev/null || echo 'no hold'; ls /tmp/playground/grabs 2>/dev/null | tail -2"
        ;;
    *)
        echo "usage: pi_switch.sh on | off | status" >&2
        exit 2
        ;;
esac
