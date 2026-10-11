/**
 * nx-window: exactly one window is in front, and a window that is opened is
 * the one.
 *
 * The main menu belongs to whatever is in front, so a window that came up
 * without saying so would leave the menu of the window before it standing.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay, remembered } from "./desk.js";

const MARKUP = `<main>
  <nx-window name="files" title="File Viewer" x="10" y="10" w="300" h="200"></nx-window>
  <nx-window name="info" title="Info" x="40" y="40" w="300" h="200" closed></nx-window>
</main>`;

test("a window that is opened comes to the front and the other goes back", () => {
  lay(MARKUP);
  const files = document.querySelector('nx-window[name="files"]');
  const info = document.querySelector('nx-window[name="info"]');
  files.raise();

  info.open();

  assert.equal(info.hidden, false);
  assert.equal(info.hasAttribute("inactive"), false);
  assert.equal(files.hasAttribute("inactive"), true);
  assert.ok(Number(info.style.zIndex) > Number(files.style.zIndex));
});

test("coming to the front says which window it is", () => {
  lay(MARKUP);
  const info = document.querySelector('nx-window[name="info"]');
  const fronts = [];
  document.addEventListener("nx-front", (event) => fronts.push(event.detail.name));

  info.open();

  assert.deepEqual(fronts, ["info"]);
});

test("a window closed and opened again comes to the front again", () => {
  lay(MARKUP);
  const files = document.querySelector('nx-window[name="files"]');
  const info = document.querySelector('nx-window[name="info"]');
  info.open();
  info.close();
  files.raise();

  info.open();

  assert.equal(info.hasAttribute("inactive"), false);
  assert.equal(files.hasAttribute("inactive"), true);
});

/* The desk the kit's tests lay out is NeXTSTEP's own 1120 by 832, drawn at
   its own size, so that is the room a window has. */
const ROOM = { width: 1120, height: 832 };

test("a window remembered larger than the desk comes back as large as the desk", () => {
  /* Its title bar cannot go above the top edge, so a window taller than the
     desk keeps its resize bar out of reach for good. Remembered that way, it
     came back that way at every load. */
  lay(MARKUP, { files: { open: true, x: 60, y: 90, w: 1500, h: 1400 } });
  const files = document.querySelector('nx-window[name="files"]');

  assert.equal(files.style.width, ROOM.width + "px");
  assert.equal(files.style.height, ROOM.height + "px");
  /* And at the desk's edge, because anywhere further in its resize bar would
     be off the desk again. */
  assert.equal(files.style.left, "0px");
  assert.equal(files.style.top, "0px");
});

test("a window that fits the desk stays where it was left", () => {
  lay(MARKUP, { files: { open: true, x: 60, y: 90, w: 400, h: 300 } });
  const files = document.querySelector('nx-window[name="files"]');

  assert.equal(files.style.left, "60px");
  assert.equal(files.style.top, "90px");
  assert.equal(files.style.height, "300px");
});

test("dragging the resize bar past the foot of the desk stops at it", () => {
  lay(MARKUP);
  const files = document.querySelector('nx-window[name="files"]');
  const corner = files.querySelector(".resizer .end[data-corner=right]");
  corner.setPointerCapture = () => {};

  corner.dispatchEvent(new PointerEvent("pointerdown", { clientX: 300, clientY: 200, pointerId: 1, bubbles: true }));
  corner.dispatchEvent(new PointerEvent("pointermove", { clientX: 2600, clientY: 2400, pointerId: 1, bubbles: true }));
  corner.dispatchEvent(new PointerEvent("pointerup", { clientX: 2600, clientY: 2400, pointerId: 1, bubbles: true }));

  /* The pointer went far past the desk, which a gesture holding on to it
     outside the page reports, and the window ends at the desk's edges. */
  assert.ok(files.offsetTop + parseFloat(files.style.height) <= ROOM.height, files.style.height);
  assert.ok(files.offsetLeft + parseFloat(files.style.width) <= ROOM.width, files.style.width);
  assert.equal(remembered().files.h <= ROOM.height, true);
});

test("a window remembers that it is open, under its name", () => {
  lay(MARKUP);
  const info = document.querySelector('nx-window[name="info"]');

  info.open();

  assert.equal(remembered().info.open, true);
  assert.equal(remembered().desk.front, "info");
});
