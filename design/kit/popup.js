/* --- nx-popup ----------------------------------------------------------- */

/**
 * A pop-up list: a button labeled with what is chosen and marked with NeXT's
 * pop-up mark, and the list of choices that comes up while it is held.
 *
 * Chapter 7 of NeXTSTEP's interface guidelines says how it goes: the list is
 * there only while the mouse stays down, placed so the item that matches the
 * label sits over the button, and letting go over another item chooses it and
 * changes the label. A press and a release without moving chooses what was
 * chosen, which changes nothing. The chapter gives a pop-up list no keyboard,
 * and neither does this.
 *
 * Raises `nx-pick` carrying the value chosen, and only where it changed. Not
 * `nx-choose`, which the File Viewer's things raise and the page answers by
 * opening whatever was chosen.
 *
 * With fewer than two choices there is nothing to choose between, so the
 * button greys its label and does nothing, which is what the chapter asks of a
 * button that would do nothing.
 */
class NxPopup extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;
    this.choices ??= [];

    this.button = document.createElement("button");
    this.button.type = "button";
    this.button.className = "popup-button";
    this.label = document.createElement("span");
    this.label.className = "popup-label";
    const mark = document.createElement("i");
    mark.className = "popup-mark";
    this.button.append(this.label, mark);
    this.append(this.button);

    this.button.addEventListener("pointerdown", (event) => this.held(event));
    this.drawLabel();
  }

  /**
   * Says what can be chosen, and which of it is.
   * @param {{value: string, label: string}[]} choices - In the order the list
   *   shows them.
   * @param {string} [value] - The one chosen, the first where none is named or
   *   the one named is not among them.
   */
  offer(choices, value) {
    this.choices = choices;
    this.value = choices.some((choice) => choice.value === value)
      ? value : choices[0]?.value ?? "";
    this.drawLabel();
  }

  /** Writes the chosen one onto the button, and greys it where there is
   *  nothing to choose between. */
  drawLabel() {
    if (!this.button) return;
    this.label.textContent =
      this.choices.find((choice) => choice.value === this.value)?.label ?? "";
    this.button.disabled = this.choices.length < 2;
  }

  /**
   * Brings the list up for as long as the button is held.
   * @param {PointerEvent} event - The press.
   *
   * The list goes onto the desk rather than into the window, because it is a
   * spring-loaded window of its own: it stands above everything, panels
   * included, and nothing it covers can hold it in.
   */
  held(event) {
    if (event.button !== 0 || this.button.disabled) return;
    event.preventDefault();

    /* The entries are menu entries, which is what NeXTSTEP drew a pop-up
       list's items as, so they wear exactly what an entry of the menu wears. */
    const list = document.createElement("div");
    list.className = "popup-list";
    for (const choice of this.choices) {
      const item = document.createElement("nx-menu-item");
      item.dataset.value = choice.value;
      item.textContent = choice.label;
      item.toggleAttribute("lit", choice.value === this.value);
      list.append(item);
    }
    document.body.append(list);
    this.place(list);

    const under = (pointer) => /** @type {any} */ (
      document.elementFromPoint(pointer.clientX, pointer.clientY))
      ?.closest?.(".popup-list nx-menu-item");
    const follow = (pointer) => {
      const item = under(pointer);
      for (const each of list.children) each.toggleAttribute("lit", each === item);
    };
    const finish = (pointer) => {
      removeEventListener("pointermove", follow);
      removeEventListener("pointercancel", finish);
      const item = pointer.type === "pointerup" ? under(pointer) : null;
      list.remove();
      if (item && item.dataset.value !== this.value) {
        this.value = item.dataset.value;
        this.drawLabel();
        this.dispatchEvent(new CustomEvent("nx-pick", {
          detail: { value: this.value }, bubbles: true }));
      }
    };
    addEventListener("pointermove", follow);
    addEventListener("pointerup", finish, { once: true });
    addEventListener("pointercancel", finish, { once: true });
  }

  /**
   * Puts the list where the chosen item lies over the button.
   * @param {HTMLElement} list - The list, already on the desk so it has a size.
   *
   * Held inside the desk, because a list that runs off it has items nobody can
   * reach. That moves the chosen item off the button near an edge, which is
   * what the chapter warns of and why it advises against a pop-up list there.
   */
  place(list) {
    const button = deskRect(this.button);
    list.style.minWidth = button.width + "px";
    const own = deskRect(list);
    const first = deskRect(list.firstElementChild);
    const row = first?.height ?? 0;
    /* The list's own edge stands above its first item, and the chosen item is
       centered on the button rather than aligned with its top, because the two
       are not the same height. */
    const edge = first ? first.top - own.top : 0;
    const at = Math.max(0, this.choices.findIndex((choice) => choice.value === this.value));
    const top = button.top + (button.height - row) / 2 - edge - at * row;
    const room = deskRoom();
    list.style.left = Math.max(0, Math.min(button.left, room.width - own.width)) + "px";
    list.style.top = Math.max(0, Math.min(top, room.height - own.height)) + "px";
  }
}
