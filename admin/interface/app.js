/* What this particular application does with the kit.
 *
 * The kit in nextstep.js knows about windows and shelves and nothing about
 * emulators. Everything that knows what a NeXTcube is lives here.
 *
 * Reading needs no password. The three buttons that switch the emulated
 * machine on and off do, and the service refuses them without one.
 */

import {
  NEAR_FLIGHT_MS,
  between,
  defineTheKit,
  deskIsNew,
  deskRect,
  fly,
  gesture,
  remember,
  setDeskScale,
  zoom,
} from "./nextstep.js";
import {
  LANGUAGE_NAMES,
  currentLanguage,
  currentLocale,
  setLanguage,
  t,
  translate,
  writeTitle,
  writeWords,
} from "./strings.js";
import { defineTheTerminal } from "./terminal.js";


/** How often the status is fetched. A machine whose job is to sit there does
 *  not repay a faster poll than this. */
const REFRESH_MS = 5000;

/** What the service names a screenshot it filed, so the viewer can be redrawn
 *  without asking for the whole tree to find out whether it should be. */
const KEPT_HEADER = "X-Previously-Kept";

/** What stands in a field that has nothing to say. An em dash rather than an
 *  empty field, because an empty one reads as a value that is missing and this
 *  one is a question that does not arise. */
const NOTHING = "—";

/** What the name of an application ends in. NeXTSTEP showed the whole file
 *  name, suffix and all, and this is a filesystem however made up it is. */
const APPLICATION = ".app";

/** Which window the Config Editor is. The tree names the same one as what
 *  `Config Editor.app` opens, and this is the one application here that is
 *  started on something rather than on nothing. */
const EDITOR = "editor";

/** What the pictures are called, by what they mean rather than by their file. */
const Art = {
  Computer: "root",
  Folder: "folder",
  Cube: "nextcube",
  Station: "nextstation",
  Editor: "defaultAppIcon",
  Installer: "Installer",
  Picture: "tiff",
  Disk: "winchester",
  /* NeXTSTEP 3.3 has no picture of a CD, so a disc wears the generic SCSI
     device, which is what a CD-ROM on the bus is. */
  Disc: "scsi",
};

/** Which picture a machine wears, by the case the service says it comes in.
 *  Both are the boot ROM's own drawings, so the shelf shows what the screen
 *  shows a second after a machine is chosen. */
const MACHINE_ART = {
  cube: Art.Cube,
  station: Art.Station,
};

/**
 * What the service just said, as a sentence.
 * @param {object|null} told - Its answer, carrying `reason` and whatever fills
 *   it.
 * @returns {string} The sentence in the language the interface speaks, or the
 *   bare name where no catalogue knows it, because a name on the screen is
 *   ugly and silence is worse.
 *
 * The service sends a name and the values that fill it, so this is a lookup
 * and nothing more. Three of its answers need one thing beyond their values:
 * two say how many, which decides singular against plural, and one says which
 * of two things the board is doing.
 */
function say(told) {
  if (!told?.reason) return "";
  const key = `told.${told.reason}`;
  /* The reason a change was rolled back is itself a name, and it stands in the
     middle of the sentence rather than beside it. */
  const values = told.why ? { ...told, why: t(`why.${told.why}`) } : told;

  if (told.reason === "board.on-its-way") return t(`${key}.${told.action}`, values);
  /* What the Pi was asked to do, which is five different things and therefore
     five sentences: one for all of them would say nothing about any. */
  if (told.reason === "setup.asked") return t(`${key}.${told.job}`, values);
  if (told.reason === "guest.still-shutting-down") return t(key, values, told.seconds);
  if (["machine.running", "disk.booting", "disc.inserted", "disc.ejected"]
      .includes(told.reason)) {
    return t(key, values, told.lines);
  }
  return t(key, values);
}

/** Where a shell session comes from. Not a POST like everything that changes
 *  the machine, because what comes back is a connection rather than an answer,
 *  and what guards it is this machine's own SSH server rather than anything
 *  here. */
const TERMINAL = "/api/terminal";

/** What the buttons ask the service to do, by the route that does it. */
const Kiosk = {
  Start: "/api/kiosk/start",
  Stop: "/api/kiosk/stop",
  Restart: "/api/kiosk/restart",
};

/** And what the board itself can be asked. Separate from the emulator's,
 *  because these two take the whole machine with them. */
const Board = {
  Reboot: "/api/pi/reboot",
  PowerOff: "/api/pi/poweroff",
};

/** What can be asked about the configurations somebody saved. Not one of these
 *  touches the running machine: keeping a configuration and running one are two
 *  different acts, and the second is /api/machine.
 *
 *  Keep is the Config Editor's, which is the one window that puts a
 *  configuration together. The other two are in the context menu on a saved
 *  machine. */
const Saved = {
  Keep: "/api/machine/save",
  Rename: "/api/machine/rename",
  Remove: "/api/machine/remove",
};

/** How long a shutdown may take before the page stops waiting for the answer.
 *  Longer than the service's own patience with the guest, so the reason it
 *  gives always arrives rather than being cut off by the browser. */
const OPERATION_TIMEOUT_MS = 150000;

/**
 * Fetches one of the service's answers.
 * @param {string} route - The path, such as "/api/status".
 * @returns {Promise<object|null>} The parsed answer, or null when the service
 *   cannot be reached, because a page that throws tells the reader less than
 *   one that says it has lost contact.
 */
async function ask(route) {
  try {
    const answer = await fetch(route, { cache: "no-store" });
    return answer.ok ? await answer.json() : null;
  } catch {
    return null;
  }
}

/**
 * Sends something to the service and reads its answer.
 * @param {string} route - The path.
 * @param {object} [body] - What to send, where the route takes something.
 * @returns {Promise<Response|null>} The answer, or null when the service
 *   cannot be reached.
 *
 * The session rides along in a cookie the browser sets and this page never
 * sees, so nothing here carries a secret and nothing here can leak one.
 */
async function send(route, body) {
  try {
    return await fetch(route, {
      method: "POST",
      cache: "no-store",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(OPERATION_TIMEOUT_MS),
    });
  } catch {
    return null;
  }
}

/**
 * The words every panel needs, put in front of what the caller says.
 * @param {object} question - As the kit's ask takes it.
 * @returns {object} The same, with the two buttons named.
 *
 * The kit holds no words of its own, so they are named here and nowhere else.
 * A caller that has a better word for the acting button says so and keeps the
 * safe one.
 */
function worded(question) {
  return { confirm: t("button.ok"), cancel: t("button.cancel"), ...question };
}

/**
 * Puts a question.
 * @param {object} question
 * @returns {Promise<boolean>} Whether the acting button was pressed.
 */
function askPanel(question) {
  return document.getElementById("ask").ask(worded(question));
}

/**
 * Puts a question that needs something typed.
 * @param {object} question
 * @returns {Promise<string|null>} What was typed, or null.
 */
function askPanelFor(question) {
  return document.getElementById("ask").askFor(worded(question));
}

/**
 * Puts whichever question about the password this machine is due.
 * @param {string} [why] - A first line saying what prompted it.
 * @returns {Promise<boolean>} Whether this browser may now change something.
 *
 * Three states and one entry point, because whoever reaches this wants to get
 * past it rather than to know which of the three they are in. A machine nobody
 * has claimed asks for a password to set, one that is claimed asks for the
 * password it has, and a browser that is already signed in is offered a new
 * one, which is how a password is changed without going near the Pi.
 */
async function askForPassword(why) {
  const state = await ask("/api/session");
  if (state === null) return false;
  if (!state.claimed) return chooseThePassword(why, "ask.password.unclaimed", state);
  if (state.signed_in) return chooseThePassword(why, "ask.password.change", state);
  return signIn(why);
}

/**
 * Asks for the password this machine has, until it is given or the panel is
 * dismissed.
 * @param {string} [why] - A first line saying what prompted it.
 * @returns {Promise<boolean>} Whether the service accepted it.
 */
async function signIn(why) {
  let complaint = why;

  for (;;) {
    const typed = await askPanelFor({
      title: t("ask.password.title"),
      text: [complaint, t("ask.password.sign-in")].filter(Boolean),
      icon: Art.Computer,
      confirm: t("button.use"),
      secret: true,
    });
    if (typed === null) return false;

    const answer = await send("/api/session", { password: typed });
    if (answer === null) return false;
    if (answer.ok) return true;
    /* A service that has been asked too often says so, because the next
       attempt will fail however right it is. */
    complaint = t(answer.status === 429 ? "ask.password.too-often" : "ask.password.wrong");
  }
}

/**
 * Asks for a password to set, until one is accepted or the panel is dismissed.
 * @param {string} [why] - A first line saying what prompted it.
 * @param {string} what - Which sentence explains the question, by its key.
 * @param {object} state - What /api/session answered, which says how short a
 *   password may be. Read from the service rather than stated here, so the
 *   rule lives where it is enforced.
 * @returns {Promise<boolean>} Whether one was set.
 */
async function chooseThePassword(why, what, state) {
  let complaint = why;

  for (;;) {
    const typed = await askPanelFor({
      title: t("ask.password.title"),
      text: [complaint, t(what), t("ask.password.length", { least: state.smallest })]
        .filter(Boolean),
      icon: Art.Computer,
      confirm: t("button.use"),
      secret: true,
    });
    if (typed === null) return false;

    const answer = await send("/api/password", { password: typed });
    if (answer === null) return false;
    if (answer.ok) return true;
    /* Somebody else claimed this machine whilst the panel stood open, so what
       is due now is the password they chose rather than one of ours. */
    if (answer.status === 403) return signIn(t("ask.password.needed"));
    complaint = t(answer.status === 400
      ? "ask.password.too-short" : "ask.password.not-kept");
  }
}

/**
 * Writes text into an element by id.
 * @param {string} id
 * @param {string} text
 */
function show(id, text) {
  document.getElementById(id).textContent = text;
}

/**
 * Says what the chosen setting of a group does, under its cells.
 * @param {string} id - The note under that group.
 * @param {...string} sentences - One per setting the group holds. A group of
 *   one choice sends one, a group of switches sends one per switch, and a
 *   sentence that does not apply arrives as nothing and is left out.
 *
 * Written by the page rather than carried by the markup, because which
 * sentence applies follows from what is chosen. A note with nothing to say
 * hides itself, which the kit's stylesheet does for an empty one.
 */
function explain(id, ...sentences) {
  show(id, sentences.filter(Boolean).join(" "));
}

/**
 * What a machine is called, from the facts the service sent.
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The model's own name with what is fitted to it.
 *
 * The model is a product name and arrives as it is. What gets added to it is
 * a sentence, so it is added here.
 */
function nameOf(machine) {
  const name = modelOf(machine);
  return machine.dimension ? t("machine.with-dimension", { name }) : name;
}

/**
 * What the machine is called, and nothing about the boards in it.
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The model's own name, with Turbo where that is part of it.
 *
 * For the one place a whole sentence does not fit: a menu entry is a line in a
 * narrow column, and a machine named after everything fitted to it runs off
 * the end of it.
 */
function modelOf(machine) {
  let name = machine.model;
  if (machine.turbo && machine.kind !== 0) name += " Turbo";
  return name;
}

/**
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The processor and its clock.
 */
function cpuOf(machine) {
  return t("machine.cpu", { cpu: machine.cpu, mhz: machine.mhz });
}

/**
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} What the screen shows, which is where colour is decided.
 *
 * A cube has no colour of its own: Previous forces the flag off for that
 * machine type, and colour arrives only through a NeXTdimension.
 */
function screenOf(machine) {
  if (machine.dimension) return t("machine.screen.dimension");
  return t(machine.colour ? "machine.screen.colour" : "machine.screen.grey");
}

/**
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The three chips that decide whether it runs at all.
 */
function chipsOf(machine) {
  return t(machine.nbic ? "machine.chips.with-nextbus" : "machine.chips.without-nextbus",
           { rtc: machine.rtc, scsi: machine.scsi });
}

/**
 * The picture for a machine.
 * @param {string|null} enclosure - What the service called its case.
 * @returns {string} The picture's name. A case nobody knows falls back to the
 *   generic computer, so a service that learns a new machine type before this
 *   page does still draws something.
 */
function machineArt(enclosure) {
  return MACHINE_ART[enclosure] ?? Art.Computer;
}

/**
 * Says how long something has been running, in the words a person uses.
 * @param {number|null} seconds
 * @returns {string}
 */
function since(seconds) {
  if (seconds === null || seconds === undefined) return "";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return t("since.hours", { hours, minutes: String(minutes).padStart(2, "0") });
  }
  if (minutes > 0) return t("since.minutes", { minutes });
  return t("since.less-than-a-minute");
}

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

/**
 * Asks the service to do something to the emulator.
 * @param {string} route - Where to send it.
 * @param {object} [body] - What to send, where the route takes something.
 * @returns {Promise<object|null>} What it answered, or null on no contact.
 */
async function tell(route, body) {
  let answer = await send(route, body);
  if (answer === null) return null;

  /* Refused for want of the password. Ask for it and do what was asked, rather
     than reporting a failure the reader would have to interpret. */
  if (answer.status === 403) {
    const accepted = await askForPassword(t("ask.password.needed"));
    if (!accepted) return { ok: false, reason: "password.not-given" };
    answer = await send(route, body);
    if (answer === null) return null;
  }

  try {
    return await answer.json();
  } catch {
    return null;
  }
}

/**
 * Runs one of the three operations and reports what came of it.
 * @param {string} route - One of Kiosk.
 * @param {string} working - What to say while it happens.
 */
async function operate(route, working) {
  setBusy(true, working);
  const answer = await tell(route);
  setBusy(false, answer === null ? t("note.no-service") : say(answer));
  if (answer) drawStatus(answer);
  refresh();
}

/** The picture of the machine that is configured now, so a panel asking about
 *  it shows it rather than a generic computer. Set from every status. */
let runningArt = Art.Computer;

/** Everything this tool holds, as the service arranged it. */
let root = { name: "Previously", path: "/", entries: [] };

/** The way to the place being shown, outermost first. */
let at = [root];

/** Every machine anywhere in that tree. Kept because the info window says what
 *  a machine is without anything having to run. */
let catalogue = [];

/** Where the shelf's contents live between visits. The things themselves come
 *  from the service; this is only which of them somebody put there. */
const KEPT_KEY = "previously:kept";

/** What lies there before anybody puts anything there: the root, so there is
 *  always one step home, the machines, and the disks, which are the two things
 *  somebody switches between. A shelf entry for a folder that is not there is
 *  dropped when the shelf is drawn, so a machine with no disks shows two. */
const KEPT_BY_DEFAULT = ["/", "/Machines", "/Disks"];

/** The identifiers on the viewer's shelf, in the order they were put there. */
let kept = readKept();

/** @returns {string[]} What was on the shelf last time, or the two that are
 *  there to begin with. An empty shelf is a shelf somebody emptied, and that
 *  is remembered as itself. */
function readKept() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEPT_KEY));
    return Array.isArray(saved) ? saved : [...KEPT_BY_DEFAULT];
  } catch {
    return [...KEPT_BY_DEFAULT];
  }
}

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

/**
 * Fills the shelf with the machines the service offers.
 *
 * The list comes from the service rather than from here, because what can be
 * chosen is decided by what can be written, and keeping a second copy in the
 * page is how the two come to disagree.
 */
async function drawMachines() {
  const answer = await ask("/api/files");
  if (!answer) {
    show("machine-note", t("viewer.unreachable"));
    return;
  }

  root = answer;
  catalogue = allMachines(root);
  /* The applications are in the tree, so what is running can only be drawn
     once it has arrived. */
  noticeTheApplications();
  /* Stay where the reader was, by path rather than by object, because the
     tree they are looking at was fetched again. */
  at = at.map((step) => find(root, step.path)).filter(Boolean);
  if (!at.length) at = [root];
  drawPlace();
}

/**
 * Every machine anywhere in the tree.
 * @param {object} folder - Where to look.
 * @returns {object[]} The machines, in the order they are met.
 *
 * The info window says what a machine is without caring where it sits, so it
 * reads from this rather than from wherever the viewer happens to be.
 */
