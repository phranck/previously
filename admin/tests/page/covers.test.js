/**
 * How a cover is cut: the front of a spread, and inside that the frame the
 * cover is printed in. Settled on the mockup of #752 against archive.org's
 * thumbnail of nebula-se, whose front is cut to columns 98 to 191 and rows 2
 * to 96 of 192 by 100.
 *
 * The pictures here are made of lightness values, which is what the page reads
 * out of a canvas, so the rule is tested without a browser.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

const { frameIn } = await import("../../interface/app/covers.js");

const WHITE = 255;
const GRAY = 150;
const BLACK = 0;

/**
 * A picture as lightness values, every pixel `ground`, with what `draw` puts
 * on it.
 * @param {number} width
 * @param {number} height
 * @param {number} ground
 * @param {(set: (x: number, y: number, value: number) => void) => void} draw
 * @returns {Uint8Array}
 */
function picture(width, height, ground, draw = () => {}) {
  const lightness = new Uint8Array(width * height).fill(ground);
  draw((x, y, value) => { lightness[y * width + x] = value; });
  return lightness;
}

/** Draws a rectangle's edge one pixel wide, its corners included. */
function frame(set, left, top, right, bottom) {
  for (let x = left; x <= right; x += 1) { set(x, top, BLACK); set(x, bottom, BLACK); }
  for (let y = top; y <= bottom; y += 1) { set(left, y, BLACK); set(right, y, BLACK); }
}

test("a spread shows its front, cut to the frame it is printed in", () => {
  /* Twice as wide as tall: the back on the left, and on the right a white
     margin round a black frame round the front. */
  const lightness = picture(40, 20, WHITE, (set) => {
    for (let y = 0; y < 20; y += 1) for (let x = 0; x < 20; x += 1) set(x, y, GRAY);
    for (let y = 2; y < 18; y += 1) for (let x = 22; x < 38; x += 1) set(x, y, GRAY);
    frame(set, 21, 1, 38, 18);
  });

  assert.deepEqual(frameIn(lightness, 40, 20), { left: 21, top: 1, width: 18, height: 18 });
});

test("a cover whose dark edges lie on the picture's own edges stays whole", () => {
  const lightness = picture(20, 20, GRAY, (set) => frame(set, 0, 0, 19, 19));

  assert.deepEqual(frameIn(lightness, 20, 20), { left: 0, top: 0, width: 20, height: 20 });
});

test("a cover without a frame stays as it is", () => {
  assert.deepEqual(frameIn(picture(20, 20, GRAY), 20, 20),
                   { left: 0, top: 0, width: 20, height: 20 });
});

test("a dark line in the middle is part of the picture, not its frame", () => {
  const lightness = picture(20, 20, WHITE, (set) => {
    for (let y = 0; y < 20; y += 1) set(10, y, BLACK);
  });

  assert.deepEqual(frameIn(lightness, 20, 20), { left: 0, top: 0, width: 20, height: 20 });
});

test("a picture not quite twice as wide is no spread", () => {
  /* 1.5 to 1, under the 1.6 a spread is at least. */
  const lightness = picture(30, 20, GRAY);

  assert.deepEqual(frameIn(lightness, 30, 20), { left: 0, top: 0, width: 30, height: 20 });
});
