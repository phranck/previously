"""The web admin tool for a Raspberry Pi that boots into NeXTSTEP.

One module per job:

    settings.py   what the service itself is configured with
    config.py     reading and writing the emulator's configuration
    machines.py   which machines exist, and the rules Previous keeps for them
    saved.py      the configurations somebody saved, and what a name may be
    files.py      the places this tool shows, which are on no disk
    change.py     changing the machine without leaving it unable to start
    kiosk.py      everything this tool does to the machine, in one file
    screen.py     reading the emulated screen, and pressing its keys
    grab.py       taking a picture of that screen and keeping it
    terminal.py   the shell session behind the Terminal window
    websocket.py  the protocol that session travels over
    pi.py         what the board underneath is doing
    token.py      the one secret, and what a request may do without it
    server.py     which addresses exist and what answers them
    answers.py    how the service names what happened, so the browser can say it
"""
