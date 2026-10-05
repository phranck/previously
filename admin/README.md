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

`activity.py` needs none of them. It answers the same kind of question once a second and reads `/proc` alone, because what is cheap at one answer every five seconds is not cheap at one a second. Measured on a Pi 5: a whole reading costs 0.42 ms whilst the emulator runs, against 9.9 ms for an answer to `/api/pi`, which forks `vcgencmd` twice and `ps` once at 1.5 ms a fork. Every figure it gives is the difference between two readings, since the kernel's counters are totals since the board started and a total says nothing about now.

What each is for: `cage` is the compositor the emulator runs in, `7zip` unpacks the disk archive, `xdotool` presses the emulator's keys, and ImageMagick's `import` reads its screen, which is the only way to tell a machine that booted from one that did not.

**To work on it**, `flake8` and `pytest` as well. They are not on the Pi and `install.sh` does not put them there, because nothing in running the service needs them.

```bash
sudo apt install python3-pytest python3-flake8       # Debian, the Pi included
brew install flake8 pytest                           # macOS
```

The interface is checked by `eslint` and by `tsc`, both from `package.json` beside it, and is built by `esbuild`. None of the three ever reaches the Pi: what ships is the built interface, and that is committed.

```bash
npm install                                          # eslint and tsc, into admin/node_modules
brew install esbuild                                 # or npm install --global esbuild
```

**The interface is JavaScript and stays JavaScript.** `tsc` compiles nothing here: with `checkJs` it reads the documentation comment on each function as the types of that function and holds the code to what is already written down beside it. That is most of what TypeScript would give this project, because the comments are there anyway, and it costs no build step and no rename of every file. `interface/nextstep.d.ts` is generated with the kit and is the one thing the checker cannot work out for itself: that `nx-window` carries `open` and `close` and `rename`.

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
| `previously/machines.py` | Which machines exist, what each one is in the file, and the rules Previous keeps |
| `previously/saved.py` | The configurations somebody saved, and what a name may be |
| `previously/files.py` | The places this tool shows, which are not places on any disk |
| `previously/change.py` | Changing the machine without leaving it unable to start |
| `previously/kiosk.py` | Everything this tool does to the machine, in one file |
| `previously/systems.py` | The six systems that can be put on this machine, and where each comes from |
| `previously/release.py` | Which release of this tool is published, where its package is, and what it says about itself |
| `previously/fetching.py` | Where a download may go, and where it may be sent on to |
| `previously/discs.py` | The media that go beside the system, and what NeXTSTEP cannot read |
| `previously/setup.py` | What root does on this tool's behalf, and the only thing root does |
| `previously/screen.py` | Reading the emulated screen, and pressing its keys |
| `previously/grab.py` | Taking a picture of that screen and keeping it |
| `previously/terminal.py` | The shell session behind the Terminal window |
| `previously/websocket.py` | The protocol that session travels over |
| `previously/pi.py` | What the board underneath is doing |
| `previously/activity.py` | The same question asked once a second, off `/proc` alone |
| `previously/server.py` | Which addresses exist and what answers them |
| `previously/password.py` | The one secret, who is signed in, and what a request may do without it |
| `previously/answers.py` | How the service names what happened, so the browser can say it |
| `interface/app.js` | Where the page starts, and the order everything in it is woken in |
| `interface/app/` | One module per subject, which is what the interface is made of |
| `interface/lang/` | One catalogue of words per language |
| `build_web.py` | What bundles that into the three files a browser is given |
| `web/` | What the browser gets, and nothing in it is written by hand |
| `web/vendor/` | The one library this interface takes, with its licence |
| `web/fonts/` | The face the Terminal and the code in a document are set in, with its licence |
| `packaging/` | The unit and the default configuration |

`kiosk.py` is one module because it is the whole surface: reviewing what this tool may do to the machine means reading that one file.

**What a version is.** `RELEASE` in `server.py` is the release, and it is written down in that one place. `packaging/build.py` reads it and asks git what the tree is, so a package built on the tag of that release is the plain number and every other build carries how far it stands from the last tag and which commit it is: `1.0.0+7.g2f250d5` after the release, `1.0.0~7.g2f250d5` on the way to one, and `.modified` on the end where something was uncommitted. The count is there because dpkg orders versions and a hash does not. The version it settles on is written into the package as `previously/version.txt`, which is what the service reports about itself, so what the API answers and what `dpkg` says are the same string.

**The interface shows the release and drops the build.** `words.released` is the one place that decides it, so `1.0.0+35.g553551d` reads as `1.0.0` in the Raspberry Pi window and in the About panel. What is dropped is not lost: it is what apt orders packages by, it is still in every answer the API gives, and `dpkg-query -W previously` on the Pi says it in full. On a screen it costs the whole line and buys nothing. The emulator's own version is left whole, because `4.3-0wmlive1` is what that package is called and `4.3` would name a version that does not exist.

**It needs no privileges at all.** Reading state does not, because `systemctl is-active` answers any user. Switching the emulated machine on and off does not either, because it happens through one file rather than through systemd. The next section says why.

Installing the emulator does need them, and the tool still does not have them: it writes a request and a separate program acts on it as root. "Installing from the browser" below says what that program may be asked to do, which is three names out of three tables.

## What anybody on the network can reach

**Reading is open.** Anything on the same network can see which machine is configured, how much memory it has, which disk it boots and whether it is running. That is deliberate: knowing the Pi is set up as a NeXTcube costs nothing.

**Changing anything needs the password.** Writing a configuration, stopping the emulator, taking a picture of the screen: all of it is refused without it. Sitting at the machine and pressing F12 needs physical access to it. Being on the network does not, and that difference is what the password answers.

**The password is chosen in the interface, not fetched from the Pi.** A machine nobody has claimed asks the first browser that reaches it to choose one, and there is nothing to read over SSH and nothing to copy. What the service keeps is an scrypt hash in `/var/lib/previously/password`, readable by the service alone, and the password itself is never in this repository, never in a URL and never in a log line. A browser that has given it holds a session in a cookie that no script on the page can read, so nothing the page loads can take the secret with it.

