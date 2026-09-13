"""The web admin tool for a Raspberry Pi that boots into NeXTSTEP.

One module per job:

    settings.py   what the service itself is configured with
    config.py     reading the emulator's configuration
    kiosk.py      everything asked of systemd, and the whole privilege surface
    server.py     which addresses exist and what answers them
"""
