/**
 * Every application's menu opens with an entry about it, and that entry puts
 * up its About panel: the application's picture, its name in words, its own
 * version and the copyright.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, never, settled } from "./page.js";

/** The tree as GET /api/files answers it, with two applications whose
 *  versions differ from each other and from this tool's. */
const TREE = {
  name: "Previously", icon: "home", path: "/", kind: "folder", writable: true,
  entries: [{
    name: "Apps", icon: "folder", path: "/Apps", kind: "folder", writable: false,
    entries: [
      {
        name: "Grab.app", label: "app.grab", icon: "Grab", path: "/Apps/Grab.app",
        kind: "application", opens: "grab", version: "2.3.4",
      },
      {
        name: "Terminal.app", label: "app.terminal", icon: "Terminal",
        path: "/Apps/Terminal.app", kind: "application", opens: "terminal", version: "1.0.7",
      },
    ],
  }],
};

answering((route) => (route.startsWith("/api/files")
  ? Promise.resolve(json(TREE)) : never()));

layThePage();
const { drawMachines } = await import("../../interface/app/viewer.js");
const { drawTheMenu, watchTheFrontWindow } = await import("../../interface/app/menu.js");
const { t } = await import("../../interface/strings.js");

/**
 * Lays the page, lets the tree arrive, and wires the menu to it.
 * @returns {Promise<void>}
 */
async function loadThePage() {
  layThePage();
  await drawMachines();
  watchTheFrontWindow();
}

/** @returns {Element[]} The main menu's entries that are showing. */
function showing() {
  return [...document.querySelectorAll('nx-menu[name="menu"] > nx-menu-item')]
    .filter((entry) => !entry.hidden);
}

test("the menu of the application in front opens with the entry about it", async () => {
  await loadThePage();

  drawTheMenu("grab");

  const [first] = showing();
  assert.equal(first.getAttribute("name"), "about-app");
  assert.equal(first.getAttribute("for"), "grab");
  assert.match(first.textContent, new RegExp(t("menu.about-app", { app: t("app.grab") })
    .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("the entry puts up that application's About panel with its own version", async () => {
  await loadThePage();
  drawTheMenu("terminal");
  const [about] = showing();

  about.click();
  await settled();

  const panel = document.getElementById("ask");
  assert.ok(panel.hasAttribute("data-open"), "no panel came up");
  assert.equal(panel.querySelector(".name").textContent, t("app.terminal"));
  assert.match(panel.querySelector(".lines").textContent,
               new RegExp(t("about.version", { version: "1.0.7" })));
  panel.close(true);
});

test("the Workspace's menu holds no entry about an application", async () => {
  await loadThePage();

  drawTheMenu("");

  const names = showing().map((entry) => entry.getAttribute("name"));
  assert.ok(!names.includes("about-app"), names.join(", "));
});
