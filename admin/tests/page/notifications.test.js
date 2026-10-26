/**
 * What the page does with the list of notifications the Pi sends: words in the
 * language in force, what somebody closed kept closed until its reading
 * changes, and the window each one opens.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, layThePage, never } from "./page.js";

answering(() => never());

const notifications = await import("../../interface/app/notifications.js");
const update = await import("../../interface/app/update.js");
const { t } = await import("../../interface/strings.js");

const NEWER = {
  name: "update", level: "info", reading: "1.13.0",
  values: { version: "1.13.0+2.gabcdef0", installed: "1.12.4" },
};
const CRASHED = {
  name: "crash", level: "error", reading: "2",
  values: { count: 2, last: 1790657571 },
};

/** @returns {any} The stack on the page. */
function stack() {
  return document.querySelector("nx-notifications");
}

test("a notification is said in the interface's words, with the release alone", () => {
  layThePage();

  notifications.drawTheNotifications([NEWER]);

  const shown = stack().querySelector("nx-notification");
  assert.equal(shown.querySelector(".headline").textContent,
               t("notification.update.headline", { version: "1.13.0" }));
  assert.equal(shown.querySelector(".sign").style.backgroundImage, "var(--sign-info)");
});

test("a count is said in its plural, and an error wears the stop sign", () => {
  layThePage();

  notifications.drawTheNotifications([CRASHED]);

  const shown = stack().querySelector("nx-notification");
  assert.match(shown.querySelector(".message").textContent, /^2 /);
  assert.equal(shown.querySelector(".sign").style.backgroundImage, "var(--stop)");
});

test("one somebody closed stays closed until its reading changes", () => {
  layThePage();
  notifications.wireTheNotifications();
  notifications.drawTheNotifications([CRASHED]);

  stack().querySelector("nx-notification .close").click();
  notifications.drawTheNotifications([CRASHED]);
  assert.deepEqual(stack().names, []);

  notifications.drawTheNotifications([{ ...CRASHED, reading: "3",
                                        values: { count: 3, last: 1790660000 } }]);
  assert.deepEqual(stack().names, ["crash"]);
});

test("one whose condition has gone goes, and comes back when it does", () => {
  layThePage();
  notifications.wireTheNotifications();
  notifications.drawTheNotifications([NEWER]);
  stack().querySelector("nx-notification .close").click();

  notifications.drawTheNotifications([]);
  notifications.drawTheNotifications([NEWER]);

  assert.deepEqual(stack().names, ["update"]);
});

test("opening one opens the window that shows what it is about", () => {
  layThePage();
  notifications.wireTheNotifications();
  const installer = document.querySelector('nx-window[name="installer"]');
  installer.close();

  notifications.drawTheNotifications([{
    name: "emulator", level: "info", reading: "4.6-0wmlive1",
    values: { version: "4.6-0wmlive1", installed: "4.5-0wmlive1" },
  }]);
  stack().querySelector("nx-notification .message").click();

  assert.equal(installer.hidden, false);
});

test("the Raspberry Pi window leaves saying a newer release to the notification", () => {
  layThePage();

  update.drawTheUpdate({
    installed: "1.12.4", published: "1.13.0", newer: true, progress: null,
  });

  assert.equal(document.getElementById("pi-update-note").textContent, "");
  assert.equal(document.getElementById("pi-newest").hasAttribute("newer"), true);
});
