/**
 * Which applications are in the dock: the Config Editor until somebody changes
 * it, whatever is let go over a free slot from then on, and nothing that was
 * carried out again.
 *
 * The page draws each docked application's tile from the tree, keeps the list
 * in this browser, and puts an application that leaves the dock while it runs
 * on the floor of the screen.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, never } from "./page.js";

const EDITOR = {
  name: "Config Editor.app", label: "app.config-editor", icon: "defaultAppIcon",
  path: "/Apps/Config Editor.app", kind: "application", opens: "editor",
};
const TERMINAL = {
  name: "Terminal.app", label: "app.terminal", icon: "Terminal",
  path: "/Apps/Terminal.app", kind: "application", opens: "terminal",
};

/** The tree as GET /api/files answers it, with the two applications above. */
const TREE = {
  name: "Previously", icon: "home", path: "/", kind: "folder", writable: true,
  entries: [{
    name: "Apps", icon: "folder", path: "/Apps", kind: "folder", writable: false,
    entries: [EDITOR, TERMINAL],
  }],
};

/** Where the page keeps the docked applications, which a reload reads back. */
const DOCKED_KEY = "previously:docked";

answering((route) => (route.startsWith("/api/files")
  ? Promise.resolve(json(TREE)) : never()));

layThePage();
const { drawMachines } = await import("../../interface/app/viewer.js");
const { watchTheApplications } = await import("../../interface/app/dock.js");
const { t } = await import("../../interface/strings.js");
watchTheApplications();

/**
 * Lays the page and lets the tree arrive, which is when the dock is drawn.
 * @param {string[]} [kept] - What this browser kept as docked, as a reload
 *   finds it. Left out, nothing was kept.
 * @returns {Promise<Element>} The dock.
 */
async function loadThePage(kept) {
  layThePage();
  if (kept) localStorage.setItem(DOCKED_KEY, JSON.stringify(kept));
  await drawMachines();
  return document.getElementById("dock");
}

/** @returns {Element | null} The tile in the dock that stands for that path. */
function tileFor(dock, path) {
  return dock.querySelector(`nx-tile[value="${path}"]`);
}

test("the Config Editor is in the dock before anybody has changed it", async () => {
  const dock = await loadThePage();
  const editor = tileFor(dock, EDITOR.path);

  assert.ok(editor, "the Config Editor has no tile");
  assert.equal(editor.getAttribute("name"), "editor");
  assert.equal(editor.getAttribute("title"), t("app.config-editor"));
  assert.ok(!tileFor(dock, TERMINAL.path), "the Terminal is in the dock");
});

test("an application let go over a free slot joins the dock there and is there after a reload", async () => {
  let dock = await loadThePage();

  dock.dispatchEvent(new CustomEvent("nx-dock", {
    bubbles: true, detail: { value: TERMINAL.path, slot: 5 },
  }));

  assert.equal(dock.slotOf(tileFor(dock, TERMINAL.path)), 5);
  const kept = JSON.parse(localStorage.getItem(DOCKED_KEY));
  assert.deepEqual(kept, [EDITOR.path, TERMINAL.path]);

  dock = await loadThePage(kept);
  assert.ok(tileFor(dock, EDITOR.path) && tileFor(dock, TERMINAL.path),
            "a docked application is gone after a reload");
});

test("a docked tile starts its application on a double click", async () => {
  const dock = await loadThePage([TERMINAL.path]);
  const terminal = document.querySelector('nx-window[name="terminal"]');

  tileFor(dock, TERMINAL.path).dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));

  assert.ok(!terminal.hidden, "the Terminal did not open");
  assert.ok(!tileFor(dock, TERMINAL.path).hasAttribute("idle"),
            "the tile still says the Terminal is not running");
});

test("an application whose tile leaves the dock while it runs stands on the floor", async () => {
  const dock = await loadThePage([EDITOR.path, TERMINAL.path]);
  document.querySelector('nx-window[name="terminal"]').open();

  dock.release(tileFor(dock, TERMINAL.path));

  assert.deepEqual(JSON.parse(localStorage.getItem(DOCKED_KEY)), [EDITOR.path]);
  assert.ok(document.querySelector(`#floor nx-tile[value="${TERMINAL.path}"]`),
            "the Terminal has no tile on the floor");
});
