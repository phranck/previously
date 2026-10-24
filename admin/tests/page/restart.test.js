/**
 * How long the page waits for a restart of the board, on the page's own markup.
 *
 * The page asks for the status every five seconds without a time limit, and a
 * request that falls into the restart waits until the board answers again and
 * then comes back like any other. Asked that way of next5 on 24.10.2026, all
 * thirty requests across a restart came back with 200 and none failed. So the
 * page never sees the board gone, and what tells it the board is back is a
 * status from another boot.
 *
 * The restart is taken, the status the page asks for afterwards never comes,
 * and each test hands the page the statuses it wants it to have heard.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, never, settled } from "./page.js";

/** A machine that is running, as /api/status describes one, on one boot. */
const RUNNING = {
  running: true,
  held: false,
  console_active: true,
  uptime_seconds: 60,
  boot: "6f1c2a4e-0b8d-4c7e-9a51-3d2f8e7b6c10",
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
  ? json({ ok: true, reason: "board.on-its-way", action: "reboot" })
  : never()));

const status = await import("../../interface/app/status.js");
const board = await import("../../interface/app/board.js");
const system = await import("../../interface/app/system.js");

/** @returns {string[]} What the busy lines say, without the empty ones. */
function busy() {
  return [...document.querySelectorAll(".busy")].map((line) => line.textContent)
    .filter(Boolean);
}

/** Restarts the board from the Raspberry Pi window, as somebody would, on a
 *  page with nothing under way. The system's state outlives one test, because
 *  the module holding it is imported once. */
async function restart() {
  system.end();
  document.getElementById("pi-reboot").click();
  await settled();
  document.querySelector('#ask [data-answer="yes"]').click();
  await settled();
}

test("a restart lasts while the board answers from the boot it was asked on", async () => {
  layThePage();
  status.drawStatus(RUNNING);
  board.wireBoard();

  await restart();
  status.drawStatus(RUNNING);

  assert.notDeepEqual(busy(), []);
});

test("a restart is over when the board answers from another boot, though no status failed", async () => {
  layThePage();
  status.drawStatus(RUNNING);
  board.wireBoard();

  await restart();
  status.drawStatus(RUNNING);
  status.drawStatus({ ...RUNNING, boot: "9a0d5e3b-7c21-4f86-b4e2-1c8a6d0f5e97" });

  assert.deepEqual(busy(), []);
});
