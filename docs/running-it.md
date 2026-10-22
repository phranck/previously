# Running it

Everything the README leaves out: how a machine is set up, how to check the result, and how to get back into one whose screen now belongs to a NeXT.

## Setting a machine up

One line, on the Pi, over SSH:

```bash
curl -fsSL https://previous.li/install.sh | bash
```

It installs the admin tool as a Debian package and hands the rest to the tool's helper, which runs the same job the Installer window runs from a browser. The helper installs `cage`, `7zip`, `xdotool` and `imagemagick`, adds the signed [Window Maker Live archive](https://wmlive.rumbero.org/repo/) pinned to Previous alone, and installs Previous from it. A network that cannot reach the archive gets the same packages from its copy at `https://previous.li/apt/wmlive/`, which the archive's signature covers as well. The helper then fetches NeXTSTEP 3.3, writes `~/.config/previous/previous.cfg`, logs the first console in, silences the startup and has that console start Previous. Last, it sends the sound to a speaker and starts the machine. The script shows each step as it happens, and at the end NeXTSTEP is on the Pi's screen. It then says where the admin answers, which is `http://<hostname>.local:8810`. Open it and choose a password.

Run it as the user the machine will belong to, not under `sudo`. It raises its own privileges where it needs them, asking for your password once, before it prints anything else. The pipe does not get in the way of that, because `sudo` reads the password from the terminal device rather than from stdin.

Every step exists once, in `admin/previously/setup.py`, one function each, and that file is what to read to do any of them by hand.

Running it a second time changes nothing that is already in place. A step that finds its work done skips itself and says so: a system already on the card is not fetched again, and an existing configuration is left exactly as it is.

## The Installer window

**It changes the machine afterwards.** The emulator can be updated or removed, a system can be fetched or taken off the card, and a disk can be copied and the copy put back. On a Pi that has the admin tool and nothing else, it runs the whole job itself, with NeXTSTEP 3.3 unless another of the six is chosen.

It says what each system costs to fetch and what would be left on the card before it starts, and it refuses a system the card has no room for before anything is installed, saying what is needed and what is free. On an 8 GB card the first attempt asks for a restart instead: the Pi keeps a swap file of up to 2 GB on the card, the tool switches swap to memory alone, and the file goes when the Pi starts again. While it runs it says which step it is on and how far through.

**Nothing in the browser holds any privilege.** The tool writes a small file into its own runtime directory, and a systemd path unit starts a program that runs as root and reads it. That file carries four names: a job, a system, a machine and, for putting a copy back, the name of that copy. Three of the four are looked up in tables that ship with the package and the fourth is matched against the listing of one folder, so nothing that arrives from a browser is ever a path, a URL or a command. `admin/previously/setup.py` is the whole of what root does, and it is one file.

## When it stops half way

A step that fails puts back what it changed, and the steps before it as well, in reverse order. The script says which step stopped it and what was put back, and the Installer window says the same and can try again.

Ctrl+C while the admin tool is being installed takes the tool off again. Once the helper has the job, the Pi carries on by itself. Ctrl+C then stops the script from watching and nothing else, and the Installer window shows how far it is.

Only this run's own changes are reversed. A package that was already installed stays, an existing configuration is not touched, and exactly the fenced block is removed from `~/.profile` rather than the file. A step that skipped itself records nothing, so it can never take away what it found in place.

The refreshed package lists are the one thing left behind. They are more current than before and harm nothing.

## Running it off the network

The script reads no file beside itself, so a single copy at a URL is the whole deployment. Two properties make that safe:

- All the work sits in functions, and nothing executes until `main` is called on the last line. A download cut short runs nothing at all rather than half of it.
- Nothing in it reads from stdin, which is where the script itself arrives when piped in. A program that did would swallow the rest of the script. `DEBIAN_FRONTEND=noninteractive` is set for that reason, because a package asking a configuration question would reach for stdin.

Anyone who wants to read it first can read [the one file on GitHub](https://github.com/phranck/previously/blob/main/install.sh). Pages serves it as `application/x-sh`, so a browser sent to that address saves it rather than showing it.

## Checking the result

The installation ends with the machine starting on the Pi's screen. The gray NeXT screen appears, followed within half a minute by the NeXTSTEP login panel. Log in as `me`, no password. A second account, `root`, has none either.

Over SSH there is no screen to draw on, but the disk can still be checked:

```bash
ditool -im ~/nextstep/nextstep-3.3.dd -lsp
ditool -im ~/nextstep/nextstep-3.3.dd -p a -ls
```

Names like `NextLibrary` and `NextApps` in the listing mean the image and its path are right. To start it on the Pi's own screen from an SSH session:

```bash
sudo systemctl restart getty@tty1
```

## Using your own disk image

Put it into `~/nextstep` as `nextstep-3.3.dd` before running the script. It finds it, skips the download, and writes the configuration against your image. Every system is looked for under its own name the same way, such as `openstep-4.2.dd`, and an image under any other name is not one the script knows to use.

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

## Updating the admin tool

**From the browser.** Open the Raspberry Pi window. The line marked Previously is the version that is answering, the one under it is the newest that has been published, and where the second is newer than the first that field is tinted and an Update button stands beside Restart. Pressing it is the whole of it.

Opening the window is what asks GitHub, at most three times a minute. So a release published while you are looking at the window turns up when you close it and open it again, and leaving the window open does not spend the sixty requests an hour an address is allowed.

**Release Notes**, beside that line, opens the published release's own notes in Preview, in the language set in Preferences. It is there whenever there is a release to read about, whether it is newer than the one you are running or not.

The window then says which step it is on and how much of the package has come down. Half way through, the tool is stopped and the new one started, so for a few seconds there is nothing for the page to talk to; it says so rather than going blank, and when the new tool answers it says which version is now talking to it. Nothing needs reloading and nothing needs stopping, and NeXTSTEP keeps running throughout.

An update that fails leaves the tool that is here running, and the window says which step stopped it and why. A board that cannot reach GitHub offers no update and says that it does not know what is published.

**From a shell**, which is what a machine with no admin tool on it needs:

```bash
curl -fsSL https://previous.li/install.sh | bash -s -- --update-admin
```

From a checkout on the Pi, the same script builds the package out of what is beside it:

```bash
./install.sh --update-admin
```

However the tool is replaced, from the window or from a shell, the console that starts the emulator and the source Previous comes from are brought up to the new version as well, where the machine has them.

The password in `/var/lib/previously/password` and the configuration in `/etc/previously/config.ini` both survive either way, because the password is state the tool wrote itself and the configuration is a conffile that an upgrade never overwrites. `dpkg-query -W previously` says on the Pi itself what the window says in the browser.

**The browser shows the release, and the Pi knows which build it is.** In the window a version reads as `1.0.0`. The package itself carries more: anything built between two releases says how far it stands from the last tag and which commit it came from, so `1.0.0+7.g2f250d5` is seven commits past the release and `1.0.0~7.g2f250d5` is seven commits on the way to one that has not been tagged yet, and a build from a tree with something uncommitted in it ends in `.modified`. Every one of those sorts the way apt expects, so an upgrade is an upgrade in either direction. `dpkg-query -W previously` is where you read it when you need it.

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

The page at [previous.li](https://previous.li/) is its own repository, [phranck/previous.li](https://github.com/phranck/previous.li), and its README says how it is made and where its pictures come from.

`install.sh` is the one thing the two share, and its source is here. That repository fetches it and serves it, so the line at the top of this documentation reaches the same script that sits beside the tool it installs. Editing the copy over there would put a second version of it in the world, and the one people run would be the one that drifted.
