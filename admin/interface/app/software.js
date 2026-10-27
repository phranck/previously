/* The software catalog: the Info window of one entry, and the Software module
   of Preferences with the form an entry is added and edited in. */

import { NxPopup } from "../nextstep.js";
import { t } from "../strings.js";
import { byId, show, theWindow } from "./page.js";
import { askPanel } from "./panels.js";
import { Software, ask, tell } from "./service.js";
import { Needs, hold, holdTheControls } from "./system.js";
import { drawMachines } from "./viewer.js";
import { say, sized } from "./words.js";

/** @typedef {import("../answers.js").SoftwareEntry} SoftwareEntry */
/** @typedef {import("../answers.js").SoftwareAnswer} SoftwareAnswer */
/** @typedef {import("../answers.js").SoftwareListed} SoftwareListed */
/** @typedef {import("../answers.js").SoftwarePackage} SoftwarePackage */
/** @typedef {import("../answers.js").PostAnswers} PostAnswers */
/** @typedef {import("../answers.js").PasswordNotGiven} PasswordNotGiven */

/** The digests an entry can be checked with, as software.DIGEST_DIGITS names
 *  them, with what they are called. Technical names, read the same in every
 *  language. */
const ALGORITHMS = [
  { value: "sha1", label: "SHA-1" },
  { value: "sha256", label: "SHA-256" },
];

/** Where the form shows each field the service can refuse, by the field's
 *  name, so a refusal can put the cursor where the mistake is. */
const FIELD_IDS = {
  name: "se-name",
  version: "se-version",
  description: "se-description",
  group: "se-group",
  kind: "se-kind",
  systems: "se-systems",
  address: "se-address",
  size: "se-size",
  algorithm: "se-algorithm",
  digest: "se-digest",
};

/** What the service last said about the catalog, or null before it has.
 *  @type {SoftwareAnswer | null} */
let catalog = null;

/** Which entry is chosen in the Software module, by its identifier.
 *  @type {string | null} */
let chosenEntry = null;

/** Which entry the form is editing, or null while it adds one.
 *  @type {string | null} */
let editing = null;

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
  show("si-kind", kindWord(about.kind));
  show("si-size", sized(about.size));
  show("si-source", about.source);
  show("si-description", about.description);

  window_.open(asker);
}

/**
 * @param {string} kind - "disc" or "file", as software.KINDS.
 * @returns {string} What that kind is called in the language being read.
 */
function kindWord(kind) {
  return kind === "disc" ? t("software.kind.disc") : t("software.kind.file");
}

/**
 * Asks the service for the catalog and draws the Software module from it,
 * which happens whenever the module is shown.
 */
async function refreshTheSoftware() {
  const answer = await ask("/api/software");
  if (answer) catalog = answer;
  show("software-note", answer ? t("preferences.pi-wide") : t("note.no-service"));
  drawTheSoftware();
}

/**
 * Draws the list of entries, and the four buttons again for the entry chosen.
 *
 * The entries come in the catalog's own order, and the shipped ones removed
 * here follow in gray, with "removed" where a version stands, so they can be
 * chosen and brought back. Nothing but Restore can be done to a removed one.
 */
function drawTheSoftware() {
  const listed = catalog?.entries ?? [];
  const gone = catalog?.removed ?? [];
  if (![...listed, ...gone].some((entry) => entry.identifier === chosenEntry)) {
    chosenEntry = null;
  }

  byId("software-list").replaceChildren(
    ...listed.map((entry) => softwareRow(entry, entry.version, false)),
    ...gone.map((entry) => softwareRow(entry, t("software.gone"), true)));

  holdTheControls();
}

/** Whether the chosen entry is a shipped one edited or removed here, which is
 *  what Restore brings back.
 *  @returns {boolean} */
function canRestore() {
  return theChosenEntry()?.origin === "changed"
    || (catalog?.removed ?? []).some((entry) => entry.identifier === chosenEntry);
}

/**
 * One row of the Software module's list.
 * @param {SoftwarePackage} entry - The entry.
 * @param {string} said - What stands at the right: its version, or that it
 *   was removed.
 * @param {boolean} gone - Whether it is a shipped entry removed here.
 * @returns {HTMLElement}
 *
 * The Installer's row, whose first column is kept free for whether a package
 * is on the card.
 */
