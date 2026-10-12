/* Putting words into the page, and saying so when there are none. */

import { NxMenuItem } from "../nextstep.js";

/** @typedef {import("../nextstep.js").NxMenu} NxMenu */
/** @typedef {import("../nextstep.js").NxWindow} NxWindow */

/**
 * @overload
 * @param {string} id
 * @returns {HTMLElement}
 */
/**
 * @template {Element} Type
 * @overload
 * @param {string} id
 * @param {new () => Type} type
 * @returns {Type}
 */
/**
 * An element of the page, by its id.
 * @param {string} id
 * @param {new () => Element} [type] - What it is, where more than an
 *   HTMLElement is wanted of it, such as a button or one of the kit's own.
 * @returns {Element}
 *
 * The markup is this page's own, and `tests/test_page.py` holds every id the
 * page names to it, so one that is missing or of another type is a mistake in
 * this repository and says so at once rather than as a null somewhere later.
 */
function byId(id, type = HTMLElement) {
  const found = document.getElementById(id);
  if (!(found instanceof type)) throw new Error(`the page has no ${type.name} #${id}`);
  return found;
}

/**
 * Writes text into an element by id.
 * @param {string} id
 * @param {string} text
 */
function show(id, text) {
  byId(id).textContent = text;
}

/**
 * Says what the chosen setting of a group does, under its cells.
 * @param {string} id - The note under that group.
 * @param {...string} sentences - One per setting the group holds. A group of
 *   one choice sends one, a group of switches sends one per switch, and a
 *   sentence that does not apply arrives as nothing and is left out.
 *
 * Written by the page rather than carried by the markup, because which
 * sentence applies follows from what is chosen. A note with nothing to say
 * hides itself, which the kit's stylesheet does for an empty one.
 */
function explain(id, ...sentences) {
  show(id, sentences.filter(Boolean).join(" "));
}

/**
 * Puts a lamp and a sentence into a field.
 * @param {string} id
 * @param {boolean} well - Whether this reading is the good case.
 * @param {string} words
 */
function showState(id, well, words) {
  const lamp = document.createElement("span");
  lamp.className = "lamp";
  if (!well) lamp.style.background = "var(--dark)";
  byId(id).replaceChildren(lamp, document.createTextNode(" " + words));
}

/**
 * The window of that name, or nothing where none is in the page.
 * @param {string} name - What the markup calls it.
 * @returns {NxWindow | null} The window, carrying open, close, raise and
 *   rename.
 *
 * A dozen places were building the same selector, and what comes back from
 * one the checker did not write is an Element, which has none of a window's
 * own doings on it. Asked here, both the selector and that answer are in one
 * place.
 */
function theWindow(name) {
  return /** @type {NxWindow | null} */ (
    document.querySelector(`nx-window[name="${name}"]`));
}

/**
 * The menu of that name, or nothing where none is in the page.
 * @param {string} name - What the markup calls it.
 * @returns {NxMenu | null} The menu, carrying openAt and close.
 */
function theMenu(name) {
  return /** @type {NxMenu | null} */ (
    document.querySelector(`nx-menu[name="${name}"]`));
}

/**
 * One entry of a menu, by its name.
 * @param {NxMenu} menu - The menu it is in.
 * @param {string} name - What the markup calls the entry.
 * @returns {NxMenuItem} The entry.
 *
 * A context menu sets what each of its entries does every time it opens, so
 * it reaches for every one of them by name. An entry missing from the markup
 * is a mistake in this repository, and says so here the way byId does.
 */
function menuEntry(menu, name) {
  const found = menu.querySelector(`nx-menu-item[name="${name}"]`);
  if (!(found instanceof NxMenuItem)) throw new Error(`the menu has no entry ${name}`);
  return found;
}

/**
 * The name the element an event happened on carries, such as a window's.
 * @param {EventTarget | null} target - Where the event happened.
 * @returns {string | null} Its `name`, or null where it is not an element or
 *   carries none.
 *
 * A window raises its events on itself, and they bubble to the document, so
 * the one listener there tells the windows apart by this.
 */
function targetName(target) {
  return target instanceof Element ? target.getAttribute("name") : null;
}

export {
  byId,
  show,
  targetName,
  explain,
  showState,
  theMenu,
  menuEntry,
  theWindow,
};
