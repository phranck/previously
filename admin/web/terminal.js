/* The terminal view, which is the one part of this interface that is not the
 * kit's.
 *
 * Everything else here is written from nothing. A terminal is not: what
 * arrives from a shell is a stream of escape sequences that move a cursor,
 * set a colour, switch to an alternate screen and scroll a region, and
 * writing that again would be a project of its own. xterm.js does it, and it
 * is in vendor/ with its licence beside it.
 *
 * So this element stays out of the kit, which takes nothing from anybody. It
 * is a view and nothing more: it draws what it is given, says what was typed
 * into it, and says how large it has become. What is on the other end is the
 * page's business.
 */

/** What NeXT's Terminal looked like, as xterm's theme.
 *
 *  Black on white, which is the whole of it: NeXTSTEP drew its terminal in
 *  one colour on paper. The sixteen ANSI colours stay, because a shell that
 *  paints its prompt and its listings is saying something with them, but the
 *  pale ones are darkened. Yellow on white is the one nobody can read. */
const NEXT_THEME = {
  background: "#ffffff",
  foreground: "#000000",
  cursor: "#000000",
  cursorAccent: "#ffffff",
  selectionBackground: "#aaaaaa",
  selectionForeground: "#000000",
  black: "#000000",
  red: "#a02020",
  green: "#006000",
  yellow: "#805000",
  blue: "#0000c0",
  magenta: "#800080",
  cyan: "#006060",
  white: "#555555",
  brightBlack: "#555555",
  brightRed: "#c03030",
  brightGreen: "#008000",
  brightYellow: "#a06000",
  brightBlue: "#0000ee",
  brightMagenta: "#a000a0",
  brightCyan: "#008080",
  brightWhite: "#000000",
};

/** How large a session starts, before anything has been measured. The shell
 *  is told the real size as soon as the window has one. */
const STARTING_SIZE = { rows: 24, cols: 80 };

/**
 * A terminal, drawn the way NeXT's was.
 *
 * @fires nx-typed - Somebody typed, carrying the characters in `detail.data`.
 * @fires nx-sized - The view changed size, carrying `detail.rows` and
 *   `detail.columns`, which is what the far side has to be told so that
 *   anything drawing itself is drawn in the right place.
 */
class NxTerminal extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    /* Without the library this is an empty view rather than an error. The
       mockup has no Pi behind it and loads no vendor, and a kit that throws
       there would take the rest of the page with it. */
    if (typeof Terminal !== "function") return;

    this.terminal = new Terminal({
      theme: NEXT_THEME,
      fontFamily: getComputedStyle(document.body).getPropertyValue("--mono").trim(),
      fontSize: 12,
      lineHeight: 1.35,
      cursorBlink: true,
      cursorStyle: "block",
      /* NeXT's Terminal kept what had scrolled off, and so does this. */
      scrollback: 2000,
      allowProposedApi: true,
      ...STARTING_SIZE,
    });
    this.terminal.open(this);

    /* What scrolls is the viewport the library builds, not this element, so
       the scroller around it is pointed at that. It exists only once open has
       run, which is why this is said here rather than in the markup. */
    this.closest("nx-scroller")?.drive(this.querySelector(".xterm-viewport"));

    if (typeof FitAddon === "object" && FitAddon.FitAddon) {
      this.fitter = new FitAddon.FitAddon();
      this.terminal.loadAddon(this.fitter);
    }

    this.terminal.onData((data) => this.dispatchEvent(
      new CustomEvent("nx-typed", { bubbles: true, detail: { data } })));

    this.terminal.onResize(({ rows, cols }) => this.dispatchEvent(
      new CustomEvent("nx-sized", { bubbles: true, detail: { rows, columns: cols } })));

    /* The window is resized by dragging, which changes this box without
       anything telling it so. */
    new ResizeObserver(() => this.fit()).observe(this);
  }

  /**
   * Draws what the far side said.
   * @param {Uint8Array|string} data
   */
  write(data) {
    this.terminal?.write(data);
  }

  /** Measures the view and tells the terminal how many rows and columns fit. */
  fit() {
    if (!this.terminal || !this.fitter) return;
    if (!this.offsetWidth || !this.offsetHeight) return;
    try {
      this.fitter.fit();
    } catch {
      /* Measuring a view that is not laid out yet, which the next one
         answers. */
    }
  }

  /** Puts the cursor here, so that typing goes to the shell. */
  focus() {
    this.terminal?.focus();
  }

  /** @returns {object} How large it is now, in rows and columns. */
  get size() {
    return this.terminal
      ? { rows: this.terminal.rows, columns: this.terminal.cols }
      : { ...STARTING_SIZE, columns: STARTING_SIZE.cols };
  }

  /** Empties it, which is what a new session starts from. */
  clear() {
    this.terminal?.reset();
  }
}

customElements.define("nx-terminal", NxTerminal);
