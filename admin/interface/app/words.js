/* What everything here is called, and how a figure is said. */

import { currentLocale, t } from "../strings.js";
/** What stands in a field that has nothing to say. An em dash rather than an
 *  empty field, because an empty one reads as a value that is missing and this
 *  one is a question that does not arise. */
const NOTHING = "—";

/** What the name of an application ends in. NeXTSTEP showed the whole file
 *  name, suffix and all, and this is a filesystem however made up it is. */
const APPLICATION = ".app";

/** Which window the Config Editor is. The tree names the same one as what
 *  `Config Editor.app` opens, and this is the one application here that is
 *  started on something rather than on nothing. */
const EDITOR = "editor";

/** What the pictures are called, by what they mean rather than by their file. */
const Art = {
  Computer: "root",
  Folder: "folder",
  Cube: "nextcube",
  Station: "nextstation",
  Editor: "defaultAppIcon",
  Installer: "Installer",
  Picture: "tiff",
  Disk: "winchester",
  /* NeXTSTEP 3.3 has no picture of a CD, so a disc wears the generic SCSI
     device, which is what a CD-ROM on the bus is. */
  Disc: "scsi",
};

/** Which picture a machine wears, by the case the service says it comes in.
 *  Both are the boot ROM's own drawings, so the shelf shows what the screen
 *  shows a second after a machine is chosen. */
const MACHINE_ART = {
  cube: Art.Cube,
  station: Art.Station,
};

/**
 * What the service just said, as a sentence.
 * @param {object|null} told - Its answer, carrying `reason` and whatever fills
 *   it.
 * @returns {string} The sentence in the language the interface speaks, or the
 *   bare name where no catalogue knows it, because a name on the screen is
 *   ugly and silence is worse.
 *
 * The service sends a name and the values that fill it, so this is a lookup
 * and nothing more. Three of its answers need one thing beyond their values:
 * two say how many, which decides singular against plural, and one says which
 * of two things the board is doing.
 */
function say(told) {
  if (!told?.reason) return "";
  const key = `told.${told.reason}`;
  /* The reason a change was rolled back is itself a name, and it stands in the
     middle of the sentence rather than beside it. */
  const values = told.why ? { ...told, why: t(`why.${told.why}`) } : told;

  if (told.reason === "board.on-its-way") return t(`${key}.${told.action}`, values);
  /* What the Pi was asked to do, which is five different things and therefore
     five sentences: one for all of them would say nothing about any. */
  if (told.reason === "setup.asked") return t(`${key}.${told.job}`, values);
  if (told.reason === "guest.still-shutting-down") return t(key, values, told.seconds);
  if (["machine.running", "disk.booting", "disc.inserted", "disc.ejected"]
      .includes(told.reason)) {
    return t(key, values, told.lines);
  }
  return t(key, values);
}

/**
 * What a machine is called, from the facts the service sent.
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The model's own name with what is fitted to it.
 *
 * The model is a product name and arrives as it is. What gets added to it is
 * a sentence, so it is added here.
 */
function nameOf(machine) {
  const name = modelOf(machine);
  return machine.dimension ? t("machine.with-dimension", { name }) : name;
}

/**
 * What the machine is called, and nothing about the boards in it.
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The model's own name, with Turbo where that is part of it.
 *
 * For the one place a whole sentence does not fit: a menu entry is a line in a
 * narrow column, and a machine named after everything fitted to it runs off
 * the end of it.
 */
function modelOf(machine) {
  let name = machine.model;
  if (machine.turbo && machine.kind !== 0) name += " Turbo";
  return name;
}

/**
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The processor and its clock.
 */
function cpuOf(machine) {
  return t("machine.cpu", { cpu: machine.cpu, mhz: machine.mhz });
}

/**
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} What the screen shows, which is where colour is decided.
 *
 * A cube has no colour of its own: Previous forces the flag off for that
 * machine type, and colour arrives only through a NeXTdimension.
 */
function screenOf(machine) {
  if (machine.dimension) return t("machine.screen.dimension");
  return t(machine.colour ? "machine.screen.colour" : "machine.screen.grey");
}

/**
 * @param {object} machine - A configuration or a catalogue entry.
 * @returns {string} The three chips that decide whether it runs at all.
 */
function chipsOf(machine) {
  return t(machine.nbic ? "machine.chips.with-nextbus" : "machine.chips.without-nextbus",
           { rtc: machine.rtc, scsi: machine.scsi });
}

