/* Which applications are in the dock and which are running, and their icons
   on the floor. */

import { NxDock, NxFloor } from "../nextstep.js";
import { t, writeTitle } from "../strings.js";
import { readPaths, writeDown } from "./kept.js";
import { byId, targetName, theWindow } from "./page.js";
import { find, open, root } from "./viewer.js";

/** @typedef {import("../answers.js").ApplicationEntry} ApplicationEntry */
/** @typedef {import("../nextstep.js").DeskRect} DeskRect */

/** Where the applications somebody put in the dock are kept between visits.
 *  Which they are is one person's arrangement rather than the Pi's, so it
 *  stays in this browser, as the shelf's contents do. */
const DOCKED_KEY = "previously:docked";

/** What is in the dock before anybody has changed it. */
const DOCKED_BY_DEFAULT = ["/Apps/Config Editor.app"];

/** @returns {string[]} The applications in the dock, by their paths, in the
 *  order they were put there. Read where they are kept every time, so there
 *  is no second copy to disagree with it. */
function docked() {
  return readPaths(DOCKED_KEY, DOCKED_BY_DEFAULT);
}

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
 * One application's tile in the dock.
 * @param {ApplicationEntry} application - What it stands for.
 * @returns {HTMLElement} The tile, ready to be taken into the column.
 *
 * Named by the window it opens, because that is what the dock remembers its
 * place under. A double click starts it the way a double click in the File
 * Viewer does, so the Config Editor opens on the machine that is set however
 * it is started.
 */
function dockTile(application) {
  const tile = document.createElement("nx-tile");
  tile.setAttribute("icon", application.icon);
  tile.setAttribute("value", application.path);
  tile.setAttribute("name", application.opens);
  tile.dataset.tTitle = application.label;
  writeTitle(tile, t(application.label));
  tile.addEventListener("dblclick", () => open(application.path, tile));
  return tile;
}

/**
 * Puts a tile in the dock for every docked application that has none yet.
 *
 * The tiles come from the tree, because that is where an application's
 * picture and name are. Until the tree has arrived there is nothing to draw,
 * and an application the tree no longer holds stays in the list without a
 * tile, the way a folder that is gone stays off the shelf.
 */
function drawTheDock() {
  const dock = byId("dock", NxDock);
  const paths = docked();
  for (const application of applications()) {
    if (paths.includes(application.path) && !dock.holds(application.path)) {
      dock.take(dockTile(application));
    }
  }
}

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
  const inTheDock = [...document.querySelectorAll("nx-dock nx-tile[value]")];
  for (const tile of inTheDock) {
    const application = applications().find((entry) => entry.path === tile.getAttribute("value"));
    tile.toggleAttribute("idle", application !== undefined && !isRunning(application));
  }

  const tiled = new Set(inTheDock.map((tile) => tile.getAttribute("value")));
  const standing = applications()
    .filter((application) => !tiled.has(application.path) && isRunning(application))
    /* The order they were started in, which is the order they arrived in the
       list this keeps. */
    .sort((one, other) => started.indexOf(one.path) - started.indexOf(other.path))
    .map((application) => ({
      icon: application.icon, opens: application.opens, value: application.path,
    }));
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
  drawTheDock();
  drawWhatIsRunning(arriving && from ? { opens: arriving.opens, from } : undefined);
}

/**
 * Puts an application into the dock, where something standing for it was let
 * go over a free slot.
 * @param {DocumentEventMap["nx-dock"]} event - What it stands for, and the slot.
 *
 * Anything that is not an application this tool holds is not taken, and one
 * that is in the dock already keeps the tile it has.
 */
function putIntoTheDock(event) {
  const { value, slot } = event.detail;
  const application = applications().find((entry) => entry.path === value);
  const paths = docked();
  if (!application || paths.includes(application.path)) return;

  writeDown(DOCKED_KEY, [...paths, application.path]);
  byId("dock", NxDock).take(dockTile(application), slot);
  drawWhatIsRunning();
}

/**
 * Forgets an application whose tile was carried out of the dock.
 * @param {DocumentEventMap["nx-undock"]} event - What the tile stood for.
 *
 * One that is running stands on the floor from then on, because it is
 * running and no longer in the dock.
 */
function takeOutOfTheDock(event) {
  writeDown(DOCKED_KEY, docked().filter((path) => path !== event.detail.value));
  drawWhatIsRunning();
}

/** Listens for a window opening or closing, which is what starting and
 *  stopping an application is here, and for the dock gaining or losing one.
 *  Wired once. */
function watchTheApplications() {
  document.addEventListener("nx-open", noticeTheApplications);
  document.addEventListener("nx-close", noticeTheApplications);
  document.addEventListener("nx-dock", putIntoTheDock);
  document.addEventListener("nx-undock", takeOutOfTheDock);
  noticeTheApplications();
}

export {
  applications,
  noticeTheApplications,
  watchTheApplications,
};
