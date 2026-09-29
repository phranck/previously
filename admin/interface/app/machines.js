/* Changing which machine this is, which disk it boots and what is in its drive. */

import { t, writeWords } from "../strings.js";
import { backUpTheDisk, bootFromDisk, putTheCopyBack, useTheDisc } from "./disks.js";
import { editConfiguration } from "./editor.js";
import { show } from "./page.js";
import { askPanel, askPanelFor } from "./panels.js";
import { openPictureMenu } from "./preview.js";
import { Saved, tell } from "./service.js";
import { drawStatus, lastStatus, refresh, setBusy } from "./status.js";
import { catalogue, drawMachines, find, goTo, keepOnShelf, open, root, visitFromTheShelf } from "./viewer.js";
import { Art, EDITOR, NOTHING, changedLine, chipsOf, cpuOf, fitted, machineArt, say, screenOf, writtenLine } from "./words.js";

/**
 * Shows what one machine is, in a window of its own.
 * @param {string} where - The machine's path in the tree.
 *
 * The settings come from the catalogue, so a machine that is not running is
 * described exactly as the running one is. The two lines about the file are
 * about the file rather than about the machine, so they are filled in only for
 * the machine the file actually holds.
 */
function showMachineInfo(where) {
  const machine = catalogue.find((entry) => entry.path === where);
  if (!machine) return;

  const window_ = document.querySelector('nx-window[name="machine-info"]');
  window_.rename(machine.name);
  show("mi-caption", machine.name);
  document.getElementById("mi-icon").style.backgroundImage =
    `var(--${machineArt(machine.enclosure)})`;

  show("mi-cpu", cpuOf(machine));
  show("mi-ram", t("machine.memory-banks",
                   { mb: machine.memory_mb, banks: fitted(machine.banks) }));
  show("mi-screen", screenOf(machine));
  show("mi-dimension", t(machine.dimension
    ? "machine.dimension.fitted" : "machine.dimension.none"));
  show("mi-chips", chipsOf(machine));

  /* The file holds one machine, so everything it can say applies to that one
     and to no other. */
  const file = lastStatus?.file;
  /* By identifier rather than by name, because the file cannot carry the
     Nitro that the catalogue's name does. */
  const isTheOneInTheFile = lastStatus?.configuration?.catalogue === machine.id;
  if (!file || !isTheOneInTheFile) {
    show("mi-changed", t("file.other-machine"));
    show("mi-written", NOTHING);
  } else {
    show("mi-changed", changedLine(file));
    show("mi-written", writtenLine(file));
  }

  window_.open();
}

/**
 * Asks about a machine and changes to it when the answer is yes.
 * @param {string} identifier - Which machine, as the catalogue names it.
 *   The catalogue's own identifier rather than a path, because that is what
 *   the service takes.
 */
async function changeTo(identifier) {
  const machine = catalogue.find((entry) => entry.id === identifier);
  if (!machine) return;

  const name = machine.name;
  /* What is in the file now is nobody's machine from this list, so saying it
     will be written over is the difference between a change and a loss. */
  const own = Boolean(lastStatus?.configuration) && !lastStatus.configuration.catalogue;
  const agreed = await askPanel({
    title: t("ask.change.title"),
    text: [
      t("ask.change.question", { machine: name }),
      own && t("ask.change.own"),
      t("ask.change.how"),
      t("ask.change.rollback"),
    ].filter(Boolean),
    /* The same picture it wears in the viewer, taken from the same place. */
    icon: machineArt(machine.enclosure),
    confirm: t("button.change"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: name }));
  const answer = await tell("/api/machine", { machine: identifier });
  setBusy(false, answer === null ? t("note.no-service") : say(answer));
  if (answer) drawStatus(answer);
  refresh();
}

/**
 * Says what came of a change to the machine, and draws everything again.
 * @param {object|null} answer - What the service said, or null on no contact.
 *
 * The tree as well as the status, because what it says about a disk or a disc
 * comes out of the same file that has just been written.
 */
function reportAboutTheMachine(answer) {
  setBusy(false, answer === null ? t("note.no-service") : say(answer));
  if (answer) drawStatus(answer);
  drawMachines();
  refresh();
}

/**
 * Gives a saved configuration another name.
 * @param {object} machine - Its entry in the tree.
 *
 * Only a configuration somebody saved has a name to change. The eleven are the
 * set to go back to, and the menu does not offer this for them at all.
 */
async function renameConfiguration(machine) {
  const typed = await askPanelFor({
    title: t("ask.rename.title", { name: machine.name }),
    text: [t("ask.rename.question")],
    icon: machineArt(machine.enclosure),
    confirm: t("button.rename"),
  });
  if (typed === null) return;

  reportAboutTheSaved(
    await tell(Saved.Rename, { machine: machine.id, name: typed }));
}

