/**
 * What the Config Editor draws from an answer, and what it asks when somebody
 * presses faster than the Pi answers.
 *
 * Every press asks the service what the machine is now, and the window is
 * drawn again only once it says. A second press before that answer builds on
 * the first, so a bank pressed twice moves on two sizes and a board pressed
 * twice is back where it was, as two presses on the machine itself would be.
 *
 * A NeXTdimension board that is in gets a group of its own for its memory,
 * built before it is on the page, and the rest of the window is drawn after it.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, never, settled } from "./page.js";

/** A NeXTcube with neither board, as GET /api/machine/settled answers for it.
 *  Its third bank is empty and takes 1, 4 and 16 MB. */
const NEXTCUBE = {
  configuration: {
    kind: 1, turbo: false, mhz: 25, colour: false, dimensions: [0, 0, 0],
    banks: [4, 4, 0, 0], dsp: "plain", dsp_memory: 96, floppy: false,
    optical: true, ethernet: true, socket: "thin-wire", printer: false,
  },
  machine: {
    kind: 1, model: "NeXTcube", enclosure: "cube", turbo: false, colour: false,
    dimension: false, cpu: "68040", mhz: 25, memory_mb: 8, banks: [4, 4, 0, 0],
    rtc: "MC68HC68T1", scsi: "NCR53C90A", nbic: true,
  },
  offers: {
    kinds: [
      { kind: 0, model: "NeXT Computer" },
      { kind: 1, model: "NeXTcube" },
      { kind: 2, model: "NeXTstation" },
    ],
    turbo: true, colour: false, dimension_slots: [2, 4, 6],
    dimension_memory: [4, 16, 32, 64], clocks: [16, 20, 25, 33],
    memory: [8, 16, 32, 64],
    banks: [[4, 16], [0, 1, 4, 16], [0, 1, 4, 16], [0, 1, 4, 16]],
    dsps: ["none", "plain", "with-rom"], dsp_memory: [24, 96],
    floppy: true, optical: true, ethernet: true, printer: true,
    sockets: ["thin-wire", "twisted-pair"],
  },
};

/** The same NeXTcube with a board of 32 MB in its first NeXTdimension slot. */
const WITH_A_BOARD = {
  ...NEXTCUBE,
  configuration: { ...NEXTCUBE.configuration, dimensions: [32, 0, 0] },
  machine: { ...NEXTCUBE.machine, dimension: true },
};

answering(() => never());

const editor = await import("../../interface/app/editor.js");
const { t } = await import("../../interface/strings.js");

/**
 * Opens the editor on a NeXTcube, answers its first question, and from then
 * on writes down every question and answers none.
 * @param {object} [answer] - What the service settles the machine as.
 * @returns {Promise<URLSearchParams[]>} What each later question asked, filled
 *   in as they are asked.
 */
async function openWithoutFurtherAnswers(answer = NEXTCUBE) {
  layThePage();
  /** @type {URLSearchParams[]} */
  const asked = [];
  let answered = false;
  answering((route) => {
    if (!answered) {
      answered = true;
      return Promise.resolve(json(answer));
    }
    asked.push(new URL(route, "http://next.local").searchParams);
    return never();
  });
  /* As the File Viewer hands the machine over. */
  editor.editConfiguration({
    kind: "machine", set: "system", id: "nextcube", name: "NeXTcube",
    path: "/Machines/System/NeXTcube", configuration: answer.configuration,
  });
  await settled();
  return asked;
}

test("a bank pressed twice before the answer moves on two sizes", async () => {
  const asked = await openWithoutFurtherAnswers();
  const third = document.querySelectorAll("#editor-banks .bank")[2];

  third.click();
  third.click();

  assert.equal(asked.length, 2);
  assert.equal(asked[1].get("banks"), "4,4,4,0");
  /* A bank chosen on its own lets the total go, so the service adds it up. */
  assert.equal(asked[1].get("memory"), null);
});

test("a board pressed twice before the answer is back where it was", async () => {
  const asked = await openWithoutFurtherAnswers();
  const [turbo] = document.querySelectorAll("#editor-boards .choice");

  turbo.click();
  turbo.click();

  assert.equal(asked.length, 2);
  assert.equal(asked[0].get("turbo"), "1");
  assert.equal(asked[1].get("turbo"), "0");
});

test("a machine with a NeXTdimension board is drawn whole", async () => {
  await openWithoutFurtherAnswers(WITH_A_BOARD);
  const memory = document.querySelector("#editor-dimension-memory nx-slider");

  assert.ok(memory, "the board has no group for its memory");
  assert.deepEqual([...memory.querySelectorAll(".tick[chosen]")].map((tick) => tick.textContent),
                   ["32"]);
  /* What saving will do is drawn after the boards, so it is what a fault in
     them leaves undone. */
  assert.equal(document.getElementById("editor-note").textContent,
               t("editor.into-a-new-one"));
});
