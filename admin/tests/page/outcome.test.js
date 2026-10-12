/**
 * What the page does with an answer that refuses, on the page's own markup.
 *
 * A POST is answered by `tell` with whatever body came back, and a refusal is
 * a body with `error` and nothing else. Drawn as a status it reads as a
 * machine that has stopped, and waited on as a board that is going away it
 * holds every control until the page is reloaded.
 *
 * Every POST here is refused, and the status the page asks for afterwards
 * never comes, so what the refusal itself drew is what stays on the page to be
 * read.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, never, settled } from "./page.js";

/** A machine that is running, as /api/status describes one. */
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

answering(async (route, options) => (options?.method === "POST"
  ? json({ error: "unreadable request" }, 400)
  : never()));

const status = await import("../../interface/app/status.js");
const service = await import("../../interface/app/service.js");
const board = await import("../../interface/app/board.js");

test("a refused operation leaves the status that was drawn", async () => {
  layThePage();
  status.drawStatus(RUNNING);
  const before = document.getElementById("info-state").textContent;

  await service.operate(service.Kiosk.Start, "switching on");

  assert.equal(document.getElementById("info-state").textContent, before);
});

test("a refused restart of the board ends what the page waits for", async () => {
  layThePage();
  status.drawStatus(RUNNING);
  board.wireBoard();

  document.getElementById("pi-reboot").click();
  await settled();
  document.querySelector('#ask [data-answer="yes"]').click();
  await settled();

  const busy = [...document.querySelectorAll(".busy")].map((line) => line.textContent);
  assert.deepEqual(busy.filter(Boolean), []);
});
