/* How large the interface is drawn. */

import { setDeskScale } from "../nextstep.js";
/** What the interface can be drawn at. */
const SIZES = [1, 1.25, 1.5, 1.75, 2];

/** What a browser that has never been told draws it at. Not the original's
 *  own, because that is measured for a screen 1120 across and this is read on
 *  panels several times that, where a first look at 100% is an interface
 *  somebody has to go and enlarge before they can use it. */
const SIZE_AT_FIRST = 1.25;

/** Where the choice is kept. The browser's, like the language: how large one
 *  person needs this drawn is not a property of the machine. */
const SIZE_KEY = "previously:size";

/** @returns {number} The size last chosen, or the one a first look takes. */
function chosenSize() {
  const saved = Number(localStorage.getItem(SIZE_KEY));
  return SIZES.includes(saved) ? saved : SIZE_AT_FIRST;
}

/**
 * Draws the interface at that size and keeps the choice.
 * @param {number} scale - One of what SIZES offers.
 */
function drawAtSize(scale) {
  setDeskScale(scale);
  try {
    localStorage.setItem(SIZE_KEY, String(scale));
  } catch {
    /* A browser that refuses to store it still draws it this way for now. */
  }
  drawSizes();
}

/** Draws the row of sizes, with the one in force marked.
 *
 * Each button shows a letter at the size it sets, which is what Preferences
 * does wherever a setting can be shown rather than described: its Keyboard
 * module draws the repeat rate as letters at four spacings.
 *
 * Under the letter is the figure the step is, because a letter alone says
 * which is larger and not by how much. Five steps also outgrow a set of names:
 * Normal, Large and Largest is a scale that does not extend, and two more
 * words for the gaps would be a vocabulary rather than a scale. The figure
 * reads the same in every language, and 100% says which one is the original.
 */
function drawSizes() {
  const row = /** @type {any} */ (document.getElementById("size-choices"));
  if (!row) return;
  row.replaceChildren(...SIZES.map((scale) => {
    const choice = document.createElement("div");
    choice.className = "choice";
    choice.toggleAttribute("chosen", scale === chosenSize());

    const sample = document.createElement("div");
    sample.className = "sample";
    sample.textContent = "A";
    /* The size this button sets, shown at that size against the interface's
       own, so the five of them read as one scale. */
    sample.style.fontSize = `calc(var(--text-size) * ${scale})`;

    const under = document.createElement("div");
    under.className = "choice-name";
    under.textContent = Math.round(scale * 100) + " %";

    choice.append(sample, under);
    choice.addEventListener("click", () => drawAtSize(scale));
    return choice;
  }));
}

export {
  chosenSize,
  drawAtSize,
  drawSizes,
};
