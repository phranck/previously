/* Preferences: the language, the size, how notifications reach this browser,
   whether the Pi looks for updates on its own, and the software catalog. */

import { LANGUAGE_NAMES, currentLanguage, setLanguage, t, writeWords } from "../strings.js";
import { redrawActivity } from "./activity.js";
import { redrawTheEditor } from "./editor.js";
import { drawTheInstaller, drawTheTabs, setupState } from "./installer.js";
import { drawTheMenu } from "./menu.js";
import { changeNotificationSettings, notificationSettings, redrawTheNotifications,
         refreshTheNotifications } from "./notifications.js";
import { ask, tell } from "./service.js";
import { byId } from "./page.js";
import { showTheNotesAgain } from "./preview.js";
import { drawSizes } from "./size.js";
import { drawTheSoftware, refreshTheSoftware, wireTheSoftware } from "./software.js";
import { refresh } from "./status.js";
import { drawPlace } from "./viewer.js";

/**
 * Draws the languages this tool speaks, with the one in force marked.
 *
 * Each is named in its own language, because a language named in a language
 * one cannot read is no help to whoever is looking for theirs. The order is
 * the catalog's own, so it does not move about as the interface changes.
 */
function drawLanguages() {
  const list = byId("languages");
  list.replaceChildren(...Object.entries(LANGUAGE_NAMES).map(([code, name]) => {
    const option = document.createElement("div");
    option.className = "option";
    option.textContent = name;
    option.toggleAttribute("chosen", code === currentLanguage());
    option.addEventListener("click", () => speak(code));
    return option;
  }));
}

/** What each module of Preferences is called and which panel it shows.
 *  @type {Record<string, {name: string, panel: string}>} */
const MODULES = {
  localization: { name: "preferences.localization", panel: "languages-page" },
  monitor: { name: "preferences.monitor", panel: "sizes" },
  notifications: { name: "preferences.notifications", panel: "notifications-page" },
  updates: { name: "preferences.updates", panel: "updates-page" },
  software: { name: "preferences.software", panel: "software-page" },
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
    byId(one.panel).hidden = name !== which;
  }
  writeWords(byId("module-name"), t(module.name));
  /* The catalog is the Pi's and can change from another browser, so it is
     asked for each time its module comes up. */
  if (which === "software") refreshTheSoftware();
}

/**
 * Sets the Notifications module's switches and radio buttons from what this
 * browser keeps, and wires them to keep what is changed.
 *
 * A change takes effect at once, on the stack beside the dock, which is the
 * direct effect the Controls chapter asks a control to have.
 */
function wireNotificationSettings() {
  const show = byId("notifications-show", HTMLInputElement);
  const sound = byId("notifications-sound", HTMLInputElement);
  const corners = byId("notifications-corner");
  const settings = notificationSettings();

  show.checked = settings.show;
  sound.checked = settings.sound;
  for (const radio of corners.querySelectorAll("input")) {
    if (radio instanceof HTMLInputElement) radio.checked = radio.value === settings.corner;
  }

  show.addEventListener("change", () => changeNotificationSettings({ show: show.checked }));
  sound.addEventListener("change", () => changeNotificationSettings({ sound: sound.checked }));
  corners.addEventListener("change", (event) => {
    if (event.target instanceof HTMLInputElement) {
      changeNotificationSettings({ corner: event.target.value });
    }
  });
}

/** How long after Check Now the notifications are asked again. The Pi asks
 *  GitHub and the archive in a thread and answers at once, and either answer
 *  is back well within this on a working network. */
const LOOKED_MS = 5000;

/**
 * Shows whether the Pi looks for updates on its own: the radio button that is
 * in force, and Check Now usable only while it looks manually.
 * @param {boolean | null} automatic - What the Pi said, or null where it did
 *   not answer, which leaves the page as it stands.
 */
function drawUpdateSettings(automatic) {
  if (automatic === null) return;
  for (const radio of document.querySelectorAll('input[name="updates-mode"]')) {
    if (radio instanceof HTMLInputElement) {
      radio.checked = radio.value === (automatic ? "automatic" : "manual");
    }
  }
  byId("updates-look", HTMLButtonElement).disabled = automatic;
}

/** Asks the Pi how it looks for updates, and shows it. */
async function refreshUpdateSettings() {
  const answer = await ask("/api/updates");
  drawUpdateSettings(answer ? answer.automatic : null);
}

/**
 * Wires the Updates module: choosing a radio button tells the Pi, and Update
 * Now has it look once.
 *
 * A choice the Pi refused, for want of the password or otherwise, is drawn
 * back to what the Pi holds, so the page never shows a choice that is not in
 * force.
 */
function wireUpdateSettings() {
  const modes = byId("updates-page");
  modes.addEventListener("change", async (event) => {
    if (!(event.target instanceof HTMLInputElement) || event.target.name !== "updates-mode") return;
    const answer = await tell("/api/updates", { automatic: event.target.value === "automatic" });
    if (answer && "automatic" in answer) drawUpdateSettings(answer.automatic);
    else await refreshUpdateSettings();
  });
  byId("updates-look", HTMLButtonElement).addEventListener("click", async () => {
    await tell("/api/updates/look");
    setTimeout(refreshTheNotifications, LOOKED_MS);
  });
  refreshUpdateSettings();
}

/** Wires the row of modules, and draws the one that starts up chosen. */
function wirePreferences() {
  const row = document.querySelector("nx-window[name='preferences'] .modules");
  if (!row) return;

  row.addEventListener("click", (event) => {
    const cell = event.target instanceof Element ? event.target.closest(".module") : null;
    if (cell) showModule(cell.getAttribute("value") ?? "");
  });
  showModule("localization");
  drawSizes();
  wireNotificationSettings();
  wireUpdateSettings();
  wireTheSoftware();
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
    /* Activity Monitor names its cores itself, one row per core the board
       has, so its last reading is drawn again rather than waiting for the
       next. */
    redrawActivity();
    /* Release notes come from the service in one language at a time. */
    showTheNotesAgain();
    /* The notifications are put into words here from the last list the Pi
       sent, so they are drawn again rather than waiting for the next. */
    redrawTheNotifications();
    /* A removed entry says so in words, so the list is drawn again. */
    drawTheSoftware();
  });
}

export {
  drawLanguages,
  wirePreferences,
};
