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
    downloaded: false,
  };
}

/** The catalog as /api/software answers it: one shipped entry, one added,
 *  one added with an address off archive.org, which has no page, and one
 *  shipped entry removed here. */
const CATALOG = {
  booted: "nextstep-3.3",
  groups: [{ identifier: "developer", name: "Developer" }],
  systems: [{ identifier: "nextstep-3.3", name: "NeXTSTEP 3.3" }],
  entries: [described("shipped-one", "Shipped One", "shipped"),
            described("added-one", "Added One", "added"),
            { ...described("typed-one", "Typed One", "added"), page: "" }],
  removed: [described("gone-one", "Gone One", "shipped")],
  download: null,
  room: 1e9,
};

/** What archive.org's adapter answers for a dropped address: the fields of
 *  one file, and the page of the item it is in. */
const FOUND = {
  ok: true, reason: "lookup.found",
  fields: { name: "Nebula", address: "https://archive.org/download/nebula-se/NEBULA_SE.ISO",
            kind: "disc", algorithm: "sha1", size: 1000, digest: "b".repeat(40) },
  page: "https://archive.org/details/nebula-se",
};

/** What the Pi says of the download, and whether Shipped One is downloaded,
 *  which a test sets. */
let download = null;
let downloadedOne = false;

/** What was asked to be downloaded. */
const posted = [];

/** @returns {object} The catalog as the Pi answers it now. */
function catalogNow() {
  return {
    ...CATALOG, download,
    entries: CATALOG.entries.map((entry) => (entry.identifier === "shipped-one"
      ? { ...entry, downloaded: downloadedOne } : entry)),
  };
}

answering(async (route, options = {}) => {
  const path = String(route);
  if (path.startsWith("/api/software/lookup")) return json(FOUND);
  if (path.startsWith("/api/software/download")) {
    posted.push(JSON.parse(options.body));
    download = { entry: "shipped-one", done: 400, of: 1000, running: true, outcome: null };
    return json({ ok: true, reason: "download.started", name: "Shipped One", ...catalogNow() });
  }
  return path.startsWith("/api/software") ? json(catalogNow()) : never();
});

const system = await import("../../interface/app/system.js");
const software = await import("../../interface/app/software.js");
const { t } = await import("../../interface/strings.js");

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

    assert.equal(button.disabled, false);
    button.click();
  } finally {
    window.open = open;
  }

  /* noopener, so the page that opens cannot reach this one. */
  assert.deepEqual(opened, [["https://archive.org/details/added-one", "_blank", "noopener"]]);
});

test("an address dropped on the list opens the form with its item's page", async () => {
  await theModule();
  const drop = new Event("drop", { bubbles: true, cancelable: true });
  Object.defineProperty(drop, "dataTransfer", {
    value: { types: ["text/uri-list"], getData: () => "https://archive.org/details/nebula-se" },
  });

  document.querySelector("nx-scroller.packages").dispatchEvent(drop);
  await settled();

  assert.equal(document.getElementById("se-name").value, "Nebula");
  assert.equal(document.getElementById("se-page").disabled, false);
});

/** @returns {boolean} Whether a button can be seen, which it cannot where it
 *  or a box around it is hidden. */
function shown(id) {
  return !document.getElementById(id).closest("[hidden]");
}

test("View Origin is disabled in the form of an entry without a page", async () => {
  await theModule();

  rowOf("Typed One").dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
  await settled();

  assert.equal(shown("se-page"), true);
  assert.equal(document.getElementById("se-page").disabled, true);
});

test("View Origin is disabled in the Info window of an entry without a page", async () => {
  await theModule();

  software.showSoftwareInfo({ package: CATALOG.entries[2], icon: "cdrom" });
  await settled();

  assert.equal(shown("si-page"), true);
  assert.equal(document.getElementById("si-page").disabled, true);
});

test("double clicking a shipped entry removed here opens nothing", async () => {
  await theModule();

  rowOf("Gone One").dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
  await settled();

  assert.equal(document.querySelector('nx-window[name="software-entry"]').hidden, true);
});

/** Opens the Info window of Shipped One, as a double click in the File
 *  Viewer does. */
async function itsInfo() {
  software.showSoftwareInfo({ package: CATALOG.entries[0], icon: "cdrom" });
  await settled();
}

test("the Info window says an entry is not on the Pi and offers Download", async () => {
  download = null;
  downloadedOne = false;
  await theModule();

  await itsInfo();

  assert.equal(document.getElementById("si-here").textContent, t("software.here.not"));
  assert.equal(document.getElementById("si-download").disabled, false);
  assert.equal(shown("si-gauge"), false);
});

test("a downloaded entry says so and is not offered again", async () => {
  download = null;
  downloadedOne = true;
  await theModule();

  await itsInfo();

  assert.equal(document.getElementById("si-here").textContent, t("software.here.done"));
  assert.equal(document.getElementById("si-download").disabled, true);
});

test("the File Viewer shows the gauge under the entry that downloads", async () => {
  download = { entry: "shipped-one", done: 400, of: 1000, running: true, outcome: null };
  await theModule();
  const contents = document.querySelector("#file-viewer .contents");
  const thing = document.createElement("nx-thing");
  thing.setAttribute("value", "/Software/Developer/shipped-one");
  const other = document.createElement("nx-thing");
  other.setAttribute("value", "/Software/Developer/added-one");
  contents.append(thing, other);

  software.showTheDownloadInTheViewer();

  assert.equal(thing.querySelector(".gauge-fill").style.width, "40%");
  assert.equal(other.querySelector(".gauge"), null);
  download = null;
});

test("Download asks first, has the Pi start it, and says when it is done", async () => {
  download = null;
  downloadedOne = false;
  posted.length = 0;
  await theModule();
  await itsInfo();

  document.getElementById("si-download").click();
  await settled();
  const panel = document.getElementById("ask");
  assert.ok(panel.hasAttribute("data-open"), "no panel came up");
  panel.close(true);
  await settled();

  assert.deepEqual(posted, [{ entry: "shipped-one" }]);
  assert.equal(shown("si-gauge"), true);
  assert.equal(document.getElementById("si-fill").style.width, "40%");
  assert.equal(document.getElementById("si-download").disabled, true);

  /* The Pi finishes, and the next time the page asks it says so. */
  download = { entry: "shipped-one", done: 1000, of: 1000, running: false,
               outcome: { reason: "download.finished", name: "Shipped One" } };
  downloadedOne = true;
  await new Promise((done) => setTimeout(done, 1200));
  await settled();

  assert.equal(shown("si-gauge"), false);
  assert.equal(document.getElementById("si-here").textContent, t("software.here.done"));
  assert.equal(document.getElementById("si-note").textContent,
               t("told.download.finished", { name: "Shipped One" }));
});