Whoever is on the network whilst the machine is still unclaimed can claim it. That window lasts from installing the tool until somebody first opens it, the interface says plainly whilst it is open, and closing it would mean going back to a secret fetched from somewhere else.

**Changing the password is the same panel.** A browser that is signed in chooses a new one, and every other browser has to give it again. Forgetting it is the one thing that still needs the Pi: `sudo rm /var/lib/previously/password` leaves the machine unclaimed, and the next browser sets a new one.

**It speaks plain HTTP, and there is no TLS.** The password crosses the home network in the open, so somebody already inside that network and reading traffic can take it. That is not the threat it is for. It is there so that nothing reaches this by accident, and so that a device with no business writing a configuration cannot. It is also why this is the tool's own password rather than the Pi's login: what somebody reading the network gets is this tool, not a shell.

Anybody putting this anywhere less trusted needs more in front of it than a certificate, and that layer terminates TLS itself. A security claim that is not true is worse than none, so this one is not made.

## The addresses

| | |
|---|---|
| `GET /api/health` | Its version, and whether it can read `previous.cfg` |
| `GET /api/status` | What the machine is set to, and whether the kiosk runs |
| `GET /api/machine/settled` | What a configuration would be, and what else could be chosen with it |
| `GET /api/session` | Whether this machine has a password, and whether this browser has given it |
| `POST /api/session` | Takes the password and answers with a session |
| `POST /api/session/end` | Ends this browser's session |
| `POST /api/password` | Sets the password, on a machine nobody has claimed or from a browser that is signed in |
| `POST /api/kiosk/start` | Lets the emulated machine come back |
| `POST /api/kiosk/stop` | Shuts it down properly and keeps it down |
| `POST /api/kiosk/restart` | Both, in that order |
| `GET /api/pi` | Temperature, power, sound, disk, what the emulator costs, whether it has crashed since the boot, and which version of this tool is answering |
| `GET /api/activity` | What every core is doing, the load averages, memory, and what the emulator costs |
| `GET /api/files` | Everything this tool holds, as a place with places in it |
| `POST /api/machine` | Makes the emulated machine the one named, from either set |
| `POST /api/machine/save` | Keeps a configuration under a name, without touching the running machine |
| `POST /api/machine/rename` | Gives a saved configuration another name |
| `POST /api/machine/remove` | Takes a saved configuration out of the list |
| `POST /api/disk` | Makes the machine boot the disk of the system named |
| `POST /api/disk/backup` | Asks for a copy of one of the disks |
| `POST /api/disk/restore` | Asks for a copy to be written back over its disk |
| `POST /api/disc` | Puts a disc on a free slot beside the disk that boots |
| `POST /api/disc/eject` | Takes the disc off a slot, and never off slot 0 |
| `POST /api/pi/reboot` | Shuts NeXTSTEP down, then restarts the board |
| `POST /api/pi/poweroff` | Shuts NeXTSTEP down, then switches the board off |
| `GET /api/setup` | Which systems there are, which are here, how much room is left, and what is being installed |
| `POST /api/setup` | Asks the privileged helper to install, update, remove or fetch something |
| `GET /api/update` | Which version of this tool is installed, which is published, and how a replacement of it is getting on |
| `GET /api/update/notes` | What the published release says about itself, as the Markdown it was written in |
| `POST /api/update` | Asks the privileged helper to replace this tool with the newest release |
| `GET /api/terminal` | Becomes a WebSocket carrying a login on this machine |

Every POST is checked for a session before anything looks at what was sent, and the three routes above about the secret itself are what a browser goes through to have one. A POST that says it comes from another page is refused whatever it carries, because a cookie rides along with every request to this host and a session alone would let another site act here.

The one route with no check of ours at all is the terminal, and the section below says why: what answers there is this machine's own SSH server, so whoever is connecting proves who they are to that.

**Every answer from the API is `no-store`**, because each one is about right now and a kept copy is a wrong one. Files are the opposite and say so: each carries an `ETag` and a `Last-Modified`, and a browser that already has one is told `304` rather than sent it again. The pictures, the faces and the one vendor library also carry a day's `max-age`, since they change when a package is installed and at no other time. The page, the script and the stylesheet carry `no-cache`, which means the browser asks every time and is told `304` when nothing changed, so a new build is picked up at once.

**The connection stays open.** `http.server` speaks HTTP/1.0 unless it is told otherwise, which closes the socket after every answer. That was costing a page load thirty connections, and on a Pi joined by Wi-Fi each of those took two seconds to open: measured on 2026-09-29, an icon of 1232 bytes arrived 8.7 seconds after it was asked for, of which 1 millisecond was the data. Every answer here carries a `Content-Length`, which is what lets the handler speak 1.1 and keep the socket.

## The shell

`GET /api/terminal` upgrades to a WebSocket, and what runs on the pseudo terminal behind it is `ssh` to this machine's own SSH server on the loopback. So what somebody sees is the login prompt sshd puts up, and what they get afterwards is an ordinary login shell: their own home, `sudo` if they have it, everything they would have sitting at the machine.

**This is why there is no check of ours on that route.** The door is the same one sshd already holds open on this network, and the service is only the corridor. It never learns a login's password, never changes user, and needs no privilege of its own to hand out a shell that can do everything the person logging in can do.

The other two ways are worse in both directions. Forking a shell here would hand one out without asking anybody who they are, and that shell would inherit this service's sandbox: no `sudo`, a read-only home, and a person left wondering why. `/bin/login` would ask, but it changes user, which `NoNewPrivileges=yes` refuses for this whole process tree, and on current Debian it no longer works when another program calls it. WeTTY solves it the same way when it is not running as root.

**The first thing the browser says is who is logging in**, as `{"login": "next", "size": [rows, columns]}`, so the session starts at the size it will be read at. The name is checked against what a Unix login name may be, because it becomes an argument to the SSH client and one beginning with a dash would be read as an option. After that, binary frames are what the session sees and text frames are what it is told, which today is `{"resize": [rows, columns]}`.

**A browser that connects and says nothing is given up on after ten seconds**, because there is one session at a time and holding it needs no password. A second browser is answered with 409.

