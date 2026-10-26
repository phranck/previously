/* The Raspberry Pi window, which is about the board rather than the machine. */

import { t } from "../strings.js";
import { byId, show, showState } from "./page.js";
import { NOTHING, boardArt, costOf, duration, named, released, when } from "./words.js";

/** @typedef {import("../answers.js").PiAnswer} PiAnswer */

/** How often the status is fetched. A machine whose job is to sit there does
 *  not repay a faster poll than this. */
const REFRESH_MS = 5000;

/**
 * What stands under the board's picture, in this window and in Activity
 * Monitor alike.
 * @param {{model: string | null} | null} answer - What the service answered,
 *   carrying `model`, or null where it did not answer.
 * @returns {string} The board's model, or that the Pi cannot be reached.
 */
function modelOf(answer) {
  return answer === null ? t("state.unreachable") : (answer.model ?? NOTHING);
}

/**
 * Puts the drawing of the board the service runs on into a picture, in this
 * window and in Activity Monitor alike.
 * @param {string} id - The picture's id.
 * @param {{board: string | null} | null} answer - What the service answered,
 *   carrying `board`, or null where it did not answer. No answer leaves the
 *   picture as it stands, because a board that stops answering is still the
 *   board it was.
 */
function showBoard(id, answer) {
  if (answer === null) return;
  byId(id).style.backgroundImage = `var(--${boardArt(answer.board)})`;
}

/**
 * Draws what the board underneath is doing.
 * @param {PiAnswer | null} pi - What /api/pi answered, or null.
 */
function drawPi(pi) {
  show("pi-model", modelOf(pi));
  showBoard("pi-board", pi);
  /* Whether the buttons can be used is the system's state, which the status
     asked for at the same moment decides. */
  if (pi === null) return;

  show("pi-uptime", duration(pi.uptime_seconds));

  /* Where the board begins to slow itself down the reading stops being a
     number and becomes a warning. The service sends that limit, so this
     window marks the temperature a notification is raised for. */
  const temperature = pi.temperature_c;
  showState("pi-temp", temperature !== null && temperature < pi.temperature_limit_c,
    temperature === null ? NOTHING : `${temperature.toFixed(1)} °C`);

  /* Two different things. Something happening now is a problem to act on, and
     something that happened once may have been the moment a drive was plugged
     in, which is worth knowing and not worth alarm. */
  const throttling = pi.throttling;
  if (!throttling) {
    showState("pi-power", true, NOTHING);
  } else if (throttling.now.length) {
    showState("pi-power", false, t("pi.power.now", { what: named(throttling.now) }));
  } else if (throttling.since_boot.length) {
    showState("pi-power", false,
      t("pi.power.since-boot", { what: named(throttling.since_boot) }));
  } else {
    showState("pi-power", true, t("pi.power.fine"));
  }

  show("pi-emulator", costOf(pi.emulator));

  /* The one that looks like nothing: the card is there, the configuration
     still names it, and the stream was closed when the speaker was moved. */
  showState("pi-sound", Boolean(pi.sound?.playing), pi.sound
    ? t(pi.sound.playing ? "pi.sound.playing" : "pi.sound.silent", { card: pi.sound.card })
    : t("pi.sound.none"));

  /* Whether the emulator has ended badly since this board came up. A machine
     that has crashed four times in a morning looks exactly like one that has
     not, from a screen that shows NeXTSTEP either way. */
  showState("pi-crashes", !pi.crashes, pi.crashes
    ? t("pi.crashes.since", { count: pi.crashes.count, at: when(pi.crashes.last) })
    : t("pi.crashes.none"));

  show("pi-memory", pi.memory
    ? t("pi.memory.free",
        { available: pi.memory.available_mb, total: pi.memory.total_mb })
    : NOTHING);
  show("pi-disk", pi.disk
    ? t("pi.disk.free",
        { gb: Math.round(pi.disk.free_mb / 1024), percent: pi.disk.used_percent })
    : NOTHING);

  /* Which tool is answering. The one reading here that is about this program
     rather than about the board, and it is here because this is the window
     somebody opens to find out what a machine is running. The release alone:
     the build the service also reports is what apt orders packages by and is
     read off the Pi when somebody needs it. */
  show("pi-version", released(pi.version));
}

export {
  REFRESH_MS,
  drawPi,
  modelOf,
  showBoard,
};
