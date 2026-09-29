/* Switching the board itself off, which takes the emulator down first. */

import { t } from "../strings.js";
import { show } from "./page.js";
import { askPanel } from "./panels.js";
import { Board, tell } from "./service.js";
import { allowActions, refresh } from "./status.js";
import { Art, say } from "./words.js";

/**
 * Asks before the whole machine goes, and says in which order.
 * @param {string} what - The wording on the acting button.
 * @param {string} question - Which question to put, by its name in the
 *   catalogue, because the two differ in what the board does afterwards.
 * @returns {Promise<boolean>}
 */
function warnAboutTheBoard(what, question) {
  return askPanel({
    title: "Raspberry Pi",
    text: [t(question), t("ask.board.order"), t("ask.board.loss")],
    icon: Art.Computer,
    confirm: what,
  });
}

/**
 * Runs one of the board's two actions and reports what came of it.
 * @param {string} route - One of Board.
 * @param {string} working - What to say while it happens.
 */
async function operateBoard(route, working) {
  allowActions(false);
  show("pi-note", working);

  const answer = await tell(route);

  /* A board that is going down answers nothing, and that is the ordinary case
     rather than a failure. Saying so beats a page that claims no contact. */
  show("pi-note", answer === null ? t("note.board-gone") : say(answer));

  /* Nothing is switched back on here. The next status decides: whilst the
     board is away it does not answer, and everything stays off until it does. */
  refresh();
}

/** Wires the board's own two buttons. */
function wireBoard() {
  /** @type {any} */ (document.getElementById("pi-reboot")).addEventListener("click", async () => {
    if (await warnAboutTheBoard(t("button.restart"), "ask.board.reboot")) {
      operateBoard(Board.Reboot, t("busy.board-restart"));
    }
  });

  /** @type {any} */ (document.getElementById("pi-poweroff")).addEventListener("click", async () => {
    if (await warnAboutTheBoard(t("button.power-off"), "ask.board.poweroff")) {
      operateBoard(Board.PowerOff, t("busy.board-poweroff"));
    }
  });
}

export {
  wireBoard,
};
