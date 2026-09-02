/* Pure helpers for host-driven lighting. Kept separate so the DSP and final
 * brightness stage can be tested without a browser or a connected keyboard. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.Spade65LiveEffects = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const DEFAULT_BAND_COUNT = 64;

  function clamp(value, minimum = 0, maximum = 1) {
    const number = Number(value);
    if (!Number.isFinite(number)) return minimum;
    return Math.max(minimum, Math.min(maximum, number));
  }

  function emptyAudioFrame(bandCount = DEFAULT_BAND_COUNT) {
    const count = Math.max(1, Math.min(256, Math.trunc(Number(bandCount)) || DEFAULT_BAND_COUNT));
    return {
      level: 0,
      peak: 0,
      bass: 0,
      bands: Array(count).fill(0)
    };
  }

  function resampleBands(values, bandCount) {
    const source = Array.isArray(values) ? values.map(value => clamp(value)) : [];
    if (!source.length) return Array(bandCount).fill(0);
    if (source.length === bandCount) return source;
    return Array.from({
      length: bandCount
    }, (_, index) => {
      const start = index * source.length / bandCount;
      const end = (index + 1) * source.length / bandCount;
      const first = Math.floor(start);
      const last = Math.max(first, Math.ceil(end) - 1);
      let total = 0;
      let weight = 0;
      for (let sourceIndex = first; sourceIndex <= last; sourceIndex += 1) {
        const overlap = Math.max(0, Math.min(end, sourceIndex + 1) - Math.max(start, sourceIndex));
        total += (source[sourceIndex] || 0) * overlap;
        weight += overlap;
      }
      return weight ? total / weight : 0;
    });
  }

  function shapeLevel(value, gain, gate, linearScale = false) {
    const amplified = clamp(value * gain);
    // Native capture reports linear PCM magnitude while Web Audio reports an
    // already logarithmic byte spectrum. Convert only native measurements so
    // both sources give the controls a comparable, useful range.
    const perceived = linearScale && amplified > 0 ?
      clamp((20 * Math.log10(amplified) + 80) / 80) :
      amplified;
    if (perceived <= gate) return 0;
    // A square-root response keeps quiet passages useful without pretending
    // to reproduce an undocumented curve from the vendor binary.
    return Math.sqrt((perceived - gate) / Math.max(0.001, 1 - gate));
  }

  function smoothValue(previous, target, smoothing) {
    const release = Math.max(0.05, 1 - smoothing);
    const attack = Math.max(0.35, release);
    const amount = target >= previous ? attack : release;
    return clamp(previous + (target - previous) * amount);
  }

  function processAudioSnapshot(snapshot = {}, controls = {}, previous = null) {
    const before = previous && Array.isArray(previous.bands) ? previous : emptyAudioFrame();
    const count = before.bands.length || DEFAULT_BAND_COUNT;
    const sensitivity = clamp(controls.sensitivity ?? 1000, 200, 8000) / 1000;
    const gate = clamp(controls.noiseGate ?? controls.noise_gate ?? 2, 0, 95) / 100;
    const smoothing = clamp(controls.smoothing ?? 65, 0, 95) / 100;
    const linearScale = snapshot.scale === "linear";
    const targets = resampleBands(snapshot.bands, count).map(value => shapeLevel(value, sensitivity, gate, linearScale));
    const bands = targets.map((target, index) => smoothValue(before.bands[index] || 0, target, smoothing));
    const rawLevel = Number.isFinite(Number(snapshot.level)) ?
      clamp(snapshot.level) :
      targets.reduce((sum, value) => sum + value, 0) / targets.length;
    const rawPeak = Number.isFinite(Number(snapshot.peak)) ? clamp(snapshot.peak) : Math.max(0, ...targets);
    const level = smoothValue(before.level || 0, shapeLevel(rawLevel, sensitivity, gate, linearScale), smoothing);
    const peak = smoothValue(before.peak || 0, shapeLevel(rawPeak, sensitivity, gate, linearScale), smoothing);
    const bassCount = Math.max(1, Math.ceil(bands.length * 0.2));
    const bassTarget = bands.slice(0, bassCount).reduce((sum, value) => sum + value, 0) / bassCount;
    const bass = smoothValue(before.bass || 0, bassTarget, smoothing);
    return {
      level,
      peak,
      bass,
      bands
    };
  }

  function audioInfluence(frame, mode, xNormalized = 0, yNormalized = 0) {
    const audio = frame && Array.isArray(frame.bands) ? frame : emptyAudioFrame();
    if (mode === "bass") return clamp(audio.bass);
    if (mode !== "spectrum") return clamp(audio.level);
    const x = clamp(xNormalized);
    const y = clamp(yNormalized);
    const index = Math.min(audio.bands.length - 1, Math.floor(x * audio.bands.length));
    // This mirrors the original application's 256 x 64 spectrum gate without
    // materialising a bitmap: bars grow from the keyboard's bottom row upward.
    return clamp(audio.bands[index]) >= 1 - y ? 1 : 0;
  }

  function bandRowPosition(rowIndex, rowCount) {
    // Rasterise a spectrum bar onto a fixed number of key rows. Each row owns a
    // band of the bar's height, so the bottom row lights as soon as the band is
    // audible and the top row lights at (rowCount-1)/rowCount. Spreading the
    // rows across 0..1 instead would put the top row at exactly 1.0, which
    // shapeLevel only reaches when the signal clips.
    const total = Math.max(1, Math.trunc(Number(rowCount)) || 1);
    const index = clamp(Math.trunc(Number(rowIndex)) || 0, 0, total - 1);
    return (index + 1) / total;
  }

  function preferredAudioSource(entries, preferred = "") {
    const sources = Array.isArray(entries) ? entries : [];
    const exact = sources.find(source => source && source.value === preferred);
    if (exact) return exact.value;
    const systemDefault = sources.find(source => source?.kind === "system" && source.default === true);
    if (systemDefault) return systemDefault.value;
    const system = sources.find(source => source?.kind === "system");
    return system?.value || sources.find(source => source?.value)?.value || "";
  }

  function scaleHexColor(color, brightness) {
    const match = /^#([0-9a-f]{6})$/i.exec(String(color));
    if (!match) return "#000000";
    const amount = clamp(brightness, 0, 100) / 100;
    const hex = match[1];
    const channels = [0, 2, 4].map(offset => Math.round(parseInt(hex.slice(offset, offset + 2), 16) * amount));
    return `#${channels.map(value => value.toString(16).padStart(2, "0")).join("")}`;
  }

  function applyMasterBrightness(colors, brightness = 100) {
    const output = {};
    if (!colors || typeof colors !== "object" || Array.isArray(colors)) return output;
    for (const [key, color] of Object.entries(colors)) output[key] = scaleHexColor(color, brightness);
    return output;
  }

  function hexRgb(value) {
    const hex = value.replace('#', '');
    return [0, 2, 4].map(offset => parseInt(hex.slice(offset, offset + 2), 16))
  }

  function paletteRgb(colors, position, gradient = true) {
    const palette = (colors?.length ? colors : ['#ff0000']).map(hexRgb);
    if (!gradient || palette.length === 1) return palette[0];
    const scaled = ((position % 1) + 1) % 1 * (palette.length - 1),
      index = Math.floor(scaled),
      amount = scaled - index,
      next = Math.min(index + 1, palette.length - 1);
    return palette[index].map((value, channel) => Math.round(value + (palette[next][channel] - value) * amount))
  }

  function layerPixel(layer, key, x, y, index, audioAmount, animationPhase = 0) {
    if (layer.enabled === false || (layer.keys?.length && !layer.keys.includes(key))) return null;
    const speed = Number(layer.speed || 1),
      phase = animationPhase * speed,
      direction = (layer.reverse ? -1 : 1) * (layer.bidirectional && y % 2 ? -1 : 1),
      dx = x - 6.5 - Number(layer.center_x || 0),
      dy = y - 2 - Number(layer.center_y || 0),
      angle = (Math.atan2(dy, dx) * 180 / Math.PI + 360 + Number(layer.angle || 0)) % 360,
      distance = Math.sqrt(dx * dx + dy * dy),
      band = 200 / Math.max(50, Number(layer.bandwidth || 200)),
      gap = Number(layer.gap || 0) / 100,
      density = Math.max(1, Number(layer.number || 5));
    let position = 0.95,
      light = 1;
    if (layer.mode === 'wave') position = (Math.sin((x * band + direction * phase / 8) + gap) + 1) / 2;
    else if (layer.mode === 'conic') position = (angle + direction * phase * 2) % 360 / 360;
    else if (layer.mode === 'spiral') position = (angle + distance * 35 * band + direction * phase * 2) % 360 / 360;
    else if (layer.mode === 'cycle') position = (index / 70 + direction * phase / 120) % 1;
    else if (layer.mode === 'linear-wave') position = (x * band / 8 + y / 14 + Number(layer.angle || 0) / 360 + direction * phase / 100 + gap) % 1;
    else if (layer.mode === 'ripple') position = (distance * band / 5 - direction * phase / 80 + gap) % 1;
    else if (layer.mode === 'breathe') {
      position = 0;
      light = .25 + .75 * (1 + Math.sin(phase / 18)) / 2
    } else if (layer.mode === 'rain') {
      position = .55;
      light = ((x * 19 + y * 37 + direction * phase * density) % 100) > 100 - density * 6 ? 1 : .08
    } else if (layer.mode === 'fire') {
      position = Math.random() * .14;
      light = .25 + Math.random() * .06 * Math.max(1, Number(layer.fire || 1))
    } else if (layer.mode === 'trigger') {
      position = .95;
      light = ((index * 31 + phase * 3) % 97) > 90 ? 1 : .08
    }
    if (layer.bump) light *= 1 - Math.abs((((position % 1) + 1) % 1) * 2 - 1);
    if (layer.audio) light *= Math.max(0, Math.min(1, audioAmount));
    const color = paletteRgb(layer.colors, position, layer.gradient !== false),
      alpha = Math.max(0, Math.min(1, Number(layer.opacity ?? 100) / 100 * light));
    return {
      color,
      alpha
    }
  }

  function composeFrame(rows, layers, audio, settings = {}, phase = 0) {
    // The row loop that rasterises every layer onto the keyboard. It lives
    // here rather than beside the DOM because the spectrum gate below is the
    // part that has been wrong before and the part worth testing.
    const grid = Array.isArray(rows) ? rows : [];
    const stack = Array.isArray(layers) ? layers : [];
    const colors = {};
    let index = 0;
    grid.forEach((row, y) => (Array.isArray(row) ? row : []).forEach((key, x) => {
      const pixels = [];
      for (const layer of stack) {
        const influence = layer && layer.audio ?
          audioInfluence(audio, settings.audio_mode, x / 14, bandRowPosition(y, grid.length)) :
          1;
        const pixel = layerPixel(layer, key, x, y, index, influence, phase);
        if (pixel) pixels.push(pixel);
      }
      const output = compositePixels(pixels);
      colors[key] = "#" + output.map(value => value.toString(16).padStart(2, "0")).join("");
      index += 1;
    }));
    return applyMasterBrightness(colors, settings.master_brightness);
  }

  function blendRgb(base, top, alpha) {
    const amount = clamp(alpha);
    return [0, 1, 2].map(index => Math.round(
      clamp(base?.[index], 0, 255) * (1 - amount) +
      clamp(top?.[index], 0, 255) * amount
    ));
  }

  function compositePixels(pixels, base = [0, 0, 0]) {
    let output = [0, 1, 2].map(index => Math.round(clamp(base?.[index], 0, 255)));
    for (const pixel of Array.isArray(pixels) ? pixels : []) {
      if (!pixel || pixel.enabled === false) continue;
      output = blendRgb(output, pixel.color, pixel.alpha);
    }
    return output;
  }

  return {
    DEFAULT_BAND_COUNT,
    applyMasterBrightness,
    audioInfluence,
    bandRowPosition,
    blendRgb,
    composeFrame,
    compositePixels,
    hexRgb,
    layerPixel,
    paletteRgb,
    emptyAudioFrame,
    preferredAudioSource,
    processAudioSnapshot,
    resampleBands,
    scaleHexColor
  };
});
