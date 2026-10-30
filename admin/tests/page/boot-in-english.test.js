/**
 * A browser that chose no language, or chose English. English is part of the
 * script, so the page fetches no catalog at all and starts at once.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { definitions, startThePage } from "./boot.js";
import { never, settled } from "./served.js";

const { en } = await import("../../interface/lang/en.js");

/** What the page asked for that is not the service's: its own files. */
const files = [];

await startThePage(null, (route) => {
  if (!route.startsWith("/api/")) files.push(route);
  return never();
});

test("the page starts in English and fetches no catalog", async () => {
  await settled();

  assert.deepEqual(files, []);
  const [first] = definitions;
  assert.ok(first, "the kit was never defined");
  assert.equal(first.language, "en");
  for (const [key, shown] of first.words) assert.equal(shown, en[key], key);
});
