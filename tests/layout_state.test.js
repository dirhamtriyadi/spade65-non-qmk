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
const readonlyReceiver = {...usb, pid: "0352"};
const gated = {...usb, configuration_status: "descriptor-gated"};
const receiverEntry = {
  vid: "0603",
  pid: "0352",
  usages: ["0001:0006"],
  configuration_status: "unsupported-read-only",
};

test("the header names the configurable keyboard, not the read-only receiver", () => {
  // The receiver can enumerate first, so position must not decide the headline.
  assert.equal(layout.primaryDevice([receiverEntry, gated]).pid, "0351");
  assert.equal(layout.primaryDevice([gated, receiverEntry]).pid, "0351");
  // The real case: one keyboard exposing a boot interface and a configuration
  // interface, in enumeration order. The ff02:0001 interface must win.
  const bootOnlyGated = {...gated, usages: ["0001:0006"], path: "/dev/hidraw0"};
  const configGated = {...gated, path: "/dev/hidraw1"};
  assert.equal(
    layout.primaryDevice([bootOnlyGated, configGated]).path,
    "/dev/hidraw1"
  );
  // A configurable device without the configuration collection still beats it.
  assert.equal(layout.primaryDevice([receiverEntry, bootOnlyGated]).path, "/dev/hidraw0");
  // Null entries must not throw.
  assert.equal(layout.primaryDevice([null, configGated]).path, "/dev/hidraw1");
  assert.equal(layout.primaryDevice([null]), null);
  // Receiver alone is still reported so the status strip can label it.
  assert.equal(layout.primaryDevice([receiverEntry]).pid, "0352");
  assert.equal(layout.primaryDevice([]), null);
  assert.equal(layout.primaryDevice(null), null);
});

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
  const receiver = layout.resolveLayout(readonlyReceiver, {}, "iso-split");
  assert.equal(receiver.connected, false);
  assert.equal(receiver.layout, "ansi-standard");
});

test("storage parser keeps only bounded known layout values", () => {
  assert.deepEqual(
    layout.parseDeviceLayouts({good: "iso-split", bad: "something-else"}),
    {good: "iso-split"},
  );
  assert.deepEqual(layout.parseDeviceLayouts([]), {});
});

test("a wired keyboard says nothing about a battery it does not have", () => {
  // Plugged in, so an "unavailable" badge would be noise rather than news.
  const wired = { transport: "USB", readonly: { battery_percent: null } };
  assert.deepEqual(layout.batteryDisplay(wired), { show: false });
  assert.deepEqual(layout.batteryDisplay(null), { show: false });
  assert.deepEqual(layout.batteryDisplay(undefined), { show: false });
});

test("a wireless keyboard reports its level and where the level came from", () => {
  for (const transport of ["Dongle", "2.4 GHz receiver", "Bluetooth LE"]) {
    const device = {
      transport,
      readonly: {
        battery_percent: 87,
        battery_source: "BlueZ Battery1",
        battery_status: "reported by BlueZ Battery1",
      },
    };
    assert.deepEqual(layout.batteryDisplay(device), {
      show: true,
      percent: 87,
      source: "BlueZ Battery1",
      status: "reported by BlueZ Battery1",
    });
  }
});

test("a wireless keyboard without a reading says so instead of vanishing", () => {
  // The badge used to hide itself, which is why the reading was never found.
  const device = {
    transport: "Bluetooth LE",
    readonly: {
      battery_percent: null,
      battery_source: null,
      battery_status: "not exposed by the current transport/kernel",
    },
  };
  assert.deepEqual(layout.batteryDisplay(device), {
    show: true,
    percent: null,
    source: null,
    status: "not exposed by the current transport/kernel",
  });
  // A device with no readonly block at all is the same situation.
  assert.deepEqual(layout.batteryDisplay({ transport: "Dongle" }), {
    show: true,
    percent: null,
    source: null,
    status: null,
  });
});

test("an impossible percentage is treated as no reading", () => {
  // A percentage outside 0-100, or a non-integer, is a broken source rather
  // than a level worth showing.
  for (const percent of [-1, 101, 1.5, "87", null, undefined, NaN]) {
    const device = { transport: "Dongle", readonly: { battery_percent: percent } };
    assert.equal(layout.batteryDisplay(device).percent, null, String(percent));
  }
  for (const percent of [0, 1, 50, 100]) {
    const device = { transport: "Dongle", readonly: { battery_percent: percent } };
    assert.equal(layout.batteryDisplay(device).percent, percent);
  }
});

test("an unknown transport is treated as wired rather than guessed at", () => {
  assert.deepEqual(layout.batteryDisplay({ transport: "" }), { show: false });
  assert.deepEqual(layout.batteryDisplay({ transport: "Thunderbolt" }), {
    show: false,
  });
});

test("an empty interface list says why it is empty", () => {
  // The dropdown used to go blank with no explanation, which reads as "the
  // keyboard is not detected" even while the header says it is.
  const configurable = {
    configuration_status: "descriptor-gated",
    usages: ["ff02:0001", "0001:0006"],
  };
  const receiver = {
    configuration_status: "unsupported-read-only",
    usages: ["0001:0006", "ff55:0202"],
  };
  assert.equal(layout.unconfigurableReason([]), "none");
  assert.equal(layout.unconfigurableReason(null), "none");
  assert.equal(layout.unconfigurableReason([receiver, receiver]), "readOnly");
  assert.equal(layout.unconfigurableReason([configurable]), null);
  assert.equal(layout.unconfigurableReason([receiver, configurable]), null);
});

test("a read-only judgement outranks a config report the device advertises", () => {
  // Both checks have to hold. The backend decides configurability from the
  // whole descriptor, so an interface it rejected must stay rejected even if
  // it advertises the report writes would use.
  const rejected = {
    path: "/dev/hidraw9",
    configuration_status: "unsupported-read-only",
    usages: ["ff02:0001", "0001:0006"],
  };
  assert.deepEqual(layout.configurableDevices([rejected]), []);
  assert.equal(layout.unconfigurableReason([rejected]), "readOnly");
});

test("a device that claims to be configurable without the config report is not", () => {
  // configuration_status alone is not enough: writes go through ff02:0001,
  // so an interface without it can never be the target.
  const liar = {
    configuration_status: "descriptor-gated",
    usages: ["0001:0006"],
  };
  assert.equal(layout.unconfigurableReason([liar]), "readOnly");
  assert.deepEqual(layout.configurableDevices([liar]), []);
});

test("the selector lists every interface that can actually be written to", () => {
  const first = {
    path: "/dev/hidraw2",
    configuration_status: "descriptor-gated",
    usages: ["ff02:0001"],
  };
  const second = {
    path: "/dev/hidraw4",
    configuration_status: "descriptor-gated",
    usages: ["ff02:0001"],
  };
  const receiver = {
    path: "/dev/hidraw1",
    configuration_status: "unsupported-read-only",
    usages: ["ff55:0202"],
  };
  assert.deepEqual(layout.configurableDevices([receiver, first, second]), [
    first,
    second,
  ]);
  assert.deepEqual(layout.configurableDevices(null), []);
  assert.deepEqual(layout.configurableDevices([{ usages: null }]), []);
});
