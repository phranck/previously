# The web admin tool

A small service on the Pi that shows what the emulator is set to, from a browser on the home network. It is a more comfortable way to reach what Previous already offers behind F12, and nothing beyond that: no port is forwarded to it and nothing publishes it.

## Running it

```bash
make run          # in the foreground, on port 8810
make check        # lint and tests, which is what a commit needs
```

## What it needs installed

**To run, on the Pi**, five things beyond what Raspberry Pi OS already has. `install.sh` installs four of them, `cage`, `7zip`, `xdotool` and `imagemagick`, and the fifth is Previous itself out of the Window Maker Live archive.

The rest is the system's own and is assumed rather than installed: `systemd` for `systemctl`, `procps` for `pgrep` and `ps`, `raspi-utils-core` for `vcgencmd`, and `python3`. A Pi without `vcgencmd` still runs this; the window shows one reading fewer, because every reading in `pi.py` answers with nothing rather than failing.

What each is for: `cage` is the compositor the emulator runs in, `7zip` unpacks the disk archive, `xdotool` presses the emulator's keys, and ImageMagick's `import` reads its screen, which is the only way to tell a machine that booted from one that did not.

**To work on it**, `flake8` and `pytest` as well. They are not on the Pi and `install.sh` does not put them there, because nothing in running the service needs them.

```bash
sudo apt install python3-pytest python3-flake8       # Debian, the Pi included
brew install flake8 pytest                           # macOS
```

Homebrew's are their own programs rather than modules of the system Python, which the Makefile calls as `$(PYTHON) -m`. So on a Mac it is a virtual environment that works with it:

```bash
python3 -m venv .venv && .venv/bin/pip install flake8 pytest
make check PYTHON=.venv/bin/python
```

Nothing is fetched at runtime. The service itself uses only the standard library, so it starts on a machine with no network and inside a package build.

## What is in here

| | |
|---|---|
| `previously/settings.py` | What the service itself is configured with |
| `previously/config.py` | Reading and writing `previous.cfg` |
| `previously/machines.py` | Which machines exist, and what each one is in the file |
| `previously/files.py` | The places this tool shows, which are not places on any disk |
| `previously/change.py` | Changing the machine without leaving it unable to start |
| `previously/kiosk.py` | Everything this tool does to the machine, in one file |
| `previously/pi.py` | What the board underneath is doing |
| `previously/server.py` | Which addresses exist and what answers them |
| `previously/token.py` | The one secret, and what a request may do without it |
| `web/` | What the browser gets, including one catalogue of words per language |
| `web/vendor/` | The one library this interface takes, with its licence |
| `packaging/` | The unit and the default configuration |

`kiosk.py` is one module because it is the whole surface: reviewing what this tool may do to the machine means reading that one file.

**It needs no privileges at all.** Reading state does not, because `systemctl is-active` answers any user. Switching the emulated machine on and off does not either, because it happens through one file rather than through systemd. The next section says why.

## What anybody on the network can reach

**Reading is open.** Anything on the same network can see which machine is configured, how much memory it has, which disk it boots and whether it is running. That is deliberate: knowing the Pi is set up as a NeXTcube costs nothing.

**Changing anything needs a token.** Writing a configuration, stopping the emulator, opening a shell: all of it is refused without one. Sitting at the machine and pressing F12 needs physical access to it. Being on the network does not, and that difference is what the token answers.

The token is made on first start and lives in `/var/lib/previously/token`, readable by the service alone. Read it once with `sudo cat /var/lib/previously/token` and type it into the panel the interface raises the first time something is refused. The browser keeps it from then on, and the menu has its own way back to it. It is never in this repository, never in a URL and never in a log line.

**It speaks plain HTTP, and there is no TLS.** The token crosses the home network in the open, so somebody already inside that network and reading traffic can take it. That is not the threat the token is for. It is there so that nothing reaches this by accident, and so that a device with no business writing a configuration cannot.

Anybody putting this anywhere less trusted needs more in front of it than a certificate, and that layer terminates TLS itself. A security claim that is not true is worse than none, so this one is not made.

## The addresses

| | |
|---|---|
| `GET /api/health` | Its version, and whether it can read `previous.cfg` |
| `GET /api/status` | What the machine is set to, and whether the kiosk runs |
| `GET /api/token` | Whether the token this request carried is the right one |
| `POST /api/kiosk/start` | Lets the emulated machine come back |
| `POST /api/kiosk/stop` | Shuts it down properly and keeps it down |
| `POST /api/kiosk/restart` | Both, in that order |
| `GET /api/pi` | Temperature, power, sound, disk, what the emulator costs, and which version of this tool is answering |
| `GET /api/files` | Everything this tool holds, as a place with places in it |
| `POST /api/machine` | Makes the emulated machine the one named |
| `POST /api/pi/reboot` | Shuts NeXTSTEP down, then restarts the board |
| `POST /api/pi/poweroff` | Shuts NeXTSTEP down, then switches the board off |
| `GET /api/terminal` | Becomes a WebSocket carrying a login on this machine |

