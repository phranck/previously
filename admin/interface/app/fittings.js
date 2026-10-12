/* The controls the Config Editor is built from: a scale, a set of fittings, the memory banks. */

import { NxSlider } from "../nextstep.js";
import { t } from "../strings.js";
import { DIMENSION_DEFAULT_MEMORY, change, holding } from "./editor.js";
import { noteFor } from "./notes.js";
import { byId, explain } from "./page.js";

/** @typedef {import("../answers.js").Offers} Offers */
/** @typedef {import("./editor.js").Settled} Settled */
/** @typedef {import("./notes.js").Switch} Switch */

/**
 * One step of a scale in the editor, which is always a figure.
 * @typedef {object} ScaleStep
 * @property {number} value - What landing on it hands back.
 * @property {string} label - What it is called, read out to assistive
 *   technology.
 * @property {string} tick - The figure that stands over it.
 */

/**
 * One cell of a group.
 * @typedef {object} Cell
 * @property {string} label - What it says.
 * @property {boolean} chosen - Whether it is the one in force.
 * @property {() => void} choose - What pressing it does.
 */

/** What each scale does with the step it lands on, by the slider's id.
 *
 *  Kept here rather than in the listener, because the action closes over what
 *  the machine is now and the scale is filled again on every change, while the
 *  listener is put on once.
 *  @type {Map<string, (value: number) => void>} */
const SCALE_ACTIONS = new Map();

/**
 * Draws the three NeXTdimension slots and the memory of each board there is.
 * @param {Offers} offers - The service's answer, which says which slots this
 *   machine has and how much memory a board takes.
 * @param {Settled} settled - The machine the window shows.
 *
 * A slot is a cell that puts a board in and takes it out again, and a board
 * that is in gets a group of its own for its memory. One group per board rather
 * than one for all of them, because Previous gives each its own and a cube with
 * two boards of different sizes is a machine it will run.
 */
function drawTheDimensionBoards(offers, settled) {
  fillWithChoices("editor-dimensions", offers.dimension_slots.map((slot, board) => ({
    label: t("editor.slot", { slot }),
    chosen: settled.dimensions[board] > 0,
    /* Put in with the memory Previous's own file gives a board, and taken out
       by setting that back to nothing. */
    choose: () => change({
      dimensions: dimensionsWith(settled, board,
        holding("dimensions", settled)[board] ? 0 : DIMENSION_DEFAULT_MEMORY),
    }),
  })));
  byId("editor-dimension-group").hidden = !offers.dimension_slots.length;

  /* The console follows the first board there is, so the sentence names that
     board's slot, and says how many boards there are because each gets a
     group of its own below. */
  const seated = offers.dimension_slots
    .filter((slot, board) => settled.dimensions[board] > 0);
  explain("editor-dimensions-note", seated.length
    ? t("editor.dimension.note.some",
        { count: seated.length, slot: seated[0] }, seated.length)
    : t("editor.dimension.note.none"));

  /* The board's index is taken before the empty slots are dropped, because
     after that the second board that is in would be counted as the second
     slot, and a cube with boards in slots 2 and 6 would draw and change the
     memory of slot 4. */
  byId("editor-dimension-memory").replaceChildren(...offers.dimension_slots
    .map((slot, board) => ({ slot, board }))
    .filter(({ board }) => settled.dimensions[board] > 0)
    .map(({ slot, board }) => drawOneBoardsMemory(slot, board, offers, settled)));
}

/**
 * One board's memory, as a group of its own.
 * @param {number} slot - Which slot it answers from, for the heading.
 * @param {number} board - Which of the three it is, from 0.
 * @param {Offers} offers - The service's answer.
 * @param {Settled} settled - The machine the window shows.
 * @returns {HTMLElement} The group, ready to go in.
 */
function drawOneBoardsMemory(slot, board, offers, settled) {
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
  slider.value = settled.dimensions[board];
  slider.addEventListener("nx-slide", (event) => {
    const landed = event.detail.value;
    if (typeof landed === "number") {
      change({ dimensions: dimensionsWith(settled, board, landed) });
    }
  });

  /* The same sentence under the cells the groups in the markup carry, put here
     because this group is built rather than written. */
  const note = document.createElement("p");
  note.className = "note";
  note.textContent = noteFor("dimension-memory", settled.dimensions[board]);
  group.append(note);

  return group;
}

/**
 * The three boards with one of them changed.
 * @param {Settled} settled - The machine the window shows.
 * @param {number} board - Which of them, from 0.
 * @param {number} memory - How much memory it has now, and zero for taking it
 *   out altogether.
 * @returns {[number, number, number]} All three, for the service to settle.
 */
function dimensionsWith(settled, board, memory) {
  /** @type {[number, number, number]} */
  const boards = [...holding("dimensions", settled)];
  boards[board] = memory;
  return boards;
}

