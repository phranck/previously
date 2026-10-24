#!/bin/bash -e

# Puts Previously on the card the way install.sh does: the package, then the
# setup's install job with NeXTSTEP 3.3, through the same code. The package
# runs the tool as the first user, pi until Raspberry Pi Imager renames them
# at the first boot, and previously-owner.service follows that rename. The
# workflow puts the package it built into files/ first.

install -m 644 files/previously_all.deb "${ROOTFS_DIR}/root/previously_all.deb"

on_chroot << EOF
apt-get install -y /root/previously_all.deb
rm /root/previously_all.deb
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/usr/lib/previously python3 -m previously.setup install nextstep-3.3
EOF
