/* What this particular application does with the kit.
 *
 * The kit in nextstep.js knows about windows and shelves and nothing about
 * emulators. Everything that knows what a NeXTcube is lives here.
 *
 * Reading needs no token. The three buttons that switch the emulated machine
 * on and off do, and the service refuses them without one.
 */

/** How often the status is fetched. A machine whose job is to sit there does
 *  not repay a faster poll than this. */
const REFRESH_MS = 5000;

/** Where the token is kept, so it is typed once rather than every visit. */
const TOKEN_KEY = "previously:token";

/** The header the service reads it from. Not a query parameter: a URL ends up
 *  in logs, in history and in whatever somebody pastes into a chat window. */
const TOKEN_HEADER = "X-Previously-Token";

/** What stands in a field that has nothing to say. An em dash rather than an
 *  empty field, because an empty one reads as a value that is missing and this
 *  one is a question that does not arise. */
const NOTHING = "—";

/** What the pictures are called, by what they mean rather than by their file. */
const Art = {
  Computer: "root",
  Folder: "folder",
  Cube: "nextcube",
  Station: "nextstation",
  Editor: "defaultAppIcon",
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
  if (told.reason === "guest.still-shutting-down") return t(key, values, told.seconds);
  if (told.reason === "machine.running") return t(key, values, told.lines);
  return t(key, values);
}

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
    const answer = await fetch(route, { cache: "no-store", headers: headers() });
    return answer.ok ? await answer.json() : null;
  } catch {
    return null;
  }
}

/**
 * The headers every request carries.
 * @returns {object} The token where one is known, nothing otherwise.
 */
function headers() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { [TOKEN_HEADER]: token } : {};
}

/**
 * Keeps a token and reports whether the service accepts it.
 * @param {string} token - What the user read out of /var/lib/previously/token.
 * @returns {Promise<boolean>} A wrong one is thrown away rather than kept, so
 *   the next request fails for a reason somebody can act on.
 */
