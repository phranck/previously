/* The Installer: what is on this Pi, and what can be put on it. */

import { t } from "../strings.js";
import { fillWithChoices } from "./fittings.js";
import { activateTheSystem, fetchTheSystem, forgetTheSystem, installTheEmulator, removeTheEmulator, updateTheEmulator } from "./jobs.js";
import { explain, show } from "./page.js";
import { ask, tell } from "./service.js";
import { say, sized } from "./words.js";

/** Where the Installer asks and tells. One address for both, because what
 *  comes back from asking is what the window shows anyway. */
const SETUP = "/api/setup";

/** What the service may be asked to do, by the name it takes. */
const Install = {
  Emulator: "install",
  Newest: "update",
  Away: "remove",
  Fetch: "fetch",
  Forget: "forget",
};

/** How often the Installer looks. Faster than the desk's own poll, because a
 *  download says something new every second and this is a window somebody sits
 *  and watches. Asked only whilst the window is open or something is running,
 *  and only every fourth time whilst neither is true. */
const WATCHING_MS = 500;
const EVERY_FOURTH = 4;

/** The last thing /api/setup said, so the window can be drawn again in another
 *  language without asking for it. */
let setupState = null;

/** Which system is chosen in the list, by identifier, or null. */
let chosenSystem = null;

/** What the Installer shows one of at a time, and what each is called. Two
 *  subjects in one window, because the emulator is a package and a system is a
 *  two gigabyte disk: they belong together and want to be apart. */
const INSTALLER_TABS = {
  emulator: "installer.emulator.title",
  systems: "installer.systems",
};

/** Which of them is showing. Kept here rather than read back off the markup,
 *  so a redraw whilst something is installing leaves somebody where they
 *  were. */
let showingInTheInstaller = Object.keys(INSTALLER_TABS)[0];

/** Whether something has been asked for and the helper has not started yet.
 *
 *  The request is written into a file and a path unit starts the program that
 *  reads it, so for a moment after the answer comes back the newest thing the
 *  Pi has to say is still about the run before. Without this the window
 *  answers a press with the last run's "Finished". */
let waitingForTheHelper = false;

/** Which run was showing when that request was left, by the moment it started,
 *  so the one that follows it can be told apart from it. */
let theRunBefore = null;

/** When that request was left, by this browser's clock, so waiting for ever is
 *  not one of the states this window has. */
let askedAt = 0;

/** How long the helper may take to start before the window says it has not.
 *  A path unit fires within a second of the file appearing, so anything past
 *  this is a machine whose helper is not there rather than one that is slow. */
const PATIENCE_MS = 30000;

/** What the window says whilst it waits: first that the Pi is being asked, and
 *  then whatever the service answered. It stands until the helper has
 *  something of its own to say, because a sentence that is wiped by the next
 *  draw is a sentence nobody reads. */
let whilstWaiting = "";

/**
 * Asks the service what can be installed and what is happening, and draws it.
 *
 * Every figure is read now rather than remembered. What is free changes with
 * everything else on the machine, and a number from five minutes ago is what
 * lets an unpack stop half way through a disk image.
 */
async function refreshTheInstaller() {
  drawTheInstaller(await ask(SETUP));
}

/**
 * Draws the whole window.
 * @param {object|null} state - What /api/setup answered, or null on no contact.
 */
function drawTheInstaller(state) {
  if (state === null) {
    show("installer-caption", t("info.no-contact"));
    allowInstalling(false);
    return;
  }
  setupState = state;

  const here = state.systems.filter((system) => system.here);
  show("installer-emulator", emulatorLine(state.emulator));
  show("installer-count", t("installer.count",
                            { here: here.length, all: state.systems.length }));
  show("installer-room", sized(state.room));
  show("installer-emulator-note", whatTheButtonsDo(state.emulator));
  explain("installer-systems-note", t("installer.systems.note"));

  drawTheTabs();
  drawTheSystems(state.systems);
  drawWhatIsBeingInstalled(state.progress);
}

