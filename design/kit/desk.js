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

/* --- how large the desk is drawn -----------------------------------------

   Everything here is measured off NeXTSTEP at its own 1120 by 832: a tile is
   68, a menu row is 20, the type is 12. On the screen that machine had, that
   is what those things were. On a 32 inch panel it is small, and the answer is
   to draw the same desk larger rather than to pick new numbers, which would
   be a second set of measurements and the end of every one of them being the
   original's.

   CSS zoom, because it is the one thing that scales a layout rather than a
   picture of one: the pointer lands where it looks, a window measures what it
   is, and the dock stays against the edge. Whole and half steps only, since
   every icon here is a bitmap and anything else draws them between pixels. */

/** How large the desk is drawn, as a multiplier. */
function deskScale() {
  return Number(getComputedStyle(document.body).zoom) || 1;
}

/**
 * Draws the desk at that size.
 * @param {number} scale - 1, 1.5 or 2.
 *
 * Drawing larger leaves less room: at twice the size a desk 1200 across is
 * 600 wide in the units a window's own position is written in, and a window
 * at 700 is then off the screen with no way back to it. So everything is
 * gathered in afterwards.
 */
function setDeskScale(scale) {
  document.body.style.zoom = scale;
  gatherWindows();
}

/** Brings any window that is off the desk back onto it. */
function gatherWindows() {
  const room = deskRoom();
  for (const window_ of document.querySelectorAll("nx-window")) {
    if (window_.hidden) continue;
    const left = Math.min(window_.offsetLeft, Math.max(0, room.width - 90));
    const top = Math.min(window_.offsetTop, Math.max(0, room.height - 40));
    if (left === window_.offsetLeft && top === window_.offsetTop) continue;
    window_.style.left = left + "px";
    window_.style.top = top + "px";
    window_.save?.();
  }
}

/* --- the two units, and the three doors between them ---------------------

   A pointer answers in the viewport's pixels, and so does
   getBoundingClientRect. Everything the desk is laid out in answers in its
   own: offsetLeft, style.left, clientHeight and a transform are all in the
   pixels an element has before zoom multiplies them.

   At twice the size a hand that travelled 100 viewport pixels has moved a
   window 50 of its own, so one cannot be subtracted from the other. There are
   three ways a viewport number reaches this desk, and each of them is a
   function below: a pointer, an element's rectangle, and the size of the
   window itself. Nothing past them divides by anything. */

/**
 * @param {number} length - A viewport measurement.
 * @returns {number} The same length as the desk writes it.
 */
function onDesk(length) {
  return length / deskScale();
}

/**
 * @param {PointerEvent} event
 * @returns {object} Where the pointer is, as `{x, y}` on the desk.
 */
function deskPoint(event) {
  return { x: onDesk(event.clientX), y: onDesk(event.clientY) };
}

/**
 * Where an element is, on the desk.
 * @param {HTMLElement} [element] - Anything drawn there.
 * @returns {?object} Its `left`, `top`, `width` and `height`, or null where
 *   there is no element. A DOMRect's shape, so it goes wherever one went.
 *
 * What draws a picture of something moving puts that picture against the
 * viewport, and anything put there is still a child of the body and carries
 * the desk's zoom. A rect taken straight off an element would be scaled a
 * second time by it.
 */
function deskRect(element) {
  const rect = element?.getBoundingClientRect?.();
  if (!rect) return null;
  return {
    left: onDesk(rect.left), top: onDesk(rect.top),
    width: onDesk(rect.width), height: onDesk(rect.height),
  };
}

/** @returns {object} How much room there is for windows, in the units a
 *  window's own left and top are written in, which zoom does not change. */