/**
 * Takes a saved configuration out of the list, after asking.
 * @param {object} machine - Its entry in the tree.
 *
 * Asked first, because there is no wastebasket here to fish one out of again.
 * What this does not touch is the running machine: previous.cfg is the
 * emulator's own file, so a machine running this configuration goes on running
 * it.
 */
async function removeConfiguration(machine) {
  const sure = await askPanel({
    title: t("ask.remove.title", { name: machine.name }),
    text: [t("ask.remove.loss")],
    icon: machineArt(machine.enclosure),
    confirm: t("button.remove"),
  });
  if (!sure) return;

  reportAboutTheSaved(await tell(Saved.Remove, { machine: machine.id }));
}

/**
 * Says what came of a change to the saved configurations, and draws them again.
 * @param {object|null} answer - What the service said, or null on no contact.
 *
 * The line under the viewer, because that is the window this happened in. The
 * status is asked for again as well: the machine in force may be the one that
 * has just been renamed, and the info window names it.
 */
function reportAboutTheSaved(answer) {
  show("machine-note", answer === null ? t("note.no-service") : say(answer));
  drawMachines();
  refresh();
}

/* --- the Config Editor ----------------------------------------------------

   Previous's own System dialogue, in this interface's idiom: what can be chosen
   on one side and what follows from it on the other. Here the picture and its
   readings stand over the groups that change them.

   It holds no rule of its own. What a choice turns into, and what may be chosen
   beside it, are both asked of the service on every change, so there is one
   statement of what Previous allows and this window cannot offer a machine the
   emulator would correct underneath it. That is also why the configuration it
   saves is the one the service handed back rather than one assembled here. */

/**
 * Opens the editor on the configuration that is set now.
 * @param {HTMLElement} [asker] - What was used to open it.
 *
 * Which is what somebody means by starting the editor without having chosen a
 * machine: the one in front of them. Where the file holds a configuration of
 * their own, that one is edited in place, and where it holds one of the eleven or
 * none of them, what comes out of editing it is new.
 */
function editOnWhatIsRunning(asker) {
  const machine = lastStatus?.configuration;
  const own = catalogue.find((entry) =>
    entry.id === machine?.catalogue && entry.set === "user");
  editConfiguration(own ?? machine, asker);
}

/**
 * Says that an application that is not built yet is not built yet.
 * @param {string} name - What it will be called.
 */
function notYet(name) {
  return askPanel({
    title: name,
    text: [t("ask.not-yet.missing", { name }), t("ask.not-yet.plan")],
    icon: Art.Editor,
    confirm: t("button.fine"),
    cancel: t("button.close"),
  });
}

/**
 * Opens the context menu for whatever was clicked.
 * @param {HTMLElement} thing - What was clicked.
 * @param {number} x - Where the pointer was.
 * @param {number} y
 * @returns {boolean} Whether there was anything to offer.
 *
 * A machine gets the whole menu. Anything else gets one entry, and only where
 * it lies on the shelf: a folder is opened by double clicking it, so a menu of
 * entries that all refuse would be worse than none.
 */
