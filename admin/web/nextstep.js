/* The NeXTSTEP kit: a handful of custom elements that plug into one another.
 *
 * Everything on the desk is built from them, and each one owns one job:
 *
 *   nx-menu, nx-menu-item   the menu, and the entries that open windows
 *   nx-dock, nx-tile        the strip of tiles down the right edge
 *   nx-window               a frame that drags, resizes, closes and remembers
 *   nx-scroller             a view with NeXT's scroller on its left
 *   nx-shelf, nx-thing      a floor of icons, one of which may be chosen
 *   nx-portrait, nx-row     the pieces an info panel is laid out from
 *
 * They use the light DOM rather than a shadow root, so the stylesheet above
 * reaches them and the design tokens carry through.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const STORE = "nextstep-workspace:v4";

/* --- what the desk remembers -------------------------------------------- */

/** @returns {object} Everything saved about the desk, or an empty record. */
function readState() {
  try { return JSON.parse(localStorage.getItem(STORE)) ?? {}; }
  catch { return {}; }
}

/**
 * Writes one element's state, leaving every other one untouched.
 * @param {string} name - What the element calls itself.
 * @param {object} state - The keys to merge in.
 */
function remember(name, state) {
  const all = readState();
  all[name] = { ...(all[name] ?? {}), ...state };
  localStorage.setItem(STORE, JSON.stringify(all));
}

/** @param {string} name @returns {object} That element's saved state. */
function recall(name) {
  return readState()[name] ?? {};
}

/**
 * Points an element at one of the pictures build.py baked into the stylesheet.
 * @param {HTMLElement} el
 * @param {string} name - The picture's name, which is its file's stem.
 */
function showArt(el, name) {
  el.style.backgroundImage = "var(--" + name + ")";
}

/**
 * Runs a pointer gesture and reports the result when it ends.
 * @param {HTMLElement} handle - Where the gesture starts.
 * @param {(event: PointerEvent, start: object) => void} onMove
 * @param {(event: PointerEvent) => object} onStart - Whatever the mover needs
 *   to know about the moment the gesture began.
 * @param {(start: object) => void} [onEnd] - Given what onStart returned,
 *   which by then carries whatever the moves wrote into it.
 */
function gesture(handle, onMove, onStart, onEnd) {
  handle.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
    /* Without this the browser starts its own text selection under the
       pointer, and dragging a window paints half the desk blue. */
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    const start = onStart(event);

    /* A pointer reports faster than the screen redraws, so the moves are
       coalesced into one update per frame. Everything beyond the last one in
       a frame is work whose result is painted over before anybody sees it. */
    let latest = null;
    let frame = 0;

    const apply = () => {
      frame = 0;
      onMove(latest, start);
    };

    const move = (moveEvent) => {
      latest = moveEvent;
      if (!frame) frame = requestAnimationFrame(apply);
    };

    const finish = () => {
      handle.removeEventListener("pointermove", move);
      /* The last position has to land before anything saves it, so a frame
         still owed is run now rather than cancelled. */
      if (frame) {
        cancelAnimationFrame(frame);
        apply();
      }
      onEnd?.(start);
    };

    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", finish, { once: true });
    handle.addEventListener("pointercancel", finish, { once: true });
  });
}

/**
 * Moves an element by its handle, and settles it where it was let go.
 *
 * Whilst the gesture runs the element is moved with a transform, which the
 * compositor can do without laying the page out again. Its left and top are
 * written once, at the end, so everything that reads them afterwards sees a
 * plain position and knows nothing about how it got there.
 *
 * @param {HTMLElement} element - What moves.
 * @param {HTMLElement} handle - What is grabbed.
 * @param {object} hooks
 * @param {() => void} [hooks.onGrab] - Called as the gesture begins.
 * @param {() => void} [hooks.onSettled] - Called once the position is written.
 */
