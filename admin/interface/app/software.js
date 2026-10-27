/* The Info window of one piece of software in the Software folder. */

import { t } from "../strings.js";
import { byId, show, theWindow } from "./page.js";
import { sized } from "./words.js";

/** @typedef {import("../answers.js").SoftwareEntry} SoftwareEntry */

/**
 * Shows what one piece of software is, in the window kept for that.
 * @param {SoftwareEntry} entry - What was double clicked in the Software folder.
 * @param {Element} [asker] - The thing that was opened, which is where the
 *   window starts from.
 *
 * Its name, version and description stand as the catalog has them, in the one
 * language they were written in. Only the labels beside them and the word for
 * its kind are this interface's, because those are the page talking rather
 * than the software.
 */
function showSoftwareInfo(entry, asker) {
  const window_ = theWindow("software-info");
  if (!window_) return;

  const about = entry.package;
  window_.rename(about.name);
  show("si-caption", about.name);
  byId("si-icon").style.backgroundImage = `var(--${entry.icon})`;
  show("si-version", about.version);
  show("si-for", about.for.join(", "));
  show("si-kind", about.kind === "disc" ? t("software.kind.disc") : t("software.kind.file"));
  show("si-size", sized(about.size));
  show("si-source", about.source);
  show("si-description", about.description);

  window_.open(asker);
}

export { showSoftwareInfo };
