// What the service answers, one type per route of its JSON API.
//
// The service is admin/previously/server.py, and every JSON body it sends goes
// through `Handler._json`. Each type below names the route and the Python
// function that builds the body.
//
// A GET is read by `ask` in interface/app/service.js, which hands over the body
// of a 2xx answer only. A POST is read by `tell`, which hands over the body of
// every answer whatever its status, so each POST type below is the union of
// every body that route can send, refusals included.
//
// Where the Python code draws a value from a table of its own, such as the
// steps of a job or the names of the systems, the value is a `string` here: the
// interface reads it as a key into its catalogs and never decides anything by
// it, and a copy of the table would be a second list to keep in step. Only a
// set the interface branches on is spelled out. The names of what happened are
// the one large set spelled out, because `say` decides by them, and
// tests/test_strings.py holds them to the service.

/* -- values that can arrive in a request and are echoed back ------------- */

/** Any JSON value. A few refusals hand a posted value back unchanged. */
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/** A posted value that has passed through a dict lookup on its way back, so a
 *  list or an object never returns here. */
export type JsonScalar = string | number | boolean | null;

/* -- the sets the interface branches on ------------------------------------- */

/** What the board itself can be asked to do, as kiosk.BOARD_REQUESTS. */
export type BoardAction = "reboot" | "poweroff";

/** Which DSP, as machines.DSPS. The editor keys its notes by these. */
export type DspKind = "none" | "plain" | "with-rom";

/** Which case a machine stands in, from config.enclosure, which answers "cube"
 *  for a type it does not know. The pictures are keyed by these. */
export type Enclosure = "cube" | "station";

/* -- what happened, as a name and the values that fill it ------------------ */

/**
 * Every name `answers.told` is called with, and the values each one carries
 * beside `reason`. The browser turns the name into a sentence through
 * `told.<reason>` in interface/lang/.
 */
export interface ToldValues {
  // kiosk.stop
  "emulator.was-not-running": {};
  "emulator.ended-because-blank": {};
  "emulator.blank-and-will-not-end": {};
  "emulator.power-key-refused": {};
  /** `seconds` is the timeout that ran out. */
  "guest.still-shutting-down": { seconds: number };
  "guest.shut-itself-down": {};

  // kiosk.start
  "emulator.already-running": {};
  "emulator.nothing-holding-it": {};
  "emulator.on-its-way-back": {};

  // kiosk.board
  "board.no-such-action": { action: string };
  "board.request-refused": { action: BoardAction };
  "board.on-its-way": { action: BoardAction };

  // kiosk.ask_to_set_up
  "setup.no-such-job": {};
  "setup.no-such-system": {};
  "setup.no-such-machine": {};
  "setup.one-at-a-time": {};
  "setup.request-refused": {};
  /** `job` is one of setup.JOBS. */
  "setup.asked": { job: string };

  // change.to_machine, to_disk, to_disc, eject_disc
  /** `asked` is the posted `machine`, handed back. */
  "machine.no-such": { asked: JsonScalar };
  /** `asked` is the posted `disk`, handed back. */
  "disk.no-such": { asked: JsonScalar };
  /** `name` is the system's name. */
  "disk.not-here": { name: string };
  "disc.no-such": {};
  "disc.no-free-slot": {};
  "disc.no-such-slot": {};
  "disc.that-is-the-disk": {};
  "disc.nothing-there": {};

  // change._applied and change._rolled_back
  /** `detail` is the text of config.NotReadable. */
  "file.not-readable": { detail: string };
  /** `machine` is what was chosen: a machine's name, a system's name, or a
   *  disc's file name. `lines` is how many lines of previous.cfg changed. */
  "machine.running": { machine: string; lines: number };
  "machine.was-already-set": { machine: string };
  "disk.booting": { machine: string; lines: number };
  "disk.was-already-set": { machine: string };
  "disc.inserted": { machine: string; lines: number };
  "disc.was-already-in": { machine: string };
  "disc.ejected": { machine: string; lines: number };
  "disc.was-already-out": { machine: string };
  /** `why` names what made the change go back, as `why.<why>` in the
   *  catalogs. `detail` is the OSError's text. */
  "rollback.could-not-write": { machine: string; why: string; detail: string };
  "rollback.emulator-will-not-end": { machine: string; why: string };
  "rollback.back-as-before": { machine: string; why: string };
  "rollback.nothing-runs": { machine: string; why: string };

