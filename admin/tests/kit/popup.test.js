/**
 * nx-popup: a button labeled with what is chosen, and the list that comes up
 * while it is held.
 *
 * happy-dom lays nothing out, so where the pointer is let go is said by
 * standing in for `elementFromPoint`, which is what the element asks.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay } from "./desk.js";

const VERSIONS = [
  { value: "1.3.1", label: "1.3.1" },
  { value: "1.3.0", label: "1.3.0" },
  { value: "1.2.6", label: "1.2.6" },
];

/** @returns {any} A pop-up on the desk, offering the three versions. */
function popup(value) {
  const element = /** @type {any} */ (lay("<nx-popup></nx-popup>"));
  element.offer(VERSIONS, value);
  return element;
}

/**
 * Holds the button down and lets go over an item.
 * @param {any} element - The pop-up.
 * @param {string|null} over - The value of the item let go over, or null for
 *   letting go somewhere else.
 * @returns {string[]} What `nx-pick` carried, each time it was raised.
 */
function holdAndLetGo(element, over) {
  const picked = [];
  element.addEventListener("nx-pick", (event) => picked.push(event.detail.value));
  element.button.dispatchEvent(new PointerEvent("pointerdown", { button: 0, bubbles: true }));

  const item = over === null ? null
    : document.querySelector(`.popup-list nx-menu-item[data-value="${over}"]`);
  const asked = document.elementFromPoint;
  document.elementFromPoint = () => item;
  try {
    dispatchEvent(new PointerEvent("pointerup", { button: 0 }));
  } finally {
    document.elementFromPoint = asked;
  }
  return picked;
}

test("the button says what is chosen", () => {
  assert.equal(popup("1.3.0").label.textContent, "1.3.0");
});

test("a value that is not offered leaves the first chosen", () => {
  assert.equal(popup("9.9.9").value, "1.3.1");
});

test("holding the button brings up every choice, with the chosen one lit", () => {
  const element = popup("1.3.0");

  element.button.dispatchEvent(new PointerEvent("pointerdown", { button: 0, bubbles: true }));
  const items = [...document.querySelectorAll(".popup-list nx-menu-item")];

  assert.deepEqual(items.map((item) => item.textContent), ["1.3.1", "1.3.0", "1.2.6"]);
  assert.deepEqual(items.map((item) => item.hasAttribute("lit")), [false, true, false]);
  dispatchEvent(new PointerEvent("pointerup", { button: 0 }));
});

test("letting go over another choice picks it, once", () => {
  const element = popup("1.3.1");

  const picked = holdAndLetGo(element, "1.2.6");

  assert.deepEqual(picked, ["1.2.6"]);
  assert.equal(element.value, "1.2.6");
  assert.equal(element.label.textContent, "1.2.6");
});

test("letting go over the chosen one or anywhere else changes nothing", () => {
  const element = popup("1.3.1");

  assert.deepEqual(holdAndLetGo(element, "1.3.1"), []);
  assert.deepEqual(holdAndLetGo(element, null), []);
  assert.equal(element.value, "1.3.1");
});

test("the list goes when the button is let go", () => {
  holdAndLetGo(popup("1.3.1"), null);

  assert.equal(document.querySelector(".popup-list"), null);
});

test("with nothing to choose between the button does nothing", () => {
  const element = /** @type {any} */ (lay("<nx-popup></nx-popup>"));
  element.offer([{ value: "1.3.1", label: "1.3.1" }]);

  element.button.dispatchEvent(new PointerEvent("pointerdown", { button: 0, bubbles: true }));

  assert.equal(element.button.disabled, true);
  assert.equal(document.querySelector(".popup-list"), null);
});
