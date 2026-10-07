/**
 * nx-scroller drives the view it wraps.
 *
 * The bars are prepended to the scroller, so once they exist its first child
 * is a bar. A scroller that takes its view after building them drives its own
 * bar instead, and the File Viewer then shows a trough with no knob whatever is
 * in the folder, with every other test still green.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay, measure } from "./desk.js";

const MARKUP = `<nx-scroller><div class="list"><p>one</p><p>two</p></div></nx-scroller>`;

test("the view it drives is the element it wraps, not one of its bars", () => {
  const scroller = lay(MARKUP);

  assert.equal(scroller.view.className, "list");
  assert.equal(scroller.firstElementChild.classList.contains("bar"), true);
});

test("a view with more than it shows gets a knob and both arrows", () => {
  const scroller = lay(MARKUP);
  measure(scroller.view, { scrollHeight: 400, clientHeight: 100 });

  scroller.refresh();

  const { knob, arrows } = scroller.bars.down;
  assert.equal(knob.hidden, false);
  assert.equal(arrows.hidden, false);
});

test("a view that shows everything keeps its trough and loses its knob", () => {
  const scroller = lay(MARKUP);
  measure(scroller.view, { scrollHeight: 100, clientHeight: 100 });

  scroller.refresh();

  const { trough, knob, arrows } = scroller.bars.down;
  assert.equal(trough.isConnected, true);
  assert.equal(knob.hidden, true);
  assert.equal(arrows.hidden, true);
});

test("the knob stands as far down its trough as the view is scrolled", () => {
  const scroller = lay(MARKUP);
  const { trough, knob } = scroller.bars.down;
  measure(trough, { clientHeight: 200 });
  measure(scroller.view, { scrollHeight: 400, clientHeight: 100, scrollTop: 300 });

  scroller.refresh();

  /* A quarter of the content shows, so the knob is a quarter of the trough,
     and the view is scrolled to its end, so the knob stands at the foot. */
  assert.equal(knob.style.height, "50px");
  assert.equal(knob.style.top, "150px");
});

test("a scroller asked for both bars builds one along its foot as well", () => {
  const scroller = lay(`<nx-scroller bars="down across"><div class="list"></div></nx-scroller>`);

  assert.deepEqual(Object.keys(scroller.bars), ["down", "across"]);
  assert.equal(scroller.view.className, "list");
});