  // saved.save, rename, remove and _why_not
  /** `detail` is the text of saved.NotReadable. */
  "saved.not-readable": { detail: string };
  /** `asked` is the posted `replacing` or `machine`, handed back. It is
   *  compared by equality and never looked up, so any JSON value can return
   *  here, and null where `machine` was absent. */
  "saved.no-such": { asked: JsonValue };
  "saved.kept": { name: string };
  /** `was` is the name it had. */
  "saved.renamed": { name: string; was: string };
  "saved.removed": { name: string };
  "saved.name-needed": {};
  /** `most` is saved.LONGEST_NAME. */
  "saved.name-too-long": { most: number };
  "saved.name-has-a-separator": {};
  "saved.name-has-a-control-character": {};
  "saved.name-taken": { name: string };
  /** `detail` is the OSError's text. */
  "saved.could-not-write": { detail: string };

  // setup.Refused and setup._said_of
  /** `command` is the program's name, `seconds` the limit. */
  "setup.took-too-long": { command: string; seconds: number };
  "setup.no-such-command": { command: string };
  /** `code` is the exit status. */
  "setup.command-failed": { command: string; code: number };
  "setup.no-owner": {};
  "setup.wrong-architecture": { found: string; wanted: string };
  /** `found` is "?" where /etc/os-release says nothing. */
  "setup.wrong-release": { found: string; wanted: string };
  /** `free`, `needed` and `back` are bytes, and `back` is what the next boot
   *  gives back. */
  "setup.no-room-until-restart": { free: number; needed: number; back: number; name: string };
  /** `free` and `needed` are bytes. */
  "setup.no-room": { free: number; needed: number; name: string };
  /** `version` is "?" where dpkg knows none. */
  "setup.tool-is-current": { version: string };
  "setup.no-package-to-install": {};
  "setup.cannot-ask-about-releases": {};
  "setup.not-our-package": { found: string };
  "setup.not-that-version": { found: string; wanted: string };
  "setup.no-system-named": {};
  "setup.system-is-not-here": { name: string };
  "setup.system-in-use": { name: string };
  "setup.machine-is-running": {};
  "setup.no-such-copy": {};
  /** `name` is "?" where the run names no system. */
  "setup.cannot-copy": { name: string };
  /** `name` is the expected file's name, or the address where nothing is
   *  expected of it. */
  "setup.cannot-fetch": { name: string };
  "setup.not-what-was-expected": { name: string };
  /** `name` is "?" where the run names no system. */
  "setup.cannot-unpack": { name: string };
  "setup.no-disk-in-the-archive": { name: string };
  /** `error` is the OSError's text. */
  "setup.file-error": { error: string };
}

/** Every name the service can answer with. */
export type Reason = keyof ToldValues;

/** One answer of `answers.told`: `reason` and the values beside it. A union
 *  over the names given, so checking `reason` narrows the values. */
export type Told<R extends Reason = Reason> = {
  [K in R]: { reason: K } & ToldValues[K];
}[R];

/**
 * What an operation answers: `ok` with the status line 200 and the names in
 * `Done`, or `ok` false with 409 and the names in `Failed`. Every operation
 * route builds its body as `{"ok": finished, **told, ...}` with
 * `status=200 if finished else 409`.
 */
export type Outcome<Done extends Reason, Failed extends Reason> =
  | ({ ok: true } & Told<Done>)
  | ({ ok: false } & Told<Failed>);

/* -- refusals ------------------------------------------------------------- */

/** A refusal: one `error`, such as "password required", and nothing else. It
 *  carries no `ok` and no `reason`. */
export interface Refusal {
  error: string;
}

/* -- the machine the emulator is set to ------------------------------------ */

/**
 * What a machine is, from config.describe. Built from the running machine's
 * previous.cfg in /api/status, and from machines.settings_for in /api/files
 * and /api/machine/settled.
 */
