/**
 * The Updates module of Preferences: whether the Pi looks for updates on its
 * own, as the Pi says, and the button that has it look once.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, json, layThePage, settled } from "./page.js";

/** What the Pi holds, and every request the page sent, as route and body. */
let holds = true;
const sent = [];

answering(async (route, options = {}) => {
  if (route === "/api/updates" && options.method !== "POST") return json({ automatic: holds });
  /* The catalog is asked for as Preferences is wired, and is not what these
     tests are about. */
  if (route === "/api/software") return json({}, 404);
  if (options.method === "POST") {
    const body = options.body ? JSON.parse(options.body) : null;
    sent.push([route, body]);
    if (route === "/api/updates" && body.automatic === false && holds === "refuses") {
      return json({ ok: false, automatic: true }, 409);
    }
    if (route === "/api/updates") holds = body.automatic;
    return json({ ok: true, automatic: holds === true });
  }
  return json({ notifications: [] });
});

const preferences = await import("../../interface/app/preferences.js");

/** @returns {Record<string, boolean>} Which radio button is chosen, by value. */
function chosen() {
  return Object.fromEntries([...document.querySelectorAll('input[name="updates-mode"]')]
    .map((radio) => [radio.value, radio.checked]));
}

test("the module shows what the Pi holds, with the button off while it looks on its own", async () => {
  holds = true;
  layThePage();
  preferences.wirePreferences();
  await settled();

  assert.deepEqual(chosen(), { automatic: true, manual: false });
  assert.equal(document.getElementById("updates-look").disabled, true);
});

test("choosing to look manually tells the Pi and lets the button be pressed", async () => {
  holds = true;
  sent.length = 0;
  layThePage();
  preferences.wirePreferences();
  await settled();

  document.querySelector('input[name="updates-mode"][value="manual"]').click();
  await settled();

  assert.deepEqual(sent, [["/api/updates", { automatic: false }]]);
  assert.equal(document.getElementById("updates-look").disabled, false);
});

test("a choice the Pi refuses is drawn back to what it holds", async () => {
  holds = "refuses";
  layThePage();
  preferences.wirePreferences();
  await settled();

  document.querySelector('input[name="updates-mode"][value="manual"]').click();
  await settled();

  assert.deepEqual(chosen(), { automatic: true, manual: false });
  assert.equal(document.getElementById("updates-look").disabled, true);
});

test("the button has the Pi look once", async () => {
  holds = false;
  sent.length = 0;
  layThePage();
  preferences.wirePreferences();
  await settled();

  document.getElementById("updates-look").click();
  await settled();

  assert.deepEqual(sent.map(([route]) => route), ["/api/updates/look"]);
});
