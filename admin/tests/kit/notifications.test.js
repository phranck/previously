/**
 * nx-notifications: a stack of notifications beside the dock, each of which
 * opens or closes and leaves its room to the ones below it.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay } from "./desk.js";

/** @returns {any} An empty stack on the desk. */
function stack() {
  return lay("<nx-notifications></nx-notifications>");
}

const WORDS = { art: "stop", headline: "Previous ended unexpectedly", message: "Twice." };

/** @returns {Promise<void>} Once the slide a notification leaves with is over. */
function slid() {
  return new Promise((resolve) => setTimeout(resolve, 300));
}

test("a notification says its headline and its message beside its picture", () => {
  const notifications = stack();

  notifications.post("crash", WORDS);
  const shown = notifications.querySelector("nx-notification");

  assert.equal(shown.querySelector(".headline").textContent, WORDS.headline);
  assert.equal(shown.querySelector(".message").textContent, WORDS.message);
  assert.equal(shown.querySelector(".sign").style.backgroundImage, "var(--stop)");
});

test("posting the same name again rewrites it rather than adding one", () => {
  const notifications = stack();

  notifications.post("disk", { ...WORDS, headline: "91%" });
  notifications.post("disk", { ...WORDS, headline: "92%" });

  assert.equal(notifications.querySelectorAll("nx-notification").length, 1);
  assert.equal(notifications.querySelector(".headline").textContent, "92%");
});

test("a new notification stands at the foot of the stack", () => {
  const notifications = stack();

  notifications.post("update", WORDS);
  notifications.post("crash", WORDS);

  assert.deepEqual(notifications.names, ["update", "crash"]);
});

test("clicking one says so and takes it away", async () => {
  const notifications = stack();
  notifications.post("update", WORDS);
  notifications.post("crash", WORDS);
  const opened = [];
  notifications.addEventListener("nx-notification-open",
    (event) => opened.push(event.detail.name));

  notifications.querySelector("nx-notification .message").click();

  assert.deepEqual(opened, ["update"]);
  assert.deepEqual(notifications.names, ["crash"]);
  await slid();
  assert.equal(notifications.querySelectorAll("nx-notification").length, 1);
});

test("its close button closes it rather than opening it", () => {
  const notifications = stack();
  notifications.post("update", WORDS);
  const said = [];
  for (const kind of ["nx-notification-open", "nx-notification-close"]) {
    notifications.addEventListener(kind, (event) => said.push([kind, event.detail.name]));
  }

  notifications.querySelector("nx-notification .close").click();

  assert.deepEqual(said, [["nx-notification-close", "update"]]);
  assert.deepEqual(notifications.names, []);
});

test("one that goes is hidden at once and its room closes", () => {
  const notifications = stack();
  notifications.post("update", WORDS);
  const shown = notifications.querySelector("nx-notification");

  notifications.withdraw("update");

  assert.equal(shown.hasAttribute("leaving"), true);
  assert.equal(shown.style.height, "0px");
});

test("withdrawing one that is not there changes nothing", () => {
  const notifications = stack();
  notifications.post("update", WORDS);

  notifications.withdraw("crash");

  assert.deepEqual(notifications.names, ["update"]);
});
