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
 *
 * @fires nx-front - It has come to the front, carrying its `name`. The main
 *   menu belongs to whatever is in front, so this is what it follows.
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

  /**
   * Puts a different name in the title bar.
   * @param {string} text - What the window is about now.
   *
   * For a window that says something about whatever was chosen, where the
   * name is the difference between two of them.
   */
  rename(text) {
    const title = this.bar?.querySelector(".title");
    if (title) title.textContent = text;
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
    /* A window nobody can resize has no size of its own to remember, so its
       markup decides. Otherwise a size saved before it was fixed, or before
       its contents changed, would outlive both. */
    const fixed = this.hasAttribute("fixed");
    const size = fixed
      ? (_key, attribute) => Number(this.getAttribute(attribute))
      : number;

    const room = deskRoom();
    this.style.left = Math.min(number("x", "x"), Math.max(0, room.width - 90)) + "px";
    this.style.top = Math.min(number("y", "y"), Math.max(0, room.height - 40)) + "px";

    /* Before the size, because the floor is read off these and a size saved
       when the window held something else has to be held to what it holds
       now. */
    for (const [attribute, property] of [["min-w", "--win-min-w"], ["min-h", "--win-min-h"]]) {
      if (this.hasAttribute(attribute)) {
        this.style.setProperty(property, this.getAttribute(attribute) + "px");
      }
    }
    const floor = this.floor;

    this.style.width = Math.max(size("w", "w"), floor.width) + "px";

    /* A fixed window is as tall as what is in it, unless its markup says
       otherwise. A height written by hand is a number that stops being right
       the moment a row is added, and both windows here had drifted that way.
       Width stays a decision, because a column of readings has no natural
       one. */
    this.style.height = fixed && !this.hasAttribute("h")
      ? "auto"
      : Math.max(size("h", "h"), floor.height) + "px";
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
   *
   * @fires nx-front - Only where something changed, so a window already in
   *   front raises nothing and the menu is not rewritten for nothing.
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
    /* The main menu belongs to whatever is in front, so the one thing that
       decides which window that is has to say when it changes. */
    this.dispatchEvent(new CustomEvent("nx-front", {
      bubbles: true,
      detail: { name: this.name },
    }));
  }

  /**
   * Shows it, in front.
   * @param {HTMLElement} [asker] - What was used to open it, if anything was.
   *   It rides along as a rectangle, because an application whose icon has to
   *   travel to the foot of the screen has to know where it is travelling
   *   from, and only whoever was clicked knows that.
   */
  open(asker) {
    this.hidden = false;
    this.raise();
    this.save();
    /* So whatever fills this window can fill it now rather than at the next
       poll, which is up to five seconds of dashes. */
    this.dispatchEvent(new CustomEvent("nx-open", {
      bubbles: true,
      detail: { from: asker?.getBoundingClientRect?.() ?? null },
    }));
  }

  /** Hides it, keeping its geometry for the next time.
   *
   * Says so as it goes, because what a window holds may be more than a
   * drawing: a session on the other side of a socket has to be told that
   * nobody is looking any more.
   */
  close() {
    this.hidden = true;
    /* A window that is not on the screen is not the active one, and saying so
       is what lets it come to the front again: raise does nothing for a
       window that already believes it is there, so without this a window
       closed and opened again would arrive silently and the menu would go on
       showing whatever was in front before it. */
    this.setAttribute("inactive", "");
    this.save();
    this.dispatchEvent(new CustomEvent("nx-close", { bubbles: true }));
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

