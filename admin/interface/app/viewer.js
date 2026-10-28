/* The File Viewer: what Previously holds, and moving about in it. */

import { NEAR_FLIGHT_MS, NxViewer, deskRect, fly, zoom } from "../nextstep.js";
import { t } from "../strings.js";
import { coverNow } from "./covers.js";
import { bootFromDisk, putTheCopyBack, useTheDisc } from "./disks.js";
import { noticeTheApplications } from "./dock.js";
import { readPath, readPaths, writeDown } from "./kept.js";
import { changeTo, editOnWhatIsRunning, notYet } from "./machines.js";
import { byId, show, targetName, theWindow } from "./page.js";
import { showInPreview } from "./preview.js";
import { ask } from "./service.js";
import { showSoftwareInfo } from "./software.js";
import { lastStatus, refresh } from "./status.js";
import { EDITOR, machineArt } from "./words.js";

/** @typedef {import("../answers.js").FilesAnswer} FilesAnswer */
/** @typedef {import("../answers.js").TreeEntry} TreeEntry */
/** @typedef {import("../answers.js").Folder<TreeEntry>} TreeFolder */
/** @typedef {import("../answers.js").ApplicationEntry} ApplicationEntry */
/** @typedef {import("../answers.js").MachineEntry} MachineEntry */
/** @typedef {import("../nextstep.js").ViewerEntry} ViewerEntry */

/** Everything this tool holds, as the service arranged it. Until it has
 *  answered, the root alone, named and drawn the way the service draws it.
 *  @type {FilesAnswer} */
let root = { name: "Previously", icon: "home", path: "/", kind: "folder", writable: true, entries: [] };

/** The way to the place being shown, outermost first.
 *  @type {TreeFolder[]} */
let at = [root];

/** Where the folder the viewer shows is kept between visits, by its path, so
 *  a reload finds the viewer where it was left, the way its window comes back
 *  where it stood. */
const PLACE_KEY = "previously:place";

/** Every machine anywhere in that tree. Kept because the info window says what
 *  a machine is without anything having to run.
 *  @type {MachineEntry[]} */
let catalogue = [];

/** Where the shelf's contents live between visits. The things themselves come
 *  from the service; this is only which of them somebody put there. */
const KEPT_KEY = "previously:kept";

/** What lies there before anybody puts anything there: the root, so there is
 *  always one step home, the machines, and the disks, which are the two things
 *  somebody switches between. A shelf entry for a folder that is not there is
 *  dropped when the shelf is drawn, so a machine with no disks shows two. */
const KEPT_BY_DEFAULT = ["/", "/Machines", "/Disks"];

/** The identifiers on the viewer's shelf, in the order they were put there. */
let kept = readPaths(KEPT_KEY, KEPT_BY_DEFAULT);

/**
 * Fills the shelf with the machines the service offers.
 *
 * The list comes from the service rather than from here, because what can be
 * chosen is decided by what can be written, and keeping a second copy in the
 * page is how the two come to disagree.
 */
async function drawMachines() {
  const answer = await ask("/api/files");
  if (!answer) {
    show("machine-note", t("viewer.unreachable"));
    return;
  }

  root = answer;
  catalogue = allMachines(root);
  /* The applications are in the tree, so what is running can only be drawn
     once it has arrived. */
  noticeTheApplications();
  /* Stay where the reader was, by path rather than by object, because the
     tree they are looking at was fetched again. Where they were is what was
     written down, which after a reload is the folder the page was left on. */
  standAt(chainTo(readPath(PLACE_KEY, root.path)));
  drawPlace();
}

/**
 * Moves the viewer to a place and writes down where it is.
 * @param {TreeFolder[]} steps - The way there, the root first, as chainTo
 *   gives it.
 */
function standAt(steps) {
  at = steps;
  writeDown(PLACE_KEY, steps[steps.length - 1].path);
}

/**
 * Every machine anywhere in the tree.
 * @param {TreeEntry} entry - Where to look.
 * @returns {MachineEntry[]} The machines, in the order they are met.
 *
 * The info window says what a machine is without caring where it sits, so it
 * reads from this rather than from wherever the viewer happens to be.
 */
function allMachines(entry) {
  if (entry.kind === "machine") return [entry];
  return entry.kind === "folder" ? entry.entries.flatMap((inside) => allMachines(inside)) : [];
}

/** Draws whatever place the viewer is in, with the way there above it. */
function drawPlace() {
  const here = at[at.length - 1];
  byId("file-viewer", NxViewer).show({
    path: at.map(entryFor),
    contents: here.entries.map(entryFor),
    /* Anything can lie on the shelf, a folder as readily as a machine, so
       this looks in the whole tree rather than among the machines. */
    keeps: kept.map((path) => find(root, path)).filter((entry) => entry !== null).map(entryFor),
    status: saying(here),
  });
  markCurrent(lastStatus?.configuration?.catalogue,
              lastStatus?.file?.newer_than_the_machine);
}

