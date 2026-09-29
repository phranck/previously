/* Markdown, turned into elements rather than into markup.
 *
 * Release notes arrive from GitHub as the Markdown somebody wrote, so they are
 * text off a network reaching a page. Nothing here ever builds a string of
 * markup: every piece of that text becomes the contents of an element created
 * here, which is what makes escaping structural rather than a thing to
 * remember. `tests/test_page.py` holds the whole interface to that, so the
 * shorter road is closed here and everywhere else.
 *
 * What it understands is what release notes use: headings, paragraphs, fenced
 * code, lists, and inside a line a piece of code, something in bold and a link.
 * Anything else is left as the text it is, which reads as itself rather than
 * disappearing, and that is the right failure for a document somebody wrote by
 * hand.
 *
 * A Markdown library would understand more and would be a licence, a weight and
 * a supply chain for a tool that ships to a Raspberry Pi. What it would buy is
 * constructs these notes do not use.
 */

/** A fence, and the language written after it where there is one. */
const FENCE = /^```(\w*)\s*$/;

/** A heading, by how many hashes it carries. Three deep, because notes that
 *  need a fourth are notes that want splitting. */
const HEADING = /^(#{1,3})\s+(.*)$/;

/** An item of a list, either kind. What follows the marker is the item. */
const BULLET = /^\s*[-*]\s+(.*)$/;
const NUMBERED = /^\s*\d+\.\s+(.*)$/;

/** What is found inside a line: a piece of code, something in bold, or a link.
 *  One pattern rather than three passes, so the first of them in the line wins
 *  and a backtick inside a link's text cannot be read as code. */
const INSIDE = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)/g;

/** Which addresses a link may lead to. Plain HTTP is not one of them: this
 *  interface speaks it on a home network by decision, and a link out of a
 *  document is a different thing from that. */
const ALLOWED = "https:";

/**
 * Turns Markdown into elements.
 * @param {string} text - What was written, as GitHub keeps it.
 * @returns {DocumentFragment} Everything in it, ready to be put into a window.
 */
function render(text) {
  const into = document.createDocumentFragment();
  const lines = String(text ?? "").replace(/\r\n?/g, "\n").split("\n");

  for (let at = 0; at < lines.length; at += 1) {
    const line = lines[at];

    const fence = FENCE.exec(line);
    if (fence) {
      at = code(into, lines, at, fence[1]);
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      into.append(inside(document.createElement(`h${heading[1].length}`),
                         heading[2]));
      continue;
    }

    if (BULLET.test(line) || NUMBERED.test(line)) {
      at = list(into, lines, at);
      continue;
    }

    if (line.trim() === "") continue;
    at = paragraph(into, lines, at);
  }
  return into;
}

/**
 * Takes a fenced block whole, up to its closing fence or the end.
 * @param {DocumentFragment} into @param {string[]} lines
 * @param {number} at - The opening fence.
 * @param {string} language - What the fence named, or "".
 * @returns {number} The line the caller carries on from.
 *
 * Every line between the fences is kept exactly, because that is what a fence
 * is for. The language is set as an attribute rather than acted on: nothing
 * here highlights anything, and a reader who wants to know what they are
 * looking at is told.
 */
function code(into, lines, at, language) {
  const held = [];
  let end = at + 1;
  while (end < lines.length && !FENCE.test(lines[end])) {
    held.push(lines[end]);
    end += 1;
  }

  const block = document.createElement("pre");
  block.textContent = held.join("\n");
  if (language) block.setAttribute("language", language);
  into.append(block);
  return end;
}

/**
 * Takes a run of items as one list.
 * @param {DocumentFragment} into @param {string[]} lines
 * @param {number} at - The first item.
 * @returns {number} The last line of the list.
 *
 * Which kind it is comes from the first item, so a run that starts numbered
 * stays numbered even where somebody wrote a dash half way down. Two lists of
 * different kinds touching are two runs and become two lists.
 */
function list(into, lines, at) {
  const numbered = NUMBERED.test(lines[at]);
  const block = document.createElement(numbered ? "ol" : "ul");

  let end = at;
  while (end < lines.length) {
    const item = (numbered ? NUMBERED : BULLET).exec(lines[end])
      ?? (numbered ? BULLET : NUMBERED).exec(lines[end]);
    if (!item) break;
    block.append(inside(document.createElement("li"), item[1]));
    end += 1;
  }

  into.append(block);
  return end - 1;
}

/**
 * Takes the lines up to the next blank one as one paragraph.
 * @param {DocumentFragment} into @param {string[]} lines
 * @param {number} at - The first line.
 * @returns {number} The last line of the paragraph.
 *
 * Joined with spaces rather than kept as lines, because Markdown wraps a
 * paragraph wherever it was typed and a window is a different width from
 * whatever that was.
 */
function paragraph(into, lines, at) {
  const held = [];
  let end = at;
  while (end < lines.length && lines[end].trim() !== ""
         && !HEADING.test(lines[end]) && !FENCE.test(lines[end])
         && !BULLET.test(lines[end]) && !NUMBERED.test(lines[end])) {
    held.push(lines[end].trim());
    end += 1;
  }

  into.append(inside(document.createElement("p"), held.join(" ")));
  return end - 1;
}

/**
 * Fills one element with a line, with what is inside the line drawn out.
 * @param {HTMLElement} element - What to fill.
 * @param {string} line - The text.
 * @returns {HTMLElement} The same element.
 *
 * Every piece that is not one of the three is a text node, so a line carrying
 * something that looks like markup arrives on the screen as the characters
 * somebody typed.
 */
function inside(element, line) {
  let from = 0;
  INSIDE.lastIndex = 0;

  for (let found = INSIDE.exec(line); found; found = INSIDE.exec(line)) {
    if (found.index > from) {
      element.append(line.slice(from, found.index));
    }
    element.append(piece(found));
    from = found.index + found[0].length;
  }

  if (from < line.length) element.append(line.slice(from));
  return element;
}

/**
 * One thing found inside a line.
 * @param {RegExpExecArray} found - Which of the three matched, and its parts.
 * @returns {Node}
 *
 * A link whose address is not one this may show becomes its own text, so what
 * somebody wrote is read and nothing on the page leads anywhere unexpected.
 */
function piece(found) {
  const [, asCode, asBold, label, address] = found;
  if (asCode !== undefined) return filled("code", asCode);
  if (asBold !== undefined) return filled("b", asBold);

  let where = null;
  try {
    where = new URL(address);
  } catch {
    return document.createTextNode(found[0]);
  }
  if (where.protocol !== ALLOWED) return document.createTextNode(found[0]);

  const link = /** @type {HTMLAnchorElement} */ (filled("a", label));
  link.href = where.href;
  /* A document opens its links away from the desk, which is one page and does
     not come back. `noreferrer` takes the opener with it, so nothing on the
     other side can reach back into this window. */
  link.target = "_blank";
  link.rel = "noreferrer";
  return link;
}

/**
 * @param {string} tag @param {string} text
 * @returns {HTMLElement} One element holding that text and nothing else.
 */
function filled(tag, text) {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

export {
  render,
};
