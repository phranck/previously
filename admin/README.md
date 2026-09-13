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

**It speaks plain HTTP, and for a tool on a home network that is the sensible way to run it.** The token crosses that network in the open, so somebody already inside it and reading traffic can take it. On a network you control that is not the threat the token is for: it is there so that nothing reaches this by accident, and so that a device with no business writing a configuration cannot.

HTTPS is available for anybody whose situation is different, and the section below says what it takes. It is off unless a certificate is named, and nothing needs it.

## HTTPS, for anybody who wants it

**Not needed on a home network, and off unless configured.** Two paths in `config.ini` name a certificate and a key, and until they do the service speaks HTTP.

It is worth switching on where the network is not yours to trust: a shared flat, an office, a machine reached over a VPN from elsewhere. Exposing this to the internet is a different question that a certificate does not answer on its own.

Which certificate a machine can have turns on one thing: **is its name one that the rest of the internet can look up?**

### A name only your house knows

`raspberrypi.local`, `pi.fritz.box` and `192.168.1.50` mean something inside one house and nothing outside it. There is nothing for a public authority to verify, so none of them issues anything. That is the trust system working rather than a gap in it.

Such a machine signs a certificate for itself:

```bash
sudo /usr/lib/previously/self-signed-certificate.sh
```

It reads every name the machine answers to and issues for all of them: the short name, the same name under `.local`, whatever the router's domain makes of it, and each address. Nothing is written down in advance, so it works on a machine called anything. Extra names go in as arguments.

```ini
[service]
certificate = /etc/previously/tls/fullchain.pem
private_key = /etc/previously/tls/privkey.pem
```

**The trade.** The connection is encrypted. The certificate proves nothing about who is answering, because nobody vouched for it, so the browser warns the first time on every device and somebody has to accept it. That warning is the cost, it recurs on each new device, and on a network you control it tells you nothing you did not already know. It lasts 825 days, which is the longest macOS and iOS accept from anybody.

### A name the internet can look up

Then there is no warning, and the machine still never has to be reachable from outside.

Point a name you control at its address on the home network:

```
cube.example.org.   A   10.0.0.135
```

The record is public and answers with a private address. Inside the house it resolves and works; everywhere else it points into a network the caller is not on.

Proving the name by answering on port 80 from outside cannot work here. The DNS-01 challenge proves it through a DNS record instead, somewhere Let's Encrypt can already reach. Their documentation names this as the reason to use it: it validates "domain names whose webservers aren't exposed to the public internet" ([Challenge Types](https://letsencrypt.org/docs/challenge-types/)).

```bash
sudo certbot certonly --preferred-challenges dns \
    --dns-<your-provider> --dns-<your-provider>-credentials /etc/letsencrypt/dns.ini \
    -d cube.example.org \
    --deploy-hook /usr/lib/previously/certificate-hook.sh
```

`certificate-hook.sh` copies the pair into `/etc/previously/tls/` owned by the service user and restarts the service, at every renewal, so nothing has to be remembered every sixty days. Name the same two files as above, with `fullchain.pem` rather than `cert.pem`, because it carries the intermediate certificate browsers need.

**If your DNS provider has no API**, delegate only the challenge record to a zone that does, once, by hand:

```
_acme-challenge.cube.example.org.   CNAME   cube.acme.example-with-an-api.org.
```

Let's Encrypt follows that CNAME, so the client only ever needs a credential for the second zone, and that zone holds nothing but challenge records. They support this explicitly: "you can use CNAME records or NS records to delegate answering the challenge to other DNS zones" ([Challenge Types](https://letsencrypt.org/docs/challenge-types/)).

Do not put an account password on the machine to avoid this. Some ACME clients offer providers that log into a customer portal and drive its web forms, which puts credentials for everything that account can reach on a Pi, for the sake of one TXT record.

### A reverse proxy in front

Leave both paths empty. The service speaks HTTP and the proxy holds the certificate.

### Dropping the port number

`packaging/previously-443.conf` lets the service bind 443, so the address carries no port. It grants one capability and restricts it to that one port.

### What none of it does

A certificate says nobody is reading along. It does not say who may change something, which is the token's job, and it does not make this safe to expose to the internet.

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