**It ends when the socket does.** The window closing, the page going, or the login ending all end the other side, and the hangup goes to the whole process group so that what was left running goes with it.

The SSH client is told not to check the host key and not to write one down, because the service's home is read only and the other end of the loopback is this machine: an impostor there would already be root on it. It is also told to use passwords rather than keys, so that a key put in `authorized_keys` later cannot quietly turn the login prompt off.

`websocket.py` is the protocol, out of the standard library: the handshake from `hashlib`, the frames from `struct`. `terminal.py` is the session and the two directions it is pumped in.

In the browser, `interface/terminal.js` is the view and `interface/app/shell.js` holds the socket and the login prompt. The view draws what it is given, says what was typed into it and says how large it has become; what is on the other end is the page's business.

**The one library.** Everything else here is written from nothing, and a terminal is not: what arrives from a shell is a stream of escape sequences that move a cursor, switch to an alternate screen and scroll a region. `xterm.js` 5.5.0 and its fit addon 0.10.0 do that, both MIT, in `web/vendor/` with the licence beside them, and its stylesheet is in `interface/vendor/`. That is also why the terminal view is not part of the kit, which takes nothing from anybody.

One line is taken off each of them as they are vendored: the `sourceMappingURL` at the foot, which names a map that is not here. Left on, every page load with the console open asks for it and is told 404 twice. Shipping the maps is the other answer and the worse one, because xterm's is about a megabyte, it is read only by somebody debugging a library they did not write, and this service is reached over a Pi's Wi-Fi. `tests/test_web.py` holds both files to that, so an upgrade that brings the line back is caught here rather than in a console.

It is themed to what NeXT's Terminal was, black on white with a blinking block cursor. The sixteen ANSI colours stay, because a shell that paints its prompt is saying something with them, and the pale ones are darkened to be readable on white. The scroller NeXTSTEP put on the left of its own terminal is #107.

## Changing which machine it is

Choosing a NeXTcube Turbo is not one setting. It is a machine type, a processor level, a clock, whether the colour board is seated, which slot it speaks from, and four memory banks, and getting one of them wrong gives a machine that will not boot or is not the one that was asked for. `machines.py` holds the eleven that can be chosen and what each is in the file.

Those values come from Previous itself, out of the function its own dialogue runs when the machine changes there. Sixteen keys are written and everything else in `previous.cfg`, including the disk it boots from, belongs to the installation rather than to the machine and is passed through untouched.

**They have to be written together.** Seven of them follow from the machine type, the turbo board and the colour board at once: the processor level, its clock, the floating point unit, the real-time clock chip, the SCSI controller, the bus interface chip and the DSP's expansion memory. A machine that gets some of them and keeps the rest is not a machine Previous can run, and it does not say so: it resets in a loop and shows a white screen with nothing in the log.

**The order is fixed, because the risky part is not the writing.** Previous reads `previous.cfg` when it starts and never again, so a change made underneath a running emulator does nothing until it restarts and nobody watching can tell. And a machine it cannot run leaves a black screen with SSH as the only way back.

**Previous never writes the file back by itself.** Not when it exits, and not when its own configuration dialogue closes. The only thing that writes is "Save Config" in that dialogue, which asks for a filename first. So what somebody sets behind F12 holds for that session and is gone at the next start unless they save it, and this tool cannot see it whilst it is only in the emulator's memory. What it does see, within five seconds, is a file somebody saved.

That also decides what this tool overwrites, which is the sixteen keys that make up a machine and nothing else. Sound, network and screen are left exactly as the file has them, whoever put them there.

**Disks are the one exception, and it is three keys wide.** Which disk the machine boots is `szImageName0`, `nDeviceType0` and `bDiskInserted0`, and those are written when somebody activates a disk and at no other time. The six further slots, the write protection and everything else in `[HardDisk]` stay exactly as the file has them, so a disc somebody put on the bus is still on the bus afterwards. What it points at is always one of the disks this tool put on the card and never a path from anywhere else.

So: shut the guest down properly, copy the file beside itself as `previous.cfg.bak`, write, let it come back, and watch long enough to know that it did. Anything that does not come back is put straight back the way it was.

**Watching means two questions, not one.** A configuration Previous cannot run makes it exit at once, and the waiting console starts it again, so a machine that is broken looks exactly like one that is running. The age of the emulator process is what tells them apart.

## System and User configurations

The eleven in `machines.py` are System configurations and cannot be changed. Whatever else happens there is a known set to go back to, and going back is one double click. Anything somebody puts together is a User configuration, kept under a name they gave it, and those two sets are the two folders in the machines window.

**They live in one file in the home**, `~/.config/previously/machines.json`, one directory along from the emulator's own configuration. In the home rather than under `/var/lib`, because they are the person's: what the service keeps under `/var/lib` is its own, being the hash of the password and the digest of its last write, and `apt purge` takes that with it. It must not take away the machines somebody built, any more than it takes `previous.cfg` or the disk image. One file rather than one per configuration, because a name is not a file name: a file each would need a second answer to what a configuration is called, and the two would part company the first time one was renamed. It is written beside itself and moved into place, so a write that fails halfway leaves the file as it was.

**The unit opens that one path and the package creates it.** `ProtectHome=read-only` leaves the rest of the home alone, and systemd skips a `ReadWritePaths=` entry whose path is absent, so the directory has to exist before the service starts or the first save refuses. `postinst` makes it, reading the user and the group out of the unit rather than naming them a second time. Opening `~/.config` instead, which exists already, would let a service reachable on the home network rewrite every other application's configuration in that home to save five lines, so it is not done. `tests/test_packaging.py` holds the three places that name this path against each other, because a machine where they disagree looks exactly like one where they agree until somebody saves something.

**A name has to be a name.** It cannot be empty, it cannot be longer than 48 characters, which is what can be read under an icon, and it cannot hold a slash, because that is what parts one folder from the next in the path the viewer shows. No two configurations may share one, compared without case and across both sets: a User configuration called after one of the eleven would show two things with the same name in the same window.

