/**
 * What the page is given: its own markup, its own files as the build wrote
 * them, and the answers a test writes for what it asks the service.
 *
 * Nothing here touches a document, so a test that starts the page the way a
 * browser does can use all of it before any element of the kit is defined.
 */
import { readFileSync } from "node:fs";

/** What the service serves the page out of, which is what `build_web.py`
 *  writes. */
const WEB = new URL("../../web/", import.meta.url);

/** The status the service answers a file it does not have with. */
const NOT_FOUND = 404;

/** What the service says beside that status, which is JSON like every answer
 *  of its own, as `_file` in `previously/server.py` writes it. So a page that
 *  read a refusal as a file would find something to read. */
const NOT_FOUND_BODY = { error: "not found" };

/** How long `settled` waits, which is longer than anything a test has already
 *  started takes to run once nothing it waits for is outstanding. */
const SETTLING_MS = 20;

/** The page's own markup, the body of interface/index.html without its
 *  scripts: the modules under test are imported by the tests, and happy-dom
 *  refuses to load a script file. */
export const MARKUP = readFileSync(new URL("../../interface/index.html", import.meta.url), "utf-8")
  .split("<body>")[1].split("</body>")[0]
  .replace(/<script\b[\s\S]*?<\/script>/g, "");

/**
 * Answers a request for one of the page's files the way the service does.
 *
 * Out of `web/`, because that is what a browser is given. So a route the page
 * asks for and a file the build writes are held to each other here: where the
 * two part company, the page is told 404 exactly as it would be on the Pi.
 *
 * @param {string} route - What the page asked for, relative to the page, such
 *   as `lang/de.json`.
 * @returns {Response} The file with status 200, or `notFound()` where `web/`
 *   holds no such file.
 */
export function served(route) {
  try {
    return new Response(readFileSync(new URL(route, WEB)));
  } catch {
    return notFound();
  }
}

/** @returns {Response} What the service answers for a file it does not have:
 *  404, with a body of JSON that is not the file. */
export function notFound() {
  return json(NOT_FOUND_BODY, NOT_FOUND);
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
  return new Promise((resolve) => setTimeout(resolve, SETTLING_MS));
}