function softwareRow(entry, said, gone) {
  const row = document.createElement("div");
  row.className = "system";
  row.classList.toggle("gone", gone);
  row.toggleAttribute("chosen", entry.identifier === chosenEntry);

  const mark = document.createElement("i");
  mark.className = "system-mark";
  const name = document.createElement("span");
  name.textContent = entry.name;
  const right = document.createElement("span");
  right.className = "system-cost";
  right.textContent = said;

  row.append(mark, name, right);
  row.addEventListener("click", () => {
    chosenEntry = entry.identifier;
    drawTheSoftware();
  });
  return row;
}

/**
 * Says what came of a change to the catalog, and draws what it left.
 * @param {PostAnswers[typeof Software[keyof typeof Software]] | PasswordNotGiven | null} answer
 *   - What the service said, or null without contact.
 *
 * Every answer of these routes carries the catalog as it now stands, so the
 * list is drawn from that rather than asked for again. The File Viewer's
 * Software folder follows, because it shows the same catalog.
 */
function reportAboutTheSoftware(answer) {
  show("software-note", answer === null ? t("note.no-service") : say(answer));
  if (answer && "entries" in answer) catalog = answer;
  drawTheSoftware();
  drawMachines();
}

/** The entry chosen in the list, or undefined where none is.
 *  @returns {SoftwareListed | undefined} */
function theChosenEntry() {
  return catalog?.entries.find((entry) => entry.identifier === chosenEntry);
}

/**
 * Removes the chosen entry, once the panel has been answered.
 *
 * The panel says what removing costs: a shipped entry can be brought back
 * with Restore, and one added here is gone for good.
 */
async function removeTheChosenEntry() {
  const entry = theChosenEntry();
  if (!entry) return;
  const sure = await askPanel({
    name: t("ask.remove.title", { name: entry.name }),
    text: [t(entry.origin === "added" ? "ask.remove-software.added" : "ask.remove-software.shipped")],
    icon: entry.kind === "disc" ? "cdrom" : "defaultIcon",
    confirm: t("button.remove"),
  });
  if (!sure) return;
  reportAboutTheSoftware(await tell(Software.Remove, { entry: entry.identifier }));
}

/**
 * Brings the chosen shipped entry back as it was shipped.
 *
 * One that was edited here loses those edits, so the panel asks first. One
 * that was removed loses nothing and comes straight back.
 */
async function restoreTheChosenEntry() {
  const identifier = chosenEntry;
  if (identifier === null) return;
  const edited = theChosenEntry();
  if (edited) {
    const sure = await askPanel({
      name: t("ask.restore-software.title", { name: edited.name }),
      text: [t("ask.restore-software.loss")],
      icon: edited.kind === "disc" ? "cdrom" : "defaultIcon",
      confirm: t("button.restore"),
    });
    if (!sure) return;
  }
  reportAboutTheSoftware(await tell(Software.Restore, { entry: identifier }));
}

/**
 * Opens the form on an entry, or empty to add one.
 * @param {SoftwareListed | null} entry - What to edit, or null.
 *
 * A new entry starts for the system the machine boots, as a CD image checked
 * with SHA-1, which is what archive.org states for every file it holds.
 */
function openTheForm(entry) {
  const window_ = theWindow("software-entry");
  if (!window_ || !catalog) return;
  editing = entry?.identifier ?? null;

  value("se-name", entry?.name ?? "");
  value("se-version", entry?.version ?? "");
  value("se-description", entry?.description ?? "");
  value("se-address", entry?.address ?? "");
  value("se-size", entry ? String(entry.size) : "");
  value("se-digest", entry?.digest ?? "");

  byId("se-group", NxPopup).offer(
    catalog.groups.map((group) => ({ value: group.identifier, label: group.name })),
    entry?.group);
  byId("se-algorithm", NxPopup).offer(ALGORITHMS, entry?.algorithm);
  for (const radio of byId("se-kind").querySelectorAll("input")) {
    radio.checked = radio.value === (entry?.kind ?? "disc");
  }
  drawTheSystems(entry ? entry.systems : (catalog.booted ? [catalog.booted] : []));

  show("se-note", "");
  window_.open();
  byId("se-name", HTMLInputElement).focus();
}

/**
 * Writes a value into one of the form's fields.
 * @param {string} id - The field.
 * @param {string} text - What it holds.
 */
function value(id, text) {
  const field = byId(id);
  if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
    field.value = text;
  }
}

/**
 * Draws a switch for every system an entry can be for.
 * @param {string[]} chosen - The identifiers that are switched on.
 */
function drawTheSystems(chosen) {
  byId("se-systems").replaceChildren(...(catalog?.systems ?? []).map((system) => {
    const label = document.createElement("label");
    label.className = "two-state";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.className = "switch";
    box.value = system.identifier;
    box.checked = chosen.includes(system.identifier);
    const words = document.createElement("span");
    words.textContent = system.name;
    label.append(box, words);
    return label;
  }));
}

