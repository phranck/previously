/* What this tool and each of its applications are, and what a browser sees the
   first time it arrives. */

import { byId, theWindow } from "./page.js";
import { ask } from "./service.js";
import { appName } from "./viewer.js";
import { released } from "./words.js";
import { NxAsk, deskIsNew } from "../nextstep.js";
import { t } from "../strings.js";

/** @typedef {import("../answers.js").ApplicationEntry} ApplicationEntry */

const PRODUCT = "Previously";

/** Where whoever holds the copyright can be read about. */
const HOLDER_SITE = "https://layered.work";

/**
 * Puts up an About panel and waits until it has been read.
 * @param {object} about
 * @param {string} about.icon - The picture, by the name showArt knows.
 * @param {string} about.name - What it is called.
 * @param {string | undefined} about.version - Its version, or nothing where
 *   it is not known, which `released` shows as no number rather than a guess.
 * @param {string} [about.subtitle] - A line under the name.
 * @param {string[]} [about.more] - Paragraphs after the version and the
 *   copyright.
 * @returns {Promise<void>}
 *
 * One shape for this tool and for every application in it, which is the shape
 * of NeXTSTEP's Info panel: the name, the icon, the version and the copyright.
 */
async function tellAbout({ icon, name, version, subtitle, more = [] }) {
  await byId("ask", NxAsk).tell({
    icon,
    name,
    subtitle,
    text: [
      versionAndCopyright(t("about.version", { version: released(version) })),
      ...more,
    ],
    confirm: t("about.ok"),
  });
}

/**
 * Says what this tool is, and waits until that has been read.
 * @returns {Promise<void>}
 *
 * The name and the icon, what the tool is for under the name, then the
 * version and the copyright, and where it was made. The version is the
 * service's own answer rather than a line written here, so what this panel
 * says and what the Raspberry Pi window says cannot drift apart.
 */
async function showWhatThisIs() {
  const version = (await ask("/api/pi"))?.version;
  await tellAbout({
    icon: "Previously",
    name: PRODUCT,
    version,
    subtitle: t("about.tagline"),
    more: [t("about.made")],
  });
}

/**
 * Says what one application is, and waits until that has been read.
 * @param {ApplicationEntry} application - An entry of the Apps folder.
 * @returns {Promise<void>}
 *
 * Its picture, what it is called in words, and its own version, which the
 * tree hands over with the rest of what describes it.
 */
function showWhatItIs(application) {
  return tellAbout({
    icon: application.icon,
    name: appName(application),
    version: application.version,
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
 * a link and the catalogs hold words rather than markup. The name is its own
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

  /* This year rather than one written into the catalogs, so the line is
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
  showWhatItIs,
  greetTheFirstVisit,
};
