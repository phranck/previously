/**
 * The File Viewer stands where it was left. A folder opened before a reload is
 * the folder it shows after it, and a folder that has gone by then leaves it
 * at the nearest folder above.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, never } from "./page.js";

/** The tree as GET /api/files answers it: the root, Apps with one
 *  application in it, and nothing else. */
const TREE = {
  name: "Previously", icon: "home", path: "/", kind: "folder", writable: true,
  entries: [{
    name: "Apps", icon: "folder", path: "/Apps", kind: "folder", writable: false,
    entries: [{
      name: "Terminal.app", label: "app.terminal", icon: "Terminal",
      path: "/Apps/Terminal.app", kind: "application", opens: "terminal",
    }],
  }],
};

/** Where the page keeps the folder the viewer shows. */
const PLACE_KEY = "previously:place";

answering((route) => (route.startsWith("/api/files")
  ? Promise.resolve(json(TREE)) : never()));

layThePage();
const viewer = await import("../../interface/app/viewer.js");

/** How many times the page has been loaded again, which names each fresh copy
 *  of the viewer so that none of them shares memory with another. */
let reloads = 0;

/**
 * Loads the viewer the way a reload does: a fresh copy of the module, which
 * remembers nothing but what this browser kept.
 * @param {string} place - The path the browser kept as the viewer's place.
 */
async function reload(place) {
  layThePage();
  localStorage.setItem(PLACE_KEY, JSON.stringify(place));
  reloads += 1;
  const fresh = await import(`../../interface/app/viewer.js?reload=${reloads}`);
  await fresh.drawMachines();
}

/** @returns {string | null} The path of the last step the viewer's path shows,
 *  which is the folder it is in. */
function shownPlace() {
  const steps = document.querySelectorAll("#file-viewer .path nx-thing");
  return steps[steps.length - 1]?.getAttribute("value") ?? null;
}

test("a folder opened before a reload is the folder the viewer shows after it", async () => {
  layThePage();
  await viewer.drawMachines();

  await viewer.open("/Apps");
  assert.equal(shownPlace(), "/Apps");
  const kept = JSON.parse(localStorage.getItem(PLACE_KEY));
  assert.equal(kept, "/Apps");

  await reload(kept);
  assert.equal(shownPlace(), "/Apps");
});

test("a folder that has gone by the reload leaves the viewer at the nearest one above", async () => {
  await reload("/Apps/Gone");

  assert.equal(shownPlace(), "/Apps");
});
