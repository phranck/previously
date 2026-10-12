/* The one menu, which belongs to whatever window is in front.
 *
 * NeXTSTEP had one menu, in one place, whose title and entries were replaced
 * when another application became active. Read off the running system: the
 * Workspace's menu is titled Workspace and holds ten entries, and Preferences'
 * is titled Preferences and holds five, of which Info, Ausblenden and
 * Verlassen are the ones every application has.
 *
 * Here an application is a window, so the front window decides. A window that
 * is not an application's, which is the Info window, the Raspberry Pi window
 * and the File Viewer, leaves the workspace's own menu standing: under
 * NeXTSTEP those are the Workspace's own windows too.
 */

import { showWhatThisIs } from "./about.js";
import { applications } from "./dock.js";
import { saveThePicture, shownPictures, takeAPicture } from "./grab.js";
import { theMenu, theWindow } from "./page.js";
import { deleteThePicture } from "./preview.js";
import { Needs, hold } from "./system.js";
import { appName } from "./viewer.js";

/** @typedef {import("../nextstep.js").NxWindow} NxWindow */

/**
 * Puts the menu of whatever is in front into the one menu there is.
 * @param {string} [front] - The name of the window that came forward. Left
 *   out, whichever window is in front now is asked.
 */
function drawTheMenu(front) {
  const menu = theMenu("menu");
  /* The menu can be asked for before the kit has built it, and then it cannot
     show anything yet. */
  if (typeof menu?.showFor !== "function") return;

  const name = front ?? /** @type {NxWindow | null} */ (
    document.querySelector("nx-window:not([inactive]):not([hidden])"))?.name;
  const application = applications().find((entry) => entry.opens === name);
  menu.showFor(application?.opens ?? "",
               application ? appName(application) : WORKSPACE);
}

/** What the workspace's own menu is called. NeXTSTEP's own name for it, and
 *  not translated anywhere, the way the applications' names are not: this menu
 *  belongs to the desk rather than to any machine, and it is there whether one
 *  is installed or not. */
const WORKSPACE = "Workspace";

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
      if (owner) theWindow(owner)?.close();
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
  /* Taking a picture away touches neither the machine nor the board, so it
     needs the service and nothing more. */
  hold('nx-menu-item[name="preview-delete"]', Needs.Contact);
  const deleting = document.querySelector('nx-menu-item[name="preview-delete"]');
  deleting?.addEventListener("click", async () => {
    if (deleting.hasAttribute("disabled")) return;
    const showing = shownPictures["preview-picture"];
    if (!showing?.name) return;
    /* The window goes with the picture, because a window showing something
       that is no longer there is worse than no window. */
    if (await deleteThePicture(showing.name)) {
      theWindow("preview")?.close();
    }
  });

  drawTheMenu();
}

export {
  drawTheMenu,
  watchTheFrontWindow,
};
