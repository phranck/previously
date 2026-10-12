/**
 * What the page does with an answer that refuses, on the page's own markup.
 *
 * A POST is answered by `tell` with whatever body came back, and a refusal is
 * a body with `error` and nothing else. Drawn as a status it reads as a
 * machine that has stopped, and waited on as a board that is going away it
 * holds every control until the page is reloaded.
 *
 * The service is the page's `fetch`, answered here: a POST is refused, and the
 * status the page asks for afterwards never comes, so what the refusal itself
 * drew is what stays on the page to be read.
 */
import { after, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

import { lay } from "../kit/desk.js";

/* What the page leaves running, such as the timeout a POST is sent with, would
   keep the run going until it fires. Taking the window down clears it. */
after(() => GlobalRegistrator.unregister());

/** The page's own markup, the body of interface/index.html without its
 *  scripts: the modules under test are imported here, and happy-dom refuses
 *  to load a script file. */
const markup = readFileSync(new URL("../../interface/index.html", import.meta.url), "utf-8")
  .split("<body>")[1].split("</body>")[0]
  .replace(/<script\b[\s\S]*?<\/script>/g, "");

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

/** Every POST is refused as the service refuses one, and every GET waits for
 *  ever, so nothing after the refusal draws over what it drew. */
globalThis.fetch = async (route, options) => {
  if (options?.method === "POST") {
    return new Response(JSON.stringify({ error: "unreadable request" }),
                        { status: 400, headers: { "Content-Type": "application/json" } });
  }
  return new Promise(() => {});
};

/** @returns {Promise<void>} Once everything already started has run. */
function settled() {
  return new Promise((resolve) => setTimeout(resolve, 20));
}

const status = await import("../../interface/app/status.js");
const service = await import("../../interface/app/service.js");
const board = await import("../../interface/app/board.js");

test("a refused operation leaves the status that was drawn", async () => {
  lay(markup);
  status.drawStatus(RUNNING);
  const before = document.getElementById("info-state").textContent;

  await service.operate(service.Kiosk.Start, "switching on");

  assert.equal(document.getElementById("info-state").textContent, before);
});

test("a refused restart of the board ends what the page waits for", async () => {
  lay(markup);
  status.drawStatus(RUNNING);
  board.wireBoard();

  document.getElementById("pi-reboot").click();
  await settled();
  document.querySelector('#ask [data-answer="yes"]').click();
  await settled();

  const busy = [...document.querySelectorAll(".busy")].map((line) => line.textContent);
  assert.deepEqual(busy.filter(Boolean), []);
});
