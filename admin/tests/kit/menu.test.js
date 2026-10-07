/**
 * nx-menu: one menu, whose entries change with the application in front.
 *
 * Every entry is in the markup and says which application it belongs to, and
 * the menu shows the ones of one owner. An entry the page has taken away
 * stays away whoever is in front.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay } from "./desk.js";

const MARKUP = `<nx-menu name="main" title="Workspace" x="0" y="0">
  <nx-menu-item opens="info" key="i">Info</nx-menu-item>
  <nx-menu-item away>About NeXTcube</nx-menu-item>
  <nx-menu-item for="viewer" key="o">Open</nx-menu-item>
  <nx-menu-item for="viewer" key="w">Close</nx-menu-item>
</nx-menu>`;

/** @returns {string[]} The words on the entries that are showing. */
function showing(menu) {
  return [...menu.querySelectorAll("nx-menu-item")]
    .filter((entry) => !entry.hidden)
    .map((entry) => entry.firstChild.nextSibling.textContent.trim());
}

test("it shows the entries of one owner and none of the others", () => {
  const menu = lay(MARKUP);

  menu.showFor("viewer", "File Viewer");

  assert.deepEqual(showing(menu), ["Open", "Close"]);
  assert.equal(menu.querySelector(":scope > .title").textContent, "File Viewer");
});

test("the workspace owns the entries that name no owner", () => {
  const menu = lay(MARKUP);

  menu.showFor("", "Workspace");

  assert.deepEqual(showing(menu), ["Info"]);
});

test("the foot of the menu is drawn on the last entry that shows", () => {
  const menu = lay(MARKUP);

  menu.showFor("", "Workspace");
  const marked = [...menu.querySelectorAll("nx-menu-item[last]")];

  assert.equal(marked.length, 1);
  assert.equal(marked[0].getAttribute("opens"), "info");
});

test("an entry with a letter is pressed by that letter", () => {
  const menu = lay(MARKUP);
  menu.showFor("", "Workspace");
  let pressed = 0;
  menu.querySelector('nx-menu-item[key="i"]').addEventListener("click", () => { pressed += 1; });

  dispatchEvent(new KeyboardEvent("keydown", { key: "i" }));

  assert.equal(pressed, 1);
});
