/**
 * The row of modules in Preferences, and which of them is up after the page is
 * loaded again.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, layThePage, never, settled } from "./page.js";

/** Where this browser keeps the module that is up. */
const MODULE_KEY = "previously:module";

answering(async () => never());

const preferences = await import("../../interface/app/preferences.js");

/** @returns {string | null} The module chosen in the row, by its value. */
function chosenModule() {
  return document.querySelector("nx-window[name='preferences'] .module[chosen]")
    ?.getAttribute("value") ?? null;
}

/**
 * Loads the page with what this browser keeps, which is what a reload does.
 * @param {string | null} kept - What is kept under MODULE_KEY, as stored, or
 *   null for nothing.
 *
 * Laying the page empties the storage for each test, so what a reload keeps
 * is put back after it.
 */
async function loaded(kept) {
  layThePage();
  if (kept !== null) localStorage.setItem(MODULE_KEY, kept);
  preferences.wirePreferences();
  await settled();
}

test("the module up before a reload is up after it", async () => {
  await loaded(null);

  document.querySelector("nx-window[name='preferences'] .module[value='software']")
    .dispatchEvent(new MouseEvent("click", { bubbles: true }));
  await settled();
  await loaded(localStorage.getItem(MODULE_KEY));

  assert.equal(chosenModule(), "software");
  assert.equal(document.getElementById("software-page").hidden, false);
  assert.equal(document.getElementById("languages-page").hidden, true);
});

for (const name of ["printing", "toString"]) test(`a kept ${name}, which is no module, starts on Localization`, async () => {
  await loaded(JSON.stringify(name));

  assert.equal(chosenModule(), "localization");
  assert.equal(document.getElementById("languages-page").hidden, false);
  /* The markup starts on Localization as well, but without its name, which
     only showing the module writes. */
  assert.notEqual(document.getElementById("module-name").textContent.trim(), "");
});
