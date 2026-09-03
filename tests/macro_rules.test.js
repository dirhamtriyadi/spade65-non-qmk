"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const rules = require("../spade65/web/macro-rules.js");

// A small stand-in for the usage table the backend publishes.
const USAGES = { a: 4, b: 5, enter: 40, "left-ctrl": 224 };

const press = usage => ({ delay_ms: 20, usage, pressed: true });
const release = usage => ({ delay_ms: 20, usage, pressed: false });

test("a balanced sequence has no issue", () => {
  const macro = { events: [press("a"), release("a"), press("b"), release("b")] };
  assert.equal(rules.sequenceIssue(macro, USAGES), null);
  assert.equal(rules.sequenceIssue({ events: [] }, USAGES), null);
  assert.equal(rules.sequenceIssue(null, USAGES), null);
});

test("an unknown usage is reported with its position", () => {
  const macro = { events: [press("a"), press("nonsense")] };
  const issue = rules.sequenceIssue(macro, USAGES);
  assert.equal(issue.kind, "unknown");
  assert.equal(issue.number, 2);
  assert.equal(issue.usage, "nonsense");
});

test("pressing a key that is already held is reported", () => {
  const macro = { events: [press("a"), press("a")] };
  const issue = rules.sequenceIssue(macro, USAGES);
  assert.equal(issue.kind, "duplicate");
  assert.equal(issue.number, 2);
  assert.equal(issue.usage, "a");
});

test("releasing a key that was never pressed is reported", () => {
  const macro = { events: [press("a"), release("b")] };
  const issue = rules.sequenceIssue(macro, USAGES);
  assert.equal(issue.kind, "release");
  assert.equal(issue.number, 2);
  assert.equal(issue.usage, "b");
});

test("a key left held at the end is reported without a position", () => {
  const macro = { events: [press("a"), release("a"), press("b")] };
  const issue = rules.sequenceIssue(macro, USAGES);
  assert.equal(issue.kind, "held");
  assert.equal(issue.usage, "b");
  assert.equal(issue.number, undefined);
});

test("the same key written two ways is one identity", () => {
  // "a" and its numeric usage are the same key, so a press written one way and
  // a release written the other must still balance.
  const macro = { events: [press("a"), release("4")] };
  assert.equal(rules.sequenceIssue(macro, USAGES), null);
  assert.equal(rules.usageIdentity("A", USAGES), rules.usageIdentity("a", USAGES));
  assert.equal(rules.usageIdentity(" enter ", USAGES), "40");
});

test("numeric usages are accepted only inside one byte", () => {
  assert.equal(rules.usageIdentity("0", USAGES), "0");
  assert.equal(rules.usageIdentity("255", USAGES), "255");
  assert.equal(rules.usageIdentity("0x1f", USAGES), "31");
  assert.equal(rules.usageIdentity("256", USAGES), null);
  assert.equal(rules.usageIdentity("-1", USAGES), null);
  assert.equal(rules.usageIdentity("1.5", USAGES), null);
  assert.equal(rules.usageIdentity("", USAGES), null);
  assert.equal(rules.usageIdentity(null, USAGES), null);
});

test("an absent usage table rejects names but still accepts numbers", () => {
  assert.equal(rules.usageIdentity("a", undefined), null);
  assert.equal(rules.usageIdentity("4", undefined), "4");
});

test("bindings list every layer and key pointing at a macro", () => {
  const layers = {
    normal: { esc: { macro: 0 }, q: "a" },
    fn1: { w: { macro: 1 } },
    fn2: { e: { macro: 0 } },
  };
  assert.deepEqual(rules.bindings(layers, 0), [
    { layer: "normal", key: "esc" },
    { layer: "fn2", key: "e" },
  ]);
  assert.deepEqual(rules.bindings(layers, 1), [{ layer: "fn1", key: "w" }]);
  assert.deepEqual(rules.bindings(layers, 2), []);
  assert.deepEqual(rules.bindings(null, 0), []);
});

test("a plain assignment is never mistaken for a macro binding", () => {
  // A key assigned the letter "a" has no macro property to compare.
  assert.deepEqual(rules.bindings({ normal: { q: "a", w: { usage: "b" } } }, 0), []);
});

test("the recorder stops before it runs out of reserved release slots", () => {
  // Room is judged against the events already recorded plus one release for
  // every key that will still be held after this one.
  assert.equal(rules.hasRoomForEvent(0, 0), true);
  assert.equal(rules.hasRoomForEvent(82, 1), true);
  assert.equal(rules.hasRoomForEvent(83, 1), false);
  assert.equal(rules.hasRoomForEvent(83, 0), true);
  assert.equal(rules.hasRoomForEvent(84, 0), false);
  assert.equal(rules.hasRoomForEvent(80, 4), false);
});

test("a recording is finished once it is full with nothing held", () => {
  assert.equal(rules.isRecordingFull(84, 0), true);
  assert.equal(rules.isRecordingFull(84, 1), false);
  assert.equal(rules.isRecordingFull(83, 0), false);
});

test("closing a recording releases every held key in order", () => {
  const closing = rules.pendingReleases(["a", "b"], 4);
  assert.equal(closing.overflow, false);
  assert.deepEqual(closing.events, [
    { delay_ms: 0, usage: "a", pressed: false },
    { delay_ms: 0, usage: "b", pressed: false },
  ]);
  assert.deepEqual(rules.pendingReleases([], 4), { events: [], overflow: false });
});

test("closing reports overflow rather than exceeding the limit", () => {
  const closing = rules.pendingReleases(["a", "b"], rules.MAX_EVENTS - 1);
  assert.equal(closing.events.length, 1);
  assert.equal(closing.overflow, true);
  assert.equal(rules.pendingReleases(["a"], rules.MAX_EVENTS).events.length, 0);
  assert.equal(rules.pendingReleases(["a"], rules.MAX_EVENTS).overflow, true);
});

test("no recording session can produce a macro the keyboard would reject", () => {
  // The reservation rule exists so Stop never leaves a key held down. Drive a
  // whole session through the same rules the recorder uses and check the
  // macro it produces always validates.
  const usages = { a: 4, b: 5, c: 6, d: 7, e: 8 };
  const names = Object.keys(usages);
  let seed = 20260903;
  const rnd = n => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) >>> 8) % n;

  for (let session = 0; session < 3000; session += 1) {
    const events = [];
    const held = [];
    for (let step = 0; step < 200; step += 1) {
      const name = names[rnd(names.length)];
      const down = held.includes(name) ? false : rnd(3) > 0;
      if (down === held.includes(name)) continue;
      const heldAfter = held.length + (down ? 1 : -1);
      if (!rules.hasRoomForEvent(events.length, heldAfter)) break;
      events.push({ delay_ms: 0, usage: name, pressed: down });
      if (down) held.push(name);
      else held.splice(held.indexOf(name), 1);
      if (rules.isRecordingFull(events.length, held.length)) break;
    }
    const closing = rules.pendingReleases(held, events.length);
    assert.equal(closing.overflow, false, "reservation ran out");
    events.push(...closing.events);
    assert.ok(events.length <= rules.MAX_EVENTS, "over the protocol limit");
    assert.equal(rules.sequenceIssue({ events }, usages), null,
      "invalid macro from a legal session: " + JSON.stringify(events));
  }
});
