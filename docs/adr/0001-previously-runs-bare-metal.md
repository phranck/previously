# Previously runs bare metal, on our fork of BMNeXT

Previously becomes a device that people buy, so what matters most is that nothing beneath the emulator needs maintenance. On a Raspberry Pi 4 or 5 it therefore runs without Linux, on our fork of BMNeXT, which runs Previous on the Circle bare metal environment. A kernel of about 3.5 MB on a FAT card replaces a Linux image with a writable root, and with it the layer that #572, #617 and #619 came from.

## Consequences

- The admin's backend is rewritten in C++ ([0005](0005-admin-keeps-its-interface-and-api.md)), and the device has no shell to debug with.
- The Linux edition gets no new features. Its open work, such as #577, is on hold.
- The measurements behind the move are in #768.
