#!/bin/bash -e

# Starts from what Stage 2 left, which is Raspberry Pi OS Lite.
if [ ! -d "${ROOTFS_DIR}" ]; then
	copy_previous
fi