/**
 * The picture for a machine.
 * @param {string|null} enclosure - What the service called its case.
 * @returns {string} The picture's name. A case nobody knows falls back to the
 *   generic computer, so a service that learns a new machine type before this
 *   page does still draws something.
 */
function machineArt(enclosure) {
  return MACHINE_ART[enclosure] ?? Art.Computer;
}

/**
 * Says how long something has been running, in the words a person uses.
 * @param {number|null} seconds
 * @returns {string}
 */
function since(seconds) {
  if (seconds === null || seconds === undefined) return "";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return t("since.hours", { hours, minutes: String(minutes).padStart(2, "0") });
  }
  if (minutes > 0) return t("since.minutes", { minutes });
  return t("since.less-than-a-minute");
}

/**
 * When a moment was, in the words a person here uses.
 * @param {number|null} seconds - A Unix timestamp.
 * @returns {string} The date and time, or an em dash where there is none.
 */
function when(seconds) {
  if (!seconds) return NOTHING;
  /* In the language the interface speaks, because a date written the German
     way in an English panel is a date somebody has to stop and read. */
  return new Date(seconds * 1000).toLocaleString(currentLocale(), {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

/**
 * When the configuration file was last written.
 * @param {object|undefined} file - What the service says about previous.cfg.
 * @returns {string} The moment, and a note where the running machine is older
 *   than the file. Previous reads the file once at its start, so anything
 *   written afterwards is a machine nobody has tried.
 */
function changedLine(file) {
  if (!file) return NOTHING;
  return t(file.newer_than_the_machine ? "file.changed-not-booted" : "file.changed",
           { when: when(file.changed_at) });
}

/**
 * Who wrote the configuration file last.
 * @param {object|undefined} file - What the service says about previous.cfg.
 * @returns {string} One of two sentences. Previously leaves a note of what it
 *   wrote, so a file that no longer matches that note came from somewhere
 *   else, and the two candidates are the emulator's own settings dialogue and
 *   somebody at the keyboard.
 */
function writtenLine(file) {
  if (!file) return NOTHING;
  return t(file.written_by_us ? "file.by-previously" : "file.by-previous-or-hand");
}

/**
 * How a machine's memory is made up.
 * @param {number[]} banks - The four banks in megabytes, empty ones as zero.
 * @returns {string} "4 × 32" where every filled bank is the same size, and
 *   "16 + 8" where they are not. Empty banks are left out: a bank with nothing
 *   in it is a socket, and nobody counts sockets.
 */
function fitted(banks) {
  const filled = banks.filter((size) => size > 0);
  if (!filled.length) return t("machine.banks-empty");
  return filled.every((size) => size === filled[0])
    ? `${filled.length} × ${filled[0]}`
    : filled.join(" + ");
}

/**
 * Says how long something has been running, the short way.
 * @param {number|null} seconds
 * @returns {string}
 */
function duration(seconds) {
  if (seconds === null || seconds === undefined) return NOTHING;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return t("duration.days", { days, hours }, days);
  if (hours > 0) return t("duration.hours", { hours, minutes });
  return t("duration.minutes", { minutes });
}

/**
 * What the board says about its power, in words.
 * @param {string[]} names - The service's names for it, such as
 *   `under-voltage`. It sends names rather than sentences for the same reason
 *   it does everywhere else: a sentence written there could only ever be in
 *   one language.
 * @returns {string} Them in one list, in the language the interface speaks.
 */
function named(names) {
  return names.map((name) => t(`throttling.${name}`)).join(", ");
}

/**
 * How large something is, in the words a person uses.
 * @param {number} bytes
 * @returns {string} Megabytes below a gigabyte and gigabytes above it, with the
 *   figure written the way the language being read writes one.
 */
function sized(bytes, fine) {
  /* @param fine - Whether to keep a decimal below a gigabyte. A figure that
     stands still says nothing about a download, so the counter keeps one and
     the list, where the number never moves, does not. */
  if (!bytes && bytes !== 0) return NOTHING;
  const gigabytes = bytes >= 1e9;
  const figure = new Intl.NumberFormat(currentLocale(),
    { maximumFractionDigits: gigabytes || fine ? 1 : 0 })
    .format(bytes / (gigabytes ? 1e9 : 1e6));
  return t(gigabytes ? "size.gb" : "size.mb", { size: figure });
}

export {
  NOTHING,
  APPLICATION,
  EDITOR,
  Art,
  MACHINE_ART,
  say,
  nameOf,
  modelOf,
  cpuOf,
  screenOf,
  chipsOf,
  machineArt,
  since,
  when,
  changedLine,
  writtenLine,
  fitted,
  duration,
  named,
  sized,
};
