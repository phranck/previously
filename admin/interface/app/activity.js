/* Activity Monitor: what every core of the board is doing, twice a second. */

import { t } from "../strings.js";
import { show, theWindow } from "./page.js";
import { modelOf } from "./pi.js";
import { ask } from "./service.js";
import { NOTHING, costOf, decimal, memoryInUse } from "./words.js";

/** How often the window asks while it is open. The service reads `/proc` and
 *  forks nothing for this, and a whole answer costs it 1.5 ms of a core on a
 *  Pi 5, so twice a second is three tenths of one per cent of one core. A bar
 *  that moves more slowly reads as a figure rather than as a monitor. */
const ACTIVITY_MS = 500;

/** Which window this is, as the markup and the Apps folder name it. */
const ACTIVITY = "activity";

/** Whether an answer is still on its way, so a service that is slow to reply
 *  is not asked again on top of itself at every tick until it does. */
let asking = false;

/**
 * Asks what the board is doing and draws it, while the window is open.
 *
 * Nothing at all while it is closed: the timer still fires, finds the window
 * hidden and goes back to sleep, so a window nobody is looking at costs the
 * Pi nothing. That is the same test the Raspberry Pi window's readings pass
 * through on their slower poll.
 */
async function sampleActivity() {
  const window_ = theWindow(ACTIVITY);
  if (!window_ || window_.hidden || asking) return;
  asking = true;
  try {
    drawActivity(await ask("/api/activity"));
  } finally {
    asking = false;
  }
}

/**
 * Draws one answer of `/api/activity` into the window.
 * @param {any} activity - The answer, or null where the service did not give
 *   one. Every reading inside it may be null as well, and a reading that is
 *   null is drawn as nothing rather than as zero.
 */
function drawActivity(activity) {
  show("activity-note", activity ? "" : t("note.no-service"));
  show("activity-model", modelOf(activity));

  /* One bar per core the service reports. The very first answer has no
     figures yet, since each one is a difference between two readings, and
     the load averages already say how many cores there are, so the bars are
     there from the first moment and light up at the next answer. */
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
 * reaches them at the next answer.
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

/** Starts the sampling, and fills the window the moment it is opened rather
 *  than at the next tick. Wired once. */
function wireActivity() {
  document.addEventListener("nx-open", (/** @type {any} */ event) => {
    if (event.target.getAttribute("name") === ACTIVITY) sampleActivity();
  });
  setInterval(sampleActivity, ACTIVITY_MS);
  sampleActivity();
}

export {
  sampleActivity,
  wireActivity,
};
