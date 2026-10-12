/* Activity Monitor: what every core of the board is doing, twice a second. */

import { t } from "../strings.js";
import { show, theWindow } from "./page.js";
import { modelOf } from "./pi.js";
import { NOTHING, costOf, decimal, memoryInUse } from "./words.js";

/** Where the readings come from while the window is open: a stream of
 *  Server-Sent Events, one reading every half second, each the object
 *  `/api/activity` answers with. A request per reading would cost the service
 *  more than the readings themselves. */
const STREAM = "/api/activity/stream";

/** How long to wait before opening the stream again where the service closed
 *  it for good, such as one that refused it for having too many open. A stream
 *  that only broke is opened again by the browser itself. */
const AGAIN_MS = 5000;

/** Which window this is, as the markup and the Apps folder name it. */
const ACTIVITY = "activity";

/** The stream while the window is open, and null while it is closed, so a
 *  window nobody is looking at costs the Pi nothing.
 *  @type {EventSource | null} */
let stream = null;

/** The last reading, so a change of language redraws it at once rather than
 *  at the next one. @type {any} */
let lastReading = null;

/**
 * Opens the stream, where the window is open and none is.
 *
 * A reading is drawn the moment it arrives. A stream that breaks says so in
 * the window and is opened again by the browser on its own; one the service
 * closed for good is opened again from here a few seconds later, for as long
 * as the window stays open.
 */
function openTheStream() {
  const window_ = theWindow(ACTIVITY);
  if (!window_ || window_.hidden || stream) return;

  const opened = new EventSource(STREAM);
  stream = opened;
  opened.addEventListener("message", (event) => {
    lastReading = JSON.parse(event.data);
    drawActivity(lastReading);
  });
  opened.addEventListener("error", () => {
    drawActivity(null);
    if (opened.readyState !== EventSource.CLOSED || stream !== opened) return;
    stream = null;
    setTimeout(openTheStream, AGAIN_MS);
  });
}

/** Closes the stream, which is what the service is waiting for to stop. */
function closeTheStream() {
  stream?.close();
  stream = null;
}

/** Draws the last reading again, where the window is open. For a change of
 *  language, because the window writes its own words. */
function redrawActivity() {
  const window_ = theWindow(ACTIVITY);
  if (window_ && !window_.hidden && lastReading) drawActivity(lastReading);
}

/**
 * Draws one reading into the window.
 * @param {any} activity - The reading, or null where the service is not
 *   answering. Every figure inside it may be null as well, and a figure that
 *   is null is drawn as nothing rather than as zero.
 */
function drawActivity(activity) {
  show("activity-note", activity ? "" : t("note.no-service"));
  show("activity-model", modelOf(activity));

  /* One bar per core the service reports. The very first reading has no
     figures yet, since each one is a difference between two samples, and
     the load averages already say how many cores there are, so the bars are
     there from the first moment and light up with the next reading. */
  const meters = drawTheCores(activity?.cores?.length ?? activity?.load?.cores);
  for (const [index, meter] of meters.entries()) {
    showShare(meter, activity?.cores?.[index] ?? null,
      (share) => t("activity.percent", { percent: Math.round(share) }));
  }

  /* Read against how many cores there are, because 4.0 is a machine working
     flat out on four of them and one four times oversubscribed on one. */
  const load = activity?.load;
  show("activity-load", load
    ? t("activity.load.figure", {
        one: decimal(load.one),
        five: decimal(load.five),
        fifteen: decimal(load.fifteen),
        cores: load.cores,
      }, load.cores)
    : NOTHING);

  /* The bar and the first figure are both what is in use, so the words read
     the bar out. */
  const memory = activity?.memory;
  const used = memory ? memory.total_mb - memory.available_mb : null;
  showShare(document.getElementById("activity-memory"),
    memory ? used * 100 / memory.total_mb : null,
    () => memoryInUse(used, memory.total_mb));

  show("activity-emulator", activity ? costOf(activity.emulator) : NOTHING);
}

/**
 * Puts one share into one row of lamps.
 * @param {any} meter - An nx-leds.
 * @param {number|null} share - How full, in per cent, or null where there is
 *   no reading.
 * @param {(share: number) => string} words - What the share is called, asked
 *   only where there is one.
 */
function showShare(meter, share, words) {
  meter.value = share;
  meter.says = share === null ? NOTHING : words(share);
}

/**
 * Makes sure there is one row for each core, and names them.
 * @param {number|null|undefined} count - How many cores the service reports.
 *   Anything that is not a count keeps the rows that are there.
 * @returns {any[]} The rows of lamps, one per core, in the kernel's order.
 *
 * Built here rather than written into the markup, because how many cores a
 * board has is the board's to say: a Pi 5 has four, and a two-core board
 * draws two. The names are written every time, so a change of language
 * reaches them with the next reading.
 */
function drawTheCores(count) {
  const cores = /** @type {any} */ (document.getElementById("activity-cores"));
  if (Number.isInteger(count) && cores.children.length !== count) {
    cores.replaceChildren(...Array.from({ length: count }, () => {
      const row = document.createElement("nx-row");
      row.append(document.createElement("label"), document.createElement("nx-leds"));
      return row;
    }));
  }

  return [...cores.children].map((row, index) => {
    row.querySelector("label").textContent = t("activity.core", { number: index + 1 });
    return row.querySelector("nx-leds");
  });
}

/** Opens the stream with the window and closes it with the window, and opens
 *  it at once where the desk came back with the window open. Wired once. */
function wireActivity() {
  document.addEventListener("nx-open", (/** @type {any} */ event) => {
    if (event.target.getAttribute("name") === ACTIVITY) openTheStream();
  });
  document.addEventListener("nx-close", (/** @type {any} */ event) => {
    if (event.target.getAttribute("name") === ACTIVITY) closeTheStream();
  });
  openTheStream();
}

export {
  redrawActivity,
  wireActivity,
};
