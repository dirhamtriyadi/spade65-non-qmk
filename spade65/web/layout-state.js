(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Spade65LayoutState = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const DEFAULT_LAYOUT = "ansi-standard";
  const VALID_LAYOUTS = Object.freeze([
    DEFAULT_LAYOUT,
    "ansi-split",
    "iso-standard",
    "iso-split",
  ]);
  const CONFIG_USAGE = "ff02:0001";

  function isValidLayout(value) {
    return VALID_LAYOUTS.includes(value);
  }

  function parseDeviceLayouts(value) {
    let source = value;
    if (typeof source === "string") {
      try {
        source = JSON.parse(source);
      } catch (_error) {
        return {};
      }
    }
    if (!source || typeof source !== "object" || Array.isArray(source)) return {};
    const result = {};
    for (const [key, layout] of Object.entries(source).slice(0, 100)) {
      if (
        typeof key === "string" &&
        key.length > 0 &&
        key.length <= 128 &&
        isValidLayout(layout)
      ) result[key] = layout;
    }
    return result;
  }

  function primaryDevice(devices) {
    // Discovery returns interfaces in hidraw/hidapi enumeration order, so the
    // first entry can be the read-only receiver even while the configurable
    // keyboard is attached. The header must name the interface writes target.
    if (!Array.isArray(devices) || devices.length === 0) return null;
    const configurable = devices.filter(
      device => device && device.configuration_status === "descriptor-gated"
    );
    return (
      configurable.find(
        device =>
        Array.isArray(device.usages) && device.usages.includes(CONFIG_USAGE)
      ) ||
      configurable[0] ||
      devices[0]
    );
  }

  function deviceKey(device) {
    if (
      !device ||
      !Array.isArray(device.usages) ||
      !device.usages.includes(CONFIG_USAGE)
    ) return null;
    const vid = String(device.vid || "").toLowerCase();
    const pid = String(device.pid || "").toLowerCase();
    // The observed 0352 receiver has only ordinary input/output collections.
    // Never let it select a configurable layout, even if malformed metadata
    // were to claim that a configuration usage exists.
    if (vid === "0603" && pid === "0352") return null;
    if (vid === "0603" && ["0351", "0356"].includes(pid)) {
      // Wired USB and the 2.4 GHz dongle are two transports for one keyboard.
      return "0603:spade65";
    }
    return vid && pid ? `${vid}:${pid}` : null;
  }

  function resolveLayout(device, storedLayouts, legacyLayout) {
    const layouts = parseDeviceLayouts(storedLayouts);
    const key = deviceKey(device);
    if (key === null) {
      return {
        connected: false,
        key: null,
        layout: DEFAULT_LAYOUT,
        layouts,
        changed: false,
        migrated: false,
      };
    }
    let layout = layouts[key];
    let migrated = false;
    if (!isValidLayout(layout)) {
      layout = isValidLayout(legacyLayout) ? legacyLayout : DEFAULT_LAYOUT;
      migrated = isValidLayout(legacyLayout);
      layouts[key] = layout;
      return {
        connected: true,
        key,
        layout,
        layouts,
        changed: true,
        migrated
      };
    }
    return {
      connected: true,
      key,
      layout,
      layouts,
      changed: false,
      migrated
    };
  }

  // Only these transports run on the battery. On USB the keyboard is powered
  // by the cable, so an "unavailable" badge would be noise rather than news.
  const BATTERY_TRANSPORTS = Object.freeze([
    "Dongle",
    "2.4 GHz receiver",
    "Bluetooth LE"
  ]);

  function batteryDisplay(device) {
    // The badge used to hide itself whenever a reading was missing, which is
    // why users never found it: the only mode most people run is USB, where
    // there is nothing to show. On a wireless link the absence of a reading is
    // itself worth saying, along with the reason the backend already worked
    // out, so report the state rather than disappearing.
    const transport = device && device.transport;
    if (!BATTERY_TRANSPORTS.includes(transport)) return {
      show: false
    };
    const readonly = device.readonly || {};
    const percent = readonly.battery_percent;
    const usable = Number.isInteger(percent) && percent >= 0 && percent <= 100;
    return {
      show: true,
      percent: usable ? percent : null,
      source: readonly.battery_source == null ? null : readonly.battery_source,
      status: readonly.battery_status == null ? null : readonly.battery_status
    };
  }

  return Object.freeze({
    BATTERY_TRANSPORTS,
    CONFIG_USAGE,
    DEFAULT_LAYOUT,
    VALID_LAYOUTS,
    batteryDisplay,
    deviceKey,
    isValidLayout,
    parseDeviceLayouts,
    primaryDevice,
    resolveLayout,
  });
});
