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

import { currentLanguage, t } from "../strings.js";
import { drawPicture } from "./grab.js";
import { render } from "./markdown.js";
import { wasTaken } from "./outcome.js";
import { byId, menuEntry, theMenu, theWindow } from "./page.js";
import { askForPassword, askPanel } from "./panels.js";
import { ask, tell } from "./service.js";
import { drawMachines, find, root } from "./viewer.js";
import { Art, released } from "./words.js";

/** @typedef {import("../answers.js").ReleaseRun} ReleaseRun */

/**
 * Something Preview shows. A picture is what the tree says about it, of which
 * the name is all that is read. Notes carry everything they show, because they
 * are not fetched again once they are here.
 * @typedef {object} PreviewDocument
 * @property {"picture" | "notes"} kind - Which renderer takes it.
 * @property {string} name - The window's title, and for a picture what it is
 *   called in the Pictures folder.
 * @property {string} [notes] - Notes only: the Markdown they were written in,
 *   "" where there are none.
 * @property {string | null} [version] - Notes only: the release they are of,
 *   or null where no release is known.
 * @property {ReleaseRun[]} [versions] - Notes only: every entry there is,
 *   newest first.
 * @property {string | null} [installed] - Notes only: what dpkg has of this
 *   tool, or null.
 * @property {string[]} [newer] - Notes only: the releases newer than that,
 *   newest first.
 * @property {boolean} [since] - Notes only: whether `notes` is the document
 *   of every release in `newer` rather than one release's.
 */

/**
 * How one kind of document is shown.
 * @typedef {object} Renderer
 * @property {string} room - The id of the part of the window it fills.
 * @property {(document_: PreviewDocument) => Promise<string>} show - Fills
 *   it, and answers with what to say under the window, or "".
 * @property {() => void} clear - Empties it again.
 */

/** Where Preview keeps what it is showing, so a reload comes back to it.
 *
 *  The desk remembers that a window was open and where it stood, and nothing
 *  else: what is inside one belongs to whatever fills it. Every other part of
 *  this interface that outlives a reload keeps its own key the same way, which
 *  is what the chosen size, the shelf and the language do.
 *
 *  What is kept is the document rather than what it turned into, so coming back
 *  to it fetches the picture again and asks for the notes of whichever release
 *  is published now. A window that reopened onto a copy of yesterday's answer
 *  would be a window saying something nothing else on the desk says. */
const SHOWING_KEY = "previously.preview";

/**
 * What Preview can show, one entry per kind of document.
 *
 * Each names the part of the window it fills and says how to fill it and how to
 * empty it again. A document is whatever its own kind needs: a picture carries
 * a name and is fetched, and notes carry their text and are not.
 *
 * `show` answers with what to say under the window where there is anything, and
 * with nothing where the document arrived whole.
 *
 * @type {Record<PreviewDocument["kind"], Renderer>}
 */
const RENDERERS = {
  picture: {
    room: "preview-picture-view",

    /**
     * @param {PreviewDocument} document_ - What the tree says about a kept
     *   picture.
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
    room: "preview-notes",

    /**
     * @param {PreviewDocument} document_ - Carrying `notes`, `version`,
     *   `versions`, `installed`, `newer` and `since`.
     * @returns {Promise<string>} What to say where there are none.
     *
     * Turned into elements rather than into markup, which `markdown.js` is
     * what does: the text comes off a network and nothing built here is ever a
     * string of markup.
     *
     * The releases go into the list beside the notes, which is how somebody
     * reaches the notes of one before the newest, and how to update is said
     * once under both rather than in every release's own notes.
     */
    async show(document_) {
      drawTheReleases(document_);
      byId("preview-updating").hidden = false;

      if (!document_.notes) return t("preview.no-notes");
      byId("preview-document").append(render(document_.notes));
      return "";
    },

    clear() {
      byId("preview-document").replaceChildren();
      byId("preview-releases").replaceChildren();
      byId("preview-updating").hidden = true;
    },
  },
};

