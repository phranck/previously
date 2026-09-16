/* --- nx-dock ------------------------------------------------------------ */

/** How far the pointer may wander before it is carrying a tile rather than
 *  clicking one. A tile is opened with a double click, and a hand that moves
 *  a pixel between the two clicks must not leave the tile a slot lower. */
const GRIP_PX = 4;

/**
 * The dock: a column of slots, one tile high, that a person arranges.
 *
 * A tile is lifted out of the column by dragging it, carried up and down, and
 * set down on a slot that is free. Whilst it travels, the slot it would land
 * on shows itself. Letting go anywhere else puts it back where it came from,
 * because a tile can only be somewhere in the dock.
 *
 * Where a tile ends up is remembered under its name, so a tile that is to
 * keep its place across a reload needs one. The Workspace tile carries
 * `fixed` instead: NeXTSTEP kept it at the head of the dock, and it is the
 * one tile there is nothing to remember about.
 */
class NxDock extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.mark = document.createElement("i");
    this.mark.className = "slot";

    this.arrange();
    for (const tile of this.tiles) {
      if (!tile.hasAttribute("fixed")) this.carry(tile);
    }

    /* A window made shorter can leave a tile on a slot that is no longer on
       the screen. Arranging again puts it on the nearest free one, and
       because only letting go of a tile writes anything down, making the
       window tall again brings it back to where it was put. */
    addEventListener("resize", () => this.arrange());
  }

  /** @returns {HTMLElement[]} The tiles in the column, in markup order. */
  get tiles() {
    return [...this.querySelectorAll("nx-tile")];
  }

  /** @returns {number} How tall one slot is, which is how tall a tile is. */
  get step() {
    return parseFloat(getComputedStyle(this).getPropertyValue("--dock-width"));
  }

  /** @returns {number} How many slots are on the screen. */
  get slots() {
    return Math.max(1, Math.floor(innerHeight / this.step));
  }

  /**
   * Puts every tile on a slot.
   *
   * The fixed ones take the ends of the column in markup order, the head by
   * default and the foot where they say so. Everything else goes back to
   * where it was left, and anything without a place to go back to, or whose
   * place is taken or off the screen, takes the first slot that is free.
   */
  arrange() {
    const saved = recall("dock").places ?? {};
    const taken = new Set();
    const put = (tile, slot) => {
      taken.add(slot);
      tile.style.gridRow = slot;
    };
    const open = (slot) => slot >= 1 && slot <= this.slots && !taken.has(slot);

    const fixed = this.tiles.filter((tile) => tile.hasAttribute("fixed"));
    fixed.filter((tile) => !tile.hasAttribute("foot"))
      .forEach((tile, index) => put(tile, index + 1));
    const feet = fixed.filter((tile) => tile.hasAttribute("foot"));
    feet.forEach((tile, index) => put(tile, this.slots - feet.length + 1 + index));

    const waiting = [];
    for (const tile of this.tiles.filter((tile) => !tile.hasAttribute("fixed"))) {
      const slot = saved[tile.getAttribute("name")];
      if (Number.isInteger(slot) && open(slot)) put(tile, slot);
      else waiting.push(tile);
    }
    for (const tile of waiting) {
      let slot = 1;
      while (!open(slot)) slot += 1;
      put(tile, slot);
    }
  }

  /** @param {HTMLElement} tile @returns {number} Which slot it is on. */
  slotOf(tile) {
    return Number(tile.style.gridRow);
  }

  /**
   * @param {number} slot - Which one.
   * @param {HTMLElement} carried - The tile on its way, which does not count
   *   as being in the way of itself.
   * @returns {boolean} Whether a tile may be set down there.
   */
  isFree(slot, carried) {
    if (!(slot >= 1 && slot <= this.slots)) return false;
    return !this.tiles.some(
      (tile) => tile !== carried && this.slotOf(tile) === slot);
  }

  /**
   * @param {number} top - How far down the column something sits.
   * @returns {number} The slot its middle is over.
   */
  slotUnder(top) {
    const middle = top + this.step / 2;
    return Math.min(this.slots, Math.max(1, Math.floor(middle / this.step) + 1));
  }

  /**
   * Shows which slot a travelling tile would land on.
   * @param {number} slot - Which one, or 0 for none, which is what letting go
   *   over an occupied slot means.
   */
  aimAt(slot) {
    if (!slot) {
      this.mark.remove();
      return;
    }
    this.mark.style.gridRow = slot;
    if (!this.mark.isConnected) this.append(this.mark);
  }

  /**
   * Sets a tile down and writes where it went.
   * @param {HTMLElement} tile
   * @param {number} slot
   */
  settle(tile, slot) {
    tile.style.gridRow = slot;
    const name = tile.getAttribute("name");
    if (!name) return;
    remember("dock", { places: { ...(recall("dock").places ?? {}), [name]: slot } });
  }

  /**
   * Lets one tile be carried up and down the column.
   * @param {HTMLElement} tile
   *
   * Only up and down, because the dock is one tile wide and a tile has
   * nowhere else to be. It is moved with a transform whilst it travels, so
   * the column it is leaving is not laid out again on every frame, and its
   * slot is written once at the end.
   */
  carry(tile) {
    gesture(tile,
      (event, start) => {
        const moved = event.clientY - start.grabbedAt;
        if (!start.carrying && Math.abs(moved) < GRIP_PX) return;

        start.carrying = true;
        tile.setAttribute("carried", "");
        tile.style.transform = `translateY(${moved}px)`;
        start.landing = this.slotUnder(start.from + moved);
        this.aimAt(this.isFree(start.landing, tile) ? start.landing : 0);
      },
      (event) => ({
        grabbedAt: event.clientY,
        from: tile.offsetTop,
        carrying: false,
        landing: 0,
      }),
      (start) => {
        tile.style.transform = "";
        tile.removeAttribute("carried");
        this.aimAt(0);
        if (start.carrying && this.isFree(start.landing, tile)) {
          this.settle(tile, start.landing);
        }
      });
  }
}