**Saving does not activate.** Keeping a configuration and running one are two different acts, and only the second shuts the guest down and writes `previous.cfg`. So the Config Editor cannot leave a machine that will not boot, and a saved configuration is run exactly as one of the eleven is, by double clicking it or through its context menu.

**Previous's own rules are kept when a configuration is written and again when it is read.** The emulator never refuses a configuration it cannot run: it corrects one, partly in its own dialogue when the machine type changes and partly at every start, whatever wrote the file. `machines.settled` is that correction, so colour on a cube, a NeXTdimension in a station, three megabytes in a bank and a fifth bank all come back as the machine that would actually run. A file somebody edited by hand gets the same treatment as one this tool wrote.

Which sizes a memory bank takes comes from the same place: 0, 2, 8 and 32 with a turbo board, 0, 2 and 8 with colour, and 0, 1, 4 and 16 otherwise, rounded up to the next of those. A NeXTstation without a turbo board and without colour reaches two banks rather than four, because on that board the other two are not physically there.

**Bank 0 is the one the machine boots from.** Previous says so on the face of its own memory dialogue, and does not enforce it: the check that would is compiled out. This tool does, so that bank is offered no empty socket and no module below 4 MB, and asking it to be empty leaves the smallest it can boot from. A gap behind it is left alone, because Previous corrects one only on a NeXTdimension board, where its own comment says an empty first bank with memory behind it panics the kernel, and it says nothing of the kind about the machine's own memory.

**Renaming and removing belong to User alone.** The context menu offers them for a saved configuration and does not carry them at all for one of the eleven. Removing one takes it out of the list and leaves `previous.cfg` alone, so a machine running that configuration goes on running it.

## The Config Editor

Previous's own System dialogue, in this interface's idiom. That dialogue puts what can be chosen on its left and what follows from it on its right, and this window stacks the two: the machine's picture and four readings above the groups that change them.

**Every control is something Previous can actually be told, and something it acts on.** The machine type, the boards that can be seated, the processor clock, how much memory, the four banks it sits in, the DSP with its own memory, and what the machine has fitted. Everything else in the forty-one keys follows from those, so offering it would be offering a machine that does not exist.

**The memory speed is written and not offered.** It goes into System Control Register 1 and nowhere else, so it changes what the machine says about itself and nothing about how fast it runs, and two of its four positions are not even distinct on a machine without a turbo board. Previous never moves it either, since `Configuration_SetSystemDefaults` does not touch the key, so this tool writes what Previous starts every machine from.

**The NeXTdimension is three boards.** A cube holds one in each of slots 2, 4 and 6, and each has memory of its own: 4, 16, 32 or 64 MB, which is what its four banks of 4 and 16 MB come to. A slot is a cell that puts a board in and takes it out again, and a board that is in gets a group of its own for its memory. The console follows the first board there is, and a machine with no board draws it itself. A NeXTstation holds none of them, because the board speaks on the NeXTbus and that machine has none.

The board's ROM is not here. A path to a file on the Pi is not the machine.

**What is fitted is the drive, never what is in it.** Whether the machine has a floppy drive, a magneto-optical drive, a network connection and which of the two sockets it uses, and whether the printer port is in use. A disk image, a paper size and a directory to print into are the installation's business and are not here. NeXT's 1988 machine is the one with the optical drive and no floppy, a turbo board drops the optical drive, and that machine has the coaxial socket alone. Previous says the first two on the face of its own dialogues without enforcing either, and the third it does enforce at every start.

**Memory is a total or four banks, and the banks are the real thing.** A total lays them out the way Previous lays them out, which is the quick way to a machine somebody wants. Pressing a bank fits the next size that bank takes and comes back to an empty one after the largest, so a machine no total adds up to can be built by hand.

They are drawn as what they are: four named sockets stacked the way the modules stand on the board, each a sunken field with a raised module in it where something is seated. Those two edges are what this whole interface is built from, so it needs no picture of a memory module. An empty socket says so rather than standing blank, and a bank the machine does not have keeps its place and loses its edge.

**The window holds no rule at all.** On every change it asks `GET /api/machine/settled` what that configuration is and what may be chosen beside it, and draws the answer. So there is one statement of what Previous allows, in `machines.py`, and the interface cannot show a machine the emulator would correct underneath it: a cube in colour comes back as a cube, and a total of 128 MB asked of a plain station comes back as the 32 it holds. What it saves is the configuration the service handed back rather than one assembled in the browser.

**One subject at a time.** Thirteen groups in one column is taller than the desk, so a row of cells across the top chooses between Machine, Processor, Memory, Graphics and Fitted, and the groups below it take turns. That is the shape Preferences gives its modules, with words in the cells rather than pictures, because there is no drawing of a processor or of memory to put in one. Which subject is showing survives a change to the machine, so choosing a board does not send anybody back to the first.

**A group whose values have an order is a knob in a trough rather than a row of cells.** The processor clock, the memory and a NeXTdimension board's memory are all read as more or less of one thing, and a row of cells says they have none. `nx-slider` is that knob: the scroller's own trough and knob laid on their side, moving between the steps it is given and never between them, with the value beside it in the same sunken field the info panels state a fact in. Everything that is one of several rather than more of one thing keeps its cells.

A group with nothing to offer is not drawn, and a group's cells change with the machine. The boards group holds only the boards that machine takes, and the clock group holds the fastest one only where the turbo board that carries it is seated, which is what Previous does with its own 40 MHz option.

**Under each group, a line says what the chosen setting does and what it changes elsewhere in the window.** The page writes it from the choice: a group of one choice shows the sentence for its value, a group of switches shows one sentence per switch for the state it is in, and the memory banks say which modules this machine takes and whether the first bank is large enough to boot from. `tests/test_strings.py` derives every value the service can offer from `machines.py` and fails when the English catalogue has no sentence for one of them.

**The clock is chosen rather than worked out.** Previous offers 16, 20, 25 and 33 MHz for every machine and 40 only with a turbo board, and so does this. Changing the machine type or a board sets the clock afresh, to 33 with that board and 25 without, which is what `Configuration_SetSystemDefaults` writes at both of those moments.

**The clock is also where Nitro lives.** Previous has no such thing and reads `nCpuFreq` as it finds it, so what the catalogue calls a Nitro is a turbo board running at 40.

