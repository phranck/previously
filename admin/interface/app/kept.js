/* What somebody put somewhere, such as the shelf or the dock, kept in this
   browser by the paths of what was put there. */

/**
 * Reads one list of paths back.
 * @param {string} key - Which list, as localStorage knows it.
 * @param {string[]} first - What it holds before anybody has changed it.
 * @returns {string[]} The paths, in the order they were put there. An empty
 *   list is one somebody emptied, and is read back as itself.
 */
function readPaths(key, first) {
  try {
    /** @type {unknown} */
    const saved = JSON.parse(localStorage.getItem(key) ?? "null");
    return Array.isArray(saved)
      ? saved.filter((path) => typeof path === "string")
      : [...first];
  } catch {
    return [...first];
  }
}

/**
 * Writes one list of paths down.
 * @param {string} key - Which list.
 * @param {string[]} paths - All of them, in order.
 */
function writePaths(key, paths) {
  try {
    localStorage.setItem(key, JSON.stringify(paths));
  } catch {
    /* A browser that refuses to store it still shows it for this visit. */
  }
}

export {
  readPaths,
  writePaths,
};
