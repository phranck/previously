/* What everything here is called, and how a figure is said. */

import { currentLocale, t } from "../strings.js";

/** @typedef {import("../answers.js").Said} Said */
/** @typedef {import("../answers.js").MachineFacts} MachineFacts */
/** @typedef {import("../answers.js").ConfigurationFile} ConfigurationFile */
/** @typedef {import("../answers.js").EmulatorCost} EmulatorCost */

/** What stands in a field that has nothing to say. An em dash rather than an
 *  empty field, because an empty one reads as a value that is missing and this
 *  one is a question that does not arise. */
const NOTHING = "—";

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
const MACHINE_ART = new Map([
  ["cube", Art.Cube],
  ["station", Art.Station],
]);

/**
 * What the service just said, as a sentence.
 * @param {Said | null | undefined} told - Its answer, carrying `reason` and
 *   whatever fills it, or a refusal, which names nothing and says nothing.
 * @returns {string} The sentence in the language the interface speaks, or the
 *   bare name where no catalog knows it, because a name on the screen is
 *   ugly and silence is worse.
 *
 * The service sends a name and the values that fill it, so this is mostly a
 * lookup. Some answers need one thing beyond their values: a count decides
 * singular against plural, a job or an action picks the sentence, and a count
 * of bytes is put into words here, as every other size in this interface is.
 */
function say(told) {
  if (!told || !("reason" in told)) return "";
  const key = `told.${told.reason}`;
  /* The reason a change was rolled back is itself a name, and it stands in the
     middle of the sentence rather than beside it. */
  const values = "why" in told ? { ...told, why: t(`why.${told.why}`) } : told;

  /* Bytes are the one value the service cannot send ready to read: how large a
     number is worth writing out, and how it is written, are questions about
     the language rather than about the machine. */
  if (told.reason === "setup.no-room") {
    return t(key, { ...values, free: sized(told.free), needed: sized(told.needed) });
  }
  if (told.reason === "setup.no-room-until-restart") {
    return t(key, { ...values, free: sized(told.free), needed: sized(told.needed),
                    back: sized(told.back) });
  }
  if (told.reason === "board.on-its-way") return t(`${key}.${told.action}`, values);
  /* What the Pi was asked to do, which is five different things and therefore
     five sentences: one for all of them would say nothing about any. */
  if (told.reason === "setup.asked") return t(`${key}.${told.job}`, values);
  if (told.reason === "guest.still-shutting-down") return t(key, values, told.seconds);
  if (told.reason === "machine.running" || told.reason === "disk.booting"
      || told.reason === "disc.inserted" || told.reason === "disc.ejected") {
    return t(key, values, told.lines);
  }
  return t(key, values);
}

/**
 * What a machine is called, from the facts the service sent.
 * @param {MachineFacts} machine - A configuration or a catalog entry.
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
 * @param {MachineFacts} machine - A configuration or a catalog entry.
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
 * @param {MachineFacts} machine - A configuration or a catalog entry.
 * @returns {string} The processor and its clock.
 */
function cpuOf(machine) {
  return t("machine.cpu", { cpu: machine.cpu, mhz: machine.mhz });
}

/**
 * @param {MachineFacts} machine - A configuration or a catalog entry.
 * @returns {string} What the screen shows, which is where color is decided.
 *
 * A cube has no color of its own: Previous's own dialog switches the flag off
 * for that machine type, and color arrives only through a NeXTdimension.
 */
function screenOf(machine) {
  if (machine.dimension) return t("machine.screen.dimension");
  return t(machine.colour ? "machine.screen.colour" : "machine.screen.grey");
}

/**
 * @param {MachineFacts} machine - A configuration or a catalog entry.
 * @returns {string} The three chips that decide whether it runs at all.
 */
function chipsOf(machine) {
  return t(machine.nbic ? "machine.chips.with-nextbus" : "machine.chips.without-nextbus",
           { rtc: machine.rtc, scsi: machine.scsi });
}

/**
 * The picture for a machine.
 * @param {string | null | undefined} enclosure - What the service called its
 *   case.
 * @returns {string} The picture's name. A case nobody knows falls back to the
 *   generic computer, so a service that learns a new machine type before this
 *   page does still draws something.
 */
function machineArt(enclosure) {
  return MACHINE_ART.get(enclosure ?? "") ?? Art.Computer;
}

/**
 * Says how long something has been running, in the words a person uses.
 * @param {number | null | undefined} seconds
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
 * @param {number | null | undefined} seconds - A Unix timestamp.
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
 * @param {ConfigurationFile | null | undefined} file - What the service says
 *   about previous.cfg.
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
 * @param {ConfigurationFile | null | undefined} file - What the service says
 *   about previous.cfg.
 * @returns {string} One of two sentences. Previously leaves a note of what it
 *   wrote, so a file that no longer matches that note came from somewhere
 *   else, and the two candidates are the emulator's own settings dialog and
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
 * @param {number | null | undefined} seconds
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
 * What the emulator is costing, as one line.
 * @param {EmulatorCost | null | undefined} emulator - What the service says
 *   about it, or null where it is not running.
 * @returns {string}
 *
 * The Raspberry Pi window and Activity Monitor both say this, and they say it
 * the same way. The percentage is of one core, so around 150 is ordinary with
 * a NeXTdimension, whose second thread runs beside the first, and the figure
 * is stated without judging it. A figure the service could not work out yet,
 * which is the first answer after a pause, stands as a dash.
 */
