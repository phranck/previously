# The web admin tool

A small service on the Pi that shows what the emulator is set to, from a browser on the home network. It is a more comfortable way to reach what Previous already offers behind F12, and nothing beyond that: no port is forwarded to it and nothing publishes it.

## Running it

```bash
make run          # in the foreground, on port 2342
make check        # lint and tests, which is what a commit needs
```

Nothing is fetched. Everything runs on what Debian ships: `python3`, `python3-pytest` and `python3-flake8`.

## What is in here

| | |
|---|---|
| `previously/settings.py` | What the service itself is configured with |
| `previously/config.py` | Reading and writing `previous.cfg` |
| `previously/machines.py` | Which machines exist, and what each one is in the file |
| `previously/change.py` | Changing the machine without leaving it unable to start |
| `previously/kiosk.py` | Everything this tool does to the machine, in one file |
| `previously/server.py` | Which addresses exist and what answers them |
| `previously/token.py` | The one secret, and what a request may do without it |
| `web/` | What the browser gets |
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
| `GET /api/machines` | Which machines can be chosen |
| `POST /api/machine` | Makes the emulated machine the one named |

Every POST is checked for the token before anything looks at what was sent.

## Changing which machine it is

Choosing a NeXTcube Turbo is not one setting. It is a machine type, a processor level, a clock, whether the colour board is seated, which slot it speaks from, and four memory banks, and getting one of them wrong gives a machine that will not boot or is not the one that was asked for. `machines.py` holds the eleven that can be chosen and what each is in the file.

Those values come from the eleven ready-made configurations in the project's Papers folder. Ten of their 195 keys differ between machines, and those ten are what gets written. Everything else in `previous.cfg`, including the disk it boots from, belongs to the installation rather than to the machine and is passed through untouched.

**The order is fixed, because the risky part is not the writing.** Previous writes `previous.cfg` from memory when it exits, so a change made underneath a running emulator is thrown away by the emulator itself. And a machine it cannot run leaves a black screen with SSH as the only way back.

So: shut the guest down properly, copy the file beside itself as `previous.cfg.bak`, write, let it come back, and watch long enough to know that it did. Anything that does not come back is put straight back the way it was.

**Watching means two questions, not one.** A configuration Previous cannot run makes it exit at once, and the waiting console starts it again, so a machine that is broken looks exactly like one that is running. The age of the emulator process is what tells them apart.

## Switching the machine on and off

**Stopping means pressing the power button, not killing the emulator.** Previous maps the NeXT power button to F10. Taking the emulator away instead leaves the guest's file system dirty, and it runs a check on the way back up.

One key is not enough. NeXTSTEP answers the power key with a panel asking whether the machine should really switch off, so the return key follows it two seconds later to press that panel's default button.

The keys go in through the X server with `xdotool`, because Previous runs as an X client under the kiosk's Xwayland. A Wayland virtual keyboard is not the way: it binds its protocol against the compositor and reports success, and the emulator never sees the key. Both directions were measured on the machine.

**Keeping it down is a file, not a systemd command.** `getty@tty1` restarts itself the instant a session ends, and the console's `~/.profile` starts the emulator. So when the guest powers off, a fresh emulator is booting a second later, and anything arriving after that to stop the unit would kill a guest that had just begun writing.

`~/.profile` therefore waits on `/var/lib/previously/hold` rather than starting the emulator unconditionally:

```sh
while [ -f /var/lib/previously/hold ]; do sleep 2; done
exec cage -- /usr/bin/previous
```

Stopping writes that file, presses F10 and waits for the guest to go. Starting removes the file, and the waiting console notices within two seconds. Nothing is killed, nothing races, and the service never needs a privilege it could misuse.

**The warning before stopping is always shown and always says the same thing.** Previous exposes nothing about what the emulated machine is doing, so a warning that appeared only sometimes would teach the reader that its absence means safe, which cannot be known.

## Its own configuration

`/etc/previously/config.ini`, with defaults that work unconfigured, so the package installs into a running state rather than into a file to edit. `packaging/config.ini` is that file with every default written out.

## The interface

`web/` holds the same custom elements the draft in `../design/` is built from: `nx-window`, `nx-menu`, `nx-dock`, `nx-scroller`, `nx-shelf`, `nx-thing`, `nx-ask`.

A thing with a `value` can be lifted and carried, and a window with `drop` takes what lands on it. Both raise `nx-choose` carrying that value, so double clicking a thing and dragging it somewhere mean the same to whoever answers, and a page answers once. They are split into files here rather than baked into one page, and the pictures are files rather than data URIs.

The stylesheet and the kit are taken from the draft rather than written again, so a change to the look happens in one place. `../design/extract.py` says where every picture came from.

## Installing it on the Pi

```bash
sudo cp -r previously web /usr/lib/previously/
sudo cp packaging/config.ini /etc/previously/
sudo cp packaging/previously.service /etc/systemd/system/
sudo systemctl enable --now previously
```

This is the hand version. The package in #9 replaces it.
