"""The emulator's process, and the keyboard this service reaches it through.

Every key this service sends goes through one virtual keyboard, a device the
kernel makes through /dev/uinput. The compositor reads it like any keyboard
plugged into the Pi, and so would SDL with no compositor at all, so nothing
here depends on an X server or on which way Previous draws.

The device is made once and kept for as long as the service runs, because
the compositor needs a moment to take a new keyboard in and a key sent before
then reaches nobody.

A key goes only to a running emulator. The keyboard belongs to the whole
board: with no compositor holding it, its keys reach the text console on tty1,
where the login shell that starts the emulator is waiting.
"""

import fcntl
import os
import struct
import subprocess
import threading
import time

#: What Previous calls its process. Whether it is running is the only honest
#: signal that the guest has finished shutting down, because the unit stays
#: active either way: it holds a login shell, not the emulator.
PROCESS = "previous"

#: How long to wait for pgrep. It answers at once or not at all.
TIMEOUT_SECONDS = 5

#: Where the kernel makes virtual input devices. The package's udev rule gives
#: it to the input group, and the service runs with that group.
UINPUT = "/dev/uinput"

#: The keys this service sends, by the names it uses for them, with their codes
#: from the kernel's linux/input-event-codes.h as Raspberry Pi OS trixie ships
#: it. The keyboard is made able to send these and nothing else.
KEYS = {"F10": 68, "Return": 28, "ctrl": 29, "alt": 56, "q": 16, "g": 34}

#: Event types and the one code of the synchronizing event, from the same
#: header, and the bus a virtual device names, from linux/input.h.
EV_SYN = 0x00
EV_KEY = 0x01
SYN_REPORT = 0
BUS_VIRTUAL = 0x06

#: What the keyboard calls itself, which is what `libinput list-devices` and
#: the compositor's log show.
NAME = b"Previously keyboard"

#: struct uinput_setup from linux/uinput.h: a struct input_id of four u16, a
#: name of UINPUT_MAX_NAME_SIZE characters, and a u32 for force feedback.
SETUP = struct.Struct("=4H80sI")

#: struct input_event from linux/input.h: a struct timeval of two longs, which
#: the kernel fills in itself, then a u16 type, a u16 code and an s32 value.
EVENT = struct.Struct("@llHHi")


def _ioctl(number, size=0):
    """@returns int, a request on the letter U as linux/uinput.h builds it with
    _IO where nothing is passed and _IOW where `size` bytes are written."""
    write = 1 if size else 0
    return (write << 30) | (size << 16) | (ord("U") << 8) | number


UI_DEV_CREATE = _ioctl(1)
UI_DEV_SETUP = _ioctl(3, SETUP.size)
UI_SET_EVBIT = _ioctl(100, struct.calcsize("i"))
UI_SET_KEYBIT = _ioctl(101, struct.calcsize("i"))

#: How long the compositor takes to take a new keyboard in, before the first
#: key is sent. Measured under cage on 23.10.2026: a key sent at once was lost
#: on both Pis, one after 0.05 s arrived on a Pi 5 and not on a Pi 4, and one
#: after 0.1 s arrived on both. The keyboard is made once, so the margin costs
#: one wait per start of the service.
SETTLE_SECONDS = 1.0

#: How long a key is held down.
HOLD_SECONDS = 0.02

#: The keyboard once it is made, as an open file descriptor, and what keeps two
#: requests answered on two threads from making it twice or interleaving keys.
_DEVICE = None
_LOCK = threading.Lock()


def pid():
    """Which process is the emulator.

    @returns int, or None where it is not running or pgrep cannot say.
    """
    try:
        result = subprocess.run(["pgrep", "-x", PROCESS], capture_output=True,
                                text=True, timeout=TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    first = result.stdout.split()
    return int(first[0]) if first and first[0].isdigit() else None


def press(keys):
    """Sends a key or a shortcut to the emulator.

    @param keys - Names from KEYS joined by "+", such as "F10" or "ctrl+alt+g".
    @returns bool, whether it was sent. False for a name this keyboard does not
      have, where no emulator is running, and where the keyboard cannot be made.

    Pressed in the order given and let go in the reverse order, as a person
    holds the modifiers first.
    """
    codes = [KEYS.get(name) for name in keys.split("+")]
    if None in codes or pid() is None:
        return False
    with _LOCK:
        device = _keyboard()
        if device is None:
            return False
        try:
            for code in codes:
                _send(device, code, 1)
            time.sleep(HOLD_SECONDS)
            for code in reversed(codes):
                _send(device, code, 0)
        except OSError:
            _forget()
            return False
    return True


def _keyboard():
    """The virtual keyboard, made on first use.

    @returns int, its file descriptor, or None where /dev/uinput cannot be
      opened or will not make the device.
    """
    global _DEVICE
    if _DEVICE is not None:
        return _DEVICE
    try:
        device = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        fcntl.ioctl(device, UI_SET_EVBIT, EV_KEY)
        for code in KEYS.values():
            fcntl.ioctl(device, UI_SET_KEYBIT, code)
        fcntl.ioctl(device, UI_DEV_SETUP, SETUP.pack(BUS_VIRTUAL, 0, 0, 1, NAME, 0))
        fcntl.ioctl(device, UI_DEV_CREATE)
    except OSError:
        os.close(device)
        return None
    time.sleep(SETTLE_SECONDS)
    _DEVICE = device
    return device


def _send(device, code, value):
    """Writes one key going down (1) or up (0), and the event that ends it."""
    os.write(device, EVENT.pack(0, 0, EV_KEY, code, value))
    os.write(device, EVENT.pack(0, 0, EV_SYN, SYN_REPORT, 0))


def _forget():
    """Lets a keyboard that failed go, so the next key makes a fresh one."""
    global _DEVICE
    if _DEVICE is not None:
        try:
            os.close(_DEVICE)
        except OSError:
            pass
    _DEVICE = None
