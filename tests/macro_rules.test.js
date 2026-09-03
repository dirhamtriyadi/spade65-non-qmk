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
