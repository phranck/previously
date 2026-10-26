/* --- nx-notifications and nx-notification ------------------------------- */

/**
 * What one notification says.
 * @typedef {object} NotificationWords
 * @property {string} art - Which picture, by the name showArt knows.
 * @property {string} headline - The short line in the panel name's bold.
 * @property {string} message - The sentence under it.
 */

/** How long the notifications below one that goes take to slide up into its
 *  place. Stated here rather than in the stylesheet, because the stack both
 *  sets the transition and waits for it to end. phranck settled on a slide
 *  with no fade on 26 October 2026, and the 220 is a choice: the guide states
 *  no motion at all. */
const SLIDE_MS = 220;

/**
 * One notification: the quiet end of the attention panel.
 *
 * The empty title bar with the window's close button at its right, the
 * picture, the headline in bold and the sentence under it. Nothing in it takes
 * the keyboard or waits for an answer.
 */
class NxNotification extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;
    this.innerHTML = `
      <div class="titlebar"><i class="close"></i></div>
      <div class="body">
        <i class="art sign"></i>
        <div class="words"><div class="headline"></div><p class="message"></p></div>
      </div>`;
  }

  /**
   * Writes what it says.
   * @param {NotificationWords} words
   */
  say({ art, headline, message }) {
    const sign = this.querySelector(".sign");
    if (sign instanceof HTMLElement) showArt(sign, art);
    const lines = this.querySelectorAll(".headline, .message");
    lines[0].textContent = headline;
    lines[1].textContent = message;
  }
}

/**
 * The stack of notifications beside the dock.
 *
 * NeXTSTEP had no notifications, so what stands here is built from the
 * attention panel, and it never stops anybody.
 *
 * A notification appears and goes at once, as every window and panel on this
 * desk does. What moves is the stack: the ones below a notification that goes
 * slide up into its place, so the eye can follow where each went.
 *
 * Clicking a notification raises `nx-notification-open`, and its close button
 * `nx-notification-close`, both carrying its name. Either way it goes. What
 * opening one leads to, and what closing one means for the next time, belong
 * to whoever posted it.
 */
class NxNotifications extends HTMLElement {
  /**
   * Shows a notification, or rewrites the one of that name in place.
   * @param {string} name - Which notification it is.
   * @param {NotificationWords} words - What it says.
   */
  post(name, words) {
    let shown = this.shown(name);
    if (!shown) {
      const made = document.createElement("nx-notification");
      made.dataset.name = name;
      made.addEventListener("click", (event) => {
        const closing = event.target instanceof Element && event.target.closest(".close");
        this.withdraw(name);
        this.dispatchEvent(new CustomEvent(
          closing ? "nx-notification-close" : "nx-notification-open", { detail: { name } }));
      });
      this.append(made);
      shown = made;
    }
    shown.say(words);
  }

  /**
   * Takes a notification away and lets the ones below it slide up.
   * @param {string} name
   *
   * It is hidden at once and its room closes over SLIDE_MS. With reduced
   * motion asked for, the room goes at once as well. A timer stands behind
   * the end of the transition, because a page in a tab nobody is looking at
   * may never run it, and a notification that stays half gone is in the way.
   */
  withdraw(name) {
    const shown = this.shown(name);
    if (!shown) return;
    shown.toggleAttribute("leaving", true);
    if (globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      shown.remove();
      return;
    }

    shown.style.height = `${shown.offsetHeight}px`;
    shown.style.transition =
      `height ${SLIDE_MS}ms ease-in-out, margin-bottom ${SLIDE_MS}ms ease-in-out`;
    shown.getBoundingClientRect();
    shown.style.height = "0px";
    shown.style.marginBottom = "0px";
    shown.style.borderWidth = "0px";
    const gone = () => shown.remove();
    shown.addEventListener("transitionend", gone, { once: true });
    setTimeout(gone, SLIDE_MS + 50);
  }

  /** @returns {string[]} The names of the notifications standing now, top
   *  first, leaving out any that are on their way out. */
  get names() {
    return this.standing().map((shown) => shown.dataset.name ?? "");
  }

  /**
   * One notification that is standing, by its name.
   * @param {string} name
   * @returns {NxNotification | null}
   */
  shown(name) {
    return this.standing().find((shown) => shown.dataset.name === name) ?? null;
  }

  /** @returns {NxNotification[]} Every notification standing, top first. */
  standing() {
    return [...this.querySelectorAll("nx-notification:not([leaving])")]
      .filter((shown) => shown instanceof NxNotification);
  }
}
