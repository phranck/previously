/**
 * The page for the page's own tests: the kit's desk from `tests/kit/desk.js`
 * with the markup of `interface/index.html` laid on it, and the service
 * answered by whatever the test says.
 *
 * The modules under test are imported by each test file itself, after this,
 * so they find the document and `fetch` this puts in place.
 */
import { after } from "node:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

import { lay } from "../kit/desk.js";
import { MARKUP } from "./served.js";

/* The answers a test writes live beside the markup, where a test that starts
   the page without the kit's desk reaches them too. Offered here as well, so a
   test on the desk imports everything it needs from one place. */
export { json, never, settled } from "./served.js";

/* What the page leaves running, such as the timeout a POST is sent with, would
   keep the run going until it fires. Taking the window down clears it. */
after(() => GlobalRegistrator.unregister());

/** Lays the whole page on an empty desk, with nothing remembered. */
export function layThePage() {
  lay(MARKUP);
}

/**
 * Says how the service answers, for every request the page makes from now on.
 * @param {(route: string, options?: object) => Promise<Response>} answer
 */
export function answering(answer) {
  globalThis.fetch = answer;
}
