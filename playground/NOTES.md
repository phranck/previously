# Screen geometry in NeXTSTEP 3.3 for m68k, as found in the binaries

Everything here comes from the next5 disk image of 2026-10-25, extracted with Previous's ditool, read with `macho68k.py` and Ghidra through `ghidra.sh`, and from Previous SVN trunk r1859 with its ROM Rev 3.3 v74. Addresses are the kernel's virtual addresses; `sdmach` maps its `__TEXT` segment at `0x04000000` from file offset 0, so a file offset is the address minus `0x04000000`.

## Which screen the kernel takes

`_m68k_init` sets `_machine_type` at `0x040b6e6c` from bits 12 to 15 of SCR1 at slot base plus `0x0200c000`. Where that says 4, a turbo machine, it takes them from the turbo's SCR1 at slot base plus `0x02200000` instead. Previous answers 4 for a turbo NeXTstation in gray, 5 for one in color and 8 for a turbo NeXTcube (`src/tmc.c`, `tmc_scr1_reset`). The non-turbo machines are 0 to 3, with 3 the NeXTstation Color, and on all of them `_dma_chip` at `0x040c4358` is 0x139.

The screen driver table `_st_sdsw` at `0x040b2e44` holds three screens of eleven functions each. The first of each is a probe on `_machine_type`, the second builds the screen record the WindowServer receives through `/dev/vid0`.

| Screen | Probe | Machine types | Record | Size from |
|---|---|---|---|---|
| Gray | `0x040975a8` | 0, 1, 2, 4, 8, and every other even turbo type | `0x040975ec` | TMC display counts on a turbo machine, constants on 0x139 |
| Color, turbo | `0x04097d6c` | 5, 9, and every other odd turbo type | `0x04097ef6` | TMC display counts |
| Color, NeXTstation Color | `0x04097d56` | 3 | `0x04097da2` | constants |

A turbo machine therefore takes its screen size from the TMC display counts in gray and in color alike. Only the NeXTstation Color and the non-turbo gray machines carry the size as constants.

## The three records

| Offset | Gray `0x040975ec` | Color turbo `0x04097ef6` | NeXTstation Color `0x04097da2` |
|---|---|---|---|
| +0x00 | 16 | 2 | 2 |
| +0x04 | row bytes, total width divided by 4 | row bytes, width times 2 | row bytes, 2304 |
| +0x08 | width | width | width, 1120 |
| +0x0c | total width | width | total width, 1152 |
| +0x10 | height | height | height, 832 |
| +0x40, +0x44 | frame buffer address | 0x0c000000 | 0x2c000000 |
| +0x48 | height times row bytes | width times height times 2 | 0x1d4000 |
| +0x4c, +0x50 | address plus +0x48 | address plus +0x48 | address with 0x1d4000 or'ed in |
| +0x54 | VRAM rows minus height, times row bytes | 0x200000 minus +0x48 | 78 rows times 2304 |

On a turbo machine the TMC registers at slot base plus `0x02200088` and `0x0220008c` give the size: width is the low twelve bits of the first times four, height the low twelve bits of the second. Previous emulates both in `src/tmc.c`, reset to 0x118 and 0x340, and the ROM writes them twice at boot, from `0x010003a4` and `0x0100c6b0`. The kernel never writes them.

+0x54 is the video memory behind the picture. Each record fixes how much video memory there is, so a picture taller or larger than that needs these values changed together with the memory Previous provides.

The constants a different size changes, by record:

| Address | Instruction | What it is |
|---|---|---|
| `0x0409762e` | `move.l #$460,d3` | gray on 0x139: width |
| `0x04097634` | `move.l #$480,d2` | gray on 0x139: total width |
| `0x0409763a` | `move.l #$340,d4` | gray on 0x139: height |
| `0x040976fc` | `move.l #$3a8,d0` | gray on a turbo: 936 VRAM rows |
| `0x0409770c` | `move.l #$38e,d0` | gray on 0x139: 910 VRAM rows |
| `0x04097fc6` | `move.l #$200000,d5` | color turbo: 2 MB of VRAM |
| `0x04097dc2` | `move.l #$900,d0` | NeXTstation Color: row bytes |
| `0x04097dcc` | `move.l #$460,8(a0)` | NeXTstation Color: width |
| `0x04097de2` | `move.l #$480,d0` | NeXTstation Color: total width |
| `0x04097dec` | `move.l #$340,$10(a0)` | NeXTstation Color: height |
| `0x04097e54` | `move.l #$1d4000,d0` | NeXTstation Color: +0x48 |
| `0x04097e7a` | `ori.l #$1d4000,d0` | NeXTstation Color: +0x50 |
| `0x04097eac` | `ori.l #$1d4000,d0` | NeXTstation Color: +0x4c |
| `0x04097ecc` to `0x04097ee0` | `moveq #$4e,d0`, then times 9 and shifted by 8 | NeXTstation Color: 78 rows times 2304 for +0x54, a computation rather than one value |

The turbo values in `0x04097da2` (`0x04097db4`, `0x04097dd4`, `0x04097e46`, `0x04097e82`, `0x04097eb4`, `0x04097ec2`, `0x04097ee2`) are never reached, because only machine type 3 takes that record.

## Other places the numbers appear

