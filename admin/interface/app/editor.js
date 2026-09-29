/* The Config Editor: the machine somebody is building, until they save it. */

import { t, writeWords } from "../strings.js";
import { drawTheDimensionBoards, fillWithBanks, fillWithChoices, fillWithFittings, fillWithScale } from "./fittings.js";
import { editOnWhatIsRunning } from "./machines.js";
import { DSP_WORDS, KIND_NOTES, SOCKET_WORDS, bankNotes, noteFor, switchNote } from "./notes.js";
import { explain, show, theWindow } from "./page.js";
import { askPanelFor } from "./panels.js";
import { Saved, ask, tell } from "./service.js";
import { refresh } from "./status.js";
import { drawMachines } from "./viewer.js";
import { EDITOR, chipsOf, cpuOf, fitted, machineArt, nameOf, say, screenOf } from "./words.js";

/** What the editor is showing: the controls, and nothing derived.
 *
 *  Whatever is not known is left out of the question rather than filled in here,
 *  so a fresh window is answered with the service's own idea of a machine and
 *  there is no second copy of that here. */
let drafting = {};

/** Which controls the service writes afresh whenever the machine type or a
 *  board changes, so that changing one of those sends none of them. Named here
 *  rather than at each cell, because a control this forgets to name is one that
 *  quietly carries a value from the machine that has been left behind. */
const FOLLOWS_THE_MACHINE = ["mhz", "dsp", "dsp_memory", "banks"];

/** How much memory a NeXTdimension board gets when it is first put in, which is
 *  what the emulator's own file holds for one. Changed from there in its own
 *  group, so this decides only where somebody starts. */
const DIMENSION_DEFAULT_MEMORY = 32;

/** What the editor shows one of at a time, and what each is called, in the order
 *  a machine is put together: what it is, what runs in it, what it remembers,
 *  what it draws with, and what is plugged into it. Every group in the markup
 *  carries one of these names, which the page test holds it to. */
const SUBJECTS = {
  machine: "editor.subject.machine",
  processor: "editor.subject.processor",
  memory: "editor.subject.memory",
  graphics: "editor.subject.graphics",
  fitted: "editor.subject.fitted",
};

/** Which of them is showing. Kept here rather than read back off the markup, so
 *  a redraw after a change leaves somebody where they were rather than sending
 *  them to the first subject. */
let showing = Object.keys(SUBJECTS)[0];

/** Which saved configuration is being written over, or null where what comes out
 *  of this is a new one. A System machine cannot be changed, so editing one
 *  leaves this null and saving asks for a name. */
let replacing = null;

/** The last answer about the draft, so saving posts what was shown rather than
 *  asking again for something that may meanwhile read differently. Null whilst
 *  an answer is still on its way, which is what stops the button saving the
 *  machine that was in the window a moment ago. */
let drafted = null;

/** Which question about the draft is the current one. Every click asks one, and
 *  an answer that arrives after a newer question was asked is dropped rather
 *  than drawn over it. */
let asking = 0;

/**
 * Opens the editor on a machine.
 * @param {any} machine - An entry of the tree, or what /api/status says is
 *   configured now. Both carry the same facts, because one function describes
 *   them.
 * @param {HTMLElement} [asker] - What was used to open it, so its icon can
 *   travel to the floor of the screen.
 *
 * A configuration of somebody's own is edited in place, and one of the eleven is
 * the starting point for a new one. That is the whole difference between the two
 * sets, and it is decided here by which folder the machine came from.
 */
function editConfiguration(machine, asker) {
  replacing = machine?.set === "user" ? machine.id : null;
  /* The configuration a tree entry carries beside the words a person reads,
     which is the same shape saving takes. The description alone would not do:
     it leaves out everything two machines do not differ by in words, and its
     `kind` says what sort of entry this is rather than what machine it is. */
  drafting = machine?.configuration
    ? { ...machine.configuration }
    : whatTheDescriptionSays(machine);
  /* Nothing to save until the service has said what this is, so the button
     cannot send the machine the window held before. */
  drafted = null;

  drawTheTitle();
  theWindow(EDITOR).open(asker);
  drawTheDraft();
}

/**
 * As much of a machine as a description holds.
 * @param {any} machine - What /api/status says is configured now, which is a
 *   description rather than a configuration.
 * @returns {any} A draft of what can be read off it.
 *
 * For the machine that is running whilst being none of the ones this tool
 * knows. What a description does not carry is left out rather than guessed, so
 * the service answers those with what that machine has.
 */
