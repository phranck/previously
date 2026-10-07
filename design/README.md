# The kit the web admin tool is built from

The interface that configures Previous from a browser, as one source per component, plus the tools that fetch the pictures it uses and the draft it is all shown in.

`mockup-nextstep.html` is that draft: a NeXTSTEP workspace where machines and disks are things you pick up and drop on one another. It opens in a browser with no server and no build step, because `build.py` writes the whole kit into it, pictures and faces included, on every run.

Two other drafts were tried and not taken up, one showing the back of the cube and one an instrument that answers whether the machine is running. They are in this repository's history rather than beside this file.

## Where the pictures come from

The NeXTSTEP draft draws nothing by hand. Its icons are the original files out of a NeXTSTEP 3.3 disk image, and its window buttons and dock marks are cut from a screenshot of the running system, because NeXTSTEP drew those in PostScript and they exist as no file at all.

Six tools do that work:

| Tool | What it does |
|---|---|
| `ufs.py` | Reads a NeXT UFS filesystem: 4.3BSD FFS, big endian, behind a `dlV3` disk label. |
| `nxtiff.py` | Decodes NeXT's TIFFs, which no current library reads: two bits per sample, alpha in its own plane, and a second copy of each picture at four bits per color channel. |
| `extract.py` | Pulls the icons out of the image and the controls out of the screenshot, into `../admin/web/parts/`. |
| `bootpicture.py` | Cuts the machine out of a boot screen and makes an icon of it. |
| `fonts.py` | Fetches Inconsolata and writes the two faces the Terminal is set in, with their license, into `../admin/web/fonts/`. |
| `build.py` | Puts the kit together, writes the two files the admin serves, and bakes the pictures and those faces into the mockup as data URIs so it stays one file. |

**Every picture lives in `../admin/web/parts/`, and nowhere else.** That is the folder the admin serves them from, and a package is built out of `admin/` alone. Every tool here writes into it, and `build.py` bakes the mockup from it, as it bakes the Terminal's face from `../admin/web/fonts/`. The folder is committed, so the draft works without running any of this. Run it again when a picture needs to change:

```bash
python3 extract.py ~/nextstep/NS33_2GB.dd screenshot.png
python3 build.py
```

`extract.py` needs two things that are not in this repository. The first is a NeXTSTEP 3.3 disk image, which the paper PAP-PRE-001 says where to get. The second is a screenshot of NeXTSTEP 3.3 at its own resolution of 1120 by 832, because the pixel bounds in `extract.py` are that screenshot's and nothing else will line up.

## The two machines

The pictures of the NeXTcube and the NeXTstation come from somewhere else again, because NeXTSTEP holds no drawing of either. The boot ROM does: while it tests the hardware it puts up a panel with the NeXT cube on the left and the machine on the right, and which machine that is follows from the configuration.

Previous can write the emulated framebuffer itself, which is what makes those pictures usable. Ctrl+Alt+G grabs it at the machine's own 1120 by 832 in NeXT's four grays, unscaled, and leaves `next_screen_NNN.png` in the directory the emulator was started in. Grabbing once a second through a boot catches the panel, and `bootpicture.py` finds the machine inside it and reduces it to an icon:

```bash
python3 bootpicture.py next_screen_021.png ../admin/web/parts/nextstation.png
```

Nothing in it is fixed to one screenshot. The panel is found by its own gray, and the machine by the gap that separates it from the text, so the same call works for either.

## The Terminal's face

NeXT's Terminal was set in Ohlfs, a face Keith Ohlfs drew for NeXTSTEP and only ever as bitmaps. The Terminal here is set in [Inconsolata](https://github.com/googlefonts/Inconsolata), the outline face closest to it. At 16 pixels its cell is Ohlfs's 8 by 16, its capitals are Ohlfs's 10 pixels, and its zero is slashed as Ohlfs's is. It carries hinting, so it is drawn sharp at every size the desk is drawn at.

`fonts.py` takes the Regular and the Bold from the 3.000 release, checks each against its sum, and writes them into `../admin/web/fonts/` as WOFF2. The license goes beside them as `OFL.txt`, because the SIL Open Font License lets the faces travel with software only together with it.

