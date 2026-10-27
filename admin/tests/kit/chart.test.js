/**
 * nx-chart: a history of readings as columns of lamps, the newest on the
 * right, lit as high as each reading is of the top.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { kit, lay } from "./desk.js";

/** @returns {number[]} How many lamps each column has lit, left to right. */
function heights(chart) {
  return [...chart.querySelectorAll(".column")]
    .map((column) => column.querySelectorAll(".led[lit]").length);
}

/** @returns {(string | null)[]} The color zone of each lamp of one column,
 *  bottom up. */
function zones(chart, column) {
  return [...chart.querySelectorAll(".column")[column].children]
    .map((lamp) => lamp.getAttribute("zone"));
}

test("a chart is as wide and as tall as it says, and empty at first", () => {
  const chart = lay(`<nx-chart columns="5" lamps="4"></nx-chart>`);

  assert.equal(chart.querySelectorAll(".column").length, 5);
  assert.equal(chart.querySelectorAll(".column")[0].children.length, 4);
  assert.deepEqual(heights(chart), [0, 0, 0, 0, 0]);
  assert.equal(lay(`<nx-chart></nx-chart>`).querySelectorAll(".column").length,
               kit.CHART_COLUMNS);
});

test("a reading enters on the right and moves the others left", () => {
  const chart = lay(`<nx-chart columns="3" lamps="4"></nx-chart>`);
  chart.floor = 100;

  chart.push(25);
  chart.push(100);

  assert.deepEqual(heights(chart), [0, 1, 4]);
});

test("a missing reading lights nothing in its column", () => {
  const chart = lay(`<nx-chart columns="2" lamps="4"></nx-chart>`);
  chart.floor = 100;

  chart.push(50);
  chart.push(null);

  assert.deepEqual(heights(chart), [2, 0]);
});

test("a fixed top holds a reading above it to a full column", () => {
  const chart = lay(`<nx-chart columns="2" lamps="4"></nx-chart>`);
  chart.floor = 200;

  chart.push(400);
  chart.push(100);

  assert.deepEqual(heights(chart), [4, 2]);
});

test("a growing top rises to the highest reading in view, and falls back once it is gone", () => {
  /* Four cores, so a full column is every core busy until the load goes
     beyond that. */
  const chart = lay(`<nx-chart columns="2" lamps="4"></nx-chart>`);
  chart.floor = 4;
  chart.grows = true;

  chart.push(2);
  assert.deepEqual(heights(chart), [0, 2]);

  chart.push(8);
  assert.deepEqual(heights(chart), [1, 4]);

  chart.push(4);
  chart.push(4);
  assert.deepEqual(heights(chart), [4, 4]);
});

test("each lamp takes the color of the value it stands for", () => {
  const chart = lay(`<nx-chart columns="1" lamps="4"></nx-chart>`);
  chart.floor = 4;
  chart.grows = true;
  chart.warm = 2.8;
  chart.hot = 4;

  /* The top is 4: the lamps stand for 1, 2, 3 and 4. */
  chart.push(4);
  assert.deepEqual(zones(chart, 0), [null, null, "warm", "warm"]);

  /* The top grows to 8: the lamps stand for 2, 4, 6 and 8. */
  chart.push(8);
  assert.deepEqual(zones(chart, 0), [null, "warm", "hot", "hot"]);
});

test("the green lamps grow paler up a column, by the value they stand for", () => {
  const chart = lay(`<nx-chart columns="1" lamps="4"></nx-chart>`);
  chart.floor = 4;
  chart.warm = 2.8;
  chart.hot = 4;

  chart.push(4);

  /* The lamps stand for 1, 2, 3 and 4, and orange begins above 2.8. */
  assert.deepEqual([...chart.querySelectorAll(".led")]
    .map((lamp) => lamp.style.getPropertyValue("--along")), ["0.357", "0.714", "", ""]);
});

test("a chart that never warns grades its green up the whole column", () => {
  const chart = lay(`<nx-chart columns="1" lamps="4"></nx-chart>`);
  chart.floor = 4;

  chart.push(4);

  assert.deepEqual([...chart.querySelectorAll(".led")]
    .map((lamp) => lamp.style.getPropertyValue("--along")), ["0", "0.333", "0.667", "1"]);
});

test("clearing empties every column", () => {
  const chart = lay(`<nx-chart columns="2" lamps="4"></nx-chart>`);
  chart.floor = 100;
  chart.push(100);
  chart.push(100);

  chart.clear();

  assert.deepEqual(heights(chart), [0, 0]);
});
