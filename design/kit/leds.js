/* --- nx-leds ------------------------------------------------------------- */

/** How many lamps a row has where it does not say. Twenty is one lamp for
 *  every five per cent, which is as fine as an eye reads a row of lamps at a
 *  glance and still fits beside a label in a panel. */
const LEDS_IN_A_ROW = 20;

/**
 * A row of lamps lighting from the left, for a share of something.
 *
 * It holds no scale beyond the share itself: whoever uses it hands over a
 * percentage and the words for it, and the words stay with whoever owns them.
 * It is drawn once for each value it is given and never animated, because
 * what it shows changes once a second at most and a lamp has no state
 * between on and off.
 *
 * @attr lamps - How many lamps the row has. LEDS_IN_A_ROW where it does not
 *   say.
 */
class NxLeds extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.row = document.createElement("div");
    this.row.className = "lamps";
    const count = Number(this.getAttribute("lamps")) || LEDS_IN_A_ROW;
    for (let lamp = 0; lamp < count; lamp += 1) {
      const led = document.createElement("i");
      led.className = "led";
      this.row.append(led);
    }

    /* Beside the row rather than over it, the way the unit stands beside a
       slider, so the lamps are never covered by what they mean. */
    this.figure = document.createElement("span");
    this.figure.className = "says";
    this.figure.textContent = this.words ?? "";

    this.append(this.row, this.figure);
    this.setAttribute("role", "meter");
    this.setAttribute("aria-valuemin", "0");
    this.setAttribute("aria-valuemax", "100");
    this.draw();
  }

  /** @returns {number|null} The share last given, in per cent. */
  get value() {
    return this.share ?? null;
  }

  /**
   * @param {number|null} percent - How full whatever it measures is, from 0
   *   to 100. Anything outside that lights all of the row or none of it, and
   *   null is a reading that is not there, which lights nothing.
   *
   * Kept even before the row is on the page, and drawn once it arrives, so
   * whoever builds one can fill it in before or after putting it somewhere.
   */
  set value(percent) {
    this.share = Number.isFinite(percent) ? percent : null;
    this.draw();
  }

  /** @param {string} words - What the share is, in the words of whoever
   *  measures it, such as `12 %`. Written beside the row. */
  set says(words) {
    this.words = words;
    if (this.figure) this.figure.textContent = words;
    this.setAttribute("aria-valuetext", words);
  }

  /** Lights as many lamps from the left as the share is of the row.
   *
   *  Rounded to the nearest lamp, so a row of twenty lights its first lamp at
   *  two and a half per cent and its last at ninety-seven and a half. */
  draw() {
    if (!this.row) return;
    const lamps = [...this.row.children];
    const share = this.value === null ? null : Math.min(Math.max(this.value, 0), 100);
    const lit = share === null ? 0 : Math.round(share / 100 * lamps.length);
    for (const [index, lamp] of lamps.entries()) {
      lamp.toggleAttribute("lit", index < lit);
    }

    if (share === null) this.removeAttribute("aria-valuenow");
    else this.setAttribute("aria-valuenow", String(share));
  }
}
