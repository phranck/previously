/* The Config Editor: the machine somebody is building, until they save it. */

import { currentLocale, t, writeWords } from "../strings.js";
import { editOnWhatIsRunning } from "./machines.js";
import { explain, show } from "./page.js";
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

/** What each DSP is called. The service answers the three by name, because the
 *  numbers Previous writes are not in the order a person would read them in, and
 *  these are this page's words for those names. Written out one by one rather
 *  than built from the name, so that a key nothing answers is caught by the
 *  strings test instead of appearing as an empty cell. */
const DSP_WORDS = {
  none: "editor.dsp.none",
  plain: "editor.dsp.plain",
  "with-rom": "editor.dsp.with-rom",
};

/** What each ethernet socket is called, written out for the same reason. */
const SOCKET_WORDS = {
  "thin-wire": "editor.thin-wire",
  "twisted-pair": "editor.twisted-pair",
};

/** What the sentence about each machine type is called, by the number Previous
 *  gives the type. Written out rather than built from the number, because a
 *  sentence keyed by a name can be found in the catalogue and one keyed by 1
 *  cannot. The strings test holds these numbers to the types the service
 *  offers. */
const KIND_NOTES = {
  0: "editor.machine.note.next-computer",
  1: "editor.machine.note.nextcube",
  2: "editor.machine.note.nextstation",
};

/** The least the first memory bank may hold for the machine to boot, in
 *  megabytes. Previous says so on its own memory dialogue and does not raise a
 *  smaller bank itself, so the note under the banks is the one place somebody
 *  is told before the machine fails to come up. */

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
 * @param {object} machine - An entry of the tree, or what /api/status says is
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
  document.querySelector(`nx-window[name="${EDITOR}"]`).open(asker);
  drawTheDraft();
}

/**
 * As much of a machine as a description holds.
 * @param {object} machine - What /api/status says is configured now, which is a
 *   description rather than a configuration.
 * @returns {object} A draft of what can be read off it.
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
  document.querySelector(`nx-window[name="${EDITOR}"]`)
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
 * @param {object} machine - The facts, as config.describe answers them.
 */
function drawTheMachineInTheEditor(machine) {
  document.getElementById("editor-icon").style.backgroundImage =
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
 * @param {object} offers - Its answer: the machine types, which boards may be
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
  document.getElementById("editor-boards-group").hidden = !boards.length;
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
  document.getElementById("editor-dsp-memory-group").hidden =
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
  document.getElementById("editor-socket-group").hidden = !offers.sockets.length;
  explain("editor-sockets-note", noteFor("socket", drafting.socket));

  drawTheDimensionBoards(offers);
}

/**
 * The sentence about one value of a group.
 * @param {string} group - The group's name in the catalogue, such as `clock`.
 * @param {string|number} value - What is chosen there, which is the last part
 *   of the key.
 * @param {object} [values] - What fills the sentence's places.
 * @returns {string}
 *
 * Built from the value rather than written out per value, so a clock or a size
 * the service starts to offer arrives with its sentence or fails the strings
 * test, which derives every key this can build from the service.
 */
function noteFor(group, value, values) {
  return t(`editor.${group}.note.${value}`, values);
}

/**
 * The sentence about a switch, for the state it is in.
 * @param {string} which - The switch, such as `turbo` or `floppy`, which is
 *   both the control's name in the draft and its name in the catalogue.
 * @returns {string}
 */
function switchNote(which) {
  return noteFor(which, drafting[which] ? "in" : "out");
}

/**
 * What the four memory banks have to say about themselves.
 * @param {Array<Array<number>>} banks - What each bank accepts, as the service
 *   offers them, with an empty bank as the first size of each.
 * @returns {string[]} The sentences that apply, and nothing for those that do
 *   not.
 *
 * Which modules the machine takes is read off the first bank, because every
 * bank that is there takes the same ones. A bank that is not there offers an
 * empty one and nothing else, which is how the reachable banks are counted here
 * without the page holding the rule that decides them.
 */
