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
| `packaging/` | The unit, the default configuration and the renewal hook |

`kiosk.py` is one module because it is the whole privilege surface: reviewing what this tool may do to the machine means reading that one file.

## What anybody on the network can reach

**Reading is open.** Anything on the same network can see which machine is configured, how much memory it has, which disk it boots and whether it is running. That is deliberate: knowing the Pi is set up as a NeXTcube costs nothing.

**Changing anything needs a token.** Writing a configuration, stopping the emulator, opening a shell: all of it is refused without one. Sitting at the machine and pressing F12 needs physical access to it. Being on the network does not, and that difference is what the token answers.

The token is made on first start, lives in `/var/lib/previously/token` readable by the service alone, and is read once over SSH and typed into the interface, which keeps it. It is never in this repository, never in a URL and never in a log line.

**HTTPS is available and off until a certificate is configured.** Without one the token crosses the home network in the clear, where anybody already on that network can read it. With one they cannot. Nothing about this makes the tool safe to expose to the internet, and nothing here should be read as an invitation to forward a port to it.

The next section says how to get a certificate for a machine that the internet cannot reach.

## HTTPS with a Let's Encrypt certificate

The service reads a certificate and a key from two paths and knows nothing else about them. Getting one is the operator's job, and how it is done depends on who runs the DNS, so this section describes the route rather than one provider's buttons.

### Why the usual route does not work here

Most guides prove control of a name by answering a request on port 80 from the outside. That is the HTTP-01 challenge, and it cannot work for a machine on a home network with nothing forwarded to it.

The DNS-01 challenge proves the same thing by putting a value in DNS, which is a place Let's Encrypt can already reach. Their own documentation names this as the reason to use it: it validates "domain names whose webservers aren't exposed to the public internet" ([Let's Encrypt, Challenge Types](https://letsencrypt.org/docs/challenge-types/)). Nothing about the Pi has to be reachable from anywhere.

### The machine needs a real name

`cube.local` can never carry a certificate. `.local` belongs to multicast DNS and no public authority issues for it, so this is a wall rather than a difficulty.

Give the machine a name under a domain you own, say `cube.example.org`, with an `A` record pointing at its address on the home network:

```
cube.example.org.   A   10.0.0.135
```

That record is public and answers with a private address, which is fine. On the home network it resolves and works. Everywhere else it points into a network the caller is not on, so nothing answers. What it does publish is which private range you use, which is not worth hiding.

### Getting the certificate

Whichever ACME client you prefer, the shape is the same: prove the name over DNS, then hand the result to the hook.

```bash
sudo certbot certonly --preferred-challenges dns \
    --dns-<your-provider> --dns-<your-provider>-credentials /etc/letsencrypt/dns.ini \
    -d cube.example.org \
    --deploy-hook /usr/lib/previously/certificate-hook.sh
```

`certificate-hook.sh` copies the pair into `/etc/previously/tls/`, owned by the service user, and restarts the service. It runs again at every renewal, so nothing has to be remembered every sixty days.

Then name them and restart:

```ini
[service]
certificate = /etc/previously/tls/fullchain.pem
private_key = /etc/previously/tls/privkey.pem
```

`fullchain.pem` rather than `cert.pem`, because it carries the intermediate certificate that browsers need.

### If your DNS provider has no API

This is the common case, and there is a way through that does not involve giving the Pi your registrar password. Delegate only the challenge record to a zone that does have an API, once, by hand:

```
_acme-challenge.cube.example.org.   CNAME   cube.acme.example-with-an-api.org.
```

Let's Encrypt follows that CNAME, so the ACME client only ever needs a credential for the second zone, and that zone holds nothing but challenge records. The registrar keeps your real domain and never needs an API at all. Let's Encrypt supports this explicitly: "you can use CNAME records or NS records to delegate answering the challenge to other DNS zones" ([Challenge Types](https://letsencrypt.org/docs/challenge-types/)).

Do not put an account password on the Pi to avoid this. Some ACME clients offer providers that log into a customer portal and drive its web forms, which means the machine holds credentials to everything that account can reach, for the sake of one TXT record.

### Dropping the port number

Optional. `packaging/previously-443.conf` lets the service bind 443, so the address is `https://cube.example.org` with nothing after it. It grants one capability and restricts it to that one port. Without it, `https://cube.example.org:8088` works just as well.

### What a certificate does not do

It encrypts the connection and proves the name. It does not make this tool safe to expose to the internet, and it does not replace the token. Both answer different questions: the certificate says nobody is reading along, and the token says who may change something.

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
sudo cp packaging/certificate-hook.sh /usr/lib/previously/
sudo cp packaging/previously.service /etc/systemd/system/
sudo systemctl enable --now previously
```

This is the hand version. The package in #9 replaces it.
