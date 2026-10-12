/* Which applications are running, and their icons on the floor. */

import { NxFloor } from "../nextstep.js";
import { byId, targetName, theWindow } from "./page.js";
import { find, root } from "./viewer.js";

/** @typedef {import("../answers.js").ApplicationEntry} ApplicationEntry */
/** @typedef {import("../nextstep.js").DeskRect} DeskRect */

/**
 * Every application this tool holds, as the tree gives them.
 * @returns {ApplicationEntry[]} Each with its path, its picture and the window
 *   it opens.
 */
function applications() {
  const apps = find(root, "/Apps");
  return apps?.kind === "folder"
    ? apps.entries.filter((entry) => entry.kind === "application")
    : [];
}

/**
 * Whether an application is running, which here is its window being open.
 * @param {ApplicationEntry} application - An entry of the Apps folder.
 * @returns {boolean}
 *
 * In NeXTSTEP an application outlives its windows. Here it does not: the
 * window is the application, so closing it is quitting, and saying otherwise
 * would be a light that means nothing.
 */
function isRunning(application) {
  const window_ = theWindow(application.opens);
  return window_ !== null && !window_.hidden;
}

/** Which applications are running, by their paths, oldest first, so their
 *  icons keep the places they took when they started.
 *  @type {string[]} */
let started = [];

/**
 * Draws which applications are running and where their icons go.
 * @param {{opens: string, from: DeskRect}} [arriving] - The application that
 *   has just started, by the window it opens, and where its icon comes from.
 *
 * A tile in the dock carries the three marks while its application is not
 * running and loses them when it is, which is what NeXTSTEP's dock did. An
 * application that is running and is not in the dock stands on the floor of
 * the screen instead, from the left corner rightwards.
 */
function drawWhatIsRunning(arriving) {
  const docked = [...document.querySelectorAll("nx-dock nx-tile[app]")];
  for (const tile of docked) {
    const application = applications().find((entry) => entry.path === tile.getAttribute("app"));
    tile.toggleAttribute("idle", application !== undefined && !isRunning(application));
  }

  const inTheDock = new Set(docked.map((tile) => tile.getAttribute("app")));
  const standing = applications()
    .filter((application) => !inTheDock.has(application.path) && isRunning(application))
    /* The order they were started in, which is the order they arrived in the
       list this keeps. */
    .sort((one, other) => started.indexOf(one.path) - started.indexOf(other.path));
  byId("floor", NxFloor).show(standing, arriving);
}

/**
 * Reads which applications are running now and draws them.
 * @param {DocumentEventMap["nx-open"] | DocumentEventMap["nx-close"]} [event] -
 *   The window opening or closing that prompted this, which is what says where
 *   a newly started application is coming from.
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

  /* Only an opening says where it came from. A closing carries nothing, so
     nothing arrives. */
  const from = event?.detail?.from;
  const reached = event ? targetName(event.target) : null;
  const arriving = applications().find((entry) => entry.opens === reached);
  drawWhatIsRunning(arriving && from ? { opens: arriving.opens, from } : undefined);
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
