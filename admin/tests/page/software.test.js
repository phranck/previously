/**
 * The Software module of Preferences, on the page's own markup, with the
 * catalog the service would answer.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, never, settled } from "./page.js";

/** One entry, as `/api/software` describes it. */
function described(identifier, name, origin) {
  return {
    identifier, name, description: "", group: "developer", version: "3.3",
    systems: ["nextstep-3.3"], for: ["NeXTSTEP 3.3"],
    address: `https://archive.org/download/item/${identifier}.iso`, size: 1000,
    algorithm: "sha1", digest: "a".repeat(40), kind: "disc", source: "archive.org",
    cover: "", picture: null, page: `https://archive.org/details/${identifier}`, origin,
  };
}

/** The catalog as /api/software answers it: one shipped entry, one added,
 *  and one shipped entry removed here. */
const CATALOG = {
  booted: "nextstep-3.3",
  groups: [{ identifier: "developer", name: "Developer" }],
  systems: [{ identifier: "nextstep-3.3", name: "NeXTSTEP 3.3" }],
  entries: [described("shipped-one", "Shipped One", "shipped"),
            described("added-one", "Added One", "added")],
  removed: [described("gone-one", "Gone One", "shipped")],
};

answering(async (route) => (String(route).startsWith("/api/software")
  ? json(CATALOG) : never()));

const system = await import("../../interface/app/system.js");
const software = await import("../../interface/app/software.js");

/** Lays the page, wires the module and draws the catalog. */
async function theModule() {
  layThePage();
  system.heard({ running: true });
  software.wireTheSoftware();
  await software.refreshTheSoftware();
  await settled();
}

/** @returns {HTMLElement} The row of the entry of that name. */
function rowOf(name) {
  const row = [...document.querySelectorAll("#software-list .system")]
    .find((one) => one.textContent.includes(name));
  assert.ok(row, name);
  return /** @type {HTMLElement} */ (row);
}

test("double clicking an entry opens the window it is edited in", async () => {
  await theModule();

  rowOf("Added One").dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
  await settled();

  assert.equal(document.querySelector('nx-window[name="software-entry"]').hidden, false);
  assert.equal(document.getElementById("se-name").value, "Added One");
});

test("View Origin opens the entry's page in a window of its own", async () => {
  await theModule();
  const opened = [];
  const open = window.open;
  window.open = (...asked) => { opened.push(asked); return null; };
  try {
    rowOf("Added One").dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
    await settled();
    const button = document.getElementById("se-page");

    assert.equal(button.hidden, false);
    button.click();
  } finally {
    window.open = open;
  }

  /* noopener, so the page that opens cannot reach this one. */
  assert.deepEqual(opened, [["https://archive.org/details/added-one", "_blank", "noopener"]]);
});

test("double clicking a shipped entry removed here opens nothing", async () => {
  await theModule();

  rowOf("Gone One").dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
  await settled();

  assert.equal(document.querySelector('nx-window[name="software-entry"]').hidden, true);
});