export interface MachineDescription {
  /** nMachineType as a number, and 1 where the file holds none. A file or a
   *  saved entry can carry any integer. */
  kind: number;
  /** The model's own name, or "?" for a type config.MACHINE_NAMES does not
   *  hold. */
  model: string;
  enclosure: Enclosure;
  turbo: boolean;
  /** Whether the color board is seated. */
  colour: boolean;
  /** Whether any NeXTdimension board is seated. */
  dimension: boolean;
  /** The processor, such as "68040". */
  cpu: string;
  /** nCpuFreq, and 25 where the file holds none. */
  mhz: number;
  /** The four banks added up, in megabytes. */
  memory_mb: number;
  /** The four memory banks in megabytes, in slot order. */
  banks: [number, number, number, number];
  /** The clock chip, "MCCS1850" or "MC68HC68T1". */
  rtc: string;
  /** The SCSI chip, "NCR53C90A" or "NCR53C90". */
  scsi: string;
  /** Whether the NeXTbus interface chip is there. */
  nbic: boolean;
}

/** What the interface reads off any machine it describes, whether it came as
 *  a description or as an entry of the tree, where `kind` reads "machine". */
export type MachineFacts = Omit<MachineDescription, "kind"> & { kind: number | "machine" };

/** The running machine as /api/status describes it: config.read with
 *  `catalogue` added by Handler._status. */
export interface StatusConfiguration extends MachineDescription {
  /** The name of the disk image the machine boots, without its folder, or
   *  null where no slot holds an inserted disk. */
  disk: string | null;
  /** Which configuration the file holds exactly: a System identifier or a
   *  saved configuration's name, or null where it is none of them. */
  catalogue: string | null;
}

/** What previous.cfg says about itself, from config.file_state. */
export interface ConfigurationFile {
  /** When the file was last written, as a Unix timestamp with a fraction, or
   *  null where it cannot be read. */
  changed_at: number | null;
  /** Whether the file was written after the running emulator started. False
   *  where no emulator runs. */
  newer_than_the_machine: boolean;
  /** Whether the file is still the one this service last wrote. */
  written_by_us: boolean;
}

/** Whether this machine has been set up, from Handler._ready. */
export interface Readiness {
  /** Whether dpkg has the emulator's package in place. */
  emulator: boolean;
  /** Whether any system's disk is on the card. */
  system: boolean;
  /** Whether previous.cfg could be read. */
  configuration: boolean;
  /** All three together. */
  set_up: boolean;
}

/** One configuration in the shape the file of saved ones holds it and
 *  /api/machine/save takes it, from saved.as_values. */
export interface SavedConfiguration {
  /** The machine type. */
  kind: number;
  turbo: boolean;
  /** In megahertz. */
  mhz: number;
  colour: boolean;
  /** Memory of each NeXTdimension board in megabytes, zero for an empty slot,
   *  in slot order. */
  dimensions: [number, number, number];
  banks: [number, number, number, number];
  dsp: DspKind;
  /** In kilobytes, one of machines.DSP_MEMORIES. */
  dsp_memory: number;
  floppy: boolean;
  optical: boolean;
  ethernet: boolean;
  /** Which ethernet socket, as machines.ETHERNET_SOCKETS. */
  socket: string;
  printer: boolean;
}

/** What may be chosen beside a machine, from machines.offers. */
export interface Offers {
  /** The three machine types with the model each is. */
  kinds: { kind: number; model: string }[];
  /** Whether a turbo board may be seated. */
  turbo: boolean;
  /** Whether the color board may be seated. */
  colour: boolean;
  /** The slots that can hold a NeXTdimension, 2, 4 and 6, or none. */
  dimension_slots: number[];
  /** What one board's memory can be, in megabytes. */
  dimension_memory: number[];
  /** In megahertz, slowest first. */
  clocks: number[];
  /** Totals of memory in megabytes, smallest first. */
  memory: number[];
  /** What each of the four banks accepts, in megabytes. A bank the machine
   *  cannot reach offers [0]. */
  banks: [number[], number[], number[], number[]];
  dsps: DspKind[];
  /** In kilobytes, and empty where the DSP is "none". */
  dsp_memory: number[];
  floppy: boolean;
  optical: boolean;
  /** Always true. */
  ethernet: boolean;
  /** Always true. */
  printer: boolean;
  /** Empty where the machine is off the network. */
  sockets: string[];
}

/* -- the privileged helper's record -------------------------------------- */

/** How far through something long one step is, from setup.Work.through.
 *  `done` can be negative while an archive unpacks, since it is what is
 *  written minus the archive's size. `of` is 0 where nobody knows the total. */
export interface ProgressPart {
  done: number;
  of: number;
  /** What the step is doing inside itself, as setup.DOINGS. */
  doing: string;
}