function deskRoom() {
  return { width: onDesk(innerWidth), height: onDesk(innerHeight) };
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
 * @param {(point: object, start: object) => void} onMove - Given where the
 *   pointer is now, as `{x, y}` on the desk.
 * @param {(point: object) => object} onStart - Whatever the mover needs to
 *   know about the moment the gesture began, given the same.
 * @param {(start: object) => void} [onEnd] - Given what onStart returned,
 *   which by then carries whatever the moves wrote into it.
 *
 * The pointer is converted here, so what a gesture hands on is already in the
 * units of the element it moves and nothing downstream has to know the desk
 * can be drawn larger.
 */
function gesture(handle, onMove, onStart, onEnd) {
  handle.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
    /* Without this the browser starts its own text selection under the
       pointer, and dragging a window paints half the desk blue. */
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    const start = onStart(deskPoint(event));

    /* A pointer reports faster than the screen redraws, so the moves are
       coalesced into one update per frame. Everything beyond the last one in
       a frame is work whose result is painted over before anybody sees it. */
    let latest = null;
    let frame = 0;

    const apply = () => {
      frame = 0;
      onMove(deskPoint(latest), start);
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
    (point, start) => {
      /* Never past the top or left edge, and never wholly behind the dock. */
      const room = deskRoom();
      start.left = Math.max(0, Math.min(point.x - start.grabX, room.width - 90));
      start.top = Math.max(0, Math.min(point.y - start.grabY, room.height - 24));
      element.style.transform =
        `translate(${start.left - start.fromLeft}px, ${start.top - start.fromTop}px)`;
    },
    (point) => {
      onGrab?.();
      const fromLeft = element.offsetLeft;
      const fromTop = element.offsetTop;
      return {
        grabX: point.x - fromLeft, grabY: point.y - fromTop,
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
   caller says where from and where to, and waits for it to land.

   Both put their picture against the viewport, and both take their two places
   on the desk, which is what deskRect answers in. A caller reaching for
   getBoundingClientRect here would hand over the one unit that does not
   work. */

/** How long an icon takes to reach its place on the floor. Brisk, because it
 *  is a thing moving rather than an effect: long enough to be followed by the
 *  eye and short enough that anybody waits for it. */
const FLIGHT_MS = 260;

/** The same inside one window, where the way is a fraction as long. A hundred
 *  pixels crossed at the speed of half a screen reads as hesitant, so a short
 *  way is given a short time. */
const NEAR_FLIGHT_MS = 130;

/** How many rectangles the way is drawn with, and over how long. Few and
 *  fast: what is wanted is a run of outlines standing on the screen for a
 *  moment, not a box growing. */
const ZOOM_RECTANGLES = 8;
const ZOOM_MS = 200;

/** @returns {boolean} Whether the reader has asked for less movement. */
function stillness() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Sends a picture of an icon from one place to another.
 * @param {string} icon - Which picture.
 * @param {object} from - Where it starts, as deskRect answers.
 * @param {object} to - Where it lands, as deskRect answers.
 * @param {number} howLong - How long it takes, in milliseconds. The default
 *   is the way across the screen; a way inside one window is shorter and is
 *   given NEAR_FLIGHT_MS.
 * @returns {Promise} Settled when it has landed.
 *
 * A transform and nothing else, so this costs the compositor and not the
 * layout. Where the reader has asked for less movement there is no flight at
 * all: the tile is simply there, which is what they asked for.
 */
function fly(icon, from, to, howLong = FLIGHT_MS) {
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
  ], { duration: howLong, easing: "ease-out" });

  return flight.finished.catch(() => {}).finally(() => ghost.remove());
}



/**
 * Draws the way from one place to another, as a run of rectangles.
 * @param {object} from - Where it starts, which is the mark around an icon,
 *   as deskRect answers.
 * @param {object} to - Where it ends, which is the box about to hold what was
 *   in that folder, in the same units.
 * @returns {Promise} Settled when they have gone.
 *
 * Several, and none of them is rubbed out: each is drawn at its own size a
 * moment after the last, so what stands on the screen is a run of nested
 * outlines from the icon to the band, and they all go together at the end.
 * That is what makes it read as a wave rather than as one box growing.
 *
 * Outlines rather than filled rectangles, because filled ones would be a
 * black flash across half the window.
 */
function zoom(from, to) {
  if (stillness()) return Promise.resolve();

  const drawn = [];
  let last = null;
  for (let step = 1; step <= ZOOM_RECTANGLES; step += 1) {
    const part = step / ZOOM_RECTANGLES;
    const box = document.createElement("div");
    box.className = "zooming";
    box.style.left = between(from.left, to.left, part) + "px";
    box.style.top = between(from.top, to.top, part) + "px";
    box.style.width = between(from.width, to.width, part) + "px";
    box.style.height = between(from.height, to.height, part) + "px";
    box.style.opacity = "0";
    document.body.append(box);
    drawn.push(box);

    /* Turned on rather than faded in: a rectangle is there or it is not. */
    last = box.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: 1,
      delay: (step - 1) * (ZOOM_MS / ZOOM_RECTANGLES),
      fill: "forwards",
    });
  }

  return last.finished
    .catch(() => {})
    .finally(() => drawn.forEach((box) => box.remove()));
}

/**
 * @param {number} start
 * @param {number} end
 * @param {number} part - Where between them, from zero to one.
 * @returns {number} Rounded, because a rectangle drawn on half a pixel is a
 *   grey line rather than a black one.
 */
function between(start, end, part) {
  return Math.round(start + (end - start) * part);
}
