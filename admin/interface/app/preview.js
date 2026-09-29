/* Preview, which shows a picture that was taken and can throw it away. */

import { t } from "../strings.js";
import { drawPicture } from "./grab.js";
import { askForPassword, askPanel } from "./panels.js";
import { tell } from "./service.js";
import { drawMachines, find, root } from "./viewer.js";
import { Art } from "./words.js";

/**
 * Shows one kept picture in Preview.
 * @param {object} entry - What the tree says about it.
 *
 * Fetched rather than pointed at, for the same reason Grab fetches its own: a
 * refusal is answered by asking for the password. The window is titled with the
 * picture's name, the way a document window is.
 */
async function showInPreview(entry) {
  const window_ = document.querySelector('nx-window[name="preview"]');
  const note = document.getElementById("preview-note");
  if (!window_) return;

  window_.rename(entry.name);
  window_.open();
  drawPicture("preview-picture", null);
  note.textContent = "";

  try {
    const answer = await fetch(
      "/api/picture?name=" + encodeURIComponent(entry.name),
      { cache: "no-store" });
    if (answer.status === 403) return askForPassword(t("ask.password.needed"));
    if (!answer.ok) return void (note.textContent = t("preview.empty"));
    drawPicture("preview-picture", await answer.blob(), entry.name);
  } catch {
    note.textContent = t("preview.empty");
  }
}

/**
 * Asks whether a picture should go, and takes it away if so.
 * @param {string} name - What it is called in the Pictures folder.
 * @returns {Promise<boolean>} Whether it went.
 *
 * Asked first, because a picture that has gone does not come back and there
 * is no wastebasket here to fish it out of.
 */
async function deleteThePicture(name) {
  const sure = await askPanel({
    title: t("ask.delete.title", { name }),
    text: [t("ask.delete.loss")],
    icon: Art.Picture,
    confirm: t("button.delete"),
  });
  if (!sure) return false;

  const answer = await tell("/api/picture/delete", { name });
  if (!answer?.ok) return false;

  /* The folder has one thing fewer in it than the viewer is drawing, and a
     window showing what has gone is showing something that is not there. */
  drawMachines();
  return true;
}

/**
 * Offers what can be done to a picture, where one was right clicked.
 * @param {HTMLElement} thing - The icon under the pointer.
 * @param {number} x @param {number} y - Where the pointer was.
 * @returns {boolean} Whether this menu was the right one for what was clicked.
 *
 * Titled for the kind of thing rather than for the file, because a file's
 * name is as long as somebody made it and a menu bar is one row. Which file
 * this is about is said by where the menu stands and by the question that
 * follows it.
 */
function openPictureMenu(thing, x, y) {
  const where = thing.getAttribute("value");
  const entry = find(root, where);
  if (entry?.kind !== "picture") return false;

  const menu = document.querySelector('nx-menu[name="picture-menu"]');
  menu.querySelector('nx-menu-item[name="delete"]').onclick = async () => {
    menu.close();
    await deleteThePicture(entry.name);
  };
  menu.openAt(x, y);
  return true;
}

/** Wires Preview, which holds nothing of its own once it is closed. */
function wirePreview() {
  document.querySelector('nx-window[name="preview"]')
    ?.addEventListener("nx-close", () => drawPicture("preview-picture", null));
}

export {
  showInPreview,
  deleteThePicture,
  openPictureMenu,
  wirePreview,
};
