"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const picker = require("../spade65/web/usage-picker.js");

const usages = {
  a: 0x04,
  "play-pause": 0xa1,
  "volume-up": 0xa3,
  "browser-back": 0xab,
  "mouse-left": 0xb4,
};
const groups = {
  Keyboard: ["a"],
  Media: ["play-pause", "volume-up"],
  "Browser/System": ["browser-back"],
  Mouse: ["mouse-left"],
};
const labels = group => ({
  Keyboard: "Keyboard",
  Media: "Media",
  "Browser/System": "Browser / Sistem",
  Mouse: "Mouse",
})[group];

test("an empty query preserves groups and their source order", () => {
  const result = picker.filterGroups(groups, usages, "", labels);
  assert.deepEqual(result.map(item => item.group), [
    "Keyboard",
    "Media",
    "Browser/System",
    "Mouse",
  ]);
  assert.equal(result.flatMap(item => item.items).length, 5);
});

test("names are searchable without caring about separators", () => {
  const result = picker.filterGroups(groups, usages, "play pause", labels);
  assert.deepEqual(result.flatMap(item => item.items.map(entry => entry.name)), [
    "play-pause",
  ]);
});

test("a translated group name returns the complete group", () => {
  const result = picker.filterGroups(groups, usages, "sistem", labels);
  assert.deepEqual(result.flatMap(item => item.items.map(entry => entry.name)), [
    "browser-back",
  ]);
});

test("hex and decimal HID values are searchable", () => {
  assert.equal(
    picker.filterGroups(groups, usages, "0xa3", labels)[0].items[0].name,
    "volume-up",
  );
  assert.equal(
    picker.filterGroups(groups, usages, "180", labels)[0].items[0].name,
    "mouse-left",
  );
});

test("labels make the selected function and byte unambiguous", () => {
  assert.equal(
    picker.optionLabel({ name: "play-pause", hex: "0xa1" }),
    "play-pause · 0xa1",
  );
  assert.equal(picker.usageHex(4), "0x04");
});

test("an unknown query produces no empty group shells", () => {
  assert.deepEqual(picker.filterGroups(groups, usages, "not-a-function", labels), []);
});