**The DSP is three choices rather than a chip that is simply there.** It can be absent, or a 56001, or a 56001 started with its bootstrap ROM, which is the more faithful of the two and loads no file. Its own memory is 24 or 96 kB, and that group is not drawn where there is no chip to give memory to. The 1988 machine is the one whose DSP has no expansion, and every machine gets its own back whenever the machine type or a board changes, exactly as the clock does.

**Saving does not activate.** Opened on one of the eleven, which cannot be changed, it asks for a name and keeps a configuration of your own. Opened on one of your own, it writes that one back under the name it has. Either way `previous.cfg` is untouched, so the editor cannot leave a machine that will not boot. Starting one is the same double click as always.

It opens three ways: from the context menu on a machine, which is the one that decides what is being edited; from its tile in the dock; and from `Config Editor.app` in the Apps folder. The last two open it on the configuration that is set now, because that is the machine in front of you.

## Disks, and which one the machine boots

A system is a disk, and several of them fit on the card. `Disks` in the File Viewer holds the ones that are here, each with the name of the system on it, how large it is and the picture of what it is: `winchester`, which is what NeXTSTEP drew for a hard disk. A disk is not drawn as a disc for the same reason a machine wears the drawing its own boot ROM makes of it.

**Choosing which one the machine boots is the same gesture as choosing a machine**, a double click or Activate in the context menu, and it goes through the same cycle in `change.py`: the guest is shut down through the power key, three keys are written, the machine comes back, and anything that does not come back gets its old disk put straight back.

**What was on the disk that was running stays on it.** Each system is one file, the guest writes into that file, and pointing the machine elsewhere freezes the first exactly as it was left. The panel says so before anything happens, because somebody who has spent an evening inside NeXTSTEP wants to read it there rather than find out afterwards.

## Discs, which go beside the system

A system is a disk and the machine boots it. Developer Tools, applications and whatever else somebody wants inside NeXTSTEP are media: they go on a free slot of the SCSI bus beside the disk that is running, write protected, and NeXTSTEP mounts them the way it mounted a CD on the bus. `Discs` in the File Viewer holds what is there, and a disc that is in the machine says which slot it is on.

**They are files somebody puts on the Pi**, in `~/nextstep/discs`, rather than anything this tool fetches. The six systems are a known set with measured sizes and digests; these are not, and a list of addresses for NeXT media is one this tool could not stand behind. So the folder appears when somebody puts something in it and not before.

**Inserting one is the same cycle as changing a disk.** Previous can put a disc on a slot that is already a CD drive without resetting the machine, and its own dialogue does exactly that: `Change_DoNeedReset` in its `src/change.c` asks for a reset only where a slot's device type changes, and a change of image alone re-initialises the SCSI emulation. What it cannot do is notice a file written from outside, because it reads `previous.cfg` when it starts and never again. So from here a disc arrives with the guest shut down properly first, exactly as a disk does.

**A disc is written as `nDeviceType = 2`**, which is what `SCSI_DEVTYPE` in Previous's `src/includes/configuration.h` counts as a CD: none, hard disk, CD and floppy, from zero. It is written protected as well, which is two ways of saying one thing, since Previous makes a CD target read only from its type alone.

**Slot 0 is never ejected.** That is the disk the machine is running, and changing it is choosing another disk rather than taking this one out from under the system.

**An image that says ISO 9660 says so in the panel.** NeXT's own CDs carry a variation of 4.3BSD FFS, so an ISO 9660 image mounts nowhere however good it is. That is a positive test on the signature at offset 0x8001 and nothing more: an image that says nothing may still be anything, and the tool claims nothing about those.

**A disc wears the generic SCSI device**, because NeXTSTEP 3.3 has no picture of a CD at all. Its Workspace carries a hard disk, a floppy, the magneto-optical cartridge, the network and a SCSI device, and a CD-ROM on the bus is the last of those. Nothing is invented for it.

**A disk can be copied, and a copy can be put back.** A system is one file, so a backup of it is a copy of that file, kept in `Backups` inside the disks folder and shown there as what it is. Both directions are the helper's work, because a disk is two gigabytes and that folder is one this service may not write, so the Installer window is where the copying is watched.

Both directions need the machine switched off. A copy taken whilst NeXTSTEP is writing is a torn file system: it looks like a disk and fails on its first boot in a way nobody can debug. What a copy costs and what would be left on the card is in the question, and putting one back says plainly that what is on that disk now is written over. The copy is written beside the disk and moved into place, so a card that fills up half way through leaves the disk that was there rather than half of each.

**Which system needs which machine is not written down anywhere this tool can read**, so it is not guessed at. What answers it is the machine itself: a disk that will not boot on the configuration in force does not come up, and the rollback puts the old one back. That is the same answer the tool already gives for a machine it cannot run, and it needs no table that would be wrong somewhere.

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
cage -- /usr/bin/previous
status=$?
if [ "$status" -ne 0 ] && [ -d /run/previously ]; then
  printf "%s %s\n" "$(date +%s)" "$status" >> /run/previously/crashes
