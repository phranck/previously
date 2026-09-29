/* The panels that ask before something changes, and the one that signs in. */

import { t } from "../strings.js";
import { ask, send } from "./service.js";
import { Art } from "./words.js";

/**
 * The one word and the one assumption every panel needs, put in front of what
 * the caller says.
 * @param {any} question - As the kit's ask takes it.
 * @returns {any} The same, with the safe button named and the acting one
 *   treated as dangerous until the caller says otherwise.
 *
 * The kit holds no words of its own, so they are named here and nowhere else.
 * Only the safe button has a word that fits everywhere, because Cancel says
 * the same thing whatever was asked. The acting button never does: its label
 * is the verb naming what it will do, so every caller names it and there is no
 * default to fall back to. A panel whose acting button said Yes would be one
 * whose text has to be read before it can be answered.
 *
 * Dangerous by default, which turns the kit's own default round, and the kit
 * is the one following the chapter. The reason is what these panels are for:
 * of the twenty, fourteen stop a running machine or take something away that
 * does not come back, and a panel is put up here precisely because something
 * is about to be lost. Written the other way round, a panel added later and
 * not thought about would answer the Return key, and the failure would be
 * silent and irreversible. This way it costs a click that was not needed.
 */
function worded(question) {
  return { cancel: t("button.cancel"), dangerous: true, ...question };
}

/**
 * Puts a question.
 * @param {any} question
 * @returns {Promise<boolean>} Whether the acting button was pressed.
 */
function askPanel(question) {
  return /** @type {any} */ (document.getElementById("ask")).ask(worded(question));
}

/**
 * Puts a question that needs something typed.
 * @param {any} question
 * @returns {Promise<string|null>} What was typed, or null.
 */
function askPanelFor(question) {
  return /** @type {any} */ (document.getElementById("ask")).askFor(worded(question));
}

/**
 * Puts whichever question about the password this machine is due.
 * @param {string} [why] - A first line saying what prompted it.
 * @returns {Promise<boolean>} Whether this browser may now change something.
 *
 * Three states and one entry point, because whoever reaches this wants to get
 * past it rather than to know which of the three they are in. A machine nobody
 * has claimed asks for a password to set, one that is claimed asks for the
 * password it has, and a browser that is already signed in is offered a new
 * one, which is how a password is changed without going near the Pi.
 */
async function askForPassword(why) {
  const state = await ask("/api/session");
  if (state === null) return false;
  if (!state.claimed) return chooseThePassword(why, "ask.password.unclaimed", state);
  if (state.signed_in) return chooseThePassword(why, "ask.password.change", state);
  return signIn(why);
}

/**
 * Asks for the password this machine has, until it is given or the panel is
 * dismissed.
 * @param {string} [why] - A first line saying what prompted it.
 * @returns {Promise<boolean>} Whether the service accepted it.
 */
async function signIn(why) {
  let complaint = why;

  for (;;) {
    const typed = await askPanelFor({
      name: t("ask.password.title"),
      text: [complaint, t("ask.password.sign-in")].filter(Boolean),
      icon: Art.Computer,
      confirm: t("button.use"),
      secret: true,
      dangerous: false,
    });
    if (typed === null) return false;

    const answer = await send("/api/session", { password: typed });
    if (answer === null) return false;
    if (answer.ok) return true;
    /* A service that has been asked too often says so, because the next
       attempt will fail however right it is. */
    complaint = t(answer.status === 429 ? "ask.password.too-often" : "ask.password.wrong");
  }
}

/**
 * Asks for a password to set, until one is accepted or the panel is dismissed.
 * @param {string} why - A first line saying what prompted it, which is
 *   empty rather than absent where there is none. Not optional, because two
 *   required parameters follow it.
 * @param {string} what - Which sentence explains the question, by its key.
 * @param {any} state - What /api/session answered, which says how short a
 *   password may be. Read from the service rather than stated here, so the
 *   rule lives where it is enforced.
 * @returns {Promise<boolean>} Whether one was set.
 */
async function chooseThePassword(why, what, state) {
  let complaint = why;

  for (;;) {
    const typed = await askPanelFor({
      name: t("ask.password.title"),
      text: [complaint, t(what),
             t("ask.password.length", { least: state.smallest })].filter(Boolean),
      icon: Art.Computer,
      confirm: t("button.use"),
      secret: true,
      dangerous: false,
    });
    if (typed === null) return false;

    const answer = await send("/api/password", { password: typed });
    if (answer === null) return false;
    if (answer.ok) return true;
    /* Somebody else claimed this machine whilst the panel stood open, so what
       is due now is the password they chose rather than one of ours. */
    if (answer.status === 403) return signIn(t("ask.password.needed"));
    complaint = t(answer.status === 400
      ? "ask.password.too-short" : "ask.password.not-kept");
  }
}

export {
  askPanel,
  askPanelFor,
  askForPassword,
};