function draggable(element, handle, { onGrab, onSettled } = {}) {
  gesture(handle,
    (event, start) => {
      /* Never past the top or left edge, and never wholly behind the dock. */
      start.left = Math.max(0, Math.min(event.clientX - start.grabX, innerWidth - 90));
      start.top = Math.max(0, Math.min(event.clientY - start.grabY, innerHeight - 24));
      element.style.transform =
        `translate(${start.left - start.fromLeft}px, ${start.top - start.fromTop}px)`;
    },
    (event) => {
      onGrab?.();
      const fromLeft = element.offsetLeft;
      const fromTop = element.offsetTop;
      return {
        grabX: event.clientX - fromLeft, grabY: event.clientY - fromTop,
        fromLeft, fromTop, left: fromLeft, top: fromTop,
      };
    },
    (start) => {
      element.style.transform = "";
      element.style.left = start.left + "px";
      element.style.top = start.top + "px";
      onSettled?.();
    });
}

/* --- nx-window ---------------------------------------------------------- */

/**
 * A window: title bar, close button, optional resize bar, and a memory.
 *
 * It writes its position, its size and whether it is open under its name, so
 * the desk comes back the way it was left. A window marked `fixed` has no
 * resize bar, one marked `flush` lets its content run to the frame, and one
 * marked `drop` accepts things dragged onto it.
 *
 * @attr name   - What it is called in storage and to the menu. Required.
 * @attr title  - The text in the bar.
 * @attr x y w h - Where it starts, before anything was remembered.
 * @attr min-w min-h - The floor its content needs.
 */