function costOf(emulator) {
  if (!emulator) return t("pi.emulator.stopped");
  return t("pi.emulator.running", {
    percent: emulator.cpu_percent === null ? NOTHING : Math.round(emulator.cpu_percent),
    mb: emulator.memory_mb ?? NOTHING,
    uptime: duration(emulator.uptime_seconds),
  });
}

/**
 * A figure with two places after the point, written the way the language
 * being read writes one.
 * @param {number} value
 * @returns {string} Two places, which is how the kernel writes a load average
 *   and how every tool that shows one has shown it.
 */
function decimal(value) {
  return new Intl.NumberFormat(currentLocale(),
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
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
 * @param {number | null | undefined} bytes
 * @param {boolean} [fine] - Whether to keep a decimal below a gigabyte. A
 *   figure that stands still says nothing about a download, so the counter
 *   keeps one and the list, where the number never moves, does not.
 * @returns {string} Megabytes below a gigabyte and gigabytes above it, with the
 *   figure written the way the language being read writes one.
 */
function sized(bytes, fine) {
  if (!bytes && bytes !== 0) return NOTHING;
  const gigabytes = bytes >= 1e9;
  const figure = new Intl.NumberFormat(currentLocale(),
    { maximumFractionDigits: gigabytes || fine ? 1 : 0 })
    .format(bytes / (gigabytes ? 1e9 : 1e6));
  return t(gigabytes ? "size.gb" : "size.mb", { size: figure });
}

/** Megabytes in a gigabyte of memory. Memory is counted in powers of two, which
 *  is how the kernel reports it and how a board is sold: a 4 GB Pi 5 reports
 *  4049 MB, which is 4.0 GB this way and 4.2 the way a disk is counted. */
const MEGABYTES_IN_A_GIGABYTE = 1024;

/**
 * How much of the memory is in use, the short way.
 * @param {number | null} used - Megabytes in use.
 * @param {number | null} total - Megabytes there are.
 * @returns {string} Both figures in the unit the total reads in, such as
 *   `1.2/4.0 GB`, or an em dash where either is missing.
 *
 * One unit for both, so the line stays short beside a row of lamps. In
 * gigabytes both keep one place after the point even where it is a zero, so
 * the figure holds its width while it changes under somebody reading it.
 */
function memoryInUse(used, total) {
  if (used === null || total === null
      || !Number.isFinite(used) || !Number.isFinite(total)) return NOTHING;
  const gigabytes = total >= MEGABYTES_IN_A_GIGABYTE;
  const places = gigabytes ? 1 : 0;
  const format = new Intl.NumberFormat(currentLocale(),
    { minimumFractionDigits: places, maximumFractionDigits: places });
  const scale = gigabytes ? MEGABYTES_IN_A_GIGABYTE : 1;
  return t(gigabytes ? "size.gb" : "size.mb",
    { size: `${format.format(used / scale)}/${format.format(total / scale)}` });
}

/** Where a version stops being the release and starts being the build. The
 *  release is digits and periods, and a package built between two releases
 *  carries how far it stands from a tag and which commit it is after a `+` or
 *  a `~`. */
const RELEASE_IN = /^\d+(?:\.\d+)*/;

/**
 * A version of this tool, as a person reads one.
 * @param {string | null | undefined} version - What the service reports, which
 *   for a build between two releases is something like `1.0.0+35.g553551d`.
 * @returns {string} The release alone, so `1.0.0`. A version this does not
 *   recognize is shown whole rather than swallowed, because a string nobody
 *   expected is still better on the screen than nothing.
 *
 * The build is dropped here rather than at the service, which goes on reporting
 * it: apt orders packages by it, and `dpkg-query -W previously` on the Pi is
 * where somebody reads it when they need it. What it buys on a screen is
 * nothing, and it costs the whole line.
 *
 * Only for versions of this tool. The emulator's is Debian's, and `4.3-0wmlive1`
 * cut down to `4.3` would name a version that does not exist.
 */
function released(version) {
  if (!version) return NOTHING;
  return RELEASE_IN.exec(version)?.[0] ?? version;
}

export {
  Art,
  EDITOR,
  NOTHING,
  changedLine,
  chipsOf,
  costOf,
  cpuOf,
  decimal,
  duration,
  fitted,
  machineArt,
  memoryInUse,
  modelOf,
  nameOf,
  named,
  released,
  say,
  screenOf,
  since,
  sized,
  when,
  writtenLine,
};
