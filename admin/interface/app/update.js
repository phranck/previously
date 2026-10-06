/* Replacing this tool with the newest release, from the Raspberry Pi window.
 *
 * The one thing on this page that takes the page's own service away while it
 * runs. Everything else this interface asks for is done to the emulated machine
 * or to the board; this replaces the program answering the request, so half way
 * through there is nothing on the other end.
 *
 * What makes that watchable is where the record lives. The privileged helper
 * writes how far it has got into root's own runtime directory, which outlives
 * the service being stopped and started, so the page reads the same run before
 * and after and never has to hold the progress itself.
 */

import { t } from "../strings.js";
import { show } from "./page.js";
import { showTheReleaseNotes } from "./preview.js";
import { ask, tell } from "./service.js";
import { released, say, sized } from "./words.js";

/** Where the update asks and tells. One address for both, because what comes
 *  back from asking is what the window shows anyway. */
const UPDATE = "/api/update";

/** How often to look while something is happening. The download is a quarter
 *  of a megabyte and the whole run is over in well under a minute, so the five
 *  second poll the rest of this window takes would show two frames of it. */
const WATCHING_MS = 500;

/** And how many of those to skip while nothing is. Every fourth, which is the
 *  window's own two seconds. */
const EVERY_FOURTH = 4;

/** How long the helper may take to start before the window says it has not. A
 *  path unit fires within a second of the request appearing, so anything past
 *  this is a machine whose helper is not there rather than one that is slow. */
const PATIENCE_MS = 30000;

/** The last thing /api/update said, so the window can be drawn again in another
 *  language, and so a moment with no service still has something to show. */
let updateState = null;

/** Whether the request has been left and the helper has not started yet. The
 *  request goes into a file and a path unit starts the program that reads it, so
 *  for a moment after the answer comes back the newest thing the Pi has to say
 *  is still about the run before. */
let waitingForTheHelper = false;

/** Which run was showing when that request was left, by the moment it started,
 *  so the one that follows it can be told apart from it. */
let theRunBefore = null;

/** When it was left, by this browser's clock, so waiting for ever is not one of
 *  the states this window has. */
let askedAt = 0;

/** Whether somebody pressed the button on this page.
 *
 *  What decides whether a finished run is reported at all. Whoever asked for it
 *  is owed the sentence saying it worked, and whoever opens this window tomorrow
 *  is owed what the state is now, while the record on the Pi says the same
 *  thing to both until the next boot. Never put back, because the page is not
 *  reloaded by the replacement: the service goes and comes back underneath it.
 */
let weAskedForOne = false;

/**
 * Asks what is installed, what is published and how a run is getting on.
 * @param {boolean} [check] - Whether to have the Pi ask GitHub again. True when
 *   somebody opens this window, and false for the poll that redraws it while
 *   it is open: an address may ask GitHub sixty times an hour, and a loop
 *   would spend that in twenty minutes.
 */
async function refreshTheUpdate(check) {
  drawTheUpdate(await ask(check ? `${UPDATE}?check=1` : UPDATE));
}

/**
 * Draws the version line, the trough and the sentence under it.
 * @param {any} state - What /api/update answered, or null on no contact.
 */
function drawTheUpdate(state) {
  if (state === null) {
    /* While a replacement is running, no contact is what a replacement looks
       like from here rather than a failure: the service is stopped and started
       by the package being installed. So the last reading is kept and the
       sentence says what is happening, and the poll carries on until the new
       service answers. */
    offerTheUpdate(false);
    if (replacing()) show("pi-update-note", t("pi.update.away"));
    return;
  }
  updateState = state;

  /* The release alone, because the build on the end of what the service reports
     is what apt orders packages by and says nothing to a reader. */
  show("pi-newest", released(state.published));
  /* And marked where it is not the version answering, so the line somebody is
     reading says so rather than only the button at the foot of the window. */
  /** @type {any} */ (document.getElementById("pi-newest"))
    .toggleAttribute("newer", Boolean(state.newer));
  /* What that release says about itself can be read whenever there is a release
     to read about, whether it is newer than this one or not. */
  /** @type {any} */ (document.getElementById("pi-notes")).disabled =
    state.published === null;
  drawWhatIsHappening(state);
}

/**
 * Says how a replacement is getting on, or what there is to do.
 * @param {any} state - What /api/update answered.
 */
function drawWhatIsHappening(state) {
  const gauge = /** @type {any} */ (document.getElementById("pi-update-gauge"));
  const progress = state.progress;

  /* Anything the Pi is still showing from before the request is the run before
     this one, so the window keeps saying it was asked rather than reading out
     that one's ending. */
  if (waitingForTheHelper && Boolean(progress)
      && progress.started_at !== theRunBefore) {
    waitingForTheHelper = false;
  }
  if (waitingForTheHelper) {
    const tooLong = Date.now() - askedAt > PATIENCE_MS;
    offerTheUpdate(tooLong && state.newer);
    gauge.hidden = true;
    show("pi-update-note",
         t(tooLong ? "installer.not-started.why" : "pi.update.asked"));
    return;
  }

  const running = Boolean(progress) && progress.finished_at === null;
  gauge.hidden = !running;
  offerTheUpdate(!running && state.newer);

  if (running) return drawHowFarItHasGot(progress);
  if (progress && !progress.ok) return drawWhyItStopped(progress);
  if (progress && weAskedForOne) {
    return show("pi-update-note",
                t("pi.update.done", { version: released(state.installed) }));
  }

  /* Nothing has been asked for, so the sentence is what there is to do. Which
     version would come is the whole of why somebody would press the button, so
     it is named rather than left to the line above. */
  if (state.published === null) {
    return show("pi-update-note", t("pi.update.unknown"));
  }
  show("pi-update-note", state.newer
    ? t("pi.update.available", { version: released(state.published) })
    : t("pi.update.current"));
}

