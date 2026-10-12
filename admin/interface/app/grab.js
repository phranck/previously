/* Grab, which takes a picture of the emulated screen.
 *
 * The picture is the machine's own framebuffer, taken at the moment it is
 * asked for. Nothing here polls: a screen that redrew itself every few seconds
 * would be a window that costs the emulator something for as long as it is
 * open, and what a person wants is to look now.
 */

import { byId, theWindow } from "./page.js";
import { askForPassword } from "./panels.js";
import { KEPT_HEADER } from "./service.js";
import { lastStatus } from "./status.js";
import { Needs, allowed, hold, holdTheControls } from "./system.js";
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
  const button = byId("shot-take", HTMLButtonElement);
  /* No screen to take while the emulator is down or being changed, and the
     note says which of the two it is. */
  if (!allowed(Needs.Screen, "shot-note")) return drawPicture("shot", null);

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
    /* Handed back to the system's state, which knows whether it may be pressed
       again, rather than simply switched on. */
    holdTheControls();
  }
}

/**
 * Puts a picture in the window, or says why there is none.
 * @param {Blob | null} picture - What the service answered with, or null.
 * @param {string | null} [name] - What the service filed it as.
 */
function showTheScreen(picture, name) {
  drawPicture("shot", picture, name);
  byId("shot-note").textContent = picture
    ? ""
    : t(lastStatus?.running === false ? "grab.idle" : "grab.failed");
}

/**
 * Draws a picture into a view, and releases the one it replaces.
 * @param {string} id - Which view, which is its element's id.
 * @param {Blob | null} picture - The picture, or null to empty the view.
 * @param {string | null} [name] - What it is called, for saving it later.
 *
 * One place, because two windows show a picture: Grab shows what it has just
 * taken and Preview shows one that was kept. A blob has to be released or the
 * browser holds every picture ever shown, and the only way to do that is to
 * remember the last one per view.
 */
function drawPicture(id, picture, name) {
  const view = byId(id);

  const before = shownPictures[id];
  if (before) URL.revokeObjectURL(before.url);
  const shown = picture ? { url: URL.createObjectURL(picture), name } : null;
  shownPictures[id] = shown;
  view.style.backgroundImage = shown ? `url("${shown.url}")` : "";
}

/** What each picture view is showing and what it is called, so it can be
 *  released when it is replaced and saved while it is up.
 *  @type {Record<string, {url: string, name: string | null | undefined} | null>} */
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

/** Wires the window that shows the emulated screen. */
function wireGrab() {
  const window_ = theWindow("grab");
  if (!window_) return;
  const button = byId("shot-take", HTMLButtonElement);

  hold("#shot-take", Needs.Screen);
  hold('nx-menu-item[name="grab-take"]', Needs.Screen);
  button.addEventListener("click", takeAPicture);
  /* Opening it takes one straight away, because an empty window would ask
     somebody to press a button to find out what they opened it for. */
  window_.addEventListener("nx-open", takeAPicture);
  window_.addEventListener("nx-close", () => showTheScreen(null));
  if (!window_.hidden) takeAPicture();
}

export {
  takeAPicture,
  drawPicture,
  shownPictures,
  saveThePicture,
  wireGrab,
};
