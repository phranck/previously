<div align="center">

[![release](https://img.shields.io/github/v/release/phranck/previously?style=flat&color=e53935&label=release)](https://github.com/phranck/previously/releases)
[![build](https://img.shields.io/github/actions/workflow/status/phranck/previously/release.yml?style=flat&color=fb8c00&label=build)](https://github.com/phranck/previously/actions)
[![license](https://img.shields.io/github/license/phranck/previously?style=flat&color=f9a825)](https://layered.mit-license.org)
[![last commit](https://img.shields.io/github/last-commit/phranck/previously?style=flat&color=43a047)](https://github.com/phranck/previously/commits/main)
[![code size](https://img.shields.io/github/languages/code-size/phranck/previously?style=flat&color=1e88e5)](https://github.com/phranck/previously)
[![stars](https://img.shields.io/github/stars/phranck/previously?style=flat&color=8e24aa)](https://github.com/phranck/previously)

<img src="https://previous.li/site/shots/readme-hero.png" alt="A gray circuit board and the NeXT cube rushing at each other, each trailing a smear, with a pressed Merge button and the cursor that pressed it between them, over the name Previously and the line about a Raspberry Pi that boots directly into NeXTSTEP." width="860">

</div>

# Previously

A Raspberry Pi 4 or 5 that starts straight into NeXTSTEP. No desktop behind it, no login to get past, nothing on the screen but the gray NeXT panel. The emulator underneath is [Previous](https://previous.nextcommunity.net/), and the machine it pretends to be is a NeXTcube Turbo, one of eleven it can be.

A ready image or one line sets all of it up, and afterwards a web admin takes over that looks like the machine it configures.

## Installing it

There are two ways, and both end in the same machine.

**Write the ready image** to a card or a USB stick of 8 GB or more with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2, started with Previously's list:

```bash
open -a "Raspberry Pi Imager" --args --repo https://github.com/phranck/previously/releases/latest/download/os-list.json   # macOS
rpi-imager --repo https://github.com/phranck/previously/releases/latest/download/os-list.json                           # Linux
```

Choose your Raspberry Pi 4 or 5 and Previously, then set a user name, a hostname, a password and the Wi-Fi as you would for Raspberry Pi OS. Any names will do. The Pi starts straight into NeXTSTEP, and the admin answers at `http://<hostname>.local:8810`.

**Or install it on Raspberry Pi OS Lite**, 64 bit, based on Debian 13, on a Raspberry Pi 4 or 5. On the Pi, over SSH:

```bash
curl -fsSL https://previous.li/install.sh | bash
```

That is the whole of it. It installs the admin tool, then the emulator, a NeXTSTEP 3.3 disk, the console and the sound, and shows each step as it runs. At the end NeXTSTEP starts on the Pi's screen, and the script says where the admin is, which is `http://<your-pi>.local:8810`. Open it, choose a password, and that is what it asks for whenever something changes the machine.

A step that fails puts back what it changed. The Installer window in the admin then says what went wrong and can try again.

## The admin

Machines, drives and displays are things you pick rather than values you type. Complete configurations move by drag and drop, and any of them can be changed and kept as your own. It answers on the network, so the Pi never needs a keyboard of its own. Its Activity Monitor shows what every core of the Pi is doing as a row of LEDs, twice a second.

The icons are the original files out of a NeXTSTEP 3.3 disk image, the window buttons are cut pixel for pixel out of a screenshot of the running system, and the grays, edges and rasters are read off that screenshot. What NeXTSTEP had no picture of, such as the icon of a PNG file or the circuit boards, is drawn to match.

## More

- [previous.li](https://previous.li/) is the page this installs from.
- [Running it](docs/running-it.md) covers the rest: what the script touches, how to check the result, how to update the emulator and the admin, and how to get back into a machine whose screen now belongs to a NeXT.

## Thanks

To Andreas Grabher and everyone on [Previous](https://previous.nextcommunity.net/), without whom none of this would run at all.

NeXT, NeXTSTEP, OPENSTEP and the NeXT cube logo are registered trademarks of Apple Computer, Inc. Raspberry Pi is a trademark of Raspberry Pi Ltd. Neither of them has anything to do with this project, and neither the marks nor the icons taken from a NeXTSTEP disk image are covered by the license below.

## License

This repository has been published under the [MIT](https://layered.mit-license.org) license.
