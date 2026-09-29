/* The Raspberry Pi window, which is about the board rather than the machine. */

import { t } from "../strings.js";
import { show, showState } from "./page.js";
import { allowActions } from "./status.js";
import { NOTHING, duration, named, released, when } from "./words.js";

/** How often the status is fetched. A machine whose job is to sit there does
 *  not repay a faster poll than this. */
const REFRESH_MS = 5000;

/**
 * Draws what the board underneath is doing.
 * @param {any} pi - What /api/pi answered, or null.
 */
function drawPi(pi) {
  if (pi === null) {
    show("pi-model", t("state.unreachable"));
    allowActions(false);
    return;
  }

  show("pi-model", pi.model ?? NOTHING);
  show("pi-uptime", duration(pi.uptime_seconds));

  /* Above 80 degrees a Pi 5 begins to slow itself down, so that is where the
     reading stops being a number and becomes a warning. */
  const temperature = pi.temperature_c;
  showState("pi-temp", temperature !== null && temperature < 80,
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

  /* Around 150 per cent of one core is ordinary with a NeXTdimension, because
     two threads run, so the figure is stated without judging it. */
  show("pi-emulator", pi.emulator
    ? t("pi.emulator.running", {
        percent: Math.round(pi.emulator.cpu_percent),
        mb: pi.emulator.memory_mb,
        uptime: duration(pi.emulator.uptime_seconds),
      })
    : t("pi.emulator.stopped"));

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
};
