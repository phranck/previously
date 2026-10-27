/* --- nx-leds ------------------------------------------------------------- */

/** How many lamps a row has where it does not say. Twenty is one lamp for
 *  every five per cent, which is as fine as an eye reads a row of lamps at a
 *  glance and still fits beside a label in a panel. */
const LEDS_IN_A_ROW = 20;

/** Where along a row the lamps stop being green, as shares of the row: from
 *  here they light orange, and from LEDS_HOT_FROM red, the way a level meter
 *  warns as it nears its end. A row of twenty lights fourteen green, four
 *  orange and two red. */
const LEDS_WARM_FROM = 0.7;
const LEDS_HOT_FROM = 0.9;

/** How quickly the lamps follow a new share: the time they take to cover all
 *  but a third of the way, after which they slow as they arrive. A row fed a
 *  share twice a second has gone almost all of the way before the next one
 *  comes. */
const LEDS_FOLLOW_MS = 120;

/** How close to the share given the row counts as there, in per cent. Well
 *  under a lamp, so the row stops moving only once it lights what the share
 *  lights. */
const LEDS_ARRIVED = 0.5;

/**
 * How far along the green part of a row or a column a lamp stands, as the
 * stylesheet's `--along` reads it, which grades its green from darker to
 * paler.
 * @param {number} share - From 0 at the start of the green part to 1 at its
 *   end. Anything beyond is held to that.
 * @returns {string} The share to three places, as a custom property takes it.
 */
function alongTheGreen(share) {
  return String(Number(Math.min(Math.max(share, 0), 1).toFixed(3)));
}

/**
 * A row of lamps lighting from the left, for a share of something.
 *
 * It holds no scale beyond the share itself: whoever uses it hands over a
 * percentage and the words for it, and the words stay with whoever owns them.
 *
 * A new share is not jumped to. The row lights or puts out the lamps between
 * one after another and slows as it arrives, the way a meter's needle swings,
 * so a load that changes reads as a load changing rather than as a twitch.
 * Each lamp is still on or off, because a lamp has no state between the two.
 * What the row says in words, and to assistive technology, is the share given
 * at once. Where the reader has asked for less movement the lamps show it at
 * once as well.
 *
 * @attr lamps - How many lamps the row has. LEDS_IN_A_ROW where it does not
 *   say.
 */
class NxLeds extends HTMLElement {
  /** @type {number | null} The share last given, in per cent, or null where
   *  there is no reading. */
  share = null;

  /** @type {number} The share the lamps show now, which follows `share`. */
  shown = 0;

  /** @type {number} The animation frame asked for, or 0 while the lamps are
   *  still. */
  frame = 0;

  /** @type {number | undefined} When the lamps were last moved, by the clock
   *  the animation frames are given. */
  moved = undefined;

  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.row = document.createElement("div");
    this.row.className = "lamps";
    const count = Number(this.getAttribute("lamps")) || LEDS_IN_A_ROW;
    const green = Math.ceil(count * LEDS_WARM_FROM);
    for (let lamp = 0; lamp < count; lamp += 1) {
      const led = document.createElement("i");
      led.className = "led";
      /* Each lamp keeps the color of its place in the row, so a row filling
         up goes green, then orange, then red, and the color says how near
         the end the share is before the figure is read. The green ones grow
         paler towards the orange. */
      const along = lamp / count;
      if (along >= LEDS_HOT_FROM) led.setAttribute("zone", "hot");
      else if (along >= LEDS_WARM_FROM) led.setAttribute("zone", "warm");
      else led.style.setProperty("--along", alongTheGreen(lamp / Math.max(green - 1, 1)));
      this.row.append(led);
    }

    /* Beside the row rather than over it, the way the unit stands beside a
       slider, so the lamps are never covered by what they mean. */
    this.figure = document.createElement("span");
    this.figure.className = "says";
    this.figure.textContent = this.words ?? "";
    if (this.longest) this.figure.dataset.widest = this.longest;

    this.append(this.row, this.figure);
    this.setAttribute("role", "meter");
    this.setAttribute("aria-valuemin", "0");
    this.setAttribute("aria-valuemax", "100");
    /* A row that arrives with a share already given shows it, rather than
       swinging up to it from nothing. */
    this.shown = this.held() ?? 0;
    this.draw();
  }

  /** @returns {number|null} The share last given, in per cent. */
  get value() {
    return this.share;
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
    const held = this.held();
    if (held === null) this.removeAttribute("aria-valuenow");
    else this.setAttribute("aria-valuenow", String(held));
    this.follow();
  }

  /** @returns {number|null} The share given, held between 0 and 100, or null
   *  where there is no reading. */
  held() {
    return this.share === null ? null : Math.min(Math.max(this.share, 0), 100);
  }

  /** @param {string} words - What the share is, in the words of whoever
   *  measures it, such as `12%`. Written beside the row. */
  set says(words) {
    this.words = words;
    if (this.figure) this.figure.textContent = words;
    this.setAttribute("aria-valuetext", words);
  }

  /** @param {string} words - The longest the row will say, such as `100%`.
   *  The figure takes that much room and stands against its right edge, so a
   *  figure that gains or loses a digit leaves the ones after it where they
   *  are. Left unsaid, the figure is as wide as what it says. */
  set widest(words) {
    this.longest = words;
    if (this.figure) this.figure.dataset.widest = words;
  }

  /** Lets the lamps follow the share given, a frame at a time, or shows it at
   *  once where the reader has asked for less movement. */
  follow() {
    if (!this.row) return;
    if (stillness()) {
      this.shown = this.held() ?? 0;
      this.draw();
      return;
    }
    if (this.frame) return;
    this.moved = undefined;
    this.frame = requestAnimationFrame((now) => this.step(now));
  }

  /**
   * Moves the lamps one frame's worth of the way to the share given.
   * @param {number} now - The frame's time, in milliseconds.
   *
   * By the time that has passed rather than by the frame, so the row takes
   * the same time on a screen that draws sixty frames a second as on one that
   * draws a hundred and twenty. A share that changes while the row is moving
   * is simply where it goes from then on.
   */
  step(now) {
    const goal = this.held() ?? 0;
    const passed = this.moved === undefined ? 0 : now - this.moved;
    this.moved = now;
    this.shown += (goal - this.shown) * (1 - Math.exp(-passed / LEDS_FOLLOW_MS));
    if (Math.abs(goal - this.shown) < LEDS_ARRIVED) this.shown = goal;
    this.draw();
    this.frame = this.shown === goal ? 0 : requestAnimationFrame((later) => this.step(later));
  }

  /** Lights as many lamps from the left as the share shown is of the row.
   *
   *  Rounded to the nearest lamp, so a row of twenty lights its first lamp at
   *  two and a half per cent and its last at ninety-seven and a half. */
  draw() {
    if (!this.row) return;
    const lamps = [...this.row.children];
    const lit = Math.round(this.shown / 100 * lamps.length);
    for (const [index, lamp] of lamps.entries()) {
      lamp.toggleAttribute("lit", index < lit);
    }
  }
}
