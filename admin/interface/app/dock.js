/* Which applications are running, and their icons on the floor. */

import { theWindow } from "./page.js";
import { find, root } from "./viewer.js";

/**
 * Every application this tool holds, as the tree gives them.
 * @returns {any[]} Each with its path, its picture and the window it opens.
 */
function applications() {
  const apps = find(root, "/Apps");
  return (apps?.entries ?? []).filter((entry) => entry.kind === "application");
}

/**
 * Whether an application is running, which here is its window being open.
 * @param {any} application - An entry of the Apps folder.
 * @returns {boolean}
 *
 * In NeXTSTEP an application outlives its windows. Here it does not: the
 * window is the application, so closing it is quitting, and saying otherwise
 * would be a light that means nothing.
 */
function isRunning(application) {
  const window_ = theWindow(application.opens);
  return Boolean(window_) && !window_.hidden;
}

/** Which applications are running, oldest first, so their icons keep the
 *  places they took when they started. */
let started = [];

/**
 * Draws which applications are running and where their icons go.
 *
 * A tile in the dock carries the three marks whilst its application is not
 * running and loses them when it is, which is what NeXTSTEP's dock did. An
 * application that is running and is not in the dock stands on the floor of
 * the screen instead, from the left corner rightwards.
 */
function drawWhatIsRunning(arriving) {
  const docked = [...document.querySelectorAll("nx-dock nx-tile[app]")];
  for (const tile of docked) {
    const application = applications().find((entry) => entry.path === tile.getAttribute("app"));
    tile.toggleAttribute("idle", Boolean(application) && !isRunning(application));
  }

  const inTheDock = new Set(docked.map((tile) => tile.getAttribute("app")));
  const standing = applications()
    .filter((application) => !inTheDock.has(application.path) && isRunning(application))
    /* The order they were started in, which is the order they arrived in the
       list this keeps. */
    .sort((one, other) => started.indexOf(one.path) - started.indexOf(other.path));
  /** @type {any} */ (document.getElementById("floor"))?.show(standing, arriving);
}

/**
 * Reads which applications are running now and draws them.
 * @param {CustomEvent} [event] - The window opening or closing that prompted
 *   this, which is what says where a newly started application is coming
 *   from.
 *
 * A window that opens or closes is an application starting or stopping, and
 * an application that has just started takes the next place on the floor. Its
 * icon travels there from whatever was used to start it, which the window
 * carries along from whoever opened it.
 */
function noticeTheApplications(event) {
  for (const application of applications()) {
    const running = isRunning(application);
    const known = started.includes(application.path);
    if (running && !known) started.push(application.path);
    if (!running && known) started = started.filter((path) => path !== application.path);
  }

  const reached = /** @type {any} */ (event?.target);
  const opened = event?.type === "nx-open" ? reached.getAttribute?.("name") : null;
  const arriving = applications().find((entry) => entry.opens === opened);
  drawWhatIsRunning(arriving && event.detail?.from
    ? { opens: arriving.opens, from: event.detail.from }
    : null);
}

/** Listens for a window opening or closing, which is what starting and
 *  stopping an application is here. Wired once. */
function watchTheApplications() {
  document.addEventListener("nx-open", noticeTheApplications);
  document.addEventListener("nx-close", noticeTheApplications);
  noticeTheApplications();
}

export {
  applications,
  noticeTheApplications,
  watchTheApplications,
};
