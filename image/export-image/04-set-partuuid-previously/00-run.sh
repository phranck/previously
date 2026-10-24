#!/bin/bash -e

# The setup keeps a copy of cmdline.txt from before it made the boot quiet,
# and the remove job puts that copy back. pi-gen's 04-set-partuuid, which runs
# just before this, names the root partition in cmdline.txt alone, so the copy
# still says ROOTDEV and would not boot. This names it there as well, the way
# cmdline.txt now does. The workflow puts this beside pi-gen's own steps.

backup="${ROOTFS_DIR}/boot/firmware/cmdline.txt.previously.backup"
if [ -f "${backup}" ]; then
	root="$(grep -o 'root=[^ ]*' "${ROOTFS_DIR}/boot/firmware/cmdline.txt")"
	sed -i "s|root=ROOTDEV|${root}|" "${backup}"
fi
