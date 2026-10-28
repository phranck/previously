/**
 * nx-ask: the attention panel, and where typing goes while it asks for
 * something typed.
 *
 * Measured in WebKit on 28 October 2026: a click on the panel's text moved the
 * focus off its field onto the body, and what was typed next went nowhere.
 * That click is the one somebody makes to bring the window forward after
 * dropping an address on it from another window.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay } from "./desk.js";

/** @returns {any} A panel on the desk, asking for a password. */
function asking(field = true) {
  const panel = /** @type {any} */ (lay("<nx-ask></nx-ask>"));
  const question = { name: "Password", text: ["Type it."], confirm: "Set", cancel: "Cancel" };
  if (field) panel.askFor({ ...question, secret: true });
  else panel.ask(question);
  return panel;
}

/** @returns {boolean} Whether the panel's field holds the focus. Compared
 *  here rather than handed to assert as two elements, because a failing
 *  assertion prints both, and printing an element of the desk prints the
 *  whole desk, which takes longer than any test may. */
function fieldHasTheFocus(panel) {
  return document.activeElement === panel.parts.entry;
}

/** @returns {MouseEvent} A press on that element, as dispatched. */
function press(element) {
  const event = new MouseEvent("mousedown", { bubbles: true, cancelable: true });
  element.dispatchEvent(event);
  return event;
}

test("the field has the focus the moment the panel asks", () => {
  const panel = asking();

  assert.equal(fieldHasTheFocus(panel), true);
});

test("a press on the panel's text leaves the focus in the field", () => {
  const panel = asking();

  const event = press(panel.parts.lines);

  assert.equal(event.defaultPrevented, true);
  assert.equal(fieldHasTheFocus(panel), true);
});

test("a press on a button is the button's", () => {
  const panel = asking();

  assert.equal(press(panel.parts.safe).defaultPrevented, false);
});

test("coming back to the window puts the focus back into the field", () => {
  const panel = asking();
  panel.parts.entry.blur();

  dispatchEvent(new Event("focus"));

  assert.equal(fieldHasTheFocus(panel), true);
});

test("a panel without a field keeps nothing", () => {
  const panel = asking(false);

  assert.equal(press(panel.parts.lines).defaultPrevented, false);
});