function bankNotes(banks) {
  /* Read off a bank that is not the first, since that one is offered neither an
     empty socket nor the smallest module and would name a shorter list than the
     machine actually takes. */
  const ordinary = banks.find((sizes, bank) => bank > 0 && !isAbsent(sizes));
  const modules = (ordinary ?? banks[0]).filter((size) => size > 0);
  const reachable = banks.filter((sizes) => !isAbsent(sizes)).length;
  return [
    t("editor.banks.note.press"),
    t("editor.banks.note.first", { sizes: listed(banks[0]) }),
    t("editor.banks.note.modules", { sizes: listed(modules) }),
    reachable < banks.length
      ? t("editor.banks.note.reach", { count: reachable }) : "",
  ];
}

/**
 * Several values in one phrase, joined the way the language being read joins
 * them.
 * @param {Array<number|string>} values
 * @returns {string} "1, 4 or 16" in English and "1, 4 oder 16" in German. The
 *   browser knows each language's word before the last one, so no catalogue
 *   has to say it.
 */
function listed(values) {
  return new Intl.ListFormat(currentLocale(), { type: "disjunction" })
    .format(values.map(String));
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
 * Draws the three NeXTdimension slots and the memory of each board there is.
 * @param {object} offers - The service's answer, which says which slots this
 *   machine has and how much memory a board takes.
 *
 * A slot is a cell that puts a board in and takes it out again, and a board
 * that is in gets a group of its own for its memory. One group per board rather
 * than one for all of them, because Previous gives each its own and a cube with
 * two boards of different sizes is a machine it will run.
 */
function drawTheDimensionBoards(offers) {
  fillWithChoices("editor-dimensions", offers.dimension_slots.map((slot, board) => ({
    label: t("editor.slot", { slot }),
    chosen: drafting.dimensions[board] > 0,
    /* Put in with the memory Previous's own file gives a board, and taken out
       by setting that back to nothing. */
    choose: () => change({
      dimensions: dimensionsWith(
        board, drafting.dimensions[board] ? 0 : DIMENSION_DEFAULT_MEMORY),
    }),
  })));
  document.getElementById("editor-dimension-group").hidden =
    !offers.dimension_slots.length;

  /* The console follows the first board there is, so the sentence names that
     board's slot, and says how many boards there are because each gets a
     group of its own below. */
  const seated = offers.dimension_slots
    .filter((slot, board) => drafting.dimensions[board] > 0);
  explain("editor-dimensions-note", seated.length
    ? t("editor.dimension.note.some",
        { count: seated.length, slot: seated[0] }, seated.length)
    : t("editor.dimension.note.none"));

  /* The board's index is taken before the empty slots are dropped, because
     after that the second board that is in would be counted as the second
     slot, and a cube with boards in slots 2 and 6 would draw and change the
     memory of slot 4. */
  const memories = document.getElementById("editor-dimension-memory");
  memories.replaceChildren(...offers.dimension_slots
    .map((slot, board) => [slot, board])
    .filter(([, board]) => drafting.dimensions[board] > 0)
    .map(([slot, board]) => drawOneBoardsMemory(slot, board, offers)));
}

/**
 * One board's memory, as a group of its own.
 * @param {number} slot - Which slot it answers from, for the heading.
 * @param {number} board - Which of the three it is, from 0.
 * @param {object} offers - The service's answer.
 * @returns {HTMLElement} The group, ready to go in.
 */
function drawOneBoardsMemory(slot, board, offers) {
  const group = document.createElement("fieldset");
  group.className = "group";

  const heading = document.createElement("legend");
  heading.textContent = t("editor.dimension-memory", { slot });
  group.append(heading);

  /* A scale like the machine's own memory, so it is a knob in a trough. Built
     rather than written, so it is wired here rather than through
     fillWithScale, which reaches for a slider the markup already holds. */
  const slider = document.createElement("nx-slider");
  group.append(slider);
  slider.options = offers.dimension_memory.map((mb) => ({
    value: mb, label: t("editor.megabytes", { mb }), tick: String(mb),
  }));
  slider.says = t("editor.unit.mb");
  slider.value = drafting.dimensions[board];
  slider.addEventListener("nx-slide",
    (event) => change({ dimensions: dimensionsWith(board, event.detail.value) }));

  /* The same sentence under the cells the groups in the markup carry, put here
     because this group is built rather than written. */
  const note = document.createElement("p");
  note.className = "note";
  note.textContent = noteFor("dimension-memory", drafting.dimensions[board]);
  group.append(note);

  return group;
}

/**
 * The three boards with one of them changed.
 * @param {number} board - Which of them, from 0.
 * @param {number} memory - How much memory it has now, and zero for taking it
 *   out altogether.
 * @returns {Array<number>} All three, for the service to settle.
 */
function dimensionsWith(board, memory) {
  const boards = [...drafting.dimensions];
  boards[board] = memory;
  return boards;
}

/**
 * Puts a scale in place, as a knob in a trough.
 * @param {string} id - The slider's own id.
 * @param {string} unit - What the figures are counted in, said once beside
 *   the scale rather than on every tick.
 * @param {Array<object>} steps - `{value, label}` in the order they sit on the
 *   scale, smallest first.
 * @param {*} value - Which of them the machine is on. One that is not a step
 *   leaves the knob at the start, which is what a total made by hand out of the
 *   banks does.
 * @param {Function} choose - Given the value landed on.
 *
 * For a group whose values have an order, where a row of cells would say they
 * have none. The groups that are not a scale keep their cells: a machine type,
 * a board, a DSP, a socket, a drive and a port are all one of several rather
 * than more or less of one thing.
 *
 * The listener is put on once and reads the action off the element, because the
 * action closes over what the machine is now and this runs again on every
 * change.
 */
function fillWithScale(id, unit, steps, value, choose) {
  const slider = document.getElementById(id);
  slider.says = unit;
  slider.onSlide = choose;
  if (!slider.listening) {
    slider.listening = true;
    slider.addEventListener("nx-slide",
      (event) => slider.onSlide(event.detail.value));
  }
  slider.options = steps;
  slider.value = value;
}

/**
 * Puts one group of things a machine either has or has not in place.
 * @param {string} id - The row they go in.
 * @param {object} offers - The service's answer, which says which of them this
 *   machine can have at all.
 * @param {Array<Array>} fittings - `[name, label]` for each.
 * @returns {string[]} The names of the ones this machine was offered, so the
 *   caller can say what each is doing in the state it is in.
 *
 * One press puts it in and the next takes it out, which is the boards group's
 * cell. A machine that cannot have one is not offered it rather than being
 * offered it and refused.
 */
function fillWithFittings(id, offers, fittings) {
  const offered = fittings.filter(([which]) => offers[which]);
  fillWithChoices(id, offered.map(([which, label]) => ({
    label,
    chosen: drafting[which],
    choose: () => change({ [which]: !drafting[which] }),
  })));
  return offered.map(([which]) => which);
}

/**
 * Puts the four memory banks in place, as the sockets they are.
 * @param {string} id - The row they go in.
 * @param {Array<Array<number>>} offered - What each bank accepts, from the
 *   service, smallest first and with an empty bank as the first of them.
 *
 * A bank is a socket on the board rather than one choice among several, so it
 * is drawn as one: a sunken field with a raised module in it where something is
 * seated. Those two edges are what this whole interface is built from, so this
 * needs no picture of a memory module, and there is none to use.
 *
 * A bank the machine cannot reach accepts nothing but an empty bank, and it is
 * drawn flat, because a socket that is not there is not a socket to fill.
 */
function fillWithBanks(id, offered) {
  document.getElementById(id).replaceChildren(...offered.map((sizes, bank) => {
    const size = drafting.banks[bank];

    const row = document.createElement("div");
    row.className = "bank-row";

    const name = document.createElement("span");
    name.className = "bank-name";
    name.textContent = t("editor.bank", { bank });
    row.append(name);

    const socket = document.createElement("div");
    socket.className = "bank";
    socket.toggleAttribute("absent", isAbsent(sizes));
    /* A bank offered one size and no empty one cannot move, which is the first
       bank of a colour station: it takes an 8 MB module and nothing else. */
    if (sizes.length > 1) {
      socket.addEventListener("click", () => change({
        banks: bankMovedOn(bank, sizes),
        memory: undefined,
      }));
    }

    const module_ = document.createElement("div");
    module_.className = "bank-module";
    module_.toggleAttribute("empty", !size);
    module_.textContent = size
      ? t("editor.megabytes", { mb: size })
      : t("editor.bank-empty");
    socket.append(module_);

    row.append(socket);
    return row;
  }));
}

/**
 * Whether a bank is one this machine does not have.
 * @param {Array<number>} sizes - What it accepts, from the service.
 * @returns {boolean}
 *
 * The service answers such a bank with an empty one and nothing else, which is
 * a choice of one rather than an absence, so there are four banks to draw
 * either way.
 */
function isAbsent(sizes) {
  return sizes.length === 1 && sizes[0] === 0;
}

/**
 * The four memory banks with one of them moved on to the next size it takes.
 * @param {number} bank - Which one was pressed, from 0.
 * @param {Array<number>} sizes - What that bank accepts, smallest first, with
 *   an empty bank as the first of them.
 * @returns {Array<number>} All four, in megabytes, for the service to settle.
 *
 * A bank holds one module rather than a choice between several, so its cell
 * fits the next size up and comes back to an empty bank after the largest. It
 * is the same gesture as taking a board out and putting it back, which is the
 * one this window already has for a cell that is not one of a row of choices.
 *
 * A bank holding a size the machine no longer takes starts again at the
 * smallest, because indexOf answers -1 for it.
 */
function bankMovedOn(bank, sizes) {
  const banks = [...drafting.banks];
  banks[bank] = sizes[(sizes.indexOf(banks[bank]) + 1) % sizes.length];
  return banks;
}

/**
 * Puts one group's cells in place.
 * @param {string} id - The row they go in.
 * @param {Array<object>} cells - `{label, chosen, choose}` for each.
 *
 * The same raised cell the Preferences window offers a choice with, because
 * this interface gives anything that can be chosen one shape.
 */
function fillWithChoices(id, cells) {
  document.getElementById(id).replaceChildren(...cells.map((cell) => {
    const choice = document.createElement("div");
    choice.className = "choice";
    choice.textContent = cell.label;
    choice.toggleAttribute("chosen", cell.chosen);
    choice.addEventListener("click", cell.choose);
    return choice;
  }));
}

/**
 * Changes one control and asks what that machine is now.
 * @param {object} what - The one that moved.
 */
function change(what) {
  drafting = { ...drafting, ...what };
  drawTheDraft();
}

/**
 * Changes what the machine itself is, and lets what follows from it follow
 * again.
 * @param {object} what - The machine type or the board that moved.
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
  const button = document.getElementById("editor-save");
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
    ?.addEventListener("dblclick", (event) => editOnWhatIsRunning(event.target));
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
  const window_ = document.querySelector(`nx-window[name="${EDITOR}"]`);
  if (window_ && !window_.hidden) editOnWhatIsRunning();
}

export {
  drafting,
  FOLLOWS_THE_MACHINE,
  DSP_WORDS,
  SOCKET_WORDS,
  KIND_NOTES,
  DIMENSION_DEFAULT_MEMORY,
  SUBJECTS,
  showing,
  replacing,
  drafted,
  asking,
  editConfiguration,
  whatTheDescriptionSays,
  drawTheTitle,
  drawTheDraft,
  redrawTheEditor,
  drawTheMachineInTheEditor,
  drawTheChoices,
  noteFor,
  switchNote,
  bankNotes,
  listed,
  drawTheSubjects,
  showSubject,
  drawTheDimensionBoards,
  drawOneBoardsMemory,
  dimensionsWith,
  fillWithScale,
  fillWithFittings,
  fillWithBanks,
  isAbsent,
  bankMovedOn,
  fillWithChoices,
  change,
  changeTheMachine,
  drawWhatSavingWillDo,
  saveTheDraft,
  wireEditor,
  fillTheEditorIfItCameBackOpen,
};