- The kernel's text console takes row length, height and frame buffer from its own `_km_coni` at `0x040b75fc`: `_km_clear_screen`, `_km_flip_cursor` and the left margin `_kminit` computes from the width. The 1120 at `_km_clear_screen+0x38` and at `_rtc_power_down+0x14` is the displacement of a `bsr.l`, not a screen size.
- The gray screen draws the cursor (`0x0409784a`) and takes it away (`0x04097a2a`) with a row length of its own in longs: `moveq #$46,d5` for the 70 longs of a turbo at `0x040978aa` and `0x04097a44`, and `moveq #$48,d5` for the 72 longs of 0x139 at `0x040978b8` and `0x04097a54`. At 1024 pixels on a turbo the cursor came out sheared into dashes and a copy stayed at its first position, until the playground build set the turbo pair to the configured width.
- The two color screens share their cursor and drawing functions, `0x04097fde` to `0x0409854e`. No row length, width or height appears in them as an immediate: `#$8c0` and `#$900` occur in the driver only in the record at `0x04097da2`, and their other hits in the kernel are parts of other instructions or values.
- `_km_drawrect` and `_km_eraserect` work in coordinates for 1120 by 832 and add half the difference to the record's width and height, so the kernel's boot panels sit centered in a screen of any size.
- The WindowServer has no screen constant: its only 1120 and 832 sit in `_MouseInit` as a fallback rectangle for a device without a window, and `_GrayInit+0x2bc` is an offset into `_graphicsNames`. Neither 2240, 2304, 0x1c7000 nor 0x1d4000 appears as a screen value. `_MPInitScreen` sizes its device state by the device's depth and bounds.

## The boot ROM

Rev 3.3 v74 keeps its console record in `mon_global` from offset 0x324, laid out like the kernel's record, and `restore_mg` at `0x01000686` finds `mon_global` at VBR plus 4. The ROM's own machine type is at `mon_global+0x3a8`, and `FUN_01000c9c` sets 0x194 to 0x139 for types 0 to 3 and 0x3ba to 1 for type 3 and the turbo types 4 to 11. Types 6, 7, 10 and 11 also have the secondary cache at `0x02210000`.

The gray console is filled by `0x0100bf9e` and the color console by `0x0100b9e6`, both from constants:

| | Gray, 0x139 | Gray, turbo | Color, 0x139 | Color, turbo |
|---|---|---|---|---|
| VRAM | `0x0B000000` | `0x0C000000` | `0x2C000000` | `0x0C000000` |
| Total width | 1152 | 1120 | 1152 | 1120 |
| Row bytes | 288 | 280 | 2304 | 2240 |
| Picture rows | 832 | 832 | 832 | 832 |
| VRAM rows | 910 | 936 | 910 | 936 |

288 by 910 and 280 by 936 are both 262080 bytes, just under the 256 KB of gray VRAM, and 2304 by 910 and 2240 by 936 are 2096640, just under the 2 MB of color VRAM. The ROM always draws for 1120 by 832. Its blit at `0x01004440` places an image at `y * dspy_max_w + x`, but its layout is fixed: `0x010077a4` clears the panel's text area at x 550 to 640 and rows 340 to 440, and the animation tick at `0x0100680c` turns y around against a constant 832.

The rows behind the picture are the firmware's own memory during the power-on tests. `FUN_01000ec6` keeps its message buffer at `mon_global+0x320`, at VRAM offset `0x3fe00` on the gray machines, and records VRAM plus 0x40000 as the end of its memory in `mon_global+0xe8` and `+0xec`. The color machines and the turbo color types keep the buffer in the page of the firmware's stack instead and test the VRAM there. Once main memory is known, the same function moves `mon_global` and the stack into it. The kernel reads nothing of this: of `mon_global` it takes the boot record, the ROM's version at `0x30a`, `0x30c` and `0x312`, and the console's slot at `0x34c` and `0x34d`, and it keeps its own message buffer `_pmsgbuf` in main memory (`_m68k_init`).

The kernel does not stop the ROM from drawing. `_vidStopAnimation` clears `MGF_ANIM_RUN` in `mon_global`, and between its own panels the kernel lets the ROM clear the screen and draw its "Loading from disk" panel again. In the 1120 by 832 reference that panel is back at 140 s, rows 308 to 483 and columns 340 to 779.

The playground build therefore moves every VRAM access by firmware code into the middle of the configured screen (`src/cpu/memory.c`). Firmware code is supervisor code below `0x02000000`. The parts of the firmware's picture that the configured screen does not show live in a shadow, so the ROM reads back what it wrote there. With those writes dropped, the ROM stopped right after power-on with a light gray screen. The playground leaves the rows behind the firmware's picture where they are, which a larger picture would cover. Since nothing but the firmware uses them, they belong in the shadow too.

Booted at 1024 by 600 on the Mac, every grab matches the 1120 by 832 reference moved by 48 columns and 116 rows: the ROM's panel at rows 192 to 367 and columns 292 to 731, at 10 s and again at 140 s, and the kernel's panels at rows 212 to 387 and columns 356 to 667. Nothing is drawn outside the panels, and the desktop follows at 200 s.

## The NeXTdimension

`/usr/lib/NextStep/Displays/NeXTdimension.psdrvr/` holds `ND_MachDriver_reloc`, a loadable kernel server with the five entry points `_ND_init`, `_ND_signoff`, `_ND_port_death`, `_ND_msg` and `_ND_instance`; `reloc`, the WindowServer's display module, a relocatable object with the single symbol `_Start`; and `NDserver`, an m68k executable without symbols. The board's geometry lives in these and in the board's program, not in the TMC counts.