Every POST is checked for the token before anything looks at what was sent. The one route that is not is the terminal, and the section below says why: what answers there is this machine's own SSH server, so whoever is connecting proves who they are to that.

## The shell

`GET /api/terminal` upgrades to a WebSocket, and what runs on the pseudo terminal behind it is `ssh` to this machine's own SSH server on the loopback. So what somebody sees is the login prompt sshd puts up, and what they get afterwards is an ordinary login shell: their own home, `sudo` if they have it, everything they would have sitting at the machine.

**This is why there is no token on that route.** The door is the same one sshd already holds open on this network, and the service is only the corridor. It never learns a password, never changes user, and needs no privilege of its own to hand out a shell that can do everything the person logging in can do.

The other two ways are worse in both directions. Forking a shell here would hand one out without asking anybody who they are, and that shell would inherit this service's sandbox: no `sudo`, a read-only home, and a person left wondering why. `/bin/login` would ask, but it changes user, which `NoNewPrivileges=yes` refuses for this whole process tree, and on current Debian it no longer works when another program calls it. WeTTY solves it the same way when it is not running as root.

**The first thing the browser says is who is logging in**, as `{"login": "next", "size": [rows, columns]}`, so the session starts at the size it will be read at. The name is checked against what a Unix login name may be, because it becomes an argument to the SSH client and one beginning with a dash would be read as an option. After that, binary frames are what the session sees and text frames are what it is told, which today is `{"resize": [rows, columns]}`.

**A browser that connects and says nothing is given up on after ten seconds**, because there is one session at a time and holding it needs no password. A second browser is answered with 409.

**It ends when the socket does.** The window closing, the page going, or the login ending all end the other side, and the hangup goes to the whole process group so that what was left running goes with it.

The SSH client is told not to check the host key and not to write one down, because the service's home is read only and the other end of the loopback is this machine: an impostor there would already be root on it. It is also told to use passwords rather than keys, so that a key put in `authorized_keys` later cannot quietly turn the login prompt off.

`websocket.py` is the protocol, out of the standard library: the handshake from `hashlib`, the frames from `struct`. `terminal.py` is the session and the two directions it is pumped in.

In the browser, `web/terminal.js` is the view and `app.js` holds the socket and the login prompt. The view draws what it is given, says what was typed into it and says how large it has become; what is on the other end is the page's business.

**The one library.** Everything else here is written from nothing, and a terminal is not: what arrives from a shell is a stream of escape sequences that move a cursor, switch to an alternate screen and scroll a region. `xterm.js` 5.5.0 and its fit addon 0.10.0 do that, both MIT, in `web/vendor/` with the licence beside them. That is also why the terminal view is not part of the kit, which takes nothing from anybody.

It is themed to what NeXT's Terminal was, black on white with a blinking block cursor. The sixteen ANSI colours stay, because a shell that paints its prompt is saying something with them, and the pale ones are darkened to be readable on white. The scroller NeXTSTEP put on the left of its own terminal is #107.

## Changing which machine it is

Choosing a NeXTcube Turbo is not one setting. It is a machine type, a processor level, a clock, whether the colour board is seated, which slot it speaks from, and four memory banks, and getting one of them wrong gives a machine that will not boot or is not the one that was asked for. `machines.py` holds the eleven that can be chosen and what each is in the file.

Those values come from Previous itself, out of the function its own dialogue runs when the machine changes there. Sixteen keys are written and everything else in `previous.cfg`, including the disk it boots from, belongs to the installation rather than to the machine and is passed through untouched.

**They have to be written together.** Seven of them follow from the machine type, the turbo board and the colour board at once: the processor level, its clock, the floating point unit, the real-time clock chip, the SCSI controller, the bus interface chip and the DSP's expansion memory. A machine that gets some of them and keeps the rest is not a machine Previous can run, and it does not say so: it resets in a loop and shows a white screen with nothing in the log.

**The order is fixed, because the risky part is not the writing.** Previous reads `previous.cfg` when it starts and never again, so a change made underneath a running emulator does nothing until it restarts and nobody watching can tell. And a machine it cannot run leaves a black screen with SSH as the only way back.

**Previous never writes the file back by itself.** Not when it exits, and not when its own configuration dialogue closes. The only thing that writes is "Save Config" in that dialogue, which asks for a filename first. So what somebody sets behind F12 holds for that session and is gone at the next start unless they save it, and this tool cannot see it whilst it is only in the emulator's memory. What it does see, within five seconds, is a file somebody saved.

