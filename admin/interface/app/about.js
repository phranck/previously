/* What this tool is, and what a browser sees the first time it arrives. */

import { theWindow } from "./page.js";
import { ask } from "./service.js";
import { released } from "./words.js";
import { deskIsNew } from "../nextstep.js";
import { t } from "../strings.js";

const PRODUCT = "Previously";

/** Where whoever holds the copyright can be read about. */
const HOLDER_SITE = "https://layered.work";

/**
 * Says what this tool is, and waits until that has been read.
 * @returns {Promise<void>}
 *
 * The name and the icon, what the tool is for under the name, then the
 * version and the copyright, and where it was made. The version is the
 * service's own answer rather than a line written here, so what this panel
 * says and what the Raspberry Pi window says cannot drift apart. Where the
 * machine cannot be reached, `released` gives no number rather than a guess.
 */
async function showWhatThisIs() {
  const version = (await ask("/api/pi"))?.version;
  await /** @type {any} */ (document.getElementById("ask")).tell({
    icon: "Previously",
    name: PRODUCT,
    subtitle: t("about.tagline"),
    text: [
      versionAndCopyright(t("about.version", { version: released(version) })),
      t("about.made"),
    ],
    confirm: t("about.ok"),
  });
}

/**
 * The version and, on the line under it, the copyright, with whoever holds it
 * leading to their own site.
 * @param {string} versionLine - The version, as a sentence already.
 * @returns {HTMLParagraphElement}
 *
 * One paragraph with a break in it, because the two belong together and the
 * line about where the tool was made stands apart below them.
 *
 * Built here rather than handed over as a sentence, because one word in it is
 * a link and the catalogues hold words rather than markup. The name is its own
 * entry for the same reason: it is a name, so it is the same in every
 * language, and the sentence around it is not.
 */
function versionAndCopyright(versionLine) {
  const paragraph = document.createElement("p");
  const holder = document.createElement("a");
  holder.href = HOLDER_SITE;
  /* Away from this tab, because the desk behind this panel is a machine
     somebody is running and leaving it would stop nothing but would lose
     where they were. */
  holder.target = "_blank";
  holder.rel = "noopener noreferrer";
  holder.textContent = t("about.holder");

  /* This year rather than one written into the catalogues, so the line is
     current whenever it is read. */
  const copyright = t("about.copyright", { year: new Date().getFullYear() });
  const [before, after] = copyright.split("{holder}");
  paragraph.append(versionLine, document.createElement("br"),
                   before ?? "", holder, after ?? "");
  return paragraph;
}

/**
 * What a browser that has never been here is shown: the File Viewer, with the
 * panel saying what this is in front of it.
 *
 * Somebody arriving for the first time lands on a desk that says nothing about
 * itself, and the one place everything here can be reached from is the viewer.
 * Afterwards the desk is whatever they left it as, which is why this happens
 * once.
 */
function greetTheFirstVisit() {
  if (!deskIsNew()) return;
  theWindow("files")?.open();
  showWhatThisIs();
}

export {
  showWhatThisIs,
  greetTheFirstVisit,
};
