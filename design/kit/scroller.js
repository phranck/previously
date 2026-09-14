/* --- nx-scroller -------------------------------------------------------- */

/**
 * A view with NeXT's scroller on its left: a chequered trough, a knob that
 * takes its size from how much of the content is showing, and both arrows at
 * the foot. With nothing to scroll the whole bar goes empty, which is how an
 * idle terminal looks.
 */
class NxScroller extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.view = this.firstElementChild;
    const bar = document.createElement("div");
    bar.className = "bar";
    this.trough = document.createElement("div");
    this.trough.className = "trough";
    this.knob = document.createElement("div");
    this.knob.className = "knob";
    this.trough.append(this.knob);
    this.arrows = document.createElement("div");
    this.arrows.className = "arrows";
    for (const direction of ["up", "down"]) {
      const step = document.createElement("div");
      step.className = "step " + direction;
      step.append(document.createElement("i"));
      step.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        this.view.scrollTop += (direction === "up" ? -1 : 1) * NxScroller.LINE;
      });
      this.arrows.append(step);
    }
    bar.append(this.trough, this.arrows);
    this.prepend(bar);

    this.view.addEventListener("scroll", () => this.refresh());
    /* Two things change what there is to scroll, and they are seen by two
       different observers: the view being resized, and its content being
       replaced. Content that grows inside an unchanged box moves no edge, so
       the resize observer alone would miss a shelf being redrawn. */
    new ResizeObserver(() => this.refresh()).observe(this.view);
    new MutationObserver(() => this.refresh())
      .observe(this.view, { childList: true, subtree: true, characterData: true });

    gesture(this.knob,
      (event, start) => {
        const room = this.trough.clientHeight - this.knob.offsetHeight;
        const top = Math.max(0, Math.min(event.clientY - start.grab, room));
        this.view.scrollTop = (top / room) * (this.view.scrollHeight - this.view.clientHeight);
      },
      (event) => ({ grab: event.clientY - this.knob.offsetTop }));

    this.refresh();
  }

  /** Redraws the bar from the view's current state. */
  refresh() {
    const overflow = this.view.scrollHeight - this.view.clientHeight;
    this.knob.hidden = overflow <= 0;
    this.arrows.hidden = overflow <= 0;
    if (overflow <= 0) return;

    const room = this.trough.clientHeight;
    const height = Math.max(NxScroller.SMALLEST_KNOB,
                            room * this.view.clientHeight / this.view.scrollHeight);
    this.knob.style.height = height + "px";
    this.knob.style.top = (this.view.scrollTop / overflow) * (room - height) + "px";
  }
}
NxScroller.LINE = 18;            /* how far one press of an arrow moves the view */
NxScroller.SMALLEST_KNOB = 16;   /* below this the knob is no longer a target */

