/* Grab, which takes a picture of the emulated screen. */

import { theWindow } from "./page.js";
import { askForPassword } from "./panels.js";
import { KEPT_HEADER } from "./service.js";
import { lastStatus } from "./status.js";
import { drawMachines } from "./viewer.js";
import { t } from "../strings.js";

/**
 * Takes a picture of the emulated screen and puts it in the window.
 *
 * Fetched as a blob rather than pointed at, so that a refusal can be answered
 * by asking for the password rather than by drawing a broken picture. The last
 * one is released when the next arrives, so a window left open all day holds
 * one picture rather than all of them.
 */
async function takeAPicture() {
  const view = /** @type {any} */ (document.getElementById("shot"));
  const button = /** @type {any} */ (document.getElementById("shot-take"));
  if (!view) return;

  button.disabled = true;
  try {
    const answer = await fetch("/api/screen", { cache: "no-store" });
    if (answer.status === 403) return askForPassword(t("ask.password.needed"));
    if (!answer.ok) return showTheScreen(null);
    const filed = answer.headers.get(KEPT_HEADER);
    showTheScreen(await answer.blob(), filed);
    /* It was filed as well as shown, so the folder it went into has one more
       thing in it than the viewer is drawing. */
    if (filed) drawMachines();
  } catch {
    showTheScreen(null);
  } finally {
    button.disabled = false;
  }
}

/**
 * Puts a picture in the window, or says why there is none.
 * @param {Blob} picture - What the service answered with, or null.
 * @param {string} [name] - What the service filed it as.
 */
function showTheScreen(picture, name) {
  drawPicture("shot", picture, name);
  /** @type {any} */ (document.getElementById("shot-note")).textContent = picture
    ? ""
    : t(lastStatus?.running === false ? "grab.idle" : "grab.failed");
}

/**
 * Draws a picture into a view, and releases the one it replaces.
 * @param {string} id - Which view, which is its element's id.
 * @param {Blob} picture - The picture, or null to empty the view.
 * @param {string} [name] - What it is called, for saving it later.
 *
 * One place, because two windows show a picture: Grab shows what it has just
 * taken and Preview shows one that was kept. A blob has to be released or the
 * browser holds every picture ever shown, and the only way to do that is to
 * remember the last one per view.
 */
function drawPicture(id, picture, name) {
  const view = /** @type {any} */ (document.getElementById(id));
  if (!view) return;

  if (shownPictures[id]) URL.revokeObjectURL(shownPictures[id].url);
  shownPictures[id] = picture
    ? { url: URL.createObjectURL(picture), name }
    : null;
  view.style.backgroundImage = shownPictures[id]
    ? `url("${shownPictures[id].url}")` : "";
}

/** What each picture view is showing and what it is called, so it can be
 *  released when it is replaced and saved whilst it is up. */
const shownPictures = {};

/**
 * Hands the picture a window is showing to the browser to save.
 * @param {string} id - Which view is showing it.
 *
 * The picture is already here, so this is a link to what is in memory rather
 * than a second request: nothing is fetched and the service is not asked
 * again.
 */
function saveThePicture(id) {
  const showing = shownPictures[id];
  if (!showing) return;

  const link = document.createElement("a");
  link.href = showing.url;
  link.download = showing.name ?? "Screen.png";
  link.click();
}

/* --- the menu belongs to whatever is in front -----------------------------

   NeXTSTEP had one menu, in one place, whose title and entries were replaced
   when another application became active. Read off the running system: the
   Workspace's menu is titled Workspace and holds ten entries, and Preferences'
   is titled Preferences and holds five, of which Info, Ausblenden and
   Verlassen are the ones every application has.

   Here an application is a window, so the front window decides. A window that
   is not an application's, which is the Info window, the Raspberry Pi window
   and the File Viewer, leaves the workspace's own menu standing: under
   NeXTSTEP those are the Workspace's own windows too. */

/** Wires the window that shows the emulated screen. */
function wireGrab() {
  const window_ = theWindow("grab");
  const button = /** @type {any} */ (document.getElementById("shot-take"));
  if (!window_ || !button) return;

  button.addEventListener("click", takeAPicture);
  /* Opening it takes one straight away, because an empty window would ask
     somebody to press a button to find out what they opened it for. */
  window_.addEventListener("nx-open", takeAPicture);
  window_.addEventListener("nx-close", () => showTheScreen(null));
  if (!window_.hidden) takeAPicture();
}

/* --- the Installer --------------------------------------------------------

   What NeXT called the application that puts things on a machine and takes
   them off again. Here there are two kinds of thing: the emulator, which is a
   package and a handful of steps around it, and a system, which is a two
   gigabyte disk that arrives as an archive of a few tens of megabytes.

   The work is none of this window's. It asks the service, the service leaves a
   request, and a program running as root does it and says how far it has got.
   So what is drawn here comes from the Pi on every look, and a reload shows
   the same thing a moment later. */

export {
  takeAPicture,
  drawPicture,
  shownPictures,
  saveThePicture,
  wireGrab,
};
