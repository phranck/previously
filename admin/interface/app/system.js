/* What the whole system is doing, and therefore what can be done from here.
 *
 * Restarting NeXTSTEP, changing the machine, restarting the board and replacing
 * this tool all change what every window may offer, not only the one they were
 * started from. So the state is held here, once, and every control that changes
 * something says what it needs and is switched from here whenever the state
 * moves. A window deciding for itself is how a machine could be double clicked
 * in the File Viewer while the About window was in the middle of a change.
 */

import { t } from "../strings.js";
import { show } from "./page.js";

/** What a control needs before it can be used. */
const Needs = /** @type {const} */ ({
  /** Contact with the service and nothing under way: everything that changes
   *  the machine, its disks, the board or this tool. */
  Quiet: "quiet",
  /** Contact with the service and an emulator that is running: a picture of
   *  its screen. */
  Screen: "screen",
  /** Contact with the service and nothing more: keeping a configuration or
   *  taking a picture away, which touch neither the machine nor the board. */
  Contact: "contact",
});

/** One of Needs. @typedef {typeof Needs[keyof typeof Needs]} Need */

/** Whether the last status arrived. False until the first one has, because
 *  nothing is known about a system that has not answered yet. */
let reachable = false;

/** Whether the emulator was running at the last status. */
let running = false;

/** What this page has set going and is waiting for, or null. An operation
 *  that lasts until the board is back carries the boot it was started on.
 *  @type {{words: string, untilBack: boolean, boot: string | null} | null} */
let operation = null;

/** Which boot of the board the last status came from, or null before one has
 *  said.
 *  @type {string | null} */
let boot = null;

/** Which jobs of the privileged helper are under way, by the window that
 *  watches them. The helper takes one job at a time whoever asked for it.
 *  @type {Record<string, boolean>} */
const helping = {};

/** Every control that changes something, with what it needs and the condition
 *  of its own beside that.
 *  @type {{selector: string, needs: Need, own: () => boolean}[]} */
const held = [];

/**
 * Puts a control under the system's state.
 * @param {string} selector - Where it is, as querySelector takes it.
 * @param {Need} needs - One of Needs.
 * @param {() => boolean} [own] - What the control itself asks on top, such as
 *   an emulator that is running before it can be stopped. Read every time the
 *   controls are drawn, so it answers about now.
 */
function hold(selector, needs, own = () => true) {
  held.push({ selector, needs, own });
}

/**
 * Whether something needing that may be done now.
 * @param {Need} needs - One of Needs.
 * @returns {boolean}
 */
function may(needs) {
  return whyNot(needs) === "";
}

/**
 * Why something needing that may not be done now.
 * @param {Need} needs - One of Needs.
 * @returns {string} The sentence for it, or "" where it may.
 */
function whyNot(needs) {
  if (!reachable) return t("hold.away");
  if (needs === Needs.Contact) return "";
  if (operation) return t("hold.working");
  if (Object.values(helping).some(Boolean)) return t("hold.helper");
  if (needs === Needs.Screen && !running) return t("grab.idle");
  return "";
}

/**
 * Lets an action go ahead, or says in a note why it cannot.
 * @param {Need} needs - One of Needs.
 * @param {string} note - The note of the window it was asked from.
 * @returns {boolean} Whether to go ahead.
 *
 * For the actions that are reached by a gesture rather than by a button, such
 * as a double click in the File Viewer or an entry of its context menu: a
 * button is held off, and a gesture has to be refused where it lands.
 */
function allowed(needs, note) {
  const why = whyNot(needs);
  if (why) {
    show(note, why);
    refused.set(note, needs);
  }
  return !why;
}

/** The notes that say why something was refused, with what it needed, so each
 *  is taken away once that is possible again. Left standing, it would go on
 *  saying something is being changed after the change is over.
 *  @type {Map<string, Need>} */
const refused = new Map();

/**
 * Takes in what the service last said about the machine.
 * @param {{running: boolean, boot?: string | null} | null} status - What
 *   /api/status answered, or null where nothing did.
 *
 * An operation that takes the board away is over when the board answers from
 * another boot, and not before: its own request comes back long before the
 * board does. A status that failed in between is no sign of it, because the
 * page asks without a time limit and a request that falls into the restart
 * waits for the board and comes back like any other.
 */
function heard(status) {
  reachable = status !== null;
  running = Boolean(status?.running);
  if (status?.boot) {
    if (operation?.untilBack && operation.boot && status.boot !== operation.boot) {
      operation = null;
    }
    boot = status.boot;
  }
  drawTheSystem();
}

/**
 * Starts an operation: every control that changes something goes off, and
 * every window with a busy line says what is happening.
 * @param {string} words - What is happening.
 * @param {boolean} [untilBack] - Whether it lasts until the board answers from
 *   another boot, which is what a restart of the board does. A board that is
 *   switched off never does, and the operation then stands for as long as the
 *   page is open.
 */
function begin(words, untilBack = false) {
  operation = { words, untilBack, boot };
  drawTheSystem();
}

/** Ends the operation that is running, if any. */
function end() {
  operation = null;
  drawTheSystem();
}

/**
 * Says whether a job of the privileged helper is under way.
 * @param {string} watcher - The window that watches it.
 * @param {boolean} busy - Whether one is.
 */
function helperIs(watcher, busy) {
  if (Boolean(helping[watcher]) === busy) return;
  helping[watcher] = busy;
  drawTheSystem();
}

/** Draws every busy line and every held control from the state there is, and
 *  takes away every refusal that no longer holds. */
function drawTheSystem() {
  for (const line of document.querySelectorAll(".busy")) {
    line.textContent = operation?.words ?? "";
  }
  for (const [note, needs] of refused) {
    if (!may(needs)) continue;
    show(note, "");
    refused.delete(note);
  }
  holdTheControls();
}

/**
 * Switches every held control on or off.
 *
 * A button by its own `disabled`, and anything else by the attribute, which is
 * how the kit greys a menu entry. Exported so a control that turned itself off
 * for a moment, such as Grab's while it fetches, hands itself back here.
 */
function holdTheControls() {
  for (const { selector, needs, own } of held) {
    const control = document.querySelector(selector);
    if (!control) continue;
    const off = !may(needs) || !own();
    if (control instanceof HTMLButtonElement) control.disabled = off;
    else control.toggleAttribute("disabled", off);
  }
}

export {
  Needs,
  hold,
  may,
  allowed,
  heard,
  begin,
  end,
  helperIs,
  holdTheControls,
};
