/**
 * nx-dock: a column of slots, one tile high, where a tile can only land on a
 * slot that is free.
 *
 * The Workspace tile holds the head of the column. Every other tile goes back
 * to where it was put, or takes the first free slot when it has no place or
 * its place is taken.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay, measure, remembered } from "./desk.js";

const MARKUP = `<nx-dock>
  <nx-tile icon="Workspace" fixed></nx-tile>
  <nx-tile icon="Terminal" name="terminal"></nx-tile>
  <nx-tile icon="Grab" name="grab"></nx-tile>
</nx-dock>`;

/** @returns {number} The slot the tile with that name stands on. */
function slotOf(dock, name) {
  return dock.slotOf(dock.querySelector(`nx-tile[name="${name}"]`));
}

/**
 * Carries a tile down the column by a distance, the way a hand does: down on
 * it, a move, and up again.
 *
 * The tile is first given the height its slot stands at, because the gesture
 * starts from there and the document lays nothing out.
 *
 * @param {Element} dock - The column.
 * @param {Element} tile - What is carried.
 * @param {number} distance - How far down, in pixels.
 */
function carry(dock, tile, distance) {
  measure(tile, { offsetTop: (dock.slotOf(tile) - 1) * dock.step });
  const at = (y) => ({ bubbles: true, pointerId: 1, clientX: 30, clientY: y });
  tile.dispatchEvent(new PointerEvent("pointerdown", at(10)));
  tile.dispatchEvent(new PointerEvent("pointermove", at(10 + distance)));
  tile.dispatchEvent(new PointerEvent("pointerup", at(10 + distance)));
}

test("the Workspace tile holds the head and the others take the next free slots", () => {
  const dock = lay(MARKUP);

  assert.equal(dock.slotOf(dock.querySelector("nx-tile[fixed]")), 1);
  assert.equal(slotOf(dock, "terminal"), 2);
  assert.equal(slotOf(dock, "grab"), 3);
});

test("a tile goes back to where it was put, and a tile without a place goes round it", () => {
  const dock = lay(MARKUP, { dock: { places: { grab: 2 } } });

  assert.equal(slotOf(dock, "grab"), 2);
  assert.equal(slotOf(dock, "terminal"), 3);
});

test("a tile carried onto a free slot lands there and is remembered there", () => {
  const dock = lay(MARKUP);
  const terminal = dock.querySelector('nx-tile[name="terminal"]');

  carry(dock, terminal, dock.step * 4);

  assert.equal(dock.slotOf(terminal), 6);
  assert.equal(remembered().dock.places.terminal, 6);
});

test("a tile carried onto a slot that is taken goes back where it came from", () => {
  const dock = lay(MARKUP);
  const terminal = dock.querySelector('nx-tile[name="terminal"]');

  carry(dock, terminal, dock.step);

  assert.equal(slotOf(dock, "terminal"), 2);
  assert.equal(slotOf(dock, "grab"), 3);
});
