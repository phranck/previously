/* Putting words into the page, and saying so when there are none. */

/**
 * Writes text into an element by id.
 * @param {string} id
 * @param {string} text
 */
function show(id, text) {
  document.getElementById(id).textContent = text;
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
  document.getElementById(id)
    .replaceChildren(lamp, document.createTextNode(" " + words));
}

export {
  show,
  explain,
  showState,
};