async function useToken(token) {
  localStorage.setItem(TOKEN_KEY, token.trim());
  const answer = await ask("/api/token");
  if (!answer?.valid) localStorage.removeItem(TOKEN_KEY);
  return Boolean(answer?.valid);
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
 * Asks for the token until one is accepted or the panel is dismissed.
 * @param {string} [why] - A first line saying what prompted the question.
 * @returns {Promise<boolean>} Whether the service now accepts what we hold.
 */
async function askForToken(why) {
  let complaint = why;

  for (;;) {
    const typed = await askPanelFor({
      title: t("ask.token.title"),
      text: [
        complaint,
        t("ask.token.where"),
        /* A command is typed rather than read, so it stays as it is. */
        "sudo cat /var/lib/previously/token",
      ].filter(Boolean),
      icon: Art.Computer,
      confirm: t("button.use"),
    });

    if (typed === null) return false;
    if (await useToken(typed)) return true;
    complaint = t("ask.token.wrong");
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
 * What a machine is called, from the facts the service sent.
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The model's own name with what is fitted to it.
 *
 * The model is a product name and arrives as it is. What gets added to it is
 * a sentence, so it is added here.
 */
function nameOf(machine) {
  let name = machine.model;
  if (machine.turbo && machine.kind !== 0) name += " Turbo";
  if (machine.dimension) name = t("machine.with-dimension", { name });
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
  let words = t("state.stopped");
  if (status.running) words = t("state.running", { since: since(status.uptime_seconds) });
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

  document.getElementById("kiosk-start").disabled = status.running;
  document.getElementById("kiosk-stop").disabled = !status.running;
  document.getElementById("kiosk-restart").disabled = !status.running;

  /* Without the console session there is nothing waiting to start the emulator
     again, so switching it on would report success and do nothing. Saying so
     here is the only place that failure becomes visible. */
  if (!status.console_active) {
    show("kiosk-note", t("note.no-console"));
  }

  const machine = status.configuration;
  if (!machine) {
    show("info-caption", t("info.unreadable"));
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

/**
 * Asks the service to do something to the emulator.
 * @param {string} route - Where to send it.
 * @param {object} [body] - What to send, where the route takes something.
 * @returns {Promise<object|null>} What it answered, or null on no contact.
 */
async function tell(route, body) {
  const send = async () => fetch(route, {
    method: "POST",
    cache: "no-store",
    headers: body
      ? { ...headers(), "Content-Type": "application/json" }
      : headers(),
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(OPERATION_TIMEOUT_MS),
  });

  try {
    let answer = await send();

    /* Refused for want of a token. Ask for one and do what was asked, rather
       than reporting a failure the reader would have to interpret. */
    if (answer.status === 403) {
      const accepted = await askForToken(t("ask.token.needed"));
      if (!accepted) return { ok: false, reason: "token.not-given" };
      answer = await send();
    }

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
 *  always one step home, and the machines, which is where the work is. */
const KEPT_BY_DEFAULT = ["/", "/Machines"];

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

/** Wires the three buttons and the menu's own way to the token. */
function wireButtons() {
  document.querySelector('nx-menu-item[name="token"]')
    ?.addEventListener("click", () => askForToken());

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
  /* Stay where the reader was, by path rather than by object, because the
     tree they are looking at was fetched again. */
  at = at.map((step) => find(root, step.path)).filter(Boolean);
  if (!at.length) at = [root];
  drawPlace();

  document.getElementById("file-viewer")
    .addEventListener("click", () => show("machine-note", ""));
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
    name: folder.name,
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
    label: entry.name,
    /* A folder and an application bring their own picture. A machine wears
       the one its boot ROM draws, and which that is follows from its case. */
    icon: entry.icon ?? machineArt(entry.enclosure),
    value: entry.path,
    folder: entry.kind === "folder",
  };
}

/**
 * Answers a double click in the viewer, whatever was under it.
 * @param {string} path - What the thing carries.
 */
function open(path) {
  const entry = find(root, path);
  if (!entry) return;
  if (entry.kind === "folder" || entry.path === "/") {
    /* Built from the path rather than by adding a step, because a folder on
       the shelf can be anywhere and the way there is not the way from here. */
    at = chainTo(entry.path);
    return drawPlace();
  }
  if (entry.kind === "application") {
    return notYet(entry.name.replace(/\.app$/, ""));
  }
  changeTo(entry.id);
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
    const entry = catalogue.find((machine) => machine.path === thing.getAttribute("value"));
    const isCurrent = Boolean(identifier) && entry?.id === identifier;
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
  const onShelf = Boolean(thing.closest(".keep"));
  if (!machine && !onShelf) return false;

  const menu = document.querySelector('nx-menu[name="machine-menu"]');
  /* Which machine this is about. The menu appears over whatever was clicked
     and then goes away, so without a name it is an orphan. */
  menu.querySelector(".title").textContent = thing.getAttribute("label");
  const info = menu.querySelector('nx-menu-item[name="info"]');
  const activate = menu.querySelector('nx-menu-item[name="activate"]');
  const edit = menu.querySelector('nx-menu-item[name="edit"]');
  const shelf = menu.querySelector('nx-menu-item[name="shelf"]');

  /* Three of the four are about a machine, so a folder on the shelf shows the
     one entry that applies to it. */
  for (const entry of [info, activate, edit]) entry.hidden = !machine;

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

  if (machine) {
    /* The machine that is already running cannot be activated: it would shut
       NeXTSTEP down, write the same values back and start it again, for
       nothing. The entry stays, so the menu keeps its shape. */
    activate.toggleAttribute("disabled", thing.hasAttribute("disabled"));

    activate.onclick = () => {
      if (activate.hasAttribute("disabled")) return;
      menu.close();
      changeTo(machine.id);
    };
  }
  edit.onclick = () => {
    menu.close();
    notYet("Config Editor");
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
  /* A right click anywhere on a machine, rather than on the shelf, so the menu
     is always about something. */
  document.getElementById("file-viewer").addEventListener("contextmenu", (event) => {
    const thing = event.target.closest("nx-thing");
    if (!thing) return;
    event.preventDefault();
    openMachineMenu(thing, event.clientX, event.clientY);
  });

  document.querySelector('nx-tile[name="editor"]')
    ?.addEventListener("click", () => notYet("Config Editor"));

  /* Carried onto the info window, or double clicked in the viewer. The kit
     raises the same event for both, so this is one answer to two gestures,
     and what happens follows from what was chosen. */
  document.addEventListener("nx-choose", (event) => open(event.detail.value));

  /* A step of the path was clicked, so go back to it. */
  document.addEventListener("nx-path", (event) => goTo(event.detail.index));

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
}

/** Fetches the status and draws it, and the board's readings where its window
 *  is open. A window nobody is looking at costs nothing. */
async function refresh() {
  drawStatus(await ask("/api/status"));

  const window_ = document.querySelector('nx-window[name="pi"]');
  if (window_ && !window_.hidden) drawPi(await ask("/api/pi"));
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
 * Until the Preferences window of #19 offers this, it is reached from the
 * browser's console.
 */
function speak(code) {
  return setLanguage(code, () => {
    drawPlace();
    refresh();
  });
}

wireButtons();
wireMachines();
wireBoard();
wireOpening();
drawMachines();
refresh();
setInterval(refresh, REFRESH_MS);
