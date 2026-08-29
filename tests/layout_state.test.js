"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const layout = require("../spade65/web/layout-state.js");

const usb = {
  vid: "0603",
  pid: "0351",
  usages: ["0001:0006", "ff02:0001"],
};
const dongle = {...usb, pid: "0356"};

test("disconnected always shows Noir's ANSI standard default", () => {
  const stored = {"0603:spade65": "iso-split"};
  const result = layout.resolveLayout(null, stored, "ansi-split");
  assert.equal(result.connected, false);
  assert.equal(result.layout, "ansi-standard");
  assert.deepEqual(result.layouts, stored);
  assert.equal(result.changed, false);
});

test("wired USB and dongle restore one remembered keyboard layout", () => {
  const stored = {"0603:spade65": "iso-standard"};
  assert.equal(layout.resolveLayout(usb, stored).layout, "iso-standard");
  assert.equal(layout.resolveLayout(dongle, stored).layout, "iso-standard");
  assert.equal(layout.deviceKey(usb), layout.deviceKey(dongle));
});

test("a new detected keyboard migrates the valid legacy preference", () => {
  const result = layout.resolveLayout(usb, {}, "ansi-split");
  assert.equal(result.layout, "ansi-split");
  assert.equal(result.layouts["0603:spade65"], "ansi-split");
  assert.equal(result.changed, true);
  assert.equal(result.migrated, true);
});

test("invalid storage and non-configuration interfaces are safe", () => {
  const corrupt = layout.resolveLayout(usb, "{bad json", "unknown-layout");
  assert.equal(corrupt.layout, "ansi-standard");
  assert.deepEqual(corrupt.layouts, {"0603:spade65": "ansi-standard"});
  const bootOnly = {...usb, usages: ["0001:0006"]};
  assert.equal(layout.resolveLayout(bootOnly, {}, "iso-split").connected, false);
});

test("storage parser keeps only bounded known layout values", () => {
  assert.deepEqual(
    layout.parseDeviceLayouts({good: "iso-split", bad: "something-else"}),
    {good: "iso-split"},
  );
  assert.deepEqual(layout.parseDeviceLayouts([]), {});
});
