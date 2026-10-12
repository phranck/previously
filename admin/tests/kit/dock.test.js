/**
 * nx-dock: a column of slots, one tile high, where a tile can only land on a
 * slot that is free, and which an application joins and leaves by being
 * carried.
 *
 * The Workspace tile holds the head of the column. Every other tile goes back
 * to where it was put, or takes the first free slot when it has no place or
 * its place is taken. A tile carried off the column leaves the dock where its
 * application is not running, or where Command is held. An application's icon
 * dragged from the File Viewer, or its tile carried from the floor, onto a
 * free slot asks for a tile there.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay, measure, remembered } from "./desk.js";

const MARKUP = `<nx-dock>
  <nx-tile icon="Workspace" fixed></nx-tile>
  <nx-tile icon="Terminal" name="terminal" value="/Apps/Terminal.app" idle></nx-tile>
  <nx-tile icon="Grab" name="grab" value="/Apps/Grab.app"></nx-tile>
</nx-dock>`;

/** How wide the desk is, which is what desk.js registers the document at. */
const DESK_WIDTH = 1120;

/** @returns {number} The slot the tile with that name stands on. */
function slotOf(dock, name) {
  return dock.slotOf(dock.querySelector(`nx-tile[name="${name}"]`));
}

/**
 * Gives the dock and its tiles the places a browser would lay them out at,
 * which the document cannot work out for itself: the column against the right
 * edge, and each tile on the slot it stands on.
 * @param {Element} dock - The column.
 * @returns {Element} The same column.
 */
function placeTheDock(dock) {
  const left = DESK_WIDTH - dock.step;
  measure(dock, {
    getBoundingClientRect: () => ({ left, top: 0, width: dock.step, height: 832 }),
  });
  for (const tile of dock.tiles) {
    measure(tile, {
      getBoundingClientRect: () => ({
        left, top: (dock.slotOf(tile) - 1) * dock.step, width: dock.step, height: dock.step,
      }),
    });
  }
  return dock;
}

/** @returns {{x: number, y: number}} The middle of an element as it is measured. */
function middleOf(element) {
  const rect = element.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

/**
 * Picks a tile up and moves it by a distance, the way a hand does: down on it
 * and a move, with the button still held.
 * @param {Element} tile - What is carried.
 * @param {number} across - How far right, in pixels, or left where negative.
 * @param {number} down - How far down, or up where negative.
 * @param {boolean} [command] - Whether Command is held.
 * @returns {(command?: boolean) => void} Lets it go where it was carried to.
 */
function pickUp(tile, across, down, command = false) {
  const from = middleOf(tile);
  const at = (x, y, metaKey) =>
    ({ bubbles: true, pointerId: 1, clientX: x, clientY: y, metaKey });
  tile.dispatchEvent(new PointerEvent("pointerdown", at(from.x, from.y, false)));
  tile.dispatchEvent(new PointerEvent("pointermove", at(from.x + across, from.y + down, command)));
  return (held = command) =>
    tile.dispatchEvent(new PointerEvent("pointerup", at(from.x + across, from.y + down, held)));
}

/** Carries a tile by a distance and lets it go there. */
function carry(tile, across, down, command = false) {
  pickUp(tile, across, down, command)();
}

/** @returns {Promise<void>} Once the frame a move waits for has been drawn. */
function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

/**
 * Raises a drag event the way a browser does, which happy-dom's own DragEvent
 * cannot: it carries neither a place nor a DataTransfer.
 * @param {Element} target - Where it happens.
 * @param {string} type - Which part of the drag.
 * @param {object} [where] - The pointer, as the viewport has it.
 * @param {DataTransfer} [transfer] - What the drag carries. A browser hands
 *   the same one to every event of one drag, so a test that reads what the
 *   source offered beside what the target asked for passes one in.
 * @returns {Event} The event, so a test can read whether it was taken.
 */
function drag(target, type, { x = 0, y = 0 } = {}, transfer = new DataTransfer()) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y });
  Object.defineProperty(event, "dataTransfer", { value: transfer });
  target.dispatchEvent(event);
  return event;
}

/** @returns {Array<object>} Every `name` event the dock raises from now on. */
function heard(dock, name) {
  const caught = [];
  dock.addEventListener(name, (event) => caught.push(event.detail));
  return caught;
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
  const dock = placeTheDock(lay(MARKUP));
  const terminal = dock.querySelector('nx-tile[name="terminal"]');

  carry(terminal, 0, dock.step * 4);

  assert.equal(dock.slotOf(terminal), 6);
  assert.equal(remembered().dock.places.terminal, 6);
});