function whatTheDescriptionSays(machine) {
  return {
    kind: machine?.kind,
    turbo: Boolean(machine?.turbo),
    colour: Boolean(machine?.colour),
    mhz: machine?.mhz,
    memory: machine?.memory_mb,
  };
}

/** Puts the name of what is being edited in the title bar.
 *
 *  A configuration of one's own is a document and is titled with its name, the
 *  way the Preview window is titled with the picture's. One that has no name yet
 *  is titled with the application's, because what is being made is new. */
function drawTheTitle() {
  theWindow(EDITOR)
    ?.rename(replacing ?? t("app.config-editor"));
}

/** Asks the service what the draft is, and draws the answer. */
async function drawTheDraft() {
  const asked = new URLSearchParams();
  for (const [control, value] of Object.entries(drafting)) {
    if (value === undefined || value === null) continue;
    if (typeof value === "boolean") {
      /* As "1" and "0", because a query string carries text and a flag that is
         absent has to read as off rather than as a word. */
      asked.set(control, value ? "1" : "0");
    } else if (Array.isArray(value)) {
      /* The four memory banks, in one field, in the order they sit in. */
      asked.set(control, value.join(","));
    } else {
      asked.set(control, value);
    }
  }

  const mine = ++asking;
  const answer = await ask("/api/machine/settled?" + asked);
  /* A click whilst this was on its way asked a newer question, and that one's
     answer is the one the window belongs to. */
  if (mine !== asking) return;
  if (!answer) {
    show("editor-note", t("note.no-service"));
    return;
  }

  drafted = answer;
  /* What came back may differ from what was asked for, because Previous refuses
     some of it. The draft follows the answer, so the next question is asked
     about the machine that actually exists. */
  drafting = {
    kind: answer.configuration.kind,
    turbo: answer.configuration.turbo,
    colour: answer.configuration.colour,
    dimensions: answer.configuration.dimensions,
    mhz: answer.machine.mhz,
    memory: answer.machine.memory_mb,
    dsp: answer.configuration.dsp,
    dsp_memory: answer.configuration.dsp_memory,
    /* Carried on, so a bank chosen on its own is asked about again rather than
       being laid out afresh from the total the next question would send. The
       total goes back in charge when a cell in its group is pressed, which
       sends no banks at all. */
    banks: answer.configuration.banks,
    floppy: answer.configuration.floppy,
    optical: answer.configuration.optical,
    ethernet: answer.configuration.ethernet,
    socket: answer.configuration.socket,
    printer: answer.configuration.printer,
  };

  redrawTheEditor();
}

/** Draws the window from the last answer, without asking for it again.
 *
 *  Every word in it is this page's, so a change of language is redrawn from what
 *  is already here rather than by asking the service what it just said. */
function redrawTheEditor() {
  if (!drafted) return;
  drawTheMachineInTheEditor(drafted.machine);
  drawTheChoices(drafted.offers);
  drawWhatSavingWillDo();
}

/**
 * Draws what the drafted machine is, in the words the rest of the interface
 * uses for a machine.
 * @param {any} machine - The facts, as config.describe answers them.
 */
function drawTheMachineInTheEditor(machine) {
  /** @type {any} */ (document.getElementById("editor-icon")).style.backgroundImage =
    `var(--${machineArt(machine.enclosure)})`;
  show("editor-caption", nameOf(machine));
  show("editor-cpu", cpuOf(machine));
  show("editor-ram", t("machine.memory-banks",
                       { mb: machine.memory_mb, banks: fitted(machine.banks) }));
  show("editor-screen", screenOf(machine));
  show("editor-chips", chipsOf(machine));
}

/**
 * Draws the cells of every group from what the service says may be chosen, and
 * under each group the sentence about what is chosen there.
 * @param {any} offers - Its answer: the machine types, which boards may be
 *   seated, which clocks there are and which totals of memory.
 *
 * A group with nothing to offer is taken away rather than shown empty, which is
 * what Previous does with its own board options on a machine that takes none.
 *
 * The sentences are keyed by what is chosen, so a group of one choice shows the
 * one for its value and a group of switches shows one per switch for the state
 * it is in. What holds for every value of a group, such as the machine type
 * setting three other groups afresh, is one sentence appended to all of them.
 */
