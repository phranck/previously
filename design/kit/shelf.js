/* --- nx-shelf and nx-thing ---------------------------------------------- */

/** A floor of icons, of which at most one is chosen at a time. */
class NxShelf extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;
    this.addEventListener("click", (event) => {
      const thing = event.target.closest("nx-thing");
      if (!thing || !this.contains(thing)) return;
      if (thing.hasAttribute("disabled")) return;
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
    this.draggable = this.canBeUsed;
  }

  /** Watched so that switching a thing off takes its drag handle with it. */
  static get observedAttributes() { return ["disabled"]; }

  attributeChangedCallback() {
    if (this.ready) this.draggable = this.canBeUsed;
  }

  /** @returns {string} What this thing hands over when it is used. */
  get value() { return this.getAttribute("value"); }

  /** @returns {boolean} Whether it hands anything over at all. A thing can be
   *  switched off because using it would do nothing, which is different from
   *  having nothing to give. */
  get canBeUsed() {
    return this.hasAttribute("value") && !this.hasAttribute("disabled");
  }

  /**
   * Makes it liftable, and makes a double click mean the same as carrying it
   * somewhere and letting go.
   *
   * Both raise `nx-choose`, which bubbles, so a page answers in one place
   * however the thing was used.
   */
  carry() {
    this.addEventListener("dragstart", (event) => {
      /* Checked here rather than when this was wired, because a thing is
         switched off and on again whilst the page is up. */
      if (!this.canBeUsed) return event.preventDefault();
      event.dataTransfer.setData("text/plain", this.value);
      event.dataTransfer.effectAllowed = "copy";
      this.setAttribute("lifting", "");
    });

    this.addEventListener("dragend", () => this.removeAttribute("lifting"));

    this.addEventListener("dblclick", () => {
      if (!this.canBeUsed) return;
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

