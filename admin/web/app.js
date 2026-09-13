/* What this particular application does with the kit.
 *
 * The kit in nextstep.js knows about windows and shelves and nothing about
 * emulators. Everything that knows what a NeXTcube is lives here.
 *
 * At this point it reads and shows. Nothing on this page changes anything on
 * the machine.
 */

/** How often the status is fetched. A machine whose job is to sit there does
 *  not repay a faster poll than this. */
const REFRESH_MS = 5000;

/** What the pictures are called, by what they mean rather than by their file. */
const Art = {
  Computer: "root",
  ComputerColor: "root-color",
};

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
  state.replaceChildren(lamp,
    document.createTextNode(status.running
      ? ` läuft ${since(status.uptime_seconds)}`
      : " angehalten"));

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

/** Fetches the status and draws it. */
async function refresh() {
  drawStatus(await ask("/api/status"));
}

refresh();
setInterval(refresh, REFRESH_MS);
