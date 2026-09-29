/* Preferences, which is the size, the language and nothing else. */

import { LANGUAGE_NAMES, currentLanguage, setLanguage, t, writeWords } from "../strings.js";
import { redrawTheEditor } from "./editor.js";
import { drawTheInstaller, drawTheTabs, setupState } from "./installer.js";
import { drawTheMenu } from "./menu.js";
import { drawSizes } from "./size.js";
import { refresh } from "./status.js";
import { drawPlace } from "./viewer.js";

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

export {
  drawLanguages,
  wirePreferences,
};
