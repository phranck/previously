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
| `previously/config.py` | Reading `previous.cfg`, and knowing what its values mean |
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

The token is made on first start, lives in `/var/lib/previously/token` readable by the service alone, and is read once over SSH and typed into the interface, which keeps it. It is never in this repository, never in a URL and never in a log line.

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

Every POST is checked for the token before anything looks at what was sent.

## Switching the machine on and off

**Stopping means pressing the power button, not killing the emulator.** Previous maps the NeXT power button to F10, and pressing it starts an orderly shutdown inside NeXTSTEP, exactly as Power Off in the Logout panel does. Taking the emulator away instead leaves the guest's file system dirty, and it runs a check on the way back up. The key is sent with `wtype` through the Wayland protocol the kiosk's compositor implements.

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

`web/` holds the same custom elements the draft in `../design/` is built from: `nx-window`, `nx-menu`, `nx-dock`, `nx-scroller`, `nx-shelf`, `nx-thing`. They are split into files here rather than baked into one page, and the pictures are files rather than data URIs.

The stylesheet and the kit are taken from the draft rather than written again, so a change to the look happens in one place. `../design/extract.py` says where every picture came from.

## Installing it on the Pi

```bash
sudo cp -r previously web /usr/lib/previously/
sudo cp packaging/config.ini /etc/previously/
sudo cp packaging/previously.service /etc/systemd/system/
sudo systemctl enable --now previously
```

This is the hand version. The package in #9 replaces it.
