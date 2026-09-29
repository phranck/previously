/* What the machine is doing, and the three buttons that change it. */

import { t, writeTitle, writeWords } from "../strings.js";
import { drawTheMenu } from "./menu.js";
import { show } from "./page.js";
import { askForPassword, askPanel } from "./panels.js";
import { drawPi } from "./pi.js";
import { Kiosk, ask, operate } from "./service.js";
import { markCurrent } from "./viewer.js";
import { Art, NOTHING, changedLine, cpuOf, machineArt, modelOf, nameOf, screenOf, since, writtenLine } from "./words.js";

/** Everything on the page that changes something. */
const ACTIONS = [
  "kiosk-start", "kiosk-stop", "kiosk-restart",
  "pi-reboot", "pi-poweroff",
];

/**
 * Turns every acting button off or lets the state decide again.
 * @param {boolean} reachable - Whether the service answered.
 */
function allowActions(reachable) {
  for (const id of ACTIONS) {
    const button = document.getElementById(id);
    if (button) button.disabled = !reachable;
  }
}

/**
 * Draws the state of the machine into the info window.
 * @param {object|null} status - What /api/status answered, or null.
 */
function drawStatus(status) {
  const state = document.getElementById("info-state");
  lastStatus = status;
  drawWhatThisMachineIs(status);

  if (status === null) {
    /* Nothing can be asked of a machine that is not answering, and whilst it
       restarts it will not answer for a minute or two. Leaving the buttons
       live would collect requests that go nowhere. */
    state.replaceChildren(document.createTextNode(t("state.unreachable")));
    show("info-caption", t("info.no-contact"));
    allowActions(false);
    return;
  }

  allowActions(true);

  /* The lamp carries the state as a shape as well as a colour, because colour
     alone asks the reader to compare two small squares. */
  const lamp = document.createElement("span");
  lamp.className = "lamp";
  if (!status.running) lamp.style.background = "var(--dark)";

  /* Three states, not two. Held down means somebody switched it off from here
     and nothing will start it again; stopped without a hold means it went away
     on its own, which is a different thing and worth saying differently. */
  /* Four states, and the fourth is the one a fresh machine is in. A Pi with
     nothing installed is not stopped and not switched off: there is nothing
     there to be either, and saying "stopped" would read as a fault. */
  const isNew = status.ready?.set_up === false;
  let words = t("state.stopped");
  if (status.running) words = t("state.running", { since: since(status.uptime_seconds) });
  else if (isNew) words = t("state.not-set-up");
  else if (status.held) words = t("state.held");
  /* The file has been written since this machine started, so it holds a
     machine nobody has tried. It marks the machine in the shelf, and the file
     line below says it in words, because a texture explains nothing on its
     own. */
  const untried = Boolean(status.file?.newer_than_the_machine);
  state.replaceChildren(lamp, document.createTextNode(" " + words));

  /* "kommt zurück" is done when it is back, and the note should not still be
     saying it. So a note is kept until the machine is in a different state
     than it was when the note was written, and then it goes. */
  const nowState = `${status.running}/${status.held}/${status.configuration?.catalogue}`;
  if (noteState === JUST_WRITTEN) {
    noteState = nowState;
  } else if (noteState !== null && noteState !== nowState) {
    show("kiosk-note", "");
    noteState = null;
  }

  document.getElementById("kiosk-start").disabled = status.running || isNew;
  document.getElementById("kiosk-stop").disabled = !status.running;
  document.getElementById("kiosk-restart").disabled = !status.running;

  /* A machine with nothing on it says so and is offered the one thing that can
     be done with it. Before the console, because that one is also missing on a
     fresh Pi and "switching on will do nothing" is true and unhelpful: there is
     nothing to switch on yet. */
  if (isNew) {
    show("kiosk-note", t("note.not-set-up"));
    offerTheInstaller();
  } else if (!status.console_active) {
    /* Without the console session there is nothing waiting to start the
       emulator again, so switching it on would report success and do nothing.
       Saying so here is the only place that failure becomes visible. */
    show("kiosk-note", t("note.no-console"));
  }

  const machine = status.configuration;
  if (!machine) {
    show("info-caption", t(isNew ? "info.not-set-up" : "info.unreadable"));
    const empty = ["info-cpu", "info-ram", "info-screen", "info-disk",
                   "info-file", "info-written"];
    for (const id of empty) show(id, NOTHING);
    return;
  }

  show("info-caption", nameOf(machine));
  markCurrent(machine.catalogue, untried);

  show("info-file", changedLine(status.file));
  show("info-written", writtenLine(status.file));
  show("info-cpu", cpuOf(machine));
  show("info-ram", t("machine.memory", { mb: machine.memory_mb }));
  show("info-screen", screenOf(machine));
  show("info-disk", machine.disk ?? t("info.no-disk"));

  /* The same picture the boot ROM puts up whilst it tests this machine. Colour
     plays no part in it: a NeXTstation Color stands in the same case as a grey
     one, and the line above says which tube is in it. */
  runningArt = machineArt(machine.enclosure);
  document.getElementById("info-icon").style.backgroundImage = `var(--${runningArt})`;
}

