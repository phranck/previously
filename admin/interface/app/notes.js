/* The sentence under a group in the Config Editor, which says what the choice above it means. */

import { currentLocale, t } from "../strings.js";
import { isAbsent } from "./fittings.js";

/** @typedef {import("../answers.js").DspKind} DspKind */
/** @typedef {import("./editor.js").Settled} Settled */

/** A switch of the Config Editor, which is on or off.
 *  @typedef {"turbo" | "colour" | "floppy" | "optical" | "ethernet" | "printer"} Switch */

/** What each DSP is called. The service answers the three by name, because the
 *  numbers Previous writes are not in the order a person would read them in, and
 *  these are this page's words for those names. Written out one by one rather
 *  than built from the name, so that a key nothing answers is caught by the
 *  strings test instead of appearing as an empty cell.
 *  @type {Record<DspKind, string>} */
const DSP_WORDS = {
  none: "editor.dsp.none",
  plain: "editor.dsp.plain",
  "with-rom": "editor.dsp.with-rom",
};

/** What each ethernet socket is called, written out for the same reason.
 *  @type {Record<string, string>} */
const SOCKET_WORDS = {
  "thin-wire": "editor.thin-wire",
  "twisted-pair": "editor.twisted-pair",
};

/** What the sentence about each machine type is called, by the number Previous
 *  gives the type. Written out rather than built from the number, because a
 *  sentence keyed by a name can be found in the catalog and one keyed by 1
 *  cannot. The strings test holds these numbers to the types the service
 *  offers.
 *  @type {Record<number, string>} */
const KIND_NOTES = {
  0: "editor.machine.note.next-computer",
  1: "editor.machine.note.nextcube",
  2: "editor.machine.note.nextstation",
};

/**
 * The sentence about one value of a group.
 * @param {string} group - The group's name in the catalog, such as `clock`.
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
 * @param {Switch} which - The switch, which is both the control's name in the
 *   draft and its name in the catalog.
 * @param {Settled} settled - The machine the window shows.
 * @returns {string}
 */
function switchNote(which, settled) {
  return noteFor(which, settled[which] ? "in" : "out");
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
 *   browser knows each language's word before the last one, so no catalog
 *   has to say it.
 */
function listed(values) {
  return new Intl.ListFormat(currentLocale(), { type: "disjunction" })
    .format(values.map(String));
}

export {
  DSP_WORDS,
  SOCKET_WORDS,
  KIND_NOTES,
  noteFor,
  switchNote,
  bankNotes,
};
