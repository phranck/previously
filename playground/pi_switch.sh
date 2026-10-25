#!/bin/sh
# Switches next5 between its own console and the playground console, which
# runs the playground build of Previous at 1024 by 600 from /tmp/playground.
#
#     pi_switch.sh check | prepare | on | off | restore | status
#
# prepare puts the binary from pi_build.sh and what runs it into
# /tmp/playground on next5, which is a tmpfs, so a reboot takes it away: the
# console script, a home whose previous.cfg names the playground's disk copy
# and grab folder, and a link to the package's ROMs where the binary looks for
# its data. It changes nothing on the screen.
#
# Both directions go through the admin's own kiosk module, so the guest is
# shut down properly before the console changes hands: stop() presses the
# power key and holds the emulator down, start() lifts the hold. In between,
# a systemd drop-in swaps the console's ExecStart, which is the one root step,
# done with the sudo password that ~/.secrets exports as SUDO_NEXT. The value
# goes to sudo on its standard input and nowhere else.
set -eu

host="next@next5.local"
# The drop-in lives in /run, a tmpfs like /tmp/playground, so a reboot takes
# both away together and next5 comes back on its own console. One in /etc
# would outlive the playground and leave the console starting a script that is
# gone, which restore clears as well.
drop_in_dir="/run/systemd/system/previously-console.service.d"
drop_in="$drop_in_dir/playground.conf"
lasting_drop_in="/etc/systemd/system/previously-console.service.d/playground.conf"
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
    check)
        # The one root step must work before on stops the guest, or the
        # emulator stays held down with nothing to replace it.
        as_root "true" && echo "sudo works on $host"
        ;;
    restore)
        # next5's own console back without touching the guest, for when the
        # playground is gone and the console cannot start.
        as_root "rm -f $drop_in $lasting_drop_in && rmdir $drop_in_dir $(dirname $lasting_drop_in) 2>/dev/null; systemctl daemon-reload && systemctl restart previously-console"
        ssh "$host" "systemctl is-active previously-console; if [ -e $drop_in ] || [ -e $lasting_drop_in ]; then echo 'a playground drop-in is still there'; else echo 'no playground drop-in'; fi"
        ;;
    prepare)
        ssh "$host" "mkdir -p /tmp/playground/bin /tmp/playground/share /tmp/playground/home/.config/previous /tmp/playground/grabs && ln -sfn /usr/share/previous /tmp/playground/share/previous"
        scp "$HOME/.cache/previously-playground/pi-build/Previous" "$host:/tmp/playground/bin/previous"
        ssh "$host" "sed -e 's|^szImageName0 = .*|szImageName0 = /home/next/nextstep/nextstep-3.3-playground.dd|' -e 's|^szPrintToFileName = .*|szPrintToFileName = /tmp/playground/grabs|' $own_config > $test_config"
        ssh "$host" "cat > /tmp/playground/console-test" <<'CONSOLE'
#!/bin/sh
# The console of previously-console, with the playground build, its own home
# and the panel's size. It waits on the same hold, so the admin's kiosk module
# stops and starts it like the real one.
while [ -f /run/previously/hold ]; do sleep 2; done
cd /tmp/playground/grabs
HOME=/tmp/playground/home PREVIOUS_SCREEN_W=1024 PREVIOUS_SCREEN_H=600 \
SDL_VIDEO_DRIVER=x11,wayland XCURSOR_PATH=/usr/share/previously/cursors \
cage -- /tmp/playground/bin/previous
status=$?
[ "$status" -eq 0 ] || sleep 2
exit "$status"
CONSOLE
        ssh "$host" "chmod +x /tmp/playground/console-test /tmp/playground/bin/previous && grep -E '^(szImageName0|szPrintToFileName)' $test_config && ls -la /tmp/playground/bin /tmp/playground/share/previous/"
        ;;
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