/**
 * Draws the list of releases beside the notes, with the one showing chosen.
 * @param {PreviewDocument} document_ - The notes being shown.
 *
 * Newest first, as the service lists them. An entry standing for several
 * releases whose notes are one page is named by the first and the last of
 * them and opens the notes of the last. Where a release newer than the
 * installed one is published, the list opens with an entry for everything
 * since the installed one, which is what the Raspberry Pi window opens on.
 * A list with a scroller rather than a pop-up, because it grows by one entry
 * per release, and that is how a set that can outgrow the window is offered.
 */
function drawTheReleases(document_) {
  const entries = [];
  if (document_.newer?.length) {
    entries.push({
      label: t("preview.since", { version: released(document_.installed) }),
      chosen: Boolean(document_.since),
      open: () => showTheReleaseNotes(null, true),
    });
  }
  for (const { first, last } of document_.versions ?? []) {
    entries.push({
      label: first === last ? last : t("preview.versions.run", { first, last }),
      chosen: !document_.since && last === document_.version,
      open: () => showTheReleaseNotes(last),
    });
  }
  byId("preview-releases").replaceChildren(...entries.map((entry) => {
    const row = document.createElement("div");
    row.className = "option";
    row.textContent = entry.label;
    row.toggleAttribute("chosen", entry.chosen);
    row.addEventListener("click", entry.open);
    return row;
  }));
}

/**
 * Shows one document in Preview.
 * @param {PreviewDocument} document_ - What it is.
 *
 * Every renderer is emptied and every room but one is taken away, so a window
 * that showed a picture and is given notes is not a window showing both.
 */
async function showInPreview(document_) {
  const window_ = theWindow("preview");
  if (!window_) return;
  const renderer = RENDERERS[document_.kind];

  emptyThePreview(document_.kind);
  window_.rename(document_.name);
  window_.open();
  /* With the release where it is notes, so a reload or a change of language
     comes back to the notes somebody chose rather than to the newest. */
  keepShowing({ kind: document_.kind, name: document_.name,
                version: document_.version, since: document_.since });

  byId("preview-note").textContent = await renderer.show(document_);
}

/**
 * Writes down what the window is showing, or forgets it.
 * @param {PreviewDocument | null} showing - The document, as its kind, its
 *   name and for notes its release, or null.
 */
function keepShowing(showing) {
  try {
    if (showing) localStorage.setItem(SHOWING_KEY, JSON.stringify(showing));
    else localStorage.removeItem(SHOWING_KEY);
  } catch {
    /* A browser that will not keep anything is one where Preview opens empty
       after a reload, which is worse than it was and is not worth failing the
       window somebody just opened. */
  }
}

/** @returns {PreviewDocument | null} What it was showing, or null. */
function whatItWasShowing() {
  try {
    /** @type {unknown} */
    const kept = JSON.parse(localStorage.getItem(SHOWING_KEY) ?? "null");
    return isADocument(kept) ? kept : null;
  } catch {
    return null;
  }
}

/**
 * Whether what this browser kept is a document Preview can show.
 * @param {unknown} kept - What was read back.
 * @returns {kept is PreviewDocument}
 *
 * Whatever is in the browser's storage was written by a version of this page
 * that may not be this one, so a kind no renderer takes anymore is not shown.
 */
function isADocument(kept) {
  return typeof kept === "object" && kept !== null
    && "kind" in kept && typeof kept.kind === "string" && Object.hasOwn(RENDERERS, kept.kind)
    && "name" in kept && typeof kept.name === "string";
}

/**
 * Puts back what Preview was showing, where it came back open.
 *
 * The desk restores a window's geometry and whether it was open, so a reload
 * with the notes up brought the window back with both rooms as the markup
 * leaves them, which is an empty picture room and a window showing nothing.
 * The Config Editor has the same hook for the same reason.
 *
 * The document is fetched again rather than kept, so what comes back is what
 * the Pi says now.
 */
