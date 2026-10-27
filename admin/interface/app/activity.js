/* Activity Monitor: what every core of the board is doing, five times a
   second, and the load and the emulator's share as charts of what came
   before. */

import { NxChart, NxLeds } from "../nextstep.js";
import { t } from "../strings.js";
import { byId, show, targetName, theWindow } from "./page.js";
import { modelOf, showBoard } from "./pi.js";
import { NOTHING, costOf, decimal, memoryInUse } from "./words.js";

/** @typedef {import("../answers.js").ActivityAnswer} ActivityAnswer */

/** Where the readings come from while the window is open: a stream of
 *  Server-Sent Events of two kinds, `cores` five times a second and `rest`
 *  twice, together the object `/api/activity` answers with. A request per
 *  reading would cost the service more than the readings themselves. */
const STREAM = "/api/activity/stream";

/** How long to wait before opening the stream again where the service closed
 *  it for good, such as one that refused it for having too many open. A stream
 *  that only broke is opened again by the browser itself. */
const AGAIN_MS = 5000;

/** Which window this is, as the markup and the Apps folder name it. */
const ACTIVITY = "activity";

/** How often the load chart takes a column: as often as the kernel works the
 *  load averages out again, which is every five seconds. A column per reading
 *  would draw ten of the same in a row. */
const LOAD_EVERY_MS = 5000;

/** Where the load turns orange, as a share of the cores. Above all of them it
 *  is red, which is overload. */
const LOAD_WARM_SHARE = 0.7;

/** What the top of the emulator chart stands for, in per cent of one core: a
 *  NeXTdimension's two threads reach two cores. Around 150 is ordinary with
 *  one, so the chart warns only above that. */
const EMULATOR_TOP = 200;
const EMULATOR_WARM = 170;
const EMULATOR_HOT = 190;

/** When the load chart last took a column, by the page's clock, or 0 where it
 *  has not yet. */
let loadTakenAt = 0;

/** The stream while the window is open, and null while it is closed, so a
 *  window nobody is looking at costs the Pi nothing.
 *  @type {EventSource | null} */
let stream = null;

/** The last reading, so a change of language redraws it at once rather than
 *  at the next one. @type {ActivityAnswer | null} */
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

  /* The charts start again from the moment the window opens: what happened
     while it was closed was not measured. */
  for (const chart of charts()) chart.clear();
  loadTakenAt = 0;
  lastReading = null;

  const opened = new EventSource(STREAM);
  stream = opened;
  /* The rest comes twice a second and takes the charts on; the cores come
     five times a second. Each is laid over what is already known, so the
     window always draws one whole reading. */
  opened.addEventListener("rest", (event) => {
    /** @type {Omit<ActivityAnswer, "cores">} */
    const rest = JSON.parse(event.data);
    lastReading = { cores: null, ...lastReading, ...rest };
    chartActivity(lastReading);
    drawActivity(lastReading);
  });
  opened.addEventListener("cores", (event) => {
    /** @type {Pick<ActivityAnswer, "cores">} */
    const { cores } = JSON.parse(event.data);
    if (!lastReading) return;
    lastReading = { ...lastReading, cores };
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
 * @param {ActivityAnswer | null} activity - The reading, or null where the
 *   service is not answering. Every figure inside it may be null as well, and
 *   a figure that is null is drawn as nothing rather than as zero.
 */
function drawActivity(activity) {
  show("activity-note", activity ? "" : t("note.no-service"));
  show("activity-model", modelOf(activity));
  showBoard("activity-board", activity);

  /* One bar per core the service reports. The very first reading has no
     figures yet, since each one is a difference between two samples, and
     the load averages already say how many cores there are, so the bars are
     there from the first moment and light up with the next reading. */
  const meters = drawTheCores(activity?.cores?.length ?? activity?.load?.cores);
  for (const [index, meter] of meters.entries()) {
    /* A core's figure takes the room of the widest it can say, so the four
       of them stand right-aligned and a reading that gains a digit does not
       move its sign. */
    meter.widest = t("activity.percent", { percent: 100 });
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
      }, load.cores ?? undefined)
    : NOTHING);

  /* The bar and the first figure are both what is in use, so the words read
     the bar out. */
  const memory = activity?.memory;
  const meter = byId("activity-memory", NxLeds);
  if (memory) {
    const used = memory.total_mb - memory.available_mb;
    showShare(meter, used * 100 / memory.total_mb,
      () => memoryInUse(used, memory.total_mb));
  } else {
    showShare(meter, null, () => NOTHING);
  }

  show("activity-emulator", activity ? costOf(activity.emulator) : NOTHING);
}