/**
 * Puts a scale in place, as a knob in a trough.
 * @param {string} id - The slider's own id.
 * @param {string} unit - What the figures are counted in, said once beside
 *   the scale rather than on every tick.
 * @param {ScaleStep[]} steps - In the order they sit on the scale, smallest
 *   first.
 * @param {number} value - Which of them the machine is on. One that is not a
 *   step leaves the knob at the start, which is what a total made by hand out
 *   of the banks does.
 * @param {(value: number) => void} choose - Given the value landed on.
 *
 * For a group whose values have an order, where a row of cells would say they
 * have none. The groups that are not a scale keep their cells: a machine type,
 * a board, a DSP, a socket, a drive and a port are all one of several rather
 * than more or less of one thing.
 */
function fillWithScale(id, unit, steps, value, choose) {
  const slider = byId(id, NxSlider);
  slider.says = unit;
  if (!SCALE_ACTIONS.has(id)) {
    slider.addEventListener("nx-slide", (event) => {
      const landed = event.detail.value;
      if (typeof landed === "number") SCALE_ACTIONS.get(id)?.(landed);
    });
  }
  SCALE_ACTIONS.set(id, choose);
  slider.options = steps;
  slider.value = value;
}

/**
 * Puts one group of things a machine either has or has not in place.
 * @param {string} id - The row they go in.
 * @param {Offers} offers - The service's answer, which says which of them this
 *   machine can have at all.
 * @param {Settled} settled - The machine the window shows.
 * @param {[Switch, string][]} fittings - `[name, label]` for each.
 * @returns {Switch[]} The names of the ones this machine was offered, so the
 *   caller can say what each is doing in the state it is in.
 *
 * One press puts it in and the next takes it out, which is the boards group's
 * cell. A machine that cannot have one is not offered it rather than being
 * offered it and refused.
 */
function fillWithFittings(id, offers, settled, fittings) {
  const offered = fittings.filter(([which]) => offers[which]);
  fillWithChoices(id, offered.map(([which, label]) => ({
    label,
    chosen: settled[which],
    choose: () => change({ [which]: !holding(which, settled) }),
  })));
  return offered.map(([which]) => which);
}

/**
 * Puts the four memory banks in place, as the sockets they are.
 * @param {string} id - The row they go in.
 * @param {number[][]} offered - What each bank accepts, from the service,
 *   smallest first and with an empty bank as the first of them.
 * @param {Settled} settled - The machine the window shows.
 *
 * A bank is a socket on the board rather than one choice among several, so it
 * is drawn as one: a sunken field with a raised module in it where something is
 * seated. Those two edges are what this whole interface is built from, so this
 * needs no picture of a memory module, and there is none to use.
 *
 * A bank the machine cannot reach accepts nothing but an empty bank, and it is
 * drawn flat, because a socket that is not there is not a socket to fill.
 */
function fillWithBanks(id, offered, settled) {
  byId(id).replaceChildren(...offered.map((sizes, bank) => {
    const size = settled.banks[bank];

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
       bank of a color station: it takes an 8 MB module and nothing else. */
    if (sizes.length > 1) {
      socket.addEventListener("click", () => change({
        banks: bankMovedOn(settled, bank, sizes),
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
 * @param {number[]} sizes - What it accepts, from the service.
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
 * @param {Settled} settled - The machine the window shows.
 * @param {number} bank - Which one was pressed, from 0.
 * @param {number[]} sizes - What that bank accepts, smallest first, with an
 *   empty bank as the first of them.
 * @returns {[number, number, number, number]} All four, in megabytes, for the
 *   service to settle.
 *
 * A bank holds one module rather than a choice between several, so its cell
 * fits the next size up and comes back to an empty bank after the largest. It
 * is the same gesture as taking a board out and putting it back, which is the
 * one this window already has for a cell that is not one of a row of choices.
 *
 * A bank holding a size the machine no longer takes starts again at the
 * smallest, because indexOf answers -1 for it.
 */
function bankMovedOn(settled, bank, sizes) {
  /** @type {[number, number, number, number]} */
  const banks = [...holding("banks", settled)];
  banks[bank] = sizes[(sizes.indexOf(banks[bank]) + 1) % sizes.length];
  return banks;
}

/**
 * Puts one group's cells in place.
 * @param {string} id - The row they go in.
 * @param {Cell[]} cells - One for each choice, in the order they stand.
 *
 * The same raised cell the Preferences window offers a choice with, because
 * this interface gives anything that can be chosen one shape.
 */
function fillWithChoices(id, cells) {
  byId(id).replaceChildren(...cells.map((cell) => {
    const choice = document.createElement("div");
    choice.className = "choice";
    choice.textContent = cell.label;
    choice.toggleAttribute("chosen", cell.chosen);
    choice.addEventListener("click", cell.choose);
    return choice;
  }));
}

export {
  drawTheDimensionBoards,
  fillWithScale,
  fillWithFittings,
  fillWithBanks,
  isAbsent,
  fillWithChoices,
};
