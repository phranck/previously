/* Everything this interface asks the service, and what it says back. */

import { t } from "../strings.js";
import { askForPassword } from "./panels.js";
import { drawStatus, refresh, setBusy } from "./status.js";
import { say } from "./words.js";

/** What the service names a screenshot it filed, so the viewer can be redrawn
 *  without asking for the whole tree to find out whether it should be. */
const KEPT_HEADER = "X-Previously-Kept";

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

/** How long an operation may take before the page stops waiting for the
 *  answer. Longer than the longest change of machine, which is
 *  LONGEST_SECONDS in change.py: a machine with a NeXTdimension that never
 *  draws and is put back. So the reason the service gives always arrives
 *  rather than being cut off by the browser. */
const OPERATION_TIMEOUT_MS = 420000;

/**
 * Fetches one of the service's answers.
 * @param {string} route - The path, such as "/api/status".
 * @returns {Promise<any>} The parsed answer, or null when the service
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
 * @param {any} [body] - What to send, where the route takes something.
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
 * Asks the service to do something to the emulator.
 * @param {string} route - Where to send it.
 * @param {any} [body] - What to send, where the route takes something.
 * @returns {Promise<any>} What it answered, or null on no contact.
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

export {
  KEPT_HEADER,
  TERMINAL,
  Kiosk,
  Board,
  Saved,
  ask,
  send,
  tell,
  operate,
};
