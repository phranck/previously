/* --- nx-dock ------------------------------------------------------------ */

/** How far the pointer may wander before it is carrying a tile rather than
 *  clicking one. A tile is opened with a double click, and a hand that moves
 *  a pixel between the two clicks must not leave the tile a slot lower. */
const GRIP_PX = 4;

/**
 * The dock: a column of slots, one tile high, that a person arranges and
 * fills.
 *
 * A tile is lifted out of the column by dragging it and set down on a slot
 * that is free. While it travels, the slot it would land on shows itself with
 * the ghost of its icon. Carried off the column it leaves the dock, where
 * `mayLeave` allows that, and otherwise goes back to where it came from.
 *
 * An application joins the dock the same way the other way round: its icon is
 * dragged here from the File Viewer, or its tile from the floor of the screen,
 * onto a free slot. The dock says so with `nx-dock` and whoever knows what the
 * application is builds the tile and hands it to `take`.
 *
 * Where a tile ends up is remembered under its name, so a tile that is to
 * keep its place across a reload needs one. The Workspace tile carries
 * `fixed` instead: NeXTSTEP kept it at the head of the dock, and it is the
 * one tile there is nothing to remember about.
 *
 * @fires nx-dock - Something standing for an application was let go over a
 *   free slot, carrying its value and that slot.
 * @fires nx-undock - A tile left the dock, carrying what it stood for.
 */
