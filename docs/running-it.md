# Running it

Everything the README leaves out: what the install script does step by step, how to check the result, and how to get back into a machine whose screen now belongs to a NeXT.

## What the script does

It installs `cage` and `7zip`, adds the signed [Window Maker Live archive](https://wmlive.rumbero.org/repo/) pinned to Previous alone, installs Previous from it, fetches a preinstalled NeXTSTEP 3.3 disk image, writes `~/.config/previous/previous.cfg`, installs the admin tool as a Debian package, enables console autologin, silences the boot and hands the first console to Previous.

Run it as the user the machine will belong to, not under `sudo`. It writes the configuration and the startup line into your home directory and raises its own privileges where it needs them, asking for your password once. The pipe does not get in the way of that, because `sudo` reads the password from the terminal device rather than from stdin.

Running it a second time changes nothing that is already in place. An existing disk image, an existing configuration file and an autostart entry that is already there are all left alone.

## Interrupting it

Ctrl+C leaves the machine as it was. Every step records how to undo exactly what it changed, and an interrupt walks that record backwards. A failing step does the same, because a half-configured system is no better than an interrupted one.

Only this run's own changes are reversed. Your own disk image in `~/nextstep` stays, a package that was already installed stays, an existing configuration is not touched, and exactly the fenced block is removed from `~/.profile` rather than the file. A step that skipped itself records nothing, so it can never take away what it found in place.

The refreshed package lists are the one thing left behind. They are more current than before and harm nothing.

## Running it off the network

The script reads no file beside itself, so a single copy at a URL is the whole deployment. Two properties make that safe:

- All the work sits in functions, and nothing executes until `main` is called on the last line. A download cut short runs nothing at all rather than half of it.
- Nothing in it reads from stdin, which is where the script itself arrives when piped in. A program that did would swallow the rest of the script. `DEBIAN_FRONTEND=noninteractive` is set for that reason, because a package asking a configuration question would reach for stdin.

Anyone who wants to read it first can read [the one file on GitHub](https://github.com/phranck/previously/blob/main/install.sh). Pages serves it as `application/x-sh`, so a browser sent to that address saves it rather than showing it.

## Checking the result

Before rebooting into the kiosk, at the Pi's own keyboard on the text console:

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

## Using your own disk image

Put it into `~/nextstep` before running the script. It finds it, skips the download, and writes the configuration against your image.

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

The package owns `/usr/bin` and `/usr/share/previous`. The disk image and the configuration belong to you and are never touched by a package operation. What does cause damage is quitting Previous whilst NeXTSTEP is still running, and that damage shows up after the update rather than before it.

## Updating the admin tool

Nothing needs stopping, and NeXTSTEP keeps running throughout:

```bash
curl -fsSL https://previous.li/install.sh | bash -s -- --update-admin
```

From a checkout on the Pi, the same script builds the package out of what is beside it:

```bash
./install.sh --update-admin
```

The token in `/var/lib/previously/token` and the configuration in `/etc/previously/config.ini` both survive, because the token is state the tool wrote itself and the configuration is a conffile that an upgrade never overwrites. The service is restarted by the package, so the browser has the new tool on its next load.

The version it put there is in the Raspberry Pi window, on the line marked Previously, which is also how to tell a machine that is up to date from one that was left behind.

**A machine installed before the port moved keeps answering on 2342.** That configuration is a conffile, so no upgrade touches it:

```bash
sudo sed -i 's/^port = 2342/port = 8810/' /etc/previously/config.ini
sudo systemctl restart previously
```

## Getting back in

The first console belongs to Previous once the kiosk is active. SSH sessions carry no `XDG_VTNR`, so they fall through the autostart and remain the way to change anything on the system. Make sure SSH works before handing the screen over: from the boot-silencing step onwards the screen shows no error messages either, and `journalctl -b -e` over the network is then the only way to find out why something did not start.

Inside Previous, F12 opens the settings and F11 leaves full screen.

Shut NeXTSTEP down from within NeXTSTEP, never by pulling power. Its file system takes damage when the machine disappears mid-write. If the machine is meant to be switched off at the wall, set `nWriteProtection = 1` in `[HardDisk]`: writes then go to memory instead of the image, and nothing survives a restart, which is the point.

## The website

`index.html` and everything under `site/` are the page at [previous.li](https://previous.li/). It does not reproduce NeXTSTEP, because the admin tool already does that, and the top of `site/site.css` says which three things on it are allusions to the original.

The page is dark and only dark, it sets no cookie of its own, and the one thing it fetches from elsewhere is [Umami](https://umami.layered.work/) on our own server, which stores nothing that identifies a reader.

- The interface icons are [Phosphor](https://phosphoricons.com/) in its duotone weight, under MIT, and the GitHub mark is [Simple Icons](https://simpleicons.org/), under CC0 1.0. `site/icons.py` fetches both at a pinned version and writes `site/icons.svg`. Add a glyph there and run it rather than editing that file.
- The face is [Inter](https://rsms.me/inter/), under the SIL Open Font License, whose text sits beside the font in `site/fonts/`.
- `site/shots/og.png` is what a link to the page unfolds into elsewhere. It is a screenshot of `site/og.html` at exactly 1200 by 630, so it is set in the same face and the same colours as the site rather than drawn by hand.
- `site/shots/workspace.png` is a screenshot of the admin tool running on a Pi, taken at twice the size it is shown at so a Retina display gets one picture pixel per device pixel.
