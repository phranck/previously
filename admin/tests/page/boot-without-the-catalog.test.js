/**
 * A browser that chose German, on a page whose catalog cannot be fetched
 * because the Pi went away between serving the page and serving the words.
 * The page starts in English rather than in keys, and the choice is kept, so
 * the next visit asks for German again.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { definitions, startThePage } from "./boot.js";
import { never, settled } from "./served.js";

const { en } = await import("../../interface/lang/en.js");
const { LANGUAGE_KEY } = await import("../../interface/strings.js");

/** What a browser says when the host it asks does not answer at all. */
const UNREACHABLE = "Load failed";

await startThePage("de", (route) => (route.startsWith("/api/")
  ? never() : Promise.reject(new TypeError(UNREACHABLE))));

test("the page starts in English, with no key on it", async () => {
  await settled();

  const [first] = definitions;
  assert.ok(first, "the kit was never defined");
  assert.equal(first.language, "en");
  for (const [key, shown] of first.words) assert.equal(shown, en[key], key);
});

test("the choice stays kept for the next visit", () => {
  assert.equal(localStorage.getItem(LANGUAGE_KEY), "de");
});