/** Why a step failed: its name beside what setup._said_of made of the
 *  failure. */
export type StepFailure = { step: string } & Told<
  | "setup.took-too-long"
  | "setup.no-such-command"
  | "setup.command-failed"
  | "setup.wrong-architecture"
  | "setup.wrong-release"
  | "setup.no-room"
  | "setup.no-room-until-restart"
  | "setup.tool-is-current"
  | "setup.no-package-to-install"
  | "setup.cannot-ask-about-releases"
  | "setup.not-our-package"
  | "setup.not-that-version"
  | "setup.no-system-named"
  | "setup.system-is-not-here"
  | "setup.system-in-use"
  | "setup.machine-is-running"
  | "setup.no-such-copy"
  | "setup.cannot-copy"
  | "setup.cannot-fetch"
  | "setup.not-what-was-expected"
  | "setup.cannot-unpack"
  | "setup.no-disk-in-the-archive"
  | "setup.file-error"
>;

/** Why a request was refused before its first step, from setup.main. It names
 *  no step. */
export type RequestFailure = Told<
  | "setup.no-such-job"
  | "setup.no-such-system"
  | "setup.no-such-machine"
  | "setup.no-such-copy"
  | "setup.no-owner"
>;

/** What every record carries, from setup.Work.reading. */
export interface ProgressCommon {
  /** The job, one of setup.JOBS, or "?" where the request named none the
   *  helper knows. */
  do: string;
  /** The system it is about, by its identifier. */
  system: string | null;
  /** The machine it is about, by its identifier. Null only in the record of
   *  a request that named no job the helper knows. */
  machine: string | null;
  /** Unix timestamp with a fraction. */
  started_at: number;
  /** Which step, counted from 1, and 0 before the first. */
  done: number;
  /** How many steps the job takes. */
  of: number;
  /** The steps a failure reversed. */
  undone: string[];
  /** The steps that changed something. */
  changed: string[];
}

/**
 * What the privileged helper is doing or last did: the file it writes as
 * setup.Work.reading, read back by kiosk.setting_up.
 *
 * The service checks only that the file holds a JSON object and passes it on
 * as it is, so this is the shape setup.py writes rather than one the service
 * enforces.
 *
 * Four states. A run in progress has no ending. A finished run sets
 * `finished_at`, `ok` and `failed` together and drops `part`. A request
 * refused before its first step names no step.
 */
export type SetupProgress = ProgressCommon &
  (
    | { finished_at: null; ok: null; failed: null; step: string; part: ProgressPart | null }
    | { finished_at: number; ok: true; failed: null; step: string; part: null }
    | { finished_at: number; ok: false; failed: StepFailure; step: string; part: null }
    | { finished_at: number; ok: false; failed: RequestFailure; step: null; part: null }
  );

/** The emulator's package, from setup.emulator. */
export interface EmulatorPackage {
  here: boolean;
  /** What dpkg has in place, or null. */
  version: string | null;
  /** What apt would install now, or null. */
  newest: string | null;
  /** Whether `newest` is later than `version` by dpkg's ordering. False where
   *  either is null. */
  newer: boolean;
}

/** One system the Installer offers, from Handler._setup. */
export interface SystemOffer {
  /** Its identifier, such as "nextstep-3.3". */
  identifier: string;
  /** What it is called, such as "NeXTSTEP 3.3". */
  name: string;
  /** The archive's size in bytes. */
  size: number;
  /** What its disk takes on the card, in bytes. */
  unpacked: number;
  /** Whether its disk is on the card. */
  here: boolean;
  /** Whether previous.cfg boots that disk. */
  booting: boolean;
}

/* -- the File Viewer's tree ---------------------------------------------- */

/** A folder of the tree, from files._folder. */
export interface Folder<Entry> {
  name: string;
  /** "folder", and "home" for the root. */
  icon: string;
  path: string;
  kind: "folder";
  /** False for /Machines/System alone. */
  writable: boolean;
  entries: Entry[];
}

/** One application, which is a window this page holds, from
 *  files.APPLICATIONS. */
export interface ApplicationEntry {
  /** The bundle's name, such as "Grab.app". */
  name: string;
  /** The catalog key of what it is called in words. */
  label: string;
  icon: string;
  path: string;
  kind: "application";
  /** The `name` of the nx-window it opens. */
  opens: string;
  /** Which release of the application this is, as x.y.z, which its About
   *  panel shows. */
  version: string;
}