function openMachineMenu(thing, x, y) {
  const where = thing.getAttribute("value");
  const machine = catalogue.find((entry) => entry.path === where);
  /* A disk carries one of the same entries, because it is chosen the same way.
     The other four are about a configuration and a disk is not one. */
  const found = find(root, where);
  const disk = found?.kind === "disk" ? found : null;
  const copy = found?.kind === "backup" ? found : null;
  const disc = found?.kind === "disc" ? found : null;
  const onShelf = Boolean(thing.closest(".keep"));
  if (!machine && !disk && !copy && !disc && !onShelf) return false;

  const menu = document.querySelector('nx-menu[name="machine-menu"]');
  /* Which machine this is about. The menu appears over whatever was clicked
     and then goes away, so without a name it is an orphan. */
  menu.querySelector(".title").textContent = thing.getAttribute("label");
  const info = menu.querySelector('nx-menu-item[name="info"]');
  const activate = menu.querySelector('nx-menu-item[name="activate"]');
  const edit = menu.querySelector('nx-menu-item[name="edit"]');
  const rename = menu.querySelector('nx-menu-item[name="rename"]');
  const remove = menu.querySelector('nx-menu-item[name="remove"]');
  const backup = menu.querySelector('nx-menu-item[name="backup"]');
  const restore = menu.querySelector('nx-menu-item[name="restore"]');
  const media = menu.querySelector('nx-menu-item[name="disc"]');
  const shelf = menu.querySelector('nx-menu-item[name="shelf"]');

  /* Three of the entries are about a machine, so a folder on the shelf shows
     only the one that applies to it. Activating is the exception: a disk is
     started exactly as a machine is. */
  for (const entry of [info, edit]) entry.hidden = !machine;
  activate.hidden = !machine && !disk;
  /* And two are about a configuration somebody saved. The eleven cannot be
     renamed or removed, so for those the entries are not in the menu at all
     rather than in it and refusing. */
  for (const entry of [rename, remove]) entry.hidden = machine?.set !== "user";
  /* A disk can be copied and a copy can be put back, and neither entry means
     anything for the other three kinds of thing. */
  backup.hidden = !disk;
  restore.hidden = !copy;
  backup.onclick = () => {
    menu.close();
    backUpTheDisk(disk);
  };
  restore.onclick = () => {
    menu.close();
    putTheCopyBack(copy);
  };
  /* One entry whichever way round it is, because it is one act. The key goes
     with the wording, so a change of language finds what it is showing rather
     than what the markup started with. */
  media.hidden = !disc;
  if (disc) {
    media.dataset.t = disc.slot === null ? "menu.insert" : "menu.eject";
    writeWords(media, t(media.dataset.t));
    media.onclick = () => {
      menu.close();
      useTheDisc(disc);
    };
  }

  info.onclick = () => {
    menu.close();
    showMachineInfo(where);
  };

  /* The one entry whose wording changes, because it is the same act either
     way round and two entries for it would both be wrong half the time. The
     key is written with it, so a change of language finds the wording this
     entry is actually showing rather than the one the markup started with. */
  shelf.dataset.t = onShelf ? "menu.unkeep" : "menu.keep";
  writeWords(shelf, t(shelf.dataset.t));
  shelf.onclick = () => {
    menu.close();
    keepOnShelf(where, !onShelf);
  };

  if (machine || disk) {
    /* The one that is already running cannot be activated: it would shut
       NeXTSTEP down, write the same values back and start it again, for
       nothing. The entry stays, so the menu keeps its shape. */
    activate.toggleAttribute("disabled", thing.hasAttribute("disabled"));

    activate.onclick = () => {
      if (activate.hasAttribute("disabled")) return;
      menu.close();
      if (machine) return changeTo(machine.id);
      bootFromDisk(disk);
    };
  }

  if (machine) {
    rename.onclick = () => {
      menu.close();
      renameConfiguration(machine);
    };

    remove.onclick = () => {
      menu.close();
      removeConfiguration(machine);
    };
  }
  edit.onclick = () => {
    menu.close();
    editConfiguration(machine, thing);
  };

  menu.openAt(x, y);
  return true;
}

/** Wires the two gestures that choose a machine. The third, the context
 *  menu, wires itself where it is opened. */
function wireMachines() {
  /* The note under the viewer has been read by the time somebody reaches into
     the window again. Wired here rather than in drawMachines, which runs again
     after every change and would leave a second listener behind each time. */
  document.getElementById("file-viewer")
    .addEventListener("click", () => show("machine-note", ""));

  /* A right click anywhere on a machine, rather than on the shelf, so the menu
     is always about something. */
  document.getElementById("file-viewer").addEventListener("contextmenu", (event) => {
    const thing = event.target.closest("nx-thing");
    if (!thing) return;
    event.preventDefault();
    /* Each menu says whether what was clicked is its own, so the one that
       belongs to it opens and nothing opens over something neither covers. */
    openMachineMenu(thing, event.clientX, event.clientY)
      || openPictureMenu(thing, event.clientX, event.clientY);
  });

  /* Carried onto a window, or double clicked in the viewer. The kit raises the
     same event for both, so this is one answer to two gestures, and what happens
     follows from what was chosen. */
  /* The thing that was chosen is where an application's icon starts its
     journey to the floor of the screen, so it travels with the choice. */
  document.addEventListener("nx-choose", (event) => {
    /* Carried into the Config Editor, which means edit that machine rather than
       start it. Anything else dropped there is ignored: the editor has nothing to
       do with a folder or a picture. */
    if (event.target?.getAttribute?.("name") === EDITOR) {
      const machine = catalogue.find((entry) => entry.path === event.detail.value);
      if (machine) editConfiguration(machine);
      return;
    }
    open(event.detail.value, event.target);
  });

  /* A step of the path was clicked, so go back to it. */
  document.addEventListener("nx-path", (event) => goTo(event.detail.index));

  /* One click on the shelf, which is the one place a single click acts. */
  document.addEventListener("nx-visit",
    (event) => visitFromTheShelf(event.detail.value, event.target));

  /* Carried onto the viewer's own shelf, which means keep this one to hand
     rather than start it. */
  document.addEventListener("nx-keep",
    (event) => keepOnShelf(event.detail.value, true));
}

export {
  changeTo,
  reportAboutTheMachine,
  editOnWhatIsRunning,
  notYet,
  wireMachines,
};