/**
 * The line under the shelf.
 * @param {TreeFolder} folder - The place being shown.
 * @returns {string} Which place, what is in it, and what cannot be done to it.
 *
 * It names the place because of where it sits: directly under the shelf, which
 * holds something else entirely. NeXTSTEP put a fact about the whole disk
 * there and had no such question to answer.
 */
function saying(folder) {
  const count = folder.entries.length;
  return t("viewer.status", {
    name: folder.name,
    count: t("viewer.count", { count }, count),
    more: folder.writable ? "" : t("viewer.read-only"),
  });
}

/**
 * One entry as the viewer wants it.
 * @param {TreeEntry} entry - Anything the tree holds.
 * @returns {ViewerEntry} `{label, icon, value, folder, dockable}`. The value
 *   is the entry's path, which is what a drop, a double click and the menu all
 *   hand over, so there is one place a thing's name lives.
 *
 * Everything in the tree keeps the name it came with, because a viewer shows
 * names: the folders, the bundles, the machines and Previously itself. A
 * German NeXTSTEP holds a directory called `Apps` and a bundle called
 * `Preferences.app`, and its viewer shows both as it finds them. What an
 * application is called in words is a different question, and appName answers
 * that one.
 */
function entryFor(entry) {
  return {
    label: entry.name,
    /* A folder and an application bring their own picture. A machine wears
       the one its boot ROM draws, and which that is follows from its case. */
    icon: entry.kind === "machine" ? machineArt(entry.enclosure) : entry.icon,
    /* Software wears its cover where it has one, cut once and kept, and its
       icon until then. */
    picture: entry.kind === "software" && entry.package.picture
      ? coverNow(entry.package.picture, drawPlace) ?? undefined : undefined,
    value: entry.path,
    folder: entry.kind === "folder",
    dockable: entry.kind === "application",
  };
}

/**
 * @param {ApplicationEntry} entry - An application.
 * @returns {string} What it is called in words, in the language being read.
 *
 * NeXTSTEP kept the two apart and so does this. The bundle in `/NextApps` was
 * `Preferences.app` in every language, while the application called itself
 * `Präferenzen` in German wherever it named itself in a sentence, which is
 * what its own `preferences.strings` holds.
 */
function appName(entry) {
  return t(entry.label);
}

/**
 * Answers a double click in the viewer, whatever was under it.
 * @param {string} path - What the thing carries.
 * @param {Element} [asker] - The thing that was opened, which is where
 *   whatever opens starts from.
 */
function open(path, asker) {
  const entry = find(root, path);
  if (!entry) return;
  if (entry.kind === "folder") {
    /* Built from the path rather than by adding a step, because a folder on
       the shelf can be anywhere and the way there is not the way from here. */
    standAt(chainTo(entry.path));
    return openFolder(asker);
  }
  if (entry.kind === "application") {
    /* The editor is opened on a machine rather than on nothing, so it goes
       through the one place that decides which. Every other application's window
       holds whatever it holds. */
    if (entry.opens === EDITOR) return editOnWhatIsRunning(asker);
    /* An application this tool has is a window it already holds. One it does
       not have yet says so, which is the honest thing to do with an icon that
       is there because the place it sits in is being built around it. */
    const window_ = theWindow(entry.opens);
    return window_ ? window_.open(asker) : notYet(appName(entry));
  }
  if (entry.kind === "picture") return showInPreview(entry);
  /* A disk is chosen the same way a machine is, because it is the same act:
     the guest goes down, one thing is written, and it comes back. */
  if (entry.kind === "disk") return bootFromDisk(entry);
  /* And a copy of one is put back, which is the only thing to do with it. */
  if (entry.kind === "backup") return putTheCopyBack(entry);
  /* A disc goes into the machine, or comes out of it again. */
  if (entry.kind === "disc") return useTheDisc(entry);
  /* Software is not on the card yet, so opening it says what it is. */
  if (entry.kind === "software") return showSoftwareInfo(entry, asker);
  /* Named rather than left as what everything else falls through to, because
     what else is in here has grown and falling through would have asked the
     machine to become whatever was double clicked. */
  if (entry.kind === "machine") changeTo(entry.id);
}

/**
 * Draws the place the viewer has moved to, with the way there where it is
 * known.
 * @param {Element} [asker] - The thing that was opened, if one was.
 *
 * The rectangles run from the mark around that thing to the band that is
 * about to hold what was inside it, and the contents change when they arrive.
 * Without a thing to start from, which is what a step of the path is, the
 * place simply changes.
 */
async function openFolder(asker) {
  const band = document.querySelector("#file-viewer nx-scroller:last-child");
  /* Only from the band below. The original draws this nowhere else: what is
     opened from the shelf flies to the path instead, and a step of the path
     is a way back rather than something being opened. */
  const from = asker?.closest(".contents") ? deskRect(asker) : null;
  const to = deskRect(band);
  if (!from || !to) return drawPlace();

  await zoom(from, to);
  drawPlace();
}

