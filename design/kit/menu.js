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

    /* Whether to keep a column for pictures is the menu's decision and not
       each entry's: the words line up when every entry holds the place, and a
       menu where nothing has a picture would indent all of them for nothing. */
    this.toggleAttribute("with-icons", Boolean(this.querySelector("nx-menu-item[icon]")));

    /* A menu that answers a right click is the same menu, put where the
       pointer is and taken away again. It is not carried about and not
       remembered, so it neither drags nor saves. */
    if (this.hasAttribute("context")) {
      this.hidden = true;
      return;
    }

    const name = this.getAttribute("name");
    const saved = recall(name);
    this.style.left = (saved.x ?? Number(this.getAttribute("x"))) + "px";
    this.style.top = (saved.y ?? Number(this.getAttribute("y"))) + "px";

    draggable(this, title, {
      onSettled: () => remember(name, { x: this.offsetLeft, y: this.offsetTop }),
    });
  }

  /**
   * Puts a context menu at the pointer and takes it away on the next click.
   * @param {number} x - Where the pointer was, in the page.
   * @param {number} y
   */
  openAt(x, y) {
    this.hidden = false;
    /* Measured after it is shown, because a hidden element has no size, and
       kept inside the window so a menu near an edge is not half off it. */
    const own = this.getBoundingClientRect();
    this.style.left = Math.min(x, innerWidth - own.width - 2) + "px";
    this.style.top = Math.min(y, innerHeight - own.height - 2) + "px";

    const away = (event) => {
      if (this.contains(event.target)) return;
      this.close();
    };
    this.dismiss = () => {
      removeEventListener("pointerdown", away, true);
      removeEventListener("keydown", escape);
    };
    const escape = (event) => {
      if (event.key === "Escape") this.close();
    };
    addEventListener("pointerdown", away, true);
    addEventListener("keydown", escape);
  }

  /** Takes it away, and stops listening for what would have. */
  close() {
    this.hidden = true;
    this.dismiss?.();
    this.dismiss = null;
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

    /* Every entry gets the place, whether it has a picture for it or not, so
       the words all begin at the same column. */
    const art = document.createElement("i");
    art.className = "art mark";
    if (this.hasAttribute("icon")) showArt(art, this.getAttribute("icon"));
    this.prepend(art);
    if (this.hasAttribute("key")) {
      const key = document.createElement("span");
      key.className = "key";
      key.textContent = this.getAttribute("key");
      this.append(key);
    }
    const target = this.getAttribute("opens");
    if (target) {
      this.addEventListener("click", () => {
        if (this.hasAttribute("disabled")) return;
        document.querySelector(`nx-window[name="${target}"]`)?.open();
      });
    }
  }
}

