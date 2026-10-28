/* The software catalog: the Info window of one entry, and the Software module
   of Preferences with the form an entry is added and edited in. */

import { NxPopup } from "../nextstep.js";
import { t } from "../strings.js";
import { wearCover } from "./covers.js";
import { byId, show, theWindow } from "./page.js";
import { askPanel } from "./panels.js";
import { Software, ask, tell } from "./service.js";
import { Needs, allowed, hold, holdTheControls } from "./system.js";
import { drawMachines } from "./viewer.js";
import { NOTHING, say, sized } from "./words.js";

/** @typedef {import("../answers.js").SoftwareEntry} SoftwareEntry */
/** @typedef {import("../answers.js").SoftwareAnswer} SoftwareAnswer */
/** @typedef {import("../answers.js").SoftwareListed} SoftwareListed */
/** @typedef {import("../answers.js").SoftwarePackage} SoftwarePackage */
/** @typedef {import("../answers.js").PostAnswers} PostAnswers */
/** @typedef {import("../answers.js").PasswordNotGiven} PasswordNotGiven */
/** @typedef {import("../answers.js").LookupFile} LookupFile */
/** @typedef {import("../answers.js").ToldValues["lookup.found"]} LookupFound */

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

/** The cover the form holds, by its address on archive.org, or "" for none.
 *  The form cannot write another address, only keep this one or drop it. */
let formCover = "";

/** Where the form's picture of that cover is: the route of a kept entry, or
 *  the thumbnail a lookup handed along before the entry is kept.
 *  @type {string | null} */
let formPicture = null;

/** The archive.org page the entry in the form came from, or "" for none. The
 *  service reads it from the download address, so the form only shows it. */
let formPage = "";

/** The page of the entry the Info window shows, or "" for none. */
let infoPage = "";

/**
 * Opens an entry's page on archive.org in a window of its own.
 * @param {string} page - The page.
 *
 * With `noopener`, so the page that opens cannot reach back into this one.
 * The button stands in both windows whether or not an entry has a page, and
 * is disabled where it has none, because the Controls chapter keeps a button
 * that would do nothing in its place and disables it. Disabled, the kit greys
 * its label.
 */
function viewOrigin(page) {
  if (page) window.open(page, "_blank", "noopener");
}

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
  const portrait = byId("si-icon");
  wearCover(portrait, about.picture, entry.icon,
            () => wearCover(portrait, about.picture, entry.icon, () => {}));
  show("si-version", about.version || NOTHING);
  show("si-for", about.for.join(", "));
  show("si-kind", kindWord(about.kind));
  show("si-size", sized(about.size));
  show("si-source", about.source);
  show("si-description", about.description);
  infoPage = about.page;
  byId("si-page", HTMLButtonElement).disabled = !infoPage;

  window_.open(asker);
}

/**
 * @param {string} kind - "disc" or "file", as software.KINDS.
 * @returns {string} The icon an entry of that kind wears without a cover: the
 *   compact disc for a CD image, and the sheet the Workspace drew for a file
 *   it knew nothing about otherwise, as the File Viewer has them.
 */
function iconOf(kind) {
  return kind === "disc" ? "cdrom" : "defaultIcon";
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
  const cover = document.createElement("i");
  cover.className = "art software-cover";
  wearCover(cover, entry.picture, iconOf(entry.kind), drawTheSoftware);
  const name = document.createElement("span");
  name.textContent = entry.name;
  const right = document.createElement("span");
  right.className = "system-cost";
  right.textContent = said;

  row.append(mark, cover, name, right);
  row.addEventListener("click", () => {
    chosenEntry = entry.identifier;
    drawTheSoftware();
  });
  /* A double click does what Edit does, which is what a double click in a
     selection list does: the chosen row's own action. A shipped entry removed
     here cannot be edited, so it opens nothing. */
  row.addEventListener("dblclick", () => {
    if (gone || !allowed(Needs.Contact, "software-note")) return;
    chosenEntry = entry.identifier;
    openTheForm(theChosenEntry() ?? null);
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
    icon: iconOf(entry.kind),
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
      icon: iconOf(edited.kind),
      confirm: t("button.restore"),
    });
    if (!sure) return;
  }
  reportAboutTheSoftware(await tell(Software.Restore, { entry: identifier }));
}