function allMachines(folder) {
  return (folder.entries ?? []).flatMap((entry) =>
    entry.kind === "machine" ? [entry] : allMachines(entry));
}

/** Draws whatever place the viewer is in, with the way there above it. */
function drawPlace() {
  const viewer = document.getElementById("file-viewer");
  const here = at[at.length - 1];
  viewer.show({
    path: at.map(entryFor),
    contents: (here.entries ?? []).map(entryFor),
    /* Anything can lie on the shelf, a folder as readily as a machine, so
       this looks in the whole tree rather than among the machines. */
    keeps: kept.map((path) => find(root, path)).filter(Boolean).map(entryFor),
    status: saying(here),
  });
  markCurrent(lastStatus?.configuration?.catalogue,
              lastStatus?.file?.newer_than_the_machine);
}

/**
 * The line under the shelf.
 * @param {object} folder - The place being shown.
 * @returns {string} Which place, what is in it, and what cannot be done to it.
 *
 * It names the place because of where it sits: directly under the shelf, which
 * holds something else entirely. NeXTSTEP put a fact about the whole disk
 * there and had no such question to answer.
 */
function saying(folder) {
  const count = (folder.entries ?? []).length;
  return t("viewer.status", {
    name: nameFor(folder),
    count: t("viewer.count", { count }, count),
    more: folder.writable === false ? t("viewer.read-only") : "",
  });
}

/**
 * One entry as the viewer wants it.
 * @param {object} entry - A folder, an application or a machine.
 * @returns {object} `{label, icon, value}`. The value is the entry's path,
 *   which is what a drop, a double click and the menu all hand over, so there
 *   is one place a thing's name lives.
 */
function entryFor(entry) {
  return {
    label: nameFor(entry),
    /* A folder and an application bring their own picture. A machine wears
       the one its boot ROM draws, and which that is follows from its case. */
    icon: entry.icon ?? machineArt(entry.enclosure),
    value: entry.path,
    folder: entry.kind === "folder",
  };
}

/**
 * What one entry of the tree is called, here, now.
 * @param {object} entry - A folder, an application or a machine.
 * @returns {string} The words for it in the language being read, or its own
 *   name where it has one that belongs to it.
 *
 * Everything in the tree keeps the name it came with, because a viewer shows
 * names: the folders, the bundles, the machines and Previously itself. A
 * German NeXTSTEP holds a directory called `Apps` and a bundle called
 * `Preferences.app`, and its viewer shows both as it finds them.
 *
 * What an application is called in words is a different question, and appName
 * answers that one.
 */
function nameFor(entry) {
  if (entry.kind === "application" || !entry.label) return entry.name;
  return t(entry.label);
}

/**
 * @param {object} entry - An application.
 * @returns {string} What it is called in words, without the suffix its file
 *   name carries.
 *
 * NeXTSTEP kept the two apart and so does this. The bundle in `/NextApps` was
 * `Preferences.app` in every language, whilst the application called itself
 * `Präferenzen` in German wherever it named itself in a sentence, which is
 * what its own `preferences.strings` holds.
 */
function appName(entry) {
  return entry.label ? t(entry.label) : entry.name.replace(APPLICATION, "");
}

/**
 * Answers a double click in the viewer, whatever was under it.
 * @param {string} path - What the thing carries.
 */
function open(path, asker) {
  const entry = find(root, path);
  if (!entry) return;
  if (entry.kind === "folder" || entry.path === "/") {
    /* Built from the path rather than by adding a step, because a folder on
       the shelf can be anywhere and the way there is not the way from here. */
    at = chainTo(entry.path);
    return openFolder(asker);
  }
  if (entry.kind === "application") {
    /* The editor is opened on a machine rather than on nothing, so it goes
       through the one place that decides which. Every other application's window
       holds whatever it holds. */
    if (entry.opens === EDITOR) return editOnWhatIsRunning(asker);
    /* An application this tool has is a window it already holds. One it does
       not have yet says so, which is the honest thing to do with an icon that
       is there because the place it sits in is being built around it. */
    const window_ = document.querySelector(`nx-window[name="${entry.opens}"]`);
    return window_ ? window_.open(asker) : notYet(appName(entry));
  }
  if (entry.kind === "picture") return showInPreview(entry);
  /* A disk is chosen the same way a machine is, because it is the same act:
     the guest goes down, one thing is written, and it comes back. */
  if (entry.kind === "disk") return bootFromDisk(entry);
  /* And a copy of one is put back, which is the only thing to do with it. */
  if (entry.kind === "backup") return putTheCopyBack(entry);
  /* A disc goes into the machine, or comes out of it again. */
  if (entry.kind === "disc") return useTheDisc(entry);
  /* Named rather than left as what everything else falls through to, because
     what else is in here has grown and falling through would have asked the
     machine to become whatever was double clicked. */
  if (entry.kind === "machine") changeTo(entry.id);
}

/**
 * Draws the place the viewer has moved to, with the way there where it is
 * known.
 * @param {HTMLElement} [asker] - The thing that was opened, if one was.
 *
 * The rectangles run from the mark around that thing to the band that is
 * about to hold what was inside it, and the contents change when they arrive.
 * Without a thing to start from, which is what a step of the path is, the
 * place simply changes.
 */
async function openFolder(asker) {
  const band = document.querySelector("#file-viewer nx-scroller:last-child");
  /* Only from the band below. The original draws this nowhere else: what is
     opened from the shelf flies to the path instead, and a step of the path
     is a way back rather than something being opened. */
  const fromTheBand = asker?.closest?.(".contents");
  if (!fromTheBand || !band) return drawPlace();

  await zoom(deskRect(asker), deskRect(band));
  drawPlace();
}

/**
 * Answers one click on the shelf.
 * @param {string} where - The path of what was clicked.
 * @param {HTMLElement} thing - What was clicked, which is where its icon
 *   starts from.
 *
 * A folder on the shelf changes what the viewer shows, and its icon travels
 * to the place it takes in the path as it does. Anything else there is a
 * machine, and clicking one chooses it and nothing more.
 */
async function visitFromTheShelf(where, thing) {
  const entry = find(root, where);
  if (!entry || !(entry.kind === "folder" || entry.path === "/")) return;

  /* Already where the viewer is standing, which the path shows by ending on
     it. There is nothing to fly to and nothing to redraw, and an icon that
     travels to the place it is already in says something happened when
     nothing did. */
  if (at.at(-1)?.path === entry.path) return;

  const from = deskRect(thing);
  at = chainTo(entry.path);
  drawPlace();

  const steps = document.querySelectorAll("#file-viewer .path nx-thing");
  const landing = steps[steps.length - 1];
  if (!from || !landing) return;

  landing.style.visibility = "hidden";
  await fly(landing.getAttribute("icon"), from, deskRect(landing), NEAR_FLIGHT_MS);
  landing.style.visibility = "";
}

/**
 * The way from the root to a place, as the steps themselves.
 * @param {string} where - A path such as "/Machines/System".
 * @returns {object[]} The root first, that place last.
 */
function chainTo(where) {
  const steps = [root];
  let path = "";
  for (const part of where.split("/").filter(Boolean)) {
    path += "/" + part;
    const step = find(root, path);
    if (!step) break;
    steps.push(step);
  }
  return steps;
}

/**
 * Goes back to a step of the path.
 * @param {number} index - Which step, counted from the root.
 */
function goTo(index) {
  at = at.slice(0, index + 1);
  drawPlace();
}

/**
 * @param {object} folder - Where to look.
 * @param {string} path - What to look for.
 * @returns {object|null} The entry with that path, anywhere below.
 */
function find(folder, path) {
  if (folder.path === path) return folder;
  for (const entry of folder.entries ?? []) {
    const found = find(entry, path);
    if (found) return found;
  }
  return null;
}

/**
 * Puts a machine on the viewer's shelf, or takes it off again.
 * @param {string} where - The machine's path in the tree.
 * @param {boolean} onto - True to put it there, false to take it off.
 *
 * The shelf is for the two or three somebody actually switches between. It is
 * kept in this browser rather than on the Pi: which machines one person wants
 * to hand is not a property of the machine.
 */
function keepOnShelf(where, onto) {
  kept = kept.filter((entry) => entry !== where);
  if (onto) kept.push(where);
  try {
    localStorage.setItem(KEPT_KEY, JSON.stringify(kept));
  } catch {
    /* A browser that refuses to store it still shows it for this visit. */
  }
  drawMachines();
}

/**
 * Marks the machine the emulator is currently set to.
 * @param {string|null} identifier - Which of the eleven the file holds exactly,
 *   or null where it holds none of them.
 * @param {boolean} [untried] - Whether the file has been written since that
 *   machine started, so what is written down has never been through a boot.
 *
 * By identifier rather than by name, because two of the eleven differ from
 * another two by their clock alone and share a name in the file.
 */
function markCurrent(identifier, untried) {
  for (const thing of document.querySelectorAll("#file-viewer nx-thing")) {
    const where = thing.getAttribute("value");
    const entry = catalogue.find((machine) => machine.path === where);
    /* A disk carries which one the machine boots, because the service reads
       that out of the configuration and the browser has no business working it
       out from a path. The same mark, because it is the same statement: this
       is the one in force. */
    const isCurrent = entry
      ? Boolean(identifier) && entry.id === identifier
      : Boolean(find(root, where)?.booting);
    thing.classList.toggle("current", isCurrent);
    thing.classList.toggle("untried", isCurrent && Boolean(untried));
    /* Switching to the machine that is already running would shut NeXTSTEP
       down, write the same values back and start it again, for nothing. */
    thing.toggleAttribute("disabled", isCurrent);
    if (isCurrent) thing.removeAttribute("chosen");
  }
}

/**
 * When a moment was, in the words a person here uses.
 * @param {number|null} seconds - A Unix timestamp.
 * @returns {string} The date and time, or an em dash where there is none.
 */