/**
 * Fills the trough and says which step of how many.
 * @param {any} progress - What the helper wrote.
 *
 * Two measures in one bar: which step of how many, and how far through a step
 * that knows. Only the download knows, and the step after it is where the
 * service goes away, which is the part nobody can see for themselves.
 */
function drawHowFarItHasGot(progress) {
  show("pi-update-note", [
    t(`setup.step.${progress.step}`),
    t("installer.step", { done: progress.done, of: progress.of }),
    progress.part
      ? t(`installer.doing.${progress.part.doing}`, {
          done: sized(progress.part.done, true),
          of: sized(progress.part.of, true),
        })
      : "",
  ].filter(Boolean).join(" "));

  const through = progress.part?.of ? progress.part.done / progress.part.of : 0;
  const done = (progress.done - 1 + Math.min(1, through)) / progress.of;
  /** @type {any} */ (document.getElementById("pi-update-fill")).style.width =
    `${Math.round(done * 100)}%`;
}

/**
 * Says which step stopped it and why, in words rather than as shell output.
 * @param {any} progress - What the helper wrote.
 *
 * Always, whoever is reading. A failed replacement leaves the tool that is here
 * running, which is the safe direction and also the one nothing else on the page
 * would mention, so the reason stands until something else is asked for.
 */
function drawWhyItStopped(progress) {
  show("pi-update-note", [
    t(`setup.step.${progress.step}`),
    say(progress.failed),
  ].filter(Boolean).join(" "));
}

/**
 * Whether a replacement is under way as far as this page knows.
 * @returns {boolean}
 *
 * Read off the record rather than held as a flag of its own, because that record
 * is what decides it and this page is not the only thing that can start one.
 */
function replacing() {
  return waitingForTheHelper
    || Boolean(updateState?.progress
               && updateState.progress.finished_at === null);
}

/**
 * Shows the button or takes it away.
 * @param {boolean} offered - Whether there is something newer to put in place
 *   and nothing in the way of doing it.
 *
 * Away rather than disabled where there is nothing newer, because a button that
 * would put the version already here back is a button that does nothing.
 * Disabled while a run is on, because the helper takes one job at a time and a
 * second request is refused rather than queued.
 */
function offerTheUpdate(offered) {
  const button = /** @type {any} */ (document.getElementById("pi-update"));
  button.hidden = !updateState?.newer;
  button.disabled = !offered;
}

/**
 * Asks the Pi to replace this tool with the newest release.
 *
 * Nothing waits for it to finish, and nothing could: the run stops the service
 * this request was sent to. What comes back says whether the request was taken,
 * and the window follows it from there.
 */
async function askForTheNewest() {
  waitingForTheHelper = true;
  weAskedForOne = true;
  theRunBefore = updateState?.progress?.started_at ?? null;
  askedAt = Date.now();
  show("pi-update-note", t("pi.update.asked"));
  offerTheUpdate(false);

  const answer = await tell(UPDATE);
  waitingForTheHelper = Boolean(answer?.ok);

  if (answer === null) {
    show("pi-update-note", t("note.no-service"));
    return;
  }
  if (!answer.ok) {
    /* Refused before anything started, which is the case worth saying at once:
       there is nothing newer, or the helper is already busy with something
       else. */
    show("pi-update-note", say(answer));
  }
  drawTheUpdate(answer.published === undefined ? updateState : answer);
}

/** Wires the button and the look the window takes on its own. */
function wireTheUpdate() {
  const window_ = /** @type {any} */ (
    document.querySelector('nx-window[name="pi"]'));
  if (!window_) return;

  /** @type {any} */ (document.getElementById("pi-update"))
    .addEventListener("click", askForTheNewest);
  /** @type {any} */ (document.getElementById("pi-notes"))
    .addEventListener("click", showTheReleaseNotes);

  /* Opening it asks straight away, because a window that filled itself at the
     next poll would stand empty for a moment first, and this is also the one
     moment that has the Pi ask GitHub. A release published while somebody sits
     in front of this window therefore turns up when they close it and open it
     again, which is what keeps a window left open from spending the sixty
     requests an hour an address is allowed. */
  window_.addEventListener("nx-open", () => refreshTheUpdate(true));

  /* While the window is open, or while a replacement is running with it
     closed. The second matters more than it looks: the service goes away in the
     middle, and the page that comes back to it has to be able to say what
     happened rather than showing the state from before. */
  let ticks = 0;
  setInterval(() => {
    ticks += 1;
    const busy = replacing();
    if (!busy && ticks % EVERY_FOURTH !== 0) return;
    if (!window_.hidden || busy) refreshTheUpdate(false);
  }, WATCHING_MS);

  /* Open already, which is where the desk came back with it open. That is an
     opening too, so it asks. */
  if (!window_.hidden) refreshTheUpdate(true);
}

export {
  UPDATE,
  refreshTheUpdate,
  drawTheUpdate,
  askForTheNewest,
  wireTheUpdate,
};
