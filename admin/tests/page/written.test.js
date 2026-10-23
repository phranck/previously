/**
 * What the Info window says about a configuration changed outside Previously.
 *
 * The service compares the file with its note of what Previously wrote last
 * and answers `written_by_us`. Where that is false, the file was changed by
 * hand or saved from Previous's own dialog behind F12, and the window says
 * what that means: such a change may not be adjustable here.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, layThePage, never } from "./page.js";

/** A machine that is running, as /api/status describes one, with the file as
 *  Previously wrote it. */
const RUNNING = {
  running: true,
  held: false,
  console_active: true,
  uptime_seconds: 60,
  file: { changed_at: 1791800000, newer_than_the_machine: false, written_by_us: true },
  ready: { emulator: true, system: true, configuration: true, set_up: true },
  configuration: {
    kind: 1, model: "NeXTcube", enclosure: "cube", turbo: true, colour: false,
    dimension: false, cpu: "68040", mhz: 33, memory_mb: 64, banks: [16, 16, 16, 16],
    rtc: "MCCS1850", scsi: "NCR53C90A", nbic: true, disk: "NeXTSTEP-3.3.dsk",
    catalogue: "nextcube-turbo",
  },
};

/** The same machine, with the file changed outside Previously. */
const CHANGED_OUTSIDE = { ...RUNNING, file: { ...RUNNING.file, written_by_us: false } };

answering(async () => never());

const status = await import("../../interface/app/status.js");
const { t } = await import("../../interface/strings.js");

/** @returns {string} What the note under the file's readings says. */
function fileNote() {
  return document.getElementById("file-note")?.textContent ?? "";
}

test("a file changed outside Previously is said to be so", () => {
  layThePage();

  status.drawStatus(CHANGED_OUTSIDE);

  assert.equal(fileNote(), t("note.changed-outside"));
  assert.notEqual(fileNote(), "");
});

test("a file Previously wrote says nothing", () => {
  layThePage();

  status.drawStatus(RUNNING);

  assert.equal(fileNote(), "");
});

test("the note goes once Previously has written the file again", () => {
  layThePage();
  status.drawStatus(CHANGED_OUTSIDE);

  status.drawStatus(RUNNING);

  assert.equal(fileNote(), "");
});

test("a configuration that cannot be read says nothing about who wrote it", () => {
  layThePage();
  status.drawStatus(CHANGED_OUTSIDE);

  status.drawStatus({ ...CHANGED_OUTSIDE, configuration: null });

  assert.equal(fileNote(), "");
});
