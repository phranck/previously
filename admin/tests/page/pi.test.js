/**
 * The Raspberry Pi window's Temperature and Power rows, from what /api/pi
 * answers about the board's temperature and `vcgencmd get_throttled`.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { layThePage } from "./page.js";

const pi = await import("../../interface/app/pi.js");

/**
 * What /api/pi answers, with the readings these rows are drawn from.
 * @param {number} temperature - The chip's temperature in degrees.
 * @param {string[]} now - The names of get_throttled's low bits that are set.
 * @param {string[]} since - The names of its high bits that are set.
 * @param {number | null} [supply] - The supply voltage a Pi 5 measures, or
 *   null for a Pi 4, which cannot.
 */
function answer(temperature, now, since, supply = null) {
  return {
    version: "1.12.6", model: "Raspberry Pi 4 Model B Rev 1.5", board: "pi4",
    uptime_seconds: 60, temperature_c: temperature, temperature_limit_c: 80,
    throttling: { raw: 0, now, since_boot: since }, supply_v: supply,
    emulator: null, crashes: null, sound: null, disk: null, memory: null,
  };
}

/** @returns {{words: string, well: boolean}} What a row says, and whether its
 *  lamp is lit rather than dark. */
function row(id) {
  const state = document.getElementById(id);
  return {
    words: state.textContent.trim(),
    well: state.querySelector(".lamp").style.background !== "var(--dark)",
  };
}

test("a temperature limit reached since the start stands under Temperature", () => {
  layThePage();

  pi.drawPi(answer(76.4, [], ["temperature-limit"]));

  assert.deepEqual(row("pi-temp"),
                   { words: "76.4 °C, since the start: temperature limit reached", well: false });
  assert.deepEqual(row("pi-power"), { words: "in order", well: true });
});

test("a board slowing itself down now says so under Temperature", () => {
  layThePage();

  pi.drawPi(answer(81.2, ["frequency-capped", "throttled"], ["frequency-capped", "throttled"]));

  assert.deepEqual(row("pi-temp"),
                   { words: "81.2 °C, now: clock capped, throttled", well: false });
  assert.deepEqual(row("pi-power"), { words: "in order", well: true });
});

test("under-voltage stands under Power and leaves Temperature alone", () => {
  layThePage();

  pi.drawPi(answer(52.0, ["under-voltage"], ["under-voltage"]));

  assert.deepEqual(row("pi-temp"), { words: "52.0 °C", well: true });
  assert.deepEqual(row("pi-power"), { words: "now: under-voltage", well: false });
});

test("a Pi 5 shows its supply voltage in front of the state", () => {
  layThePage();

  pi.drawPi(answer(52.0, [], [], 5.0585));

  assert.deepEqual(row("pi-power"), { words: "5.06 V, in order", well: true });
});

test("a Pi 5 short of power shows the voltage it gets", () => {
  layThePage();

  pi.drawPi(answer(52.0, ["under-voltage"], ["under-voltage"], 4.71));

  assert.deepEqual(row("pi-power"), { words: "4.71 V, now: under-voltage", well: false });
});