/**
 * One tile, in the dock or on the floor of the screen.
 * @attr icon - Which picture it carries.
 * @attr opens - The name of an nx-window, if it starts one.
 * @attr idle - Draw the three marks that say the application is not running.
 * @attr fixed - Stay where it is put and refuse to be carried. The Workspace
 *   tile carries this, because NeXTSTEP kept it at the head of the dock.
 * @attr foot - With `fixed`, sit at the foot of the column rather than at its
 *   head.
 * @attr carried - Set whilst it is being dragged, and taken off when it lands.
 *
 * A double click starts it and a single click does nothing, which is what the
 * OpenStep guidelines require and why: a tile is moved by dragging it, and a
 * click that acted would fire whenever somebody began a drag and thought
 * better of it. It also keeps this the same as the File Viewer, where one
 * click chooses and two open.
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
      this.addEventListener("dblclick", () => {
        if (this.hasAttribute("disabled")) return;
        document.querySelector(`nx-window[name="${target}"]`)?.open(this);
      });
    }
  }
}

/**
 * Where an application that is not in the dock puts its icon.
 *
 * NeXTSTEP stacked those along the foot of the screen from the left corner
 * rightwards, and took each away when its application went. The tile is the
 * dock's own: `Workspace.app/tile.tiff` is a plain grey square with the icon
 * on it and no lettering, and that is what a tile here already is.
 *
 * An application that has just been started does not simply appear there. Its
 * icon travels from whatever was used to start it, and the tile is in place
 * when it lands.
 */
class NxFloor extends HTMLElement {
  /**
   * Puts the icons there, in the order they were started.
   * @param {Array<object>} running - `{icon, opens}` for each.
   * @param {object} [arriving] - The one that has just started, and where it
   *   is coming from: `{opens, from}` with a DOMRect. Left out, everything is
   *   simply drawn.
   * @returns {Promise} Settled once what arrived has landed.
   */
  async show(running, arriving) {
    const tiles = running.map((application) => this.tile(application));
    const newcomer = arriving && tiles.find(
      (tile) => tile.getAttribute("opens") === arriving.opens);

    if (!newcomer || !arriving.from) {
      this.replaceChildren(...tiles);
      return;
    }

    /* Drawn first and hidden, so the place it is flying to is the place it
       will actually take: the tiles beside it decide that, not this one. */
    this.replaceChildren(...tiles);
    newcomer.style.visibility = "hidden";
    await fly(newcomer.getAttribute("icon"), arriving.from,
              newcomer.getBoundingClientRect());
    newcomer.style.visibility = "";
  }

  /** @returns {HTMLElement} One tile for an application. */
  tile(application) {
    const tile = document.createElement("nx-tile");
    tile.setAttribute("icon", application.icon);
    tile.setAttribute("opens", application.opens);
    return tile;
  }
}
