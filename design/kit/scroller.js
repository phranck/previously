/* --- nx-scroller -------------------------------------------------------- */

/** What differs between the two directions, so that everything else does not
 *  have to know there are two. Each value names a property of an element, a
 *  style or a point, so the checker holds every lookup below to one that
 *  exists. */
const WAYS = /** @type {const} */ ({
  down: {
    steps: ["up", "down"],
    length: "scrollHeight", showing: "clientHeight", along: "scrollTop",
    edge: "top", size: "height", pointer: "y", offset: "offsetTop",
    room: "clientHeight", trailing: "paddingBottom",
  },
  across: {
    steps: ["left", "right"],
    length: "scrollWidth", showing: "clientWidth", along: "scrollLeft",
    edge: "left", size: "width", pointer: "x", offset: "offsetLeft",
    room: "clientWidth", trailing: "paddingRight",
  },
});

/** One of the two directions. @typedef {keyof typeof WAYS} Way */

/** What one direction differs in. @typedef {typeof WAYS[Way]} WayParts */

/**
 * One scroller, as addBar builds it.
 * @typedef {object} Bar
 * @property {HTMLDivElement} trough - The checkered track.
 * @property {HTMLDivElement} knob - What a person drags.
 * @property {HTMLDivElement} arrows - Both arrows, at the far end.
 * @property {WayParts} how - Which direction it scrolls in.
 */

/**
 * A view with NeXT's scroller on its left: a checkered trough, a knob that
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
  /** @type {HTMLElement | undefined} What the bars move, once there is one. */
  view;

  /** @type {(() => void) | undefined} What the view's scrolling calls, made
   *  once so that it can be taken off again. */
  onScroll;

  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    /* Taken before the bars exist. Each of them is prepended, so afterwards
       the first child is a bar and not the view. */
    const view = this.firstElementChild;

    const wanted = (this.getAttribute("bars") || "down").split(/\s+/);
    /** @type {Partial<Record<Way, Bar>>} */
    this.bars = {};
    for (const way of /** @type {Way[]} */ (["down", "across"])) {
      if (wanted.includes(way)) this.bars[way] = this.addBar(way);
    }

    this.drive(view);
  }

  /**
   * Points the bars at whatever actually scrolls.
   * @param {Element | null} view - The element whose scrollTop the knob
   *   moves. Nothing happens where there is none.
   *
   * The child of this element, ordinarily. Some views scroll something of
   * their own further in, because a library built the markup: a terminal
   * draws its lines into a viewport it owns, and that viewport is what
   * scrolls. Such a view says so by calling this once it exists, and the bars
   * follow it from then on.
   */
  drive(view) {
    if (!(view instanceof HTMLElement) || view === this.view) return;

    this.watch?.forEach((observer) => observer.disconnect());
    this.onScroll ??= () => this.refresh();
    this.view?.removeEventListener("scroll", this.onScroll);

    this.view = view;
    view.addEventListener("scroll", this.onScroll);

    /* What there is to scroll is the content's size against the view's, so
       both sizes are watched: the view's own, and that of every child it
       holds. A child changes size for more reasons than being replaced: a
       part inside it shown or hidden, as Preferences does when it changes
       module, a word set on it that a rule matches, a face arriving. None of
       those is a change to the list of children, and a knob drawn for the
       module before stays standing over the one after.

       The list of children is watched as well, because a child that is
       replaced has to be watched in its place, and text that changes inside
       a box of a fixed size moves no edge. */
    const sized = new ResizeObserver(() => this.refresh());
    const watchTheContent = () => {
      sized.disconnect();
      sized.observe(view);
      for (const child of view.children) sized.observe(child);
    };
    watchTheContent();
    const changed = new MutationObserver((records) => {
      if (records.some((record) => record.target === view
                       && record.type === "childList")) watchTheContent();
      this.refresh();
    });
    changed.observe(view, { childList: true, subtree: true, characterData: true });
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
   * @param {Way} way - Which direction it scrolls in.
   * @returns {Bar} Its trough, its knob and its arrows.
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
        if (!this.view) return;
        const back = step === "up" || step === "left";
        this.view[how.along] += (back ? -1 : 1) * NxScroller.LINE;
      });
      arrows.append(one);
    }
    bar.append(trough, arrows);
    this.prepend(bar);

    gesture(knob,
      (point, start) => {
        const view = this.view;
        if (!view) return;
        const room = trough[how.room] - knob[how.size === "height" ? "offsetHeight" : "offsetWidth"];
        const at = Math.max(0, Math.min(point[how.pointer] - start.grab, room));
        view[how.along] = (at / room) * (view[how.length] - view[how.showing]);
      },
      (point) => ({ grab: point[how.pointer] - knob[how.offset] }));

    return { trough, knob, arrows, how };
  }

  /** Redraws both bars from the view's current state, where there is a view. */
  refresh() {
    const view = this.view;
    if (!view) return;
    for (const bar of Object.values(this.bars)) this.fit(bar, view);
  }

  /**
   * Draws one bar.
   * @param {Bar} bar - What addBar returned.
   * @param {HTMLElement} view - What it scrolls.
   *
   * A bar with nothing to scroll keeps its trough and loses its knob and its
   * arrows, which is what the original shows: the trough is part of the view
   * rather than a thing that appears when it is needed.
   */
  fit({ trough, knob, arrows, how }, view) {
    const more = this.holdsMore(how, view);
    knob.hidden = !more;
    arrows.hidden = !more;
    if (!more) return;

    const overflow = view[how.length] - view[how.showing];
    const room = trough[how.room];
    /* The least a knob is, which base.css states for every scroller, so the
       F12 menu's scroller reads the same figure. */
    const smallest = parseFloat(getComputedStyle(this).getPropertyValue("--smallest-knob")) || 0;
    const size = Math.max(smallest, room * view[how.showing] / view[how.length]);
    knob.style[how.size] = size + "px";
    knob.style[how.edge] = (view[how.along] / overflow) * (room - size) + "px";
  }

  /**
   * Whether the view hides anything a reader could scroll to.
   * @param {WayParts} how - One of WAYS.
   * @param {HTMLElement} view - What scrolls.
   * @returns {boolean}
   *
   * The two figures cannot be compared as they come. Both are whole pixels
   * rounded from sizes that are fractions wherever the desk is drawn at 125,
   * 150 or 175 per cent, and WebKit then reports the content one pixel longer
   * than a view it fits in: a File Viewer path that fills its band exactly,
   * and a folder far shorter than its band. And the padding at the far end is
   * room rather than content, so a band the window leaves a few pixels short
   * of it still shows everything in it. So what counts is how far the content
   * runs past that padding, and only by more than one rounding.
   */
  holdsMore(how, view) {
    const trailing = parseFloat(getComputedStyle(view)[how.trailing]) || 0;
    const past = view[how.length] - view[how.showing] - trailing;
    return past > NxScroller.ROUNDING;
  }
}
NxScroller.LINE = 18;            /* how far one press of an arrow moves the view */
NxScroller.ROUNDING = 1;         /* what two sizes rounded to whole pixels can differ by */
