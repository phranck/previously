# The web admin tool

A small service on the Pi that shows what the emulator is set to, from a browser on the home network. It is a more comfortable way to reach what Previous already offers behind F12, and nothing beyond that: no port is forwarded to it and nothing publishes it.

## Running it

```bash
make run          # in the foreground, on port 8088
make check        # lint and tests, which is what a commit needs
```

Nothing is fetched. Everything runs on what Debian ships: `python3`, `python3-pytest` and `python3-flake8`.

## What is in here

| | |
|---|---|
| `previously/settings.py` | What the service itself is configured with |
| `previously/config.py` | Reading `previous.cfg`, and knowing what its values mean |
| `previously/kiosk.py` | Everything asked of systemd, and the whole privilege surface |
| `previously/server.py` | Which addresses exist and what answers them |
| `web/` | What the browser gets |
| `packaging/` | The unit and the default configuration |

`kiosk.py` is one module because it is the whole privilege surface: reviewing what this tool may do to the machine means reading that one file.

## What anybody on the network can reach

**Reading is open.** Anything on the same network can see which machine is configured, how much memory it has, which disk it boots and whether it is running. That is deliberate: knowing the Pi is set up as a NeXTcube costs nothing.

**Changing anything needs a token.** Writing a configuration, stopping the emulator, opening a shell: all of it is refused without one. Sitting at the machine and pressing F12 needs physical access to it. Being on the network does not, and that difference is what the token answers.

The token is made on first start, lives in `/var/lib/previously/token` readable by the service alone, and is read once over SSH and typed into the interface, which keeps it. It is never in this repository, never in a URL and never in a log line.

**There is no TLS, and that is a decision rather than an omission.** This tool is not meant to be reachable from the internet: no port is forwarded to it and nothing publishes it. On the home network the token stops an accident and a bored device; it does not stop somebody who is already on that network and reading traffic. Saying otherwise would be a security claim that is not true, which is worse than none. #12 has what it would take if that ever changes.

## The addresses

| | |
|---|---|
| `GET /api/health` | Its version, and whether it can read `previous.cfg` |
| `GET /api/status` | What the machine is set to, and whether the kiosk runs |
| `GET /api/token` | Whether the token this request carried is the right one |
| `POST /*` | Refused without the token. Nothing is routed here yet |

Nothing writes yet. Every route reads, and every POST is checked before it is looked at.

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
