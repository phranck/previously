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
        document.querySelector(`nx-window[name="${target}"]`)?.open();
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
 */
class NxFloor extends HTMLElement {
  /**
   * Puts the icons there, in the order they were started.
   * @param {Array<object>} running - `{icon, opens}` for each.
   */
  show(running) {
    this.replaceChildren(...running.map((application) => {
      const tile = document.createElement("nx-tile");
      tile.setAttribute("icon", application.icon);
      tile.setAttribute("opens", application.opens);
      return tile;
    }));
  }
}

