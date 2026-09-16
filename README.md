# NeXTSTEP RPi

Turns a freshly imaged Raspberry Pi 5 into a machine that boots straight into NeXTSTEP under the [Previous](https://previous.nextcommunity.net/) emulator. No desktop, no compiler, no window furniture: the screen shows the NeXT login panel and nothing else.

What configures it afterwards is a web admin built in NeXTSTEP's own idiom, which the same script installs. The line to install all of it is on [previously.layered.work](https://previously.layered.work/).

## Requirements

Raspberry Pi OS Lite, 64 bit, based on Debian 13 (trixie). The script refuses to run anywhere else, because the Previous package needs SDL3 and no earlier release carries it.

## Use

On the Pi, as the user the machine will belong to. An SSH session is the comfortable way to do this.

```bash
curl -fsSL https://previously.layered.work/install.sh | bash
```

Not under `sudo`: it writes the configuration and the startup line into your home directory, and it raises its own privileges where it needs them, asking for your password once. The pipe does not get in the way of that, because `sudo` reads the password from the terminal device rather than from stdin.

It installs `cage` and `7zip`, adds the signed [Window Maker Live archive](https://wmlive.rumbero.org/repo/) pinned to Previous alone, installs Previous from it, fetches a preinstalled NeXTSTEP 3.3 disk image, writes `~/.config/previous/previous.cfg`, installs the admin tool as a Debian package, enables console autologin, silences the boot and hands the first console to Previous.

When it finishes it says where the admin tool is, which is `http://<your-pi>.local:2342`, and how to read the token it asks for once.

Running it a second time changes nothing that is already in place. An existing disk image, an existing configuration file and an autostart entry that is already there are all left alone.

## Interrupting it

Ctrl+C leaves the machine as it was. Every step records how to undo exactly what it changed, and an interrupt walks that record backwards. A failing step does the same, because a half-configured system is no better than an interrupted one.

Only this run's own changes are reversed. Your own disk image in `~/nextstep` stays, a package that was already installed stays, an existing configuration is not touched, and exactly the fenced block is removed from `~/.profile` rather than the file. A step that skipped itself records nothing, so it can never take away what it found in place.

The refreshed package lists are the one thing left behind. They are more current than before and harm nothing.

## Publishing it

The script reads no file beside itself, so a single copy at a URL is the whole deployment. Two properties make it safe to run off the network:

- All the work sits in functions, and nothing executes until `main` is called on the last line. A download cut short runs nothing at all rather than half of it.
- Nothing in it reads from stdin, which is where the script itself arrives when piped in. A program that did would swallow the rest of the script. `DEBIAN_FRONTEND=noninteractive` is set for that reason: a package asking a configuration question would reach for stdin.

Anyone who wants to read it before running it can open the same URL in a browser.

## Checking the result

Before rebooting into the kiosk:

At the Pi's own keyboard, on the text console:

```bash
cage -- previous
```

The grey NeXT screen should appear, followed within half a minute by the NeXTSTEP login panel. Log in as `me`, no password. A second account, `root`, has none either.

Over SSH there is no screen to draw on, but the disk can still be checked:

```bash
ditool -im ~/nextstep/*/NS33_2GB.dd -lsp
ditool -im ~/nextstep/*/NS33_2GB.dd -p a -ls
```

Names like `NextLibrary` and `NextApps` in the listing mean the image and its path are right. To start it on the Pi's own screen from an SSH session:

```bash
sudo systemctl restart getty@tty1
```

## Installing from the original media instead

Put your own disk image into `~/nextstep` before running the script. It finds it, skips the download, and writes the configuration against your image.

## Updating Previous

Shut NeXTSTEP down from within NeXTSTEP first. Then stop the kiosk, because systemd restarts the console after Previous exits and the emulator would be back within seconds, holding the image file open:

```bash
sudo systemctl stop getty@tty1
```

Copy the disk image aside, then:

```bash
sudo apt update
sudo apt install --only-upgrade previous
```

Afterwards `sudo systemctl start getty@tty1` brings the machine back.

The package owns `/usr/bin` and `/usr/share/previous`. The disk image and the configuration belong to you and are never touched by a package operation. What does cause damage is quitting Previous while NeXTSTEP is still running, and that damage shows up after the update rather than before it.

## Getting back in

The first console belongs to Previous once the kiosk is active. SSH sessions carry no `XDG_VTNR`, so they fall through the autostart and remain the way to change anything on the system. Make sure SSH works before handing the screen over: from the boot-silencing step onwards the screen shows no error messages either, and `journalctl -b -e` over the network is then the only way to find out why something did not start.

Inside Previous, F12 opens the settings and F11 leaves full screen.

Shut NeXTSTEP down from within NeXTSTEP, never by pulling power. Its file system takes damage when the machine disappears mid-write. If the machine is meant to be switched off at the wall, set `nWriteProtection = 1` in `[HardDisk]`: writes then go to memory instead of the image, and nothing survives a restart, which is the point.
