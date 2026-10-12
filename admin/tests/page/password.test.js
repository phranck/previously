/**
 * Which end of the rule a refused password missed.
 *
 * The service refuses a password with the same 400 whether it is too short or
 * too long, and a panel that calls every refusal too short sends somebody who
 * typed too much to type more.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, never } from "./page.js";

answering(() => never());

const { tooShortOrTooLong } = await import("../../interface/app/panels.js");
const { t } = await import("../../interface/strings.js");

/** The rule as /api/session states it. */
const RULE = { smallest: 8, largest: 128 };

test("a password over the largest length is called too long", () => {
  assert.equal(tooShortOrTooLong("x".repeat(129), RULE),
               t("ask.password.too-long", { most: 128 }));
});

test("one under the smallest is called too short", () => {
  assert.equal(tooShortOrTooLong("short", RULE), t("ask.password.too-short"));
});

test("characters are counted as the service counts them", () => {
  /* Ninety emoji are 180 units of a JavaScript string and ninety characters
     to the service, which is within the rule. */
  assert.equal(tooShortOrTooLong("😀".repeat(90), RULE), t("ask.password.too-short"));
});