function drawTheChoices(offers) {
  drawTheSubjects();

  fillWithChoices("editor-kinds", offers.kinds.map((kind) => ({
    label: kind.model,
    chosen: kind.kind === drafting.kind,
    choose: () => changeTheMachine({ kind: kind.kind }),
  })));
  explain("editor-kinds-note",
    KIND_NOTES[drafting.kind] ? t(KIND_NOTES[drafting.kind]) : "",
    t("editor.machine.note.resets"));

  const boards = [
    ["turbo", t("editor.turbo")],
    ["colour", t("editor.colour")],
  ].filter(([which]) => offers[which]);
  fillWithChoices("editor-boards", boards.map(([which, label]) => ({
    label,
    chosen: drafting[which],
    /* A board is seated or it is not, so its cell answers a second click by
       taking it out again. */
    choose: () => changeTheMachine({ [which]: !drafting[which] }),
  })));
  /** @type {any} */ (document.getElementById("editor-boards-group")).hidden = !boards.length;
  explain("editor-boards-note",
    ...boards.map(([which]) => switchNote(which)),
    t("editor.boards.note.resets"));

  fillWithScale("editor-clocks", t("editor.unit.mhz"),
    offers.clocks.map((mhz) => ({
      value: mhz, label: t("editor.mhz", { mhz }), tick: String(mhz),
    })),
    drafting.mhz, (mhz) => change({ mhz }));
  explain("editor-clocks-note", noteFor("clock", drafting.mhz));

  fillWithScale("editor-memory", t("editor.unit.mb"),
    offers.memory.map((mb) => ({
      value: mb, label: t("editor.megabytes", { mb }), tick: String(mb),
    })),
    /* The banks below may add up to a total the scale does not carry, and then
       the knob stands at the start rather than pretending to a step. */
    drafting.memory,
    /* A total lays the banks out again, so whatever they were is let go. */
    (mb) => change({ memory: mb, banks: undefined }));
  /* Banks set one at a time can add up to a total no cell offers, and then the
     sentence says so rather than describing a cell nobody chose. */
  explain("editor-memory-note",
    offers.memory.includes(drafting.memory)
      ? noteFor("memory", drafting.memory)
      : t("editor.memory.note.by-hand", { mb: drafting.memory }),
    t("editor.memory.note.lays-out"));

  fillWithBanks("editor-banks", offers.banks);
  explain("editor-banks-note", ...bankNotes(offers.banks));

  fillWithChoices("editor-dsps", offers.dsps.map((dsp) => ({
    /* A chip this page has no word for is shown as the service named it, so a
       service that learns a fourth still draws a cell somebody can press. */
    label: DSP_WORDS[dsp] ? t(DSP_WORDS[dsp]) : dsp,
    chosen: dsp === drafting.dsp,
    choose: () => change({ dsp }),
  })));
  explain("editor-dsps-note", noteFor("dsp", drafting.dsp));

  fillWithChoices("editor-dsp-memory", offers.dsp_memory.map((kb) => ({
    label: t("editor.kilobytes", { kb }),
    chosen: kb === drafting.dsp_memory,
    choose: () => change({ dsp_memory: kb }),
  })));
  /** @type {any} */ (document.getElementById("editor-dsp-memory-group")).hidden =
    !offers.dsp_memory.length;
  explain("editor-dsp-memory-note", noteFor("dsp-memory", drafting.dsp_memory));


  /* What the machine has, which is a drive or a port being there rather than
     anything in it. The same cells as the boards group: one press puts it in and
     the next takes it out. */
  const drives = fillWithFittings("editor-drives", offers, [
    ["floppy", t("editor.floppy")],
    ["optical", t("editor.optical")],
  ]);
  explain("editor-drives-note", ...drives.map(switchNote));
  const ports = fillWithFittings("editor-ports", offers, [
    ["ethernet", t("editor.ethernet")],
    ["printer", t("editor.printer")],
  ]);
  explain("editor-ports-note", ...ports.map(switchNote));

  fillWithChoices("editor-sockets", offers.sockets.map((socket) => ({
    label: SOCKET_WORDS[socket] ? t(SOCKET_WORDS[socket]) : socket,
    chosen: socket === drafting.socket,
    choose: () => change({ socket }),
  })));
  /** @type {any} */ (document.getElementById("editor-socket-group")).hidden = !offers.sockets.length;
  explain("editor-sockets-note", noteFor("socket", drafting.socket));

  drawTheDimensionBoards(offers);
}

/**
 * Draws the row of subjects and shows the one that is chosen.
 *
 * Eleven groups in one column is taller than the desk, so the window shows one
 * subject at a time. The row is the same raised cell every choice in this window
 * uses, which is what Preferences does with its modules, and the groups
 * themselves are shown by the stylesheet from the name on the row below it.
 */
