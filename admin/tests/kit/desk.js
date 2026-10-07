/**
 * A desk for the kit's tests: a document in Node, with the kit's stylesheet on
 * it and every element the kit brings defined, so a test lays out markup and
 * reads back what the elements made of it.
 *
 * The document is happy-dom's. It lays nothing out, so every size it reports
 * is zero, and a test that needs one says so on the element it measures. The
 * stylesheet is loaded all the same, because the kit reads its own measures
 * out of it: the dock counts its slots in `--dock-width`, and a window takes
 * its floor from `--win-min-w`.
 *
 * What is loaded is the kit as the interface imports it, out of
 * `interface/nextstep.js`, which `tests/test_kit.py` holds to the sources in
 * `design/kit/`. So a fault in a part fails here once `make kit` has run.
 */
import { readFileSync } from "node:fs";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

/** The screen NeXTSTEP was drawn for, which is what the kit is measured on. */
GlobalRegistrator.register({ width: 1120, height: 832 });

const stylesheet = document.createElement("style");
stylesheet.textContent = readFileSync(
  new URL("../../interface/nextstep.css", import.meta.url), "utf-8");
document.head.append(stylesheet);

/* happy-dom resolves a custom property on the element that declares it and
   hands it on to nothing beneath, where a browser lets every element inherit
   it. The kit declares its measures on :root and reads them off the elements
   that use them, so they are declared once more on every element. Without it
   the dock reads a slot as no height at all and never finds a free one. */
const rootProperties = [...stylesheet.textContent
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .matchAll(/:root\s*\{([^}]*)\}/g)]
  .flatMap(([, block]) => block.match(/--[\w-]+\s*:[^;]+;/g) ?? []);
const inherited = document.createElement("style");
inherited.textContent = `* { ${rootProperties.join(" ")} }`;
document.head.append(inherited);

/** Everything the kit offers, as the interface imports it. */
export const kit = await import("../../interface/nextstep.js");
kit.defineTheKit();

/**
 * Lays markup on an empty desk, after forgetting everything the desk
 * remembered, so no test inherits where another one left a window.
 *
 * Parsed whole before it reaches the desk, so every element finds its
 * children in place when it is connected, as it does on the page. Written
 * straight into the body, happy-dom connects an element before its children
 * are parsed, and a scroller would then wrap nothing.
 *
 * @param {string} markup - What the body holds.
 * @param {object} [remembered] - What the desk remembers before the markup
 *   arrives, by the name each element is remembered under, as the kit's own
 *   store holds it.
 * @returns {Element} The first element in it.
 */
export function lay(markup, remembered = {}) {
  localStorage.clear();
  localStorage.setItem(kit.STORE, JSON.stringify(remembered));
  const parsed = document.createElement("template");
  parsed.innerHTML = markup;
  document.body.replaceChildren(parsed.content.cloneNode(true));
  return document.body.firstElementChild;
}

/** @returns {object} Everything the desk remembers now, as the kit wrote it. */
export function remembered() {
  return JSON.parse(localStorage.getItem(kit.STORE));
}

/**
 * Gives an element a size the document cannot work out for itself.
 *
 * @param {Element} element - What is measured.
 * @param {object} sizes - Each property and the number it answers, such as
 *   `{ scrollHeight: 400, clientHeight: 100 }`.
 */
export function measure(element, sizes) {
  for (const [property, value] of Object.entries(sizes)) {
    Object.defineProperty(element, property, { value, configurable: true });
  }
}