fi
exit "$status"
```

That path is a tmpfs and is empty at every boot, which is what makes restarting the board work: the machine comes back and starts its emulator whoever switched it off before the last shutdown. On the card it would leave a board that reboots waiting for a file nobody is going to remove.

**An emulator that ends badly says so in one line**, and the Raspberry Pi window reads it. The file is on that same tmpfs, so what is in it happened since this board came up and nothing has to work out when. The `exit` runs the session down exactly as `exec` did, so the console never falls through to a shell prompt.

**No core dumps.** Debian sets the soft core limit to 0 for every user in `/etc/security/limits.d/10-coredump-debian.conf`, and this project leaves that as it is rather than writing a limit of its own, because the platform already answers the question. It is also the right answer here: a machine that boots into an emulator and is looked after through a browser has nobody to read a 37 MB dump, and nine of them once sat in the home for two days without anybody opening one. What a person wants is to know that it crashed, which is the line above.

Stopping writes that file, presses F10 and waits for the guest to go. Starting removes the file, and the waiting console notices within two seconds. Nothing is killed, nothing races, and the service never needs a privilege it could misuse.

**The warning before stopping is always shown and always says the same thing.** Previous exposes nothing about what the emulated machine is doing, so a warning that appeared only sometimes would teach the reader that its absence means safe, which cannot be known.

## Installing from the browser

Somebody with a bare Raspberry Pi OS installs one package and does everything else in a browser. What that takes is root, twenty-five times over: apt sources, packages, files in `/etc/systemd/system`, the kernel's command line in `/boot/firmware`. The tool has none of that and gets none of it.

**A second program has it, and knows one job.** `previously-setup.path` watches for `/run/previously/setup`, and the unit it starts runs `previously/setup.py` as root. That file is the whole of the privileged surface: no routes, nothing parsed from the network, and nothing that arrives from a browser is ever a path, a URL or a command.

**A request is three names.** A job, a system and a machine. Every one of them is looked up in a table that ships with this package, and a name that is not in its table refuses the whole request before anything is touched. So the disk image, which was the one free value in the whole of `install.sh`, stops being free: the helper is asked for one of six systems by name and holds the addresses itself.

The jobs are `install`, which is the whole of `install.sh` and takes a system with it; `update` and `remove` for the emulator; `fetch` and `forget` for one system's disk; `back-up` and `restore` for a copy of one; and `update-tool`, which replaces this tool itself.

**The request is read carefully, because the directory it sits in is not root's.** It is opened without following a link, checked for being an ordinary file and read no further than four kilobytes, and it is taken away before any of the work starts, so the unit watching for it cannot start the same run twice.

**What it writes back is in a directory of root's own**, `/run/previously-setup`, which the tool reads and never writes. The other way round, a file root wrote into a directory an unprivileged service owns could be replaced by a link to somewhere else between one write and the next, and that is a way to have root overwrite anything on the machine.

**Every step skips what it finds already done, and records how to undo what it did.** A failure walks that record backwards, so each step is reversed in the world it left behind, and the record says which step failed and which ones were put back. A step that skipped records nothing, so nothing the machine already had is ever taken away.

**It says how far it has got whilst it runs.** Fetching a system is tens of megabytes and unpacking it is two gigabytes, which is minutes on a Pi, so the progress is a real figure: bytes against bytes for the download and what has been written against what a two gigabyte disk comes to for the unpack. It survives the page being reloaded, because it is a file on the Pi rather than anything the browser holds.

**The six systems are in `systems.py`**, from NeXTSTEP 2.2 to OPENSTEP 4.2, each an archive of 22 to 72 MB that unpacks to a two gigabyte disk: such a disk is mostly zeros. Each carries its size and its SHA-1 as measured from the archive's own metadata, and anything that arrives as something else is thrown away rather than installed. Redirects are followed, because archive.org answers a download by sending the caller to whichever node holds the item, and every hop is checked again so that one leading off the archive ends the fetch.

The Intel builds of OPENSTEP are not offered. Previous emulates 68k hardware, and one of those would download, unpack and never boot.

**A disk is named after its system**, `nextstep-3.3.dd`, in `~/nextstep` beside whatever else is there. A machine set up by `install.sh` has its disk inside a folder named after the archive instead, and that is recognised rather than fetched a second time.

### Installer.app

What NeXT called the application that puts things on a machine and takes them off again, and it wears that application's own face: the open package out of `/NextAdmin/Installer.app`. Two kinds of thing are in it, and they differ in cost and in kind.

**Two tabs**, because they are not the same kind of thing: a package and a two gigabyte disk. The row above them is the same cell the Config Editor gives its five subjects, and the group below takes its turn.

**Previous Emulator** is installed, updated and removed as one thing, because Previous on its own is not a machine that boots: what goes with it is the compositor it runs in, the console that logs in by itself, the silenced startup and the start on the first console. Removing it is that list backwards, and it is the half to get right rather than the half to leave out, since a tool that can only install is one nobody dares press.

A line under the group says what each button does. Update is not there at all unless the archive has something newer, and where it is, it names the version it would bring: a button that would fetch the version already installed is a button that does nothing. That takes two facts, `dpkg-query` for what is here and `apt-cache policy` for what apt would install, and `dpkg --compare-versions` to decide between them, because Debian's ordering is its own and a string comparison calls 4.10 older than 4.9. All three are read-only and want no privilege, and what they said is kept for a few seconds, since the window asks twice a second whilst it is open.

**Systeme** is a list, one of which is chosen. Each says what it costs, whether it is here or not, and the ones that are here carry NeXT's own checkmark. Three buttons: Remove, Fetch and Activate. NeXTSTEP 3.3 comes with the emulator unless another is chosen, so a machine that has just been set up boots into a system rather than into a prompt about what to do next.

**Activate is the same act as a double click on a disk in the File Viewer**, with the same question and the same code behind it: the guest is shut down through the power key, the configuration is changed to the other system, the machine starts again on it, and a machine that does not come up gets its old disk back. It is offered for a system that is on the card and is not the one already running.

**What it costs is in the question rather than in the failure.** Fetching one says what it travels as, what it becomes, and what would be left on the card. A card that fills up during an unpack leaves a half written image and a person with no idea why.

**Every system shows what it costs, and the ones that are here carry a mark.** How large a system is belongs to the system and is always worth showing; whether it is on the card is a state, and a state is a mark rather than a word. It is NeXT's own, out of `Installer.app`, and the ones that are not here keep the space so the names line up.

**Whilst it runs, the window says which step it is on, what that step is doing and how much of how much.** One step can fetch, then unpack, then move, and each of those takes minutes of its own, so a bar covering all three says none of it. The trough is there only whilst something is happening, the figures come from the Pi rather than from anything the browser holds, and a reload shows the same thing. A failure says which step failed, why, and which steps were put back, in this interface's own words.

**Pressing anything says so at once.** The request is written into a file and a path unit starts the program that reads it, so for a moment the newest thing the Pi has to say is still about the run before. Until a record newer than the request appears, the window says it was asked and holds what the service answered, rather than reading out the last run's ending to somebody who has just pressed a button. It looks four times as often whilst something is happening, because a run where every step finds its work already done is over in a second and would otherwise be missed entirely.

**A run that changed nothing says so.** Every step records whether it did anything, so a run on a machine that already has everything ends with "nothing needed doing" rather than with "finished" and a screen that looks exactly as it did.

**Switching between systems that are already here is not in this window.** That is choosing which disk the machine boots, it takes no time at all, and it belongs with the disks themselves.

**A machine with nothing on it opens into this window.** `GET /api/status` says whether the emulator is installed, whether a system is on the card and whether there is a configuration, and a machine missing any of the three is not set up. The Info window then says "not set up" rather than drawing a machine it cannot read, the buttons that would switch something on are off, and the Installer is put in front of whoever arrived. That answer comes from the service because it is the same question the installer's own steps ask before they decide what to skip, and because a Pi with nothing on it and a Pi that cannot be reached look identical to a page that has to guess.

**`install.sh` still carries its own copy of these steps.** It is the way in on a machine that has no admin tool yet and therefore cannot ask for any of this. Making it ask, so that there is one implementation rather than two, waits until this one has set a real machine up.

### Replacing the tool itself

The Raspberry Pi window says which version is here and which is published, and where they differ it offers a button. Pressing it is the whole of updating this tool: no terminal, no `sudo`, and nothing to copy. `install.sh --update-admin` still does the same thing from a shell and is what a machine with no tool on it needs.

**It is the same helper and the same road.** `update-tool` is a job of `setup.py`, so the request mechanism, the progress record, the allow-listed fetch and the reversal of a run that failed are the ones already described above rather than a second set beside them. The service writes the name of one job into a file and holds no privilege, exactly as it does for an installation.

**Root does the download, and that is the point.** The privileged half has to be able to prove that the file it hands `apt-get` is the package that was asked for, and it cannot prove that about a file an unprivileged user wrote: `/var/lib/previously` belongs to the user this service runs as, so a package downloaded there and a digest reported about it would both be that user's to choose. A digest in the request changes nothing, because whoever writes the file writes the request. So the file never leaves root's hands. The helper fetches it into a directory of its own making, checks it, installs it and removes the directory, whichever way the run went.

**Three things have to agree before `apt-get` is reached.** The size and the SHA-256 that the release states for that asset, then `dpkg-deb -f` saying the package is `previously`, and then `dpkg-deb -f` saying its version is the one the release is tagged as. The digest proves the bytes are the bytes GitHub served; the last two prove that what GitHub served is this tool at the version somebody was offered.

**Which release is newest comes from `api.github.com`**, which carries the tag, the download address, the size and the digest in one answer. `release.py` keeps that answer for a quarter of an hour and looks it up again in a thread, so `GET /api/update` never waits for the network: a board with no internet answers as quickly as one with it and says that nothing is known yet. Four requests an hour against the sixty an address is allowed unauthenticated. The address that answer carries is checked against the same hosts the fetch is allowed, because it arrives inside somebody else's answer and is then handed to a download root makes.

**Two steps, because the second one is the part nobody can see.** Fetching and checking the package is measured in bytes. Installing it stops this service and starts the new one, which the package's own maintainer scripts do, so for a few seconds there is nothing for the page to talk to.

**That is why the record is root's and not the service's.** The helper writes how far it has got into `/run/previously-setup`, which carries `RuntimeDirectoryPreserve=yes` and therefore outlives the service being replaced. The page reads the same run before and after: whilst there is no answer it says the tool is being put in place rather than claiming no contact, and when the new service answers it reads the finished record out of the same file and says which version is now talking to it. Nothing about the run is ever held in the browser.

**A failure leaves the tool that is here running**, which is the safe direction, and nothing is reversed for the same reason `install.sh --update-admin` records no undo: taking a working tool away to answer for a replacement that never happened is worse than the failure. What the window says is which step stopped it and why, in this interface's own words.

**What the release says about itself** is read in Preview, through the Release Notes button beside that line. The notes come with the answer GitHub already gave, so nothing is fetched for them, and they have an address of their own because the answer the window polls is asked every two seconds and these are thousands of characters asked for once.

## Preview and its renderers

Preview opens, takes the document's name as its title and hands the room to whichever renderer takes that kind of document. It does no fetching, no drawing and no clearing of its own. A renderer names the part of the window it fills and says how to fill it and how to empty it, so a third kind of document is an entry in one table rather than a branch through the window.

That is `nx-viewer`'s shape as well, which is handed a path, contents and a shelf and knows nothing about machines. There are two renderers today: a picture, which is fetched because a refusal has to be answerable by asking for the password, and release notes, which arrive whole.

**Markdown is turned into elements rather than into markup.** `markdown.js` creates each element and sets its text, so a line of notes carrying something that looks like markup arrives on the screen as the characters somebody typed. Nothing in the interface writes markup from a string at all, and `tests/test_page.py` holds every module to that rather than leaving it to be remembered.

What it understands is what release notes use: headings three deep, paragraphs, fenced code, lists of both kinds, and inside a line a piece of code, something in bold and a link. Anything else stays the text it is. A link is followed only where it is `https`, and one that is not is shown as the characters it was written with. A Markdown library would understand more and would be a licence, a weight and a supply chain for a tool that ships to a Pi, in exchange for constructs these notes do not use.

## Its own configuration

`/etc/previously/config.ini`, with defaults that work unconfigured, so the package installs into a running state rather than into a file to edit. `packaging/config.ini` is that file with every default written out, and a test holds it to that: a key missing from it is a setting nobody knows about.

Two of those paths are worth telling apart. `state_directory` is `/var/lib/previously` and holds what the service owns, which is the hash of the password and the digest of its last write, and a purge removes it. `machines_file` is `~/.config/previously/machines.json` and holds what the person owns, and a purge leaves it exactly where it is.

## The interface

`interface/` holds the same custom elements the draft in `../design/` is built from: `nx-window`, `nx-menu`, `nx-dock`, `nx-tile`, `nx-floor`, `nx-scroller`, `nx-shelf`, `nx-thing`, `nx-ask`, `nx-viewer`.

**An application here is its window.** The Apps folder holds three, and one is running when the window it opens is open, so closing that window is quitting it. NeXTSTEP kept an application alive without windows; this tool has nothing for such an application to be, and a light saying it was running would mean nothing.

What follows is what the dock does: the Workspace tile is Previously itself and never carries the three marks, the Config Editor carries them whilst its window is closed and loses them whilst it is open, and everything else puts its tile on the floor of the screen whilst it is open, because those are not in the dock.

## The one menu, and what is in it

NeXTSTEP had one menu, and the Workspace's own is what stands there whilst no application is in front. It is called Workspace, which is its name in every language, because it belongs to the desk rather than to any machine: a Pi with nothing installed still has one.

**Info is about the machine this runs on**, which is the Raspberry Pi, and it is there whatever else is. **About NeXTcube Turbo is about the machine it runs**, and it carries that machine's own name, so its words are written by the page rather than taken from the catalogue. On a Pi where nothing is installed there is no machine to be about, and the entry is not in the menu at all. Each window is titled the way its entry is: picking a name off the menu and reading a different one off the title bar is two windows as far as anybody looking at the screen is concerned.

That entry says so with `away`, which is the page's word for something that is not in the menu just now. `hidden` belongs to the menu, which hides every entry owned by another application each time the front window changes, and a page writing into that one would have its work put back a moment later.

## The six languages

English, German, French, Italian, Spanish and Swedish, which are the six NeXTSTEP itself shipped. English is the default and the one every other falls back to, so a missing entry shows an English sentence rather than a name.

`interface/lang/` holds one catalogue per language, `interface/strings.js` the lookup. A string is asked for by its key, `t("info.disk")`, and where it says how many of something there are the browser's own rules decide between one wording and another, so French gets its singular for zero without the catalogue saying so. Dates follow the same choice, and German means Austrian here.

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
    Grab.app
    Installer.app
    Preferences.app
    Preview.app
    Terminal.app
  Discs             the media somebody has put on the Pi, beside the system
  Disks             the systems that are on the card, and only once one is
    Backups         the copies that have been made of them
  Documents
    Pictures        the one real place here, holding the screenshots
  Machines
    System          the eleven this project ships, which cannot be changed
    User            what somebody saved, and only once there is something
```

