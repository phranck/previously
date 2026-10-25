# Screen geometry in NeXTSTEP 3.3 for m68k, as found in the binaries

Everything here comes from the next5 disk image of 2026-10-25, extracted with Previous's ditool, read with `macho68k.py`. Addresses are the kernel's virtual addresses; `sdmach` maps its `__TEXT` segment at `0x04000000` from file offset 0, so a file offset is the address minus `0x04000000`.

## The kernel's screen record

Two functions right after `_vidInterruptDisable` fill a record of at least 0x58 bytes that the WindowServer later receives through `/dev/vid0`. The machine type is told apart by `_dma_chip` at `0x040c4358`: the value 0x139 is the machine without the turbo chip, everything else is a turbo machine.

| Offset | Gray record (function at 0x040975ec) | Color record (function at 0x04097da2) |
|---|---|---|
| +0x00 | 16 | 2 |
| +0x04 | row bytes, total width divided by 4 | row bytes, 2304 on 0x139, 2240 on turbo |
| +0x08 | width | width, 1120 |
| +0x0c | total width | total width, 1152 on 0x139, 1120 on turbo |
| +0x10 | height | height, 832 |
| +0x14 | 0 | 2 |
| +0x18 | 0 | 0xfff0fff0, white |
| +0x1c | 0x55555555, light gray pattern | 0xaaa0aaa0, light gray |
| +0x20 | 0xaaaaaaaa, dark gray pattern | 0x55505550, dark gray |
| +0x24 | 0xffffffff | 0, black |
| +0x40 | frame buffer address | frame buffer address, 0x2c000000 on 0x139, 0x0c000000 on turbo |
| +0x44 | frame buffer address again | the same |
| +0x48 | height times row bytes | 0x1d4000 on 0x139, 0x1c7000 on turbo |
| +0x4c, +0x50 | address plus size | |
| +0x54 | (910 on turbo, 936 otherwise, minus height) times row bytes | |

On 0x139 the gray record uses the constants 1120, 1152 and 832. On a turbo machine it reads the TMC registers at slot base plus `0x02200088` and `0x0220008c`: width and total width are the low twelve bits of the first times four, height is the low twelve bits of the second. Previous emulates both registers in `src/tmc.c`, reset to 0x118 and 0x340, and the ROM writes them twice at boot, from `0x010003a4` and `0x0100c6b0`. The kernel never writes them and reads them only from `0x04097618` and `0x0409762a`, which is the record being built.

The color record keeps constants on both machine types. For a color screen of another size these immediates change, all in the function at 0x04097da2, turbo values shown:

| Address | Instruction | Value for 1024 by 600 |
|---|---|---|
| 0x04097db4 | `move.l #0x8c0,d0`, row bytes | 0x800 |
| 0x04097dcc | `move.l #0x460,8(a0)`, width | 0x400 |
| 0x04097dd4 | `move.l #0x460,d0`, total width | 0x400 |
| 0x04097dec | `move.l #0x340,0x10(a0)`, height | 0x258 |
| 0x04097e46 | `move.l #0x1c7000,d0`, frame buffer size | 0x12c000 |

The 0x139 variants at 0x04097dc2 (0x900), 0x04097de2 (0x480) and 0x04097e54 (0x1d4000) stay as they are for a turbo machine, because the branch before each of them skips them.

## Other places the numbers appear

- `_km_clear_screen+0x38` holds a 1120 of its own, the kernel console's clear width.
- `_rtc_power_down+0x14` holds a 1120.
- The WindowServer has no screen constant: its only 1120 and 832 sit in `_MouseInit` as a fallback rectangle for a device without a window, and `_GrayInit+0x2bc` is an offset into `_graphicsNames`.

## The NeXTdimension

`/usr/lib/NextStep/Displays/NeXTdimension.psdrvr/` holds `ND_MachDriver_reloc`, a loadable kernel server with the five entry points `_ND_init`, `_ND_signoff`, `_ND_port_death`, `_ND_msg` and `_ND_instance`; `reloc`, the WindowServer's display module, a relocatable object with the single symbol `_Start`; and `NDserver`, an m68k executable without symbols. The board's geometry lives in these and in the board's program, not in the TMC counts.