/**
 * Puts one share into one row of lamps.
 * @param {NxLeds} meter - The row.
 * @param {number|null} share - How full, in per cent, or null where there is
 *   no reading.
 * @param {(share: number) => string} words - What the share is called, asked
 *   only where there is one.
 */
function showShare(meter, share, words) {
  meter.value = share;
  meter.says = share === null ? NOTHING : words(share);
}

/** @returns {NxChart[]} The load chart and the emulator chart, as the markup
 *  holds them. */
function charts() {
  return [byId("activity-load-chart", NxChart), byId("activity-emulator-chart", NxChart)];
}

/**
 * Adds one reading to the charts.
 * @param {ActivityAnswer} activity - The reading.
 * @param {number} [now] - The page's clock, for a test.
 *
 * Called with every reading of the rest, twice a second. The emulator takes a
 * column each time, its share worked out by the service over that half
 * second. The load takes one every LOAD_EVERY_MS, and its chart reaches at
 * least the number of cores, so a full column is every core busy, and grows
 * with a load beyond that.
 */
function chartActivity(activity, now = Date.now()) {
  const [load, emulator] = charts();

  emulator.floor = EMULATOR_TOP;
  emulator.warm = EMULATOR_WARM;
  emulator.hot = EMULATOR_HOT;
  emulator.push(activity.emulator?.cpu_percent ?? null);

  const cores = activity.load?.cores;
  if (cores) {
    load.floor = cores;
    load.grows = true;
    load.warm = cores * LOAD_WARM_SHARE;
    load.hot = cores;
  }
  if (now - loadTakenAt >= LOAD_EVERY_MS) {
    loadTakenAt = now;
    load.push(activity.load?.one ?? null);
  }
}

/**
 * Makes sure there is one row for each core, and names them.
 * @param {number|null|undefined} count - How many cores the service reports.
 *   Anything that is not a count keeps the rows that are there.
 * @returns {NxLeds[]} The rows of lamps, one per core, in the kernel's order.
 *
 * Built here rather than written into the markup, because how many cores a
 * board has is the board's to say: a Pi 5 has four, and a two-core board
 * draws two. The names are written every time, so a change of language
 * reaches them with the next reading.
 */
function drawTheCores(count) {
  const cores = byId("activity-cores");
  if (typeof count === "number" && Number.isInteger(count)
      && cores.children.length !== count) {
    cores.replaceChildren(...Array.from({ length: count }, () => {
      const row = document.createElement("nx-row");
      row.append(document.createElement("label"), document.createElement("nx-leds"));
      return row;
    }));
  }

  return [...cores.children].flatMap((row, index) => {
    const label = row.querySelector("label");
    if (label) label.textContent = t("activity.core", { number: index + 1 });
    const meter = row.querySelector("nx-leds");
    return meter ? [meter] : [];
  });
}

/** Opens the stream with the window and closes it with the window, and opens
 *  it at once where the desk came back with the window open. Wired once. */
function wireActivity() {
  document.addEventListener("nx-open", (event) => {
    if (targetName(event.target) === ACTIVITY) openTheStream();
  });
  document.addEventListener("nx-close", (event) => {
    if (targetName(event.target) === ACTIVITY) closeTheStream();
  });
  openTheStream();
}

export {
  chartActivity,
  redrawActivity,
  wireActivity,
};