class NxWindow extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    const content = [...this.childNodes];
    this.replaceChildren();

    this.bar = this.build("div", "titlebar");
    this.bar.append(this.build("i", "art wbtn mini"));
    const title = this.build("div", "title");
    title.textContent = this.getAttribute("title") ?? "";
    this.removeAttribute("title");         /* or the browser shows a tooltip */
    const close = this.build("i", "art wbtn close");
    this.bar.append(title, close);

    this.pane = this.build("div", "pane");
    this.pane.append(...content);
    this.append(this.bar, this.pane);

    if (!this.hasAttribute("fixed")) this.addResizer();
    if (this.hasAttribute("drop")) this.acceptDrops();
    this.place();
    this.wire(close);
  }

  /** @returns {HTMLElement} A child element, appended nowhere yet. */
  build(tag, className) {
    const el = document.createElement(tag);
    el.className = className;
    return el;
  }

  /** Puts the window where it was left, or where its attributes say. */
  place() {
    const saved = recall(this.name);
    const number = (key, attribute) => saved[key] ?? Number(this.getAttribute(attribute));
    this.style.left = Math.min(number("x", "x"), Math.max(0, innerWidth - 90)) + "px";
    this.style.top = Math.min(number("y", "y"), Math.max(0, innerHeight - 40)) + "px";
    this.style.width = number("w", "w") + "px";
    this.style.height = number("h", "h") + "px";
    for (const [attribute, property] of [["min-w", "--win-min-w"], ["min-h", "--win-min-h"]]) {
      if (this.hasAttribute(attribute)) {
        this.style.setProperty(property, this.getAttribute(attribute) + "px");
      }
    }
    /* A window is open unless it says otherwise, and what was remembered
       beats what the markup starts it at. */
    this.hidden = !(saved.open ?? !this.hasAttribute("closed"));
  }

  /** @returns {string} The name it is known by. */
  get name() { return this.getAttribute("name"); }

  /** The floor this window's content needs, read off the element itself. */
  get floor() {
    const style = getComputedStyle(this);
    return {
      width: parseInt(style.getPropertyValue("--win-min-w"), 10),
      height: parseInt(style.getPropertyValue("--win-min-h"), 10),
    };
  }

  /**
   * Saves whether it is open, and where and how big it is.
   *
   * A hidden element measures zero on every side, so a closed window keeps the
   * geometry it had rather than writing that over with nothing. Otherwise it
   * would come back in the corner at no size at all.
   */
  save() {
    const state = { open: !this.hidden };
    if (!this.hidden) {
      Object.assign(state, {
        x: this.offsetLeft, y: this.offsetTop,
        w: this.offsetWidth, h: this.offsetHeight,
      });
    }
    remember(this.name, state);
  }

  /**
   * Brings it forward and pushes every other window back. Which window is in
   * front is part of what the desk remembers, because exactly one is active at
   * a time and a reload that made them all active would be a desk nobody has
   * ever seen.
   */
  raise() {
    if (!this.hasAttribute("inactive") && this.style.zIndex) return;
    let highest = 10;
    for (const other of document.querySelectorAll("nx-window")) {
      highest = Math.max(highest, Number(other.style.zIndex) || 10);
      other.setAttribute("inactive", "");
    }
    this.style.zIndex = highest + 1;
    this.removeAttribute("inactive");
    remember("desk", { front: this.name });
  }

  /** Shows it, in front. */
  open() {
    this.hidden = false;
    this.raise();
    this.save();
  }

  /** Hides it, keeping its geometry for the next time. */
  close() {
    this.hidden = true;
    this.save();
  }

  /**
   * Takes what is dropped on it, and says so whilst something is over it.
   *
   * Raises the same `nx-choose` a double click does, because carrying a thing
   * here and double clicking it mean the same thing to whoever answers.
   */
  acceptDrops() {
    this.addEventListener("dragover", (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      this.setAttribute("droppable", "");
    });

    /* Moving onto a child fires dragleave on the parent, so only a pointer
       that has actually left the window counts. */
    this.addEventListener("dragleave", (event) => {
      if (!this.contains(event.relatedTarget)) this.removeAttribute("droppable");
    });

    this.addEventListener("drop", (event) => {
      event.preventDefault();
      this.removeAttribute("droppable");
      this.dispatchEvent(new CustomEvent("nx-choose", {
        bubbles: true,
        detail: { value: event.dataTransfer.getData("text/plain") },
      }));
    });
  }

  /** The bar along the foot: a middle that takes the height and two ends that
   *  take the corner with it. */
  addResizer() {
    const bar = this.build("div", "resizer");
    const left = this.build("div", "end");
    const right = this.build("div", "end");
    left.dataset.corner = "left";
    right.dataset.corner = "right";
    bar.append(left, this.build("div", "middle"), right);
    this.append(bar);

    for (const handle of bar.children) {
      const corner = handle.dataset.corner;
      gesture(handle,
        (event, start) => {
          const floor = this.floor;
          this.style.height = Math.max(floor.height, start.height + event.clientY) + "px";
          if (corner === "right") {
            this.style.width = Math.max(floor.width, start.width + event.clientX) + "px";
          } else if (corner === "left") {
            /* Dragging the left end moves that edge and holds the right one
               still, so the two have to change together. */
            const left = Math.min(event.clientX - start.grabX, start.right - floor.width);
            this.style.left = left + "px";
            this.style.width = (start.right - left) + "px";
          }
        },
        (event) => {
          this.raise();
          return {
            width: this.offsetWidth - event.clientX,
            height: this.offsetHeight - event.clientY,
            grabX: event.clientX - this.offsetLeft,
            right: this.offsetLeft + this.offsetWidth,
          };
        },
        () => this.save());
    }
  }

  /** Dragging by the bar, closing by the button, raising by a click anywhere. */
  wire(close) {
    draggable(this, this.bar, {
      onGrab: () => this.raise(),
      onSettled: () => this.save(),
    });

    close.addEventListener("click", (event) => {
      event.stopPropagation();
      this.close();
    });
    /* The bar's own gesture would otherwise start a drag from the button, and
       the window would follow the pointer as it closed. */
    close.addEventListener("pointerdown", (event) => event.stopPropagation());

    this.addEventListener("pointerdown", () => this.raise());
  }
}

/* --- nx-menu ------------------------------------------------------------ */

/**
 * The menu: a title that drags the whole thing, and entries beneath it.
 * @attr name - What it is called in storage.
 * @attr title - The text in its black bar.
 * @attr x y - Where it starts.
 */