/**
 * Opens the form on an entry, or on a new one.
 * @param {SoftwareListed | null} entry - What to edit, or null to add one.
 * @param {LookupFound | null} [found] - What a lookup found for a new one: the
 *   fields it fills, the item's page, and the cover shown before the entry is
 *   kept. Null starts an empty one.
 * @param {LookupFile[] | null} [files] - The files of the item the lookup read,
 *   offered in the File row, or null where there is nothing to choose.
 * @param {string | null} [chosenFile] - The address of the file filled in.
 *
 * A new entry starts for the system the machine boots.
 */
function openTheForm(entry, found = null, files = null, chosenFile = null) {
  const window_ = theWindow("software-entry");
  if (!window_ || !catalog) return;
  editing = entry?.identifier ?? null;

  value("se-version", entry?.version ?? "");
  fill(entry ?? found?.fields ?? {});
  showTheCover(entry ? entry.cover : found?.fields.cover, entry ? entry.picture : found?.picture);
  formPage = (entry ? entry.page : found?.page) ?? "";
  byId("se-page", HTMLButtonElement).disabled = !formPage;
  byId("se-group", NxPopup).offer(
    catalog.groups.map((group) => ({ value: group.identifier, label: group.name })),
    entry?.group);
  drawTheSystems(entry ? entry.systems : (catalog.booted ? [catalog.booted] : []));

  byId("se-file-row").hidden = !files;
  if (files) {
    byId("se-file", NxPopup).offer(
      files.map((file) => ({ value: file.address, label: file.name })), chosenFile);
  }

  show("se-note", "");
  window_.open();
  byId("se-name", HTMLInputElement).focus();
}


/**
 * Writes the fields an address can fill into the form, and empties those it
 * says nothing about.
 * @param {Partial<SoftwarePackage>} source - An entry, or what a lookup filled.
 *
 * A CD image checked with SHA-1 where nothing says otherwise, which is what
 * archive.org states for every file it holds. A field the source leaves out
 * is emptied rather than kept, because choosing another file of an item must
 * not leave the size of the one before beside the name of this one.
 */
function fill(source) {
  value("se-name", source.name ?? "");
  value("se-description", source.description ?? "");
  value("se-address", source.address ?? "");
  value("se-size", source.size === undefined ? "" : String(source.size));
  value("se-digest", source.digest ?? "");
  byId("se-algorithm", NxPopup).offer(ALGORITHMS, source.algorithm);
  for (const radio of byId("se-kind").querySelectorAll("input")) {
    radio.checked = radio.value === (source.kind ?? "disc");
  }
}


/**
 * Shows the cover the form holds, with the switch that drops it.
 * @param {string | null | undefined} address - The cover's address on
 *   archive.org, or nothing.
 * @param {string | null | undefined} picture - Where its picture is shown
 *   from.
 *
 * The switch is there only where there is a cover to keep or drop, because
 * the form writes no cover of its own. The picture above it is always there,
 * as what the entry will wear.
 */
function showTheCover(address, picture) {
  formCover = address ?? "";
  formPicture = picture ?? null;
  byId("se-cover-switch").hidden = !formCover;
  byId("se-cover", HTMLInputElement).checked = Boolean(formCover);
  drawTheCoverPicture();
}

/** Draws the form's cover, or the icon of the kind chosen where the switch
 *  is off, which is what the entry will wear. */
function drawTheCoverPicture() {
  const shown = byId("se-cover", HTMLInputElement).checked ? formPicture : null;
  const radio = byId("se-kind").querySelector("input:checked");
  const icon = iconOf(radio instanceof HTMLInputElement ? radio.value : "disc");
  wearCover(byId("se-cover-art"), shown, icon, drawTheCoverPicture);
}

