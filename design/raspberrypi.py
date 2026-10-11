#!/usr/bin/env python3
"""Fetches the Raspberry Pi logo and writes the picture the Info window wears.

The logo is Raspberry Pi Ltd's registered trademark. Their trademark rules ask
that only the assets they publish on raspberrypi.com are used, so this takes
the color symbol from the page that states those rules, checks it against the
sum it was read at, and writes it at the size of a NeXTSTEP icon. Whatever
shows it says that Raspberry Pi is a trademark of Raspberry Pi Ltd, which those
rules ask of every use.

    python3 raspberrypi.py
"""

import io
import pathlib

from PIL import Image

from fetched import download

HERE = pathlib.Path(__file__).parent
#: build.py says why the pictures live there and nowhere else.
PARTS = HERE.parent / "admin" / "web" / "parts"

#: The color symbol as raspberrypi.com/trademark-rules/ shows it, 591 by 592
#: pixels, and its sum as it was read on 11 October 2026.
LOGO = ("https://www.raspberrypi.com/app/uploads/2022/02/"
        "COLOUR-Raspberry-Pi-Symbol-Registered.png")
LOGO_SUM = "24209629d7d89fbe57408c83a87c3e7b98a234f0900cddfdf575193ef7e4a93c"

#: The site answers a request that names no browser with a challenge page
#: rather than with the file.
HEADERS = {"User-Agent": "Mozilla/5.0"}

#: The size NeXTSTEP drew an icon at, which is `--icon` in the kit.
ICON = 48


def main():
    logo = Image.open(io.BytesIO(download(LOGO, LOGO_SUM, HEADERS))).convert("RGBA")
    # Cut to the symbol first, because the file carries a wide transparent
    # margin and NeXTSTEP's own icons fill their square to the edge. Then
    # scaled down whole, keeping its shape, and centered on the square.
    logo = logo.crop(logo.getbbox())
    logo.thumbnail((ICON, ICON), Image.Resampling.LANCZOS)
    icon = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
    icon.paste(logo, ((ICON - logo.width) // 2, (ICON - logo.height) // 2), logo)
    PARTS.mkdir(exist_ok=True)
    icon.save(PARTS / "raspberry-pi.png", optimize=True)
    print("wrote raspberry-pi.png, %d by %d, into %s" % (ICON, ICON, PARTS))


if __name__ == "__main__":
    main()
