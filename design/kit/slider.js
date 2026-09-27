/* --- nx-slider ----------------------------------------------------------- */

/**
 * A knob in a trough, moving between the steps it is given.
 *
 * It holds no scale of its own: whatever uses it hands over the steps and what
 * each is called, and hears back which one was landed on. So a slider here says
 * nothing about megahertz or megabytes, and the words stay with whoever owns
 * them.
 *
 * @attr dragging - Set whilst the knob follows the pointer, which is what takes
 *   the travel off it so it does not trail behind the hand.
 * @attr fixed - Set where there is only one step, so the control reads as a
 *   statement rather than as a choice.
 * @fires nx-slide - `{ value }` of the step landed on, whenever that changes.
 */
class NxSlider extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.trough = document.createElement("div");
    this.trough.className = "trough";
    this.knob = document.createElement("div");
    this.knob.className = "knob";
    this.trough.append(this.knob);

    this.reading = document.createElement("nx-field");
    this.reading.className = "reading";

    this.append(this.trough, this.reading);
    this.steps = [];

    this.tabIndex = 0;
    this.setAttribute("role", "slider");
    this.wire();
  }

  /**
   * The steps this slider offers.
   * @param {Array<object>} steps - `{value, label}` for each, in the order they
   *   sit on the scale.
   *
   * Set every time the answer changes, because which steps exist depends on the
   * machine: a clock gains one with a turbo board, and memory loses two without
   * it.
   */
  set options(steps) {
    this.steps = steps;
    this.toggleAttribute("fixed", steps.length < 2);
    this.setAttribute("aria-valuemin", "0");
    this.setAttribute("aria-valuemax", String(Math.max(steps.length - 1, 0)));
    this.draw();
  }

  /** @returns {*} The value of the step the knob is on. */
  get value() {
    return this.steps[this.at]?.value;
  }

  /** @param {*} value - Which step to stand on. One that is not a step leaves
   *  the knob at the start, which is what a machine that has just changed
   *  answers with. */
  set value(value) {
    const at = this.steps.findIndex((step) => step.value === value);
    this.at = at < 0 ? 0 : at;
    this.draw();
  }

  /** Puts the knob where its step is and says what that step is called. */
  draw() {
    const at = this.at ?? 0;
    const last = Math.max(this.steps.length - 1, 1);
    /* In per cent of the room the knob has to travel, which is the trough less
       the knob itself. Stated that way rather than in pixels, so it is right
       before the trough has been laid out and stays right when it changes
       width. */
    this.knob.style.transform =
      `translateX(calc((100cqw - var(--knob-width)) * ${at / last}))`;
    this.reading.textContent = this.steps[at]?.label ?? "";
    this.setAttribute("aria-valuenow", String(at));
    this.setAttribute("aria-valuetext", this.steps[at]?.label ?? "");
  }

  /** Listens for the pointer on the trough and for the arrow keys. */
  wire() {
    this.trough.addEventListener("pointerdown", (event) => {
      if (this.hasAttribute("fixed")) return;
      this.setAttribute("dragging", "");
      this.trough.setPointerCapture(event.pointerId);
      this.reachFor(event);
    });

    this.trough.addEventListener("pointermove", (event) => {
      if (this.hasAttribute("dragging")) this.reachFor(event);
    });

    for (const ending of ["pointerup", "pointercancel"]) {
      this.trough.addEventListener(ending, () => this.removeAttribute("dragging"));
    }

    this.addEventListener("keydown", (event) => {
      const by = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[event.key];
      if (by === undefined || this.hasAttribute("fixed")) return;
      event.preventDefault();
      this.land((this.at ?? 0) + by);
    });
  }

  /**
   * Lands on the step nearest where the pointer is.
   * @param {PointerEvent} event
   */
  reachFor(event) {
    const trough = this.trough.getBoundingClientRect();
    const knob = this.knob.getBoundingClientRect();
    /* Measured from the middle of the knob, so the step under the pointer is
       the one it looks like rather than the one half a knob to its left. */
    const along = event.clientX - trough.left - knob.width / 2;
    const room = trough.width - knob.width;
    const last = Math.max(this.steps.length - 1, 1);
    this.land(Math.round((along / (room || 1)) * last));
  }

  /**
   * Stands on one step, where that is a step at all.
   * @param {number} at - Which of them, from 0.
   */
  land(at) {
    const wanted = Math.min(Math.max(at, 0), this.steps.length - 1);
    if (wanted === this.at) return;
    this.at = wanted;
    this.draw();
    this.dispatchEvent(new CustomEvent("nx-slide", {
      bubbles: true, detail: { value: this.value },
    }));
  }
}
