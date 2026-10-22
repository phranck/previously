# Measuring a boot

How long a Pi takes from the kernel's start to a finished NeXTSTEP Workspace, and how much of a core the emulator and everything around it use on the way and afterwards. Every change to the Linux underneath Previous is measured this way, before and after, on a Pi 4 and a Pi 5.

## Running it

On the Mac, from `admin/`, with Pillow installed as the [admin README](../admin/README.md) says:

```bash
python3 measuring/boot.py next@next5.local --into /tmp/pi5-cube --title "Pi 5, NeXTcube Turbo"
python3 measuring/boot.py next@next5.local --into /tmp/pi5-nd --machine nextcube-turbo-dimension --title "Pi 5, NeXTcube Turbo with NeXTdimension"
```

Each call restarts the Pi three times and prints one report in Markdown. `--runs` changes how many starts, and `--seconds` how long each capture runs after the emulator has started, which is 240 by default. `--machine` names a machine from the admin's catalogue. The emulator becomes that machine for the runs and gets its own configuration back afterwards. `--report` reads a directory an earlier call filled and measures nothing.

Nothing on the Pi needs sudo. The tool copies its capture into `~/.cache/previously-measure`, installs the user unit `previously-measure.service`, and restarts the board the way the admin's Restart button does. When it is done, it removes the unit and the directory again.

## What happens on the Pi

The unit starts with the first login of the emulator's user, which is the console that starts Previous. From the moment Previous runs, the capture keeps three readings every second:

- a grab of the emulated screen, which Previous writes itself at the machine's own resolution,
- the time each of Previous's threads has spent on a core, and
- the same for every process on the board.

Previous encodes each grab itself, so the capture costs its main thread a little. The cost is the same in every measurement and leaves comparisons between them intact.

## The figures

All times count from the kernel's start, because that is where the board's clock starts. The firmware runs before that and no figure here includes it.

| Figure | Where it comes from |
|---|---|
| Kernel, Userspace | `systemd-analyze` |
| multi-user.target | `systemd-analyze`, added to the kernel's time |
| Previous starts | the start time `/proc` keeps for the emulator's process |
| First picture | the first grab that is not one flat color |
| Screen settled | the first grab from which every later one matches the last, apart from the clock in the dock |
| NeXTSTEP boot | from Previous's start to the settled screen |

With NeXTSTEP 3.3 the settled screen is the Workspace, because that system logs `me` in by itself. It is exact to the second, which is how often the screen is grabbed. The clock in the dock changes 13 to 17 pixels a minute, and `CLOCK_PIXELS` in `boot.py` lets up to 100 pass.

The load tables give percent of one core. A figure over 100 is a name with several threads busy at once. "While booting" runs from Previous's start to the settled screen, and "Idle" from ten seconds after that to the end of the capture. The process table lists the eight that are busiest while idle. `python3` there is the admin service, because the capture leaves itself out.

Whether the picture or the sound stutters is not something the capture can see. A person at the Pi watches and listens while NeXTSTEP boots and for a minute at the Workspace, and the report notes what they found.