function when(seconds) {
  if (!seconds) return NOTHING;
  /* In the language the interface speaks, because a date written the German
     way in an English panel is a date somebody has to stop and read. */
  return new Date(seconds * 1000).toLocaleString(currentLocale(), {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

/**
 * When the configuration file was last written.
 * @param {object|undefined} file - What the service says about previous.cfg.
 * @returns {string} The moment, and a note where the running machine is older
 *   than the file. Previous reads the file once at its start, so anything
 *   written afterwards is a machine nobody has tried.
 */
function changedLine(file) {
  if (!file) return NOTHING;
  return t(file.newer_than_the_machine ? "file.changed-not-booted" : "file.changed",
           { when: when(file.changed_at) });
}

/**
 * Who wrote the configuration file last.
 * @param {object|undefined} file - What the service says about previous.cfg.
 * @returns {string} One of two sentences. Previously leaves a note of what it
 *   wrote, so a file that no longer matches that note came from somewhere
 *   else, and the two candidates are the emulator's own settings dialogue and
 *   somebody at the keyboard.
 */
function writtenLine(file) {
  if (!file) return NOTHING;
  return t(file.written_by_us ? "file.by-previously" : "file.by-previous-or-hand");
}

/**
 * How a machine's memory is made up.
 * @param {number[]} banks - The four banks in megabytes, empty ones as zero.
 * @returns {string} "4 × 32" where every filled bank is the same size, and
 *   "16 + 8" where they are not. Empty banks are left out: a bank with nothing
 *   in it is a socket, and nobody counts sockets.
 */
function fitted(banks) {
  const filled = banks.filter((size) => size > 0);
  if (!filled.length) return t("machine.banks-empty");
  return filled.every((size) => size === filled[0])
    ? `${filled.length} × ${filled[0]}`
    : filled.join(" + ");
}

/**
 * Shows what one machine is, in a window of its own.
 * @param {string} where - The machine's path in the tree.
 *
 * The settings come from the catalogue, so a machine that is not running is
 * described exactly as the running one is. The two lines about the file are
 * about the file rather than about the machine, so they are filled in only for
 * the machine the file actually holds.
 */
function showMachineInfo(where) {
  const machine = catalogue.find((entry) => entry.path === where);
  if (!machine) return;

  const window_ = document.querySelector('nx-window[name="machine-info"]');
  window_.rename(machine.name);
  show("mi-caption", machine.name);
  document.getElementById("mi-icon").style.backgroundImage =
    `var(--${machineArt(machine.enclosure)})`;

  show("mi-cpu", cpuOf(machine));
  show("mi-ram", t("machine.memory-banks",
                   { mb: machine.memory_mb, banks: fitted(machine.banks) }));
  show("mi-screen", screenOf(machine));
  show("mi-dimension", t(machine.dimension
    ? "machine.dimension.fitted" : "machine.dimension.none"));
  show("mi-chips", chipsOf(machine));

  /* The file holds one machine, so everything it can say applies to that one
     and to no other. */
  const file = lastStatus?.file;
  /* By identifier rather than by name, because the file cannot carry the
     Nitro that the catalogue's name does. */
  const isTheOneInTheFile = lastStatus?.configuration?.catalogue === machine.id;
  if (!file || !isTheOneInTheFile) {
    show("mi-changed", t("file.other-machine"));
    show("mi-written", NOTHING);
  } else {
    show("mi-changed", changedLine(file));
    show("mi-written", writtenLine(file));
  }

  window_.open();
}

/**
 * Asks about a machine and changes to it when the answer is yes.
 * @param {string} identifier - Which machine, as the catalogue names it.
 *   The catalogue's own identifier rather than a path, because that is what
 *   the service takes.
 */
async function changeTo(identifier) {
  const machine = catalogue.find((entry) => entry.id === identifier);
  if (!machine) return;

  const name = machine.name;
  /* What is in the file now is nobody's machine from this list, so saying it
     will be written over is the difference between a change and a loss. */
  const own = Boolean(lastStatus?.configuration) && !lastStatus.configuration.catalogue;
  const agreed = await askPanel({
    title: t("ask.change.title"),
    text: [
      t("ask.change.question", { machine: name }),
      own && t("ask.change.own"),
      t("ask.change.how"),
      t("ask.change.rollback"),
    ].filter(Boolean),
    /* The same picture it wears in the viewer, taken from the same place. */
    icon: machineArt(machine.enclosure),
    confirm: t("button.change"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: name }));
  const answer = await tell("/api/machine", { machine: identifier });
  setBusy(false, answer === null ? t("note.no-service") : say(answer));
  if (answer) drawStatus(answer);
  refresh();
}

/**
 * Asks about a disk and makes the machine boot it when the answer is yes.
 * @param {object} disk - Its entry in the tree.
 *
 * Nothing is fetched and nothing is copied. Each system is one file, the guest
 * writes into that file, and pointing the machine elsewhere leaves the first
 * exactly as it was left. That is the sentence somebody who has spent an
 * evening inside NeXTSTEP wants to read before they press anything, so it is
 * in the question rather than in a manual.
 */
async function bootFromDisk(disk) {
  if (disk.booting) return;

  const agreed = await askPanel({
    title: t("ask.disk.title"),
    text: [
      t("ask.disk.question", { name: disk.name }),
      t("ask.disk.size", { name: disk.name, size: sized(disk.bytes) }),
      t("ask.disk.freeze"),
      /* The same two sentences a change of machine ends on, because it is the
         same act and the same risk. */
      t("ask.change.how"),
      t("ask.change.rollback"),
    ],
    icon: Art.Disk,
    /* The same word as the button that opens this, wherever it was opened
       from. Two words for one act is one word too many. */
    confirm: t("button.activate"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: disk.name }));
  /* The tree says which disk is in force, so it is asked for again rather than
     marked from here. */
  reportAboutTheMachine(await tell("/api/disk", { disk: disk.id }));
}

/**
 * Puts a disc into the machine, or takes it out again.
 * @param {object} disc - Its entry in the tree, which says which slot it is on
 *   where it is in the machine at all.
 *
 * One gesture for both, because it is one thing: the disc is either in the
 * machine or it is not, and a double click swaps that over. The same as taking
 * a board out and putting it back, which is what this interface already does
 * wherever something is in or out rather than one of several.
 */
function useTheDisc(disc) {
  return disc.slot === null ? putTheDiscIn(disc) : takeTheDiscOut(disc);
}

/**
 * Asks about a disc, and puts it in the machine when the answer is yes.
 * @param {object} disc - Its entry in the tree.
 *
 * It goes beside the disk the machine boots rather than instead of it, on a
 * free slot of the bus, and it is read only there because that is what a disc
 * is.
 */
async function putTheDiscIn(disc) {
  const agreed = await askPanel({
    title: t("ask.disc.title", { name: disc.name }),
    text: [
      t("ask.disc.beside"),
      /* NeXT's own CDs carry a variation of 4.3BSD FFS, so an image that says
         ISO 9660 mounts nowhere however good it is. Said before somebody waits
         for a machine to come back with nothing new in it. */
      disc.iso ? t("ask.disc.iso") : "",
      t("ask.change.how"),
      t("ask.change.rollback"),
    ].filter(Boolean),
    icon: Art.Disc,
    confirm: t("button.insert"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: disc.name }));
  const answer = await tell("/api/disc", { disc: disc.id });
  reportAboutTheMachine(answer);
}

/**
 * Asks about a disc that is in the machine, and takes it out when the answer
 * is yes.
 * @param {object} disc - Its entry in the tree.
 */
async function takeTheDiscOut(disc) {
  const agreed = await askPanel({
    title: t("ask.disc.eject-title", { name: disc.name }),
    text: [t("ask.disc.eject-question"), t("ask.change.how")],
    icon: Art.Disc,
    confirm: t("button.eject"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: disc.name }));
  const answer = await tell("/api/disc/eject", { slot: disc.slot });
  reportAboutTheMachine(answer);
}

/**
 * Says what came of a change to the machine, and draws everything again.
 * @param {object|null} answer - What the service said, or null on no contact.
 *
 * The tree as well as the status, because what it says about a disk or a disc
 * comes out of the same file that has just been written.
 */
function reportAboutTheMachine(answer) {
  setBusy(false, answer === null ? t("note.no-service") : say(answer));
  if (answer) drawStatus(answer);
  drawMachines();
  refresh();
}

/**
 * Asks about a copy of a disk, and has one made when the answer is yes.
 * @param {object} disk - Its entry in the tree.
 *
 * Two gigabytes, so what it costs and what would be left are in the question
 * rather than in a failure afterwards. The figures are fetched at the moment
 * the question is put, because what is free changes with everything else on
 * the machine.
 */
async function backUpTheDisk(disk) {
  const state = await ask(SETUP);
  const agreed = await askPanel({
    title: t("ask.backup.title", { name: disk.name }),
    text: [
      t("ask.backup.cost", { name: disk.name, size: sized(disk.bytes) }),
      state ? t("ask.fetch.left", {
        free: sized(state.room),
        left: sized(Math.max(0, state.room - disk.bytes)),
      }) : "",
      t("ask.backup.off"),
      t("ask.install.time"),
    ].filter(Boolean),
    icon: Art.Disk,
    confirm: t("button.copy"),
  });
  if (agreed) askTheInstallerToCopy("/api/disk/backup", { system: disk.id });
}

/**
 * Asks about a copy, and writes it back over its disk when the answer is yes.
 * @param {object} copy - Its entry in the tree.
 *
 * The one thing that can be done with a copy, and the one that cannot be
 * undone: what is on the disk now is written over. So the question says that
 * before it says anything else.
 */
async function putTheCopyBack(copy) {
  const agreed = await askPanel({
    title: t("ask.restore.title", { name: copy.name }),
    text: [t("ask.restore.loss"), t("ask.backup.off"), t("ask.install.time")],
    icon: Art.Disk,
    confirm: t("button.put-back"),
  });
  if (agreed) {
    askTheInstallerToCopy("/api/disk/restore",
                          { system: copy.system, backup: copy.id });
  }
}

/**
 * Leaves a request for a copy and shows the window that watches it.
 * @param {string} route - Which of the two.
 * @param {object} body - What to send.
 *
 * The Installer is opened, because it is the window that says what the Pi is
 * doing and this takes minutes. Starting a five minute job from a viewer and
 * leaving nothing on the screen about it would be the worst of both.
 */
async function askTheInstallerToCopy(route, body) {
  const answer = await tell(route, body);
  show("machine-note", answer === null ? t("note.no-service") : say(answer));
  if (!answer?.ok) return;

  document.querySelector('nx-window[name="installer"]')?.open();
  refreshTheInstaller();
}

/**
 * Gives a saved configuration another name.
 * @param {object} machine - Its entry in the tree.
 *
 * Only a configuration somebody saved has a name to change. The eleven are the
 * set to go back to, and the menu does not offer this for them at all.
 */
async function renameConfiguration(machine) {
  const typed = await askPanelFor({
    title: t("ask.rename.title", { name: machine.name }),
    text: [t("ask.rename.question")],
    icon: machineArt(machine.enclosure),
    confirm: t("button.rename"),
  });
  if (typed === null) return;

  reportAboutTheSaved(
    await tell(Saved.Rename, { machine: machine.id, name: typed }));
}

/**
 * Takes a saved configuration out of the list, after asking.
 * @param {object} machine - Its entry in the tree.
 *
 * Asked first, because there is no wastebasket here to fish one out of again.
 * What this does not touch is the running machine: previous.cfg is the
 * emulator's own file, so a machine running this configuration goes on running
 * it.
 */
async function removeConfiguration(machine) {
  const sure = await askPanel({
    title: t("ask.remove.title", { name: machine.name }),
    text: [t("ask.remove.loss")],
    icon: machineArt(machine.enclosure),
    confirm: t("button.remove"),
  });
  if (!sure) return;

  reportAboutTheSaved(await tell(Saved.Remove, { machine: machine.id }));
}

/**
 * Says what came of a change to the saved configurations, and draws them again.
 * @param {object|null} answer - What the service said, or null on no contact.
 *
 * The line under the viewer, because that is the window this happened in. The
 * status is asked for again as well: the machine in force may be the one that
 * has just been renamed, and the info window names it.
 */
function reportAboutTheSaved(answer) {
  show("machine-note", answer === null ? t("note.no-service") : say(answer));
  drawMachines();
  refresh();
}

/* --- the Config Editor ----------------------------------------------------

   Previous's own System dialogue, in this interface's idiom: what can be chosen
   on one side and what follows from it on the other. Here the picture and its
   readings stand over the groups that change them.

   It holds no rule of its own. What a choice turns into, and what may be chosen
   beside it, are both asked of the service on every change, so there is one
   statement of what Previous allows and this window cannot offer a machine the
   emulator would correct underneath it. That is also why the configuration it
   saves is the one the service handed back rather than one assembled here. */

/** What the editor is showing: the controls, and nothing derived.
 *
 *  Whatever is not known is left out of the question rather than filled in here,
 *  so a fresh window is answered with the service's own idea of a machine and
 *  there is no second copy of that here. */
let drafting = {};

/** Which controls the service writes afresh whenever the machine type or a
 *  board changes, so that changing one of those sends none of them. Named here
 *  rather than at each cell, because a control this forgets to name is one that
 *  quietly carries a value from the machine that has been left behind. */
const FOLLOWS_THE_MACHINE = ["mhz", "dsp", "dsp_memory", "banks"];

/** What each DSP is called. The service answers the three by name, because the
 *  numbers Previous writes are not in the order a person would read them in, and
 *  these are this page's words for those names. Written out one by one rather
 *  than built from the name, so that a key nothing answers is caught by the
 *  strings test instead of appearing as an empty cell. */
const DSP_WORDS = {
  none: "editor.dsp.none",
  plain: "editor.dsp.plain",
  "with-rom": "editor.dsp.with-rom",
};

/** What each ethernet socket is called, written out for the same reason. */
const SOCKET_WORDS = {
  "thin-wire": "editor.thin-wire",
  "twisted-pair": "editor.twisted-pair",
};

/** What the sentence about each machine type is called, by the number Previous
 *  gives the type. Written out rather than built from the number, because a
 *  sentence keyed by a name can be found in the catalogue and one keyed by 1
 *  cannot. The strings test holds these numbers to the types the service
 *  offers. */
const KIND_NOTES = {
  0: "editor.machine.note.next-computer",
  1: "editor.machine.note.nextcube",
  2: "editor.machine.note.nextstation",
};

/** The least the first memory bank may hold for the machine to boot, in
 *  megabytes. Previous says so on its own memory dialogue and does not raise a
 *  smaller bank itself, so the note under the banks is the one place somebody
 *  is told before the machine fails to come up. */

/** How much memory a NeXTdimension board gets when it is first put in, which is
 *  what the emulator's own file holds for one. Changed from there in its own
 *  group, so this decides only where somebody starts. */
const DIMENSION_DEFAULT_MEMORY = 32;

/** What the editor shows one of at a time, and what each is called, in the order
 *  a machine is put together: what it is, what runs in it, what it remembers,
 *  what it draws with, and what is plugged into it. Every group in the markup
 *  carries one of these names, which the page test holds it to. */
const SUBJECTS = {
  machine: "editor.subject.machine",
  processor: "editor.subject.processor",
  memory: "editor.subject.memory",
  graphics: "editor.subject.graphics",
  fitted: "editor.subject.fitted",
};

/** Which of them is showing. Kept here rather than read back off the markup, so
 *  a redraw after a change leaves somebody where they were rather than sending
 *  them to the first subject. */
let showing = Object.keys(SUBJECTS)[0];

/** Which saved configuration is being written over, or null where what comes out
 *  of this is a new one. A System machine cannot be changed, so editing one
 *  leaves this null and saving asks for a name. */
let replacing = null;

/** The last answer about the draft, so saving posts what was shown rather than
 *  asking again for something that may meanwhile read differently. Null whilst
 *  an answer is still on its way, which is what stops the button saving the
 *  machine that was in the window a moment ago. */
let drafted = null;

/** Which question about the draft is the current one. Every click asks one, and
 *  an answer that arrives after a newer question was asked is dropped rather
 *  than drawn over it. */
let asking = 0;

/**
 * Opens the editor on a machine.
 * @param {object} machine - An entry of the tree, or what /api/status says is
 *   configured now. Both carry the same facts, because one function describes
 *   them.
 * @param {HTMLElement} [asker] - What was used to open it, so its icon can
 *   travel to the floor of the screen.
 *
 * A configuration of somebody's own is edited in place, and one of the eleven is
 * the starting point for a new one. That is the whole difference between the two
 * sets, and it is decided here by which folder the machine came from.
 */
function editConfiguration(machine, asker) {
  replacing = machine?.set === "user" ? machine.id : null;
  /* The configuration a tree entry carries beside the words a person reads,
     which is the same shape saving takes. The description alone would not do:
     it leaves out everything two machines do not differ by in words, and its
     `kind` says what sort of entry this is rather than what machine it is. */
  drafting = machine?.configuration
    ? { ...machine.configuration }
    : whatTheDescriptionSays(machine);
  /* Nothing to save until the service has said what this is, so the button
     cannot send the machine the window held before. */
  drafted = null;

  drawTheTitle();
  document.querySelector(`nx-window[name="${EDITOR}"]`).open(asker);
  drawTheDraft();
}

/**
 * As much of a machine as a description holds.
 * @param {object} machine - What /api/status says is configured now, which is a
 *   description rather than a configuration.
 * @returns {object} A draft of what can be read off it.
 *
 * For the machine that is running whilst being none of the ones this tool
 * knows. What a description does not carry is left out rather than guessed, so
 * the service answers those with what that machine has.
 */
function whatTheDescriptionSays(machine) {
  return {
    kind: machine?.kind,
    turbo: Boolean(machine?.turbo),
    colour: Boolean(machine?.colour),
    mhz: machine?.mhz,
    memory: machine?.memory_mb,
  };
}

/** Puts the name of what is being edited in the title bar.
 *
 *  A configuration of one's own is a document and is titled with its name, the
 *  way the Preview window is titled with the picture's. One that has no name yet
 *  is titled with the application's, because what is being made is new. */
function drawTheTitle() {
  document.querySelector(`nx-window[name="${EDITOR}"]`)
    ?.rename(replacing ?? t("app.config-editor"));
}

/** Asks the service what the draft is, and draws the answer. */
async function drawTheDraft() {
  const asked = new URLSearchParams();
  for (const [control, value] of Object.entries(drafting)) {
    if (value === undefined || value === null) continue;
    if (typeof value === "boolean") {
      /* As "1" and "0", because a query string carries text and a flag that is
         absent has to read as off rather than as a word. */
      asked.set(control, value ? "1" : "0");
    } else if (Array.isArray(value)) {
      /* The four memory banks, in one field, in the order they sit in. */
      asked.set(control, value.join(","));
    } else {
      asked.set(control, value);
    }
  }

  const mine = ++asking;
  const answer = await ask("/api/machine/settled?" + asked);
  /* A click whilst this was on its way asked a newer question, and that one's
     answer is the one the window belongs to. */
  if (mine !== asking) return;
  if (!answer) {
    show("editor-note", t("note.no-service"));
    return;
  }

  drafted = answer;
  /* What came back may differ from what was asked for, because Previous refuses
     some of it. The draft follows the answer, so the next question is asked
     about the machine that actually exists. */
  drafting = {
    kind: answer.configuration.kind,
    turbo: answer.configuration.turbo,
    colour: answer.configuration.colour,
    dimensions: answer.configuration.dimensions,
    mhz: answer.machine.mhz,
    memory: answer.machine.memory_mb,
    dsp: answer.configuration.dsp,
    dsp_memory: answer.configuration.dsp_memory,
    /* Carried on, so a bank chosen on its own is asked about again rather than
       being laid out afresh from the total the next question would send. The
       total goes back in charge when a cell in its group is pressed, which
       sends no banks at all. */
    banks: answer.configuration.banks,
    floppy: answer.configuration.floppy,
    optical: answer.configuration.optical,
    ethernet: answer.configuration.ethernet,
    socket: answer.configuration.socket,
    printer: answer.configuration.printer,
  };

  redrawTheEditor();
}

/** Draws the window from the last answer, without asking for it again.
 *
 *  Every word in it is this page's, so a change of language is redrawn from what
 *  is already here rather than by asking the service what it just said. */
function redrawTheEditor() {
  if (!drafted) return;
  drawTheMachineInTheEditor(drafted.machine);
  drawTheChoices(drafted.offers);
  drawWhatSavingWillDo();
}

/**
 * Draws what the drafted machine is, in the words the rest of the interface
 * uses for a machine.
 * @param {object} machine - The facts, as config.describe answers them.
 */
function drawTheMachineInTheEditor(machine) {
  document.getElementById("editor-icon").style.backgroundImage =
    `var(--${machineArt(machine.enclosure)})`;
  show("editor-caption", nameOf(machine));
  show("editor-cpu", cpuOf(machine));
  show("editor-ram", t("machine.memory-banks",
                       { mb: machine.memory_mb, banks: fitted(machine.banks) }));
  show("editor-screen", screenOf(machine));
  show("editor-chips", chipsOf(machine));
}

/**
 * Draws the cells of every group from what the service says may be chosen, and
 * under each group the sentence about what is chosen there.
 * @param {object} offers - Its answer: the machine types, which boards may be
 *   seated, which clocks there are and which totals of memory.
 *
 * A group with nothing to offer is taken away rather than shown empty, which is
 * what Previous does with its own board options on a machine that takes none.
 *
 * The sentences are keyed by what is chosen, so a group of one choice shows the
 * one for its value and a group of switches shows one per switch for the state
 * it is in. What holds for every value of a group, such as the machine type
 * setting three other groups afresh, is one sentence appended to all of them.
 */
function drawTheChoices(offers) {
  drawTheSubjects();

  fillWithChoices("editor-kinds", offers.kinds.map((kind) => ({
    label: kind.model,
    chosen: kind.kind === drafting.kind,
    choose: () => changeTheMachine({ kind: kind.kind }),
  })));
  explain("editor-kinds-note",
    KIND_NOTES[drafting.kind] ? t(KIND_NOTES[drafting.kind]) : "",
    t("editor.machine.note.resets"));

  const boards = [
    ["turbo", t("editor.turbo")],
    ["colour", t("editor.colour")],
  ].filter(([which]) => offers[which]);
  fillWithChoices("editor-boards", boards.map(([which, label]) => ({
    label,
    chosen: drafting[which],
    /* A board is seated or it is not, so its cell answers a second click by
       taking it out again. */
    choose: () => changeTheMachine({ [which]: !drafting[which] }),
  })));
  document.getElementById("editor-boards-group").hidden = !boards.length;
  explain("editor-boards-note",
    ...boards.map(([which]) => switchNote(which)),
    t("editor.boards.note.resets"));

  fillWithScale("editor-clocks", t("editor.unit.mhz"),
    offers.clocks.map((mhz) => ({
      value: mhz, label: t("editor.mhz", { mhz }), tick: String(mhz),
    })),
    drafting.mhz, (mhz) => change({ mhz }));
  explain("editor-clocks-note", noteFor("clock", drafting.mhz));

  fillWithScale("editor-memory", t("editor.unit.mb"),
    offers.memory.map((mb) => ({
      value: mb, label: t("editor.megabytes", { mb }), tick: String(mb),
    })),
    /* The banks below may add up to a total the scale does not carry, and then
       the knob stands at the start rather than pretending to a step. */
    drafting.memory,
    /* A total lays the banks out again, so whatever they were is let go. */
    (mb) => change({ memory: mb, banks: undefined }));
  /* Banks set one at a time can add up to a total no cell offers, and then the
     sentence says so rather than describing a cell nobody chose. */
  explain("editor-memory-note",
    offers.memory.includes(drafting.memory)
      ? noteFor("memory", drafting.memory)
      : t("editor.memory.note.by-hand", { mb: drafting.memory }),
    t("editor.memory.note.lays-out"));

  fillWithBanks("editor-banks", offers.banks);
  explain("editor-banks-note", ...bankNotes(offers.banks));

  fillWithChoices("editor-dsps", offers.dsps.map((dsp) => ({
    /* A chip this page has no word for is shown as the service named it, so a
       service that learns a fourth still draws a cell somebody can press. */
    label: DSP_WORDS[dsp] ? t(DSP_WORDS[dsp]) : dsp,
    chosen: dsp === drafting.dsp,
    choose: () => change({ dsp }),
  })));
  explain("editor-dsps-note", noteFor("dsp", drafting.dsp));

  fillWithChoices("editor-dsp-memory", offers.dsp_memory.map((kb) => ({
    label: t("editor.kilobytes", { kb }),
    chosen: kb === drafting.dsp_memory,
    choose: () => change({ dsp_memory: kb }),
  })));
  document.getElementById("editor-dsp-memory-group").hidden =
    !offers.dsp_memory.length;
  explain("editor-dsp-memory-note", noteFor("dsp-memory", drafting.dsp_memory));


  /* What the machine has, which is a drive or a port being there rather than
     anything in it. The same cells as the boards group: one press puts it in and
     the next takes it out. */
  const drives = fillWithFittings("editor-drives", offers, [
    ["floppy", t("editor.floppy")],
    ["optical", t("editor.optical")],
  ]);
  explain("editor-drives-note", ...drives.map(switchNote));
  const ports = fillWithFittings("editor-ports", offers, [
    ["ethernet", t("editor.ethernet")],
    ["printer", t("editor.printer")],
  ]);
  explain("editor-ports-note", ...ports.map(switchNote));

  fillWithChoices("editor-sockets", offers.sockets.map((socket) => ({
    label: SOCKET_WORDS[socket] ? t(SOCKET_WORDS[socket]) : socket,
    chosen: socket === drafting.socket,
    choose: () => change({ socket }),
  })));
  document.getElementById("editor-socket-group").hidden = !offers.sockets.length;
  explain("editor-sockets-note", noteFor("socket", drafting.socket));

  drawTheDimensionBoards(offers);
}

/**
 * The sentence about one value of a group.
 * @param {string} group - The group's name in the catalogue, such as `clock`.
 * @param {string|number} value - What is chosen there, which is the last part
 *   of the key.
 * @param {object} [values] - What fills the sentence's places.
 * @returns {string}
 *
 * Built from the value rather than written out per value, so a clock or a size
 * the service starts to offer arrives with its sentence or fails the strings
 * test, which derives every key this can build from the service.
 */
function noteFor(group, value, values) {
  return t(`editor.${group}.note.${value}`, values);
}

/**
 * The sentence about a switch, for the state it is in.
 * @param {string} which - The switch, such as `turbo` or `floppy`, which is
 *   both the control's name in the draft and its name in the catalogue.
 * @returns {string}
 */
function switchNote(which) {
  return noteFor(which, drafting[which] ? "in" : "out");
}

/**
 * What the four memory banks have to say about themselves.
 * @param {Array<Array<number>>} banks - What each bank accepts, as the service
 *   offers them, with an empty bank as the first size of each.
 * @returns {string[]} The sentences that apply, and nothing for those that do
 *   not.
 *
 * Which modules the machine takes is read off the first bank, because every
 * bank that is there takes the same ones. A bank that is not there offers an
 * empty one and nothing else, which is how the reachable banks are counted here
 * without the page holding the rule that decides them.
 */
function bankNotes(banks) {
  /* Read off a bank that is not the first, since that one is offered neither an
     empty socket nor the smallest module and would name a shorter list than the
     machine actually takes. */
  const ordinary = banks.find((sizes, bank) => bank > 0 && !isAbsent(sizes));
  const modules = (ordinary ?? banks[0]).filter((size) => size > 0);
  const reachable = banks.filter((sizes) => !isAbsent(sizes)).length;
  return [
    t("editor.banks.note.press"),
    t("editor.banks.note.first", { sizes: listed(banks[0]) }),
    t("editor.banks.note.modules", { sizes: listed(modules) }),
    reachable < banks.length
      ? t("editor.banks.note.reach", { count: reachable }) : "",
  ];
}

/**
 * Several values in one phrase, joined the way the language being read joins
 * them.
 * @param {Array<number|string>} values
 * @returns {string} "1, 4 or 16" in English and "1, 4 oder 16" in German. The
 *   browser knows each language's word before the last one, so no catalogue
 *   has to say it.
 */
function listed(values) {
  return new Intl.ListFormat(currentLocale(), { type: "disjunction" })
    .format(values.map(String));
}

/**
 * Draws the row of subjects and shows the one that is chosen.
 *
 * Eleven groups in one column is taller than the desk, so the window shows one
 * subject at a time. The row is the same raised cell every choice in this window
 * uses, which is what Preferences does with its modules, and the groups
 * themselves are shown by the stylesheet from the name on the row below it.
 */
function drawTheSubjects() {
  fillWithChoices("editor-subjects",
    Object.entries(SUBJECTS).map(([subject, word]) => ({
      label: t(word),
      chosen: subject === showing,
      choose: () => showSubject(subject),
    })));

  /* Marked on each group rather than read off the row by the stylesheet, so
     that one rule hides them and nothing has to name the subjects a second
     time. */
  for (const group of document.querySelectorAll(".editor-groups > [subject]")) {
    group.toggleAttribute("away", group.getAttribute("subject") !== showing);
  }
}

/**
 * Shows one subject and leaves the machine alone.
 * @param {string} subject - One of SUBJECTS.
 *
 * Nothing is asked of the service for this: which groups are drawn is the
 * window's own business and the machine has not changed.
 */
function showSubject(subject) {
  showing = subject;
  drawTheSubjects();
}

/**
 * Draws the three NeXTdimension slots and the memory of each board there is.
 * @param {object} offers - The service's answer, which says which slots this
 *   machine has and how much memory a board takes.
 *
 * A slot is a cell that puts a board in and takes it out again, and a board
 * that is in gets a group of its own for its memory. One group per board rather
 * than one for all of them, because Previous gives each its own and a cube with
 * two boards of different sizes is a machine it will run.
 */
function drawTheDimensionBoards(offers) {
  fillWithChoices("editor-dimensions", offers.dimension_slots.map((slot, board) => ({
    label: t("editor.slot", { slot }),
    chosen: drafting.dimensions[board] > 0,
    /* Put in with the memory Previous's own file gives a board, and taken out
       by setting that back to nothing. */
    choose: () => change({
      dimensions: dimensionsWith(
        board, drafting.dimensions[board] ? 0 : DIMENSION_DEFAULT_MEMORY),
    }),
  })));
  document.getElementById("editor-dimension-group").hidden =
    !offers.dimension_slots.length;

  /* The console follows the first board there is, so the sentence names that
     board's slot, and says how many boards there are because each gets a
     group of its own below. */
  const seated = offers.dimension_slots
    .filter((slot, board) => drafting.dimensions[board] > 0);
  explain("editor-dimensions-note", seated.length
    ? t("editor.dimension.note.some",
        { count: seated.length, slot: seated[0] }, seated.length)
    : t("editor.dimension.note.none"));

  /* The board's index is taken before the empty slots are dropped, because
     after that the second board that is in would be counted as the second
     slot, and a cube with boards in slots 2 and 6 would draw and change the
     memory of slot 4. */
  const memories = document.getElementById("editor-dimension-memory");
  memories.replaceChildren(...offers.dimension_slots
    .map((slot, board) => [slot, board])
    .filter(([, board]) => drafting.dimensions[board] > 0)
    .map(([slot, board]) => drawOneBoardsMemory(slot, board, offers)));
}

/**
 * One board's memory, as a group of its own.
 * @param {number} slot - Which slot it answers from, for the heading.
 * @param {number} board - Which of the three it is, from 0.
 * @param {object} offers - The service's answer.
 * @returns {HTMLElement} The group, ready to go in.
 */
function drawOneBoardsMemory(slot, board, offers) {
  const group = document.createElement("fieldset");
  group.className = "group";

  const heading = document.createElement("legend");
  heading.textContent = t("editor.dimension-memory", { slot });
  group.append(heading);

  /* A scale like the machine's own memory, so it is a knob in a trough. Built
     rather than written, so it is wired here rather than through
     fillWithScale, which reaches for a slider the markup already holds. */
  const slider = document.createElement("nx-slider");
  group.append(slider);
  slider.options = offers.dimension_memory.map((mb) => ({
    value: mb, label: t("editor.megabytes", { mb }), tick: String(mb),
  }));
  slider.says = t("editor.unit.mb");
  slider.value = drafting.dimensions[board];
  slider.addEventListener("nx-slide",
    (event) => change({ dimensions: dimensionsWith(board, event.detail.value) }));

  /* The same sentence under the cells the groups in the markup carry, put here
     because this group is built rather than written. */
  const note = document.createElement("p");
  note.className = "note";
  note.textContent = noteFor("dimension-memory", drafting.dimensions[board]);
  group.append(note);

  return group;
}

/**
 * The three boards with one of them changed.
 * @param {number} board - Which of them, from 0.
 * @param {number} memory - How much memory it has now, and zero for taking it
 *   out altogether.
 * @returns {Array<number>} All three, for the service to settle.
 */
function dimensionsWith(board, memory) {
  const boards = [...drafting.dimensions];
  boards[board] = memory;
  return boards;
}

/**
 * Puts a scale in place, as a knob in a trough.
 * @param {string} id - The slider's own id.
 * @param {string} unit - What the figures are counted in, said once beside
 *   the scale rather than on every tick.
 * @param {Array<object>} steps - `{value, label}` in the order they sit on the
 *   scale, smallest first.
 * @param {*} value - Which of them the machine is on. One that is not a step
 *   leaves the knob at the start, which is what a total made by hand out of the
 *   banks does.
 * @param {Function} choose - Given the value landed on.
 *
 * For a group whose values have an order, where a row of cells would say they
 * have none. The groups that are not a scale keep their cells: a machine type,
 * a board, a DSP, a socket, a drive and a port are all one of several rather
 * than more or less of one thing.
 *
 * The listener is put on once and reads the action off the element, because the
 * action closes over what the machine is now and this runs again on every
 * change.
 */
function fillWithScale(id, unit, steps, value, choose) {
  const slider = document.getElementById(id);
  slider.says = unit;
  slider.onSlide = choose;
  if (!slider.listening) {
    slider.listening = true;
    slider.addEventListener("nx-slide",
      (event) => slider.onSlide(event.detail.value));
  }
  slider.options = steps;
  slider.value = value;
}

/**
 * Puts one group of things a machine either has or has not in place.
 * @param {string} id - The row they go in.
 * @param {object} offers - The service's answer, which says which of them this
 *   machine can have at all.
 * @param {Array<Array>} fittings - `[name, label]` for each.
 * @returns {string[]} The names of the ones this machine was offered, so the
 *   caller can say what each is doing in the state it is in.
 *
 * One press puts it in and the next takes it out, which is the boards group's
 * cell. A machine that cannot have one is not offered it rather than being
 * offered it and refused.
 */
function fillWithFittings(id, offers, fittings) {
  const offered = fittings.filter(([which]) => offers[which]);
  fillWithChoices(id, offered.map(([which, label]) => ({
    label,
    chosen: drafting[which],
    choose: () => change({ [which]: !drafting[which] }),
  })));
  return offered.map(([which]) => which);
}

/**
 * Puts the four memory banks in place, as the sockets they are.
 * @param {string} id - The row they go in.
 * @param {Array<Array<number>>} offered - What each bank accepts, from the
 *   service, smallest first and with an empty bank as the first of them.
 *
 * A bank is a socket on the board rather than one choice among several, so it
 * is drawn as one: a sunken field with a raised module in it where something is
 * seated. Those two edges are what this whole interface is built from, so this
 * needs no picture of a memory module, and there is none to use.
 *
 * A bank the machine cannot reach accepts nothing but an empty bank, and it is
 * drawn flat, because a socket that is not there is not a socket to fill.
 */
function fillWithBanks(id, offered) {
  document.getElementById(id).replaceChildren(...offered.map((sizes, bank) => {
    const size = drafting.banks[bank];

    const row = document.createElement("div");
    row.className = "bank-row";

    const name = document.createElement("span");
    name.className = "bank-name";
    name.textContent = t("editor.bank", { bank });
    row.append(name);

    const socket = document.createElement("div");
    socket.className = "bank";
    socket.toggleAttribute("absent", isAbsent(sizes));
    /* A bank offered one size and no empty one cannot move, which is the first
       bank of a colour station: it takes an 8 MB module and nothing else. */
    if (sizes.length > 1) {
      socket.addEventListener("click", () => change({
        banks: bankMovedOn(bank, sizes),
        memory: undefined,
      }));
    }

    const module_ = document.createElement("div");
    module_.className = "bank-module";
    module_.toggleAttribute("empty", !size);
    module_.textContent = size
      ? t("editor.megabytes", { mb: size })
      : t("editor.bank-empty");
    socket.append(module_);

    row.append(socket);
    return row;
  }));
}

/**
 * Whether a bank is one this machine does not have.
 * @param {Array<number>} sizes - What it accepts, from the service.
 * @returns {boolean}
 *
 * The service answers such a bank with an empty one and nothing else, which is
 * a choice of one rather than an absence, so there are four banks to draw
 * either way.
 */
function isAbsent(sizes) {
  return sizes.length === 1 && sizes[0] === 0;
}

/**
 * The four memory banks with one of them moved on to the next size it takes.
 * @param {number} bank - Which one was pressed, from 0.
 * @param {Array<number>} sizes - What that bank accepts, smallest first, with
 *   an empty bank as the first of them.
 * @returns {Array<number>} All four, in megabytes, for the service to settle.
 *
 * A bank holds one module rather than a choice between several, so its cell
 * fits the next size up and comes back to an empty bank after the largest. It
 * is the same gesture as taking a board out and putting it back, which is the
 * one this window already has for a cell that is not one of a row of choices.
 *
 * A bank holding a size the machine no longer takes starts again at the
 * smallest, because indexOf answers -1 for it.
 */
function bankMovedOn(bank, sizes) {
  const banks = [...drafting.banks];
  banks[bank] = sizes[(sizes.indexOf(banks[bank]) + 1) % sizes.length];
  return banks;
}

/**
 * Puts one group's cells in place.
 * @param {string} id - The row they go in.
 * @param {Array<object>} cells - `{label, chosen, choose}` for each.
 *
 * The same raised cell the Preferences window offers a choice with, because
 * this interface gives anything that can be chosen one shape.
 */
function fillWithChoices(id, cells) {
  document.getElementById(id).replaceChildren(...cells.map((cell) => {
    const choice = document.createElement("div");
    choice.className = "choice";
    choice.textContent = cell.label;
    choice.toggleAttribute("chosen", cell.chosen);
    choice.addEventListener("click", cell.choose);
    return choice;
  }));
}

/**
 * Changes one control and asks what that machine is now.
 * @param {object} what - The one that moved.
 */
function change(what) {
  drafting = { ...drafting, ...what };
  drawTheDraft();
}

/**
 * Changes what the machine itself is, and lets what follows from it follow
 * again.
 * @param {object} what - The machine type or the board that moved.
 *
 * Previous writes every one of FOLLOWS_THE_MACHINE afresh whenever one of those
 * two changes in its own dialogue, and the service does the same. Sending the
 * values that were showing would carry a setting from the machine just left
 * behind, so a 40 MHz Nitro would stay at 40 through losing its turbo board.
 */
function changeTheMachine(what) {
  const afresh = Object.fromEntries(
    FOLLOWS_THE_MACHINE.map((control) => [control, undefined]));
  change({ ...afresh, ...what });
}

/** Says what the button will do, and puts that on the button. */
function drawWhatSavingWillDo() {
  const button = document.getElementById("editor-save");
  button.dataset.t = replacing ? "button.save" : "button.save-as";
  writeWords(button, t(button.dataset.t));
  show("editor-note", replacing
    ? t("editor.over-this-one", { name: replacing })
    : t("editor.into-a-new-one"));
}

/**
 * Saves what the editor is showing.
 *
 * A name is asked for once, when the configuration is a new one. Editing one of
 * your own writes it back under the name it already has, which is what there is
 * to do with it.
 */
async function saveTheDraft() {
  if (!drafted) return;

  let name = replacing;
  if (name === null) {
    name = await askPanelFor({
      title: t("ask.name.title"),
      text: [t("ask.rename.question")],
      icon: machineArt(drafted.machine.enclosure),
      confirm: t("button.save"),
    });
    if (name === null) return;
  }

  const answer = await tell(Saved.Keep, {
    name,
    configuration: drafted.configuration,
    replacing,
  });
  show("editor-note", answer === null ? t("note.no-service") : say(answer));
  if (!answer?.ok) return;

  /* It is a configuration of its own from now on, so saving again writes over
     it rather than asking for another name, and the window carries its name. */
  replacing = name;
  drawTheTitle();
  drawWhatSavingWillDo();
  drawMachines();
  refresh();
}

/** Wires the editor's button, its menu entry, and its tile. */
function wireEditor() {
  document.getElementById("editor-save")
    ?.addEventListener("click", saveTheDraft);
  document.querySelector('nx-menu-item[name="editor-save"]')
    ?.addEventListener("click", saveTheDraft);

  /* Two clicks, like every other tile. It carries no `opens`, because the window
     is shown only once something has decided which machine it holds, and that is
     what this and the Apps folder both go through. */
  document.querySelector('nx-tile[name="editor"]')
    ?.addEventListener("dblclick", (event) => editOnWhatIsRunning(event.target));
}

/**
 * Opens the editor on the configuration that is set now.
 * @param {HTMLElement} [asker] - What was used to open it.
 *
 * Which is what somebody means by starting the editor without having chosen a
 * machine: the one in front of them. Where the file holds a configuration of
 * their own, that one is edited in place, and where it holds one of the eleven or
 * none of them, what comes out of editing it is new.
 */
function editOnWhatIsRunning(asker) {
  const machine = lastStatus?.configuration;
  const own = catalogue.find((entry) =>
    entry.id === machine?.catalogue && entry.set === "user");
  editConfiguration(own ?? machine, asker);
}

/**
 * Fills the editor where it came back open from the last visit.
 *
 * A window that was open when the page was left comes back open, and nothing
 * opened it, so nothing has decided what it holds. This runs once the first
 * status and the first tree are in, because what it shows then is the machine
 * that is set and whether that is one of the saved ones.
 */
function fillTheEditorIfItCameBackOpen() {
  const window_ = document.querySelector(`nx-window[name="${EDITOR}"]`);
  if (window_ && !window_.hidden) editOnWhatIsRunning();
}

/**
 * Says that an application that is not built yet is not built yet.
 * @param {string} name - What it will be called.
 */
function notYet(name) {
  return askPanel({
    title: name,
    text: [t("ask.not-yet.missing", { name }), t("ask.not-yet.plan")],
    icon: Art.Editor,
    confirm: t("button.fine"),
    cancel: t("button.close"),
  });
}

/**
 * Opens the context menu for whatever was clicked.
 * @param {HTMLElement} thing - What was clicked.
 * @param {number} x - Where the pointer was.
 * @param {number} y
 * @returns {boolean} Whether there was anything to offer.
 *
 * A machine gets the whole menu. Anything else gets one entry, and only where
 * it lies on the shelf: a folder is opened by double clicking it, so a menu of
 * entries that all refuse would be worse than none.
 */
function openMachineMenu(thing, x, y) {
  const where = thing.getAttribute("value");
  const machine = catalogue.find((entry) => entry.path === where);
  /* A disk carries one of the same entries, because it is chosen the same way.
     The other four are about a configuration and a disk is not one. */
  const found = find(root, where);
  const disk = found?.kind === "disk" ? found : null;
  const copy = found?.kind === "backup" ? found : null;
  const disc = found?.kind === "disc" ? found : null;
  const onShelf = Boolean(thing.closest(".keep"));
  if (!machine && !disk && !copy && !disc && !onShelf) return false;

  const menu = document.querySelector('nx-menu[name="machine-menu"]');
  /* Which machine this is about. The menu appears over whatever was clicked
     and then goes away, so without a name it is an orphan. */
  menu.querySelector(".title").textContent = thing.getAttribute("label");
  const info = menu.querySelector('nx-menu-item[name="info"]');
  const activate = menu.querySelector('nx-menu-item[name="activate"]');
  const edit = menu.querySelector('nx-menu-item[name="edit"]');
  const rename = menu.querySelector('nx-menu-item[name="rename"]');
  const remove = menu.querySelector('nx-menu-item[name="remove"]');
  const backup = menu.querySelector('nx-menu-item[name="backup"]');
  const restore = menu.querySelector('nx-menu-item[name="restore"]');
  const media = menu.querySelector('nx-menu-item[name="disc"]');
  const shelf = menu.querySelector('nx-menu-item[name="shelf"]');

  /* Three of the entries are about a machine, so a folder on the shelf shows
     only the one that applies to it. Activating is the exception: a disk is
     started exactly as a machine is. */
  for (const entry of [info, edit]) entry.hidden = !machine;
  activate.hidden = !machine && !disk;
  /* And two are about a configuration somebody saved. The eleven cannot be
     renamed or removed, so for those the entries are not in the menu at all
     rather than in it and refusing. */
  for (const entry of [rename, remove]) entry.hidden = machine?.set !== "user";
  /* A disk can be copied and a copy can be put back, and neither entry means
     anything for the other three kinds of thing. */
  backup.hidden = !disk;
  restore.hidden = !copy;
  backup.onclick = () => {
    menu.close();
    backUpTheDisk(disk);
  };
  restore.onclick = () => {
    menu.close();
    putTheCopyBack(copy);
  };
  /* One entry whichever way round it is, because it is one act. The key goes
     with the wording, so a change of language finds what it is showing rather
     than what the markup started with. */
  media.hidden = !disc;
  if (disc) {
    media.dataset.t = disc.slot === null ? "menu.insert" : "menu.eject";
    writeWords(media, t(media.dataset.t));
    media.onclick = () => {
      menu.close();
      useTheDisc(disc);
    };
  }

  info.onclick = () => {
    menu.close();
    showMachineInfo(where);
  };

  /* The one entry whose wording changes, because it is the same act either
     way round and two entries for it would both be wrong half the time. The
     key is written with it, so a change of language finds the wording this
     entry is actually showing rather than the one the markup started with. */
  shelf.dataset.t = onShelf ? "menu.unkeep" : "menu.keep";
  writeWords(shelf, t(shelf.dataset.t));
  shelf.onclick = () => {
    menu.close();
    keepOnShelf(where, !onShelf);
  };

  if (machine || disk) {
    /* The one that is already running cannot be activated: it would shut
       NeXTSTEP down, write the same values back and start it again, for
       nothing. The entry stays, so the menu keeps its shape. */
    activate.toggleAttribute("disabled", thing.hasAttribute("disabled"));

    activate.onclick = () => {
      if (activate.hasAttribute("disabled")) return;
      menu.close();
      if (machine) return changeTo(machine.id);
      bootFromDisk(disk);
    };
  }

  if (machine) {
    rename.onclick = () => {
      menu.close();
      renameConfiguration(machine);
    };

    remove.onclick = () => {
      menu.close();
      removeConfiguration(machine);
    };
  }
  edit.onclick = () => {
    menu.close();
    editConfiguration(machine, thing);
  };

  menu.openAt(x, y);
  return true;
}

/**
 * Asks before the whole machine goes, and says in which order.
 * @param {string} what - The wording on the acting button.
 * @param {string} question - Which question to put, by its name in the
 *   catalogue, because the two differ in what the board does afterwards.
 * @returns {Promise<boolean>}
 */
function warnAboutTheBoard(what, question) {
  return askPanel({
    title: "Raspberry Pi",
    text: [t(question), t("ask.board.order"), t("ask.board.loss")],
    icon: Art.Computer,
    confirm: what,
  });
}

/**
 * Runs one of the board's two actions and reports what came of it.
 * @param {string} route - One of Board.
 * @param {string} working - What to say while it happens.
 */
async function operateBoard(route, working) {
  allowActions(false);
  show("pi-note", working);

  const answer = await tell(route);

  /* A board that is going down answers nothing, and that is the ordinary case
     rather than a failure. Saying so beats a page that claims no contact. */
  show("pi-note", answer === null ? t("note.board-gone") : say(answer));

  /* Nothing is switched back on here. The next status decides: whilst the
     board is away it does not answer, and everything stays off until it does. */
  refresh();
}

/** Wires the board's own two buttons. */
function wireBoard() {
  document.getElementById("pi-reboot").addEventListener("click", async () => {
    if (await warnAboutTheBoard(t("button.restart"), "ask.board.reboot")) {
      operateBoard(Board.Reboot, t("busy.board-restart"));
    }
  });

  document.getElementById("pi-poweroff").addEventListener("click", async () => {
    if (await warnAboutTheBoard(t("button.power-off"), "ask.board.poweroff")) {
      operateBoard(Board.PowerOff, t("busy.board-poweroff"));
    }
  });
}

/** Fills a window the moment it opens, rather than at the next poll. */
function wireOpening() {
  document.addEventListener("nx-open", (event) => {
    if (event.target.getAttribute("name") === "pi") refresh();
  });
}

/** Wires the two gestures that choose a machine. The third, the context
 *  menu, wires itself where it is opened. */
function wireMachines() {
  /* The note under the viewer has been read by the time somebody reaches into
     the window again. Wired here rather than in drawMachines, which runs again
     after every change and would leave a second listener behind each time. */
  document.getElementById("file-viewer")
    .addEventListener("click", () => show("machine-note", ""));

  /* A right click anywhere on a machine, rather than on the shelf, so the menu
     is always about something. */
  document.getElementById("file-viewer").addEventListener("contextmenu", (event) => {
    const thing = event.target.closest("nx-thing");
    if (!thing) return;
    event.preventDefault();
    /* Each menu says whether what was clicked is its own, so the one that
       belongs to it opens and nothing opens over something neither covers. */
    openMachineMenu(thing, event.clientX, event.clientY)
      || openPictureMenu(thing, event.clientX, event.clientY);
  });

  /* Carried onto a window, or double clicked in the viewer. The kit raises the
     same event for both, so this is one answer to two gestures, and what happens
     follows from what was chosen. */
  /* The thing that was chosen is where an application's icon starts its
     journey to the floor of the screen, so it travels with the choice. */
  document.addEventListener("nx-choose", (event) => {
    /* Carried into the Config Editor, which means edit that machine rather than
       start it. Anything else dropped there is ignored: the editor has nothing to
       do with a folder or a picture. */
    if (event.target?.getAttribute?.("name") === EDITOR) {
      const machine = catalogue.find((entry) => entry.path === event.detail.value);
      if (machine) editConfiguration(machine);
      return;
    }
    open(event.detail.value, event.target);
  });

  /* A step of the path was clicked, so go back to it. */
  document.addEventListener("nx-path", (event) => goTo(event.detail.index));

  /* One click on the shelf, which is the one place a single click acts. */
  document.addEventListener("nx-visit",
    (event) => visitFromTheShelf(event.detail.value, event.target));

  /* Carried onto the viewer's own shelf, which means keep this one to hand
     rather than start it. */
  document.addEventListener("nx-keep",
    (event) => keepOnShelf(event.detail.value, true));
}

/**
 * Says how long something has been running, the short way.
 * @param {number|null} seconds
 * @returns {string}
 */
function duration(seconds) {
  if (seconds === null || seconds === undefined) return NOTHING;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return t("duration.days", { days, hours }, days);
  if (hours > 0) return t("duration.hours", { hours, minutes });
  return t("duration.minutes", { minutes });
}

/**
 * What the board says about its power, in words.
 * @param {string[]} names - The service's names for it, such as
 *   `under-voltage`. It sends names rather than sentences for the same reason
 *   it does everywhere else: a sentence written there could only ever be in
 *   one language.
 * @returns {string} Them in one list, in the language the interface speaks.
 */
function named(names) {
  return names.map((name) => t(`throttling.${name}`)).join(", ");
}

/**
 * Puts a lamp and a sentence into a field.
 * @param {string} id
 * @param {boolean} well - Whether this reading is the good case.
 * @param {string} words
 */
function showState(id, well, words) {
  const lamp = document.createElement("span");
  lamp.className = "lamp";
  if (!well) lamp.style.background = "var(--dark)";
  document.getElementById(id)
    .replaceChildren(lamp, document.createTextNode(" " + words));
}

/**
 * Draws what the board underneath is doing.
 * @param {object|null} pi - What /api/pi answered, or null.
 */
function drawPi(pi) {
  if (pi === null) {
    show("pi-model", t("state.unreachable"));
    allowActions(false);
    return;
  }

  show("pi-model", pi.model ?? NOTHING);
  show("pi-uptime", duration(pi.uptime_seconds));

  /* Above 80 degrees a Pi 5 begins to slow itself down, so that is where the
     reading stops being a number and becomes a warning. */
  const temperature = pi.temperature_c;
  showState("pi-temp", temperature !== null && temperature < 80,
    temperature === null ? NOTHING : `${temperature.toFixed(1)} °C`);

  /* Two different things. Something happening now is a problem to act on, and
     something that happened once may have been the moment a drive was plugged
     in, which is worth knowing and not worth alarm. */
  const throttling = pi.throttling;
  if (!throttling) {
    showState("pi-power", true, NOTHING);
  } else if (throttling.now.length) {
    showState("pi-power", false, t("pi.power.now", { what: named(throttling.now) }));
  } else if (throttling.since_boot.length) {
    showState("pi-power", false,
      t("pi.power.since-boot", { what: named(throttling.since_boot) }));
  } else {
    showState("pi-power", true, t("pi.power.fine"));
  }

  /* Around 150 per cent of one core is ordinary with a NeXTdimension, because
     two threads run, so the figure is stated without judging it. */
  show("pi-emulator", pi.emulator
    ? t("pi.emulator.running", {
        percent: Math.round(pi.emulator.cpu_percent),
        mb: pi.emulator.memory_mb,
        uptime: duration(pi.emulator.uptime_seconds),
      })
    : t("pi.emulator.stopped"));

  /* The one that looks like nothing: the card is there, the configuration
     still names it, and the stream was closed when the speaker was moved. */
  showState("pi-sound", Boolean(pi.sound?.playing), pi.sound
    ? t(pi.sound.playing ? "pi.sound.playing" : "pi.sound.silent", { card: pi.sound.card })
    : t("pi.sound.none"));

  show("pi-memory", pi.memory
    ? t("pi.memory.free",
        { available: pi.memory.available_mb, total: pi.memory.total_mb })
    : NOTHING);
  show("pi-disk", pi.disk
    ? t("pi.disk.free",
        { gb: Math.round(pi.disk.free_mb / 1024), percent: pi.disk.used_percent })
    : NOTHING);

  /* Which tool is answering. The one reading here that is about this program
     rather than about the board, and it is here because this is the window
     somebody opens to find out what a machine is running. */
  show("pi-version", pi.version ?? NOTHING);
}

/** Fetches the status and draws it, and the board's readings where its window
 *  is open. A window nobody is looking at costs nothing. */
async function refresh() {
  drawStatus(await ask("/api/status"));

  const window_ = document.querySelector('nx-window[name="pi"]');
  if (window_ && !window_.hidden) drawPi(await ask("/api/pi"));
}

/**
 * Draws the languages this tool speaks, with the one in force marked.
 *
 * Each is named in its own language, because a language named in a language
 * one cannot read is no help to whoever is looking for theirs. The order is
 * the catalogue's own, so it does not move about as the interface changes.
 */
function drawLanguages() {
  const list = document.getElementById("languages");
  list.replaceChildren(...Object.entries(LANGUAGE_NAMES).map(([code, name]) => {
    const option = document.createElement("div");
    option.className = "option";
    option.textContent = name;
    option.toggleAttribute("chosen", code === currentLanguage());
    option.addEventListener("click", () => speak(code));
    return option;
  }));
}

/* --- how large the interface is drawn -------------------------------------

   NeXTSTEP's own measurements are what everything here is built from, and on
   a large panel at a low resolution they are small. So the same desk is drawn
   larger rather than measured again.

   In quarters, which is a finer choice than the bitmaps are exact at. Measured
   against the sizes they are actually drawn at: a quarter step puts five of
   them on half pixels, a half step puts two there, and only 1 and 2 leave
   every one whole. They carry image-rendering: pixelated, so a row of their
   own pixels is doubled rather than smeared. Somebody at a large panel needs a
   size between too small and too large more than they need a picture that is
   exact at two settings out of five. */

/** What the interface can be drawn at. */
const SIZES = [1, 1.25, 1.5, 1.75, 2];

/** What a browser that has never been told draws it at. Not the original's
 *  own, because that is measured for a screen 1120 across and this is read on
 *  panels several times that, where a first look at 100% is an interface
 *  somebody has to go and enlarge before they can use it. */
const SIZE_AT_FIRST = 1.25;

/** Where the choice is kept. The browser's, like the language: how large one
 *  person needs this drawn is not a property of the machine. */
const SIZE_KEY = "previously:size";

/** @returns {number} The size last chosen, or the one a first look takes. */
function chosenSize() {
  const saved = Number(localStorage.getItem(SIZE_KEY));
  return SIZES.includes(saved) ? saved : SIZE_AT_FIRST;
}

/**
 * Draws the interface at that size and keeps the choice.
 * @param {number} scale - One of what SIZES offers.
 */
function drawAtSize(scale) {
  setDeskScale(scale);
  try {
    localStorage.setItem(SIZE_KEY, String(scale));
  } catch {
    /* A browser that refuses to store it still draws it this way for now. */
  }
  drawSizes();
}

/** Draws the row of sizes, with the one in force marked.
 *
 * Each button shows a letter at the size it sets, which is what Preferences
 * does wherever a setting can be shown rather than described: its Keyboard
 * module draws the repeat rate as letters at four spacings.
 *
 * Under the letter is the figure the step is, because a letter alone says
 * which is larger and not by how much. Five steps also outgrow a set of names:
 * Normal, Large and Largest is a scale that does not extend, and two more
 * words for the gaps would be a vocabulary rather than a scale. The figure
 * reads the same in every language, and 100% says which one is the original.
 */
function drawSizes() {
  const row = document.getElementById("size-choices");
  if (!row) return;
  row.replaceChildren(...SIZES.map((scale) => {
    const choice = document.createElement("div");
    choice.className = "choice";
    choice.toggleAttribute("chosen", scale === chosenSize());

    const sample = document.createElement("div");
    sample.className = "sample";
    sample.textContent = "A";
    /* The size this button sets, shown at that size against the interface's
       own, so the five of them read as one scale. */
    sample.style.fontSize = `calc(var(--text-size) * ${scale})`;

    const under = document.createElement("div");
    under.className = "choice-name";
    under.textContent = Math.round(scale * 100) + " %";

    choice.append(sample, under);
    choice.addEventListener("click", () => drawAtSize(scale));
    return choice;
  }));
}

/** What each module of Preferences is called and which panel it shows. */
const MODULES = {
  localization: { name: "preferences.localization", panel: "languages" },
  monitor: { name: "preferences.monitor", panel: "sizes" },
};

/**
 * Shows one module of Preferences.
 * @param {string} which - Its name, as the picture in the row carries it.
 *
 * A row of pictures with the chosen one's panel underneath, which is how
 * NeXTSTEP built this window. Only one panel is up at a time, and the name
 * between the row and the panel is that module's own.
 */
function showModule(which) {
  const module = MODULES[which];
  if (!module) return;

  for (const cell of document.querySelectorAll("nx-window[name='preferences'] .module")) {
    cell.toggleAttribute("chosen", cell.getAttribute("value") === which);
  }
  for (const [name, one] of Object.entries(MODULES)) {
    document.getElementById(one.panel).hidden = name !== which;
  }
  writeWords(document.getElementById("module-name"), t(module.name));
}

/** Wires the row of modules, and draws the one that starts up chosen. */
function wirePreferences() {
  const row = document.querySelector("nx-window[name='preferences'] .modules");
  if (!row) return;

  row.addEventListener("click", (event) => {
    const cell = event.target.closest(".module");
    if (cell) showModule(cell.getAttribute("value"));
  });
  showModule("localization");
  drawSizes();
}

/**
 * Every application this tool holds, as the tree gives them.
 * @returns {object[]} Each with its path, its picture and the window it opens.
 */
function applications() {
  const apps = find(root, "/Apps");
  return (apps?.entries ?? []).filter((entry) => entry.kind === "application");
}

/**
 * Whether an application is running, which here is its window being open.
 * @param {object} application - An entry of the Apps folder.
 * @returns {boolean}
 *
 * In NeXTSTEP an application outlives its windows. Here it does not: the
 * window is the application, so closing it is quitting, and saying otherwise
 * would be a light that means nothing.
 */
function isRunning(application) {
  const window_ = document.querySelector(`nx-window[name="${application.opens}"]`);
  return Boolean(window_) && !window_.hidden;
}

/** Which applications are running, oldest first, so their icons keep the
 *  places they took when they started. */
let started = [];

/**
 * Draws which applications are running and where their icons go.
 *
 * A tile in the dock carries the three marks whilst its application is not
 * running and loses them when it is, which is what NeXTSTEP's dock did. An
 * application that is running and is not in the dock stands on the floor of
 * the screen instead, from the left corner rightwards.
 */
function drawWhatIsRunning(arriving) {
  const docked = [...document.querySelectorAll("nx-dock nx-tile[app]")];
  for (const tile of docked) {
    const application = applications().find((entry) => entry.path === tile.getAttribute("app"));
    tile.toggleAttribute("idle", Boolean(application) && !isRunning(application));
  }

  const inTheDock = new Set(docked.map((tile) => tile.getAttribute("app")));
  const standing = applications()
    .filter((application) => !inTheDock.has(application.path) && isRunning(application))
    /* The order they were started in, which is the order they arrived in the
       list this keeps. */
    .sort((one, other) => started.indexOf(one.path) - started.indexOf(other.path));
  document.getElementById("floor")?.show(standing, arriving);
}

/**
 * Reads which applications are running now and draws them.
 * @param {CustomEvent} [event] - The window opening or closing that prompted
 *   this, which is what says where a newly started application is coming
 *   from.
 *
 * A window that opens or closes is an application starting or stopping, and
 * an application that has just started takes the next place on the floor. Its
 * icon travels there from whatever was used to start it, which the window
 * carries along from whoever opened it.
 */
function noticeTheApplications(event) {
  for (const application of applications()) {
    const running = isRunning(application);
    const known = started.includes(application.path);
    if (running && !known) started.push(application.path);
    if (!running && known) started = started.filter((path) => path !== application.path);
  }

  const opened = event?.type === "nx-open" ? event.target.getAttribute?.("name") : null;
  const arriving = applications().find((entry) => entry.opens === opened);
  drawWhatIsRunning(arriving && event.detail?.from
    ? { opens: arriving.opens, from: event.detail.from }
    : null);
}

/** Listens for a window opening or closing, which is what starting and
 *  stopping an application is here. Wired once. */
function watchTheApplications() {
  document.addEventListener("nx-open", noticeTheApplications);
  document.addEventListener("nx-close", noticeTheApplications);
  noticeTheApplications();
}

/** The shell session behind the terminal window, or null when none is open.
 *  One at a time, which is also all the service hands out. */
let shell = null;

/** What has been typed at the login prompt, or null whilst a session runs and
 *  every key belongs to the far side. */
let typedAtThePrompt = null;

/**
 * Puts the login prompt up.
 * @param {string} [complaint] - What came of the last attempt.
 *
 * Ours, and only this one line of it. What answers afterwards is this
 * machine's own SSH server: it asks for the password, it decides, and what
 * comes back is an ordinary login shell. This service never sees a password
 * and has no way to let anybody past.
 *
 * The name is asked here rather than by sshd because the client has to be
 * told who is connecting before it connects at all.
 */
function askAtTheTerminal(complaint) {
  const view = document.getElementById("session");
  if (!view.write) return;

  typedAtThePrompt = "";
  if (complaint) view.write("\r\n" + complaint + "\r\n");
  view.write("\r\n" + t("terminal.login"));
  view.focus();
}

/**
 * Answers a key at that prompt.
 * @param {string} data - What the terminal says was typed.
 *
 * Echoed, because a login name is echoed everywhere else a person types one.
 * The password is not asked here at all: by then the far side is sshd, which
 * echoes nothing itself.
 */
function typeAtThePrompt(data) {
  const view = document.getElementById("session");
  for (const character of data) {
    if (character === "\r" || character === "\n") {
      const said = typedAtThePrompt.trim();
      if (!said) {
        view.write("\r\n" + t("terminal.login"));
        continue;
      }
      typedAtThePrompt = null;
      view.write("\r\n");
      return openShell(said);
    }
    if (character === "\x7f" || character === "\b") {
      if (!typedAtThePrompt) continue;
      typedAtThePrompt = typedAtThePrompt.slice(0, -1);
      view.write("\b \b");
      continue;
    }
    if (character >= " ") {
      typedAtThePrompt += character;
      view.write(character);
    }
  }
}

/**
 * Opens a session for whoever was named at the prompt.
 * @param {string} login - The name typed.
 *
 * The name and the size go as the first thing said, so the login starts at
 * the size it will be read at rather than at one it is corrected from a
 * moment later.
 */
function openShell(login) {
  const view = document.getElementById("session");
  if (shell || !view.write) return;

  const where = location.origin.replace(/^http/, "ws") + TERMINAL;
  const opening = new WebSocket(where, ["previously"]);
  opening.binaryType = "arraybuffer";
  shell = opening;
  let accepted = false;

  opening.onopen = () => {
    accepted = true;
    view.fit();
    const size = view.size;
    opening.send(JSON.stringify({ login, size: [size.rows, size.columns] }));
    view.focus();
  };
  opening.onmessage = (event) => view.write(new Uint8Array(event.data));
  opening.onclose = () => {
    const wasRunning = shell === opening;
    shell = null;
    if (!wasRunning) return;
    /* A browser is told nothing about why a handshake failed, and the one
       thing this service refuses at that point is a second session. */
    askAtTheTerminal(accepted ? t("terminal.ended") : t("terminal.refused"));
  };
}

/** Ends the session, which the service answers by ending the shell. */
function closeShell() {
  const going = shell;
  shell = null;
  typedAtThePrompt = null;
  going?.close();
}

/**
 * Tells the shell how large the window has become.
 * @param {object} size - `{rows, columns}`.
 *
 * A text frame, which the service reads as being about the session. Anything
 * binary is what the shell itself sees.
 */
function tellTheShellItsSize(size) {
  if (shell?.readyState !== WebSocket.OPEN) return;
  shell.send(JSON.stringify({ resize: [size.rows, size.columns] }));
}

/** Wires the terminal window to the session behind it. */
function wireTerminal() {
  const window_ = document.querySelector('nx-window[name="terminal"]');
  const view = document.getElementById("session");
  if (!window_ || !view) return;

  /* Opening the window is not opening a session. The login is. */
  window_.addEventListener("nx-open", () => {
    document.getElementById("session").clear();
    askAtTheTerminal();
  });
  window_.addEventListener("nx-close", closeShell);

  view.addEventListener("nx-typed", (event) => {
    if (typedAtThePrompt !== null) return typeAtThePrompt(event.detail.data);
    if (shell?.readyState === WebSocket.OPEN) {
      shell.send(new TextEncoder().encode(event.detail.data));
    }
  });
  view.addEventListener("nx-sized", (event) => tellTheShellItsSize(event.detail));

  /* A browser that goes away without closing the window would otherwise leave
     the service holding a session nobody is looking at until the socket times
     out. */
  addEventListener("pagehide", closeShell);

  /* A window that was open when the page was last left comes back open, and
     nothing opened it, so nothing said so. What it comes back to is the
     prompt: a session does not survive a reload and must not look as though
     it did. */
  if (!window_.hidden) askAtTheTerminal();
}

/* --- Grab, which takes a picture of the emulated screen --------------------------------

   The picture is the machine's own framebuffer, taken at the moment it is
   asked for. Nothing here polls: a screen that redrew itself every few seconds
   would be a window that costs the emulator something for as long as it is
   open, and what a person wants is to look now. */

/**
 * Takes a picture of the emulated screen and puts it in the window.
 *
 * Fetched as a blob rather than pointed at, so that a refusal can be answered
 * by asking for the password rather than by drawing a broken picture. The last
 * one is released when the next arrives, so a window left open all day holds
 * one picture rather than all of them.
 */
async function takeAPicture() {
  const view = document.getElementById("shot");
  const button = document.getElementById("shot-take");
  if (!view) return;

  button.disabled = true;
  try {
    const answer = await fetch("/api/screen", { cache: "no-store" });
    if (answer.status === 403) return askForPassword(t("ask.password.needed"));
    if (!answer.ok) return showTheScreen(null);
    const filed = answer.headers.get(KEPT_HEADER);
    showTheScreen(await answer.blob(), filed);
    /* It was filed as well as shown, so the folder it went into has one more
       thing in it than the viewer is drawing. */
    if (filed) drawMachines();
  } catch {
    showTheScreen(null);
  } finally {
    button.disabled = false;
  }
}

/**
 * Puts a picture in the window, or says why there is none.
 * @param {Blob} picture - What the service answered with, or null.
 * @param {string} [name] - What the service filed it as.
 */
function showTheScreen(picture, name) {
  drawPicture("shot", picture, name);
  document.getElementById("shot-note").textContent = picture
    ? ""
    : t(lastStatus?.running === false ? "grab.idle" : "grab.failed");
}

/**
 * Draws a picture into a view, and releases the one it replaces.
 * @param {string} id - Which view, which is its element's id.
 * @param {Blob} picture - The picture, or null to empty the view.
 * @param {string} [name] - What it is called, for saving it later.
 *
 * One place, because two windows show a picture: Grab shows what it has just
 * taken and Preview shows one that was kept. A blob has to be released or the
 * browser holds every picture ever shown, and the only way to do that is to
 * remember the last one per view.
 */
function drawPicture(id, picture, name) {
  const view = document.getElementById(id);
  if (!view) return;

  if (shownPictures[id]) URL.revokeObjectURL(shownPictures[id].url);
  shownPictures[id] = picture
    ? { url: URL.createObjectURL(picture), name }
    : null;
  view.style.backgroundImage = shownPictures[id]
    ? `url("${shownPictures[id].url}")` : "";
}

/** What each picture view is showing and what it is called, so it can be
 *  released when it is replaced and saved whilst it is up. */
const shownPictures = {};

/**
 * Hands the picture a window is showing to the browser to save.
 * @param {string} id - Which view is showing it.
 *
 * The picture is already here, so this is a link to what is in memory rather
 * than a second request: nothing is fetched and the service is not asked
 * again.
 */
function saveThePicture(id) {
  const showing = shownPictures[id];
  if (!showing) return;

  const link = document.createElement("a");
  link.href = showing.url;
  link.download = showing.name ?? "Screen.png";
  link.click();
}

/* --- the menu belongs to whatever is in front -----------------------------

   NeXTSTEP had one menu, in one place, whose title and entries were replaced
   when another application became active. Read off the running system: the
   Workspace's menu is titled Workspace and holds ten entries, and Preferences'
   is titled Preferences and holds five, of which Info, Ausblenden and
   Verlassen are the ones every application has.

   Here an application is a window, so the front window decides. A window that
   is not an application's, which is the Info window, the Raspberry Pi window
   and the File Viewer, leaves the workspace's own menu standing: under
   NeXTSTEP those are the Workspace's own windows too. */

/** Which windows are an application's, and therefore carry a menu of their
 *  own. Read from the tree rather than listed here, so an application added
 *  to the Apps folder is one this follows without being told twice. */
function applicationWindows() {
  return new Set(applications().map((entry) => entry.opens).filter(Boolean));
}

/**
 * Puts the menu of whatever is in front into the one menu there is.
 * @param {string} [front] - The name of the window that came forward. Left
 *   out, whichever window is in front now is asked.
 */
function drawTheMenu(front) {
  const menu = document.querySelector('nx-menu[name="menu"]');
  if (!menu?.showFor) return;

  const name = front ?? document.querySelector("nx-window:not([inactive]):not([hidden])")?.name;
  const application = applications().find((entry) => entry.opens === name);
  menu.showFor(application ? name : "",
               application ? appName(application) : WORKSPACE);
}

/** What the workspace's own menu is called. NeXTSTEP's own name for it, and
 *  not translated anywhere, the way the applications' names are not: this menu
 *  belongs to the desk rather than to any machine, and it is there whether one
 *  is installed or not. */
const WORKSPACE = "Workspace";

/** What this tool is called, which is a name and so the same in every
    language. */
const PRODUCT = "Previously";

/** Where whoever holds the copyright can be read about. */
const HOLDER_SITE = "https://layered.work";

/** Follows the front window, and the windows that open and close with it. */
function watchTheFrontWindow() {
  document.addEventListener("nx-front", (event) => drawTheMenu(event.detail?.name));
  /* A window closing leaves something else in front, and nothing says which
     until the next raise, so the menu is asked to work it out again. */
  document.addEventListener("nx-close", () => drawTheMenu());

  /* Quitting an application is closing its window, because here an
     application is a window. Every one of those entries does the same thing
     to a different window, so it is wired once against whatever is in front.
     */
  for (const entry of document.querySelectorAll('nx-menu-item[name="quit"]')) {
    entry.addEventListener("click", () => {
      const owner = entry.getAttribute("for");
      document.querySelector(`nx-window[name="${owner}"]`)?.close();
    });
  }
  document.querySelector('nx-menu-item[name="about-previously"]')
    ?.addEventListener("click", showWhatThisIs);
  document.querySelector('nx-menu-item[name="grab-take"]')
    ?.addEventListener("click", takeAPicture);
  for (const [entry, view] of [["grab-save", "shot"], ["preview-save", "preview-picture"]]) {
    document.querySelector(`nx-menu-item[name="${entry}"]`)
      ?.addEventListener("click", () => saveThePicture(view));
  }
  document.querySelector('nx-menu-item[name="preview-delete"]')
    ?.addEventListener("click", async () => {
      const showing = shownPictures["preview-picture"];
      if (!showing?.name) return;
      /* The window goes with the picture, because a window showing something
         that is no longer there is worse than no window. */
      if (await deleteThePicture(showing.name)) {
        document.querySelector('nx-window[name="preview"]')?.close();
      }
    });

  drawTheMenu();
}


/**
 * Says what this tool is, and waits until that has been read.
 * @returns {Promise<void>}
 *
 * NeXTSTEP's Info panel holds the name, the icon, the copyright and the
 * version, and nothing else at all. The version is the service's own answer
 * rather than a line written here, so what this panel says and what the
 * Raspberry Pi window says cannot drift apart. A machine that cannot be
 * reached leaves that line out rather than guessing at it.
 */
async function showWhatThisIs() {
  const version = (await ask("/api/pi"))?.version;
  await document.getElementById("ask").tell({
    icon: "Previously",
    text: [
      PRODUCT,
      t("about.version", { version: version ?? NOTHING }),
      copyrightLine(),
    ],
    confirm: t("about.ok"),
  });
}

/**
 * The copyright, with whoever holds it leading to their own site.
 * @returns {HTMLParagraphElement}
 *
 * Built here rather than handed over as a sentence, because one word in it is
 * a link and the catalogues hold words rather than markup. The name is its own
 * entry for the same reason: it is a name, so it is the same in every
 * language, and the sentence around it is not.
 */
function copyrightLine() {
  const paragraph = document.createElement("p");
  const holder = document.createElement("a");
  holder.href = HOLDER_SITE;
  /* Away from this tab, because the desk behind this panel is a machine
     somebody is running and leaving it would stop nothing but would lose
     where they were. */
  holder.target = "_blank";
  holder.rel = "noopener noreferrer";
  holder.textContent = t("about.holder");

  const [before, after] = t("about.copyright").split("{holder}");
  paragraph.append(before ?? "", holder, after ?? "");
  return paragraph;
}

/**
 * What a browser that has never been here is shown: the File Viewer, with the
 * panel saying what this is in front of it.
 *
 * Somebody arriving for the first time lands on a desk that says nothing about
 * itself, and the one place everything here can be reached from is the viewer.
 * Afterwards the desk is whatever they left it as, which is why this happens
 * once.
 */
function greetTheFirstVisit() {
  if (!deskIsNew()) return;
  document.querySelector('nx-window[name="files"]')?.open();
  showWhatThisIs();
}

/**
 * Shows one kept picture in Preview.
 * @param {object} entry - What the tree says about it.
 *
 * Fetched rather than pointed at, for the same reason Grab fetches its own: a
 * refusal is answered by asking for the password. The window is titled with the
 * picture's name, the way a document window is.
 */
async function showInPreview(entry) {
  const window_ = document.querySelector('nx-window[name="preview"]');
  const note = document.getElementById("preview-note");
  if (!window_) return;

  window_.rename(entry.name);
  window_.open();
  drawPicture("preview-picture", null);
  note.textContent = "";

  try {
    const answer = await fetch(
      "/api/picture?name=" + encodeURIComponent(entry.name),
      { cache: "no-store" });
    if (answer.status === 403) return askForPassword(t("ask.password.needed"));
    if (!answer.ok) return void (note.textContent = t("preview.empty"));
    drawPicture("preview-picture", await answer.blob(), entry.name);
  } catch {
    note.textContent = t("preview.empty");
  }
}

/**
 * Asks whether a picture should go, and takes it away if so.
 * @param {string} name - What it is called in the Pictures folder.
 * @returns {Promise<boolean>} Whether it went.
 *
 * Asked first, because a picture that has gone does not come back and there
 * is no wastebasket here to fish it out of.
 */
async function deleteThePicture(name) {
  const sure = await askPanel({
    title: t("ask.delete.title", { name }),
    text: [t("ask.delete.loss")],
    icon: Art.Picture,
    confirm: t("button.delete"),
  });
  if (!sure) return false;

  const answer = await tell("/api/picture/delete", { name });
  if (!answer?.ok) return false;

  /* The folder has one thing fewer in it than the viewer is drawing, and a
     window showing what has gone is showing something that is not there. */
  drawMachines();
  return true;
}

/**
 * Offers what can be done to a picture, where one was right clicked.
 * @param {HTMLElement} thing - The icon under the pointer.
 * @param {number} x @param {number} y - Where the pointer was.
 * @returns {boolean} Whether this menu was the right one for what was clicked.
 *
 * Titled for the kind of thing rather than for the file, because a file's
 * name is as long as somebody made it and a menu bar is one row. Which file
 * this is about is said by where the menu stands and by the question that
 * follows it.
 */
function openPictureMenu(thing, x, y) {
  const where = thing.getAttribute("value");
  const entry = find(root, where);
  if (entry?.kind !== "picture") return false;

  const menu = document.querySelector('nx-menu[name="picture-menu"]');
  menu.querySelector('nx-menu-item[name="delete"]').onclick = async () => {
    menu.close();
    await deleteThePicture(entry.name);
  };
  menu.openAt(x, y);
  return true;
}

/** Wires Preview, which holds nothing of its own once it is closed. */
function wirePreview() {
  document.querySelector('nx-window[name="preview"]')
    ?.addEventListener("nx-close", () => drawPicture("preview-picture", null));
}

/** Wires the window that shows the emulated screen. */
function wireGrab() {
  const window_ = document.querySelector('nx-window[name="grab"]');
  const button = document.getElementById("shot-take");
  if (!window_ || !button) return;

  button.addEventListener("click", takeAPicture);
  /* Opening it takes one straight away, because an empty window would ask
     somebody to press a button to find out what they opened it for. */
  window_.addEventListener("nx-open", takeAPicture);
  window_.addEventListener("nx-close", () => showTheScreen(null));
  if (!window_.hidden) takeAPicture();
}

/* --- the Installer --------------------------------------------------------

   What NeXT called the application that puts things on a machine and takes
   them off again. Here there are two kinds of thing: the emulator, which is a
   package and a handful of steps around it, and a system, which is a two
   gigabyte disk that arrives as an archive of a few tens of megabytes.

   The work is none of this window's. It asks the service, the service leaves a
   request, and a program running as root does it and says how far it has got.
   So what is drawn here comes from the Pi on every look, and a reload shows
   the same thing a moment later. */

/** Where the Installer asks and tells. One address for both, because what
 *  comes back from asking is what the window shows anyway. */
const SETUP = "/api/setup";

/** What the service may be asked to do, by the name it takes. */
const Install = {
  Emulator: "install",
  Newest: "update",
  Away: "remove",
  Fetch: "fetch",
  Forget: "forget",
};

/** How often the Installer looks. Faster than the desk's own poll, because a
 *  download says something new every second and this is a window somebody sits
 *  and watches. Asked only whilst the window is open or something is running,
 *  and only every fourth time whilst neither is true. */
const WATCHING_MS = 500;
const EVERY_FOURTH = 4;

/** The last thing /api/setup said, so the window can be drawn again in another
 *  language without asking for it. */
let setupState = null;

/** Which system is chosen in the list, by identifier, or null. */
let chosenSystem = null;

/** What the Installer shows one of at a time, and what each is called. Two
 *  subjects in one window, because the emulator is a package and a system is a
 *  two gigabyte disk: they belong together and want to be apart. */
const INSTALLER_TABS = {
  emulator: "installer.emulator.title",
  systems: "installer.systems",
};

/** Which of them is showing. Kept here rather than read back off the markup,
 *  so a redraw whilst something is installing leaves somebody where they
 *  were. */
let showingInTheInstaller = Object.keys(INSTALLER_TABS)[0];

/** Whether something has been asked for and the helper has not started yet.
 *
 *  The request is written into a file and a path unit starts the program that
 *  reads it, so for a moment after the answer comes back the newest thing the
 *  Pi has to say is still about the run before. Without this the window
 *  answers a press with the last run's "Finished". */
let waitingForTheHelper = false;

/** Which run was showing when that request was left, by the moment it started,
 *  so the one that follows it can be told apart from it. */
let theRunBefore = null;

/** When that request was left, by this browser's clock, so waiting for ever is
 *  not one of the states this window has. */
let askedAt = 0;

/** How long the helper may take to start before the window says it has not.
 *  A path unit fires within a second of the file appearing, so anything past
 *  this is a machine whose helper is not there rather than one that is slow. */
const PATIENCE_MS = 30000;

/** What the window says whilst it waits: first that the Pi is being asked, and
 *  then whatever the service answered. It stands until the helper has
 *  something of its own to say, because a sentence that is wiped by the next
 *  draw is a sentence nobody reads. */
let whilstWaiting = "";

/**
 * How large something is, in the words a person uses.
 * @param {number} bytes
 * @returns {string} Megabytes below a gigabyte and gigabytes above it, with the
 *   figure written the way the language being read writes one.
 */
function sized(bytes, fine) {
  /* @param fine - Whether to keep a decimal below a gigabyte. A figure that
     stands still says nothing about a download, so the counter keeps one and
     the list, where the number never moves, does not. */
  if (!bytes && bytes !== 0) return NOTHING;
  const gigabytes = bytes >= 1e9;
  const figure = new Intl.NumberFormat(currentLocale(),
    { maximumFractionDigits: gigabytes || fine ? 1 : 0 })
    .format(bytes / (gigabytes ? 1e9 : 1e6));
  return t(gigabytes ? "size.gb" : "size.mb", { size: figure });
}

/**
 * Asks the service what can be installed and what is happening, and draws it.
 *
 * Every figure is read now rather than remembered. What is free changes with
 * everything else on the machine, and a number from five minutes ago is what
 * lets an unpack stop half way through a disk image.
 */
async function refreshTheInstaller() {
  drawTheInstaller(await ask(SETUP));
}

/**
 * Draws the whole window.
 * @param {object|null} state - What /api/setup answered, or null on no contact.
 */
function drawTheInstaller(state) {
  if (state === null) {
    show("installer-caption", t("info.no-contact"));
    allowInstalling(false);
    return;
  }
  setupState = state;

  const here = state.systems.filter((system) => system.here);
  show("installer-emulator", emulatorLine(state.emulator));
  show("installer-count", t("installer.count",
                            { here: here.length, all: state.systems.length }));
  show("installer-room", sized(state.room));
  show("installer-emulator-note", whatTheButtonsDo(state.emulator));
  explain("installer-systems-note", t("installer.systems.note"));

  drawTheTabs();
  drawTheSystems(state.systems);
  drawWhatIsBeingInstalled(state.progress);
}

/**
 * Draws the row that chooses between the two subjects.
 *
 * The same raised cell every choice in this interface uses, and the groups
 * below are shown by the attribute the page marks them with, so the subjects
 * are named in one place.
 */
function drawTheTabs() {
  fillWithChoices("installer-tabs",
    Object.entries(INSTALLER_TABS).map(([subject, word]) => ({
      label: t(word),
      chosen: subject === showingInTheInstaller,
      choose: () => {
        showingInTheInstaller = subject;
        drawTheTabs();
      },
    })));

  for (const group of document.querySelectorAll(".installer-groups > [subject]")) {
    group.toggleAttribute(
      "away", group.getAttribute("subject") !== showingInTheInstaller);
  }
}

/**
 * What the readings say about the emulator.
 * @param {object} emulator - What the service says: whether it is here, which
 *   version, and what the archive offers.
 * @returns {string} The version where there is one, because that is the fact
 *   somebody wants, and the bare word where there is not.
 */
function emulatorLine(emulator) {
  if (!emulator?.here) return t("installer.emulator.out");
  return emulator.version
    ? t("installer.emulator.in.version", { version: emulator.version })
    : t("installer.emulator.in");
}

/**
 * A line per button, so that what each one does is read rather than guessed.
 * @param {object} emulator - What the service says about it.
 * @returns {string} The lines, one per button that is there, parted by
 *   newlines, which the stylesheet keeps.
 *
 * Update is left out entirely where the archive has nothing newer, because a
 * button that would bring the same version is a button that does nothing. Its
 * line names the version it would bring, since that is the whole of why
 * somebody would press it.
 */
function whatTheButtonsDo(emulator) {
  if (!emulator?.here) return t("installer.emulator.what.install");
  /* Nothing at all about updating where there is nothing newer, because the
     button is not there either. A sentence explaining a button nobody can see
     is a sentence about nothing. */
  return [
    t("installer.emulator.what.remove"),
    emulator.newer
      ? t("installer.emulator.what.update", { version: emulator.newest })
      : "",
  ].filter(Boolean).join("\n");
}

/**
 * Draws the six systems, with the one chosen marked.
 * @param {object[]} systems - What the service offers, each saying what it
 *   costs and whether it is already here.
 */
function drawTheSystems(systems) {
  document.getElementById("installer-systems").replaceChildren(
    ...systems.map((system) => {
      const row = document.createElement("div");
      row.className = "system";
      row.toggleAttribute("chosen", system.identifier === chosenSystem);

      /* Whether it is already here, as a mark rather than as a word: NeXT's
         own Installer.app carried this one for exactly this question. The ones
         that are not here keep the space, so the names line up. */
      const mark = document.createElement("i");
      mark.className = "system-mark";
      mark.toggleAttribute("here", system.here);

      const name = document.createElement("span");
      name.textContent = system.name;

      /* Always, whether it is here or not. How large a system is belongs to
         the system, and whether it is here is a different fact with a column
         of its own. */
      const cost = document.createElement("span");
      cost.className = "system-cost";
      cost.textContent = sized(system.size);

      row.append(mark, name, cost);
      row.addEventListener("click", () => {
        chosenSystem = system.identifier;
        drawTheInstaller(setupState);
      });
      return row;
    }));
}

/**
 * Says what is being installed, how far it has got, and how it went.
 * @param {object|null} progress - What the privileged helper wrote, or null
 *   where it has never run on this machine since it last started.
 *
 * The step is named in words out of the catalogue, because the helper sends a
 * name rather than a sentence for the same reason everything else here does.
 * The trough is there whilst something is running and gone otherwise, since an
 * empty gauge is a window claiming to be busy.
 */
function drawWhatIsBeingInstalled(progress) {
  const gauge = document.getElementById("installer-gauge");

  /* Anything the Pi is still showing from before the request is the run
     before this one, so the window keeps saying it was asked rather than
     reading out that one's ending. */
  if (waitingForTheHelper
      && Boolean(progress) && progress.started_at !== theRunBefore) {
    waitingForTheHelper = false;
  }
  if (waitingForTheHelper) {
    /* A path unit starts its service within a second of the file appearing, so
       a wait this long is a machine whose helper is not there rather than one
       that is slow. Saying so beats one word standing for ever. */
    const tooLong = Date.now() - askedAt > PATIENCE_MS;
    allowInstalling(tooLong);
    gauge.hidden = true;
    show("installer-caption",
         t(tooLong ? "installer.not-started" : "installer.asked"));
    show("installer-note",
         tooLong ? t("installer.not-started.why") : whilstWaiting);
    return;
  }

  const running = Boolean(progress) && progress.finished_at === null;
  allowInstalling(!running);
  gauge.hidden = !running;

  if (!progress) {
    show("installer-caption", t("installer.idle"));
    show("installer-note", "");
    return;
  }

  const step = t(`setup.step.${progress.step}`);
  if (running) {
    show("installer-caption", step);
    /* Which step of how many, and then what that step is doing at this moment
       and how much of how much. One step can fetch, unpack and then move, and
       a bar on its own says none of that. */
    show("installer-note", [
      t("installer.step", { done: progress.done, of: progress.of }),
      progress.part
        ? t(`installer.doing.${progress.part.doing}`, {
            done: sized(progress.part.done, true),
            of: sized(progress.part.of, true),
          })
        : "",
    ].filter(Boolean).join(" "));
    /* Two measures in one bar: which step of how many, and how far through a
       step that knows. A download and an unpack are the only ones that know,
       and they are the ones that take the minutes. */
    const through = progress.part?.of
      ? progress.part.done / progress.part.of : 0;
    const done = (progress.done - 1 + Math.min(1, through)) / progress.of;
    document.getElementById("installer-fill").style.width =
      `${Math.round(done * 100)}%`;
    return;
  }

  if (progress.ok) {
    show("installer-caption", t("installer.done"));
    /* What the machine has now, in one sentence about the job. The steps it
       took are what somebody watched go past whilst it ran, and reading them
       back as a list afterwards tells them nothing they can act on. A run
       where every step found its work already done is right and is over in a
       second, and "Finished" on its own reads as nothing having happened. */
    show("installer-note", progress.changed?.length
      ? t(`installer.finished.${progress.do}`)
      : t("installer.nothing-to-do"));
    return;
  }

  /* A failure says which step it was and what was put back, in the words the
     rest of the interface uses rather than as a line of shell output. */
  show("installer-caption", step);
  show("installer-note", [
    whyItFailed(progress.failed),
    progress.undone?.length
      ? t("installer.undone", {
          steps: progress.undone.map((name) => t(`setup.step.${name}`)).join(", "),
        })
      : "",
  ].filter(Boolean).join(" "));
}

/**
 * Why an installation stopped, as a sentence.
 * @param {object|null} failed - What the helper said, as `answers.told` shapes
 *   it, with the step it happened in beside it.
 * @returns {string}
 *
 * One of those answers carries counts of bytes, and bytes are the one value the
 * service cannot send ready to read: how large a number is worth writing out,
 * and how it is written, are questions about the language rather than about the
 * machine. So they are put into words here, as every other size in this window
 * is.
 */
function whyItFailed(failed) {
  if (!failed) return "";
  if (failed.reason !== "setup.no-room") return say(failed);
  return say({ ...failed, free: sized(failed.free),
               needed: sized(failed.needed) });
}

/**
 * Lets the window's buttons decide again, or turns them all off.
 * @param {boolean} allowed - False whilst something is being installed, because
 *   the service takes one installation at a time and a second request would be
 *   refused rather than queued.
 */
function allowInstalling(allowed) {
  const state = setupState;
  const here = Boolean(state?.emulator?.here);
  const chosen = state?.systems.find((system) => system.identifier === chosenSystem);

  document.getElementById("installer-install").disabled = !allowed || here;
  document.getElementById("installer-remove").disabled = !allowed || !here;
  /* Not there at all where the archive has nothing newer, because a button
     that would bring the version that is already here is a button that does
     nothing. */
  const update = document.getElementById("installer-update");
  update.hidden = !state?.emulator?.newer;
  update.disabled = !allowed || !here;

  document.getElementById("installer-fetch").disabled =
    !allowed || !chosen || chosen.here;
  document.getElementById("installer-forget").disabled =
    !allowed || !chosen || !chosen.here;
  /* A system that is not on the card cannot be started, and neither can the
     one the machine is already running. */
  document.getElementById("installer-activate").disabled =
    !allowed || !chosen || !chosen.here || Boolean(chosen.booting);
}

/**
 * Asks the service to install, update, remove or fetch something.
 * @param {string} job - One of Install.
 * @param {string} [system] - Which system, where the job needs one.
 *
 * Nothing waits for it to finish: the work takes minutes and happens on the Pi,
 * so what comes back is whether the request was taken, and the window follows
 * it from there.
 */
async function askTheInstaller(job, system) {
  waitingForTheHelper = true;
  theRunBefore = setupState?.progress?.started_at ?? null;
  askedAt = Date.now();
  whilstWaiting = t("installer.asking");
  drawWhatIsBeingInstalled(setupState?.progress ?? null);

  const answer = await tell(SETUP, { do: job, system: system ?? null });
  waitingForTheHelper = Boolean(answer?.ok);

  if (answer === null) {
    show("installer-note", t("note.no-service"));
    return;
  }
  /* What the service said, kept for as long as the window is waiting, because
     the draw that follows would otherwise wipe it before anybody reads it. */
  whilstWaiting = say(answer);
  show("installer-note", whilstWaiting);
  drawTheInstaller(answer.systems ? answer : setupState);
  refreshTheInstaller();
}

/**
 * Asks before the emulator is installed, and installs it when the answer is
 * yes.
 *
 * NeXTSTEP 3.3 comes with it unless another system is chosen in the list, so
 * that a machine which has just been set up boots into a system rather than
 * into a prompt about what to do next.
 */
async function installTheEmulator() {
  const system = whichSystemToInstallWith();
  const agreed = await askPanel({
    title: t("ask.install.title"),
    text: [
      t("ask.install.what"),
      system ? t("ask.install.system", {
        name: system.name,
        size: sized(system.size),
        unpacked: sized(system.unpacked),
      }) : "",
      t("ask.install.time"),
    ].filter(Boolean),
    icon: Art.Installer,
    confirm: t("button.install"),
  });
  if (agreed) askTheInstaller(Install.Emulator, system?.identifier);
}

/**
 * Which system the emulator is installed with.
 * @returns {object|undefined} The one chosen in the list, or the one the
 *   service says comes by default, or nothing at all where that one is already
 *   here.
 */
function whichSystemToInstallWith() {
  const systems = setupState?.systems ?? [];
  const chosen = systems.find((system) => system.identifier === chosenSystem);
  const wanted = chosen ?? systems.find(
    (system) => system.identifier === setupState?.default);
  return wanted?.here ? undefined : wanted;
}

/** Asks before the newest Previous is put in place, and does it if so. */
async function updateTheEmulator() {
  const agreed = await askPanel({
    title: t("ask.update.title"),
    text: [t("ask.update.what")],
    icon: Art.Installer,
    confirm: t("button.update"),
  });
  if (agreed) askTheInstaller(Install.Newest);
}

/** Asks before the emulator goes, and takes it away if so. */
async function removeTheEmulator() {
  const agreed = await askPanel({
    title: t("ask.remove-emulator.title"),
    text: [t("ask.remove-emulator.loss"), t("ask.remove-emulator.disks")],
    icon: Art.Installer,
    confirm: t("button.remove"),
  });
  if (agreed) askTheInstaller(Install.Away);
}

/**
 * Asks before a system is fetched, saying what it costs and what is left.
 *
 * A card that fills up during an unpack leaves a half written image and a
 * person with no idea why, so the figures are in the question rather than in a
 * failure afterwards.
 */
async function fetchTheSystem() {
  const system = setupState?.systems.find(
    (entry) => entry.identifier === chosenSystem);
  if (!system) return;

  const agreed = await askPanel({
    title: t("ask.fetch.title", { name: system.name }),
    text: [
      t("ask.fetch.cost", {
        name: system.name,
        size: sized(system.size),
        unpacked: sized(system.unpacked),
      }),
      t("ask.fetch.left", {
        free: sized(setupState.room),
        left: sized(Math.max(0, setupState.room - system.unpacked)),
      }),
      /* The same sentence the other question ends on, because it says the same
         thing: this takes minutes and the window can be left. Two copies of it
         would part company the first time one was rewritten. */
      t("ask.install.time"),
    ],
    icon: Art.Installer,
    confirm: t("button.fetch"),
  });
  if (agreed) askTheInstaller(Install.Fetch, system.identifier);
}

/** Asks before a system's disk goes, and takes it away if so. */
async function forgetTheSystem() {
  const system = setupState?.systems.find(
    (entry) => entry.identifier === chosenSystem);
  if (!system) return;

  const agreed = await askPanel({
    title: t("ask.forget.title", { name: system.name }),
    text: [t("ask.forget.loss"), t("ask.forget.again")],
    icon: Art.Installer,
    confirm: t("button.remove"),
  });
  if (agreed) askTheInstaller(Install.Forget, system.identifier);
}

/**
 * Starts the machine on the system chosen in the list.
 *
 * The same act as a double click on a disk in the File Viewer, and the same
 * question, so there is one implementation of it and one thing to get right.
 * What it costs to know is built here because the Installer names a system by
 * what it is rather than by where its file sits.
 */
function activateTheSystem() {
  const chosen = setupState?.systems.find(
    (system) => system.identifier === chosenSystem);
  if (!chosen?.here) return;

  bootFromDisk({
    id: chosen.identifier,
    name: chosen.name,
    bytes: chosen.unpacked,
    booting: chosen.booting,
  });
}

/** Wires the Installer's six buttons and the look it takes on its own. */
function wireTheInstaller() {
  const window_ = document.querySelector('nx-window[name="installer"]');
  if (!window_) return;

  document.getElementById("installer-install")
    .addEventListener("click", installTheEmulator);
  document.getElementById("installer-update")
    .addEventListener("click", updateTheEmulator);
  document.getElementById("installer-remove")
    .addEventListener("click", removeTheEmulator);
  document.getElementById("installer-fetch")
    .addEventListener("click", fetchTheSystem);
  document.getElementById("installer-forget")
    .addEventListener("click", forgetTheSystem);
  document.getElementById("installer-activate")
    .addEventListener("click", activateTheSystem);

  /* Opening it asks straight away, because a window that filled itself at the
     next poll would stand empty for a moment first. */
  window_.addEventListener("nx-open", refreshTheInstaller);

  /* Whilst the window is open, or whilst something is being installed with it
     closed: a run takes minutes and goes on whether anybody is watching, and
     what is on the screen when somebody comes back has to be true.

     Four times as often whilst something is happening. A run where every step
     finds its work already done is over in a second, and asking every two
     seconds would miss it entirely: somebody would press Install and see the
     window go from asked to finished with nothing in between, or nothing at
     all. */
  let ticks = 0;
  setInterval(() => {
    ticks += 1;
    const busy = waitingForTheHelper
      || (setupState?.progress && setupState.progress.finished_at === null);
    if (!busy && ticks % EVERY_FOURTH !== 0) return;
    if (!window_.hidden || busy) refreshTheInstaller();
  }, WATCHING_MS);

  if (!window_.hidden) refreshTheInstaller();
}

/**
 * Changes the language the whole interface speaks.
 * @param {string} code - One of `en`, `de`, `fr`, `it`, `es` and `sv`.
 * @returns {boolean} Whether that language exists.
 *
 * Everything the markup carries is written by `setLanguage` itself. What this
 * adds is the other half: every window the page fills in as it goes, which has
 * to be filled in again before any of it is read in the new language.
 *
 * The Preferences window offers it, and the console can call it directly.
 */
function speak(code) {
  return setLanguage(code, () => {
    drawLanguages();
    drawSizes();
    showModule(document.querySelector(
      "nx-window[name='preferences'] .module[chosen]")?.getAttribute("value")
      ?? "localization");
    drawPlace();
    redrawTheEditor();
    /* Every figure and every sentence in the Installer is this page's, so it is
       drawn again from what the service last said rather than by asking. */
    if (setupState) drawTheInstaller(setupState);
    else drawTheTabs();
    /* The menu's title is a name this page chooses rather than a string in
       the markup, so translate() does not reach it. */
    drawTheMenu();
    refresh();
  });
}

/* The words first, so every element is built around text it already has.
   Then the elements, and only then this application's own wiring: a window
   that does not exist yet cannot be wired to anything. */
translate();
defineTheKit();
defineTheTerminal();

drawAtSize(chosenSize());
wireButtons();
wirePreferences();
wireMachines();
wireBoard();
wireOpening();
wireTerminal();
wireGrab();
wirePreview();
wireEditor();
wireTheInstaller();
watchTheFrontWindow();
greetTheFirstVisit();
watchTheApplications();
drawLanguages();
/* Both before the editor is filled, because what it shows is the machine that is
   set and which of the saved configurations that is, and neither is known until
   the tree and the status are in. */
Promise.all([drawMachines(), refresh()]).then(fillTheEditorIfItCameBackOpen);
setInterval(refresh, REFRESH_MS);
