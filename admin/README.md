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
| `previously/token.py` | The one secret, and what a request may do without it |
| `previously/tls.py` | Presenting a certificate, where one is configured |
| `web/` | What the browser gets |
| `packaging/` | The unit, the default configuration and the certificate scripts |

`kiosk.py` is one module because it is the whole privilege surface: reviewing what this tool may do to the machine means reading that one file.

## What anybody on the network can reach

**Reading is open.** Anything on the same network can see which machine is configured, how much memory it has, which disk it boots and whether it is running. That is deliberate: knowing the Pi is set up as a NeXTcube costs nothing.

**Changing anything needs a token.** Writing a configuration, stopping the emulator, opening a shell: all of it is refused without one. Sitting at the machine and pressing F12 needs physical access to it. Being on the network does not, and that difference is what the token answers.

The token is made on first start, lives in `/var/lib/previously/token` readable by the service alone, and is read once over SSH and typed into the interface, which keeps it. It is never in this repository, never in a URL and never in a log line.

**HTTPS is available and off until a certificate is configured.** Without one the token crosses the home network in the clear, where anything on that network can read it. With one it cannot. Nothing about this makes the tool safe to expose to the internet, and nothing here should be read as an invitation to forward a port to it.

The next section says which certificate a machine can have, which depends on whether it has a name the internet can look up. Most do not, and there is an answer for those too.

## Reaching it over HTTPS

Without a certificate the service speaks plain HTTP, and the token crosses the network where anything on it can read the token. With one, it cannot.

Which certificate you can have depends on a single question: **is this machine's name one that the rest of the internet can look up?** For almost every Pi on a home network the answer is no, and the first section below is the one that applies.

### A Pi on a home network, which is most of them

A public certificate authority issues nothing for `raspberrypi.local`, `pi.fritz.box` or `192.168.1.50`. There is nothing for them to verify: those names mean something inside one house and nothing outside it. This is how the trust system works rather than a gap in it, so no amount of configuration gets round it.

What such a machine can have is a certificate it signs for itself:

```bash
sudo /usr/lib/previously/self-signed-certificate.sh
```

It reads every name the machine answers to and puts all of them in: the short name, the same name under `.local`, whatever the router's domain makes of it, and each address. Nothing is written down in advance, so this works on a machine called anything at all. Names it cannot discover are added as arguments.

Then name the two files and restart:

```ini
[service]
certificate = /etc/previously/tls/fullchain.pem
private_key = /etc/previously/tls/privkey.pem
```

**What you get and what you do not.** The connection is encrypted, so the token no longer crosses the network in the open. The certificate proves nothing about who is answering, because nobody vouched for it, so the browser warns the first time and the person who typed the address decides. That is the honest trade and it is worth knowing before accepting it: on a network you control, and an address you typed yourself, the warning is telling you something you already know.

The certificate lasts 825 days, which is the longest macOS and iOS accept from anybody. Run the command again to make a new one.

### If you happen to own a domain

Then the machine can have a certificate with no warning at all, from Let's Encrypt, and it still never has to be reachable from the internet.

Point a name you control at the machine's address on the home network:

```
cube.example.org.   A   10.0.0.135
```

That record is public and answers with a private address, which is fine. Inside the house it resolves and works; everywhere else it points into a network the caller is not on, so nothing answers.

The usual way of proving a name, answering a request on port 80 from outside, cannot work here. The DNS-01 challenge proves the same thing through a DNS record instead, which is somewhere Let's Encrypt can already reach. Their documentation names this as the reason to use it: it validates "domain names whose webservers aren't exposed to the public internet" ([Challenge Types](https://letsencrypt.org/docs/challenge-types/)).

```bash
sudo certbot certonly --preferred-challenges dns \
    --dns-<your-provider> --dns-<your-provider>-credentials /etc/letsencrypt/dns.ini \
    -d cube.example.org \
    --deploy-hook /usr/lib/previously/certificate-hook.sh
```

`certificate-hook.sh` copies the pair into `/etc/previously/tls/`, owned by the service user, and restarts the service. It runs again at every renewal, so nothing has to be remembered every sixty days. Name the same two files in `config.ini` as above, with `fullchain.pem` rather than `cert.pem`, because it carries the intermediate certificate that browsers need.

**If your DNS provider has no API**, delegate only the challenge record to a zone that does, once, by hand:

```
_acme-challenge.cube.example.org.   CNAME   cube.acme.example-with-an-api.org.
```

Let's Encrypt follows that CNAME, so the client only ever needs a credential for the second zone, and that zone holds nothing but challenge records. Let's Encrypt supports this explicitly: "you can use CNAME records or NS records to delegate answering the challenge to other DNS zones" ([Challenge Types](https://letsencrypt.org/docs/challenge-types/)).

Do not put an account password on the machine to avoid this. Some ACME clients offer providers that log into a customer portal and drive its web forms, which puts credentials for everything that account can reach on a Pi, for the sake of one TXT record.

### If you already run a reverse proxy

Leave both paths empty and put it in front as usual. The service speaks plain HTTP and the proxy holds the certificate.

### Dropping the port number

Optional, and it applies to any of the three. `packaging/previously-443.conf` lets the service bind 443, so the address carries no port. It grants one capability and restricts it to that one port. Without it, `:8088` over TLS works just as well.

### What no certificate does

None of this makes the tool safe to expose to the internet, and none of it replaces the token. A certificate says nobody is reading along. The token says who may change something.

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
sudo cp packaging/certificate-hook.sh packaging/self-signed-certificate.sh /usr/lib/previously/
sudo cp packaging/previously.service /etc/systemd/system/
sudo systemctl enable --now previously
```

This is the hand version. The package in #9 replaces it.
