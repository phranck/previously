/* What somebody put somewhere, such as the shelf or the dock, and where they
   were, such as the folder the File Viewer shows, kept in this browser by the
   paths of those things. */

/**
 * @param {string} key - Which, as localStorage knows it.
 * @returns {unknown} What is kept under it, or null where nothing readable is.
 */
function stored(key) {
  try {
    return JSON.parse(localStorage.getItem(key) ?? "null");
  } catch {
    return null;
  }
}

/**
 * Reads one list of paths back.
 * @param {string} key - Which list, as localStorage knows it.
 * @param {string[]} first - What it holds before anybody has changed it.
 * @returns {string[]} The paths, in the order they were put there. An empty
 *   list is one somebody emptied, and is read back as itself.
 */
function readPaths(key, first) {
  const saved = stored(key);
  return Array.isArray(saved)
    ? saved.filter((path) => typeof path === "string")
    : [...first];
}

/**
 * Reads one path back.
 * @param {string} key - Which, as localStorage knows it.
 * @param {string} first - What it is before anybody has moved.
 * @returns {string} The path.
 */
function readPath(key, first) {
  const saved = stored(key);
  return typeof saved === "string" ? saved : first;
}

/**
 * Writes a path, or a list of them, down.
 * @param {string} key - Which, as localStorage knows it.
 * @param {string | string[]} paths - The path, or all of them in order.
 */
function writeDown(key, paths) {
  try {
    localStorage.setItem(key, JSON.stringify(paths));
  } catch {
    /* A browser that refuses to store it still shows it for this visit. */
  }
}

export {
  readPath,
  readPaths,
  writeDown,
};
