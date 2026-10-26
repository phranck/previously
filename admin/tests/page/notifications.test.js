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

/**
 * Counts the chimes played while a test runs.
 * @returns {{count: number}}
 */
function listening() {
  const heard = { count: 0 };
  globalThis.Audio = class { play() { heard.count += 1; return Promise.resolve(); } };
  return heard;
}

test("a browser that never chose shows them silently at the top right", () => {
  layThePage();
  notifications.wireTheNotifications();

  assert.deepEqual(notifications.notificationSettings(),
                   { show: true, sound: false, corner: "top-right" });
  assert.equal(stack().hidden, false);
  assert.equal(stack().getAttribute("corner"), "top-right");
});

test("switching them off hides the stack, and the corner moves it", () => {
  layThePage();
  notifications.wireTheNotifications();

  notifications.changeNotificationSettings({ show: false, corner: "bottom-left" });

  assert.equal(stack().hidden, true);
  assert.equal(stack().getAttribute("corner"), "bottom-left");
  assert.deepEqual(JSON.parse(localStorage.getItem("notifications.settings")),
                   { show: false, sound: false, corner: "bottom-left" });
});

test("a corner nobody offers is read as the top right", () => {
  layThePage();
  localStorage.setItem("notifications.settings", JSON.stringify({ corner: "middle" }));

  assert.equal(notifications.notificationSettings().corner, "top-right");
});

test("one that appears chimes once, and one that only stays does not", () => {
  layThePage();
  notifications.wireTheNotifications();
  notifications.changeNotificationSettings({ sound: true });
  const heard = listening();

  notifications.drawTheNotifications([NEWER, CRASHED]);
  notifications.drawTheNotifications([NEWER, CRASHED]);

  assert.equal(heard.count, 1);
});

test("no chime without the sound switched on", () => {
  layThePage();
  notifications.wireTheNotifications();
  const heard = listening();

  notifications.drawTheNotifications([NEWER]);

  assert.equal(heard.count, 0);
});

test("the switches in Preferences change the stack at once", async () => {
  layThePage();
  notifications.wireTheNotifications();
  const preferences = await import("../../interface/app/preferences.js");
  preferences.wirePreferences();

  const show = document.getElementById("notifications-show");
  assert.equal(show.checked, true);
  show.click();
  assert.equal(stack().hidden, true);

  document.querySelector('input[name="notifications-corner"][value="bottom-right"]').click();
  assert.equal(stack().getAttribute("corner"), "bottom-right");
});
