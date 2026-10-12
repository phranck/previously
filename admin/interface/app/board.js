/* Switching the board itself off, which takes the emulator down first. */

import { t } from "../strings.js";
import { wasTaken } from "./outcome.js";
import { show } from "./page.js";
import { askPanel } from "./panels.js";
import { Board, tell } from "./service.js";
import { refresh } from "./status.js";
import { Needs, begin, end, hold } from "./system.js";
import { Art, say } from "./words.js";

/**
 * Asks before the whole machine goes, and says in which order.
 * @param {string} what - The wording on the acting button.
 * @param {string} question - Which question to put, by its name in the
 *   catalog, because the two differ in what the board does afterwards.
 * @returns {Promise<boolean>}
 */
function warnAboutTheBoard(what, question) {
  return askPanel({
    name: "Raspberry Pi",
    text: [t(question), t("ask.board.order"), t("ask.board.loss")],
    icon: Art.Computer,
    confirm: what,
  });
}

/**
 * Runs one of the board's two actions and reports what came of it.
 * @param {string} route - One of Board.
 * @param {string} working - What to say while it happens.
 *
 * The operation lasts until the board has gone and answered again, rather than
 * until its request comes back: the service answers before the board goes
 * down, and for the minute after that nothing on the page can be done. A board
 * switched off never answers again, and the page says so for as long as it is
 * open.
 */
async function operateBoard(route, working) {
  show("pi-note", "");
  begin(working, true);

  const answer = await tell(route);

  /* Not taken, so nothing is going away and the operation is over now. That
     is any answer but the one saying it was taken: a refusal carries no `ok`
     at all, and waiting on it for a board that comes back would hold every
     control until the page is reloaded. */
  if (answer !== null && !wasTaken(answer)) end();

  /* A board that is going down answers nothing, and that is the ordinary case
     rather than a failure. Saying so beats a page that claims no contact. */
  show("pi-note", answer === null ? t("note.board-gone") : say(answer));
  refresh();
}

/** Wires the board's own two buttons. */
function wireBoard() {
  hold("#pi-reboot", Needs.Quiet);
  hold("#pi-poweroff", Needs.Quiet);

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
