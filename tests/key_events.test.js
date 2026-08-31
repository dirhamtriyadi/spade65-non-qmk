"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const keys = require("../spade65/web/key-events.js");

test("letters, digits and named keys reach their matrix button", () => {
  assert.deepEqual(keys.buttonsForCode("KeyA"), ["a"]);
  assert.deepEqual(keys.buttonsForCode("KeyZ"), ["z"]);
  assert.deepEqual(keys.buttonsForCode("Digit1"), ["n1"]);
  assert.deepEqual(keys.buttonsForCode("Digit0"), ["n0"]);
  assert.deepEqual(keys.buttonsForCode("Escape"), ["esc"]);
  assert.deepEqual(keys.buttonsForCode("Equal"), ["plus"]);
  assert.deepEqual(keys.buttonsForCode("BracketLeft"), ["lqu"]);
  assert.deepEqual(keys.buttonsForCode("ArrowUp"), ["up"]);
});

test("the right-hand modifier this board has is mapped", () => {
  // evtest reported usage 0xe6 for the key right of Fn, which the browser
  // reports as AltRight.
  assert.deepEqual(keys.buttonsForCode("AltRight"), ["ralt"]);
  assert.deepEqual(keys.buttonsForCode("ControlLeft"), ["lctrl"]);
  assert.deepEqual(keys.buttonsForCode("MetaLeft"), ["win"]);
});

test("backslash follows the selected layout family", () => {
  // One physical code, two matrix slots: ANSI keeps it above Enter, ISO moves
  // it beside a tall Enter.
  assert.deepEqual(keys.buttonsForCode("Backslash", "ansi-standard"), ["k29"]);
  assert.deepEqual(keys.buttonsForCode("Backslash", "ansi-split"), ["k29"]);
  assert.deepEqual(keys.buttonsForCode("Backslash", "iso-standard"), ["k42"]);
  assert.deepEqual(keys.buttonsForCode("Backslash", "iso-split"), ["k42"]);
  assert.deepEqual(keys.buttonsForCode("Backslash"), ["k29"]);
});

test("one space event cannot say which segment was struck", () => {
  // A split spacebar has three slots but the host reports a single code, so
  // the tester lights every segment rather than guessing one.
  assert.deepEqual(keys.buttonsForCode("Space"), ["lspace", "mspace", "rspace"]);
});

test("unknown and empty codes map to nothing instead of throwing", () => {
  for (const code of ["", null, undefined, "F13", "NumpadEnter", "Unidentified"]) {
    assert.deepEqual(keys.buttonsForCode(code), []);
  }
});

test("keys the tester can never observe are declared", () => {
  // Fn is resolved inside the firmware and emits no usage at all, confirmed
  // with evtest on the wired unit.
  assert.equal(keys.isUnobservable("fn"), true);
  assert.equal(keys.isUnobservable("ralt"), false);
  // The desktop usually claims Super before the page sees it, so a dark key
  // there is not evidence the key is broken.
  assert.equal(keys.isHostReserved("win"), true);
  assert.equal(keys.isHostReserved("lctrl"), false);
});

test("no physical code maps to a key this board does not have", () => {
  // rctrl stays mapped because a split board may carry it, but Fn must never
  // be produced from a code, since nothing emits it.
  const produced = new Set();
  for (const code of Object.keys(keys.DIRECT)) {
    for (const button of keys.buttonsForCode(code)) produced.add(button);
  }
  assert.equal(produced.has("fn"), false);
});