/** A system's disk on the card, from files._disk. */
export interface DiskEntry {
  /** The system's identifier, which /api/disk takes as `disk`. */
  id: string;
  /** The system's name. */
  name: string;
  icon: string;
  path: string;
  kind: "disk";
  /** Whether previous.cfg boots this disk. */
  booting: boolean;
  /** Its size on the card, 0 where it cannot be read. */
  bytes: number;
}

/** A copy of a disk, from files._backups. */
export interface BackupEntry {
  /** The file's own name, which /api/disk/restore takes as `backup`. */
  id: string;
  /** The system's name and the moment, as files._a_copy_called builds it. */
  name: string;
  icon: string;
  path: string;
  kind: "backup";
  /** Which system it is a copy of, read off its name, or null where the name
   *  names none the service knows. */
  system: string | null;
  bytes: number;
}

/** A disc somebody put on the card, from files._disc. */
export interface DiscEntry {
  /** The file's name, which /api/disc takes as `disc`. */
  id: string;
  /** The file's name without its suffix. */
  name: string;
  icon: string;
  path: string;
  kind: "disc";
  /** The SCSI slot it is inserted on, or null where it is not in the machine. */
  slot: number | null;
  /** Whether the image says it is ISO 9660. */
  iso: boolean;
  bytes: number;
}

/** A file in the Pictures folder, from files.pictures. Every regular file in
 *  that folder is listed with this kind, a picture or not. */
export interface PictureEntry {
  name: string;
  /** "png" or "tiff", and "defaultIcon" for any other suffix. */
  icon: string;
  path: string;
  kind: "picture";
  bytes: number;
  /** When it was last written, ISO 8601 in UTC. */
  changed: string;
}

/**
 * A configuration in /Machines, from files._machine: the machine as
 * config.describe describes it, with `kind` written over by "machine". It
 * carries no `icon`; the viewer draws it from `enclosure`.
 */
export type MachineEntry = Omit<MachineDescription, "kind"> & {
  kind: "machine";
  /** Which of the two sets it belongs to. */
  set: "system" | "user";
  /** Its identifier: a System identifier, or a saved configuration's name. */
  id: string;
  name: string;
  path: string;
  /** The configuration itself, which is what the Config Editor opens on. */
  configuration: SavedConfiguration;
};

/** Anything the tree can hold. */
export type TreeEntry =
  | Folder<TreeEntry>
  | ApplicationEntry
  | DiskEntry
  | BackupEntry
  | DiscEntry
  | PictureEntry
  | MachineEntry;

/* -- GET routes ------------------------------------------------------------ */

/**
 * GET /api/status, from Handler._status. The same body is spread into the
 * answers of the operations that change the machine.
 *
 * `configuration` and `error` go together: either the file was read, or it
 * was not and `error` says why.
 */
export type StatusAnswer = {
  /** Whether the emulator's process exists. */
  running: boolean;
  /** Whether the hold file keeps the emulator down. */
  held: boolean;
  /** Whether the console unit is active. */
  console_active: boolean;
  /** How long the emulator has been running, in seconds, and null while it
   *  is not running. */
  uptime_seconds: number | null;
  /** What the kernel calls the boot the board is running, a new one at every
   *  start, and null where it will not say. */
  boot: string | null;
  file: ConfigurationFile;
  ready: Readiness;
} & (
  | { configuration: StatusConfiguration; error?: never }
  | {
      configuration: null;
      /** The text of config.NotReadable. */
      error: string;
    }
);

/** The board's memory, from pi.memory. Shared by /api/pi and /api/activity. */
export interface MemoryReading {
  /** MemTotal in megabytes. */
  total_mb: number;
  /** MemAvailable in megabytes. */
  available_mb: number;
}

/** GET /api/pi: server.VERSION beside pi.readings. Every reading is null where
 *  it cannot be had. */
