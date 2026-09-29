/* The disks on the card and the discs in the drive: which one the machine boots, and the copies of them. */

import { t } from "../strings.js";
import { SETUP, refreshTheInstaller } from "./installer.js";
import { reportAboutTheMachine } from "./machines.js";
import { show, theWindow } from "./page.js";
import { askPanel } from "./panels.js";
import { ask, tell } from "./service.js";
import { setBusy } from "./status.js";
import { Art, say, sized } from "./words.js";

/**
 * Asks about a disk and makes the machine boot it when the answer is yes.
 * @param {any} disk - Its entry in the tree.
 *
 * Nothing is fetched and nothing is copied. Each system is one file, the guest
 * writes into that file, and pointing the machine elsewhere leaves the first
 * exactly as it was left. That is the sentence somebody who has spent an
 * evening inside NeXTSTEP wants to read before they press anything, so it is
 * in the question rather than in a manual.
 */
async function bootFromDisk(disk) {
  if (disk.booting) return;

  const agreed = await askPanel({
    text: [
      t("ask.disk.title"),
      t("ask.disk.question", { name: disk.name }),
      t("ask.disk.size", { name: disk.name, size: sized(disk.bytes) }),
      t("ask.disk.freeze"),
      /* The same two sentences a change of machine ends on, because it is the
         same act and the same risk. */
      t("ask.change.how"),
      t("ask.change.rollback"),
    ],
    icon: Art.Disk,
    /* The same word as the button that opens this, wherever it was opened
       from. Two words for one act is one word too many. */
    confirm: t("button.activate"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: disk.name }));
  /* The tree says which disk is in force, so it is asked for again rather than
     marked from here. */
  reportAboutTheMachine(await tell("/api/disk", { disk: disk.id }));
}

/**
 * Puts a disc into the machine, or takes it out again.
 * @param {any} disc - Its entry in the tree, which says which slot it is on
 *   where it is in the machine at all.
 *
 * One gesture for both, because it is one thing: the disc is either in the
 * machine or it is not, and a double click swaps that over. The same as taking
 * a board out and putting it back, which is what this interface already does
 * wherever something is in or out rather than one of several.
 */
function useTheDisc(disc) {
  return disc.slot === null ? putTheDiscIn(disc) : takeTheDiscOut(disc);
}

/**
 * Asks about a disc, and puts it in the machine when the answer is yes.
 * @param {any} disc - Its entry in the tree.
 *
 * It goes beside the disk the machine boots rather than instead of it, on a
 * free slot of the bus, and it is read only there because that is what a disc
 * is.
 */
async function putTheDiscIn(disc) {
  const agreed = await askPanel({
    text: [
      t("ask.disc.title", { name: disc.name }),
      t("ask.disc.beside"),
      /* NeXT's own CDs carry a variation of 4.3BSD FFS, so an image that says
         ISO 9660 mounts nowhere however good it is. Said before somebody waits
         for a machine to come back with nothing new in it. */
      disc.iso ? t("ask.disc.iso") : "",
      t("ask.change.how"),
      t("ask.change.rollback"),
    ].filter(Boolean),
    icon: Art.Disc,
    confirm: t("button.insert"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: disc.name }));
  const answer = await tell("/api/disc", { disc: disc.id });
  reportAboutTheMachine(answer);
}

/**
 * Asks about a disc that is in the machine, and takes it out when the answer
 * is yes.
 * @param {any} disc - Its entry in the tree.
 */
async function takeTheDiscOut(disc) {
  const agreed = await askPanel({
    text: [t("ask.disc.eject-title", { name: disc.name }),
           t("ask.disc.eject-question"), t("ask.change.how")],
    icon: Art.Disc,
    confirm: t("button.eject"),
  });
  if (!agreed) return;

  setBusy(true, t("busy.changing", { machine: disc.name }));
  const answer = await tell("/api/disc/eject", { slot: disc.slot });
  reportAboutTheMachine(answer);
}

/**
 * Asks about a copy of a disk, and has one made when the answer is yes.
 * @param {any} disk - Its entry in the tree.
 *
 * Two gigabytes, so what it costs and what would be left are in the question
 * rather than in a failure afterwards. The figures are fetched at the moment
 * the question is put, because what is free changes with everything else on
 * the machine.
 */
async function backUpTheDisk(disk) {
  const state = await ask(SETUP);
  const agreed = await askPanel({
    text: [
      t("ask.backup.title", { name: disk.name }),
      t("ask.backup.cost", { name: disk.name, size: sized(disk.bytes) }),
      state ? t("ask.fetch.left", {
        free: sized(state.room),
        left: sized(Math.max(0, state.room - disk.bytes)),
      }) : "",
      t("ask.backup.off"),
      t("ask.install.time"),
    ].filter(Boolean),
    icon: Art.Disk,
    confirm: t("button.copy"),
  });
  if (agreed) askTheInstallerToCopy("/api/disk/backup", { system: disk.id });
}

/**
 * Asks about a copy, and writes it back over its disk when the answer is yes.
 * @param {any} copy - Its entry in the tree.
 *
 * The one thing that can be done with a copy, and the one that cannot be
 * undone: what is on the disk now is written over. So the question says that
 * before it says anything else.
 */
async function putTheCopyBack(copy) {
  const agreed = await askPanel({
    text: [t("ask.restore.title", { name: copy.name }),
           t("ask.restore.loss"), t("ask.backup.off"), t("ask.install.time")],
    icon: Art.Disk,
    confirm: t("button.put-back"),
  });
  if (agreed) {
    askTheInstallerToCopy("/api/disk/restore",
                          { system: copy.system, backup: copy.id });
  }
}

/**
 * Leaves a request for a copy and shows the window that watches it.
 * @param {string} route - Which of the two.
 * @param {any} body - What to send.
 *
 * The Installer is opened, because it is the window that says what the Pi is
 * doing and this takes minutes. Starting a five minute job from a viewer and
 * leaving nothing on the screen about it would be the worst of both.
 */
async function askTheInstallerToCopy(route, body) {
  const answer = await tell(route, body);
  show("machine-note", answer === null ? t("note.no-service") : say(answer));
  if (!answer?.ok) return;

  theWindow("installer")?.open();
  refreshTheInstaller();
}

export {
  bootFromDisk,
  useTheDisc,
  backUpTheDisk,
  putTheCopyBack,
};
