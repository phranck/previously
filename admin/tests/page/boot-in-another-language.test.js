/**
 * A browser that chose a language other than English. The page fetches that
 * one catalog and nothing else, builds nothing while it is on its way, and
 * translates the markup before the kit defines its first element, so no
 * element is ever built around words that are not there yet.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { definitions, startThePage, wordsOnThePage } from "./boot.js";
import { never, served, settled } from "./served.js";

const { de } = await import("../../interface/lang/de.js");
const { en } = await import("../../interface/lang/en.js");

/** What the page asked for that is not the service's: its own files. */
const files = [];

/** Lets the catalog arrive, which it does not until a test says so. */
let deliver = () => {};
const delivered = new Promise((resolve) => { deliver = resolve; });

await startThePage("de", (route) => {
  if (route.startsWith("/api/")) return never();
  files.push(route);
  return delivered.then(() => served(route));
});

test("nothing is built and nothing is written while the catalog is on its way", async () => {
  await settled();

  assert.equal(customElements.get("nx-window"), undefined);
  assert.deepEqual(definitions, []);
  assert.deepEqual(wordsOnThePage().filter(([, shown]) => shown !== ""), []);
});

test("the markup is in the chosen language before the kit defines anything", async () => {
  deliver();
  await settled();

  assert.ok(customElements.get("nx-window"), "the kit was never defined");
  const [first] = definitions;
  assert.equal(first.language, "de");
  for (const [key, shown] of first.words) assert.equal(shown, de[key] ?? en[key], key);
});

test("the chosen catalog is the one file fetched", () => {
  assert.deepEqual(files, ["lang/de.json"]);
});
