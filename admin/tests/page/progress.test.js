/**
 * What the Installer and the update say about a request the helper refused
 * before its first step.
 *
 * Such a record is finished and failed and names no step, because none was
 * reached. A window that names the step it stopped at then names `null`, and
 * what reaches the screen is the key `setup.step.null`.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, layThePage, never } from "./page.js";

/** A request refused before its first step: nobody owns the console, as
 *  setup.main writes it. */
const REFUSED = {
  do: "update-tool", system: null, machine: "nextcube-turbo", started_at: 1791800000,
  done: 0, of: 3, undone: [], changed: [], part: null,
  finished_at: 1791800001, ok: false, step: null,
  failed: { reason: "setup.no-owner" },
};

answering(() => never());

const installer = await import("../../interface/app/installer.js");
const update = await import("../../interface/app/update.js");
const { t } = await import("../../interface/strings.js");

test("the Installer says a refused request was not started", () => {
  layThePage();

  installer.drawTheInstaller({
    systems: [], default: "nextstep-3.3", needs: 0, room: null,
    emulator: { here: true, version: "4.3", newest: "4.3", newer: false },
    progress: { ...REFUSED, do: "install" },
  });

  assert.equal(document.getElementById("installer-caption").textContent,
               t("installer.not-started"));
  assert.equal(document.getElementById("installer-note").textContent,
               t("told.setup.no-owner"));
});

test("the update says why without naming a step", () => {
  layThePage();

  update.drawTheUpdate({
    installed: "1.5.2", published: "1.5.3", newer: true, progress: REFUSED,
  });

  assert.equal(document.getElementById("pi-update-note").textContent,
               t("told.setup.no-owner"));
});
