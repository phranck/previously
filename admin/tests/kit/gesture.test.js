/**
 * gesture: one press of the pointer, followed until it is let go, and reported
 * as having ended exactly once.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { kit, lay } from "./desk.js";

test("a gesture ends once, whatever the browser sends after it", () => {
  const handle = lay("<div></div>");
  const ended = [];
  kit.gesture(handle, () => {}, () => ({}), (start, event) => ended.push(event.type));
  const at = { bubbles: true, pointerId: 1, clientX: 0, clientY: 0 };

  handle.dispatchEvent(new PointerEvent("pointerdown", at));
  handle.dispatchEvent(new PointerEvent("pointerup", at));
  handle.dispatchEvent(new PointerEvent("pointercancel", at));

  assert.deepEqual(ended, ["pointerup"]);
});