class NxMenu extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    const title = document.createElement("div");
    title.className = "title";
    title.textContent = this.getAttribute("title") ?? "";
    this.removeAttribute("title");
    this.prepend(title);

    const name = this.getAttribute("name");
    const saved = recall(name);
    this.style.left = (saved.x ?? Number(this.getAttribute("x"))) + "px";
    this.style.top = (saved.y ?? Number(this.getAttribute("y"))) + "px";

    draggable(this, title, {
      onSettled: () => remember(name, { x: this.offsetLeft, y: this.offsetTop }),
    });
  }
}

/**
 * One entry. With `opens` it shows that window, raising it when it is already
 * up, which is what the original did with an entry for a window on screen.
 * @attr opens - The name of an nx-window.
 * @attr key - The letter shown on the right.
 */
class NxMenuItem extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    if (this.hasAttribute("key")) {
      const key = document.createElement("span");
      key.className = "key";
      key.textContent = this.getAttribute("key");
      this.append(key);
    }
    const target = this.getAttribute("opens");
    if (target) {
      this.addEventListener("click", () => {
        document.querySelector(`nx-window[name="${target}"]`)?.open();
      });
    }
  }
}

/* --- nx-dock ------------------------------------------------------------ */

/**
 * One dock tile.
 * @attr icon - Which picture it carries.
 * @attr opens - The name of an nx-window, if clicking it should show one.
 * @attr idle - Draw the three marks that said the application was not started.
 * @attr spaced - Push it to the foot of the dock.
 */
class NxTile extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    const art = document.createElement("i");
    art.className = "art";
    showArt(art, this.getAttribute("icon"));
    this.append(art);

    const target = this.getAttribute("opens");
    if (target) {
      this.addEventListener("click", () => {
        document.querySelector(`nx-window[name="${target}"]`)?.open();
      });
    }
  }
}

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

/* --- nx-shelf and nx-thing ---------------------------------------------- */

/** A floor of icons, of which at most one is chosen at a time. */
class NxShelf extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;
    this.addEventListener("click", (event) => {
      const thing = event.target.closest("nx-thing");
      if (!thing || !this.contains(thing)) return;
      this.choose(thing);
    });
  }

  /** @param {HTMLElement} thing - The one to mark, clearing the others. */
  choose(thing) {
    for (const other of this.querySelectorAll("nx-thing")) other.removeAttribute("chosen");
    thing.setAttribute("chosen", "");
  }
}

/**
 * One thing on a shelf: a picture with a name under it.
 * @attr icon - Which picture it carries.
 * @attr label - The name under it.
 * @attr chosen - Draw it selected.
 */
class NxThing extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    const slot = document.createElement("span");
    slot.className = "slot art";
    const art = document.createElement("i");
    art.className = "art icon";
    showArt(art, this.getAttribute("icon"));
    slot.append(art);

    const name = document.createElement("span");
    name.className = "name";
    name.textContent = this.getAttribute("label") ?? "";

    this.append(slot, name);
    this.art = art;

    if (this.hasAttribute("value")) this.carry();
  }

  /** @returns {string} What this thing hands over when it is used. */
  get value() { return this.getAttribute("value"); }

  /**
   * Makes it liftable, and makes a double click mean the same as carrying it
   * somewhere and letting go.
   *
   * Both raise `nx-choose`, which bubbles, so a page answers in one place
   * however the thing was used.
   */
  carry() {
    this.draggable = true;

    this.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", this.value);
      event.dataTransfer.effectAllowed = "copy";
      this.setAttribute("lifting", "");
    });

    this.addEventListener("dragend", () => this.removeAttribute("lifting"));

    this.addEventListener("dblclick", () => {
      this.dispatchEvent(new CustomEvent("nx-choose", {
        bubbles: true, detail: { value: this.value },
      }));
    });
  }

  /** @param {string} icon - Swap the picture without rebuilding the thing. */
  set icon(icon) {
    this.setAttribute("icon", icon);
    if (this.art) showArt(this.art, icon);
  }
}

