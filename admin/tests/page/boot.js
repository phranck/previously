/**
 * The page started the way a browser starts it: the markup on its own, no
 * element of the kit defined yet, and `app.js` run as the bundle runs it.
 *
 * `page.js` cannot do this, because its desk defines the kit before any
 * markup is laid. Each test file that starts the page here is a process of
 * its own, since node runs every file apart and a module runs once per
 * process, so the page starts once per file.
 */
import { after } from "node:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

import { MARKUP } from "./served.js";

GlobalRegistrator.register();
after(() => GlobalRegistrator.unregister());

/** The three attributes a string of the catalog reaches the markup through,
 *  and where each one shows: the first text in an element, which is where
 *  `writeWords` puts it, the title of a window, and the letter beside a menu
 *  entry. */
const WRITTEN = [
  { selector: "[data-t]", key: "t", shown: (/** @type {HTMLElement} */ element) =>
    [...element.childNodes].find((node) => node.nodeType === Node.TEXT_NODE)?.textContent ?? "" },
  { selector: "[data-t-title]", key: "tTitle", shown: (/** @type {HTMLElement} */ element) => element.getAttribute("title") ?? "" },
  { selector: "[data-t-key]", key: "tKey", shown: (/** @type {HTMLElement} */ element) => element.getAttribute("key") ?? "" },
];

/**
 * Every string the markup asks for, and what stands there now.
 * @returns {[string, string][]} Each key with what the page shows for it, an
 *   empty string where it shows nothing yet.
 */
export function wordsOnThePage() {
  return WRITTEN.flatMap(({ selector, key, shown }) =>
    [...document.querySelectorAll(selector)].map((element) =>
      [element.dataset[key], shown(element)]));
}

/** What the page was like each time the kit defined an element, in the order
 *  it defined them: the language the document said it was in, and every
 *  string the markup shows.
 *  @type {{name: string, language: string, words: [string, string][]}[]} */
export const definitions = [];

const define = customElements.define.bind(customElements);
customElements.define = (name, constructor, options) => {
  definitions.push({ name, language: document.documentElement.lang, words: wordsOnThePage() });
  return define(name, constructor, options);
};

/**
 * Starts the page.
 * @param {string | null} kept - The language this browser chose on an earlier
 *   visit, as the page keeps it, or null where it chose none.
 * @param {(route: string) => Promise<Response>} answer - How every request the
 *   page makes is answered, the service's and its own files alike.
 * @returns {Promise<void>} Once `app.js` has run as far as it runs without
 *   waiting for an answer.
 */
export async function startThePage(kept, answer) {
  const { LANGUAGE_KEY } = await import("../../interface/strings.js");
  localStorage.clear();
  if (kept !== null) localStorage.setItem(LANGUAGE_KEY, kept);
  globalThis.fetch = answer;
  /* Written straight into the body, because no element is defined yet, so
     each one finds its children in place when the kit defines it. */
  document.body.innerHTML = MARKUP;
  await import("../../interface/app.js");
}
