"""The web admin tool for a Raspberry Pi that boots into NeXTSTEP.

One module per job:

    settings.py   what the service itself is configured with
    config.py     reading and writing the emulator's configuration
    machines.py   which machines exist, and what each one is in the file
    change.py     changing the machine without leaving it unable to start
    kiosk.py      everything this tool does to the machine, in one file
    pi.py         what the board underneath is doing
    token.py      the one secret, and what a request may do without it
    server.py     which addresses exist and what answers them
"""
