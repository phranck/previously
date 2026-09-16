/* --- nx-viewer ---------------------------------------------------------- */

/**
 * NeXTSTEP's File Viewer, which is four bands stacked in one window.
 *
 * The shelf along the top keeps whatever is dropped on it and has nothing to
 * do with where you are. Under it one line of status about the whole. Then the
 * path, as a row of icons with an arrow between each pair. Then what the last
 * step of that path holds, in a scroller.
 *
 * It knows nothing about what it is showing. The page hands it a path and a
 * list of contents and listens for what was chosen, so the same component
 * serves machines, a shared directory, or anything else that is a place with
 * things in it.
 *
 * @attr status - The line under the shelf, where the page has nothing more
 *   particular to say.
 * @fires nx-path - A step of the path was chosen, carrying its index in
 *   `detail.index` and its value in `detail.value`.
 * @fires nx-visit - Something on the shelf was clicked once, carrying its
 *   value. One click there is an act rather than a selection.
 * @fires nx-choose - Something in the contents or on the shelf was chosen,
 *   from nx-thing, carrying its value.
 */
class NxViewer extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.keep = document.createElement("nx-shelf");
    this.keep.className = "keep";

    /* One click on the shelf is an act, which is the one place in this viewer
       where that is true: NeXT's guidelines say that clicking a folder there
       changes what the viewer shows, and that a drag must not do the same,
       which is why the shelf is the example they use for it. */
    this.keep.addEventListener("click", (event) => {
      const thing = event.target.closest("nx-thing");
      if (!thing || !this.keep.contains(thing)) return;
      this.dispatchEvent(new CustomEvent("nx-visit", {
        bubbles: true,
        detail: { value: thing.getAttribute("value") },
      }));
    });
    this.keep.addEventListener("dragover", (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      this.keep.setAttribute("droppable", "");
    });
    this.keep.addEventListener("dragleave", (event) => {
      if (!this.keep.contains(event.relatedTarget)) this.keep.removeAttribute("droppable");
    });
    this.keep.addEventListener("drop", (event) => {
      event.preventDefault();
      this.keep.removeAttribute("droppable");
      this.dispatchEvent(new CustomEvent("nx-keep", {
        bubbles: true,
        detail: { value: event.dataTransfer.getData("text/plain") },
      }));
    });

    this.status = document.createElement("p");
    this.status.className = "status";
    this.status.textContent = this.getAttribute("status") ?? "";

    this.path = document.createElement("div");
    this.path.className = "path";
    this.path.addEventListener("click", (event) => {
      const thing = event.target.closest("nx-thing");
      if (!thing || !this.path.contains(thing)) return;
      this.dispatchEvent(new CustomEvent("nx-path", {
        bubbles: true,
        detail: { index: Number(thing.dataset.step), value: thing.getAttribute("value") },
      }));
    });

    /* The path is a browser in the original and scrolls sideways as it grows,
       with its trough under it whether there is anything to scroll or not. */
    const way = document.createElement("nx-scroller");
    way.setAttribute("bars", "across");
    way.className = "way";
    way.append(this.path);

    this.contents = document.createElement("nx-shelf");
    this.contents.className = "contents";
    const scroller = document.createElement("nx-scroller");
    scroller.setAttribute("bars", "down across");
    scroller.append(this.contents);

    this.append(this.keep, this.status, way, scroller);
  }

  /**
   * Puts a place and its contents in the window.
   * @param {object} view
   * @param {Array<object>} view.path - The way here, outermost first. Each is
   *   `{label, icon, value}`.
   * @param {Array<object>} view.contents - What the last step holds. Each is
   *   `{label, icon, value}`, and `folder` marks one that has more inside.
   * @param {Array<object>} [view.keeps] - What lies on the shelf, the same
   *   shape. Left out, the shelf is not touched.
   * @param {string} [view.status] - The line under the shelf.
   */
  show({ path = [], contents = [], keeps, status }) {
    if (status !== undefined) this.status.textContent = status;
    if (keeps !== undefined) {
      this.keep.replaceChildren(...keeps.map((entry) => this.thing(entry)));
    }

    this.path.replaceChildren(...path.flatMap((step, index) => {
      const thing = this.thing(step);
      thing.dataset.step = String(index);
      /* The last step is where you are, and the shape that says so is the one
         a chosen thing already wears. */
      if (index === path.length - 1) thing.setAttribute("chosen", "");
      if (index === 0) return [thing];
      return [this.arrow(), thing];
    }));

    this.contents.replaceChildren(...contents.map((entry) => {
      const thing = this.thing(entry);
      if (entry.folder) thing.setAttribute("folder", "");
      return thing;
    }));
  }

  /**
   * @param {object} entry - `{label, icon, value}`.
   * @returns {HTMLElement} The icon with its name, ready to be appended.
   */
  thing(entry) {
    const thing = document.createElement("nx-thing");
    thing.setAttribute("icon", entry.icon ?? "");
    thing.setAttribute("label", entry.label ?? "");
    if (entry.value !== undefined) thing.setAttribute("value", entry.value);
    return thing;
  }

  /** @returns {HTMLElement} The mark between two steps of the path. */
  arrow() {
    const arrow = document.createElement("i");
    arrow.className = "step-arrow";
    return arrow;
  }
}

