/**
 * The page for the page's own tests: the kit's desk from `tests/kit/desk.js`
 * with the markup of `interface/index.html` laid on it, and the service
 * answered by whatever the test says.
 *
 * The modules under test are imported by each test file itself, after this,
 * so they find the document and `fetch` this puts in place.
 */
import { after } from "node:test";
import { readFileSync } from "node:fs";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

import { lay } from "../kit/desk.js";

/* What the page leaves running, such as the timeout a POST is sent with, would
   keep the run going until it fires. Taking the window down clears it. */
after(() => GlobalRegistrator.unregister());

/** The page's own markup, the body of interface/index.html without its
 *  scripts: the modules under test are imported by the tests, and happy-dom
 *  refuses to load a script file. */
const markup = readFileSync(new URL("../../interface/index.html", import.meta.url), "utf-8")
  .split("<body>")[1].split("</body>")[0]
  .replace(/<script\b[\s\S]*?<\/script>/g, "");

/** Lays the whole page on an empty desk, with nothing remembered. */
export function layThePage() {
  lay(markup);
}

/**
 * Says how the service answers, for every request the page makes from now on.
 * @param {(route: string, options?: object) => Promise<Response>} answer
 */
export function answering(answer) {
  globalThis.fetch = answer;
}

/**
 * @param {object} body - What to answer with, as JSON.
 * @param {number} [status] - The status line.
 * @returns {Response}
 */
export function json(body, status = 200) {
  return new Response(JSON.stringify(body),
                      { status, headers: { "Content-Type": "application/json" } });
}

/** @returns {Promise<never>} An answer that never comes, so nothing that waits
 *  for it draws over what a test is looking at. */
export function never() {
  return new Promise(() => {});
}

/** @returns {Promise<void>} Once everything already started has run. */
export function settled() {
  return new Promise((resolve) => setTimeout(resolve, 20));
}
