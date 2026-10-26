/* --- nx-chart ------------------------------------------------------------ */

/** How many readings a chart shows where it does not say. */
const CHART_COLUMNS = 54;

/** How many lamps a column has where it does not say. Nine is what fits in a
 *  field as tall as two rows of readings. */
const CHART_LAMPS = 9;

/**
 * A history of readings as columns of lamps, the newest on the right.
 *
 * NeXTSTEP drew no charts, so this is built from the desk's own row of lamps,
 * nx-leds, turned on its side and repeated: the same sunken black field, the
 * same lamps lit from the bottom, green, then orange and red near the top.
 * Each column is one reading, and a new one moves every column a place to the
 * left.
 *
 * It knows numbers and nothing about what they measure. Whoever uses it says
 * what the top of the field stands for, whether it grows with a reading above
 * that, and from which value a lamp lights orange and red. The colors follow
 * the value a lamp stands for rather than its place, so where the field grows,
 * a lamp that was red can turn green.
 *
 * @attr columns - How many readings it shows. CHART_COLUMNS where it does not
 *   say.
 * @attr lamps - How many lamps a column has. CHART_LAMPS where it does not
 *   say.
 */
class NxChart extends HTMLElement {
  /** @type {(number | null)[]} The readings shown, oldest first, null where
   *  there was none. */
  history = [];

  /** @type {number} What the top of the field stands for, at the least. */
  floor = 100;

  /** @type {boolean} Whether the top rises to the highest reading in view,
   *  rounded up, where that is above `floor`. */
  grows = false;

  /** @type {number} From which value a lamp lights orange. */
  warm = Infinity;

  /** @type {number} From which value a lamp lights red. */
  hot = Infinity;

  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.field = document.createElement("div");
    this.field.className = "field";
    const columns = Number(this.getAttribute("columns")) || CHART_COLUMNS;
    const lamps = Number(this.getAttribute("lamps")) || CHART_LAMPS;
    for (let column = 0; column < columns; column += 1) {
      const standing = document.createElement("div");
      standing.className = "column";
      for (let lamp = 0; lamp < lamps; lamp += 1) {
        const led = document.createElement("i");
        led.className = "lamp";
        standing.append(led);
      }
      this.field.append(standing);
    }
    this.append(this.field);
    this.history = Array(columns).fill(null);
    this.draw();
  }

  /**
   * Adds a reading on the right and lets the oldest go on the left.
   * @param {number | null} value - The reading, or null where there was none,
   *   which lights nothing in its column.
   */
  push(value) {
    this.history.push(Number.isFinite(value) ? value : null);
    this.history.shift();
    this.draw();
  }

  /** Empties every column, for a chart that starts again from now. */
  clear() {
    this.history = this.history.map(() => null);
    this.draw();
  }

  /** @returns {number} What the top of the field stands for now. */
  top() {
    if (!this.grows) return this.floor;
    const highest = Math.max(...this.history.filter((value) => value !== null), 0);
    return Math.max(this.floor, Math.ceil(highest));
  }

  /** Lights each column as high as its reading is of the top, and gives every
   *  lamp the color of the value it stands for. */
  draw() {
    if (!this.field) return;
    const top = this.top();
    const columns = [...this.field.children];
    for (const [index, column] of columns.entries()) {
      const value = this.history[index];
      const lamps = [...column.children];
      const lit = value === null || top <= 0
        ? 0 : Math.round(Math.min(Math.max(value / top, 0), 1) * lamps.length);
      for (const [place, lamp] of lamps.entries()) {
        lamp.toggleAttribute("lit", place < lit);
        const stands = (place + 1) / lamps.length * top;
        const zone = stands > this.hot ? "hot" : stands > this.warm ? "warm" : null;
        if (zone) lamp.setAttribute("zone", zone);
        else lamp.removeAttribute("zone");
      }
    }
  }
}