/** Whether the Installer has been put in front of somebody in this visit. Once
 *  per visit rather than once ever: a machine with nothing on it has nothing
 *  else to offer, so somebody coming back to the page is offered it again, and
 *  somebody who closed the window is left alone until they do. */
let offeredTheInstaller = false;

/**
 * Puts the Installer in front of somebody on a machine that has nothing on it.
 *
 * This is what a fresh installation opens into. Everything else in the
 * interface is about a machine that exists, and on a Pi where nothing has been
 * installed those windows have nothing to say: the honest answer is not an
 * empty Info window but the one window that can change that.
 */
function offerTheInstaller() {
  if (offeredTheInstaller) return;
  offeredTheInstaller = true;
  document.querySelector('nx-window[name="installer"]')?.open();
}

/**
 * Draws the menu entry that says what the emulated machine is, or takes it
 * away.
 * @param {object|null} status - What /api/status answered, or null.
 *
 * It carries the machine's own name, so its words are written here rather than
 * taken from the catalogue: `About NeXTcube Turbo`. On a Pi with nothing
 * installed there is no machine to be about, and an entry that opened a window
 * of em dashes would be a question with no answer, so it is not in the menu at
 * all.
 */
function drawWhatThisMachineIs(status) {
  const entry = document.querySelector('nx-menu-item[name="about"]');
  if (!entry) return;

  const machine = status?.ready?.set_up ? status.configuration : null;
  if (machine) {
    /* The window says what the entry that opens it says. Two names for one
       window is two windows as far as anybody reading the screen is
       concerned. */
    const words = t("menu.about", { machine: modelOf(machine) });
    writeWords(entry, words);
    const window_ = document.querySelector('nx-window[name="info"]');
    if (window_) writeTitle(window_, words);
  }

  /* `away` rather than `hidden`, because the menu owns that one: it hides
     every entry that belongs to another application each time the front
     window changes, and would put this one back. */
  const there = Boolean(machine);
  if (there === aboutIsThere) return;
  aboutIsThere = there;
  entry.toggleAttribute("away", !there);
  /* The menu works out what it shows when the front window changes, and this
     is neither, so it is asked again. */
  drawTheMenu();
}

/** Whether the entry about this machine is in the menu, so that the menu is
 *  drawn again when that changes and not twice a second when it does not. */
let aboutIsThere = null;

/** The picture of the machine that is configured now, so a panel asking about
 *  it shows it rather than a generic computer. Set from every status. */
let runningArt = Art.Computer;

/** The last thing /api/status said, for the parts of the info window that are
 *  about the file rather than about a machine. */
let lastStatus = null;

/** Written into noteState whilst a note is new and the state it describes has
 *  not been seen yet. */
const JUST_WRITTEN = Symbol("just written");

/** What the machine looked like when the note under the readings was written,
 *  JUST_WRITTEN before that has been seen, and null where there is no note.
 *
 *  The note says what was last asked for, so it has said everything it has to
 *  say once the machine has moved on from the state it was written in. */
let noteState = null;

/**
 * Turns the buttons off while something is happening, and says what.
 * @param {boolean} busy
 * @param {string} note - What to show under the readings.
 */
function setBusy(busy, note) {
  for (const id of ["kiosk-start", "kiosk-stop", "kiosk-restart"]) {
    document.getElementById(id).disabled = busy;
  }
  show("kiosk-note", note);
  noteState = note ? JUST_WRITTEN : null;
}

/**
 * The warning before the emulator goes away.
 *
 * Always asked and always worded the same, because Previous tells us nothing
 * about what the guest is doing. A warning that appeared only sometimes would
 * teach the reader that its absence means safe, which we cannot know.
 * @param {string} what - The wording on the acting button.
 * @returns {Promise<boolean>}
 */
function warn(what) {
  return askPanel({
    title: t("ask.stop.title"),
    text: [t("ask.stop.how"), t("ask.stop.loss")],
    icon: runningArt,
    confirm: what,
  });
}

/** Wires the three buttons and the menu's own way to the password. */
function wireButtons() {
  document.querySelector('nx-menu-item[name="password"]')
    ?.addEventListener("click", () => askForPassword());

  document.getElementById("kiosk-start").addEventListener("click",
    () => operate(Kiosk.Start, t("busy.starting")));

  document.getElementById("kiosk-stop").addEventListener("click", async () => {
    if (await warn(t("button.power-off"))) operate(Kiosk.Stop, t("busy.stopping"));
  });

  document.getElementById("kiosk-restart").addEventListener("click", async () => {
    if (await warn(t("button.restart"))) operate(Kiosk.Restart, t("busy.restarting"));
  });
}

/** Fetches the status and draws it, and the board's readings where its window
 *  is open. A window nobody is looking at costs nothing. */
async function refresh() {
  drawStatus(await ask("/api/status"));

  const window_ = document.querySelector('nx-window[name="pi"]');
  if (window_ && !window_.hidden) drawPi(await ask("/api/pi"));
}

export {
  allowActions,
  drawStatus,
  lastStatus,
  setBusy,
  wireButtons,
  refresh,
};
