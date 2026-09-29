/* What the Installer's buttons ask for, each of them a question first. */

import { t } from "../strings.js";
import { bootFromDisk } from "./disks.js";
import { Install, askTheInstaller, chosenSystem, setupState } from "./installer.js";
import { askPanel } from "./panels.js";
import { Art, sized } from "./words.js";

/**
 * Asks before the emulator is installed, and installs it when the answer is
 * yes.
 *
 * NeXTSTEP 3.3 comes with it unless another system is chosen in the list, so
 * that a machine which has just been set up boots into a system rather than
 * into a prompt about what to do next.
 */
async function installTheEmulator() {
  const system = whichSystemToInstallWith();
  const agreed = await askPanel({
    title: t("ask.install.title"),
    text: [
      t("ask.install.what"),
      system ? t("ask.install.system", {
        name: system.name,
        size: sized(system.size),
        unpacked: sized(system.unpacked),
      }) : "",
      t("ask.install.time"),
    ].filter(Boolean),
    icon: Art.Installer,
    confirm: t("button.install"),
  });
  if (agreed) askTheInstaller(Install.Emulator, system?.identifier);
}

/**
 * Which system the emulator is installed with.
 * @returns {object|undefined} The one chosen in the list, or the one the
 *   service says comes by default, or nothing at all where that one is already
 *   here.
 */
function whichSystemToInstallWith() {
  const systems = setupState?.systems ?? [];
  const chosen = systems.find((system) => system.identifier === chosenSystem);
  const wanted = chosen ?? systems.find(
    (system) => system.identifier === setupState?.default);
  return wanted?.here ? undefined : wanted;
}

/** Asks before the newest Previous is put in place, and does it if so. */
async function updateTheEmulator() {
  const agreed = await askPanel({
    title: t("ask.update.title"),
    text: [t("ask.update.what")],
    icon: Art.Installer,
    confirm: t("button.update"),
  });
  if (agreed) askTheInstaller(Install.Newest);
}

/** Asks before the emulator goes, and takes it away if so. */
async function removeTheEmulator() {
  const agreed = await askPanel({
    title: t("ask.remove-emulator.title"),
    text: [t("ask.remove-emulator.loss"), t("ask.remove-emulator.disks")],
    icon: Art.Installer,
    confirm: t("button.remove"),
  });
  if (agreed) askTheInstaller(Install.Away);
}

/**
 * Asks before a system is fetched, saying what it costs and what is left.
 *
 * A card that fills up during an unpack leaves a half written image and a
 * person with no idea why, so the figures are in the question rather than in a
 * failure afterwards.
 */
async function fetchTheSystem() {
  const system = setupState?.systems.find(
    (entry) => entry.identifier === chosenSystem);
  if (!system) return;

  const agreed = await askPanel({
    title: t("ask.fetch.title", { name: system.name }),
    text: [
      t("ask.fetch.cost", {
        name: system.name,
        size: sized(system.size),
        unpacked: sized(system.unpacked),
      }),
      t("ask.fetch.left", {
        free: sized(setupState.room),
        left: sized(Math.max(0, setupState.room - system.unpacked)),
      }),
      /* The same sentence the other question ends on, because it says the same
         thing: this takes minutes and the window can be left. Two copies of it
         would part company the first time one was rewritten. */
      t("ask.install.time"),
    ],
    icon: Art.Installer,
    confirm: t("button.fetch"),
  });
  if (agreed) askTheInstaller(Install.Fetch, system.identifier);
}

/** Asks before a system's disk goes, and takes it away if so. */
async function forgetTheSystem() {
  const system = setupState?.systems.find(
    (entry) => entry.identifier === chosenSystem);
  if (!system) return;

  const agreed = await askPanel({
    title: t("ask.forget.title", { name: system.name }),
    text: [t("ask.forget.loss"), t("ask.forget.again")],
    icon: Art.Installer,
    confirm: t("button.remove"),
  });
  if (agreed) askTheInstaller(Install.Forget, system.identifier);
}

/**
 * Starts the machine on the system chosen in the list.
 *
 * The same act as a double click on a disk in the File Viewer, and the same
 * question, so there is one implementation of it and one thing to get right.
 * What it costs to know is built here because the Installer names a system by
 * what it is rather than by where its file sits.
 */
function activateTheSystem() {
  const chosen = setupState?.systems.find(
    (system) => system.identifier === chosenSystem);
  if (!chosen?.here) return;

  bootFromDisk({
    id: chosen.identifier,
    name: chosen.name,
    bytes: chosen.unpacked,
    booting: chosen.booting,
  });
}

export {
  installTheEmulator,
  updateTheEmulator,
  removeTheEmulator,
  fetchTheSystem,
  forgetTheSystem,
  activateTheSystem,
};
