/* The words, in the six languages NeXTSTEP itself shipped.
 *
 * English, German, French, Italian, Spanish and Swedish, because a tool that
 * looks like NeXTSTEP should not speak fewer languages than it did. English is
 * the default, because that is what the system fell back to and because an
 * unfamiliar interface in a language one does not read is worse than one in
 * English.
 *
 * Every catalogue is loaded with the page. All six together are smaller than
 * one of the pictures in the stylesheet, and loading them all is what makes a
 * change of language instant and the code that changes it three lines long.
 * Nothing is fetched, nothing waits, and nothing shows the wrong language
 * whilst the right one arrives.
 */

/** Where each catalogue registers itself. `lang/en.js` and the rest fill this
 *  as they load, before anything reads from it. */
const NX_STRINGS = {};

/** The one that is always complete, and the one every other falls back to. */
const FALLBACK = "en";

/** Where the choice is kept, beside the window positions. It belongs to the
 *  browser rather than to the Pi: which language one person reads is not a
 *  property of the machine. */
const LANGUAGE_KEY = "previously:language";

/** What each catalogue is called, in its own language. The Preferences window
 *  offers these, and a language named in a language one does not read is no
 *  help to anybody. */
const LANGUAGE_NAMES = {
  en: "English",
  de: "Deutsch",
  fr: "Français",
  it: "Italiano",
  es: "Español",
  sv: "Svenska",
};

/** Which locale each language formats its dates in. German is Austrian here
 *  because that is where this machine stands; the others take the plain
 *  language, so a date comes out the way that language writes one. */
const LOCALES = {
  en: "en-GB",
  de: "de-AT",
  fr: "fr-FR",
  it: "it-IT",
  es: "es-ES",
  sv: "sv-SE",
};

/** The language in force. Read once at the start and kept here, so the lookup
 *  costs nothing. */
let language = readLanguage();

/**
 * @returns {string} The language last chosen, or English where none was or
 *   where what was chosen no longer exists.
 */
function readLanguage() {
  const saved = localStorage.getItem(LANGUAGE_KEY);
  return saved && LANGUAGE_NAMES[saved] ? saved : FALLBACK;
}

/** @returns {string} Which language the interface is in. */
function currentLanguage() {
  return language;
}

/** @returns {string} The locale to format a date or a number in. */
function currentLocale() {
  return LOCALES[language] ?? LOCALES[FALLBACK];
}

/**
 * Looks a string up in the language in force.
 * @param {string} key - What the string is called, such as `info.processor`.
 * @param {object} [values] - What fills the `{name}` places in it.
 * @param {number} [count] - Where the string has one wording for one thing and
 *   another for several, the number of things. The browser knows each
 *   language's own rule for which is which, so `lang/fr.js` gets the singular
 *   for zero and `lang/en.js` the plural, without either catalogue saying so.
 * @returns {string} The string with its places filled. A key the catalogues do
 *   not know comes back as itself, which is ugly on the screen and easy to
 *   find, and both of those are better than silence.
 */
function t(key, values, count) {
  const wanted = count === undefined
    ? key
    : `${key}.${new Intl.PluralRules(currentLocale()).select(count)}`;
  const line = NX_STRINGS[language]?.[wanted]
    ?? NX_STRINGS[FALLBACK]?.[wanted]
    ?? wanted;
  return fill(line, values);
}

/**
 * Puts values into a string's `{name}` places.
 * @param {string} line
 * @param {object} [values]
 * @returns {string} A place nothing was given for keeps its braces, so a
 *   catalogue entry that names a value the caller does not send shows up
 *   rather than leaving a hole.
 */
function fill(line, values) {
  if (!values) return line;
  return line.replace(/\{(\w+)\}/g, (whole, name) =>
    (name in values ? String(values[name]) : whole));
}

/**
 * Writes every string in the document, or in part of it.
 * @param {ParentNode} [root] - Where to look. The whole document by default.
 *
 * Three attributes, because a string reaches the screen three ways: as the
 * text of an element, as the title of a window or a menu, and as the letter
 * beside a menu entry. The markup carries the key and no text at all, so
 * nothing can show the wrong language even for a moment.
 *
 * Runs once before the kit builds its elements, and again whenever the
 * language changes, which is why each case below is written to hold both
 * before and after that.
 */
function translate(root = document) {
  document.documentElement.lang = language;

  for (const element of root.querySelectorAll("[data-t]")) {
    writeWords(element, t(element.dataset.t));
  }
  for (const element of root.querySelectorAll("[data-t-title]")) {
    writeTitle(element, t(element.dataset.tTitle));
  }
  for (const element of root.querySelectorAll("[data-t-key]")) {
    writeKey(element, t(element.dataset.tKey));
  }
}

/**
 * Puts text into an element without disturbing what is around it.
 * @param {HTMLElement} element
 * @param {string} text
 *
 * A menu entry ends up holding a picture, its words and its shortcut letter,
 * in that order, and the kit builds the first and the last around the middle.
 * Writing the whole element's text would throw both away, so the text node
 * itself is written where there is one, and a new one is added beside what is
 * there where there is not.
 */
function writeWords(element, text) {
  const words = [...element.childNodes].find((node) => node.nodeType === Node.TEXT_NODE);
  if (words) words.data = text;
  else element.append(document.createTextNode(text));
}

/**
 * Puts text in the bar of a window or a menu.
 * @param {HTMLElement} element
 * @param {string} text
 *
 * Three ways, because there are three states to catch. A window that is built
 * renames itself. A menu that is built has a bar to write into. Anything not
 * built yet takes the attribute, which is what the kit reads a moment later.
 */
function writeTitle(element, text) {
  if (element.rename) return element.rename(text);
  const bar = element.querySelector(":scope > .title");
  if (bar) bar.textContent = text;
  else element.setAttribute("title", text);
}

/**
 * Puts the letter beside a menu entry, and gives the page the letter to act on.
 * @param {HTMLElement} element - A menu entry.
 * @param {string} letter
 *
 * Both, because they are two views of one thing: the attribute is what the
 * key handler compares a press against, and the span is what a person reads.
 * Writing only one of them would leave a shortcut whose letter is not the
 * letter on the screen, which is the whole of what this answers.
 *
 * The span exists once the kit has built the entry, and before that the
 * attribute is what the kit builds it from, so this holds at either moment.
 */
function writeKey(element, letter) {
  element.setAttribute("key", letter);
  const shown = element.querySelector(":scope > .key");
  if (shown) shown.textContent = letter;
}

/**
 * Changes the language the interface speaks.
 * @param {string} code - One of the six.
 * @param {() => void} [redraw] - What to call so the parts the page writes
 *   itself are written again. The document's own strings are handled here.
 * @returns {boolean} Whether that language exists.
 */
function setLanguage(code, redraw) {
  if (!LANGUAGE_NAMES[code]) return false;
  language = code;
  try {
    localStorage.setItem(LANGUAGE_KEY, code);
  } catch {
    /* A browser that refuses to store it still speaks it for this visit. */
  }
  translate();
  redraw?.();
  return true;
}
