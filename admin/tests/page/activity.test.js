/**
 * Activity Monitor listens to a stream for as long as its window is open, and
 * not a moment longer.
 *
 * The stream is the page's `EventSource`, stood in for here by one that
 * records what was opened and closed and hands over what a test sends it.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { answering, layThePage, never } from "./page.js";

/** An EventSource that never reaches a network: it remembers every stream
 *  opened, and a test sends an event through `send`. */
class Stream {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  /** Every stream opened, oldest first. @type {Stream[]} */
  static opened = [];

  constructor(url) {
    this.url = url;
    this.readyState = Stream.CONNECTING;
    this.listeners = {};
    Stream.opened.push(this);
  }

  addEventListener(type, listener) {
    (this.listeners[type] ??= []).push(listener);
  }

  close() {
    this.readyState = Stream.CLOSED;
  }

  /** Hands every listener of one type an event carrying `data`. */
  send(type, data) {
    for (const listener of this.listeners[type] ?? []) listener({ data });
  }
}

globalThis.EventSource = Stream;
answering(() => never());

const { wireActivity } = await import("../../interface/app/activity.js");

/** A reading as the service sends one. */
const READING = {
  model: "Raspberry Pi 5 Model B Rev 1.1",
  board: "pi5",
  cores: [12.5, 0, 50, 100],
  load: { one: 1.5, five: 1.6, fifteen: 1.7, cores: 4 },
  memory: { total_mb: 4049, available_mb: 3537 },
  emulator: { cpu_percent: 57, memory_mb: 180, uptime_seconds: 2160 },
};

/** @returns {any} The Activity Monitor window. */
function theWindow() {
  return document.querySelector('nx-window[name="activity"]');
}

layThePage();
wireActivity();

test("nothing is opened while the window is closed", () => {
  assert.equal(theWindow().hidden, true);
  assert.equal(Stream.opened.length, 0);
});

test("opening the window opens one stream, and a reading is drawn", () => {
  theWindow().open();

  assert.equal(Stream.opened.length, 1);
  assert.equal(Stream.opened[0].url, "/api/activity/stream");
  Stream.opened[0].send("message", JSON.stringify(READING));
  assert.equal(document.getElementById("activity-model").textContent, READING.model);
  assert.equal(document.querySelectorAll("#activity-cores nx-leds").length, 4);
});

test("closing the window closes the stream", () => {
  theWindow().close();

  assert.equal(Stream.opened[0].readyState, Stream.CLOSED);
});

test("opening it again opens a new one", () => {
  theWindow().open();

  assert.equal(Stream.opened.length, 2);
  assert.notEqual(Stream.opened[1].readyState, Stream.CLOSED);
});

test("a reading puts in the drawing of the board it names", () => {
  Stream.opened[1].send("message", JSON.stringify(
    { ...READING, model: "Raspberry Pi Compute Module 4 Rev 1.1", board: "cm4" }));

  assert.equal(document.getElementById("activity-board").style.backgroundImage,
               "var(--board-cm4)");
});

test("a stream that breaks says so in the window", () => {
  Stream.opened[1].send("error");

  assert.notEqual(document.getElementById("activity-note").textContent, "");
});

test("and keeps the drawing of the board it last heard from", () => {
  assert.equal(document.getElementById("activity-board").style.backgroundImage,
               "var(--board-cm4)");
});
