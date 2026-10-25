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
| +0x54 | (936 on turbo, 910 on 0x139, minus height) times row bytes | |

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

- The kernel's text console takes row length, height and frame buffer from its own `_km_coni` at `0x040b75fc`: `_km_clear_screen`, `_km_flip_cursor` and the left margin `_kminit` computes from the width. The 1120 at `_km_clear_screen+0x38` and at `_rtc_power_down+0x14` is the displacement of a `bsr.l`, not a screen size.
- The cursor is drawn by the kernel. `_evdispatch` calls the screen functions the gray driver registers in `FUN_04098b2a`, and they call the driver table `_st_sdsw`, whose first entry is the gray screen. Its routines that draw the cursor (`0x0409784a`) and take it away (`0x04097a2a`) step through rows of a fixed 70 longs, `moveq #$46,d5` at `0x040978aa` and `0x04097a44`, which is 1120 pixels. These two are the only fixed row lengths in the gray driver. At 1024 pixels the cursor came out sheared into dashes and a copy stayed at its first position, so the playground build sets both immediates to the configured width in longs once the kernel reads the display counts, after checking the words around them.
- `_km_drawrect` and `_km_eraserect` work in coordinates for 1120 by 832 and add half the difference to the record's width and height, so the kernel's boot panels sit centered in a screen of any size.
- The WindowServer has no screen constant: its only 1120 and 832 sit in `_MouseInit` as a fallback rectangle for a device without a window, and `_GrayInit+0x2bc` is an offset into `_graphicsNames`.

## The boot ROM

Rev 3.3 v74 keeps its console record in `mon_global` from offset 0x324, laid out like the kernel's record, and `restore_mg` at `0x01000686` finds `mon_global` at VBR plus 4. The gray console is filled by `0x0100bf9e` and the color console by `0x0100b9e6`, both from constants, so the ROM always draws for 1120 by 832, with rows of 280 bytes on turbo. Its blit at `0x01004440` places an image at `y * dspy_max_w + x`, but its layout is fixed: `0x010077a4` clears the panel's text area at x 550 to 640 and rows 340 to 440, and the animation tick at `0x0100680c` turns y around against a constant 832.

The kernel does not stop the ROM from drawing. `_vidStopAnimation` clears `MGF_ANIM_RUN` in `mon_global`, and between its own panels the kernel lets the ROM clear the screen and draw its "Loading from disk" panel again. In the 1120 by 832 reference that panel is back at 140 s, rows 308 to 483 and columns 340 to 779.

The playground build therefore moves every VRAM access by firmware code into the middle of the configured screen (`src/cpu/memory.c`). Firmware code is supervisor code below `0x02000000`. The parts of the firmware's picture that the configured screen does not show live in a shadow, so the ROM reads back what it wrote there. With those writes dropped, the ROM stopped right after power-on with a light gray screen. The ROM's message buffer at VRAM offset `0x3fe00`, set in `0x01000ec6`, lies past the picture and is not moved.

Booted at 1024 by 600 on the Mac, every grab matches the 1120 by 832 reference moved by 48 columns and 116 rows: the ROM's panel at rows 192 to 367 and columns 292 to 731, at 10 s and again at 140 s, and the kernel's panels at rows 212 to 387 and columns 356 to 667. Nothing is drawn outside the panels, and the desktop follows at 200 s.

## The NeXTdimension

`/usr/lib/NextStep/Displays/NeXTdimension.psdrvr/` holds `ND_MachDriver_reloc`, a loadable kernel server with the five entry points `_ND_init`, `_ND_signoff`, `_ND_port_death`, `_ND_msg` and `_ND_instance`; `reloc`, the WindowServer's display module, a relocatable object with the single symbol `_Start`; and `NDserver`, an m68k executable without symbols. The board's geometry lives in these and in the board's program, not in the TMC counts.
