(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Spade65MacroRules = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  function hasOwn(object, key) {
    return Object.prototype.hasOwnProperty.call(object || {}, key);
  }

  function usageIdentity(value, usages) {
    // A macro may name the same key as "a" or as its numeric usage, so compare
    // identities rather than the written form. Otherwise a press written one
    // way and a release written the other look like two different keys.
    const normalized = String(value == null ? "" : value).trim().toLowerCase();
    if (!normalized) return null;
    if (hasOwn(usages, normalized)) return String(usages[normalized]);
    const numeric = /^(?:0x[0-9a-f]+|0b[01]+|0o[0-7]+|\d+)$/.test(normalized) ?
      Number(normalized) :
      NaN;
    return Number.isInteger(numeric) && numeric >= 0 && numeric <= 255 ?
      String(numeric) :
      null;
  }

  function sequenceIssue(macro, usages) {
    // The firmware replays events verbatim, so an unbalanced sequence leaves a
    // key stuck down on the keyboard. Report the first problem and its
    // position, or a held key with no position once the list has run out.
    const held = new Set();
    const events = (macro && macro.events) || [];
    for (let index = 0; index < events.length; index += 1) {
      const event = events[index];
      const usage = usageIdentity(event.usage, usages);
      if (usage === null) {
        return {
          kind: "unknown",
          number: index + 1,
          usage: String(event.usage || "—"),
        };
      }
      if (event.pressed) {
        if (held.has(usage)) {
          return {
            kind: "duplicate",
            number: index + 1,
            usage: event.usage
          };
        }
        held.add(usage);
      } else {
        if (!held.has(usage)) {
          return {
            kind: "release",
            number: index + 1,
            usage: event.usage
          };
        }
        held.delete(usage);
      }
    }
    if (held.size) {
      const usage = [...held][0];
      const event = [...events]
        .reverse()
        .find(item => usageIdentity(item.usage, usages) === usage);
      return {
        kind: "held",
        usage: event && event.usage != null ? event.usage : usage
      };
    }
    return null;
  }

  // The firmware macro buffer holds 84 events, and protocol.py refuses a
  // longer one, so the recorder has to stop before it overruns rather than
  // truncate afterwards.
  const MAX_EVENTS = 84;

  function hasRoomForEvent(eventCount, heldAfter) {
    // Reserve one release for every key that will still be held after this
    // event, so stopping can never leave a key down on the keyboard.
    return eventCount + 1 + heldAfter <= MAX_EVENTS;
  }

  function isRecordingFull(eventCount, heldCount) {
    return eventCount >= MAX_EVENTS && heldCount === 0;
  }

  function pendingReleases(heldUsages, eventCount) {
    const events = [];
    let total = eventCount;
    for (const usage of heldUsages || []) {
      if (total >= MAX_EVENTS) return {
        events,
        overflow: true
      };
      events.push({
        delay_ms: 0,
        usage,
        pressed: false
      });
      total += 1;
    }
    return {
      events,
      overflow: false
    };
  }

  function bindings(layers, index) {
    const result = [];
    if (!layers || typeof layers !== "object") return result;
    for (const [layer, assignments] of Object.entries(layers)) {
      if (!assignments || typeof assignments !== "object") continue;
      for (const [key, value] of Object.entries(assignments)) {
        if (value && typeof value === "object" && value.macro === index) {
          result.push({
            layer,
            key
          });
        }
      }
    }
    return result;
  }

  return Object.freeze({
    MAX_EVENTS,
    bindings,
    hasRoomForEvent,
    isRecordingFull,
    pendingReleases,
    sequenceIssue,
    usageIdentity
  });
});
