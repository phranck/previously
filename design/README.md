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

Six tools do that work:

| Tool | What it does |
|---|---|
| `ufs.py` | Reads a NeXT UFS filesystem: 4.3BSD FFS, big endian, behind a `dlV3` disk label. |
| `nxtiff.py` | Decodes NeXT's TIFFs, which no current library reads: two bits per sample, alpha in its own plane, and a second copy of each picture at four bits per colour channel. |
| `extract.py` | Pulls the icons out of the image and the controls out of the screenshot, into `parts/`. |
| `bootpicture.py` | Cuts the machine out of a boot screen and makes an icon of it. |
| `fonts.py` | Fetches Ohlfs and writes the four faces the Terminal is set in, into `../admin/web/fonts/`. |
| `build.py` | Puts the kit together, writes the two files the admin serves, and bakes `parts/` and those faces into the mockup as data URIs so it stays one file. |

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

## The Terminal's face

Keith Ohlfs drew Ohlfs for NeXTSTEP as bitmaps, and Terminal.app was set in its 12 pixel strike. [jasonwoodland/ohlfs-font-extras](https://github.com/jasonwoodland/ohlfs-font-extras) decodes the original `Ohlfs.font` bundle and writes each strike out as TrueType, with the Extra variants adding glyphs the original never had. `fonts.py` takes the four Screen 12 Extra faces from one named commit there, checks each against its sum, and writes them into `../admin/web/fonts/` as WOFF2.

```bash
python3 fonts.py
python3 build.py
```

The four files are committed, so nothing has to run for the Terminal to be set in it. Run it again to move to a later commit upstream, which means changing `UPSTREAM` and the four sums together.

It changes two things on the way, both in metrics rather than in outlines. A font states its line in three tables and a browser picks one of them by platform, so all three are set to what the face itself says, which is 16 pixels. The flag that tells a browser to prefer the typographic pair needs a table one version newer, so the version is raised as well. Without the first of those, the same terminal draws rows two pixels taller on one machine than on the next.

What comes out of it is outlines and not bitmaps, which matters when reading the files: they carry no strike table, and their 288 glyphs are made of 7710 points, every one on a grid of 100 units and not one of them a curve. Each contour is a rectangle around one of the original's pixels.

It behaves like a bitmap face all the same, and that is down to hinting rather than to format. An outline face is drawn sharp at any size because its hinting pulls each stem onto the pixel grid; this one carries none, so it is on the grid only where its own 100-unit step lands on a whole pixel. The em is 1500, so that is a type size of 15 and whole multiples of it, and the cell that follows is 8 across by 16 down. That is why `--terminal-size` is 15 and why nothing states the cell: whatever needs it reads it off the face as `1ch` and `1lh`. The pictures here are bitmaps outright, and both want a desk drawn at a whole step rather than at a quarter of one.

## The kit

`kit/` is the interface, one source per part. Each part holds its element and its styles beside each other, `window.js` next to `window.css`, and `build.py` puts them together into the two files the admin serves and into this draft. So a part is edited in one place and cannot drift from itself.

```bash
python3 build.py            # or: make -C ../admin kit
```

`build.py` carries the list of parts, in the order they go together. That one list decides the order of the stylesheet, the order of the definitions, the `customElements.define` call at the foot of the script, and the overview comment at its head. Adding a part means adding a line to it.

The two files it writes, `../admin/web/nextstep.css` and `../admin/web/nextstep.js`, say at the top that they are generated. `../admin/tests/test_kit.py` fails when either has been edited by hand, which is what makes one source safe to rely on.

What is not in the kit is what only one application has. The admin keeps that in `../admin/web/previously.css`, and this draft keeps its own beside the marks in the file.

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

The three marks in the lower left corner of a tile say the application is **not** running, and they go when it starts. That is the direction the OpenStep guidelines give and the direction the running system shows: Mail, Librarian and the console carry them whilst the Workspace and the clock do not.

An application that is running and is not in the dock puts its tile on the floor of the screen instead, from the left corner rightwards, and takes it away again when it stops. `nx-floor` is that floor. The tile is the dock's own, because `Workspace.app/tile.tiff` is a plain 64 by 64 grey square with the icon on it and no lettering.

## A note on the icons and the face

The pictures in `parts/` are NeXT's, and NeXT's assets belong to Apple. They stay, and this repository can carry them: that was weighed and decided in #8 on 14 September 2026. Ohlfs is the same thing in another form, so the four faces in `../admin/web/fonts/` stand on that decision too. The repository they are built from states no licence of its own; what it holds is NeXT's bitmaps read out of NeXT's own font bundle, which is what the tools here do with the icons.

Thirteen are read out of the Workspace Manager's own bundle in a NeXTSTEP 3.3 disk image, one out of Terminal.app and two out of Preferences.app in the same image. Three are cut from a screenshot of the running system, because NeXTSTEP drew its window buttons and dock marks in PostScript and they exist as no file at all. Two come from the boot ROM, through the emulator's own grab.

The tools are ours and hold none of it. `extract.py`, `bootpicture.py`, `ufs.py` and `nxtiff.py` know how to read a NeXT filesystem, a NeXT TIFF and a NeXT screen, which is a description of formats rather than a copy of anything.
