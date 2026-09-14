# Design drafts for the web admin tool

Three one-page drafts of the interface that configures Previous from a browser, plus the tools that fetch the pictures one of them uses.

| File | What it is |
|---|---|
| `mockup-nextstep.html` | A NeXTSTEP workspace. Machines and disks are things you pick up and drop on one another. |
| `mockup-backplane.html` | The back of the cube. Changing the configuration means seating a card or fitting memory. |
| `mockup-console.html` | An instrument. It answers one question in five seconds: is the machine running? |

Open any of them in a browser. They need no server and no build step.

## Where the pictures come from

The NeXTSTEP draft draws nothing by hand. Its icons are the original files out of a NeXTSTEP 3.3 disk image, and its window buttons and dock marks are cut from a screenshot of the running system, because NeXTSTEP drew those in PostScript and they exist as no file at all.

Five tools do that work:

| Tool | What it does |
|---|---|
| `ufs.py` | Reads a NeXT UFS filesystem: 4.3BSD FFS, big endian, behind a `dlV3` disk label. |
| `nxtiff.py` | Decodes NeXT's TIFFs, which no current library reads: two bits per sample, alpha in its own plane, and a second copy of each picture at four bits per colour channel. |
| `extract.py` | Pulls the icons out of the image and the controls out of the screenshot, into `parts/`. |
| `bootpicture.py` | Cuts the machine out of a boot screen and makes an icon of it. |
| `build.py` | Bakes everything in `parts/` into the mockup as data URIs, so it stays one file. |

`parts/` is committed, so the draft works without running any of this. Run it again when a picture needs to change:

```bash
python3 extract.py ~/nextstep/NS33_2GB.dd screenshot.png
python3 build.py
```

`extract.py` needs two things that are not in this repository. The first is a NeXTSTEP 3.3 disk image, which the paper PAP-NXR-001 says where to get. The second is a screenshot of NeXTSTEP 3.3 at its own resolution of 1120 by 832, because the pixel bounds in `extract.py` are that screenshot's and nothing else will line up.

## The two machines

The pictures of the NeXTcube and the NeXTstation come from somewhere else again, because NeXTSTEP holds no drawing of either. The boot ROM does: whilst it tests the hardware it puts up a panel with the NeXT cube on the left and the machine on the right, and which machine that is follows from the configuration.

Previous can write the emulated framebuffer itself, which is what makes those pictures usable. Ctrl+Alt+G grabs it at the machine's own 1120 by 832 in NeXT's four greys, unscaled, and leaves `next_screen_NNN.png` in the directory the emulator was started in. Grabbing once a second through a boot catches the panel, and `bootpicture.py` finds the machine inside it and reduces it to an icon:

```bash
python3 bootpicture.py next_screen_021.png ../admin/web/parts/nextstation.png
```

Nothing in it is fixed to one screenshot. The panel is found by its own grey, and the machine by the gap that separates it from the text, so the same call works for either.

## What the interface is built from

The NeXTSTEP draft is a set of custom elements that plug into one another:

```html
<nx-window name="disks" title="Platten" x="172" y="366" w="300" h="220">
  <nx-scroller>
    <nx-shelf>
      <nx-thing icon="winchester" label="NeXTSTEP 3.3" chosen></nx-thing>
    </nx-shelf>
  </nx-scroller>
</nx-window>
```

`nx-window` builds its own title bar, close button and resize bar, and remembers where it is, how big it is and whether it is open. `fixed` takes the resize bar away, `flush` lets content run to the frame, `drop` makes it a target for dragging, and `closed` starts it shut.

`nx-scroller` is the only rule in the stylesheet that hands out `overflow`. Anything that can scroll therefore sits inside one and wears NeXT's own scroller on its left, and the browser's native scrollbar cannot appear.

`nx-viewer` is the File Viewer: a shelf that keeps what is dropped on it, a line of status, the path as a row of icons with an arrow between each pair, and the contents of the last step in a scroller. It is given what to show and says what was chosen, so it serves machines and directories alike.

The rest: `nx-menu` with `nx-menu-item`, `nx-dock` with `nx-tile`, `nx-shelf` with `nx-thing`, and `nx-portrait`, `nx-row` and `nx-field` for panels. They use the light DOM rather than a shadow root, so one stylesheet and one set of design tokens reach all of them.

## A note on the icons

The pictures in `parts/` are NeXT's, and NeXT's assets belong to Apple. They stay, and this repository can carry them: that was weighed and decided in #8 on 14 September 2026.

Thirteen are read out of the Workspace Manager's own bundle in a NeXTSTEP 3.3 disk image, one out of Terminal.app and two out of Preferences.app in the same image. Three are cut from a screenshot of the running system, because NeXTSTEP drew its window buttons and dock marks in PostScript and they exist as no file at all. Two come from the boot ROM, through the emulator's own grab.

The tools are ours and hold none of it. `extract.py`, `bootpicture.py`, `ufs.py` and `nxtiff.py` know how to read a NeXT filesystem, a NeXT TIFF and a NeXT screen, which is a description of formats rather than a copy of anything.