test("the dock and the floor take the pointer on their tiles and nowhere else", () => {
  /* Both lie above the windows and run the height or the width of the screen.
     A window reaching into the strip along the foot had its resize bar under
     the floor, which took the pointer although nothing lay there. */
  lay(`<main>${MARKUP}<nx-floor><nx-tile icon="Preview" opens="preview"></nx-tile></nx-floor></main>`);

  for (const holder of ["nx-dock", "nx-floor"]) {
    const element = document.querySelector(holder);
    assert.equal(getComputedStyle(element).pointerEvents, "none", holder);
    for (const tile of element.querySelectorAll("nx-tile")) {
      assert.equal(getComputedStyle(tile).pointerEvents, "auto", holder + " tile");
    }
  }
});

test("a tile carried onto a slot that is taken goes back where it came from", () => {
  const dock = placeTheDock(lay(MARKUP));
  const terminal = dock.querySelector('nx-tile[name="terminal"]');

  carry(terminal, 0, dock.step);

  assert.equal(slotOf(dock, "terminal"), 2);
  assert.equal(slotOf(dock, "grab"), 3);
});

test("a tile whose application is not running leaves the dock when let go off the column", () => {
  const dock = placeTheDock(lay(MARKUP, { dock: { places: { terminal: 4, grab: 3 } } }));
  const left = heard(dock, "nx-undock");

  carry(dock.querySelector('nx-tile[name="terminal"]'), -200, 0);

  assert.ok(!dock.querySelector('nx-tile[name="terminal"]'), "the tile is still in the dock");
  assert.deepEqual(left, [{ value: "/Apps/Terminal.app" }]);
  /* Its place goes with it, so an application put back later lands where it
     is let go rather than where it once stood. */
  assert.deepEqual(remembered().dock.places, { grab: 3 });
});

test("a tile whose application is running leaves the dock only with Command held", () => {
  const dock = placeTheDock(lay(MARKUP));
  const grab = dock.querySelector('nx-tile[name="grab"]');
  const left = heard(dock, "nx-undock");

  carry(grab, -200, 0);
  assert.equal(slotOf(dock, "grab"), 3);
  assert.deepEqual(left, []);

  carry(grab, -200, 0, true);
  assert.ok(!dock.querySelector('nx-tile[name="grab"]'), "the tile is still in the dock");
  assert.deepEqual(left, [{ value: "/Apps/Grab.app" }]);
});

test("the copy left in the slot goes only where letting go would take the tile out", async () => {
  const dock = placeTheDock(lay(MARKUP));
  const terminal = dock.querySelector('nx-tile[name="terminal"]');
  const grab = dock.querySelector('nx-tile[name="grab"]');

  /* Not running, so off the column it would leave. */
  const letTerminalGo = pickUp(terminal, -200, 0);
  await nextFrame();
  assert.ok(terminal.hasAttribute("carried"));
  assert.ok(terminal.hasAttribute("leaving"));
  /* A picture of it follows the pointer, and that picture is not in the dock. */
  assert.equal(document.querySelectorAll("nx-tile[picture]").length, 1);
  assert.equal(dock.querySelectorAll("nx-tile[picture]").length, 0);
  letTerminalGo();
  assert.equal(document.querySelectorAll("nx-tile[picture]").length, 0);

  /* Running, so without Command it stays, and its copy stays with it. */
  const letGrabGo = pickUp(grab, -200, 0);
  await nextFrame();
  assert.ok(grab.hasAttribute("carried"));
  assert.ok(!grab.hasAttribute("leaving"));
  letGrabGo();
  assert.ok(!grab.hasAttribute("carried"));
});

