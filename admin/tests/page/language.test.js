/**
 * Changing the language in Preferences. The catalog is fetched the first time
 * its language is chosen and not again, the page is then written in it with
 * no key showing, and a catalog that cannot be fetched leaves the interface as
 * it was.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, layThePage, never, settled } from "./page.js";
import { notFound, served } from "./served.js";

/** What the page asked for that is not the service's, since the test began. */
let files = [];

/** How the page's own files are answered, which a test may change. */
let answer = (/** @type {string} */ route) => Promise.resolve(served(route));

answering((route) => {
  if (route.startsWith("/api/")) return never();
  files.push(route);
  return answer(route);
});

layThePage();
const { LANGUAGE_KEY, LANGUAGE_NAMES, currentLanguage } = await import("../../interface/strings.js");
const { drawLanguages } = await import("../../interface/app/preferences.js");

/** Every catalog, out of its source, to read what the page should say.
 *  @type {Record<string, Record<string, string>>} */
const catalogs = {};
for (const code of Object.keys(LANGUAGE_NAMES)) {
  catalogs[code] = (await import(`../../interface/lang/${code}.js`))[code];
}

/** What a browser says when the host it asks does not answer at all. */
const UNREACHABLE = "Load failed";

/** Each way a catalog can fail to arrive: the Pi gone, and the file missing. */
const FAILURES = {
  unreachable: () => Promise.reject(new TypeError(UNREACHABLE)),
  missing: () => Promise.resolve(notFound()),
};

/**
 * Chooses a language the way a person does, in the Localization module.
 * @param {string} code - One of the six.
 */
function choose(code) {
  const option = [...document.getElementById("languages")?.children ?? []]
    .find((element) => element.textContent === LANGUAGE_NAMES[code]);
  assert.ok(option, `Preferences offers no ${code}`);
  /** @type {HTMLElement} */ (option).click();
}

/**
 * Lays the page out in English with every file answered, and forgets what was
 * asked so far. English is part of the script, so choosing it fetches nothing.
 * @returns {Promise<void>}
 */
async function start() {
  answer = (route) => Promise.resolve(served(route));
  layThePage();
  drawLanguages();
  choose("en");
  await settled();
  files = [];
}

/**
 * Holds the whole page to one language: the document says it, the lookup is
 * in it, every string the markup carries is that language's sentence rather
 * than its key, and Preferences marks it.
 * @param {string} code - The language the page should speak.
 */
function assertThePageSpeaks(code) {
  assert.equal(document.documentElement.lang, code);
  assert.equal(currentLanguage(), code);
  for (const element of document.querySelectorAll("[data-t]")) {
    const key = /** @type {HTMLElement} */ (element).dataset.t ?? "";
    const shown = [...element.childNodes].find((node) => node.nodeType === Node.TEXT_NODE);
    assert.equal(shown?.textContent, catalogs[code][key] ?? catalogs.en[key], key);
  }
  const chosen = document.querySelector("#languages [chosen]");
  assert.equal(chosen?.textContent, LANGUAGE_NAMES[code]);
}

test("choosing a language fetches its catalog and writes the page in it", async () => {
  await start();

  choose("fr");
  await settled();

  assert.deepEqual(files, ["lang/fr.json"]);
  assertThePageSpeaks("fr");
  assert.equal(localStorage.getItem(LANGUAGE_KEY), "fr");
});

test("a catalog already here is not fetched again, and English never is", async () => {
  await start();

  choose("it");
  await settled();
  choose("en");
  await settled();
  choose("it");
  await settled();

  assert.deepEqual(files, ["lang/it.json"]);
  assertThePageSpeaks("it");
});

test("a catalog that cannot be fetched leaves the interface as it was", async () => {
  for (const [why, failing] of Object.entries(FAILURES)) {
    await start();
    answer = failing;

    choose("de");
    await settled();

    assert.deepEqual(files, ["lang/de.json"], why);
    assertThePageSpeaks("en");
    assert.equal(localStorage.getItem(LANGUAGE_KEY), "en", why);
  }
});

test("a catalog that could not be fetched is asked for again the next time", async () => {
  await start();
  answer = FAILURES.unreachable;
  choose("es");
  await settled();

  answer = (route) => Promise.resolve(served(route));
  choose("es");
  await settled();

  assert.deepEqual(files, ["lang/es.json", "lang/es.json"]);
  assertThePageSpeaks("es");
});

test("the language chosen last is the one that stays", async () => {
  await start();
  /** @type {() => void} */
  let deliver = () => {};
  const delivered = new Promise((resolve) => { deliver = () => resolve(undefined); });
  answer = (route) => delivered.then(() => served(route));

  choose("sv");
  await settled();
  choose("en");
  await settled();
  deliver();
  await settled();

  assertThePageSpeaks("en");
  assert.equal(localStorage.getItem(LANGUAGE_KEY), "en");
});