That also decides what this tool overwrites, which is the sixteen keys that make up a machine and nothing else. Disks, sound, network and screen are left exactly as the file has them, whoever put them there.

So: shut the guest down properly, copy the file beside itself as `previous.cfg.bak`, write, let it come back, and watch long enough to know that it did. Anything that does not come back is put straight back the way it was.

**Watching means two questions, not one.** A configuration Previous cannot run makes it exit at once, and the waiting console starts it again, so a machine that is broken looks exactly like one that is running. The age of the emulator process is what tells them apart.

## Switching the machine on and off

**Stopping means pressing the power button, not killing the emulator.** Previous maps the NeXT power button to F10. Taking the emulator away instead leaves the guest's file system dirty, and it runs a check on the way back up.

One key is not enough. NeXTSTEP answers the power key with a panel asking whether the machine should really switch off, so the return key follows it two seconds later to press that panel's default button.

The keys go in through the X server with `xdotool`, because Previous runs as an X client under the kiosk's Xwayland. A Wayland virtual keyboard is not the way: it binds its protocol against the compositor and reports success, and the emulator never sees the key. Both directions were measured on the machine.

**Restarting or switching off the board takes NeXTSTEP down first**, and waits for it. A board that reboots underneath a running emulator does the same damage as killing the emulator, and to a machine that then has to come back up.

**The tool still needs no privileges for that.** Only root may power a machine down, so the tool does not: it leaves a file in its own runtime directory, and a systemd path unit running as root does the one thing that file means. `previously-reboot.path` watches for `/run/previously/reboot` and starts a unit whose whole body is `ExecStart=/usr/bin/systemctl reboot`. The name of the file is the whole of the request, so there is nothing to pass and no shell to pass it through.

A sudoers rule was the other way to do this, and it cannot work here: the service sets `NoNewPrivileges=yes`, which is exactly what stops `sudo` from becoming root, and that flag is worth more than the convenience.

**Keeping it down is a file, not a systemd command.** `getty@tty1` restarts itself the instant a session ends, and the console's `~/.profile` starts the emulator. So when the guest powers off, a fresh emulator is booting a second later, and anything arriving after that to stop the unit would kill a guest that had just begun writing.

`~/.profile` therefore waits on `/run/previously/hold` rather than starting the emulator unconditionally:

```sh
while [ -f /run/previously/hold ]; do sleep 2; done
exec cage -- /usr/bin/previous
```

That path is a tmpfs and is empty at every boot, which is what makes restarting the board work: the machine comes back and starts its emulator whoever switched it off before the last shutdown. On the card it would leave a board that reboots waiting for a file nobody is going to remove.

Stopping writes that file, presses F10 and waits for the guest to go. Starting removes the file, and the waiting console notices within two seconds. Nothing is killed, nothing races, and the service never needs a privilege it could misuse.

**The warning before stopping is always shown and always says the same thing.** Previous exposes nothing about what the emulated machine is doing, so a warning that appeared only sometimes would teach the reader that its absence means safe, which cannot be known.

## Its own configuration

`/etc/previously/config.ini`, with defaults that work unconfigured, so the package installs into a running state rather than into a file to edit. `packaging/config.ini` is that file with every default written out.

## The interface

`web/` holds the same custom elements the draft in `../design/` is built from: `nx-window`, `nx-menu`, `nx-dock`, `nx-tile`, `nx-floor`, `nx-scroller`, `nx-shelf`, `nx-thing`, `nx-ask`, `nx-viewer`.

**An application here is its window.** The Apps folder holds three, and one is running when the window it opens is open, so closing that window is quitting it. NeXTSTEP kept an application alive without windows; this tool has nothing for such an application to be, and a light saying it was running would mean nothing.

What follows is what the dock does: the Workspace tile is Previously itself and never carries the three marks, the Config Editor carries them because it is not built, and Preferences and the Terminal put their tiles on the floor of the screen whilst they are open, because they are not in the dock.

## The six languages

English, German, French, Italian, Spanish and Swedish, which are the six NeXTSTEP itself shipped. English is the default and the one every other falls back to, so a missing entry shows an English sentence rather than a name.

`web/lang/` holds one catalogue per language, `web/strings.js` the lookup. A string is asked for by its key, `t("info.disk")`, and where it says how many of something there are the browser's own rules decide between one wording and another, so French gets its singular for zero without the catalogue saying so. Dates follow the same choice, and German means Austrian here.

Neither the markup nor the kit holds any words. `index.html` carries `data-t` keys and no text, which is why the page cannot show the wrong language for a moment whilst the right one arrives, and `nx-ask` is given the wording of its two buttons by whoever asks the question.