/**
 * Draws the row that chooses between the two subjects.
 *
 * The same raised cell every choice in this interface uses, and the groups
 * below are shown by the attribute the page marks them with, so the subjects
 * are named in one place.
 */
function drawTheTabs() {
  fillWithChoices("installer-tabs",
    Object.entries(INSTALLER_TABS).map(([subject, word]) => ({
      label: t(word),
      chosen: subject === showingInTheInstaller,
      choose: () => {
        showingInTheInstaller = subject;
        drawTheTabs();
      },
    })));

  for (const group of document.querySelectorAll(".installer-groups > [subject]")) {
    group.toggleAttribute(
      "away", group.getAttribute("subject") !== showingInTheInstaller);
  }
}

/**
 * What the readings say about the emulator.
 * @param {object} emulator - What the service says: whether it is here, which
 *   version, and what the archive offers.
 * @returns {string} The version where there is one, because that is the fact
 *   somebody wants, and the bare word where there is not.
 */
function emulatorLine(emulator) {
  if (!emulator?.here) return t("installer.emulator.out");
  return emulator.version
    ? t("installer.emulator.in.version", { version: emulator.version })
    : t("installer.emulator.in");
}

/**
 * A line per button, so that what each one does is read rather than guessed.
 * @param {object} emulator - What the service says about it.
 * @returns {string} The lines, one per button that is there, parted by
 *   newlines, which the stylesheet keeps.
 *
 * Update is left out entirely where the archive has nothing newer, because a
 * button that would bring the same version is a button that does nothing. Its
 * line names the version it would bring, since that is the whole of why
 * somebody would press it.
 */
function whatTheButtonsDo(emulator) {
  if (!emulator?.here) return t("installer.emulator.what.install");
  /* Nothing at all about updating where there is nothing newer, because the
     button is not there either. A sentence explaining a button nobody can see
     is a sentence about nothing. */
  return [
    t("installer.emulator.what.remove"),
    emulator.newer
      ? t("installer.emulator.what.update", { version: emulator.newest })
      : "",
  ].filter(Boolean).join("\n");
}

/**
 * Draws the six systems, with the one chosen marked.
 * @param {object[]} systems - What the service offers, each saying what it
 *   costs and whether it is already here.
 */
function drawTheSystems(systems) {
  document.getElementById("installer-systems").replaceChildren(
    ...systems.map((system) => {
      const row = document.createElement("div");
      row.className = "system";
      row.toggleAttribute("chosen", system.identifier === chosenSystem);

      /* Whether it is already here, as a mark rather than as a word: NeXT's
         own Installer.app carried this one for exactly this question. The ones
         that are not here keep the space, so the names line up. */
      const mark = document.createElement("i");
      mark.className = "system-mark";
      mark.toggleAttribute("here", system.here);

      const name = document.createElement("span");
      name.textContent = system.name;

      /* Always, whether it is here or not. How large a system is belongs to
         the system, and whether it is here is a different fact with a column
         of its own. */
      const cost = document.createElement("span");
      cost.className = "system-cost";
      cost.textContent = sized(system.size);

      row.append(mark, name, cost);
      row.addEventListener("click", () => {
        chosenSystem = system.identifier;
        drawTheInstaller(setupState);
      });
      return row;
    }));
}

/**
 * Says what is being installed, how far it has got, and how it went.
 * @param {object|null} progress - What the privileged helper wrote, or null
 *   where it has never run on this machine since it last started.
 *
 * The step is named in words out of the catalogue, because the helper sends a
 * name rather than a sentence for the same reason everything else here does.
 * The trough is there whilst something is running and gone otherwise, since an
 * empty gauge is a window claiming to be busy.
 */