**Everything in it is shown by its name, in every language.** A viewer shows names, and NeXTSTEP's did: `/NextApps` in a German installation holds `Preferences.app` and `Terminal.app` exactly as an English one does, and the Workspace shows the directory called `Apps` under that name. So the folders, the bundles and the machines read the same whatever language the rest of the interface is in.

**What an application is called in words is another thing**, and NeXTSTEP translated that one: the bundle is `Preferences.app` and the window over it says `Präferenzen`. Both are true at once. The words are used in the window's title, in the menu that opens it, and in a panel that talks about it.

**The sentence around the names is read in whichever language is chosen**, so the line under the shelf says `Apps: 3 Einträge` and `System: 11 Einträge, nur lesbar`.

**An application in that folder opens its window**, and one whose window is not built yet says so. All five are built, and a test holds each one's `opens` to a window the markup actually has.

**The User folder is not there until it holds something.** An empty folder promises a place to put things, and the Config Editor is what puts one there.

**System cannot be written.** Whatever else happens, the eleven are a set to go back to, and going back is one double click.

**`nx-viewer` is NeXTSTEP's File Viewer**, which is four bands in one window: a shelf that keeps whatever is dropped on it, one line of status, the path as a row of icons with an arrow between each pair, and what the last step of that path holds. The last two sit in scrollers with their troughs always showing, which is what the original does. It knows nothing about what it shows. The page hands it a path, contents and a shelf, and listens for `nx-choose` when something is chosen, `nx-path` when a step of the path is, and `nx-keep` when something is dropped on the shelf. The machines window is one, and the shared directory of #21 will be another.

