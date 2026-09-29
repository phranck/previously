/* The one menu, which belongs to whatever window is in front. */

import { showWhatThisIs } from "./about.js";
import { applications } from "./dock.js";
import { saveThePicture, shownPictures, takeAPicture } from "./grab.js";
import { deleteThePicture } from "./preview.js";
import { appName } from "./viewer.js";

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

export {
  applicationWindows,
  drawTheMenu,
  WORKSPACE,
  watchTheFrontWindow,
};
