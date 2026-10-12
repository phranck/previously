/**
 * nx-slider stands on the step it is given, with the ticks and the unit it is
 * given, whenever it is given them.
 *
 * Whoever builds a slider may fill it in before putting it on the page, as the
 * Config Editor does with the memory of each NeXTdimension board. A slider
 * that drew only once it was there would throw at the first step it was
 * handed, and take the rest of the window with it.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { lay } from "./desk.js";

/** The memory a NeXTdimension board can have, as the editor offers it. */
const STEPS = [4, 16, 32, 64].map((mb) => ({ value: mb, label: `${mb} MB`, tick: String(mb) }));

/**
 * What a slider shows.
 * @param {Element} slider
 * @returns {{unit: string, ticks: string[], chosen: string[], now: string | null}}
 */
function shown(slider) {
  const ticks = [...slider.querySelectorAll(".tick")];
  return {
    unit: slider.querySelector(".unit")?.textContent ?? "",
    ticks: ticks.map((tick) => tick.textContent),
    chosen: ticks.filter((tick) => tick.hasAttribute("chosen")).map((tick) => tick.textContent),
    now: slider.getAttribute("aria-valuenow"),
  };
}

test("a slider filled in on the page shows what it was given", () => {
  const slider = lay(`<nx-slider></nx-slider>`);

  slider.options = STEPS;
  slider.says = "MB";
  slider.value = 32;

  assert.deepEqual(shown(slider),
                   { unit: "MB", ticks: ["4", "16", "32", "64"], chosen: ["32"], now: "2" });
});

test("a slider filled in before it is on the page is drawn when it arrives", () => {
  lay("");
  const group = document.createElement("fieldset");
  const slider = document.createElement("nx-slider");
  group.append(slider);

  slider.options = STEPS;
  slider.says = "MB";
  slider.value = 32;
  document.body.append(group);

  assert.deepEqual(shown(slider),
                   { unit: "MB", ticks: ["4", "16", "32", "64"], chosen: ["32"], now: "2" });
  assert.equal(slider.value, 32);
});
