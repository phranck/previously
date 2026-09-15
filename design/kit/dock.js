/* --- nx-dock ------------------------------------------------------------ */

/**
 * One tile, in the dock or on the floor of the screen.
 * @attr icon - Which picture it carries.
 * @attr opens - The name of an nx-window, if it starts one.
 * @attr idle - Draw the three marks that say the application is not running.
 * @attr spaced - Push it to the foot of the dock.
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

/** How long an icon takes to reach its place on the floor. Brisk, because it
 *  is a thing moving rather than an effect: long enough to be followed by the
 *  eye and short enough that nobody waits for it. */
const FLIGHT_MS = 260;

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

/**
 * Sends a picture of an icon from one place to another.
 * @param {string} icon - Which picture.
 * @param {DOMRect} from - Where it starts.
 * @param {DOMRect} to - Where it lands.
 * @returns {Promise} Settled when it has landed.
 *
 * A transform and nothing else, so this costs the compositor and not the
 * layout. Where the reader has asked for less movement there is no flight at
 * all: the tile is simply there, which is what they asked for.
 */
function fly(icon, from, to) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return Promise.resolve();

  const ghost = document.createElement("i");
  ghost.className = "art flying";
  showArt(ghost, icon);
  ghost.style.left = to.left + "px";
  ghost.style.top = to.top + "px";
  ghost.style.width = to.width + "px";
  ghost.style.height = to.height + "px";
  document.body.append(ghost);

  const across = (from.left + from.width / 2) - (to.left + to.width / 2);
  const down = (from.top + from.height / 2) - (to.top + to.height / 2);
  const smaller = to.width ? Math.max(0.2, from.width / to.width) : 1;

  const flight = ghost.animate([
    { transform: `translate(${across}px, ${down}px) scale(${smaller})` },
    { transform: "translate(0, 0) scale(1)" },
  ], { duration: FLIGHT_MS, easing: "ease-out" });

  return flight.finished.catch(() => {}).finally(() => ghost.remove());
}