/**
 * Answers one click on the shelf.
 * @param {string} where - The path of what was clicked.
 * @param {Element} thing - What was clicked, which is where its icon starts
 *   from.
 *
 * A folder on the shelf changes what the viewer shows, and its icon travels
 * to the place it takes in the path as it does. Anything else there is a
 * machine, and clicking one chooses it and nothing more.
 */
async function visitFromTheShelf(where, thing) {
  const entry = find(root, where);
  if (entry?.kind !== "folder") return;

  /* Already where the viewer is standing, which the path shows by ending on
     it. There is nothing to fly to and nothing to redraw, and an icon that
     travels to the place it is already in says something happened when
     nothing did. */
  if (at.at(-1)?.path === entry.path) return;

  const from = deskRect(thing);
  standAt(chainTo(entry.path));
  drawPlace();

  const steps = document.querySelectorAll("#file-viewer .path nx-thing");
  const landing = steps[steps.length - 1];
  const to = deskRect(landing);
  if (!from || !to || !(landing instanceof HTMLElement)) return;

  landing.style.visibility = "hidden";
  await fly(landing.getAttribute("icon") ?? "", from, to, NEAR_FLIGHT_MS);
  landing.style.visibility = "";
}

/**
 * The way from the root to a place, as the steps themselves.
 * @param {string} where - A path such as "/Machines/System".
 * @returns {TreeFolder[]} The root first, that place last.
 */
function chainTo(where) {
  const steps = [root];
  let path = "";
  for (const part of where.split("/").filter(Boolean)) {
    path += "/" + part;
    const step = folderAt(path);
    if (!step) break;
    steps.push(step);
  }
  return steps;
}

/**
 * Goes back to a step of the path.
 * @param {number} index - Which step, counted from the root.
 */
function goTo(index) {
  standAt(at.slice(0, index + 1));
  drawPlace();
}

/**
 * @param {TreeEntry} entry - Where to look.
 * @param {string} path - What to look for.
 * @returns {TreeEntry | null} The entry with that path, that one or anywhere
 *   below it.
 */
function find(entry, path) {
  if (entry.path === path) return entry;
  if (entry.kind !== "folder") return null;
  for (const inside of entry.entries) {
    const found = find(inside, path);
    if (found) return found;
  }
  return null;
}

/**
 * @param {string} path - What to look for.
 * @returns {TreeFolder | null} The folder with that path, or null where the
 *   path leads to something else or nowhere.
 */
function folderAt(path) {
  const found = find(root, path);
  return found?.kind === "folder" ? found : null;
}

/**
 * Puts a machine on the viewer's shelf, or takes it off again.
 * @param {string} where - The machine's path in the tree.
 * @param {boolean} onto - True to put it there, false to take it off.
 *
 * The shelf is for the two or three somebody actually switches between. It is
 * kept in this browser rather than on the Pi: which machines one person wants
 * to hand is not a property of the machine.
 */
function keepOnShelf(where, onto) {
  kept = kept.filter((entry) => entry !== where);
  if (onto) kept.push(where);
  writeDown(KEPT_KEY, kept);
  drawMachines();
}

/**
 * Marks the machine the emulator is currently set to.
 * @param {string | null} [identifier] - Which of the eleven the file holds
 *   exactly, or null where it holds none of them or nothing has been read yet.
 * @param {boolean} [untried] - Whether the file has been written since that
 *   machine started, so what is written down has never been through a boot.
 *
 * By identifier rather than by name, because two of the eleven differ from
 * another two by their clock alone and share a name in the file.
 */
function markCurrent(identifier, untried) {
  for (const thing of document.querySelectorAll("#file-viewer nx-thing")) {
    const where = thing.getAttribute("value") ?? "";
    const machine = catalogue.find((entry) => entry.path === where);
    const entry = find(root, where);
    /* A disk carries which one the machine boots, because the service reads
       that out of the configuration and the browser has no business working it
       out from a path. The same mark, because it is the same statement: this
       is the one in force. */
    const isCurrent = machine
      ? machine.id === identifier
      : entry?.kind === "disk" && entry.booting;
    thing.classList.toggle("current", isCurrent);
    thing.classList.toggle("untried", isCurrent && Boolean(untried));
    /* Switching to the machine that is already running would shut NeXTSTEP
       down, write the same values back and start it again, for nothing. */
    thing.toggleAttribute("disabled", isCurrent);
    if (isCurrent) thing.removeAttribute("chosen");
  }
}

/** Fills a window the moment it opens, rather than at the next poll. */
function wireOpening() {
  document.addEventListener("nx-open", (event) => {
    if (targetName(event.target) === "pi") refresh();
  });
}

export {
  root,
  catalogue,
  drawMachines,
  drawPlace,
  appName,
  open,
  visitFromTheShelf,
  goTo,
  find,
  keepOnShelf,
  markCurrent,
  wireOpening,
};