A thing with a `value` can be lifted and carried, and a window with `drop` takes what lands on it. A menu with `context` is the same menu put where the pointer is and taken away again, and an item in one can carry an `icon` and be `disabled`. Both raise `nx-choose` carrying that value, so double clicking a thing and dragging it somewhere mean the same to whoever answers, and a page answers once. They are split into files here rather than baked into one page, and the pictures are files rather than data URIs.

`interface/nextstep.css`, `interface/nextstep.js` and `interface/nextstep.d.ts` are generated. The kit is one source per part in `../design/kit/`, each holding its element and its styles beside each other, and `../design/build.py` puts them together into those files and into the draft. Edit a part there and run `make kit`; `tests/test_kit.py` fails when either of the first two has been edited by hand instead.

The third is for the type checker, and it is read out of the same sources: every element the kit brings, the methods on it, and which tag answers to which. Without it a call to `open` on a window looks like a mistake in every one of the places that makes one.

## What is written and what ships

`interface/` is where the interface is written. `app.js` is the entry, which puts the words on the page, defines the elements and then wires them, and `app/` beside it holds one module per subject, each saying at its head what it is for. A module offers what somebody asks it for and keeps the rest, and every import names where it comes from: nothing here shares one scope any more, which is what makes it possible to see what depends on what. `web/` is what a browser is given, and nothing in it is written by hand.

`make web` runs `build_web.py`, which puts the sources together in the order the page loads them, hands them to esbuild and writes three files: `web/index.html` with its comments gone and three tags where fourteen stood, `web/previously.js` with everything of ours inside one function and every name in it shortened, and `web/previously.css` with the vendor stylesheet, the kit and this application's own. `tests/test_web.py` builds them again and fails when what is committed is not what the sources say, so a source edited without `make web` is caught rather than shipped.

The vendor library keeps its own tag. It arrives minified from the people who wrote it, it is a third of a megabyte, and it never changes, so putting it in a file that is rewritten on every edit would cost a great deal and save one request on a local network.

esbuild is needed here and on whatever runs the tests, and never on the Pi: what it writes is committed, so a package built from a checkout carries the same files as the published one.

```bash
brew install esbuild                 # macOS
npm install --global esbuild         # anywhere with node
```

`interface/app.css` is this application's own. What goes in it is what only Previously has, which is its Preferences window and its Config Editor.

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