function drawTheSubjects() {
  fillWithChoices("editor-subjects",
    Object.entries(SUBJECTS).map(([subject, word]) => ({
      label: t(word),
      chosen: subject === showing,
      choose: () => showSubject(subject),
    })));

  /* Marked on each group rather than read off the row by the stylesheet, so
     that one rule hides them and nothing has to name the subjects a second
     time. */
  for (const group of document.querySelectorAll(".editor-groups > [subject]")) {
    group.toggleAttribute("away", group.getAttribute("subject") !== showing);
  }
}

/**
 * Shows one subject and leaves the machine alone.
 * @param {string} subject - One of SUBJECTS.
 *
 * Nothing is asked of the service for this: which groups are drawn is the
 * window's own business and the machine has not changed.
 */
function showSubject(subject) {
  showing = subject;
  drawTheSubjects();
}

/**
 * Changes one control and asks what that machine is now.
 * @param {any} what - The one that moved.
 */
function change(what) {
  drafting = { ...drafting, ...what };
  drawTheDraft();
}

/**
 * Changes what the machine itself is, and lets what follows from it follow
 * again.
 * @param {any} what - The machine type or the board that moved.
 *
 * Previous writes every one of FOLLOWS_THE_MACHINE afresh whenever one of those
 * two changes in its own dialogue, and the service does the same. Sending the
 * values that were showing would carry a setting from the machine just left
 * behind, so a 40 MHz Nitro would stay at 40 through losing its turbo board.
 */
function changeTheMachine(what) {
  const afresh = Object.fromEntries(
    FOLLOWS_THE_MACHINE.map((control) => [control, undefined]));
  change({ ...afresh, ...what });
}

/** Says what the button will do, and puts that on the button. */
function drawWhatSavingWillDo() {
  const button = /** @type {any} */ (document.getElementById("editor-save"));
  button.dataset.t = replacing ? "button.save" : "button.save-as";
  writeWords(button, t(button.dataset.t));
  show("editor-note", replacing
    ? t("editor.over-this-one", { name: replacing })
    : t("editor.into-a-new-one"));
}

/**
 * Saves what the editor is showing.
 *
 * A name is asked for once, when the configuration is a new one. Editing one of
 * your own writes it back under the name it already has, which is what there is
 * to do with it.
 */
async function saveTheDraft() {
  if (!drafted) return;

  let name = replacing;
  if (name === null) {
    name = await askPanelFor({
      title: t("ask.name.title"),
      text: [t("ask.rename.question")],
      icon: machineArt(drafted.machine.enclosure),
      confirm: t("button.save"),
    });
    if (name === null) return;
  }

  const answer = await tell(Saved.Keep, {
    name,
    configuration: drafted.configuration,
    replacing,
  });
  show("editor-note", answer === null ? t("note.no-service") : say(answer));
  if (!answer?.ok) return;

  /* It is a configuration of its own from now on, so saving again writes over
     it rather than asking for another name, and the window carries its name. */
  replacing = name;
  drawTheTitle();
  drawWhatSavingWillDo();
  drawMachines();
  refresh();
}

/** Wires the editor's button, its menu entry, and its tile. */
function wireEditor() {
  document.getElementById("editor-save")
    ?.addEventListener("click", saveTheDraft);
  document.querySelector('nx-menu-item[name="editor-save"]')
    ?.addEventListener("click", saveTheDraft);

  /* Two clicks, like every other tile. It carries no `opens`, because the window
     is shown only once something has decided which machine it holds, and that is
     what this and the Apps folder both go through. */
  document.querySelector('nx-tile[name="editor"]')
    ?.addEventListener("dblclick", (/** @type {any} */ event) => editOnWhatIsRunning(event.target));
}

/**
 * Fills the editor where it came back open from the last visit.
 *
 * A window that was open when the page was left comes back open, and nothing
 * opened it, so nothing has decided what it holds. This runs once the first
 * status and the first tree are in, because what it shows then is the machine
 * that is set and whether that is one of the saved ones.
 */
function fillTheEditorIfItCameBackOpen() {
  const window_ = theWindow(EDITOR);
  if (window_ && !window_.hidden) editOnWhatIsRunning();
}

export {
  drafting,
  DIMENSION_DEFAULT_MEMORY,
  editConfiguration,
  redrawTheEditor,
  change,
  wireEditor,
  fillTheEditorIfItCameBackOpen,
};