function drawWhatIsBeingInstalled(progress) {
  const gauge = document.getElementById("installer-gauge");

  /* Anything the Pi is still showing from before the request is the run
     before this one, so the window keeps saying it was asked rather than
     reading out that one's ending. */
  if (waitingForTheHelper
      && Boolean(progress) && progress.started_at !== theRunBefore) {
    waitingForTheHelper = false;
  }
  if (waitingForTheHelper) {
    /* A path unit starts its service within a second of the file appearing, so
       a wait this long is a machine whose helper is not there rather than one
       that is slow. Saying so beats one word standing for ever. */
    const tooLong = Date.now() - askedAt > PATIENCE_MS;
    allowInstalling(tooLong);
    gauge.hidden = true;
    show("installer-caption",
         t(tooLong ? "installer.not-started" : "installer.asked"));
    show("installer-note",
         tooLong ? t("installer.not-started.why") : whilstWaiting);
    return;
  }

  const running = Boolean(progress) && progress.finished_at === null;
  allowInstalling(!running);
  gauge.hidden = !running;

  if (!progress) {
    show("installer-caption", t("installer.idle"));
    show("installer-note", "");
    return;
  }

  const step = t(`setup.step.${progress.step}`);
  if (running) {
    show("installer-caption", step);
    /* Which step of how many, and then what that step is doing at this moment
       and how much of how much. One step can fetch, unpack and then move, and
       a bar on its own says none of that. */
    show("installer-note", [
      t("installer.step", { done: progress.done, of: progress.of }),
      progress.part
        ? t(`installer.doing.${progress.part.doing}`, {
            done: sized(progress.part.done, true),
            of: sized(progress.part.of, true),
          })
        : "",
    ].filter(Boolean).join(" "));
    /* Two measures in one bar: which step of how many, and how far through a
       step that knows. A download and an unpack are the only ones that know,
       and they are the ones that take the minutes. */
    const through = progress.part?.of
      ? progress.part.done / progress.part.of : 0;
    const done = (progress.done - 1 + Math.min(1, through)) / progress.of;
    document.getElementById("installer-fill").style.width =
      `${Math.round(done * 100)}%`;
    return;
  }

  if (progress.ok) {
    show("installer-caption", t("installer.done"));
    /* What the machine has now, in one sentence about the job. The steps it
       took are what somebody watched go past whilst it ran, and reading them
       back as a list afterwards tells them nothing they can act on. A run
       where every step found its work already done is right and is over in a
       second, and "Finished" on its own reads as nothing having happened. */
    show("installer-note", progress.changed?.length
      ? t(`installer.finished.${progress.do}`)
      : t("installer.nothing-to-do"));
    return;
  }

  /* A failure says which step it was and what was put back, in the words the
     rest of the interface uses rather than as a line of shell output. */
  show("installer-caption", step);
  show("installer-note", [
    whyItFailed(progress.failed),
    progress.undone?.length
      ? t("installer.undone", {
          steps: progress.undone.map((name) => t(`setup.step.${name}`)).join(", "),
        })
      : "",
  ].filter(Boolean).join(" "));
}

/**
 * Why an installation stopped, as a sentence.
 * @param {object|null} failed - What the helper said, as `answers.told` shapes
 *   it, with the step it happened in beside it.
 * @returns {string}
 *
 * One of those answers carries counts of bytes, and bytes are the one value the
 * service cannot send ready to read: how large a number is worth writing out,
 * and how it is written, are questions about the language rather than about the
 * machine. So they are put into words here, as every other size in this window
 * is.
 */
function whyItFailed(failed) {
  if (!failed) return "";
  if (failed.reason !== "setup.no-room") return say(failed);
  return say({ ...failed, free: sized(failed.free),
               needed: sized(failed.needed) });
}

/**
 * Lets the window's buttons decide again, or turns them all off.
 * @param {boolean} allowed - False whilst something is being installed, because
 *   the service takes one installation at a time and a second request would be
 *   refused rather than queued.
 */