test("an application dragged from the File Viewer asks for a tile on the free slot under it", () => {
  lay(`<main>${MARKUP}<nx-thing icon="Preview" label="Preview.app" value="/Apps/Preview.app" dockable></nx-thing></main>`);
  const dock = placeTheDock(document.querySelector("nx-dock"));
  const asked = heard(dock, "nx-dock");
  const sixth = { x: DESK_WIDTH - dock.step / 2, y: 5 * dock.step + dock.step / 2 };

  drag(document.querySelector("nx-thing"), "dragstart");
  assert.ok(dock.hasAttribute("receiving"));

  const over = drag(dock, "dragover", sixth);
  assert.ok(over.defaultPrevented, "the dock refused a free slot");
  const mark = dock.querySelector(".slot");
  assert.equal(mark.style.gridRow, "6");
  assert.match(mark.querySelector(".art").style.backgroundImage, /--Preview\b/);

  drag(dock, "drop", sixth);
  assert.deepEqual(asked, [{ value: "/Apps/Preview.app", slot: 6 }]);
  assert.ok(!dock.hasAttribute("receiving"));
  assert.ok(!dock.querySelector(".slot"), "the slot is still marked");
});

test("the dock asks a drag from the File Viewer for a copy, which is what Safari offers", () => {
  /* Safari on a Mac offers a drag inside the page as a copy, a move or a
     generic operation. A target that asks for anything else is refused the
     drop, and the icon slides back where it came from. */
  lay(`<main>${MARKUP}<nx-thing icon="Preview" value="/Apps/Preview.app" dockable></nx-thing></main>`);
  const dock = placeTheDock(document.querySelector("nx-dock"));
  const sixth = { x: DESK_WIDTH - dock.step / 2, y: 5 * dock.step + dock.step / 2 };
  const transfer = new DataTransfer();

  drag(document.querySelector("nx-thing"), "dragstart", {}, transfer);
  drag(dock, "dragover", sixth, transfer);

  assert.equal(transfer.dropEffect, "copy");
  assert.equal(transfer.effectAllowed, "copy");
});

test("an occupied slot, something that is not an application, and one already docked are refused", () => {
  lay(`<main>${MARKUP}
    <nx-thing icon="Preview" value="/Apps/Preview.app" dockable></nx-thing>
    <nx-thing icon="folder" value="/Machines"></nx-thing>
    <nx-thing icon="Grab" value="/Apps/Grab.app" dockable></nx-thing>
  </main>`);
  const dock = placeTheDock(document.querySelector("nx-dock"));
  const [preview, folder, grab] = document.querySelectorAll("nx-thing");
  const third = { x: DESK_WIDTH - dock.step / 2, y: 2 * dock.step + dock.step / 2 };
  const sixth = { x: DESK_WIDTH - dock.step / 2, y: 5 * dock.step + dock.step / 2 };

  drag(preview, "dragstart");
  assert.ok(!drag(dock, "dragover", third).defaultPrevented, "an occupied slot took it");
  drag(preview, "dragend");

  for (const thing of [folder, grab]) {
    drag(thing, "dragstart");
    assert.ok(!dock.hasAttribute("receiving"), thing.getAttribute("value"));
    assert.ok(!drag(dock, "dragover", sixth).defaultPrevented, thing.getAttribute("value"));
    drag(thing, "dragend");
  }
});

test("a tile taken into the column stands where it was let go and is remembered there", () => {
  const dock = lay(MARKUP);
  const preview = document.createElement("nx-tile");
  preview.setAttribute("icon", "Preview");
  preview.setAttribute("name", "preview");

  dock.take(preview, 5);

  assert.equal(slotOf(dock, "preview"), 5);
  assert.equal(remembered().dock.places.preview, 5);
});

test("a tile on the floor carried onto a free slot asks for a tile there", async () => {
  lay(`<main>${MARKUP}<nx-floor></nx-floor></main>`);
  const dock = placeTheDock(document.querySelector("nx-dock"));
  const floor = document.querySelector("nx-floor");
  await floor.show([{ icon: "Preview", opens: "preview", value: "/Apps/Preview.app" }]);
  const tile = floor.querySelector("nx-tile");
  measure(tile, {
    getBoundingClientRect: () => ({ left: 0, top: 832 - dock.step, width: dock.step, height: dock.step }),
  });
  const asked = heard(dock, "nx-dock");
  const from = middleOf(tile);

  /* Onto the column, short of it, and onto the fourth slot. */
  carry(tile, DESK_WIDTH - dock.step - from.x - 10, 0);
  assert.deepEqual(asked, []);
  carry(tile, DESK_WIDTH - dock.step / 2 - from.x, 3 * dock.step + dock.step / 2 - from.y);
  assert.deepEqual(asked, [{ value: "/Apps/Preview.app", slot: 4 }]);
});
