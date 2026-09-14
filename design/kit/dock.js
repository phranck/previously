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
        if (this.hasAttribute("disabled")) return;
        document.querySelector(`nx-window[name="${target}"]`)?.open();
      });
    }
  }
}

