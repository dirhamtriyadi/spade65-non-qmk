"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const effects = require("../spade65/web/live-effects.js");

test("master brightness scales the final composited frame", () => {
  const source = { esc: "#ff8040", a: "#123456" };
  assert.deepEqual(effects.applyMasterBrightness(source, 100), source);
  assert.deepEqual(effects.applyMasterBrightness(source, 50), { esc: "#804020", a: "#091a2b" });
  assert.deepEqual(effects.applyMasterBrightness(source, 0), { esc: "#000000", a: "#000000" });
  assert.deepEqual(source, { esc: "#ff8040", a: "#123456" });
});

test("layer opacity and disabled layers change the actual composite", () => {
  const red = { color: [255, 0, 0], alpha: 1 };
  assert.deepEqual(effects.compositePixels([{ ...red, alpha: 0 }]), [0, 0, 0]);
  assert.deepEqual(effects.compositePixels([{ ...red, alpha: 0.5 }]), [128, 0, 0]);
  assert.deepEqual(effects.compositePixels([red]), [255, 0, 0]);
  assert.deepEqual(effects.compositePixels([{ ...red, enabled: false }]), [0, 0, 0]);
  assert.deepEqual(
    effects.compositePixels([red, { color: [0, 0, 255], alpha: 0.5 }]),
    [128, 0, 128]
  );
});

test("sensitivity, noise gate, and smoothing affect audio levels", () => {
  const quiet = { level: 0.08, peak: 0.1, bands: Array(64).fill(0.08) };
  const gated = effects.processAudioSnapshot(quiet, { sensitivity: 1000, noiseGate: 10, smoothing: 0 });
  assert.equal(gated.level, 0);
  assert.ok(gated.bands.every(value => value === 0));

  const normal = effects.processAudioSnapshot(quiet, { sensitivity: 1000, noiseGate: 0, smoothing: 0 });
  const sensitive = effects.processAudioSnapshot(quiet, { sensitivity: 4000, noiseGate: 0, smoothing: 0 });
  assert.ok(normal.level > 0);
  assert.ok(sensitive.level > normal.level);

  const previous = effects.emptyAudioFrame();
  const smoothed = effects.processAudioSnapshot({ level: 1, peak: 1, bands: Array(64).fill(1) }, { smoothing: 90 }, previous);
  assert.ok(smoothed.level > 0 && smoothed.level < 1);

  const nativeQuiet = { scale: "linear", level: 0.0005, peak: 0.0006, bands: Array(64).fill(0.0005) };
  const nativeLow = effects.processAudioSnapshot(nativeQuiet, { sensitivity: 200, noiseGate: 2, smoothing: 0 });
  const nativeDefault = effects.processAudioSnapshot(nativeQuiet, { sensitivity: 1000, noiseGate: 2, smoothing: 0 });
  const nativeHigh = effects.processAudioSnapshot(nativeQuiet, { sensitivity: 8000, noiseGate: 2, smoothing: 0 });
  assert.ok(nativeDefault.level > nativeLow.level);
  assert.ok(nativeHigh.level > nativeDefault.level);
});

test("bass and spectrum modes use frequency bands rather than global loudness", () => {
  const frame = effects.emptyAudioFrame();
  frame.level = 0.25;
  frame.bass = 0.8;
  frame.bands[32] = 0.75;
  assert.equal(effects.audioInfluence(frame, "loudness", 0.5, 0.5), 0.25);
  assert.equal(effects.audioInfluence(frame, "bass", 0.5, 0.5), 0.8);
  assert.equal(effects.audioInfluence(frame, "spectrum", 0.5, 0.5), 1);
  assert.equal(effects.audioInfluence(frame, "spectrum", 0.5, 0.1), 0);
  frame.bands[32] = 1;
  assert.equal(effects.audioInfluence(frame, "spectrum", 0.5, 0), 1);
});

test("a spectrum bar can reach the top row of the keyboard", () => {
  // Five discrete rows have to be rasterised as five bands, not as five points
  // on 0..1. Dividing by rowCount-1 puts the top row exactly at 1.0, which
  // shapeLevel only reaches on a clipping signal, so the top row stayed dark.
  const rowCount = 5;
  const thresholds = [0, 1, 2, 3, 4].map(
    row => 1 - effects.bandRowPosition(row, rowCount)
  );
  assert.deepEqual(
    thresholds.map(value => Number(value.toFixed(2))),
    [0.8, 0.6, 0.4, 0.2, 0]
  );

  const lit = level => {
    const frame = effects.emptyAudioFrame();
    frame.bands.fill(level);
    return [0, 1, 2, 3, 4].filter(row => effects.audioInfluence(
      frame, "spectrum", 0.5, effects.bandRowPosition(row, rowCount)
    ) === 1).length;
  };
  assert.equal(lit(0), 1);
  assert.equal(lit(0.5), 3);
  assert.equal(lit(0.85), 5);
  assert.equal(lit(1), 5);
});

test("row positions stay inside the keyboard for odd input", () => {
  assert.equal(effects.bandRowPosition(-3, 5), 1 / 5);
  assert.equal(effects.bandRowPosition(99, 5), 1);
  assert.equal(effects.bandRowPosition(0, 1), 1);
  assert.equal(effects.bandRowPosition(0, 0), 1);
});

test("band resampling preserves the requested shape", () => {
  assert.deepEqual(effects.resampleBands([0, 1], 4), [0, 0, 1, 1]);
  assert.deepEqual(effects.resampleBands([], 3), [0, 0, 0]);
});

test("system output is preferred without overwriting an unavailable preference", () => {
  const sources = [
    { value: "native:system:default", kind: "system", default: true },
    { value: "microphone:default", kind: "microphone" }
  ];
  assert.equal(effects.preferredAudioSource(sources), "native:system:default");
  assert.equal(effects.preferredAudioSource(sources, "microphone:default"), "microphone:default");
  assert.equal(effects.preferredAudioSource(sources, "native:missing"), "native:system:default");
});