/**
 * Reads an address into a new entry and opens the form on it.
 * @param {string} address - What was dropped on the list.
 *
 * Where the address names an item holding several files, the form opens on
 * the CD image among them, or on the largest where there is none, with the
 * others offered above the name. What archive.org could not say is left for
 * whoever adds the entry, and Save is what keeps it.
 */
async function lookUp(address) {
  if (!allowed(Needs.Contact, "software-note")) return;
  const answer = await tell(Software.Lookup, { address });
  if (!answer || !("reason" in answer) || !answer.ok) {
    show("software-note", answer === null ? t("note.no-service") : say(answer));
    return;
  }
  if (answer.reason === "lookup.found") {
    openTheForm(null, answer);
    show("se-note", say(answer));
    return;
  }
  const files = answer.files;
  const chosen = files.find((file) => file.kind === "disc")
    ?? [...files].sort((one, other) => (other.size ?? 0) - (one.size ?? 0))[0];
  const found = await tell(Software.Lookup, { address: chosen.address });
  if (!found || !("reason" in found) || !found.ok || found.reason !== "lookup.found") {
    show("software-note", found === null ? t("note.no-service") : say(found));
    return;
  }
  openTheForm(null, found, files, chosen.address);
  show("se-note", say(answer));
}

/**
 * Fills the form again for another file of the same item.
 * @param {string} address - The file chosen in the File pop-up list.
 */
async function lookUpAnotherFile(address) {
  const found = await tell(Software.Lookup, { address });
  show("se-note", found === null ? t("note.no-service") : say(found));
  if (found && "reason" in found && found.ok && found.reason === "lookup.found") {
    fill(found.fields);
    showTheCover(found.fields.cover, found.picture);
  }
}

/**
 * The address a drop carries.
 * @param {DataTransfer | null} carried - What was dropped.
 * @returns {string} The first address of its list, or "" where it holds none.
 *
 * Read from `text/uri-list` alone, the form a browser hands an address in.
 * The interface's own drags carry `text/plain`, so a machine or a folder
 * dragged over from the File Viewer is not taken for an address.
 */
function addressIn(carried) {
  const lines = (carried?.getData("text/uri-list") ?? "").split(/\r?\n/);
  return lines.map((line) => line.trim()).find((line) => line && !line.startsWith("#")) ?? "";
}

/**
 * Makes the package list take a dropped address.
 *
 * While an address is over it, the list says it will take it, which is the
 * receiving green and its running edge in app.css. A drop is kept from the
 * browser, which would otherwise leave the page for the address.
 */
function wireTheDrop() {
  const target = document.querySelector("nx-window[name='preferences'] nx-scroller.packages");
  if (!(target instanceof HTMLElement)) return;
  const carriesAnAddress = (/** @type {DragEvent} */ event) =>
    [...(event.dataTransfer?.types ?? [])].includes("text/uri-list");

  target.addEventListener("dragover", (event) => {
    if (!carriesAnAddress(event)) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    target.toggleAttribute("droppable", true);
  });
  target.addEventListener("dragleave", (event) => {
    if (event.relatedTarget instanceof Node && target.contains(event.relatedTarget)) return;
    target.toggleAttribute("droppable", false);
  });
  target.addEventListener("drop", (event) => {
    if (!carriesAnAddress(event)) return;
    event.preventDefault();
    target.toggleAttribute("droppable", false);
    const address = addressIn(event.dataTransfer);
    if (address) lookUp(address);
  });
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
    cover: byId("se-cover", HTMLInputElement).checked ? formCover : "",
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
  byId("se-page").addEventListener("click", () => viewOrigin(formPage));
  byId("si-page").addEventListener("click", () => viewOrigin(infoPage));
  byId("se-file").addEventListener("nx-pick", (event) => {
    if (event instanceof CustomEvent) lookUpAnotherFile(event.detail.value);
  });
  /* What the entry will wear follows the switch and the kind at once. */
  byId("se-cover").addEventListener("change", drawTheCoverPicture);
  byId("se-kind").addEventListener("change", drawTheCoverPicture);
  wireTheDrop();

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