/* --- nx-ask ------------------------------------------------------------- */

/**
 * The panel that asks before anything changes.
 *
 * NeXTSTEP put an attention panel in the middle of the screen over a dimmed
 * desk, with the icon of whatever is about to happen, a sentence saying what
 * it is, and the safe answer on the left. This is that, and it is a component
 * rather than markup in the page because more than one thing needs to ask:
 * stopping the emulator does, and changing the machine will.
 *
 * It answers with a promise rather than a callback, so the caller reads as one
 * sequence: ask, then act on the answer.
 */
class NxAsk extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;
    this.className = "scrim";

    this.innerHTML = `
      <div class="panel">
        <div class="titlebar"><div class="title"></div></div>
        <div class="pane">
          <div class="panel-body">
            <i class="art icon"></i>
            <div class="words">
              <div class="lines"></div>
              <input class="entry" type="text" spellcheck="false" hidden>
            </div>
          </div>
          <div class="buttons" style="padding-right:0">
            <button data-answer="no"></button>
            <button data-answer="yes" class="default"></button>
          </div>
        </div>
      </div>`;

    this.settle = null;
    for (const button of this.querySelectorAll("button")) {
      button.addEventListener("click", () => this.close(button.dataset.answer === "yes"));
    }

    /* Escape is the safe answer, which is the one a panel like this must have:
       somebody who wants out of a question should not have to aim at a button. */
    this.keys = (event) => {
      if (event.key === "Escape") this.close(false);
      const entry = this.querySelector(".entry");
      if (event.key === "Enter" && !entry.hidden) this.close(true);
    };
  }

  /**
   * Puts the question and waits for an answer.
   * @param {object} question
   * @param {string} question.title - The panel's own title bar.
   * @param {string[]} question.text - One paragraph per entry.
   * @param {string} [question.icon] - Which picture, by the name showArt knows.
   * @param {string} [question.confirm] - The wording on the acting button.
   * @param {string} [question.cancel] - The wording on the safe one.
   * @param {boolean} [question.field] - Show a line to type into.
   * @returns {Promise<boolean>} True where the acting button was pressed.
   */
  ask({ title, text, icon, confirm = "Ja", cancel = "Abbrechen", field = false }) {
    this.querySelector(".title").textContent = title;
    this.querySelector(".lines").replaceChildren(
      ...text.map((line) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = line;
        return paragraph;
      }));
    if (icon) showArt(this.querySelector(".icon"), icon);
    this.querySelector('[data-answer="yes"]').textContent = confirm;
    this.querySelector('[data-answer="no"]').textContent = cancel;

    const entry = this.querySelector(".entry");
    entry.hidden = !field;
    entry.value = "";

    this.toggleAttribute("data-open", true);
    addEventListener("keydown", this.keys);
    (field ? entry : this.querySelector('[data-answer="no"]')).focus();

    return new Promise((settle) => { this.settle = settle; });
  }

  /**
   * Puts a question that needs something typed.
   * @param {object} question - As ask, and the field is shown.
   * @returns {Promise<string|null>} What was typed, or null where the panel was
   *   dismissed. Empty counts as dismissed, because a blank answer is not one.
   */
  async askFor(question) {
    const answered = await this.ask({ ...question, field: true });
    if (!answered) return null;
    const typed = this.querySelector(".entry").value.trim();
    return typed || null;
  }

  /**
   * Closes the panel and settles whoever was waiting.
   * @param {boolean} answer
   */
  close(answer) {
    this.toggleAttribute("data-open", false);
    removeEventListener("keydown", this.keys);
    this.settle?.(answer);
    this.settle = null;
  }
}

for (const [tag, type] of [
  ["nx-window", NxWindow], ["nx-menu", NxMenu], ["nx-menu-item", NxMenuItem],
  ["nx-tile", NxTile], ["nx-scroller", NxScroller],
  ["nx-shelf", NxShelf], ["nx-thing", NxThing], ["nx-ask", NxAsk],
]) {
  customElements.define(tag, type);
}
