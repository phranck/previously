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

test("a view one pixel over in either direction gets no knob, which is rounding", () => {
  /* Both figures are rounded to whole pixels from fractions wherever the desk
     is drawn at 125, 150 or 175 per cent, and WebKit then reports the content
     one over a view it fits in: a File Viewer path that fills its band exactly,
     and a folder far shorter than its band. */
  const scroller = lay(`<nx-scroller bars="down across"><div class="list"></div></nx-scroller>`);
  measure(scroller.view, { scrollHeight: 194, clientHeight: 193,
                           scrollWidth: 324, clientWidth: 323 });

  scroller.refresh();

  assert.equal(scroller.bars.down.knob.hidden, true);
  assert.equal(scroller.bars.down.arrows.hidden, true);
  assert.equal(scroller.bars.across.knob.hidden, true);
  assert.equal(scroller.bars.across.arrows.hidden, true);
});

test("padding that alone runs past the view is no reason for a knob", () => {
  /* The window leaves the band a few pixels short of the padding under the
     last row of icons. Everything in it shows, and a knob would say otherwise. */
  const scroller = lay(`<nx-scroller><div class="list" style="padding-bottom: 8px"></div></nx-scroller>`);
  measure(scroller.view, { scrollHeight: 189, clientHeight: 187 });

  scroller.refresh();

  assert.equal(scroller.bars.down.knob.hidden, true);
});

test("content past the padding by more than a rounding gets a knob", () => {
  const scroller = lay(`<nx-scroller><div class="list" style="padding-bottom: 8px"></div></nx-scroller>`);
  measure(scroller.view, { scrollHeight: 197, clientHeight: 187 });

  scroller.refresh();

  assert.equal(scroller.bars.down.knob.hidden, false);
  assert.equal(scroller.bars.down.arrows.hidden, false);
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