class NxDock extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    /** The slot something on its way would land on.
     *  @type {HTMLElement} */
    this.mark = document.createElement("i");
    this.mark.className = "slot";
    /** The ghost of its icon, standing in that slot.
     *  @type {HTMLElement} */
    this.ghost = document.createElement("i");
    this.ghost.className = "art";
    this.mark.append(this.ghost);

    /** The application whose icon is being dragged here, while it is.
     *  @type {Element | null} */
    this.offered = null;

    this.arrange();
    for (const tile of this.tiles) {
      if (!tile.hasAttribute("fixed")) this.carry(tile);
    }
    this.receive();

    /* A window made shorter can leave a tile on a slot that is no longer on
       the screen. Arranging again puts it on the nearest free one, and
       because only letting go of a tile writes anything down, making the
       window tall again brings it back to where it was put. */
    addEventListener("resize", () => this.arrange());
  }

  /** @returns {NxTile[]} The tiles in the column, in markup order. */
  get tiles() {
    return [...this.querySelectorAll("nx-tile")];
  }

  /** @returns {number} How tall one slot is, which is how tall a tile is. */
  get step() {
    return parseFloat(getComputedStyle(this).getPropertyValue("--dock-width"));
  }

  /** @returns {number} How many slots are on the screen. */
  get slots() {
    return Math.max(1, Math.floor(deskRoom().height / this.step));
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
    /** @type {Set<number>} */
    const taken = new Set();
    const put = (/** @type {HTMLElement} */ tile, /** @type {number} */ slot) => {
      taken.add(slot);
      tile.style.gridRow = String(slot);
    };
    const open = (/** @type {number} */ slot) =>
      slot >= 1 && slot <= this.slots && !taken.has(slot);

    const fixed = this.tiles.filter((tile) => tile.hasAttribute("fixed"));
    fixed.filter((tile) => !tile.hasAttribute("foot"))
      .forEach((tile, index) => put(tile, index + 1));
    const feet = fixed.filter((tile) => tile.hasAttribute("foot"));
    feet.forEach((tile, index) => put(tile, this.slots - feet.length + 1 + index));

    /** @type {HTMLElement[]} */
    const waiting = [];
    for (const tile of this.tiles.filter((tile) => !tile.hasAttribute("fixed"))) {
      const name = tile.getAttribute("name");
      const slot = name === null ? undefined : saved[name];
      if (slot !== undefined && Number.isInteger(slot) && open(slot)) put(tile, slot);
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
   * @param {HTMLElement} [carried] - The tile on its way, which does not count
   *   as being in the way of itself.
   * @returns {boolean} Whether a tile may be set down there.
   */
  isFree(slot, carried) {
    if (!(slot >= 1 && slot <= this.slots)) return false;
    return !this.tiles.some(
      (tile) => tile !== carried && this.slotOf(tile) === slot);
  }

  /**
   * @param {string} value - What a tile would stand for.
   * @returns {boolean} Whether a tile for it is in the column already. An
   *   application has one tile, so one that is here is not offered a second.
   */
  holds(value) {
    return this.tiles.some((tile) => tile.getAttribute("value") === value);
  }

  /**
   * @param {DeskPoint} point - A place on the desk.
   * @returns {boolean} Whether it lies over the column.
   */
  covers(point) {
    const column = deskRect(this);
    return point.x >= column.left && point.x < column.left + column.width;
  }

  /**
   * @param {DeskPoint} point - Where something would be let go: the middle of
   *   a carried tile, or the pointer during a drag from the File Viewer.
   * @param {HTMLElement} [carried] - The tile on its way, if it is one of the
   *   column's own.
   * @returns {number} The slot it would land on, or 0 where it would land on
   *   none, which is off the column or over a slot that is taken.
   */
  landingAt(point, carried) {
    if (!this.covers(point)) return 0;
    const column = deskRect(this);
    const slot = Math.min(this.slots,
      Math.max(1, Math.floor((point.y - column.top) / this.step) + 1));
    return this.isFree(slot, carried) ? slot : 0;
  }

  /**
   * Shows which slot something on its way would land on.
   * @param {number} slot - Which one, or 0 for none.
   * @param {string} [icon] - The picture of what is on its way, which stands
   *   faded in the slot as the ghost NeXTSTEP drew there.
   */
  aimAt(slot, icon = "") {
    if (!slot) {
      this.mark.remove();
      return;
    }
    showArt(this.ghost, icon);
    this.mark.style.gridRow = String(slot);
    if (!this.mark.isConnected) this.append(this.mark);
  }

  /**
   * Sets a tile down and writes where it went.
   * @param {HTMLElement} tile
   * @param {number} slot
   */
  settle(tile, slot) {
    tile.style.gridRow = String(slot);
    const name = tile.getAttribute("name");
    if (!name) return;
    remember("dock", { places: { ...(recall("dock").places ?? {}), [name]: slot } });
  }

  /**
   * Puts a tile into the column that was not in it.
   * @param {HTMLElement} tile - The new tile, with a name if it is to keep its
   *   place across a reload.
   * @param {number} [slot] - Where it was let go. Left out, it goes back to
   *   where it stood last time, or takes the first free slot.
   */
  take(tile, slot) {
    this.append(tile);
    if (!tile.hasAttribute("fixed")) this.carry(tile);
    if (slot) this.settle(tile, slot);
    else this.arrange();
  }

  /**
   * Takes a tile out of the column, and forgets where it stood.
   * @param {HTMLElement} tile
   */
  release(tile) {
    tile.remove();
    const name = tile.getAttribute("name");
    if (name) {
      const places = { ...(recall("dock").places ?? {}) };
      delete places[name];
      remember("dock", { places });
    }
    this.dispatchEvent(new CustomEvent("nx-undock", {
      bubbles: true, detail: { value: tile.getAttribute("value") ?? "" },
    }));
  }

  /**
   * Asks for a tile standing for something that was let go over a free slot.
   * @param {string} value - What it stands for.
   * @param {number} slot - Where it was let go.
   */
  askFor(value, slot) {
    this.dispatchEvent(new CustomEvent("nx-dock", {
      bubbles: true, detail: { value, slot },
    }));
  }

  /**
   * @param {HTMLElement} tile - A tile in the column.
   * @param {boolean} command - Whether Command is held.
   * @returns {boolean} Whether letting it go off the column takes it out of
   *   the dock.
   *
   * A tile whose application is running stays unless Command is held, which
   * is what NeXTSTEP asks for. Running is a tile without the three marks.
   */
  mayLeave(tile, command) {
    return tile.hasAttribute("idle") || command;
  }

  /**
   * Lets a tile in the column be carried: onto another free slot, or off the
   * column and out of the dock.
   * @param {HTMLElement} tile
   *
   * Off the column, where letting go would take the tile out, the dimmed copy
   * in its slot goes. That is how NeXTSTEP's User's Guide says to tell the
   * moment to let go.
   */
  carry(tile) {
    liftable(tile,
      (middle, command) => {
        tile.toggleAttribute("leaving", !this.covers(middle) && this.mayLeave(tile, command));
        this.aimAt(this.landingAt(middle, tile), tile.getAttribute("icon") ?? "");
      },
      (middle, command) => {
        tile.removeAttribute("leaving");
        this.aimAt(0);
        if (!middle) return;
        if (!this.covers(middle)) {
          if (this.mayLeave(tile, command)) this.release(tile);
          return;
        }
        const slot = this.landingAt(middle, tile);
        if (slot) this.settle(tile, slot);
      });
  }

  /**
   * Lets an application be dragged onto the column from where its icon lies,
   * such as the File Viewer.
   *
   * Only an nx-thing carrying `dockable` is offered, and only while no tile
   * here stands for it. The column takes the pointer for as long as such a
   * drag lasts, so the slots it passes over are the dock's rather than those
   * of whatever window lies behind them, and it gives the pointer back however
   * the drag ends.
   */
  receive() {
    document.addEventListener("dragstart", (event) => {
      const thing = closestTo(event, "nx-thing");
      if (event.defaultPrevented || !thing?.hasAttribute("dockable")) return;
      if (this.holds(thing.getAttribute("value") ?? "")) return;
      this.offered = thing;
      this.setAttribute("receiving", "");
    });

    const over = () => {
      this.offered = null;
      this.removeAttribute("receiving");
      this.aimAt(0);
    };
    for (const ending of ["dragend", "drop"]) document.addEventListener(ending, over);

    this.addEventListener("dragover", (event) => {
      if (!this.offered) return;
      const slot = this.landingAt(deskPoint(event));
      this.aimAt(slot, this.offered.getAttribute("icon") ?? "");
      if (!slot) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "link";
    });

    this.addEventListener("dragleave", (event) => {
      const into = event.relatedTarget;
      if (!(into instanceof Node && this.contains(into))) this.aimAt(0);
    });

    this.addEventListener("drop", (event) => {
      const value = this.offered?.getAttribute("value");
      const slot = this.landingAt(deskPoint(event));
      if (!value || !slot) return;
      event.preventDefault();
      this.askFor(value, slot);
    });
  }
}

/**
 * Lets a tile be picked up and carried anywhere on the desk.
 * @param {HTMLElement} tile - What is picked up.
 * @param {(middle: DeskPoint, command: boolean) => void} onMove - Told where
 *   the middle of the carried tile is now, and whether Command is held.
 * @param {(middle: DeskPoint | null, command: boolean) => void} onLetGo - Told
 *   the same once it is let go. The middle is null where the browser took the
 *   pointer away, which counts as not having carried it anywhere.
 *
 * The tile stays where it stands, dimmed, and a picture of it follows the
 * pointer. That is what NeXTSTEP's figures show, a dimmed copy in the slot
 * while the tile is out on the desk, and it leaves the decision of where the
 * tile goes to whoever is told it was let go.
 *
 * Command is reported because a running application's tile leaves the dock
 * only with it held. A Mac keyboard has the key under the same name.
 */
function liftable(tile, onMove, onLetGo) {
  gesture(tile,
    (point, start, event) => {
      const across = point.x - start.grabbedAt.x;
      const down = point.y - start.grabbedAt.y;
      if (!start.picture) {
        if (Math.hypot(across, down) < GRIP_PX) return;
        start.picture = pictureOf(tile, start.from);
        tile.setAttribute("carried", "");
      }
      start.picture.style.transform = `translate(${across}px, ${down}px)`;
      start.middle = {
        x: start.from.left + start.from.width / 2 + across,
        y: start.from.top + start.from.height / 2 + down,
      };
      onMove(start.middle, event.metaKey);
    },
    (point) => ({
      grabbedAt: point,
      from: deskRect(tile),
      picture: /** @type {HTMLElement | null} */ (null),
      middle: /** @type {DeskPoint | null} */ (null),
    }),
    (start, event) => {
      if (!start.picture) return;
      start.picture.remove();
      tile.removeAttribute("carried");
      onLetGo(event.type === "pointercancel" ? null : start.middle, event.metaKey);
    });
}

/**
 * @param {HTMLElement} tile - What is being carried.
 * @param {DeskRect} from - Where it stands.
 * @returns {HTMLElement} A tile like it, standing over it, which follows the
 *   pointer while the tile itself stays put.
 */
function pictureOf(tile, from) {
  const picture = document.createElement("nx-tile");
  picture.setAttribute("icon", tile.getAttribute("icon") ?? "");
  picture.toggleAttribute("idle", tile.hasAttribute("idle"));
  picture.setAttribute("picture", "");
  picture.style.left = from.left + "px";
  picture.style.top = from.top + "px";
  document.body.append(picture);
  return picture;
}

/**
 * One tile, in the dock or on the floor of the screen.
 * @attr icon - Which picture it carries.
 * @attr value - What it stands for, which is the value the icon it was
 *   dragged from carries.
 * @attr opens - The name of an nx-window, if it starts one.
 * @attr idle - Draw the three marks that say the application is not running.
 * @attr fixed - Stay where it is put and refuse to be carried. The Workspace
 *   tile carries this, because NeXTSTEP kept it at the head of the dock.
 * @attr foot - With `fixed`, sit at the foot of the column rather than at its
 *   head.
 * @attr carried - Set while a picture of it is being carried, and taken off
 *   when that is let go.
 * @attr leaving - Set while it is carried off the column and letting go would
 *   take it out of the dock.
 * @attr picture - It is that picture, rather than a tile of the dock or the
 *   floor.
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
    showArt(art, this.getAttribute("icon") ?? "");
    this.append(art);

    const target = this.getAttribute("opens");
    if (target) {
      this.addEventListener("dblclick", () => {
        if (this.hasAttribute("disabled")) return;
        /** @type {NxWindow | null} */ (
          document.querySelector(`nx-window[name="${target}"]`))?.open(this);
      });
    }
  }
}

