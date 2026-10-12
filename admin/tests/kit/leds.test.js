/**
 * nx-leds lights as many lamps from the left as its share is of the row.
 *
 * Activity Monitor draws one of these per core and one for memory, twice a
 * second, and the row is the whole of what somebody reads off it. A row that
 * lights from the wrong end, rounds the wrong way or keeps lamps lit from the
 * last reading shows a machine doing something it is not.
 *
 * A row follows a new share over a moment rather than jumping to it, and
 * shows it at once where the reader has asked for less movement. Every test
 * here but the last two asks for less movement, because what they look at is
 * where the row ends up.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { kit, lay } from "./desk.js";

/** @returns {number[]} Which lamps of a row are lit, by their place in it. */
function litLamps(row) {
  return [...row.querySelectorAll(".led")]
    .flatMap((lamp, index) => (lamp.hasAttribute("lit") ? [index] : []));
}

/**
 * Says whether the reader has asked for less movement, as a browser's setting
 * would.
 * @param {boolean} less
 */
function askForLessMovement(less) {
  window.happyDOM.settings.device.prefersReducedMotion = less ? "reduce" : "no-preference";
}

/** @param {number} ms @returns {Promise<void>} Once that long has passed. */
function after(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

askForLessMovement(true);

test("a row is as long as it says, and twenty where it does not", () => {
  assert.equal(lay(`<nx-leds lamps="4"></nx-leds>`).querySelectorAll(".led").length, 4);
  assert.equal(lay(`<nx-leds></nx-leds>`).querySelectorAll(".led").length,
               kit.LEDS_IN_A_ROW);
});

test("half lights the first half, from the left", () => {
  const row = lay(`<nx-leds lamps="10"></nx-leds>`);

  row.value = 50;

  assert.deepEqual(litLamps(row), [0, 1, 2, 3, 4]);
});

test("a share is rounded to the nearest lamp", () => {
  const row = lay(`<nx-leds lamps="20"></nx-leds>`);

  /* One lamp is five per cent of twenty, so 12 is 2.4 lamps and 13 is 2.6. */
  row.value = 12;
  assert.equal(litLamps(row).length, 2);
  row.value = 13;
  assert.equal(litLamps(row).length, 3);
});

test("a falling share puts out the lamps it no longer reaches", () => {
  const row = lay(`<nx-leds lamps="10"></nx-leds>`);

  row.value = 90;
  row.value = 20;

  assert.deepEqual(litLamps(row), [0, 1]);
});

test("nothing is lit beyond either end of the row", () => {
  const row = lay(`<nx-leds lamps="10"></nx-leds>`);

  /* The emulator runs two threads with a NeXTdimension and reads above a
     hundred per cent of one core, which is ordinary and fills the row. */
  row.value = 150;
  assert.equal(litLamps(row).length, 10);
  assert.equal(row.getAttribute("aria-valuenow"), "100");
  row.value = -5;
  assert.equal(litLamps(row).length, 0);
});

test("a reading that is not there lights nothing and states no value", () => {
  const row = lay(`<nx-leds lamps="10"></nx-leds>`);
  row.value = 70;

  row.value = null;

  assert.deepEqual(litLamps(row), []);
  assert.equal(row.hasAttribute("aria-valuenow"), false);
});

test("a row filled in before it is on the page is drawn when it arrives", () => {
  lay("");
  const row = document.createElement("nx-leds");
  row.setAttribute("lamps", "4");
  row.value = 100;
  row.says = "100%";

  document.body.append(row);

  assert.deepEqual(litLamps(row), [0, 1, 2, 3]);
  assert.equal(row.querySelector(".says").textContent, "100%");
});

test("the widest a row will say reaches its figure, before it is on the page or after", () => {
  /* The figure takes the room of that and stands against its right edge, so a
     reading that gains a digit leaves its sign where it was. Where the figure
     ends is for a browser to measure. That the figure is told is for this. */
  lay("");
  const early = document.createElement("nx-leds");
  early.widest = "100%";
  document.body.append(early);
  const late = lay(`<nx-leds></nx-leds>`);
  late.widest = "100%";

  for (const row of [early, late]) {
    assert.equal(row.querySelector(".says").dataset.widest, "100%");
    assert.equal(row.querySelector(".says").textContent, "");
  }
});

test("a new share is followed rather than jumped to", async (context) => {
  askForLessMovement(false);
  context.after(() => askForLessMovement(true));
  const row = lay(`<nx-leds lamps="10"></nx-leds>`);

  row.value = 100;

  /* Nothing moves before the first frame, and the reading is stated at once. */
  assert.deepEqual(litLamps(row), []);
  assert.equal(row.getAttribute("aria-valuenow"), "100");
  /* A third of the way and more within the first time constant, and not all
     of it. */
  await after(60);
  const underway = litLamps(row).length;
  assert.ok(underway > 0 && underway < 10, `${underway} of 10 lamps lit after 60 ms`);
  await after(1000);
  assert.equal(litLamps(row).length, 10);
});

test("a falling share is followed down as well", async (context) => {
  const row = lay(`<nx-leds lamps="10"></nx-leds>`);
  row.value = 100;
  askForLessMovement(false);
  context.after(() => askForLessMovement(true));

  row.value = 0;

  await after(60);
  const underway = litLamps(row).length;
  assert.ok(underway > 0 && underway < 10, `${underway} of 10 lamps lit after 60 ms`);
  await after(1000);
  assert.deepEqual(litLamps(row), []);
});
