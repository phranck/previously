/* --- nx-slider ----------------------------------------------------------- */

/**
 * A knob in a trough, moving between the steps it is given.
 *
 * It holds no scale of its own: whatever uses it hands over the steps and what
 * each is called, and hears back which one was landed on. So a slider here says
 * nothing about megahertz or megabytes, and the words stay with whoever owns
 * them.
 *
 * @attr dragging - Set while the knob follows the pointer, which is what takes
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

    /* The ticks stand over the trough, each above the place its step puts the
       knob, so the scale is read before the hand reaches it rather than from
       under the hand that is on it. */
    this.ticks = document.createElement("div");
    this.ticks.className = "ticks";

    const scale = document.createElement("div");
    scale.className = "scale";
    scale.append(this.ticks, this.trough);

    /* The unit, once, to the left of the scale. The ticks carry figures alone
       and the one in force is the black one, so the unit is the only thing left
       to say and saying it beside every tick would crowd them out. */
    this.unit = document.createElement("span");
    this.unit.className = "unit";

    this.append(this.unit, scale);
    this.steps = [];

    this.tabIndex = 0;
    this.setAttribute("role", "slider");
    this.wire();
  }

  /**
   * The steps this slider offers.
   * @param {Array<object>} steps - `{value, label, tick}` for each, in the order
   *   they sit on the scale. `tick` is what stands under that step, which is the
   *   figure alone: the field beside the slider carries the unit, and five of
   *   those along one trough would not fit.
   *
   * Set every time the answer changes, because which steps exist depends on the
   * machine: a clock gains one with a turbo board, and memory loses two without
   * it.
   */
  /** @param {string} unit - What the figures on this scale are counted in,
   *  such as MHz or MB. Stated once, to the left of the scale. */
  set says(unit) {
    this.unit.textContent = unit;
  }

  set options(steps) {
    this.steps = steps;
    this.toggleAttribute("fixed", steps.length < 2);
    this.setAttribute("aria-valuemin", "0");
    this.setAttribute("aria-valuemax", String(Math.max(steps.length - 1, 0)));
    this.drawTheTicks();
    this.draw();
  }

  /** Puts one tick under each step, where that step puts the knob.
   *
   *  A scale of one step draws none, because there is nothing to choose
   *  between and a lone tick would read as a mark somebody could aim at. */
  drawTheTicks() {
    const last = Math.max(this.steps.length - 1, 1);
    this.ticks.replaceChildren(...(this.steps.length < 2 ? [] :
      this.steps.map((step, at) => {
        const tick = document.createElement("span");
        tick.className = "tick";
        tick.textContent = step.tick ?? "";
        /* Under the middle of the knob when it stands on this step, which is
           half a knob in plus that step's share of the room it travels. */
        tick.style.left =
          `calc(var(--knob-width) / 2 + (100% - var(--knob-width)) * ${at / last})`;
        return tick;
      })));
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
    this.setAttribute("aria-valuenow", String(at));
    this.setAttribute("aria-valuetext", this.steps[at]?.label ?? "");

    /* Which tick is in force, so the scale says where the knob stands as well
       as the knob does. */
    for (const [index, tick] of [...this.ticks.children].entries()) {
      tick.toggleAttribute("chosen", index === at);
    }
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