function allowInstalling(allowed) {
  const state = setupState;
  const here = Boolean(state?.emulator?.here);
  const chosen = state?.systems.find((system) => system.identifier === chosenSystem);

  document.getElementById("installer-install").disabled = !allowed || here;
  document.getElementById("installer-remove").disabled = !allowed || !here;
  /* Not there at all where the archive has nothing newer, because a button
     that would bring the version that is already here is a button that does
     nothing. */
  const update = document.getElementById("installer-update");
  update.hidden = !state?.emulator?.newer;
  update.disabled = !allowed || !here;

  document.getElementById("installer-fetch").disabled =
    !allowed || !chosen || chosen.here;
  document.getElementById("installer-forget").disabled =
    !allowed || !chosen || !chosen.here;
  /* A system that is not on the card cannot be started, and neither can the
     one the machine is already running. */
  document.getElementById("installer-activate").disabled =
    !allowed || !chosen || !chosen.here || Boolean(chosen.booting);
}

/**
 * Asks the service to install, update, remove or fetch something.
 * @param {string} job - One of Install.
 * @param {string} [system] - Which system, where the job needs one.
 *
 * Nothing waits for it to finish: the work takes minutes and happens on the Pi,
 * so what comes back is whether the request was taken, and the window follows
 * it from there.
 */
async function askTheInstaller(job, system) {
  waitingForTheHelper = true;
  theRunBefore = setupState?.progress?.started_at ?? null;
  askedAt = Date.now();
  whilstWaiting = t("installer.asking");
  drawWhatIsBeingInstalled(setupState?.progress ?? null);

  const answer = await tell(SETUP, { do: job, system: system ?? null });
  waitingForTheHelper = Boolean(answer?.ok);

  if (answer === null) {
    show("installer-note", t("note.no-service"));
    return;
  }
  /* What the service said, kept for as long as the window is waiting, because
     the draw that follows would otherwise wipe it before anybody reads it. */
  whilstWaiting = say(answer);
  show("installer-note", whilstWaiting);
  drawTheInstaller(answer.systems ? answer : setupState);
  refreshTheInstaller();
}

/** Wires the Installer's six buttons and the look it takes on its own. */
function wireTheInstaller() {
  const window_ = document.querySelector('nx-window[name="installer"]');
  if (!window_) return;

  document.getElementById("installer-install")
    .addEventListener("click", installTheEmulator);
  document.getElementById("installer-update")
    .addEventListener("click", updateTheEmulator);
  document.getElementById("installer-remove")
    .addEventListener("click", removeTheEmulator);
  document.getElementById("installer-fetch")
    .addEventListener("click", fetchTheSystem);
  document.getElementById("installer-forget")
    .addEventListener("click", forgetTheSystem);
  document.getElementById("installer-activate")
    .addEventListener("click", activateTheSystem);

  /* Opening it asks straight away, because a window that filled itself at the
     next poll would stand empty for a moment first. */
  window_.addEventListener("nx-open", refreshTheInstaller);

  /* Whilst the window is open, or whilst something is being installed with it
     closed: a run takes minutes and goes on whether anybody is watching, and
     what is on the screen when somebody comes back has to be true.

     Four times as often whilst something is happening. A run where every step
     finds its work already done is over in a second, and asking every two
     seconds would miss it entirely: somebody would press Install and see the
     window go from asked to finished with nothing in between, or nothing at
     all. */
  let ticks = 0;
  setInterval(() => {
    ticks += 1;
    const busy = waitingForTheHelper
      || (setupState?.progress && setupState.progress.finished_at === null);
    if (!busy && ticks % EVERY_FOURTH !== 0) return;
    if (!window_.hidden || busy) refreshTheInstaller();
  }, WATCHING_MS);

  if (!window_.hidden) refreshTheInstaller();
}

export {
  SETUP,
  Install,
  WATCHING_MS,
  EVERY_FOURTH,
  setupState,
  chosenSystem,
  INSTALLER_TABS,
  showingInTheInstaller,
  waitingForTheHelper,
  theRunBefore,
  askedAt,
  PATIENCE_MS,
  whilstWaiting,
  refreshTheInstaller,
  drawTheInstaller,
  drawTheTabs,
  emulatorLine,
  whatTheButtonsDo,
  drawTheSystems,
  drawWhatIsBeingInstalled,
  whyItFailed,
  allowInstalling,
  askTheInstaller,
  wireTheInstaller,
};