/**
 * An application's tile on the floor.
 * @typedef {object} FloorTile
 * @property {string} icon - Which picture it carries.
 * @property {string} opens - The name of the window it stands for.
 * @property {string} value - What it stands for, which is what the dock is
 *   told when the tile is carried there.
 */

/**
 * Where an application that is not in the dock puts its icon.
 *
 * NeXTSTEP stacked those along the foot of the screen from the left corner
 * rightwards, and took each away when its application went. The tile is the
 * dock's own: `Workspace.app/tile.tiff` is a plain gray square with the icon
 * on it and no lettering, and that is what a tile here already is.
 *
 * An application that has just been started does not simply appear there. Its
 * icon travels from whatever was used to start it, and the tile is in place
 * when it lands.
 */
class NxFloor extends HTMLElement {
  /**
   * Puts the icons there, in the order they were started.
   * @param {FloorTile[]} running - One for each.
   * @param {{opens: string, from: DeskRect | null}} [arriving] - The one that
   *   has just started, and where it is coming from. Left out, everything is
   *   simply drawn.
   * @returns {Promise<void>} Settled once what arrived has landed.
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
    await fly(newcomer.getAttribute("icon") ?? "", arriving.from, deskRect(newcomer));
    newcomer.style.visibility = "";
  }

  /**
   * @param {FloorTile} application - What to draw.
   * @returns {NxTile} One tile for an application.
   *
   * It can be carried into the dock, onto a free slot, which is what
   * NeXTSTEP's User's Guide offers for a freestanding icon. Let go anywhere
   * else, it stays where it stands.
   */
  tile(application) {
    const tile = document.createElement("nx-tile");
    tile.setAttribute("icon", application.icon);
    tile.setAttribute("opens", application.opens);
    tile.setAttribute("value", application.value);

    const dock = document.querySelector("nx-dock");
    if (dock) {
      liftable(tile,
        (middle) => dock.aimAt(dock.landingAt(middle), application.icon),
        (middle) => {
          dock.aimAt(0);
          const slot = middle ? dock.landingAt(middle) : 0;
          if (slot) dock.askFor(application.value, slot);
        });
    }
    return tile;
  }
}