The choice lives in this browser beside the window positions, and changing it writes the whole interface again without a reload. The Preferences window is where it is chosen.

Adding a string means adding it to all six catalogues. `tests/test_strings.py` fails when one of them is missing an entry, when a sentence loses a `{place}` that the others have, when the page asks for a key that is not there, and when the service can answer with a name that nothing can say.

## Preferences

NeXTSTEP's Preferences is a row of module pictures across the top and the chosen module's panel underneath, and this is that with one module in it. The row stays at one module because it is the shape of the window rather than a count: the next one arrives into it instead of introducing it.

The module is the one NeXTSTEP called Localization, and it offers the six languages. Everything it shows comes out of the disk image rather than from us: `Localization.tiff` is the picture Preferences.app carried for it, the window's title is what each language's `preferences.strings` called the application, and the module's name is the `Long Name` in the `Info` file of its own bundle. Three of the six left the application's name untranslated, so the window says `Preferences` in French, Italian and Swedish and `Präferenzen` in German, exactly as it did.

## What it shows

Previously arranges what it has the way NeXTSTEP arranged things, which is a place with places in it. `files.py` builds that tree and `/api/files` hands it over whole, because it is small enough that a route per folder would only add round trips.

```
Previously          the root, drawn as a home the way NeXTSTEP drew one
  Apps
    Config Editor.app
    Preferences.app
    Terminal.app
  Machines
    System          the eleven this project ships, which cannot be changed
    User            what somebody saved, and only once there is something
```

**Everything in it is shown by its name, in every language.** A viewer shows names, and NeXTSTEP's did: `/NextApps` in a German installation holds `Preferences.app` and `Terminal.app` exactly as an English one does, and the Workspace shows the directory called `Apps` under that name. So the folders, the bundles and the machines read the same whatever language the rest of the interface is in.

**What an application is called in words is another thing**, and NeXTSTEP translated that one: the bundle is `Preferences.app` and the window over it says `Präferenzen`. Both are true at once. The words are used in the window's title, in the menu that opens it, and in a panel that talks about it.

**The sentence around the names is read in whichever language is chosen**, so the line under the shelf says `Apps: 3 Einträge` and `System: 11 Einträge, nur lesbar`.

**An application in that folder opens its window**, and one whose window is not built yet says so. Preferences is built, the editor is #50 and the terminal is #6.

**The User folder is not there until it holds something.** An empty folder promises a place to put things, and until saving one is built there is none.

**System cannot be written.** Whatever else happens, the eleven are a set to go back to, and going back is one double click.

**`nx-viewer` is NeXTSTEP's File Viewer**, which is four bands in one window: a shelf that keeps whatever is dropped on it, one line of status, the path as a row of icons with an arrow between each pair, and what the last step of that path holds. The last two sit in scrollers with their troughs always showing, which is what the original does. It knows nothing about what it shows. The page hands it a path, contents and a shelf, and listens for `nx-choose` when something is chosen, `nx-path` when a step of the path is, and `nx-keep` when something is dropped on the shelf. The machines window is one, and the shared directory of #21 will be another.

A thing with a `value` can be lifted and carried, and a window with `drop` takes what lands on it. A menu with `context` is the same menu put where the pointer is and taken away again, and an item in one can carry an `icon` and be `disabled`. Both raise `nx-choose` carrying that value, so double clicking a thing and dragging it somewhere mean the same to whoever answers, and a page answers once. They are split into files here rather than baked into one page, and the pictures are files rather than data URIs.

`web/nextstep.css` and `web/nextstep.js` are generated. The kit is one source per part in `../design/kit/`, each holding its element and its styles beside each other, and `../design/build.py` puts them together into those two files and into the draft. Edit a part there and run `make kit`; `tests/test_kit.py` fails when either file has been edited by hand instead.

`web/previously.css` is this application's own and is not generated. What goes in it is what only Previously has, which today is its Preferences window.

`../design/extract.py` says where the icons came from, and `../design/bootpicture.py` where the two machines came from.

**Every machine in the viewer wears the picture its boot ROM draws.** The ROM has two, a cube and a station, and which one a machine gets follows from `nMachineType`: 0 and 1 stand in the cube's case and 2 in the station's. `/api/files` carries that with each machine, so the viewer can draw before anything is running, and `/api/status` carries it too, so the info window and the panels that ask about the running machine show the same picture. Colour plays no part in it, because a NeXTstation Color stands in the same case as a grey one.

## Installing it on the Pi

```bash
sudo cp -r previously web /usr/lib/previously/
sudo cp packaging/config.ini /etc/previously/
sudo cp packaging/previously.service /etc/systemd/system/
sudo systemctl enable --now previously
```

This is the hand version. The package in #9 replaces it.