export interface PiAnswer {
  /** The version answering, build included. */
  version: string;
  /** The device tree's description of the board, for a person to read. */
  model: string | null;
  /** The service's name for the board out of hardware.BOARDS, such as "pi5",
   *  read off the device tree's root compatible, or null for a board it does
   *  not know. The page shows the drawing named after it. */
  board: string | null;
  /** From /proc/uptime, in whole seconds. */
  uptime_seconds: number | null;
  /** From `vcgencmd measure_temp`, in degrees Celsius. */
  temperature_c: number | null;
  /** Where the temperature becomes a warning, pi.TEMPERATURE_LIMIT_C. */
  temperature_limit_c: number;
  /** From `vcgencmd get_throttled`. Each name is a key of `throttling.<name>`
   *  in the catalogs. */
  throttling: {
    /** The bit field as a number. */
    raw: number;
    now: string[];
    since_boot: string[];
  } | null;
  /** From `ps`, null where the emulator is not running. */
  emulator: {
    uptime_seconds: number;
    /** Per cent of one core since the process started, so above 100 with a
     *  NeXTdimension. */
    cpu_percent: number;
    memory_mb: number;
  } | null;
  /** How often the emulator ended badly since the board came up, null where
   *  nothing is recorded. */
  crashes: {
    count: number;
    /** Unix timestamp in whole seconds. */
    last: number;
  } | null;
  /** The card with a stream open, or the first card. */
  sound: {
    /** The card's id from /proc/asound. */
    card: string;
    playing: boolean;
  } | null;
  /** The root file system. */
  disk: {
    free_mb: number;
    total_mb: number;
    /** Rounded to a whole number. */
    used_percent: number;
  } | null;
  memory: MemoryReading | null;
}

/** What the emulator costs as Activity Monitor reads it, null where it is not
 *  running. */
export interface EmulatorCost {
  /** Per cent of one core since the last sample, null without one. */
  cpu_percent: number | null;
  /** Resident memory, null where /proc cannot be read. */
  memory_mb: number | null;
  /** Null where /proc/uptime cannot be read. */
  uptime_seconds: number | null;
}

/** GET /api/activity, from activity.readings. Every figure is a difference
 *  between two samples, so the first answer after a pause carries null where
 *  a figure needs one. */
export interface ActivityAnswer {
  /** The device tree's description of the board, for a person to read. */
  model: string | null;
  /** The service's name for the board, as PiAnswer carries it. */
  board: string | null;
  /** Per cent busy per core, in the kernel's order, one decimal; null where
   *  there is no earlier sample or /proc/stat cannot be read. */
  cores: number[] | null;
  /** From /proc/loadavg. */
  load: {
    one: number;
    five: number;
    fifteen: number;
    /** os.cpu_count(), which is None where the count cannot be determined. */
    cores: number | null;
  } | null;
  memory: MemoryReading | null;
  emulator: EmulatorCost | null;
}

/** GET /api/files, from files.tree: the root folder, which holds Apps, Disks
 *  where there is one, Discs where there is one, Documents and Machines. */
export type FilesAnswer = Folder<TreeEntry>;

/** GET /api/machine/settled, from Handler._settled_configuration. */
export interface SettledAnswer {
  /** The settled machine as /api/machine/save takes it. */
  configuration: SavedConfiguration;
  /** The same machine described. */
  machine: MachineDescription;
  offers: Offers;
}

/** GET /api/session. */
export interface SessionAnswer {
  /** Whether this machine has a password. */
  claimed: boolean;
  /** Whether this request carried an open session. */
  signed_in: boolean;
  /** The fewest characters a password may have, password.SMALLEST. */
  smallest: number;
  /** The most characters a password may have, password.LARGEST. */
  largest: number;
}

/** GET /api/setup, from Handler._setup. */
export interface SetupAnswer {
  /** All six, in systems.CATALOGUE's order. */
  systems: SystemOffer[];
  /** systems.DEFAULT, by its identifier. */
  default: string;
  emulator: EmulatorPackage;
  /** What has to be free before a system is fetched, in bytes. */
  needs: number;
  /** Free bytes where the disks live, or null where nothing can be asked. */
  room: number | null;
  /** Null where the helper has not run since the board started, or its file
   *  does not hold a JSON object. */
  progress: SetupProgress | null;
}

/** GET /api/update, from Handler._update. */
export interface UpdateAnswer {
  /** What dpkg has of this tool, build included, or null. */
  installed: string | null;
  /** The newest published release, or null until GitHub has answered once. */
  published: string | null;
  /** Whether `published` is later than `installed` by dpkg's ordering. */
  newer: boolean;
  /** The helper's record, only where its job is this tool's update. */
  progress: SetupProgress | null;
}


/** One thing the Pi decided is worth a notification, as notifications.py
 *  `worth_saying` makes it. */
