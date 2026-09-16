const SVG_NS = "http://www.w3.org/2000/svg";
const STORE = "nextstep-workspace:v4";

/* --- what the desk remembers -------------------------------------------- */

/** @returns {object} Everything saved about the desk, or an empty record. */
function readState() {
  try { return JSON.parse(localStorage.getItem(STORE)) ?? {}; }
  catch { return {}; }
}

/**
 * Writes one element's state, leaving every other one untouched.
 * @param {string} name - What the element calls itself.
 * @param {object} state - The keys to merge in.
 */
function remember(name, state) {
  const all = readState();
  all[name] = { ...(all[name] ?? {}), ...state };
  localStorage.setItem(STORE, JSON.stringify(all));
}

/** @param {string} name @returns {object} That element's saved state. */
function recall(name) {
  return readState()[name] ?? {};
}

/**
 * Points an element at one of the pictures build.py baked into the stylesheet.
 * @param {HTMLElement} el
 * @param {string} name - The picture's name, which is its file's stem.
 */
function showArt(el, name) {
  el.style.backgroundImage = "var(--" + name + ")";
}

/**
 * Runs a pointer gesture and reports the result when it ends.
 * @param {HTMLElement} handle - Where the gesture starts.
 * @param {(event: PointerEvent, start: object) => void} onMove
 * @param {(event: PointerEvent) => object} onStart - Whatever the mover needs
 *   to know about the moment the gesture began.
 * @param {(start: object) => void} [onEnd] - Given what onStart returned,
 *   which by then carries whatever the moves wrote into it.
 */
function gesture(handle, onMove, onStart, onEnd) {
  handle.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
    /* Without this the browser starts its own text selection under the
       pointer, and dragging a window paints half the desk blue. */
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    const start = onStart(event);

    /* A pointer reports faster than the screen redraws, so the moves are
       coalesced into one update per frame. Everything beyond the last one in
       a frame is work whose result is painted over before anybody sees it. */
    let latest = null;
    let frame = 0;

    const apply = () => {
      frame = 0;
      onMove(latest, start);
    };

    const move = (moveEvent) => {
      latest = moveEvent;
      if (!frame) frame = requestAnimationFrame(apply);
    };

    const finish = () => {
      handle.removeEventListener("pointermove", move);
      /* The last position has to land before anything saves it, so a frame
         still owed is run now rather than cancelled. */
      if (frame) {
        cancelAnimationFrame(frame);
        apply();
      }
      onEnd?.(start);
    };

    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", finish, { once: true });
    handle.addEventListener("pointercancel", finish, { once: true });
  });
}

/**
 * Moves an element by its handle, and settles it where it was let go.
 *
 * Whilst the gesture runs the element is moved with a transform, which the
 * compositor can do without laying the page out again. Its left and top are
 * written once, at the end, so everything that reads them afterwards sees a
 * plain position and knows nothing about how it got there.
 *
 * @param {HTMLElement} element - What moves.
 * @param {HTMLElement} handle - What is grabbed.
 * @param {object} hooks
 * @param {() => void} [hooks.onGrab] - Called as the gesture begins.
 * @param {() => void} [hooks.onSettled] - Called once the position is written.
 */
function draggable(element, handle, { onGrab, onSettled } = {}) {
  gesture(handle,
    (event, start) => {
      /* Never past the top or left edge, and never wholly behind the dock. */
      start.left = Math.max(0, Math.min(event.clientX - start.grabX, innerWidth - 90));
      start.top = Math.max(0, Math.min(event.clientY - start.grabY, innerHeight - 24));
      element.style.transform =
        `translate(${start.left - start.fromLeft}px, ${start.top - start.fromTop}px)`;
    },
    (event) => {
      onGrab?.();
      const fromLeft = element.offsetLeft;
      const fromTop = element.offsetTop;
      return {
        grabX: event.clientX - fromLeft, grabY: event.clientY - fromTop,
        fromLeft, fromTop, left: fromLeft, top: fromTop,
      };
    },
    (start) => {
      element.style.transform = "";
      element.style.left = start.left + "px";
      element.style.top = start.top + "px";
      onSettled?.();
    });
}

/* --- the desk is not a document ------------------------------------------

   A right click here opens what the thing under the pointer offers, or
   nothing. The browser's own menu is about a document: reload it, save the
   picture, look at the source. None of that is about a machine or a window,
   and NeXTSTEP never put anything of the sort on a desk.

   Refused for the whole desk, including the fields and anything a terminal
   will hold, because one rule that holds everywhere is the only kind a person
   can rely on. What has a menu of its own opens it from its own handler. */
addEventListener("contextmenu", (event) => event.preventDefault());

/* --- the desk does not hold text -----------------------------------------

   user-select says a selection may not begin inside an element. It does not
   stop a browser that begins one anyway, and a drag across a shelf then leaves
   every label it passed highlighted in the browser's own blue.

   Refused here rather than in a stylesheet, because this holds whatever the
   browser makes of the property. A terminal is the exception: reading
   something out of it is the point of having one. */
addEventListener("selectstart", (event) => {
  if (!event.target.closest?.(".terminal")) event.preventDefault();
});