```bash
python3 fonts.py
python3 build.py
```

The two files are committed, so nothing has to run for the Terminal to be set in them. Run it again to move to a later release, which means changing `RELEASE` and the sums together.

It changes one thing on the way, in metrics rather than in outlines. A font states its line in three tables and a browser picks one of them by platform, and Inconsolata's three disagree: two give a line of 16.8 pixels at the Terminal's size and the third gives 23.3. All three are set to one em, which at 16 pixels is the 16 a row of this interface is. That is also why nothing states the cell: whatever needs it reads it off the face as `1ch` and `1lh`.

## The kit

`kit/` is the interface, one source per part. Each part holds its element and its styles beside each other, `window.js` next to `window.css`, and `build.py` puts them together into the two files the admin serves and into this draft. So a part is edited in one place and cannot drift from itself.

```bash
python3 build.py            # or: make -C ../admin kit
```

`build.py` carries the list of parts, in the order they go together. That one list decides the order of the stylesheet, the order of the definitions, the `customElements.define` call at the foot of the script, and the overview comment at its head. Adding a part means adding a line to it.

The two files it writes, `../admin/interface/nextstep.css` and `../admin/interface/nextstep.js`, say at the top that they are generated. `../admin/tests/test_kit.py` fails when either has been edited by hand, which is what makes one source safe to rely on.

What is not in the kit is what only one application has. The admin keeps that in `../admin/interface/app.css`, and this draft keeps its own beside the marks in the file.

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

`nx-viewer` is the File Viewer: a shelf that keeps what is dropped on it, a line of status, the path as a row of icons with an arrow between each pair, and the contents of the last step. It is given what to show and says what was chosen, so it serves machines and directories alike.

The last two bands sit in scrollers, and each says which scrollers it has. The path only ever grows sideways, so it has the one along its foot; the contents have both. A trough is there whether or not there is anything to scroll, because in the original it is part of the view rather than something that appears when it is needed.

The rest: `nx-menu` with `nx-menu-item`, `nx-dock` with `nx-tile`, `nx-floor` for the tiles that are not in the dock, `nx-shelf` with `nx-thing`, and `nx-portrait`, `nx-row` and `nx-field` for panels. They use the light DOM rather than a shadow root, so one stylesheet and one set of design tokens reach all of them.

## How a tile behaves

NeXT wrote down why, so it is written down here. A tile acts on a double click and a single click does nothing, because a tile is moved by dragging it and a click that acted would fire whenever somebody began a drag and thought better of it. The File Viewer works the same way, one click to choose and two to open.

The three marks in the lower left corner of a tile say the application is **not** running, and they go when it starts. That is the direction the OpenStep guidelines give and the direction the running system shows: Mail, Librarian and the console carry them while the Workspace and the clock do not.

An application that is running and is not in the dock puts its tile on the floor of the screen instead, from the left corner rightwards, and takes it away again when it stops. `nx-floor` is that floor. The tile is the dock's own, because `Workspace.app/tile.tiff` is a plain 64 by 64 gray square with the icon on it and no lettering.

## A note on the icons and the face

The pictures in `../admin/web/parts/` are NeXT's, and NeXT's assets belong to Apple. They stay, and this repository can carry them: that was weighed and decided in #8 on 14 September 2026.

Thirteen are read out of the Workspace Manager's own bundle in a NeXTSTEP 3.3 disk image, one out of Terminal.app and two out of Preferences.app in the same image. Three are cut from a screenshot of the running system, because NeXTSTEP drew its window buttons and dock marks in PostScript and they exist as no file at all. Two come from the boot ROM, through the emulator's own grab.

The tools are ours and hold none of it. `extract.py`, `bootpicture.py`, `ufs.py` and `nxtiff.py` know how to read a NeXT filesystem, a NeXT TIFF and a NeXT screen, which is a description of formats rather than a copy of anything.

The face is not NeXT's. Inconsolata is published under the SIL Open Font License 1.1, which is in `../admin/web/fonts/OFL.txt` beside the two files.
