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

test("a window remembers that it is open, under its name", () => {
  lay(MARKUP);
  const info = document.querySelector('nx-window[name="info"]');

  info.open();

  assert.equal(remembered().info.open, true);
  assert.equal(remembered().desk.front, "info");
});