/* --- the letters beside the menu entries ---------------------------------

   NeXTSTEP drew those for Command key shortcuts. Command and Control both
   belong to the browser here, so the letter acts on its own, and three
   conditions keep that from being a nuisance: nothing held down, nothing being
   typed into, and no panel up, because a panel has a keyboard of its own and
   two answers to give with it.

   A context menu is left out. Its entries act on whatever was right clicked,
   and a key press has nothing under the pointer. */
addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (document.querySelector("nx-ask[data-open]")) return;

  const focused = document.activeElement;
  if (focused?.matches?.("input, textarea, select") || focused?.isContentEditable) return;

  const pressed = event.key.toLowerCase();
  const item = [...document.querySelectorAll("nx-menu:not([context]) nx-menu-item[key]")]
    .find((entry) => entry.getAttribute("key").toLowerCase() === pressed);
  if (!item || item.hasAttribute("disabled")) return;

  event.preventDefault();
  item.click();
});

/**
 * Puts the front window back in front and every other one behind it.
 *
 * This runs over all the windows rather than inside any one of them, because
 * being in front is a statement about all of them together: a window can only
 * make itself active by making the others inactive, and at a load none of them
 * has done that yet. Without it every title bar is drawn active, which is a
 * desk NeXTSTEP never showed.
 *
 * Without a remembered name the last open window in the markup takes it, which
 * is the one a reader would call the frontmost.
 */
function restoreFront() {
  const windows = [...document.querySelectorAll("nx-window")];
  for (const window_ of windows) window_.setAttribute("inactive", "");
  const remembered = recall("desk").front;
  const open = windows.filter((window_) => !window_.hidden);
  const front = open.find((window_) => window_.name === remembered) ?? open.at(-1);
  front?.raise();
}

/* --- pictures of things moving -------------------------------------------

   Two of them, and both are pictures rather than the things themselves: an
   icon on its way to the floor of the screen, and the way from a folder to
   the place its contents will appear. Neither is asked about by anything: a
   caller says where from and where to, and waits for it to land. */

/** How long an icon takes to reach its place on the floor. Brisk, because it
 *  is a thing moving rather than an effect: long enough to be followed by the
 *  eye and short enough that anybody waits for it. */
const FLIGHT_MS = 260;

/** How many rectangles the way is drawn with, and how long they take. Few and
 *  fast: the original drew them as quickly as the machine could and rubbed
 *  each one out again, and what is left of that is a flicker rather than a
 *  slide. */
const ZOOM_STEPS = 8;
const ZOOM_MS = 200;

/** @returns {boolean} Whether the reader has asked for less movement. */
function stillness() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Sends a picture of an icon from one place to another.
 * @param {string} icon - Which picture.
 * @param {DOMRect} from - Where it starts.
 * @param {DOMRect} to - Where it lands.
 * @returns {Promise} Settled when it has landed.
 *
 * A transform and nothing else, so this costs the compositor and not the
 * layout. Where the reader has asked for less movement there is no flight at
 * all: the tile is simply there, which is what they asked for.
 */
function fly(icon, from, to) {
  if (stillness()) return Promise.resolve();

  const ghost = document.createElement("i");
  ghost.className = "art flying";
  showArt(ghost, icon);
  ghost.style.left = to.left + "px";
  ghost.style.top = to.top + "px";
  ghost.style.width = to.width + "px";
  ghost.style.height = to.height + "px";
  document.body.append(ghost);

  const across = (from.left + from.width / 2) - (to.left + to.width / 2);
  const down = (from.top + from.height / 2) - (to.top + to.height / 2);
  const smaller = to.width ? Math.max(0.2, from.width / to.width) : 1;

  const flight = ghost.animate([
    { transform: `translate(${across}px, ${down}px) scale(${smaller})` },
    { transform: "translate(0, 0) scale(1)" },
  ], { duration: FLIGHT_MS, easing: "ease-out" });

  return flight.finished.catch(() => {}).finally(() => ghost.remove());
}



/**
 * Draws the way from one place to another, as rectangles stepping outwards.
 * @param {DOMRect} from - Where it starts, which is the mark around an icon.
 * @param {DOMRect} to - Where it ends, which is the box about to hold what
 *   was in that folder.
 * @returns {Promise} Settled when the last rectangle has gone.
 *
 * An outline rather than a filled rectangle, because a filled one would be a
 * black flash across half the window. It steps rather than slides, which is
 * what the original looks like: each rectangle was drawn as fast as the
 * machine could and rubbed out again.
 *
 * The geometry is animated rather than a transform, which is the one place in
 * this kit where that is right: scaling a rectangle would scale its outline
 * with it, and what is wanted is the same hairline at every size.
 */
function zoom(from, to) {
  if (stillness()) return Promise.resolve();

  const box = document.createElement("div");
  box.className = "zooming";
  document.body.append(box);

  const drawing = box.animate([
    { left: `${from.left}px`, top: `${from.top}px`,
      width: `${from.width}px`, height: `${from.height}px` },
    { left: `${to.left}px`, top: `${to.top}px`,
      width: `${to.width}px`, height: `${to.height}px` },
  ], { duration: ZOOM_MS, easing: `steps(${ZOOM_STEPS})` });

  return drawing.finished.catch(() => {}).finally(() => box.remove());
}