export interface NotificationEntry {
  /** Which one: `update`, `emulator`, `power`, `temperature`, `disk` or
   *  `crash`. The catalogs carry its words as `notification.<name>.*`. */
  name: string;
  /** `info`, `alert` or `error`, which decides its picture. */
  level: "info" | "alert" | "error";
  /** What has to change for one that somebody closed to come back. */
  reading: string;
  /** What fills its words, by name. */
  values: Record<string, string | number | null>;
}

/** GET /api/notifications. */
export interface NotificationsAnswer {
  notifications: NotificationEntry[];
}


/** GET /api/updates: whether the Pi looks for updates on its own. */
export interface UpdatesAnswer {
  automatic: boolean;
}

/** POST /api/updates and /api/updates/look: the choice as it now stands. */
export interface UpdatesChosenAnswer extends UpdatesAnswer {
  ok: boolean;
}

/** One entry of the release list: a release, or neighbors whose notes open
 *  with the same paragraph, from release.runs. */
export interface ReleaseRun {
  /** The oldest release the entry stands for. */
  first: string;
  /** The newest, whose notes the entry shows. Equal to `first` for one. */
  last: string;
}

/** GET /api/update/notes, from Handler._release_notes. */
export interface ReleaseNotesAnswer {
  /** The release whose notes these are, or null where no release is known
   *  yet. */
  version: string | null;
  /** Markdown in the language asked for, or in English; "" where no release
   *  is known. */
  notes: string;
  /** Every entry, newest first, and empty until a list has come back. */
  versions: ReleaseRun[];
}

/* -- POST routes ----------------------------------------------------------- */

/** What kiosk.stop answers with where it worked. */
export type StopDone =
  | "emulator.was-not-running"
  | "emulator.ended-because-blank"
  | "guest.shut-itself-down";

/** And where it did not. */
export type StopFailed =
  | "emulator.blank-and-will-not-end"
  | "emulator.power-key-refused"
  | "guest.still-shutting-down";

/** What kiosk.start answers with. It always works. */
export type StartDone =
  | "emulator.already-running"
  | "emulator.nothing-holding-it"
  | "emulator.on-its-way-back";

/** POST /api/kiosk/start. */
export type KioskStartAnswer = (Outcome<StartDone, never> & StatusAnswer) | Refusal;

/** POST /api/kiosk/stop. */
export type KioskStopAnswer = (Outcome<StopDone, StopFailed> & StatusAnswer) | Refusal;

/** POST /api/kiosk/restart: a stop, then a start, so the start's names where
 *  it worked and the stop's where it did not. */
export type KioskRestartAnswer = (Outcome<StartDone, StopFailed> & StatusAnswer) | Refusal;

/** POST /api/pi/reboot and POST /api/pi/poweroff. */
export type BoardAnswer =
  | (Outcome<"board.on-its-way", StopFailed | "board.request-refused"> & StatusAnswer)
  | Refusal;

/** What change._applied and change._rolled_back can refuse with, for every
 *  change to previous.cfg. */
export type ChangeFailed =
  | StopFailed
  | "file.not-readable"
  | "rollback.could-not-write"
  | "rollback.emulator-will-not-end"
  | "rollback.back-as-before"
  | "rollback.nothing-runs";

/** POST /api/machine, from change.to_machine. */
export type MachineAnswer =
  | (Outcome<
      "machine.running" | "machine.was-already-set",
      "saved.not-readable" | "machine.no-such" | ChangeFailed
    > &
      StatusAnswer)
  | Refusal;

/** POST /api/disk, from change.to_disk. */
export type DiskAnswer =
  | (Outcome<"disk.booting" | "disk.was-already-set", "disk.no-such" | "disk.not-here" | ChangeFailed> &
      StatusAnswer)
  | Refusal;

/** POST /api/disc, from change.to_disc. */
export type DiscAnswer =
  | (Outcome<"disc.inserted" | "disc.was-already-in", "disc.no-such" | "disc.no-free-slot" | ChangeFailed> &
      StatusAnswer)
  | Refusal;

/** POST /api/disc/eject, from change.eject_disc. */
export type DiscEjectAnswer =
  | (Outcome<
      "disc.ejected" | "disc.was-already-out",
      "disc.no-such-slot" | "disc.that-is-the-disk" | "disc.nothing-there" | ChangeFailed
    > &
      StatusAnswer)
  | Refusal;

