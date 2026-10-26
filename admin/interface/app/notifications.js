/* What the Pi decided is worth saying, drawn as notifications beside the dock.

   The service decides which readings become a notification and says so as
   names, levels and values. This page asks for that list, puts each entry into
   words in the language the interface speaks, and remembers in this browser
   which ones somebody has closed, whether notifications show here, where
   they stand and whether they sound. */

import { t } from "../strings.js";
import { ask } from "./service.js";
import { theWindow } from "./page.js";
import { released, sized, when } from "./words.js";

/** @typedef {import("../answers.js").NotificationEntry} NotificationEntry */
/** @typedef {import("../nextstep.js").NxNotifications} NxNotifications */

/** Where the Pi says what is worth saying. */
const NOTIFICATIONS = "/api/notifications";

/** How often to ask. A card filling up or a board getting hot changes over
 *  minutes, and the answer takes the service three forks to give. */
const POLL_MS = 30000;

/** Where this browser keeps the notifications somebody closed, as each one's
 *  name and the reading it carried then. */
const CLOSED_KEY = "notifications.closed";

/** Where this browser keeps how notifications reach it, which Preferences
 *  sets in its Notifications module. */
const SETTINGS_KEY = "notifications.settings";

/** The four corners a stack can stand in, by the names the stack's `corner`
 *  attribute and the radio buttons in Preferences carry. */
const CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"];

/**
 * How notifications reach this browser.
 * @typedef {object} NotificationSettings
 * @property {boolean} show - Whether they show at all.
 * @property {boolean} sound - Whether one that appears plays the chime.
 * @property {string} corner - One of CORNERS.
 */

/** What a browser that never chose starts with: shown, silent, top right
 *  beside the dock. @type {NotificationSettings} */
const FIRST_SETTINGS = { show: true, sound: false, corner: "top-right" };

/** The chime a notification plays as it appears: Glass, one of the sounds
 *  NeXTSTEP's Sound module offered as the system beep, which design/extract.py
 *  takes out of the disk image. */
const CHIME = "sounds/Glass.wav";

/** Which picture each level wears.
 *  @type {Record<string, string>} */
const ART = {
  info: "sign-info",
  alert: "sign-alert",
  error: "stop",
};

/** Which window each notification opens, by its name: the one that shows the
 *  reading behind it and offers what can be done about it.
 *  @type {Record<string, string>} */
const OPENS = {
  update: "pi",
  emulator: "installer",
  power: "pi",
  temperature: "pi",
  disk: "pi",
  crash: "pi",
};

/** The last list the Pi sent, so it can be drawn again in another language.
 *  @type {NotificationEntry[]} */
let lastSaid = [];

/**
 * The stack on this page, or nothing where the markup has none.
 * @returns {NxNotifications | null}
 */
function theStack() {
  return document.querySelector("nx-notifications");
}

/**
 * What somebody closed, by name.
 * @returns {Record<string, string>} Each name and the reading it carried.
 */
function closed() {
  try {
    const kept = JSON.parse(localStorage.getItem(CLOSED_KEY) ?? "{}");
    return kept && typeof kept === "object" ? kept : {};
  } catch {
    return {};
  }
}

/**
 * Writes down what somebody closed.
 * @param {Record<string, string>} kept
 */
function keepClosed(kept) {
  try {
    localStorage.setItem(CLOSED_KEY, JSON.stringify(kept));
  } catch {
    /* A browser that refuses to store it shows it again at the next visit. */
  }
}

/**
 * What this browser keeps about how notifications reach it, as it was written.
 * @returns {Record<string, unknown>} Empty where nothing readable is kept.
 */
function keptSettings() {
  try {
    const kept = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "{}");
    return kept && typeof kept === "object" ? kept : {};
  } catch {
    return {};
  }
}

/**
 * How notifications reach this browser, as kept, with anything missing or not
 * understood taken from FIRST_SETTINGS.
 * @returns {NotificationSettings}
 */
function notificationSettings() {
  const { show, sound, corner } = keptSettings();
  return {
    show: typeof show === "boolean" ? show : FIRST_SETTINGS.show,
    sound: typeof sound === "boolean" ? sound : FIRST_SETTINGS.sound,
    corner: typeof corner === "string" && CORNERS.includes(corner)
      ? corner : FIRST_SETTINGS.corner,
  };
}

/**
 * Changes how notifications reach this browser, keeps it, and applies it.
 * @param {Partial<NotificationSettings>} changes
 */
function changeNotificationSettings(changes) {
  const settings = { ...notificationSettings(), ...changes };
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    /* A browser that refuses to store it keeps the change for this visit. */
  }
  applyTheNotificationSettings(settings);
}

