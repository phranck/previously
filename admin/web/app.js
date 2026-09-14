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

/** What the pictures are called, by what they mean rather than by their file. */
const Art = {
  Computer: "root",
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
 * Asks for the token until one is accepted or the panel is dismissed.
 * @param {string} [why] - A first line saying what prompted the question.
 * @returns {Promise<boolean>} Whether the service now accepts what we hold.
 */
async function askForToken(why) {
  const panel = document.getElementById("ask");
  let complaint = why;

  for (;;) {
    const typed = await panel.askFor({
      title: "Token",
      text: [
        complaint,
        "Auf dem Pi steht es in einer Datei, die nur der Dienst lesen darf:",
        "sudo cat /var/lib/previously/token",
      ].filter(Boolean),
      icon: Art.Computer,
      confirm: "Übernehmen",
    });

    if (typed === null) return false;
    if (await useToken(typed)) return true;
    complaint = "Das war nicht das Token dieser Maschine.";
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
  if (hours > 0) return `seit ${hours}:${String(minutes).padStart(2, "0")} Std`;
  if (minutes > 0) return `seit ${minutes} Min`;
  return "seit weniger als einer Minute";
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

  if (status === null) {
    /* Nothing can be asked of a machine that is not answering, and whilst it
       restarts it will not answer for a minute or two. Leaving the buttons
       live would collect requests that go nowhere. */
    state.replaceChildren(document.createTextNode("nicht erreichbar"));
    show("info-caption", "keine Verbindung");
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
  let words = " angehalten";
  if (status.running) words = ` läuft ${since(status.uptime_seconds)}`;
  else if (status.held) words = " ausgeschaltet";
  /* The file has been written since this machine started, so it holds a
     machine nobody has tried. Said here in words, because the mark in the
     shelf is a texture and a texture explains nothing on its own. */
  const untried = Boolean(status.file?.newer_than_the_machine);
  if (untried) words += ", Konfiguration geändert";
  state.replaceChildren(lamp, document.createTextNode(words));

  /* "kommt zurück" is done when it is back, and the note should not still be
     saying it. So a note is kept until the machine is in a different state
     than it was when the note was written, and then it goes. */
  const nowState = `${status.running}/${status.held}/${status.configuration?.machine}`;
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
    show("kiosk-note", "Die Konsole läuft nicht. Einschalten bleibt wirkungslos.");
  }

  const machine = status.configuration;
  if (!machine) {
    show("info-caption", "Konfiguration nicht lesbar");
    for (const id of ["info-cpu", "info-ram", "info-screen", "info-disk"]) show(id, "—");
    return;
  }

  show("info-caption", machine.machine);
  markCurrent(machine.machine, untried);
  show("info-cpu", machine.cpu);
  show("info-ram", `${machine.memory_mb} MB`);
  show("info-screen", machine.screen);
  show("info-disk", machine.disk ?? "keine eingelegt");

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
      const accepted = await askForToken(
        "Dieser Vorgang ändert etwas an der Maschine und braucht das Token.");
      if (!accepted) return { ok: false, reason: "ohne Token abgebrochen" };
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
  setBusy(false, answer === null
    ? "keine Verbindung zum Dienst"
    : answer.reason ?? "");
  if (answer) drawStatus(answer);
  refresh();
}

/** The picture of the machine that is configured now, so a panel asking about
 *  it shows it rather than a generic computer. Set from every status. */
let runningArt = Art.Computer;

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
  return document.getElementById("ask").ask({
    title: "NeXTSTEP anhalten",
    text: [
      "NeXTSTEP wird über den Ausschalter heruntergefahren, so wie über Power Off im Logout-Fenster.",
      "Nicht gespeicherte Arbeit in laufenden Programmen geht dabei verloren. Der Dienst kann nicht sehen, woran die Maschine gerade arbeitet.",
    ],
    icon: runningArt,
    confirm: what,
  });
}

/** Wires the three buttons and the menu's own way to the token. */
function wireButtons() {
  document.querySelector('nx-menu-item[name="token"]')
    ?.addEventListener("click", () => askForToken());

  document.getElementById("kiosk-start").addEventListener("click",
    () => operate(Kiosk.Start, "wird eingeschaltet"));

  document.getElementById("kiosk-stop").addEventListener("click", async () => {
    if (await warn("Ausschalten")) operate(Kiosk.Stop, "fährt herunter");
  });

  document.getElementById("kiosk-restart").addEventListener("click", async () => {
    if (await warn("Neu starten")) operate(Kiosk.Restart, "startet neu");
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
  const answer = await ask("/api/machines");
  const shelf = document.getElementById("machine-shelf");
  if (!answer) {
    show("machine-note", "Liste nicht erreichbar");
    return;
  }

  shelf.replaceChildren(...answer.machines.map((machine) => {
    const thing = document.createElement("nx-thing");
    thing.setAttribute("icon", machineArt(machine.enclosure));
    thing.setAttribute("label", machine.name);
    /* The value is what a drop, a double click and the button all hand over,
       so there is one place the machine's name lives. */
    thing.setAttribute("value", machine.id);
    return thing;
  }));

  shelf.addEventListener("click", () => show("machine-note", ""));
}

/**
 * Marks the machine the emulator is currently set to.
 * @param {string|null} name - What /api/status called it.
 * @param {boolean} [untried] - Whether the file has been written since that
 *   machine started, so what is written down has never been through a boot.
 */
function markCurrent(name, untried) {
  for (const thing of document.querySelectorAll("#machine-shelf nx-thing")) {
    const isCurrent = thing.getAttribute("label") === name;
    thing.classList.toggle("current", isCurrent);
    thing.classList.toggle("untried", isCurrent && Boolean(untried));
    /* Switching to the machine that is already running would shut NeXTSTEP
       down, write the same values back and start it again, for nothing. */
    thing.toggleAttribute("disabled", isCurrent);
    if (isCurrent) thing.removeAttribute("chosen");
  }
}

/**
 * Asks about a machine and changes to it when the answer is yes.
 * @param {string} identifier - Which machine, as the catalogue names it.
 */
async function changeTo(identifier) {
  const thing = document.querySelector(
    `#machine-shelf nx-thing[value="${identifier}"]`);
  if (!thing) return;

  const name = thing.getAttribute("label");
  const agreed = await document.getElementById("ask").ask({
    title: "Maschine wechseln",
    text: [
      `Als ${name} starten?`,
      "NeXTSTEP wird über den Ausschalter heruntergefahren, die Konfiguration geschrieben und die Maschine neu gestartet.",
      "Kommt sie damit nicht hoch, wird die vorherige Konfiguration von selbst zurückgeschrieben.",
    ],
    /* The thing in the shelf already carries the picture for this machine, so
       the panel takes it from there rather than asking a second time. */
    icon: thing.getAttribute("icon"),
    confirm: "Wechseln",
  });
  if (!agreed) return;

  setBusy(true, `wechselt auf ${name}`);
  const answer = await tell("/api/machine", { machine: identifier });
  setBusy(false, answer === null
    ? "keine Verbindung zum Dienst"
    : answer.reason ?? "");
  if (answer) drawStatus(answer);
  refresh();
}

/**
 * Says that an application that is not built yet is not built yet.
 * @param {string} name - What it will be called.
 */
function notYet(name) {
  return document.getElementById("ask").ask({
    title: name,
    text: [
      `${name} gibt es noch nicht.`,
      "Sie soll die Maschine so einstellbar machen, wie Previous es erlaubt, und nicht als Textdatei. Das wird gerade besprochen.",
    ],
    icon: Art.Editor,
    confirm: "Gut",
    cancel: "Schliessen",
  });
}

/**
 * Opens the context menu for one machine.
 * @param {HTMLElement} thing - The machine that was clicked.
 * @param {number} x - Where the pointer was.
 * @param {number} y
 */
function openMachineMenu(thing, x, y) {
  const menu = document.querySelector('nx-menu[name="machine-menu"]');
  /* Which machine this is about. The menu appears over whatever was clicked
     and then goes away, so without a name it is an orphan. */
  menu.querySelector(".title").textContent = thing.getAttribute("label");
  const activate = menu.querySelector('nx-menu-item[name="activate"]');
  const edit = menu.querySelector('nx-menu-item[name="edit"]');

  /* The machine that is already running cannot be activated: it would shut
     NeXTSTEP down, write the same values back and start it again, for
     nothing. The entry stays, so the menu keeps its shape. */
  activate.toggleAttribute("disabled", thing.hasAttribute("disabled"));

  activate.onclick = () => {
    if (activate.hasAttribute("disabled")) return;
    menu.close();
    changeTo(thing.getAttribute("value"));
  };
  edit.onclick = () => {
    menu.close();
    notYet("Config Editor");
  };

  menu.openAt(x, y);
}

/**
 * Asks before the whole machine goes, and says in which order.
 * @param {string} what - The wording on the acting button.
 * @param {string} afterwards - What the board does once the guest is down.
 * @returns {Promise<boolean>}
 */
function warnAboutTheBoard(what, afterwards) {
  return document.getElementById("ask").ask({
    title: "Raspberry Pi",
    text: [
      `Den Raspberry Pi ${afterwards}?`,
      "NeXTSTEP wird zuerst über den Ausschalter heruntergefahren. Der Pi wartet darauf, weil ein Neustart unter einem laufenden Emulator dasselbe anrichtet wie das Abschalten mitten im Schreiben.",
      "Nicht gespeicherte Arbeit in laufenden Programmen geht dabei verloren.",
    ],
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
  show("pi-note", answer === null
    ? "Keine Antwort mehr. Das ist zu erwarten, wenn der Pi gerade abschaltet."
    : answer.reason ?? "");

  /* Nothing is switched back on here. The next status decides: whilst the
     board is away it does not answer, and everything stays off until it does. */
  refresh();
}

/** Wires the board's own two buttons. */
function wireBoard() {
  document.getElementById("pi-reboot").addEventListener("click", async () => {
    if (await warnAboutTheBoard("Neu starten", "neu starten")) {
      operateBoard(Board.Reboot, "NeXTSTEP fährt herunter, dann startet der Pi neu");
    }
  });

  document.getElementById("pi-poweroff").addEventListener("click", async () => {
    if (await warnAboutTheBoard("Ausschalten", "ausschalten")) {
      operateBoard(Board.PowerOff, "NeXTSTEP fährt herunter, dann schaltet der Pi ab");
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
  document.getElementById("machine-shelf").addEventListener("contextmenu", (event) => {
    const thing = event.target.closest("nx-thing");
    if (!thing) return;
    event.preventDefault();
    openMachineMenu(thing, event.clientX, event.clientY);
  });

  document.querySelector('nx-tile[name="editor"]')
    ?.addEventListener("click", () => notYet("Config Editor"));

  /* Carried onto the info window, or double clicked in the shelf. The kit
     raises the same event for both, so this is one answer to two gestures. */
  document.addEventListener("nx-choose",
    (event) => changeTo(event.detail.value));
}

/**
 * Says how long something has been running, the short way.
 * @param {number|null} seconds
 * @returns {string}
 */
function duration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days} Tage, ${hours} Std`;
  if (hours > 0) return `${hours} Std ${minutes} Min`;
  return `${minutes} Min`;
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
    show("pi-model", "nicht erreichbar");
    allowActions(false);
    return;
  }

  show("pi-model", pi.model ?? "—");
  show("pi-uptime", duration(pi.uptime_seconds));

  /* Above 80 degrees a Pi 5 begins to slow itself down, so that is where the
     reading stops being a number and becomes a warning. */
  const temperature = pi.temperature_c;
  showState("pi-temp", temperature !== null && temperature < 80,
    temperature === null ? "—" : `${temperature.toFixed(1)} °C`);

  /* Two different things. Something happening now is a problem to act on, and
     something that happened once may have been the moment a drive was plugged
     in, which is worth knowing and not worth alarm. */
  const throttling = pi.throttling;
  if (!throttling) {
    showState("pi-power", true, "—");
  } else if (throttling.now.length) {
    showState("pi-power", false, `jetzt: ${throttling.now.join(", ")}`);
  } else if (throttling.since_boot.length) {
    showState("pi-power", false, `seit dem Start: ${throttling.since_boot.join(", ")}`);
  } else {
    showState("pi-power", true, "in Ordnung");
  }

  /* Around 150 per cent of one core is ordinary with a NeXTdimension, because
     two threads run, so the figure is stated without judging it. */
  show("pi-emulator", pi.emulator
    ? `${Math.round(pi.emulator.cpu_percent)} %, ${pi.emulator.memory_mb} MB, `
      + duration(pi.emulator.uptime_seconds)
    : "läuft nicht");

  /* The one that looks like nothing: the card is there, the configuration
     still names it, and the stream was closed when the speaker was moved. */
  showState("pi-sound", Boolean(pi.sound?.playing),
    pi.sound ? `${pi.sound.card}, ${pi.sound.playing ? "spielt" : "still"}` : "keine Karte");

  show("pi-memory", pi.memory
    ? `${pi.memory.available_mb} von ${pi.memory.total_mb} MB frei` : "—");
  show("pi-disk", pi.disk
    ? `${Math.round(pi.disk.free_mb / 1024)} GB frei, ${pi.disk.used_percent} % belegt`
    : "—");
}

/** Fetches the status and draws it, and the board's readings where its window
 *  is open. A window nobody is looking at costs nothing. */
async function refresh() {
  drawStatus(await ask("/api/status"));

  const window_ = document.querySelector('nx-window[name="pi"]');
  if (window_ && !window_.hidden) drawPi(await ask("/api/pi"));
}

wireButtons();
wireMachines();
wireBoard();
wireOpening();
drawMachines();
refresh();
setInterval(refresh, REFRESH_MS);
