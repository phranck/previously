/* Preview, which shows a document and knows nothing about what is in one.
 *
 * The window opens, takes the document's name as its title and hands the room
 * to whichever renderer takes that kind of document. It does no fetching, no
 * drawing and no clearing of its own: a renderer owns the part of the window it
 * fills, and adding a third kind is adding an entry to the table below rather
 * than a branch to anything here.
 *
 * That is `nx-viewer`'s shape as well, which is handed a path, contents and a
 * shelf and knows nothing about machines. A window that knew both its kinds
 * would have three special cases by the third one.
 */

import { t } from "../strings.js";
import { drawPicture } from "./grab.js";
import { render } from "./markdown.js";
import { askForPassword, askPanel } from "./panels.js";
import { ask, tell } from "./service.js";
import { drawMachines, find, root } from "./viewer.js";
import { Art } from "./words.js";

/**
 * What Preview can show, one entry per kind of document.
 *
 * Each names the part of the window it fills and says how to fill it and how to
 * empty it again. A document is whatever its own kind needs: a picture carries
 * a name and is fetched, and notes carry their text and are not.
 *
 * `show` answers with what to say under the window where there is anything, and
 * with nothing where the document arrived whole.
 */
const RENDERERS = {
  picture: {
    room: "preview-picture",

    /**
     * @param {any} document_ - What the tree says about a kept picture.
     * @returns {Promise<string>} What to say under it, or "".
     *
     * Fetched rather than pointed at, for the same reason Grab fetches its own:
     * a refusal is answered by asking for the password.
     */
    async show(document_) {
      try {
        const answer = await fetch(
          "/api/picture?name=" + encodeURIComponent(document_.name),
          { cache: "no-store" });
        if (answer.status === 403) {
          askForPassword(t("ask.password.needed"));
          return "";
        }
        if (!answer.ok) return t("preview.empty");
        drawPicture("preview-picture", await answer.blob(), document_.name);
        return "";
      } catch {
        return t("preview.empty");
      }
    },

    clear() {
      drawPicture("preview-picture", null);
    },
  },

  notes: {
    room: "preview-document",

    /**
     * @param {any} document_ - Carrying `notes` as the Markdown they were
     *   written in.
     * @returns {Promise<string>} What to say where there are none.
     *
     * Turned into elements rather than into markup, which `markdown.js` is
     * what does: the text comes off a network and nothing built here is ever a
     * string of markup.
     */
    async show(document_) {
      if (!document_.notes) return t("preview.no-notes");
      document.getElementById("preview-document").append(render(document_.notes));
      return "";
    },

    clear() {
      document.getElementById("preview-document").replaceChildren();
    },
  },
};

/**
 * Shows one document in Preview.
 * @param {any} document_ - What it is, carrying at least `kind` and `name`.
 *
 * Every renderer is emptied and every room but one is taken away, so a window
 * that showed a picture and is given notes is not a window showing both.
 */
async function showInPreview(document_) {
  const window_ = /** @type {any} */ (document.querySelector('nx-window[name="preview"]'));
  const renderer = RENDERERS[document_.kind];
  if (!window_ || !renderer) return;

  emptyThePreview(document_.kind);
  window_.rename(document_.name);
  window_.open();

  /* The scroller takes its bar from one element, which is its first child
     unless it is told otherwise, and this window has a room per kind of
     document. Without this the bar measures whichever room happens to be
     first: notes in a window whose picture room is empty scroll to the wheel
     and show no bar at all, which is what they did. */
  /** @type {any} */ (window_.querySelector("nx-scroller"))
    .drive(document.getElementById(renderer.room));

  /** @type {any} */ (document.getElementById("preview-note")).textContent =
    await renderer.show(document_);
}

/**
 * Empties every renderer and leaves one room showing.
 * @param {string} [kind] - Which one stays, or nothing for none of them, which
 *   is what closing the window wants.
 */
function emptyThePreview(kind) {
  for (const [name, renderer] of Object.entries(RENDERERS)) {
    renderer.clear();
    /** @type {any} */ (document.getElementById(renderer.room)).hidden =
      name !== kind;
  }
}

/**
 * Opens the notes of whichever release is published.
 *
 * Its own address rather than a field of the answer the Raspberry Pi window
 * polls, because that one is asked every two seconds and these are thousands of
 * characters asked for when somebody presses a button.
 */
async function showTheReleaseNotes() {
  const answer = await ask("/api/update/notes");
  showInPreview({
    kind: "notes",
    name: t("preview.notes.title", { version: answer?.version ?? "" }).trim(),
    notes: answer?.notes ?? "",
  });
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
    name: t("ask.delete.title", { name }),
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

  const menu = /** @type {any} */ (document.querySelector('nx-menu[name="picture-menu"]'));
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
    ?.addEventListener("nx-close", () => emptyThePreview());
}

export {
  RENDERERS,
  showInPreview,
  showTheReleaseNotes,
  deleteThePicture,
  openPictureMenu,
  wirePreview,
};
