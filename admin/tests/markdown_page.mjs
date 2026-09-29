/* Just enough of a page to run `markdown.js` outside a browser.
 *
 * That module imports nothing of ours and touches six things a document can do,
 * so this is all it takes to exercise the real renderer rather than a copy of
 * its rules. What comes out is written as an indented tree on stdout, which is
 * a shape a test can read without a parser.
 *
 * Writing the tree rather than markup is the point: a test that compared markup
 * would be a test that built markup, which is the one thing the renderer is
 * built not to do.
 */

class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attributes = {};
  }

  set textContent(text) { this.children = [String(text)]; }

  append(...things) { this.children.push(...things); }

  setAttribute(name, value) { this.attributes[name] = value; }

  /* The three a link sets, which the renderer writes as properties. */
  set href(value) { this.attributes.href = value; }

  set target(value) { this.attributes.target = value; }

  set rel(value) { this.attributes.rel = value; }
}

globalThis.document = {
  createElement: (tag) => new Element(tag),
  createTextNode: (text) => String(text),
  createDocumentFragment: () => new Element("#fragment"),
};

/**
 * One node and everything under it, one per line, indented by how deep it is.
 * @param {Element|string} node
 * @param {number} depth
 * @returns {string}
 */
function written(node, depth = 0) {
  const pad = "  ".repeat(depth);
  if (typeof node === "string") return `${pad}text ${JSON.stringify(node)}`;

  const attributes = Object.entries(node.attributes)
    .map(([name, value]) => ` ${name}=${JSON.stringify(value)}`).join("");
  return [`${pad}${node.tag}${attributes}`,
          ...node.children.map((child) => written(child, depth + 1))].join("\n");
}

const here = new URL("../interface/app/markdown.js", import.meta.url);
const { render } = await import(here.href);

/* The notes arrive on stdin rather than as an argument, because they carry
   newlines and a shell is not the place to put those. */
const written_ = [];
for await (const chunk of process.stdin) written_.push(chunk);
console.log(written(render(Buffer.concat(written_).toString("utf-8"))));
