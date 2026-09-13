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
  ComputerColor: "root-color",
};

/** What the buttons ask the service to do, by the route that does it. */
const Kiosk = {
  Start: "/api/kiosk/start",
  Stop: "/api/kiosk/stop",
  Restart: "/api/kiosk/restart",
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

/**
 * Draws the state of the machine into the info window.
 * @param {object|null} status - What /api/status answered, or null.
 */
function drawStatus(status) {
  const state = document.getElementById("info-state");

  if (status === null) {
    state.replaceChildren(document.createTextNode("nicht erreichbar"));
    show("info-caption", "keine Verbindung");
    return;
  }

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
  state.replaceChildren(lamp, document.createTextNode(words));

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
  show("info-cpu", machine.cpu);
  show("info-ram", `${machine.memory_mb} MB`);
  show("info-screen", machine.screen);
  show("info-disk", machine.disk ?? "keine eingelegt");

  /* The picture is root.tiff either way, because NeXTSTEP had one machine icon
     and drew every host with it. Only the tube changes: a machine that could
     show colour shows colour. */
  const colour = machine.screen.includes("farbig");
  document.getElementById("info-icon").style.backgroundImage =
    `var(--${colour ? Art.ComputerColor : Art.Computer})`;
}

/**
 * Asks the service to do something to the emulator.
 * @param {string} route - One of Kiosk.
 * @returns {Promise<object|null>} What it answered, or null on no contact.
 */
async function tell(route) {
  const send = async () => fetch(route, {
    method: "POST",
    cache: "no-store",
    headers: headers(),
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
    icon: Art.Computer,
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

/** Fetches the status and draws it. */
async function refresh() {
  drawStatus(await ask("/api/status"));
}

wireButtons();
refresh();
setInterval(refresh, REFRESH_MS);
