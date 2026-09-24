/* The two things on this page that do anything: copying the install line, and
   the switch between the light and the dark scheme. */

/* --- the scheme switch --------------------------------------------------- */

const schemeButton = document.getElementById("scheme");
const schemeLabel = document.getElementById("scheme-label");
const systemPrefersDark = matchMedia("(prefers-color-scheme: dark)");

/* The three states, in the order the switch walks through them. Following the
   system is the first, because it is what somebody who has never pressed this
   gets. */
const STATES = ["system", "light", "dark"];

/* What a phone paints its address bar with. Following the system needs both,
   each behind the media query that decides it; a chosen scheme needs one and
   has to overrule the pair, which a media attribute cannot do. */
const THEME_COLOUR = { light: "#ffffff", dark: "#121218" };

/**
 * Which of the three the switch is on.
 *
 * The attribute is the single record of that: it is absent whilst the page
 * follows the system, which is also what the stylesheet tests for.
 *
 * @returns {"system" | "light" | "dark"} The state, not the scheme on screen.
 */
function currentState() {
  const chosen = document.documentElement.dataset.scheme;
  return chosen === "light" || chosen === "dark" ? chosen : "system";
}

/**
 * The scheme actually on screen, which for the system state is the system's.
 *
 * @returns {"light" | "dark"} What a reader is looking at.
 */
function currentScheme() {
  const state = currentState();
  if (state !== "system") return state;
  return systemPrefersDark.matches ? "dark" : "light";
}

/**
 * Puts the theme colour in the head, which is the one thing about a scheme
 * that lives outside the stylesheet.
 *
 * Following the system means two of them, so a reader who switches their
 * machine over whilst the page is open gets the right one without this script
 * running again.
 */
function writeThemeColour() {
  for (const meta of document.querySelectorAll('meta[name="theme-color"]')) {
    meta.remove();
  }

  const state = currentState();
  const wanted =
    state === "system"
      ? [
          { scheme: "light", media: "(prefers-color-scheme: light)" },
          { scheme: "dark", media: "(prefers-color-scheme: dark)" },
        ]
      : [{ scheme: state, media: null }];

  for (const { scheme, media } of wanted) {
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = THEME_COLOUR[scheme];
    if (media) meta.media = media;
    document.head.append(meta);
  }
}

/**
 * Says where the switch stands and what pressing it does next.
 *
 * A control that walks through three states is not a toggle, so it carries no
 * pressed state: what it announces is the state itself and the one after it.
 */
function describeScheme() {
  const state = currentState();
  const next = STATES[(STATES.indexOf(state) + 1) % STATES.length];
  const standing =
    state === "system" ? "following the system" : `set to ${state}`;
  const following = next === "system" ? "follow the system" : `switch to ${next}`;

  schemeLabel.textContent = `Colour scheme: ${standing}. Press to ${following}.`;
  writeThemeColour();
}

schemeButton.addEventListener("click", () => {
  const next = STATES[(STATES.indexOf(currentState()) + 1) % STATES.length];

  if (next === "system") {
    delete document.documentElement.dataset.scheme;
    localStorage.removeItem("scheme");
  } else {
    document.documentElement.dataset.scheme = next;
    localStorage.setItem("scheme", next);
  }

  describeScheme();
});

// Whilst the switch is on the system state, the page moves with the system: a
// Mac turns dark at sunset and this turns with it.
systemPrefersDark.addEventListener("change", () => {
  if (currentState() === "system") describeScheme();
});

describeScheme();

/* --- copying the install line -------------------------------------------- */

const copyButton = document.getElementById("copy");
const copyLabel = document.getElementById("copy-label");
const copyIcon = document.getElementById("copy-icon").querySelector("use");
const commandLine = document.getElementById("command");

const RESTING_LABEL = copyLabel.textContent;
const CONFIRMATION_MILLISECONDS = 1600;

let confirmationTimer = 0;

/**
 * Says the line has been taken, for a moment.
 *
 * The button keeps its own resting label rather than a constant written here,
 * so the two cannot disagree when the markup changes.
 *
 * @param {string} label What the button says whilst confirming.
 * @param {string} glyph The symbol id in site/icons.svg to show with it.
 */
function confirm_(label, glyph) {
  copyLabel.textContent = label;
  copyIcon.setAttribute("href", `site/icons.svg#${glyph}`);
  copyButton.classList.add("button--copied");

  clearTimeout(confirmationTimer);
  confirmationTimer = setTimeout(() => {
    copyLabel.textContent = RESTING_LABEL;
    copyIcon.setAttribute("href", "site/icons.svg#copy");
    copyButton.classList.remove("button--copied");
  }, CONFIRMATION_MILLISECONDS);
}

copyButton.addEventListener("click", async () => {
  const line = commandLine.textContent.trim();

  try {
    await navigator.clipboard.writeText(line);
    confirm_("Copied", "check");
  } catch {
    // Every browser refuses the clipboard outside a secure context, and this
    // page is also opened from a checkout over file://. Selecting the line
    // leaves the reader one keystroke away from the same result.
    const range = document.createRange();
    range.selectNodeContents(commandLine);
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    confirm_("Selected", "check");
  }
});