function fillPreviewIfItCameBackOpen() {
  const window_ = theWindow("preview");
  if (!window_ || window_.hidden) return;

  const showing = whatItWasShowing();
  if (!showing) {
    /* Open with nothing to put in it, which is a browser that forgot or a
       first visit to a desk somebody left open. Saying so beats a blank. */
    emptyThePreview();
    byId("preview-note").textContent = t("preview.empty");
    return;
  }
  if (showing.kind === "notes") {
    return void showTheReleaseNotes(showing.version, showing.since);
  }
  showInPreview(showing);
}

/**
 * Empties every renderer and leaves one room showing.
 * @param {string} [kind] - Which one stays, or nothing for none of them, which
 *   is what closing the window wants.
 */
function emptyThePreview(kind) {
  for (const [name, renderer] of Object.entries(RENDERERS)) {
    renderer.clear();
    byId(renderer.room).hidden = name !== kind;
  }
}

/**
 * Opens the notes of a release, or of every release since the installed one.
 * @param {string | null} [version] - Which release, the newest where none is
 *   named.
 * @param {boolean} [since] - Whether to open every release newer than the
 *   installed one as one document instead, which is what the Raspberry Pi
 *   window asks for. The newest release's notes answer where nothing is
 *   newer.
 *
 * Its own address rather than a field of the answer the Raspberry Pi window
 * polls, because that one is asked every two seconds and these are thousands of
 * characters asked for when somebody presses a button.
 *
 * In the language the interface speaks. A release carries its notes in each of
 * them, and the service answers with English where one is missing. The answer
 * names every release there is, which the list beside the notes offers.
 */
async function showTheReleaseNotes(version, since = false) {
  /** @type {Record<string, string>} */
  const asked = { language: currentLanguage() };
  if (since) asked.since = "1";
  else if (version) asked.version = version;
  const answer = await ask("/api/update/notes", asked);
  showInPreview({
    kind: "notes",
    name: t("preview.notes.title", { version: answer?.version ?? "" }).trim(),
    notes: answer?.notes ?? "",
    version: answer?.version ?? null,
    versions: answer?.versions ?? [],
    installed: answer?.installed ?? null,
    newer: answer?.newer ?? [],
    since: answer?.since ?? false,
  });
}

/**
 * Asks for the notes again where Preview is showing them.
 *
 * For a change of language: the notes arrive in the language in force when
 * they are asked for, and a window holding them would go on in the old one
 * while everything around it spoke the new one.
 */
function showTheNotesAgain() {
  const window_ = theWindow("preview");
  const showing = whatItWasShowing();
  if (!window_ || window_.hidden || showing?.kind !== "notes") return;
  showTheReleaseNotes(showing.version, showing.since);
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

  if (!wasTaken(await tell("/api/picture/delete", { name }))) return false;

  /* The folder has one thing fewer in it than the viewer is drawing, and a
     window showing what has gone is showing something that is not there. */
  drawMachines();
  return true;
}

/**
 * Offers what can be done to a picture, where one was right clicked.
 * @param {Element} thing - The icon under the pointer.
 * @param {number} x @param {number} y - Where the pointer was.
 * @returns {boolean} Whether this menu was the right one for what was clicked.
 *
 * Titled for the kind of thing rather than for the file, because a file's
 * name is as long as somebody made it and a menu bar is one row. Which file
 * this is about is said by where the menu stands and by the question that
 * follows it.
 */
function openPictureMenu(thing, x, y) {
  const entry = find(root, thing.getAttribute("value") ?? "");
  if (entry?.kind !== "picture") return false;

  const menu = theMenu("picture-menu");
  if (!menu) return false;

  menuEntry(menu, "delete").onclick = async () => {
    menu.close();
    await deleteThePicture(entry.name);
  };
  menu.openAt(x, y);
  return true;
}

/** Wires Preview, which holds nothing of its own once it is closed. */
function wirePreview() {
  theWindow("preview")?.addEventListener("nx-close", () => {
    emptyThePreview();
    /* So a desk that comes back does not reopen a window onto a document
       somebody closed. */
    keepShowing(null);
  });

  fillPreviewIfItCameBackOpen();
}

export {
  showInPreview,
  showTheReleaseNotes,
  showTheNotesAgain,
  deleteThePicture,
  openPictureMenu,
  wirePreview,
};
