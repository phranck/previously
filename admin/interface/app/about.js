/* What this tool is, and what a browser sees the first time it arrives. */

import { deskIsNew } from "../nextstep.js";
import { t } from "../strings.js";
import { ask } from "./service.js";
import { NOTHING } from "./words.js";

const PRODUCT = "Previously";

/** Where whoever holds the copyright can be read about. */
const HOLDER_SITE = "https://layered.work";

/**
 * Says what this tool is, and waits until that has been read.
 * @returns {Promise<void>}
 *
 * NeXTSTEP's Info panel holds the name, the icon, the copyright and the
 * version, and nothing else at all. The version is the service's own answer
 * rather than a line written here, so what this panel says and what the
 * Raspberry Pi window says cannot drift apart. A machine that cannot be
 * reached leaves that line out rather than guessing at it.
 */
async function showWhatThisIs() {
  const version = (await ask("/api/pi"))?.version;
  await document.getElementById("ask").tell({
    icon: "Previously",
    text: [
      PRODUCT,
      t("about.version", { version: version ?? NOTHING }),
      copyrightLine(),
    ],
    confirm: t("about.ok"),
  });
}

/**
 * The copyright, with whoever holds it leading to their own site.
 * @returns {HTMLParagraphElement}
 *
 * Built here rather than handed over as a sentence, because one word in it is
 * a link and the catalogues hold words rather than markup. The name is its own
 * entry for the same reason: it is a name, so it is the same in every
 * language, and the sentence around it is not.
 */
function copyrightLine() {
  const paragraph = document.createElement("p");
  const holder = document.createElement("a");
  holder.href = HOLDER_SITE;
  /* Away from this tab, because the desk behind this panel is a machine
     somebody is running and leaving it would stop nothing but would lose
     where they were. */
  holder.target = "_blank";
  holder.rel = "noopener noreferrer";
  holder.textContent = t("about.holder");

  const [before, after] = t("about.copyright").split("{holder}");
  paragraph.append(before ?? "", holder, after ?? "");
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
  document.querySelector('nx-window[name="files"]')?.open();
  showWhatThisIs();
}

export {
  showWhatThisIs,
  greetTheFirstVisit,
};