/**
 * What the form holds, as the service takes an entry.
 * @returns {Record<string, string | number | string[]>}
 *
 * The size goes as a number where it is a whole one, and as it was typed
 * otherwise, so the service refuses it beside its field rather than this page
 * deciding what was meant.
 */
function whatTheFormHolds() {
  const typed = (/** @type {string} */ id) => {
    const field = byId(id);
    return field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement
      ? field.value : "";
  };
  const size = typed("se-size").trim();
  const checked = (/** @type {string} */ id) => [...byId(id).querySelectorAll("input")]
    .filter((input) => input.checked).map((input) => input.value);
  return {
    name: typed("se-name"),
    version: typed("se-version").trim(),
    description: typed("se-description"),
    group: byId("se-group", NxPopup).value,
    kind: checked("se-kind")[0] ?? "",
    systems: checked("se-systems"),
    address: typed("se-address").trim(),
    size: /^\d+$/.test(size) ? Number(size) : size,
    algorithm: byId("se-algorithm", NxPopup).value,
    digest: typed("se-digest").trim().toLowerCase(),
  };
}

/**
 * Enters what the form holds.
 *
 * Kept, the form goes and the list shows the entry. Refused, the form stays
 * with the reason under it and the cursor in the first field that was wrong,
 * its text selected so it can be typed over, which is how the Controls chapter
 * has a text field reject a wrong entry.
 */
async function saveTheForm() {
  const before = new Set((catalog?.entries ?? []).map((entry) => entry.identifier));
  const answer = await tell(Software.Keep, { entry: whatTheFormHolds(), replacing: editing });
  if (answer && "entries" in answer && answer.ok) {
    theWindow("software-entry")?.close();
    /* The entry just written is the one chosen afterwards. An added one is
       named by the service, so it is the one the list did not hold before. */
    chosenEntry = editing
      ?? answer.entries.find((entry) => !before.has(entry.identifier))?.identifier
      ?? chosenEntry;
    reportAboutTheSoftware(answer);
    return;
  }
  show("se-note", answer === null ? t("note.no-service") : say(answer));
  if (answer && "entries" in answer) catalog = answer;
  if (answer && "reason" in answer && answer.reason === "software.refused") {
    pointAt(answer.fields[0]);
  }
}

/**
 * Puts the cursor into a field the service refused.
 * @param {string | undefined} field - Its name, as the service gives it.
 */
function pointAt(field) {
  const id = field ? FIELD_IDS[/** @type {keyof typeof FIELD_IDS} */ (field)] : undefined;
  if (!id) return;
  const place = byId(id);
  const target = place instanceof HTMLInputElement || place instanceof HTMLTextAreaElement
    ? place : place.querySelector("input, button");
  if (!(target instanceof HTMLElement)) return;
  target.focus();
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) target.select();
}

/**
 * Wires the Software module and its form.
 *
 * Return in a one-line field goes to the next field, as it does in a form,
 * and Save is what enters the entry.
 */
function wireTheSoftware() {
  /* The catalog touches neither the machine nor the board, so these need
     contact with the service and nothing more, as keeping a configuration
     does. */
  hold("#software-restore", Needs.Contact, canRestore);
  hold("#software-remove", Needs.Contact, () => Boolean(theChosenEntry()));
  hold("#software-edit", Needs.Contact, () => Boolean(theChosenEntry()));
  hold("#software-add", Needs.Contact, () => catalog !== null);
  hold("#se-save", Needs.Contact);

  byId("software-add").addEventListener("click", () => openTheForm(null));
  byId("software-edit").addEventListener("click", () => openTheForm(theChosenEntry() ?? null));
  byId("software-remove").addEventListener("click", removeTheChosenEntry);
  byId("software-restore").addEventListener("click", restoreTheChosenEntry);
  byId("se-save").addEventListener("click", saveTheForm);
  byId("se-cancel").addEventListener("click", () => theWindow("software-entry")?.close());

  const form = byId("software-form");
  form.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || !(event.target instanceof HTMLInputElement)) return;
    event.preventDefault();
    const fields = [...form.querySelectorAll("input.entry, textarea.entry")];
    const next = fields[fields.indexOf(event.target) + 1];
    if (next instanceof HTMLElement) next.focus();
  });
  drawTheSoftware();
}

export { drawTheSoftware, refreshTheSoftware, showSoftwareInfo, wireTheSoftware };