/**
 * Shows or hides the stack and puts it in its corner.
 * @param {NotificationSettings} [settings] - What to apply, the kept ones
 *   where this is left out.
 *
 * Hidden rather than emptied, so the notifications standing stay known and
 * come back as they are when they are shown again.
 */
function applyTheNotificationSettings(settings = notificationSettings()) {
  const stack = theStack();
  if (!stack) return;
  stack.hidden = !settings.show;
  stack.setAttribute("corner", settings.corner);
}

/** Plays the chime once. A browser that has not been clicked on yet refuses
 *  sound, and that refusal is the browser's to make, so it is not reported. */
function chime() {
  new Audio(CHIME).play().catch(() => {});
}

/**
 * One notification in words.
 * @param {NotificationEntry} said
 * @returns {{headline: string, message: string}}
 *
 * Every value the service sends is put into words here rather than there,
 * because how a version, a size or a moment is written is a question about
 * the language being read.
 */
function wordsFor(said) {
  const values = said.values;
  const key = `notification.${said.name}`;
  switch (said.name) {
    case "update":
      return {
        headline: t(`${key}.headline`, { version: released(String(values.version)) }),
        message: t(`${key}.message`, { installed: released(String(values.installed)) }),
      };
    case "disk":
      return {
        headline: t(`${key}.headline`, values),
        message: t(`${key}.message`, { free: sized(Number(values.free_mb) * 1024 * 1024) }),
      };
    case "crash":
      return {
        headline: t(`${key}.headline`),
        message: t(`${key}.message`, { count: values.count, at: when(Number(values.last)) },
                   Number(values.count)),
      };
    default:
      return { headline: t(`${key}.headline`, values), message: t(`${key}.message`, values) };
  }
}

/**
 * Draws what the Pi said.
 * @param {NotificationEntry[]} notifications
 *
 * A notification somebody closed stays closed for as long as its reading is
 * the one it was closed with. One whose condition has gone is taken away, and
 * what was remembered about closing it goes too, so the next time the
 * condition comes it is said again.
 */
function drawTheNotifications(notifications) {
  lastSaid = notifications;
  const stack = theStack();
  if (!stack) return;

  const kept = closed();
  const now = new Set(notifications.map((said) => said.name));
  for (const name of Object.keys(kept)) {
    if (!now.has(name)) delete kept[name];
  }
  keepClosed(kept);

  for (const name of stack.names) {
    if (!now.has(name)) stack.withdraw(name);
  }
  const standing = new Set(stack.names);
  let appeared = false;
  for (const said of notifications) {
    if (kept[said.name] === said.reading) {
      stack.withdraw(said.name);
      continue;
    }
    appeared ||= !standing.has(said.name);
    stack.post(said.name, { art: ART[said.level] ?? ART.info, ...wordsFor(said) });
  }

  /* Once for however many appeared together, and never for one that only
     stays or is drawn again in another language. */
  const settings = notificationSettings();
  if (appeared && settings.show && settings.sound) chime();
}

/** Draws the last list again, for a change of language. */
function redrawTheNotifications() {
  drawTheNotifications(lastSaid);
}

/** Asks the Pi what is worth saying, and draws it. No contact keeps what is
 *  standing, because a Pi that does not answer for a moment has not changed. */
async function refreshTheNotifications() {
  const answer = await ask(NOTIFICATIONS);
  if (answer) drawTheNotifications(answer.notifications);
}

/**
 * Remembers that a notification was dealt with, by opening it or by closing
 * it, at the reading it carried.
 * @param {string} name
 */
function dealtWith(name) {
  const said = lastSaid.find((entry) => entry.name === name);
  if (!said) return;
  keepClosed({ ...closed(), [name]: said.reading });
}

/** Wires the stack and starts asking. */
function wireTheNotifications() {
  const stack = theStack();
  if (!stack) return;

  stack.addEventListener("nx-notification-open", (event) => {
    const name = /** @type {CustomEvent<{name: string}>} */ (event).detail.name;
    dealtWith(name);
    theWindow(OPENS[name] ?? "pi")?.open();
  });
  stack.addEventListener("nx-notification-close", (event) => {
    dealtWith(/** @type {CustomEvent<{name: string}>} */ (event).detail.name);
  });

  applyTheNotificationSettings();
  refreshTheNotifications();
  setInterval(refreshTheNotifications, POLL_MS);
}

export {
  CORNERS,
  changeNotificationSettings,
  drawTheNotifications,
  notificationSettings,
  redrawTheNotifications,
  refreshTheNotifications,
  wireTheNotifications,
};
