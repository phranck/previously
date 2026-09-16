/* --- nx-scroller -------------------------------------------------------- */

/** What differs between the two directions, so that everything else does not
 *  have to know there are two. */
const WAYS = {
  down: {
    steps: ["up", "down"],
    length: "scrollHeight", showing: "clientHeight", along: "scrollTop",
    edge: "top", size: "height", pointer: "y", offset: "offsetTop",
    room: "clientHeight",
  },
  across: {
    steps: ["left", "right"],
    length: "scrollWidth", showing: "clientWidth", along: "scrollLeft",
    edge: "left", size: "width", pointer: "x", offset: "offsetLeft",
    room: "clientWidth",
  },
};

/**
 * A view with NeXT's scroller on its left: a chequered trough, a knob that
 * takes its size from how much of the content is showing, and both arrows at
 * the far end. With nothing to scroll the whole bar goes empty, which is how
 * an idle terminal looks.
 *
 * @attr bars - Which scrollers this view has: "down", "across", or both.
 *   A view says so because the original's do: the File Viewer's contents have
 *   both, and the band above them, which is a path and only ever grows
 *   sideways, has the one along its foot and nothing down its side. Left out,
 *   it is the vertical one alone, which is what a list wants.
 *
 * A scroller is there whether or not there is anything to scroll. It is part
 * of the view rather than something that appears when it is needed, and an
 * empty trough is what the original shows.
 */
class NxScroller extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    /* Taken before the bars exist. Each of them is prepended, so afterwards
       the first child is a bar and not the view. */
    const view = this.firstElementChild;

    const wanted = (this.getAttribute("bars") || "down").split(/\s+/);
    this.bars = {};
    for (const way of ["down", "across"]) {
      if (wanted.includes(way)) this.bars[way] = this.addBar(way);
    }

    this.drive(view);
  }

  /**
   * Points the bars at whatever actually scrolls.
   * @param {HTMLElement} view - The element whose scrollTop the knob moves.
   *
   * The child of this element, ordinarily. Some views scroll something of
   * their own further in, because a library built the markup: a terminal
   * draws its lines into a viewport it owns, and that viewport is what
   * scrolls. Such a view says so by calling this once it exists, and the bars
   * follow it from then on.
   */
  drive(view) {
    if (!view || view === this.view) return;

    this.watch?.forEach((observer) => observer.disconnect());
    this.view?.removeEventListener("scroll", this.onScroll);

    this.view = view;
    this.onScroll ??= () => this.refresh();
    this.view.addEventListener("scroll", this.onScroll);

    /* Two things change what there is to scroll, and they are seen by two
       different observers: the view being resized, and its content being
       replaced. Content that grows inside an unchanged box moves no edge, so
       the resize observer alone would miss a shelf being redrawn. */
    const sized = new ResizeObserver(() => this.refresh());
    sized.observe(this.view);
    const changed = new MutationObserver(() => this.refresh());
    changed.observe(this.view, { childList: true, subtree: true, characterData: true });
    this.watch = [sized, changed];

    /* Says in the markup that the child is not what scrolls, so the stylesheet
       can leave the child's own overflow alone. Asked of the view's own
       parent rather than of this element's first child, which by now is a
       bar. */
    this.toggleAttribute("inner", view.parentElement !== this);
    this.refresh();
  }

  /**
   * Builds one scroller.
   * @param {string} way - "down" or "across".
   * @returns {object} Its trough, its knob and its arrows.
   */
  addBar(way) {
    const how = WAYS[way];
    const bar = document.createElement("div");
    bar.className = way === "across" ? "bar across" : "bar";
    const trough = document.createElement("div");
    trough.className = "trough";
    const knob = document.createElement("div");
    knob.className = "knob";
    trough.append(knob);

    const arrows = document.createElement("div");
    arrows.className = "arrows";
    for (const step of how.steps) {
      const one = document.createElement("div");
      one.className = "step " + step;
      one.append(document.createElement("i"));
      one.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        const back = step === "up" || step === "left";
        this.view[how.along] += (back ? -1 : 1) * NxScroller.LINE;
      });
      arrows.append(one);
    }
    bar.append(trough, arrows);
    this.prepend(bar);

    gesture(knob,
      (point, start) => {
        const room = trough[how.room] - knob[how.size === "height" ? "offsetHeight" : "offsetWidth"];
        const at = Math.max(0, Math.min(point[how.pointer] - start.grab, room));
        this.view[how.along] =
          (at / room) * (this.view[how.length] - this.view[how.showing]);
      },
      (point) => ({ grab: point[how.pointer] - knob[how.offset] }));

    return { trough, knob, arrows, how };
  }

  /** Redraws both bars from the view's current state. */
  refresh() {
    for (const bar of Object.values(this.bars)) this.fit(bar);
  }

  /**
   * Draws one bar.
   * @param {object} bar - What addBar returned.
   *
   * A bar with nothing to scroll keeps its trough and loses its knob and its
   * arrows, which is what the original shows: the trough is part of the view
   * rather than a thing that appears when it is needed.
   */
  fit({ trough, knob, arrows, how }) {
    const overflow = this.view[how.length] - this.view[how.showing];
    knob.hidden = overflow <= 0;
    arrows.hidden = overflow <= 0;
    if (overflow <= 0) return;

    const room = trough[how.room];
    const size = Math.max(NxScroller.SMALLEST_KNOB,
                          room * this.view[how.showing] / this.view[how.length]);
    knob.style[how.size] = size + "px";
    knob.style[how.edge] = (this.view[how.along] / overflow) * (room - size) + "px";
  }
}
NxScroller.LINE = 18;            /* how far one press of an arrow moves the view */
NxScroller.SMALLEST_KNOB = 16;   /* below this the knob is no longer a target */