/** What saved._why_not refuses a name with. */
export type NameRefused =
  | "saved.name-needed"
  | "saved.name-too-long"
  | "saved.name-has-a-separator"
  | "saved.name-has-a-control-character"
  | "saved.name-taken";

/** POST /api/machine/save, from saved.save. No status rides along. */
export type SaveAnswer =
  | Outcome<"saved.kept", "saved.not-readable" | "saved.no-such" | NameRefused | "saved.could-not-write">
  | Refusal;

/** POST /api/machine/rename, from saved.rename. */
export type RenameAnswer =
  | Outcome<"saved.renamed", "saved.not-readable" | "saved.no-such" | NameRefused | "saved.could-not-write">
  | Refusal;

/** POST /api/machine/remove, from saved.remove. */
export type RemoveAnswer =
  | Outcome<"saved.removed", "saved.not-readable" | "saved.no-such" | "saved.could-not-write">
  | Refusal;

/** POST /api/disk/backup and POST /api/disk/restore, from Handler._copy_a_disk,
 *  with /api/setup's body beside the outcome. */
export type CopyAnswer =
  | (Outcome<"setup.asked", "setup.no-such-system" | "setup.one-at-a-time" | "setup.request-refused"> &
      SetupAnswer)
  | Refusal;

/** POST /api/setup, from Handler._ask_to_set_up, with /api/setup's body beside
 *  the outcome. */
export type SetupRequestAnswer =
  | (Outcome<
      "setup.asked",
      | "setup.no-such-job"
      | "setup.no-such-system"
      | "setup.no-such-machine"
      | "setup.one-at-a-time"
      | "setup.no-room"
      | "setup.no-room-until-restart"
      | "setup.request-refused"
    > &
      SetupAnswer)
  | Refusal;

/** POST /api/update, from Handler._ask_to_update, with /api/update's body
 *  beside the outcome. */
export type UpdateRequestAnswer =
  | (Outcome<"setup.asked", "setup.one-at-a-time" | "setup.request-refused"> & UpdateAnswer)
  | Refusal;

/** POST /api/picture/delete, from Handler._delete_picture: 200 with true where
 *  the picture went, 404 with false otherwise. */
export type PictureDeleteAnswer = { ok: boolean } | Refusal;

/** What `tell` answers with itself where somebody dismissed the panel asking
 *  for the password, so the request was never sent again. */
export interface PasswordNotGiven {
  ok: false;
  reason: "password.not-given";
}

/** Anything `say` is handed: what happened, the page's own answer for a
 *  dismissed password panel, or a refusal, which names nothing. */
export type Said = Told | PasswordNotGiven | Refusal;

/* -- which route answers with which ---------------------------------------- */

/** Every route `ask` reads, by its path, with what it answers. */
export interface GetAnswers {
  "/api/status": StatusAnswer;
  "/api/pi": PiAnswer;
  "/api/activity": ActivityAnswer;
  "/api/files": FilesAnswer;
  "/api/machine/settled": SettledAnswer;
  "/api/session": SessionAnswer;
  "/api/setup": SetupAnswer;
  "/api/update": UpdateAnswer;
  "/api/update/notes": ReleaseNotesAnswer;
  "/api/notifications": NotificationsAnswer;
  "/api/updates": UpdatesAnswer;
}

/** Every route `tell` sends to, by its path, with what it answers. */
export interface PostAnswers {
  "/api/kiosk/start": KioskStartAnswer;
  "/api/kiosk/stop": KioskStopAnswer;
  "/api/kiosk/restart": KioskRestartAnswer;
  "/api/pi/reboot": BoardAnswer;
  "/api/pi/poweroff": BoardAnswer;
  "/api/machine": MachineAnswer;
  "/api/disk": DiskAnswer;
  "/api/disc": DiscAnswer;
  "/api/disc/eject": DiscEjectAnswer;
  "/api/disk/backup": CopyAnswer;
  "/api/disk/restore": CopyAnswer;
  "/api/machine/save": SaveAnswer;
  "/api/machine/rename": RenameAnswer;
  "/api/machine/remove": RemoveAnswer;
  "/api/setup": SetupRequestAnswer;
  "/api/update": UpdateRequestAnswer;
  "/api/picture/delete": PictureDeleteAnswer;
  "/api/updates": UpdatesChosenAnswer;
  "/api/updates/look": UpdatesChosenAnswer;
}
