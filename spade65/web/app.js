const token = document.querySelector('meta[name="spade65-token"]').content;
const $ = id => document.getElementById(id);
const layoutState = window.Spade65LayoutState;
const macroRules = window.Spade65MacroRules;
const keyEvents = window.Spade65KeyEvents;
const usagePicker = window.Spade65UsagePicker;
const externalLinks = window.Spade65ExternalLinks;
const liveEffects = window.Spade65LiveEffects;
const copyText = window.Spade65Clipboard.createCopier(
  () => window.pywebview?.api,
  () => navigator.clipboard,
  document
);
let meta = null,
  profile = null,
  currentLayer = 'normal',
  selectedKey = null,
  colorKeys = new Set(),
  activeMacro = 0,
  activeAppLayer = 0,
  animationTimer = null,
  animationPhase = 0,
  timelineTimer = null,
  timelineIndex = 0,
  streamBusy = false,
  audioContext = null,
  audioAnalyser = null,
  audioStream = null,
  audioSourceEntries = [],
  audioSystemError = null,
  audioNativeRunning = false,
  audioRawSnapshot = null,
  audioFrame = liveEffects.emptyAudioFrame(),
  audioGeneration = 0,
  audioStartPromise = null,
  animationStarting = false,
  animationGeneration = 0,
  layoutVariant = layoutState.DEFAULT_LAYOUT,
  testerPressed = new Set(),
  testerSeen = new Set(),
  activeLayoutKey = null,
  statusFetchPromise = null,
  deviceSnapshot = '',
  devicePollBusy = false,
  recordingMacro = false,
  recordingMacroTarget = null,
  pendingMacroAssignment = null,
  recordLast = 0,
  recordPressed = new Set(),
  usagePickerItems = [],
  usagePickerActive = -1,
  desktopIntegration = null,
  lightingDraft = null,
  lightingDraftProfile = null,
  lightingMode = null,
  keymapDraftDirty = false,
  assignmentEditorKey = null,
  assignmentEditorDirty = false,
  appliedMacroSnapshot = null,
  livePreviewColors = null;
const I18N_STORAGE_KEY = 'spade65-language',
  DEFAULT_LANGUAGE = 'en';
const DEFAULT_LIGHTING = Object.freeze({
  effect: 'neon-stream',
  brightness: 4,
  speed: 5,
  color_index: 0,
  multicolor: true
});
const DEFAULT_DEBOUNCE_MS = 5;
const DEFAULT_LIVE_SETTINGS = Object.freeze({
  master_brightness: 100,
  audio_source: '',
  audio_mode: 'spectrum',
  audio_sensitivity: 1000,
  audio_noise_gate: 2,
  audio_smoothing: 65
});
const LAYOUT_STORAGE_KEY = 'spade65-device-layouts-v1',
  LEGACY_LAYOUT_STORAGE_KEY = 'spade65-layout';
const defaultLanguages = [{
  code: 'en',
  name: 'English'
}, {
  code: 'id',
  name: 'Bahasa Indonesia'
}];
let languageManifest = {
    default: DEFAULT_LANGUAGE,
    languages: defaultLanguages
  },
  currentLanguage = DEFAULT_LANGUAGE;
const catalogs = {};
const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
const cloneJson = value => JSON.parse(JSON.stringify(value));
const PAGE_HEADERS = Object.freeze({
  device: {
    title: 'nav.device',
    subtitle: 'subtitle.device'
  },
  keymap: {
    title: 'nav.keyboard',
    subtitle: 'subtitle.keymap'
  },
  tester: {
    title: 'nav.tester',
    subtitle: 'subtitle.tester'
  },
  lighting: {
    title: 'nav.lighting',
    subtitle: 'subtitle.lighting'
  },
  macros: {
    title: 'nav.macros',
    subtitle: 'subtitle.macros'
  },
  settings: {
    title: 'nav.settings',
    subtitle: 'subtitle.settings'
  },
  diagnostics: {
    title: 'nav.diagnostics',
    subtitle: 'subtitle.diagnostics'
  },
  about: {
    title: 'nav.about',
    subtitle: 'subtitle.about'
  }
});

function interpolate(value, variables = {}) {
  return String(value).replace(/\{([A-Za-z0-9_]+)\}/g, (match, key) => hasOwn(variables, key) ? String(variables[key]) : match)
}

function t(key, variables = {}) {
  if (typeof key !== 'string' || !key) return '';
  return interpolate(catalogs[currentLanguage]?.[key] ?? catalogs[DEFAULT_LANGUAGE]?.[key] ?? key, variables)
}
async function fetchJson(path) {
  const response = await fetch(path, {
    cache: 'no-store'
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const value = await response.json();
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Invalid locale JSON: ${path}`);
  return value
}

function seedEnglishCatalog() {
  const seeded = {};
  document.querySelectorAll('[data-i18n]').forEach(element => seeded[element.dataset.i18n] = element.textContent);
  document.querySelectorAll('[data-i18n-placeholder]').forEach(element => seeded[element.dataset.i18nPlaceholder] = element.placeholder);
  document.querySelectorAll('[data-i18n-title]').forEach(element => seeded[element.dataset.i18nTitle] = element.title);
  document.querySelectorAll('[data-i18n-aria-label]').forEach(element => seeded[element.dataset.i18nAriaLabel] = element.getAttribute('aria-label') || '');
  catalogs[DEFAULT_LANGUAGE] = seeded
}

function validManifest(value) {
  if (!Array.isArray(value.languages) || !value.languages.length) return false;
  const codes = value.languages.map(item => item?.code);
  return value.languages.every(item => item && /^[A-Za-z0-9_-]+$/.test(item.code) && typeof item.name === 'string') && new Set(codes).size === codes.length && codes.includes(value.default)
}

function applyTranslations(root = document) {
  root.querySelectorAll('[data-i18n]').forEach(element => element.textContent = t(element.dataset.i18n));
  root.querySelectorAll('[data-i18n-placeholder]').forEach(element => element.placeholder = t(element.dataset.i18nPlaceholder));
  root.querySelectorAll('[data-i18n-title]').forEach(element => element.title = t(element.dataset.i18nTitle));
  root.querySelectorAll('[data-i18n-aria-label]').forEach(element => element.setAttribute('aria-label', t(element.dataset.i18nAriaLabel)));
  document.documentElement.lang = currentLanguage;
  document.title = t('app.title')
}

function updatePageHeader(page) {
  const header = PAGE_HEADERS[page] || PAGE_HEADERS.device;
  $('pageTitle').dataset.i18n = header.title;
  $('pageSubtitle').dataset.i18n = header.subtitle;
  $('pageTitle').textContent = t(header.title);
  $('pageSubtitle').textContent = t(header.subtitle)
}

function renderLanguageOptions() {
  const select = $('languageSelect');
  select.innerHTML = '';
  for (const item of languageManifest.languages) {
    const option = document.createElement('option');
    option.value = item.code;
    option.textContent = item.name;
    select.append(option)
  }
  select.value = currentLanguage
}
async function setLanguage(requested, persist = true) {
  const supported = new Set(languageManifest.languages.map(item => item.code)),
    target = supported.has(requested) ? requested : (languageManifest.default || DEFAULT_LANGUAGE);
  if (!catalogs[DEFAULT_LANGUAGE]) catalogs[DEFAULT_LANGUAGE] = await fetchJson('/locales/en.json');
  let selected = target;
  if (target !== DEFAULT_LANGUAGE && !catalogs[target]) {
    try {
      catalogs[target] = await fetchJson(`/locales/${target}.json`)
    } catch (error) {
      console.warn(`Unable to load locale ${target}; using English`, error);
      selected = DEFAULT_LANGUAGE
    }
  }
  currentLanguage = selected;
  if (persist) localStorage.setItem(I18N_STORAGE_KEY, currentLanguage);
  renderLanguageOptions();
  applyTranslations();
  renderLocalizedDynamic()
}

function renderLocalizedDynamic() {
  const active = document.querySelector('#nav button.active');
  if (active) updatePageHeader(active.dataset.page);
  renderAbout();
  renderDesktopIntegration();
  renderServiceSetup();
  renderTester();
  if (!meta || !profile) return;
  renderSavedProfiles($('savedProfile').value);
  renderEffects();
  renderLightingControls();
  renderUsageList();
  renderMacros();
  renderKeyboard();
  renderAppLayers();
  renderAudioSources();
  refreshLivePreview();
  renderTimeline();
  renderConnectionStatus();
  renderDiagnostics();
  renderLiveEffectStatus();
  $('animationBtn').textContent = t(animationTimer ? 'action.stopLivePreview' : 'action.startLivePreview')
}
async function initI18n() {
  seedEnglishCatalog();
  try {
    const manifest = await fetchJson('/locales/index.json');
    if (validManifest(manifest)) languageManifest = manifest
  } catch (error) {
    console.warn('Unable to load locale manifest; using built-in language list', error)
  }
  try {
    catalogs[DEFAULT_LANGUAGE] = {
      ...catalogs[DEFAULT_LANGUAGE],
      ...await fetchJson('/locales/en.json')
    }
  } catch (error) {
    console.warn('Unable to load English locale catalog; using document text', error)
  }
  const saved = localStorage.getItem(I18N_STORAGE_KEY) || languageManifest.default || DEFAULT_LANGUAGE;
  await setLanguage(saved, false)
}
const rows = [
  ['esc', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9', 'n0', 'minus', 'plus', 'bksp'],
  ['tab', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', 'lqu', 'rqu', 'k29', 'delete'],
  ['caps', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'sem', 'quo', 'k42', 'enter', 'pageup'],
  ['lshift', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'comma', 'dot', 'qmark', 'rshift', 'up', 'pagedown'],
  ['lctrl', 'win', 'lalt', 'lspace', 'ralt', 'mspace', 'rspace', 'fn', 'rctrl', 'left', 'down', 'right']
];
const titles = {
  esc: 'Esc',
  bksp: 'Backspace',
  caps: 'Caps',
  lshift: 'L Shift',
  rshift: 'R Shift',
  lctrl: 'L Ctrl',
  rctrl: 'R Ctrl',
  lalt: 'L Alt',
  ralt: 'R Alt',
  lspace: 'Space',
  mspace: 'Space',
  rspace: 'Space',
  pageup: 'Pg Up',
  pagedown: 'Pg Dn',
  lqu: '[',
  rqu: ']',
  sem: ';',
  quo: "'",
  qmark: '/',
  comma: ',',
  dot: '.',
  minus: '-',
  plus: '=',
  win: 'Win',
  k29: '\\',
  k42: '\\'
};
const isoPositions = [
  [70, 21, 35, 35],
  [109, 21, 35, 35],
  [148, 21, 35, 35],
  [186, 21, 35, 35],
  [226, 21, 35, 35],
  [264, 21, 35, 35],
  [303, 21, 35, 35],
  [342, 21, 35, 35],
  [381, 21, 35, 35],
  [420, 21, 35, 35],
  [458, 21, 35, 35],
  [497, 21, 35, 35],
  [536, 21, 35, 35],
  [576, 21, 70, 35],
  [70, 61, 55, 35],
  [128, 61, 35, 35],
  [168, 61, 35, 35],
  [206, 61, 35, 35],
  [245, 61, 35, 35],
  [284, 61, 35, 35],
  [323, 61, 35, 35],
  [362, 61, 35, 35],
  [400, 61, 35, 35],
  [439, 61, 35, 35],
  [478, 61, 35, 35],
  [517, 61, 35, 35],
  [556, 61, 35, 35],
  [604, 61, 0, 0],
  [652, 61, 35, 35],
  [70, 100, 64, 35],
  [138, 100, 35, 35],
  [177, 100, 35, 35],
  [215, 100, 35, 35],
  [254, 100, 35, 35],
  [293, 100, 35, 35],
  [332, 100, 35, 35],
  [371, 100, 35, 35],
  [410, 100, 35, 35],
  [448, 100, 35, 35],
  [487, 100, 35, 35],
  [526, 100, 35, 35],
  [565, 100, 35, 35],
  [606, 61, 41, 74],
  [652, 100, 35, 35],
  [70, 138, 83, 35],
  [157, 138, 35, 35],
  [196, 138, 35, 35],
  [235, 138, 35, 35],
  [274, 138, 35, 35],
  [313, 138, 35, 35],
  [352, 138, 35, 35],
  [390, 138, 35, 35],
  [430, 138, 35, 35],
  [468, 138, 35, 35],
  [507, 138, 35, 35],
  [546, 138, 64, 35],
  [614, 138, 35, 35],
  [652, 138, 35, 35],
  [70, 177, 45, 35],
  [118, 177, 45, 35],
  [167, 177, 45, 35],
  [216, 177, 0, 0],
  [507, 177, 45, 35],
  [216, 177, 239, 35],
  [352, 177, 0, 0],
  [458, 177, 45, 35],
  [507, 177, 0, 0],
  [575, 177, 35, 35],
  [614, 177, 35, 35],
  [652, 177, 35, 35]
];
const ansiPositions = [
  [70, 23, 35, 35],
  [109, 23, 35, 35],
  [148, 23, 35, 35],
  [186, 23, 35, 35],
  [225, 23, 35, 35],
  [264, 23, 35, 35],
  [303, 23, 35, 35],
  [342, 23, 35, 35],
  [381, 23, 35, 35],
  [420, 23, 35, 35],
  [458, 23, 35, 35],
  [497, 23, 35, 35],
  [536, 23, 35, 35],
  [577, 23, 70, 35],
  [70, 61, 55, 35],
  [128, 61, 35, 35],
  [167, 61, 35, 35],
  [206, 61, 35, 35],
  [245, 61, 35, 35],
  [284, 61, 35, 35],
  [323, 61, 35, 35],
  [362, 61, 35, 35],
  [400, 61, 35, 35],
  [439, 61, 35, 35],
  [478, 61, 35, 35],
  [517, 61, 35, 35],
  [556, 61, 35, 35],
  [595, 61, 54, 35],
  [652, 61, 35, 35],
  [70, 100, 65, 35],
  [138, 100, 35, 35],
  [177, 100, 35, 35],
  [216, 100, 35, 35],
  [255, 100, 35, 35],
  [293, 100, 35, 35],
  [332, 100, 35, 35],
  [371, 100, 35, 35],
  [410, 100, 35, 35],
  [449, 100, 35, 35],
  [488, 100, 35, 35],
  [526, 100, 35, 35],
  [548, 100, 0, 0],
  [566, 100, 82, 35],
  [652, 100, 35, 35],
  [70, 138, 84, 35],
  [158, 138, 35, 35],
  [197, 138, 35, 35],
  [235, 138, 35, 35],
  [274, 138, 35, 35],
  [313, 138, 35, 35],
  [352, 138, 35, 35],
  [391, 138, 35, 35],
  [430, 138, 35, 35],
  [468, 138, 35, 35],
  [507, 138, 35, 35],
  [546, 138, 64, 35],
  [614, 138, 35, 35],
  [652, 138, 35, 35],
  [70, 177, 45, 35],
  [118, 177, 45, 35],
  [166, 177, 45, 35],
  [216, 177, 0, 0],
  [507, 177, 45, 35],
  [216, 177, 239, 35],
  [353, 177, 0, 0],
  [459, 177, 45, 35],
  [507, 177, 0, 0],
  [575, 177, 35, 35],
  [614, 177, 35, 35],
  [652, 177, 35, 35]
];
const splitPositions = {
  // A split spacebar only changes which caps cover the three space slots. The
  // matrix belongs to the PCB, so ralt keeps the position right of Fn that the
  // hardware reported, and mspace fills the gap between the space segments.
  iso: {
    61: [216, 177, 82, 35],
    63: [303, 177, 45, 35],
    64: [352, 177, 102, 35]
  },
  ansi: {
    61: [216, 177, 82, 35],
    63: [303, 177, 45, 35],
    64: [353, 177, 103, 35]
  }
};

function keyPosition(index, variant = layoutVariant) {
  const family = variant.startsWith('iso') ? 'iso' : 'ansi',
    positions = family === 'iso' ? isoPositions : ansiPositions;
  if (variant.endsWith('split') && splitPositions[family][index]) return splitPositions[family][index];
  return positions[index]
}

function keyVisibleInLayout(key, variant = layoutVariant) {
  const index = rows.flat().indexOf(key);
  if (index < 0) return false;
  const [, , width, height] = keyPosition(index, variant);
  return Boolean(width && height)
}

async function api(action, data = {}, method = 'POST') {
  const options = {
    method,
    headers: {
      'X-Spade65-Token': token
    }
  };
  if (method === 'POST') {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(data)
  }
  const response = await fetch(`/api/${action}`, options);
  const result = await response.json();
  if (!response.ok || result.ok === false) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}

function fetchGuiStatus() {
  if (!statusFetchPromise) statusFetchPromise = api('status', {}, 'GET').finally(() => statusFetchPromise = null);
  return statusFetchPromise
}

function deviceSignature(devices) {
  return JSON.stringify((devices || []).map(item => [item.path, item.bus, item.vid, item.pid, item.usages, item.readonly?.battery_percent]).sort((left, right) => String(left[0]).localeCompare(String(right[0]))))
}

function toast(message, error = false) {
  const el = $('toast');
  el.textContent = message;
  el.className = `show${error?' error':''}`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.className = '', 3500)
}
async function quitApplication() {
  if (!confirm(t('app.confirmQuit'))) return;
  try {
    await api('quit');
    $('quitBtn').disabled = true;
    toast(t('app.shuttingDown'))
  } catch (error) {
    toast(error.message, true)
  }
}

function device() {
  return $('deviceSelect').value || null
}

function selectedLayoutDevice() {
  const path = device();
  return path && meta ? meta.devices.find(item => item.path === path && item.usages.includes(layoutState.CONFIG_USAGE)) || null : null
}

function selectedDevice() {
  const path = device();
  return path && meta ? meta.devices.find(item => item.path === path) || null : null
}

function configurationReady() {
  const selected = selectedDevice();
  return Boolean(selected && selected.configuration_status === 'descriptor-gated' && selected.usages.includes(layoutState.CONFIG_USAGE))
}

function streamingReady() {
  const selected = selectedDevice();
  return Boolean(selected && selected.pid === '0351' && selected.usages.includes('ff55:0202'))
}

function storedDeviceLayouts() {
  return layoutState.parseDeviceLayouts(localStorage.getItem(LAYOUT_STORAGE_KEY))
}

function saveDeviceLayouts(layouts) {
  localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layoutState.parseDeviceLayouts(layouts)))
}

function applyLayoutDisplay(layout, connected, render = true) {
  const previousLayout = layoutVariant,
    nextLayout = layoutState.isValidLayout(layout) ? layout : layoutState.DEFAULT_LAYOUT,
    selectionHidden = selectedKey && !keyVisibleInLayout(selectedKey, nextLayout);
  if (render && selectionHidden && assignmentEditorDirty && previousLayout !== nextLayout && !confirm(t('keymap.confirmLayoutDiscard', {
      key: keyLabel(selectedKey)
    }))) {
    for (const id of ['layoutVariant', 'lightingLayoutVariant']) $(id).value = previousLayout;
    return false
  }
  layoutVariant = nextLayout;
  if (selectionHidden) {
    if (assignmentEditorDirty && previousLayout !== nextLayout) toast(t('keymap.hiddenDraftDiscarded'), true);
    selectedKey = null;
    assignmentEditorKey = null;
    assignmentEditorDirty = false
  }
  colorKeys = new Set([...colorKeys].filter(key => keyVisibleInLayout(key, nextLayout)));
  for (const id of ['layoutVariant', 'lightingLayoutVariant']) {
    const select = $(id);
    select.value = layoutVariant;
    select.disabled = !connected
  }
  const sourceKey = connected ? 'layout.detected' : 'layout.noDevice';
  for (const id of ['keymapLayoutSource', 'lightingLayoutSource']) {
    const source = $(id);
    source.dataset.i18n = sourceKey;
    source.textContent = t(sourceKey)
  }
  if (render && profile) {
    renderKeyboard();
    renderColorKeyboard()
  }
  // Which keys exist to test depends on the selected layout.
  if (render) renderTester();
  return true
}

function syncLayoutFromSelectedDevice(render = true) {
  const result = layoutState.resolveLayout(selectedLayoutDevice(), storedDeviceLayouts(), localStorage.getItem(LEGACY_LAYOUT_STORAGE_KEY));
  activeLayoutKey = result.key;
  if (!applyLayoutDisplay(result.layout, result.connected, render)) return false;
  if (result.connected) {
    if (result.changed) saveDeviceLayouts(result.layouts);
    localStorage.removeItem(LEGACY_LAYOUT_STORAGE_KEY)
  }
  return true
}

function chooseLayout(value) {
  if (!activeLayoutKey || !layoutState.isValidLayout(value)) {
    syncLayoutFromSelectedDevice();
    return
  }
  const layouts = storedDeviceLayouts();
  if (!applyLayoutDisplay(value, true)) return;
  layouts[activeLayoutKey] = value;
  saveDeviceLayouts(layouts);
}

function restoreLayoutPreferences(data) {
  const legacy = layoutState.isValidLayout(data.layout) ? data.layout : null,
    hasMap = data.device_layouts && typeof data.device_layouts === 'object' && !Array.isArray(data.device_layouts),
    key = layoutState.deviceKey(selectedLayoutDevice());
  if (hasMap) {
    const layouts = layoutState.parseDeviceLayouts(data.device_layouts);
    if (key && legacy && !layouts[key]) layouts[key] = legacy;
    saveDeviceLayouts(layouts);
    if (!key && legacy && !Object.keys(layouts).length) localStorage.setItem(LEGACY_LAYOUT_STORAGE_KEY, legacy);
    else localStorage.removeItem(LEGACY_LAYOUT_STORAGE_KEY)
  } else if (legacy) {
    if (key) {
      const layouts = storedDeviceLayouts();
      layouts[key] = legacy;
      saveDeviceLayouts(layouts);
      localStorage.removeItem(LEGACY_LAYOUT_STORAGE_KEY)
    } else localStorage.setItem(LEGACY_LAYOUT_STORAGE_KEY, legacy)
  }
  syncLayoutFromSelectedDevice(false)
}

function actionPayload(extra = {}) {
  return {
    device: device(),
    ...extra
  }
}

function storedProfiles() {
  try {
    const value = JSON.parse(localStorage.getItem('spade65-profiles') || '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
  } catch {
    return {}
  }
}

function renderSavedProfiles(selected = '') {
  const select = $('savedProfile'),
    items = storedProfiles();
  select.innerHTML = '';
  const unsaved = document.createElement('option');
  unsaved.value = '';
  unsaved.textContent = t('profile.unsaved');
  select.append(unsaved);
  Object.keys(items).sort().forEach(name => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    select.append(option)
  });
  select.value = selected
}
async function loadSavedProfile(name) {
  if (!name) return;
  try {
    const item = migrateProfileLighting(cloneJson(storedProfiles()[name]));
    await api('validate', {
      profile: item
    });
    if (!mayLeaveAssignmentEditor(currentLayer, null)) {
      renderSavedProfiles($('profileName').value);
      return
    }
    profile = item;
    $('profileName').value = name;
    renderAllEditors();
    renderTester();
    toast(t('profile.loaded', {
      name
    }))
  } catch (error) {
    renderSavedProfiles();
    toast(error.message, true)
  }
}
async function saveProfile() {
  if (!requireCommittedAssignment()) return;
  try {
    await api('validate', {
      profile
    });
    const name = $('profileName').value.trim();
    if (!name) return toast(t('profile.nameRequired'), true);
    const items = storedProfiles();
    items[name] = cloneJson(profile);
    localStorage.setItem('spade65-profiles', JSON.stringify(items));
    renderSavedProfiles(name);
    toast(t('profile.savedLocal', {
      name
    }))
  } catch (error) {
    toast(error.message, true)
  }
}

function deleteSavedProfile() {
  const name = $('savedProfile').value;
  if (!name) return toast(t('profile.selectSaved'), true);
  if (!confirm(t('profile.confirmDelete', {
      name
    }))) return;
  const items = storedProfiles();
  delete items[name];
  localStorage.setItem('spade65-profiles', JSON.stringify(items));
  renderSavedProfiles();
  toast(t('profile.deleted', {
    name
  }))
}

async function refresh() {
  try {
    meta = await fetchGuiStatus();
    deviceSnapshot = deviceSignature(meta.devices);
    if (!profile) profile = cloneJson(meta.profile);
    migrateProfileLighting(profile);
    renderDevices();
    syncLayoutFromSelectedDevice(false);
    renderEffects();
    renderLightingControls();
    renderDebounceControl();
    renderUsageList();
    renderSavedProfiles($('savedProfile').value);
    renderKeyboard();
    renderColorKeyboard();
    renderMacros();
    renderAppLayers();
    renderTimeline();
    renderDiagnostics();
    renderAbout();
    renderServiceSetup();
    renderConnectionStatus()
  } catch (error) {
    renderLightingConnectionStatus(true);
    $('applyProfileBtn').disabled = true;
    toast(error.message, true)
  }
}
async function pollDeviceChanges() {
  if (devicePollBusy || document.hidden || !meta) return;
  devicePollBusy = true;
  try {
    const status = await fetchGuiStatus(),
      snapshot = deviceSignature(status.devices);
    if (snapshot === deviceSnapshot) return;
    meta = {
      ...meta,
      devices: status.devices
    };
    deviceSnapshot = snapshot;
    renderDevices();
    syncLayoutFromSelectedDevice();
    renderDiagnostics();
    renderConnectionStatus()
  } catch (error) {
    console.warn('Unable to refresh Spade65 device presence', error)
  } finally {
    devicePollBusy = false
  }
}

function renderConnectionStatus() {
  if (!meta) return;
  const connected = meta.devices.length > 0,
    readOnlyDevice = connected && meta.devices.every(d => d.configuration_status === 'unsupported-read-only'),
    primary = layoutState.primaryDevice(meta.devices),
    battery = primary?.readonly?.battery_percent,
    hasBattery = Number.isInteger(battery) && battery >= 0 && battery <= 100,
    batteryBadge = $('batteryBadge');
  $('connectionDot').classList.toggle('online', connected);
  $('connectionText').textContent = connected ? t(readOnlyDevice ? 'status.detectedReadOnly' : 'status.connected', {
    name: primary.name
  }) : t('status.noDevice');
  $('transportBadge').textContent = connected ? `${primary.transport} ${primary.vid}:${primary.pid}` : t('status.notConnected');
  batteryBadge.hidden = !hasBattery;
  batteryBadge.textContent = hasBattery ? t('status.battery', {
    percent: battery
  }) : '';
  $('descriptorBadge').textContent = readOnlyDevice ? t('status.unsupportedReadOnly') : meta.devices.some(d => d.reports.some(r => r.kind === 'feature' && r.id === 7 && r.bytes === 620)) ? t('status.descriptorVerified') : t('status.configUnavailable');
  renderLightingConnectionStatus();
  setProfileControlsRecordingLocked()
}

function renderDevices() {
  const select = $('deviceSelect'),
    old = select.value,
    configurable = meta.devices.filter(d => d.configuration_status === 'descriptor-gated' && d.usages.includes('ff02:0001'));
  select.innerHTML = '';
  for (const item of configurable) {
    const o = document.createElement('option');
    o.value = item.path;
    o.textContent = `${item.name} · ${item.transport} · ${item.path}`;
    select.append(o)
  }
  if ([...select.options].some(o => o.value === old)) select.value = old;
  select.disabled = configurable.length === 0;
  $('applyProfileBtn').disabled = configurable.length === 0
}

function builtInEffects() {
  return meta.effects.filter(effect => effect !== 'custom')
}

function renderEffects() {
  const select = $('effectSelect'),
    selected = select.value || DEFAULT_LIGHTING.effect,
    effects = builtInEffects();
  select.innerHTML = '';
  for (const effect of effects) {
    const o = document.createElement('option'),
      key = `effect.${effect}`,
      translated = t(key);
    o.value = effect;
    o.textContent = translated === key ? effect.replaceAll('-', ' ') : translated;
    select.append(o)
  }
  select.value = effects.includes(selected) ? selected : DEFAULT_LIGHTING.effect
}

function normalizedLighting(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const baseFields = ['effect', 'brightness', 'speed', 'color_index', 'multicolor'],
    fields = value.effect === 'custom' ? [...baseFields, 'colors'] : baseFields,
    invalid = Object.keys(value).length !== fields.length ||
    fields.some(field => !hasOwn(value, field)) ||
    !meta?.effects.includes(value.effect) ||
    !Number.isInteger(value.brightness) || value.brightness < 0 || value.brightness > 4 ||
    !Number.isInteger(value.speed) || value.speed < 1 || value.speed > 5 ||
    !Number.isInteger(value.color_index) || value.color_index < 0 || value.color_index > 7 ||
    typeof value.multicolor !== 'boolean' ||
    (value.effect === 'custom' && (!value.colors || typeof value.colors !== 'object' || Array.isArray(value.colors)));
  if (invalid) return null;
  const lighting = {
    effect: value.effect,
    brightness: value.brightness,
    speed: value.speed,
    color_index: value.color_index,
    multicolor: value.multicolor
  };
  if (value.effect === 'custom') lighting.colors = cloneJson(value.colors);
  return lighting
}

function migrateProfileLighting(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
  // A legacy top-level color table is an editable draft, not evidence that it
  // was the last lighting state applied to hardware.  Default it explicitly
  // instead of invisibly selecting a sparse custom palette.
  if (!hasOwn(value, 'lighting') || value.lighting === null) value.lighting = cloneJson(DEFAULT_LIGHTING);
  return value
}

function savedLighting() {
  return normalizedLighting(profile?.lighting)
}

function lightingTarget() {
  return {
    profile,
    savedName: $('savedProfile').value
  }
}

function resetLightingDraft() {
  migrateProfileLighting(profile);
  lightingDraft = cloneJson(savedLighting() || DEFAULT_LIGHTING);
  lightingDraftProfile = profile
}

function ensureLightingDraft() {
  if (lightingDraftProfile !== profile || !normalizedLighting(lightingDraft)) resetLightingDraft();
  return lightingDraft
}

function lightingForProfileApply() {
  // The visible mode owns the draft. Controls from another, currently hidden
  // mode may contain newer values and must never leak into a scoped apply.
  return cloneJson(ensureLightingDraft())
}

function selectBuiltInLightingDraft() {
  lightingDraft = lightingFromControls();
  lightingDraftProfile = profile;
  setLightingMode('preset');
  renderLightingIntent()
}

function selectCustomLightingDraft() {
  setLightingMode('per-key');
  if (!Object.keys(profile.colors).length) {
    lightingDraft = cloneJson(savedLighting() || DEFAULT_LIGHTING);
    lightingDraftProfile = profile;
    renderLightingIntent();
    return false
  }
  const controls = lightingFromControls();
  lightingDraft = {
    ...controls,
    effect: 'custom',
    colors: cloneJson(profile.colors)
  };
  lightingDraftProfile = profile;
  renderLightingIntent();
  return true
}

function updateLightingDraftParameters() {
  const controls = lightingFromControls(),
    draft = ensureLightingDraft();
  lightingDraft = lightingMode === 'per-key' || (draft.effect === 'custom' && lightingMode !== 'preset') ? {
    ...controls,
    effect: 'custom',
    colors: cloneJson(draft.colors)
  } : controls;
  lightingDraftProfile = profile;
  renderLightingIntent()
}

function lightingValuesMatch(left, right) {
  return Boolean(left && right && JSON.stringify(left) === JSON.stringify(right))
}

function renderLightingIntent() {
  const lighting = normalizedLighting(lightingDraft) || savedLighting() || DEFAULT_LIGHTING,
    changed = !lightingValuesMatch(lighting, savedLighting()),
    effectKey = `effect.${lighting.effect}`,
    translatedEffect = t(effectKey),
    intent = lighting.effect === 'custom' ?
    t('lighting.snapshotCustom') :
    t('lighting.snapshotBuiltIn', {
      effect: translatedEffect === effectKey ? lighting.effect.replaceAll('-', ' ') : translatedEffect
    });
  $('lightingSnapshotStatus').textContent = `${intent} · ${t(changed?'lighting.draftChanged':'lighting.draftMatches')}`;
  $('lightingSnapshotStatus').classList.toggle('changed', changed);
  renderPresetOptionState();
  renderLightingConnectionStatus()
}

function chooseLightingMode(mode) {
  if (mode === 'preset') return selectBuiltInLightingDraft();
  if (mode === 'per-key') return selectCustomLightingDraft();
  setLightingMode('live')
}

function setLightingMode(mode) {
  if (!['preset', 'per-key', 'live'].includes(mode)) mode = 'preset';
  if (lightingMode === 'live' && mode !== 'live') {
    if (animationTimer || animationStarting) stopAnimation();
    if (timelineTimer) stopTimeline()
  }
  lightingMode = mode;
  document.querySelectorAll('[data-lighting-mode]').forEach(button => {
    const active = button.dataset.lightingMode === mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1
  });
  document.querySelectorAll('[data-lighting-panel]').forEach(panel => panel.hidden = panel.dataset.lightingPanel !== mode)
}

function renderLightingConnectionStatus(forceOffline = false) {
  const target = $('lightingConnectionStatus');
  if (!target) return;
  const configurable = !forceOffline && configurationReady(),
    streamable = !forceOffline && streamingReady();
  if (!streamable && (animationTimer || animationStarting || timelineTimer)) {
    if (animationTimer || animationStarting) stopAnimation();
    if (timelineTimer) stopTimeline()
  }
  target.textContent = t(!configurable ? 'lighting.connectionOffline' : streamable ? 'lighting.connectionReady' : 'lighting.connectionDongle');
  target.classList.toggle('success', configurable);
  $('applyEffectBtn').disabled = !configurable;
  $('applyColorsBtn').disabled = !configurable || !profile || Object.keys(profile.colors).length === 0;
  $('streamOnceBtn').disabled = !streamable;
  $('animationBtn').disabled = !streamable && !animationTimer;
  $('playTimelineBtn').disabled = !profile || !timeline().frames.length || (!streamable && !timelineTimer)
}

function renderLiveEffectStatus() {
  const target = $('liveEffectStatus');
  if (!target) return;
  target.classList.toggle('live', Boolean(animationTimer || timelineTimer));
  if (animationTimer) target.textContent = t('lighting.liveRunning', {
    fps: $('fps').value
  });
  else if (timelineTimer) target.textContent = t('lighting.timelineRunning');
  else target.textContent = t('lighting.liveStopped')
}

function rememberLighting(value, target) {
  const lighting = normalizedLighting(value);
  if (!lighting) return;
  target.profile.lighting = cloneJson(lighting);
  if (profile === target.profile) {
    lightingDraft = cloneJson(lighting);
    lightingDraftProfile = profile;
    renderLightingControls()
  }
  const name = target.savedName;
  if (!name) return;
  try {
    const items = storedProfiles();
    if (!hasOwn(items, name)) return;
    // Persist only the state that reached hardware. Unsaved keymap/macro edits
    // must not be folded into the named profile as a lighting side effect.
    items[name].lighting = cloneJson(lighting);
    if (lighting.effect === 'custom') items[name].colors = cloneJson(lighting.colors);
    localStorage.setItem('spade65-profiles', JSON.stringify(items))
  } catch (error) {
    console.warn('Unable to persist the lighting snapshot', error);
    setTimeout(() => toast(t('lighting.snapshotSaveFailed'), true), 0)
  }
}

function lightingFromControls() {
  const selected = $('effectSelect').value,
    effect = meta.effects.includes(selected) ? selected : DEFAULT_LIGHTING.effect,
    lighting = {
      effect,
      brightness: Number($('brightness').value),
      speed: Number($('speed').value),
      color_index: Number($('colorIndex').value),
      multicolor: $('multicolor').checked
    };
  if (effect === 'custom') lighting.colors = cloneJson(profile.colors);
  return lighting
}

function renderPresetOptionState() {
  const fixed = $('effectSelect').value === 'fixed',
    multicolor = $('multicolor').checked;
  $('multicolor').disabled = fixed;
  $('colorIndex').disabled = !fixed && multicolor;
  const hint = $('presetColorHint');
  if (hint) hint.textContent = t(fixed ? 'lighting.fixedColorHint' : multicolor ? 'lighting.multicolorHint' : 'lighting.singleColorHint')
}

function renderLightingControls() {
  migrateProfileLighting(profile);
  const lighting = ensureLightingDraft();
  $('effectSelect').value = builtInEffects().includes(lighting.effect) ? lighting.effect : DEFAULT_LIGHTING.effect;
  $('brightness').value = lighting.brightness;
  $('brightnessOut').value = lighting.brightness;
  $('speed').value = lighting.speed;
  $('speedOut').value = lighting.speed;
  $('colorIndex').value = lighting.color_index;
  $('multicolor').checked = lighting.multicolor;
  if (!lightingMode) setLightingMode(lighting.effect === 'custom' ? 'per-key' : 'preset');
  renderLightingIntent()
}

function renderUsageList() {
  const macroList = $('macroUsageList');
  macroList.innerHTML = '';
  for (const name of Object.keys(meta.usages).sort()) {
    const option = document.createElement('option');
    option.value = name;
    macroList.append(option)
  }
  closeUsagePicker();
  syncUsageSelection()
}

function usageGroupLabel(group) {
  const key = `usageGroup.${group}`,
    translated = t(key);
  return translated === key ? group : translated
}

function selectedUsage() {
  if (!meta) return null;
  return usagePicker.resolveUsage(meta.usages, $('usageInput').value)
}

function friendlyUsageName(value) {
  const key = `usage.${value}`,
    translated = t(key);
  if (translated !== key) return translated;
  return String(value).split('-').map(word => word.length === 1 ? word.toUpperCase() : word[0].toUpperCase() + word.slice(1)).join(' ')
}

function syncUsageSelection(preserveAdvanced = false) {
  if (!meta) return;
  const raw = $('usageInput').value.trim(),
    selected = selectedUsage(),
    label = selected ? `${friendlyUsageName(selected.name)} · ${selected.hex}` : raw ? t('keymap.customUsageValue', {
      value: raw
    }) : '';
  $('usageSearch').value = label;
  $('usageCurrent').textContent = raw ? t('keymap.selectedFunction', {
    value: label
  }) : t('keymap.noFunctionSelected');
  if (!preserveAdvanced) {
    $('customUsageInput').value = selected ? '' : raw;
    $('customUsageDetails').open = false
  }
}

function renderUsageOptions(query = '') {
  const options = $('usageOptions'),
    selected = selectedUsage(),
    groups = usagePicker.filterGroups(
      meta?.usage_groups,
      meta?.usages,
      query,
      usageGroupLabel,
      friendlyUsageName
    );
  options.innerHTML = '';
  usagePickerItems = [];
  usagePickerActive = -1;
  $('usageSearch').removeAttribute('aria-activedescendant');
  if (!groups.length) {
    const empty = document.createElement('div');
    empty.className = 'search-select-empty';
    empty.setAttribute('role', 'status');
    empty.textContent = t('keymap.noFunctionResults');
    options.append(empty);
    return
  }
  for (const group of groups) {
    const section = document.createElement('div'),
      heading = document.createElement('div');
    section.className = 'search-select-group';
    heading.className = 'search-select-group-title';
    heading.textContent = group.label;
    section.append(heading);
    for (const item of group.items) {
      const index = usagePickerItems.length,
        button = document.createElement('button'),
        name = document.createElement('span'),
        code = document.createElement('code');
      usagePickerItems.push(item);
      button.type = 'button';
      button.id = `usage-option-${index}`;
      button.className = 'search-select-option';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(item.name === selected?.name));
      name.textContent = friendlyUsageName(item.name);
      code.textContent = item.hex;
      button.append(name, code);
      button.onmouseenter = () => setUsagePickerActive(index, false);
      button.onclick = () => chooseUsage(index);
      section.append(button)
    }
    options.append(section)
  }
}

function setUsagePickerActive(index, scroll = true) {
  const options = [...$('usageOptions').querySelectorAll('[role="option"]')];
  if (!options.length) return;
  usagePickerActive = (index + options.length) % options.length;
  options.forEach((option, itemIndex) => option.classList.toggle('active', itemIndex === usagePickerActive));
  const active = options[usagePickerActive];
  $('usageSearch').setAttribute('aria-activedescendant', active.id);
  if (scroll) active.scrollIntoView({
    block: 'nearest'
  })
}

function openUsagePicker(query = '') {
  renderUsageOptions(query);
  $('usageOptions').hidden = false;
  $('usagePicker').classList.add('open');
  $('usageSearch').setAttribute('aria-expanded', 'true');
  if (!usagePickerItems.length) return;
  const selected = selectedUsage(),
    selectedIndex = usagePickerItems.findIndex(item => item.name === selected?.name);
  setUsagePickerActive(selectedIndex >= 0 ? selectedIndex : 0, false)
}

function closeUsagePicker() {
  $('usageOptions').hidden = true;
  $('usagePicker').classList.remove('open');
  $('usageSearch').setAttribute('aria-expanded', 'false');
  $('usageSearch').removeAttribute('aria-activedescendant');
  usagePickerActive = -1
}

function chooseUsage(index) {
  const item = usagePickerItems[index];
  if (!item) return;
  $('usageInput').value = item.name;
  syncUsageSelection();
  closeUsagePicker();
  markAssignmentEditorDirty()
}

function usageSearchKeydown(event) {
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    if ($('usageOptions').hidden) openUsagePicker('');
    else setUsagePickerActive(usagePickerActive + (event.key === 'ArrowDown' ? 1 : -1));
    return
  }
  if (event.key === 'Home' || event.key === 'End') {
    if ($('usageOptions').hidden || !usagePickerItems.length) return;
    event.preventDefault();
    setUsagePickerActive(event.key === 'Home' ? 0 : usagePickerItems.length - 1);
    return
  }
  if (event.key === 'Enter' && !$('usageOptions').hidden && usagePickerActive >= 0) {
    event.preventDefault();
    chooseUsage(usagePickerActive);
    return
  }
  if (event.key === 'Escape' && !$('usageOptions').hidden) {
    event.preventDefault();
    syncUsageSelection();
    closeUsagePicker();
    return
  }
  if (event.key === 'Tab') {
    syncUsageSelection();
    closeUsagePicker()
  }
}

function keyLabel(key) {
  if (typeof key !== 'string' || !key) return '—';
  return titles[key] || key.replace(/^n(?=\d)/, '')
}

function moveKeyboardFocus(container, current, direction) {
  const origin = current.getBoundingClientRect(),
    originX = origin.left + origin.width / 2,
    originY = origin.top + origin.height / 2,
    candidates = [...container.querySelectorAll('.key')].filter(button => button !== current).map(button => {
      const bounds = button.getBoundingClientRect(),
        deltaX = bounds.left + bounds.width / 2 - originX,
        deltaY = bounds.top + bounds.height / 2 - originY,
        inDirection = direction === 'left' ? deltaX < -1 : direction === 'right' ? deltaX > 1 : direction === 'up' ? deltaY < -1 : deltaY > 1,
        primary = direction === 'left' || direction === 'right' ? Math.abs(deltaX) : Math.abs(deltaY),
        secondary = direction === 'left' || direction === 'right' ? Math.abs(deltaY) : Math.abs(deltaX);
      return {
        button,
        inDirection,
        score: primary + secondary * 3
      }
    }).filter(item => item.inDirection).sort((a, b) => a.score - b.score);
  if (!candidates.length) return;
  current.tabIndex = -1;
  candidates[0].button.tabIndex = 0;
  candidates[0].button.focus()
}

function buildKeyboard(container, mode) {
  container.innerHTML = '';
  const focusKey = mode === 'assign' ? selectedKey : mode === 'color' ? colorKeys.values().next().value : null;
  rows.flat().forEach((key, index) => {
    const [x, y, w, h] = keyPosition(index);
    if (!w || !h) return;
    const b = document.createElement('button'),
      customized = mode === 'assign' && hasOwn(profile.layers[currentLayer], key);
    b.type = 'button';
    b.className = 'key';
    b.dataset.key = key;
    b.style.cssText = `--x:${x/7.57}%;--y:${y/2.36}%;--w:${w/7.57}%;--h:${h/2.36}%`;
    b.textContent = keyLabel(key);
    if (mode === 'tester') {
      if (testerPressed.has(key)) b.classList.add('pressed');
      if (testerSeen.has(key)) b.classList.add('tested');
      if (keyEvents.isUnobservable(key)) b.classList.add('unobservable');
      else if (keyEvents.isHostReserved(key)) b.classList.add('host-reserved')
    }
    if (customized) b.classList.add('assigned');
    if (mode === 'assign' && selectedKey === key) b.classList.add('selected');
    if (mode === 'color' && colorKeys.has(key)) b.classList.add('selected');
    if (mode === 'color' && profile.colors[key]) {
      const sw = document.createElement('i');
      sw.className = 'swatch';
      const c = profile.colors[key];
      sw.style.background = Array.isArray(c) ? `rgb(${c.join(',')})` : c;
      b.append(sw)
    }
    if (mode === 'live') {
      const color = livePreviewColors?.[key] || '#000000';
      b.style.setProperty('--live-color', color);
      b.setAttribute('aria-label', t('lighting.liveKeyPreview', {
        key: keyLabel(key),
        color
      }))
    }
    if (mode === 'assign') {
      b.setAttribute('aria-pressed', String(selectedKey === key));
      b.setAttribute('aria-label', t(customized ? 'keymap.keyCustomizedAria' : 'keymap.keyAria', {
        key: keyLabel(key)
      }))
    }
    if (mode === 'color') b.setAttribute('aria-pressed', String(colorKeys.has(key)));
    if (mode === 'tester' || mode === 'live') b.disabled = true;
    else {
      b.tabIndex = key === focusKey ? 0 : -1;
      b.onkeydown = event => {
        const direction = {
          ArrowLeft: 'left',
          ArrowRight: 'right',
          ArrowUp: 'up',
          ArrowDown: 'down'
        } [event.key];
        if (!direction) return;
        event.preventDefault();
        moveKeyboardFocus(container, b, direction)
      };
      b.onclick = () => {
        mode === 'assign' ? selectKey(key) : toggleColorKey(key);
        requestAnimationFrame(() => container.querySelector(`[data-key="${key}"]`)?.focus({
          preventScroll: true
        }))
      }
    }
    container.append(b)
  });
  if (mode !== 'tester' && mode !== 'live' && !container.querySelector('.key[tabindex="0"]')) container.querySelector('.key')?.setAttribute('tabindex', '0')
}

function profileSettings() {
  if (!profile.settings || typeof profile.settings !== 'object') profile.settings = {
    win_lock: false,
    wasd_arrows: false,
    debounce_ms: DEFAULT_DEBOUNCE_MS
  };
  if (!Number.isInteger(profile.settings.debounce_ms) || profile.settings.debounce_ms < 1 || profile.settings.debounce_ms > 255) profile.settings.debounce_ms = DEFAULT_DEBOUNCE_MS;
  return profile.settings
}

function liveSettings() {
  const settings = profileSettings();
  if (!settings.live_effects || typeof settings.live_effects !== 'object' || Array.isArray(settings.live_effects)) settings.live_effects = {};
  const live = settings.live_effects,
    bounded = (value, fallback, minimum, maximum) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? Math.max(minimum, Math.min(maximum, numeric)) : fallback
    };
  live.master_brightness = bounded(live.master_brightness, DEFAULT_LIVE_SETTINGS.master_brightness, 0, 100);
  live.audio_source = typeof live.audio_source === 'string' ? live.audio_source : DEFAULT_LIVE_SETTINGS.audio_source;
  live.audio_mode = ['spectrum', 'bass', 'loudness'].includes(live.audio_mode) ? live.audio_mode : DEFAULT_LIVE_SETTINGS.audio_mode;
  live.audio_sensitivity = bounded(live.audio_sensitivity, DEFAULT_LIVE_SETTINGS.audio_sensitivity, 200, 8000);
  live.audio_noise_gate = bounded(live.audio_noise_gate, DEFAULT_LIVE_SETTINGS.audio_noise_gate, 0, 30);
  live.audio_smoothing = bounded(live.audio_smoothing, DEFAULT_LIVE_SETTINGS.audio_smoothing, 0, 95);
  return live
}

function renderDebounceControl() {
  $('debounce').value = profileSettings().debounce_ms
}

function currentDebounce() {
  return Number($('debounce').value)
}

function rememberDebounce(value, target) {
  if (!Number.isInteger(value) || value < 1 || value > 255) return;
  if (!target.profile.settings || typeof target.profile.settings !== 'object') target.profile.settings = {};
  target.profile.settings.debounce_ms = value;
  if (profile === target.profile) renderDebounceControl();
  const name = target.savedName;
  if (!name) return;
  try {
    const items = storedProfiles();
    if (!hasOwn(items, name)) return;
    if (!items[name].settings || typeof items[name].settings !== 'object') items[name].settings = {};
    items[name].settings.debounce_ms = value;
    localStorage.setItem('spade65-profiles', JSON.stringify(items))
  } catch (error) {
    console.warn('Unable to persist the debounce snapshot', error)
  }
}

function assignmentIdentity(layer = currentLayer, key = selectedKey) {
  return key ? `${layer}:${key}` : null
}

function markAssignmentEditorDirty() {
  if (!selectedKey) return;
  assignmentEditorKey = assignmentIdentity();
  assignmentEditorDirty = true;
  $('discardAssignmentBtn').disabled = false;
  renderKeymapDraftStatus();
  setProfileControlsRecordingLocked()
}

function mayLeaveAssignmentEditor(nextLayer = currentLayer, nextKey = selectedKey) {
  if (!assignmentEditorDirty || assignmentEditorKey === assignmentIdentity(nextLayer, nextKey)) return true;
  if (!confirm(t('keymap.confirmDiscardAssignment', {
      key: keyLabel(selectedKey)
    }))) return false;
  assignmentEditorDirty = false;
  return true
}

function requireCommittedAssignment() {
  if (!assignmentEditorDirty) return true;
  activatePage('keymap');
  $('keyAssignmentEditor').scrollIntoView({
    behavior: 'smooth',
    block: 'center'
  });
  toast(t('keymap.saveBeforeApply'), true);
  return false
}

function renderKeyboard() {
  buildKeyboard($('keyboard'), 'assign');
  renderLayerSummary();
  const hasSelection = Boolean(selectedKey),
    layerName = currentLayer === 'normal' ? t('layer.normal') : currentLayer === 'fn1' ? 'Fn 1' : 'Fn 2';
  $('selectedKey').textContent = hasSelection ? `${keyLabel(selectedKey)} · ${layerName}` : t('common.none');
  $('keymapActiveLayer').textContent = layerName;
  $('keymapEmptyState').hidden = hasSelection;
  $('keyAssignmentEditor').hidden = !hasSelection;
  $('keyAssignmentEditor').disabled = !hasSelection;
  $('keymapStepKey').classList.toggle('active', !hasSelection);
  $('keymapStepKey').classList.toggle('complete', hasSelection);
  $('keymapStepAction').classList.toggle('active', hasSelection);
  document.querySelectorAll('#layerTabs button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.layer === currentLayer)));
  $('winLock').checked = !!profileSettings().win_lock;
  $('wasdArrows').checked = !!profileSettings().wasd_arrows;
  if (hasSelection && (!assignmentEditorDirty || assignmentEditorKey !== assignmentIdentity())) loadAssignment();
  $('discardAssignmentBtn').disabled = !assignmentEditorDirty;
  renderKeymapDraftStatus();
  setProfileControlsRecordingLocked()
}

function testerButtons() {
  // Only keys the current layout actually draws can be tested, and Fn never
  // reaches the host at all, so neither counts towards the total.
  return rows.flat().filter((key, index) => {
    const [, , w, h] = keyPosition(index);
    return w && h && !keyEvents.isUnobservable(key)
  })
}

function renderTester() {
  const container = $('testerKeyboard');
  if (!container) return;
  buildKeyboard(container, 'tester');
  const testable = testerButtons(),
    seen = testable.filter(key => testerSeen.has(key)),
    remaining = testable.filter(key => !testerSeen.has(key));
  const selectedLayout = $('layoutVariant')?.selectedOptions?.[0];
  $('testerLayoutBadge').textContent = selectedLayout?.textContent || layoutVariant;
  $('testerCount').textContent = `${seen.length} / ${testable.length}`;
  $('testerRemaining').textContent = remaining.length ?
    remaining.map(keyLabel).join(', ') :
    t('tester.allPressed')
}

function testerKeyEvent(event) {
  if (!$('page-tester').classList.contains('active')) return;
  const buttons = keyEvents.buttonsForCode(event.code, layoutVariant);
  if (!buttons.length) return;
  event.preventDefault();
  const down = event.type === 'keydown';
  for (const key of buttons) {
    down ? testerPressed.add(key) : testerPressed.delete(key);
    if (down) testerSeen.add(key)
  }
  if (down) {
    $('testerLastKey').textContent = buttons.map(keyLabel).join(' / ');
    $('testerLastCode').textContent = event.code
  }
  renderTester()
}

function resetTester() {
  testerPressed.clear();
  testerSeen.clear();
  $('testerLastKey').textContent = '—';
  $('testerLastCode').textContent = '—';
  renderTester();
  toast(t('tester.cleared'))
}

function renderColorKeyboard() {
  buildKeyboard($('colorKeyboard'), 'color');
  renderAppRangeSummary();
  const selected = colorKeys.size,
    colored = Object.keys(profile.colors).length;
  $('colorSelectionStatus').textContent = t('lighting.colorSelectionStatus', {
    selected,
    colored
  });
  const selectionColored = selected > 0 && [...colorKeys].every(key => hasOwn(profile.colors, key));
  setWorkflowStep('colorStepSelect', selected === 0 && colored === 0, selected > 0 || colored > 0);
  setWorkflowStep('colorStepChoose', selected > 0 && !selectionColored, selectionColored);
  setWorkflowStep('colorStepApply', colored > 0 && !(selected > 0 && !selectionColored), false);
  $('setColorBtn').disabled = selected === 0;
  $('clearColorsBtn').disabled = colored === 0;
  $('applyColorsBtn').disabled = colored === 0 || !configurationReady()
}

function renderLiveKeyboard() {
  const container = $('liveKeyboard');
  if (container && profile) buildKeyboard(container, 'live')
}

function setWorkflowStep(id, active, complete) {
  const step = $(id);
  if (!step) return;
  step.classList.toggle('active', active);
  step.classList.toggle('complete', complete)
}

function selectKey(key) {
  if (!mayLeaveAssignmentEditor(currentLayer, key)) return;
  selectedKey = key;
  renderKeyboard();
  if (pendingMacroAssignment !== null && profile.macros.some(macro => macro.index === pendingMacroAssignment)) {
    $('assignmentType').value = 'macro';
    $('macroAssign').value = pendingMacroAssignment;
    pendingMacroAssignment = null;
    assignmentTypeChanged();
    markAssignmentEditorDirty();
    $('keyAssignmentEditor').scrollIntoView({
      behavior: 'smooth',
      block: 'nearest'
    })
  }
  if (window.matchMedia('(max-width: 640px)').matches) requestAnimationFrame(() => $('keyAssignmentEditor').scrollIntoView({
    behavior: 'smooth',
    block: 'start'
  }))
}

function toggleColorKey(key) {
  colorKeys.has(key) ? colorKeys.delete(key) : colorKeys.add(key);
  renderColorKeyboard()
}

function loadAssignment() {
  const value = profile.layers[currentLayer][selectedKey];
  document.querySelectorAll('#modifierWrap input').forEach(x => x.checked = false);
  $('modifierDetails').open = false;
  if (value === undefined) {
    $('assignmentType').value = 'default';
    $('usageInput').value = ''
  } else if (typeof value === 'object' && 'macro' in value) {
    $('assignmentType').value = 'macro';
    $('macroAssign').value = value.macro;
    $('usageInput').value = ''
  } else {
    $('assignmentType').value = 'usage';
    $('usageInput').value = typeof value === 'object' ? value.usage : value;
    const mods = typeof value === 'object' ? (value.modifiers || 0) : 0;
    document.querySelectorAll('#modifierWrap input').forEach(x => x.checked = !!(mods & Number(x.value)));
    $('modifierDetails').open = Boolean(mods)
  }
  assignmentTypeChanged();
  syncUsageSelection();
  assignmentEditorKey = assignmentIdentity();
  assignmentEditorDirty = false
}

function assignmentTypeChanged() {
  const type = $('assignmentType').value;
  $('usageWrap').hidden = type !== 'usage';
  $('macroWrap').hidden = type !== 'macro';
  $('macroAssignEmpty').hidden = type !== 'macro' || Boolean(profile.macros.length);
  $('macroAssign').disabled = type === 'macro' && !profile.macros.length;
  $('assignBtn').disabled = type === 'macro' && !profile.macros.length
}

function discardAssignmentEditorChange() {
  if (!selectedKey || !assignmentEditorDirty) return;
  loadAssignment();
  renderKeyboard();
  toast(t('keymap.editorDiscarded'))
}

function renderKeymapDraftStatus() {
  const target = $('keymapDraftStatus');
  if (!target) return;
  target.textContent = t(assignmentEditorDirty ? 'keymap.editorUnsaved' : keymapDraftDirty ? 'keymap.draftChanged' : 'keymap.draftReady');
  target.classList.toggle('changed', assignmentEditorDirty || keymapDraftDirty)
}

function markKeymapDraftChanged() {
  keymapDraftDirty = true;
  renderKeymapDraftStatus()
}

function saveAssignment() {
  if (!selectedKey) return toast(t('keymap.selectFirst'), true);
  const type = $('assignmentType').value;
  if (type === 'default') delete profile.layers[currentLayer][selectedKey];
  else if (type === 'macro') {
    if (!profile.macros.length) return toast(t('keymap.createMacroFirst'), true);
    profile.layers[currentLayer][selectedKey] = {
      macro: Number($('macroAssign').value)
    }
  } else {
    const rawUsage = $('usageInput').value.trim(),
      selected = selectedUsage(),
      customUsage = usagePicker.rawUsageValue(rawUsage);
    if (!rawUsage) return toast(t('keymap.usageRequired'), true);
    if (!selected && customUsage === null) return toast(t('keymap.customUsageInvalid'), true);
    const usage = selected?.name || usagePicker.usageHex(customUsage);
    let modifiers = 0;
    document.querySelectorAll('#modifierWrap input:checked').forEach(x => modifiers |= Number(x.value));
    profile.layers[currentLayer][selectedKey] = modifiers ? {
      usage,
      modifiers
    } : usage;
    $('usageInput').value = usage;
    syncUsageSelection()
  }
  markKeymapDraftChanged();
  assignmentEditorKey = assignmentIdentity();
  assignmentEditorDirty = false;
  renderMacros();
  renderKeyboard();
  toast(t('keymap.assignmentSaved', {
    key: keyLabel(selectedKey),
    layer: currentLayer
  }))
}

function renderLayerSummary() {
  const box = $('layerSummary');
  box.innerHTML = '';
  for (const layer of ['normal', 'fn1', 'fn2']) {
    const div = document.createElement('div');
    div.textContent = t('keymap.assignments', {
      layer: layer === 'normal' ? t('layer.normal') : layer === 'fn1' ? 'Fn 1' : 'Fn 2',
      count: Object.keys(profile.layers[layer]).length
    });
    box.append(div)
  }
}

function backupKeys(name, keys) {
  const settings = profileSettings();
  settings[name] = {};
  for (const key of keys) settings[name][key] = hasOwn(profile.layers.normal, key) ? {
    present: true,
    value: cloneJson(profile.layers.normal[key])
  } : {
    present: false
  }
}

function restoreKeys(name) {
  const settings = profileSettings(),
    backup = settings[name] || {};
  for (const [key, item] of Object.entries(backup)) item.present ? profile.layers.normal[key] = item.value : delete profile.layers.normal[key];
  delete settings[name]
}

function toggleWinLock(enabled) {
  const settings = profileSettings();
  if (enabled && !settings.win_lock) {
    backupKeys('win_lock_backup', ['win']);
    profile.layers.normal.win = 'disabled'
  } else if (!enabled && settings.win_lock) restoreKeys('win_lock_backup');
  settings.win_lock = enabled;
  markKeymapDraftChanged();
  renderKeyboard();
  toast(t(enabled ? 'keymap.winDisabled' : 'keymap.winRestored'))
}

function toggleWasdArrows(enabled) {
  const settings = profileSettings(),
    keys = ['w', 'a', 's', 'd', 'up', 'left', 'down', 'right'];
  if (enabled && !settings.wasd_arrows) {
    backupKeys('wasd_arrows_backup', keys);
    Object.assign(profile.layers.normal, {
      w: 'up',
      a: 'left',
      s: 'down',
      d: 'right',
      up: 'w',
      left: 'a',
      down: 's',
      right: 'd'
    })
  } else if (!enabled && settings.wasd_arrows) restoreKeys('wasd_arrows_backup');
  settings.wasd_arrows = enabled;
  markKeymapDraftChanged();
  renderKeyboard();
  toast(t(enabled ? 'keymap.wasdSwapped' : 'keymap.wasdRestored'))
}

function disableGroup(group) {
  const groups = {
    numbers: ['n0', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9'],
    letters: [...'abcdefghijklmnopqrstuvwxyz'],
    symbols: ['minus', 'plus', 'lqu', 'rqu', 'k29', 'k42', 'sem', 'quo', 'comma', 'dot', 'qmark'],
    controls: ['esc', 'bksp', 'tab', 'caps', 'enter', 'delete', 'pageup', 'pagedown', 'lshift', 'rshift', 'lctrl', 'rctrl', 'lalt', 'ralt', 'win', 'fn', 'up', 'down', 'left', 'right', 'lspace', 'mspace', 'rspace'],
    all: meta.buttons
  };
  if (group === 'all' && !confirm(t('keymap.confirmDisableAll', {
      layer: currentLayer === 'normal' ? t('layer.normal') : currentLayer === 'fn1' ? 'Fn 1' : 'Fn 2'
    }))) return;
  for (const key of groups[group]) profile.layers[currentLayer][key] = 'disabled';
  markKeymapDraftChanged();
  renderKeyboard();
  toast(t('keymap.groupDisabled', {
    group: t(group === 'all' ? 'group.allKeys' : `group.${group}`),
    layer: currentLayer
  }))
}

function undoDisabled() {
  for (const [key, value] of Object.entries(profile.layers[currentLayer]))
    if (value === 'disabled' || value === 0) delete profile.layers[currentLayer][key];
  markKeymapDraftChanged();
  renderKeyboard();
  toast(t('keymap.disabledRemoved', {
    layer: currentLayer
  }))
}

function newAppLayer() {
  return {
    mode: 'wave',
    enabled: true,
    speed: 5,
    opacity: 100,
    bandwidth: 200,
    angle: 0,
    number: 5,
    gap: 0,
    fire: 1,
    center_x: 0,
    center_y: 0,
    gradient: true,
    reverse: false,
    bump: false,
    bidirectional: false,
    audio: false,
    colors: ['#ff0000', '#00ffff', '#8000ff'],
    keys: []
  }
}

function appLayers() {
  const settings = profileSettings();
  if (!Array.isArray(settings.app_effects) || !settings.app_effects.length) settings.app_effects = [newAppLayer()];
  settings.app_effects = settings.app_effects.slice(0, 10).map(value => {
    const layer = value && typeof value === 'object' && !Array.isArray(value) ? value : newAppLayer(),
      defaults = newAppLayer();
    for (const [key, fallback] of Object.entries(defaults)) {
      if (!hasOwn(layer, key)) layer[key] = Array.isArray(fallback) ? [...fallback] : fallback
    }
    layer.keys = Array.isArray(layer.keys) ? layer.keys.filter(key => meta?.buttons.includes(key)) : [];
    layer.colors = Array.isArray(layer.colors) ? layer.colors.slice(0, 20).filter(color => /^#[0-9a-f]{6}$/i.test(color)) : [];
    if (!layer.colors.length) layer.colors = newAppLayer().colors;
    return layer
  });
  return settings.app_effects
}

function appLayer() {
  activeAppLayer = Math.min(activeAppLayer, appLayers().length - 1);
  return appLayers()[activeAppLayer]
}

function animationKey(mode) {
  return mode === 'linear-wave' ? 'linearWave' : mode
}

function renderAppLayers() {
  const list = $('appLayerList');
  list.innerHTML = '';
  appLayers().forEach((layer, index) => {
    const row = document.createElement('div');
    row.className = `effect-layer${index===activeAppLayer?' active':''}`;
    const enabled = document.createElement('input');
    enabled.type = 'checkbox';
    enabled.checked = layer.enabled !== false;
    enabled.title = t('lighting.toggleLayer');
    enabled.onclick = event => event.stopPropagation();
    enabled.onchange = () => {
      const current = appLayers()[index];
      if (!current) return;
      current.enabled = enabled.checked;
      refreshLivePreview();
      if (animationTimer) {
        const needsAudio = appLayers().some(item => item.enabled !== false && item.audio);
        if (!needsAudio) stopAudio();
        else if (!audioAnalyser && !audioNativeRunning) restartAudioForLivePreview()
      }
    };
    const name = document.createElement('button');
    name.textContent = `${index+1} · ${t(`animation.${animationKey(layer.mode||'wave')}`)}`;
    name.onclick = () => {
      activeAppLayer = index;
      renderAppLayers();
      loadAppLayer()
    };
    row.append(enabled, name);
    list.append(row)
  });
  $('removeAppLayerBtn').disabled = appLayers().length <= 1;
  loadAppLayer()
}

function loadAppLayer() {
  const layer = appLayer();
  $('animation').value = layer.mode;
  $('appSpeed').value = layer.speed;
  $('appSpeedOut').value = layer.speed;
  $('appOpacity').value = layer.opacity;
  $('appOpacityOut').value = layer.opacity;
  $('appBandwidth').value = layer.bandwidth;
  $('appBandwidthOut').value = layer.bandwidth;
  $('appAngle').value = layer.angle;
  $('appAngleOut').value = layer.angle;
  $('appNumber').value = layer.number;
  $('appGap').value = layer.gap;
  $('appFire').value = layer.fire;
  $('appCenterX').value = layer.center_x;
  $('appCenterY').value = layer.center_y;
  $('appGradient').checked = layer.gradient !== false;
  $('appReverse').checked = !!layer.reverse;
  $('appBump').checked = !!layer.bump;
  $('appBidirectional').checked = !!layer.bidirectional;
  $('audioSync').checked = !!layer.audio;
  const settings = liveSettings();
  $('liveBrightness').value = settings.master_brightness;
  $('liveBrightnessOut').value = settings.master_brightness;
  $('audioMode').value = settings.audio_mode;
  $('audioSensitivity').value = settings.audio_sensitivity;
  $('audioSensitivityOut').value = settings.audio_sensitivity;
  $('audioNoiseGate').value = settings.audio_noise_gate;
  $('audioNoiseGateOut').value = settings.audio_noise_gate;
  $('audioSmoothing').value = settings.audio_smoothing;
  $('audioSmoothingOut').value = settings.audio_smoothing;
  document.querySelectorAll('.app-color').forEach((input, index) => input.value = layer.colors?.[index] || '#000000');
  renderAppRangeSummary();
  renderAudioControlState()
}

function saveAppLayer(refreshLayerList = false) {
  const layer = appLayer();
  layer.mode = $('animation').value;
  layer.speed = Number($('appSpeed').value);
  layer.opacity = Number($('appOpacity').value);
  layer.bandwidth = Number($('appBandwidth').value);
  layer.angle = Number($('appAngle').value);
  layer.number = Number($('appNumber').value);
  layer.gap = Number($('appGap').value);
  layer.fire = Number($('appFire').value);
  layer.center_x = Number($('appCenterX').value);
  layer.center_y = Number($('appCenterY').value);
  layer.gradient = $('appGradient').checked;
  layer.reverse = $('appReverse').checked;
  layer.bump = $('appBump').checked;
  layer.bidirectional = $('appBidirectional').checked;
  layer.audio = $('audioSync').checked;
  layer.colors = [...document.querySelectorAll('.app-color')].map(input => input.value);
  if (refreshLayerList) renderAppLayers();
  else {
    renderAppRangeSummary();
    refreshLivePreview()
  }
}

function saveLiveSettings(persistSource = false) {
  const settings = liveSettings();
  settings.master_brightness = Number($('liveBrightness').value);
  if (persistSource === true) settings.audio_source = $('audioSource').value;
  settings.audio_mode = $('audioMode').value;
  settings.audio_sensitivity = Number($('audioSensitivity').value);
  settings.audio_noise_gate = Number($('audioNoiseGate').value);
  settings.audio_smoothing = Number($('audioSmoothing').value);
  audioFrame = liveEffects.emptyAudioFrame();
  refreshLivePreview()
}

async function restartAudioForLivePreview() {
  if (!animationTimer || !appLayers().some(layer => layer.enabled !== false && layer.audio)) return;
  stopAudio();
  try {
    await startAudio()
  } catch (error) {
    stopAnimation();
    toast(t('lighting.audioUnavailable', {
      error: error.message || String(error)
    }), true)
  }
}

async function audioReactiveChanged() {
  saveAppLayer();
  renderAudioControlState();
  if (!animationTimer) return;
  if (appLayers().some(layer => layer.enabled !== false && layer.audio)) {
    if (!audioAnalyser && !audioNativeRunning) await restartAudioForLivePreview()
  } else stopAudio()
}

function addAppLayer() {
  if (appLayers().length >= 10) return toast(t('lighting.maxLayers'), true);
  appLayers().push(newAppLayer());
  activeAppLayer = appLayers().length - 1;
  renderAppLayers();
  toast(t('lighting.layerAdded'))
}

function removeAppLayer() {
  if (appLayers().length <= 1) return;
  appLayers().splice(activeAppLayer, 1);
  activeAppLayer = Math.max(0, activeAppLayer - 1);
  renderAppLayers();
  toast(t('lighting.layerRemoved'))
}

function setAppRange() {
  appLayer().keys = [...colorKeys];
  renderAppRangeSummary();
  toast(colorKeys.size ? t('lighting.effectSelectedKeys', {
    count: colorKeys.size
  }) : t('lighting.effectAllKeys'))
}

function clearAppRange() {
  appLayer().keys = [];
  renderAppRangeSummary();
  toast(t('lighting.effectAllKeys'))
}

function renderAppRangeSummary() {
  const target = $('appRangeSummary');
  if (!target || !profile) return;
  const keys = appLayer().keys || [],
    selected = colorKeys.size;
  target.textContent = keys.length ? t('lighting.currentRangeSelected', {
    count: keys.length
  }) : t('lighting.currentRangeAll')
  $('setAppRangeBtn').disabled = selected === 0;
  $('setAppRangeBtn').textContent = t('action.useSelectedRangeCount', {
    count: selected
  })
}

function macroDisplayName(macro) {
  return macro.name || t('macro.defaultName', {
    index: macro.index
  })
}

function macroIssueMessage(issue) {
  if (!issue) return '';
  return t(`macro.sequence.${issue.kind}`, issue)
}

function macroStateSnapshot(source = profile) {
  const bindings = {};
  for (const [layer, assignments] of Object.entries(source.layers)) {
    bindings[layer] = Object.fromEntries(Object.entries(assignments).filter(([, value]) => typeof value === 'object' && value !== null && hasOwn(value, 'macro')))
  }
  return JSON.stringify({
    macros: source.macros,
    bindings
  })
}

function renderMacros() {
  const list = $('macroList');
  list.innerHTML = '';
  profile.macros.forEach((macro, i) => {
    const b = document.createElement('button');
    b.className = i === activeMacro ? 'active' : '';
    const name = document.createElement('strong'),
      meta = document.createElement('small');
    name.textContent = macroDisplayName(macro);
    meta.textContent = t('macro.listMeta', {
      index: macro.index,
      count: macro.events.length,
      bindings: macroRules.bindings(profile.layers, macro.index).length
    });
    b.append(name, meta);
    b.disabled = recordingMacro;
    b.onclick = () => {
      activeMacro = i;
      renderMacros()
    };
    list.append(b)
  });
  const macro = profile.macros[activeMacro];
  $('macroListEmpty').hidden = Boolean(profile.macros.length);
  $('macroEditorEmpty').hidden = Boolean(macro);
  $('macroEditorContent').hidden = !macro;
  $('macroTitle').textContent = macro ? `M${macro.index} · ${macroDisplayName(macro)}` : t('macro.editor');
  $('macroName').value = macro?.name ?? '';
  $('macroRepeat').value = macro?.repeat ?? 1;
  $('eventList').innerHTML = '';
  if (macro) macro.events.forEach((event, i) => renderEvent(event, i));
  const eventCount = macro?.events.length ?? 0,
    bindings = macro ? macroRules.bindings(profile.layers, macro.index) : [],
    sequenceIssue = macroRules.sequenceIssue(macro, meta?.usages),
    sequenceValid = eventCount > 0 && !sequenceIssue,
    applyReady = sequenceValid && bindings.length > 0,
    applied = applyReady && appliedMacroSnapshot?.device === device() && appliedMacroSnapshot.state === macroStateSnapshot();
  $('macroEventCount').textContent = t('macro.eventCount', {
    count: eventCount
  });
  $('macroNoEvents').hidden = !macro || eventCount > 0 || recordingMacro;
  $('macroSequenceStatus').hidden = !sequenceIssue;
  $('macroSequenceStatus').textContent = macroIssueMessage(sequenceIssue);
  $('macroRecordingBanner').hidden = !recordingMacro;
  $('macroRecordingStatus').textContent = macro ? t('macro.recordingStatus', {
    name: macroDisplayName(macro),
    count: eventCount
  }) : '';
  $('macroBindingStatus').textContent = macro ? t(bindings.length ? 'macro.assignedStatus' : 'macro.unassignedStatus', {
    count: bindings.length
  }) : '';
  $('macroNextStepTitle').textContent = t(eventCount === 0 ? 'macro.nextStepRecord' : sequenceIssue ? 'macro.nextStepFix' : bindings.length ? 'macro.nextStepAssigned' : 'macro.nextStep');
  setWorkflowStep('macroStepCreate', !macro, Boolean(macro));
  setWorkflowStep('macroStepRecord', Boolean(macro) && !sequenceValid, sequenceValid);
  setWorkflowStep('macroStepAssign', sequenceValid && bindings.length === 0, sequenceValid && bindings.length > 0);
  setWorkflowStep('macroStepApply', applyReady && !applied, applied);
  $('addMacroBtn').disabled = recordingMacro;
  $('deleteMacroBtn').disabled = !macro || recordingMacro;
  $('addEventBtn').disabled = !macro || recordingMacro;
  $('macroName').disabled = !macro || recordingMacro;
  $('macroRepeat').disabled = !macro || recordingMacro;
  $('recordMacroBtn').disabled = !macro;
  $('recordMacroBtn').hidden = recordingMacro;
  $('stopMacroBtn').disabled = !recordingMacro;
  $('assignMacroToKeyBtn').disabled = !macro || !sequenceValid || recordingMacro;
  $('prepareMacroApplyBtn').hidden = !macro || !sequenceValid || bindings.length === 0;
  $('prepareMacroApplyBtn').disabled = recordingMacro;
  setProfileControlsRecordingLocked();
  renderMacroAssign()
}

function setProfileControlsRecordingLocked() {
  for (const id of ['applyProfileBtn', 'newProfileBtn', 'saveProfileBtn', 'deleteProfileBtn', 'importProfileBtn', 'vendorImportBtn', 'exportProfileBtn', 'backupLibraryBtn', 'restoreLibraryBtn', 'savedProfile', 'profileName']) {
    const control = $(id);
    if (control) control.disabled = recordingMacro || id === 'applyProfileBtn' && !configurationReady()
  }
}

function renderMacroAssign() {
  const s = $('macroAssign'),
    selected = s.value;
  s.innerHTML = '';
  for (const macro of profile.macros) {
    const o = document.createElement('option');
    o.value = macro.index;
    o.textContent = `M${macro.index} · ${macroDisplayName(macro)}`;
    s.append(o)
  }
  if ([...s.options].some(option => option.value === selected)) s.value = selected
}

function renderEvent(event, index) {
  const row = document.createElement('div');
  row.className = 'event';
  const delay = document.createElement('input');
  delay.type = 'number';
  delay.min = 0;
  delay.max = 32767;
  delay.value = event.delay_ms;
  delay.setAttribute('aria-label', t('macro.delayAria', {
    number: index + 1
  }));
  delay.disabled = recordingMacro;
  delay.onchange = () => {
    event.delay_ms = Math.max(0, Math.min(32767, Number(delay.value) || 0));
    renderMacros()
  };
  const usage = document.createElement('input');
  usage.value = event.usage;
  usage.setAttribute('aria-label', t('macro.functionAria', {
    number: index + 1
  }));
  usage.disabled = recordingMacro;
  usage.setAttribute('list', 'macroUsageList');
  usage.onchange = () => {
    event.usage = usage.value;
    renderMacros()
  };
  const state = document.createElement('select');
  for (const [value, key] of [
      ['true', 'macro.keyDown'],
      ['false', 'macro.keyUp']
    ]) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = t(key);
    state.append(option)
  }
  state.value = String(event.pressed);
  state.setAttribute('aria-label', t('macro.stateAria', {
    number: index + 1
  }));
  state.disabled = recordingMacro;
  state.onchange = () => {
    event.pressed = state.value === 'true';
    renderMacros()
  };
  const del = document.createElement('button');
  del.textContent = '×';
  del.className = 'danger';
  del.setAttribute('aria-label', t('macro.removeEventAria', {
    number: index + 1
  }));
  del.disabled = recordingMacro;
  del.onclick = () => {
    profile.macros[activeMacro].events.splice(index, 1);
    renderMacros()
  };
  row.append(delay, usage, state, del);
  $('eventList').append(row)
}

function addMacro() {
  if (profile.macros.length >= 10) return toast(t('macro.maximumTen'), true);
  const used = new Set(profile.macros.map(m => m.index));
  let index = 0;
  while (used.has(index)) index++;
  profile.macros.push({
    index,
    name: t('macro.defaultName', {
      index
    }),
    repeat: 1,
    events: []
  });
  activeMacro = profile.macros.length - 1;
  renderMacros();
  $('macroName').focus();
  $('macroName').select()
}

function deleteMacro() {
  const macro = profile.macros[activeMacro];
  if (!macro) return;
  const bindings = macroRules.bindings(profile.layers, macro.index);
  if (!confirm(t('macro.confirmDelete', {
      name: macroDisplayName(macro),
      count: bindings.length
    }))) return;
  for (const layer of Object.values(profile.layers))
    for (const [key, value] of Object.entries(layer))
      if (typeof value === 'object' && value.macro === macro.index) delete layer[key];
  if (pendingMacroAssignment === macro.index) pendingMacroAssignment = null;
  profile.macros.splice(activeMacro, 1);
  if (bindings.length) markKeymapDraftChanged();
  activeMacro = Math.max(0, activeMacro - 1);
  renderMacros();
  renderKeyboard()
}

function addEvent() {
  const macro = profile.macros[activeMacro];
  if (!macro) return;
  if (macro.events.length > 82) return toast(t('macro.maximumEvents'), true);
  macro.events.push({
    delay_ms: 20,
    usage: 'a',
    pressed: true
  }, {
    delay_ms: 20,
    usage: 'a',
    pressed: false
  });
  renderMacros()
}

function recordMacroEvent(event) {
  if (!recordingMacro || event.repeat) return;
  if (event.type === 'keydown' && event.key === 'Escape') {
    event.preventDefault();
    event.stopImmediatePropagation();
    stopMacroRecording();
    return
  }
  const usage = keyEvents.usageForCode(event.code);
  if (!usage) return;
  const isDown = event.type === 'keydown';
  if (isDown && recordPressed.has(event.code) || !isDown && !recordPressed.has(event.code)) return;
  const macro = recordingMacroTarget;
  if (!macro) {
    stopMacroRecording();
    return
  }
  const pressedAfter = recordPressed.size + (isDown ? 1 : -1);
  if (!macroRules.hasRoomForEvent(macro.events.length, pressedAfter)) {
    stopMacroRecording({
      notify: false
    });
    return toast(t('macro.maximumReached'), true)
  }
  const now = performance.now();
  macro.events.push({
    delay_ms: macro.events.length ? Math.min(32767, Math.max(0, Math.round(now - recordLast))) : 0,
    usage,
    pressed: isDown
  });
  isDown ? recordPressed.add(event.code) : recordPressed.delete(event.code);
  recordLast = now;
  event.preventDefault();
  renderMacros();
  if (macroRules.isRecordingFull(macro.events.length, recordPressed.size)) {
    stopMacroRecording({
      notify: false
    });
    toast(t('macro.maximumReached'))
  }
}

function startMacroRecording() {
  const macro = profile.macros[activeMacro];
  if (!macro) return;
  if (macro.events.length && !confirm(t('macro.confirmClear'))) return;
  macro.events = [];
  recordPressed.clear();
  recordLast = performance.now();
  $('recordMacroBtn').blur();
  recordingMacroTarget = macro;
  recordingMacro = true;
  document.addEventListener('keydown', recordMacroEvent, true);
  document.addEventListener('keyup', recordMacroEvent, true);
  renderMacros();
  toast(t('macro.recording'))
}

function closeRecordedKeyPresses(macro) {
  const held = [...recordPressed].map(code => keyEvents.usageForCode(code)).filter(Boolean);
  const closing = macroRules.pendingReleases(held, macro.events.length);
  macro.events.push(...closing.events);
  if (closing.overflow) {
    console.error('Macro recorder exhausted its reserved release slots');
  }
}

function stopMacroRecording({
  notify = true,
  render = true
} = {}) {
  if (!recordingMacro) return false;
  if (recordingMacroTarget) closeRecordedKeyPresses(recordingMacroTarget);
  recordingMacro = false;
  recordingMacroTarget = null;
  recordPressed.clear();
  document.removeEventListener('keydown', recordMacroEvent, true);
  document.removeEventListener('keyup', recordMacroEvent, true);
  if (render) renderMacros();
  if (notify) toast(t('macro.stopped'));
  return true
}

function assignActiveMacroToKey() {
  const macro = profile.macros[activeMacro];
  if (!macro) return;
  if (!mayLeaveAssignmentEditor(currentLayer, null)) return;
  pendingMacroAssignment = macro.index;
  selectedKey = null;
  activatePage('keymap');
  renderKeyboard();
  $('keyboard').scrollIntoView({
    behavior: 'smooth',
    block: 'center'
  });
  toast(t('macro.chooseKeyForAssignment', {
    name: macroDisplayName(macro)
  }))
}

function prepareMacroApply() {
  const macro = profile.macros[activeMacro];
  if (!macro) return;
  const issue = macroRules.sequenceIssue(macro, meta?.usages);
  if (issue) return toast(macroIssueMessage(issue), true);
  if (!macro.events.length || !macroRules.bindings(profile.layers, macro.index).length) return;
  $('scopeKeymap').checked = true;
  $('scopeMacros').checked = true;
  $('applyProfileBtn').scrollIntoView({
    behavior: 'smooth',
    block: 'center'
  });
  $('applyProfileBtn').focus();
  toast(t('macro.applyPrepared'))
}

async function doAction(action, payload, success, onSuccess = null) {
  try {
    const result = await api(action, actionPayload(payload));
    if (onSuccess) onSuccess(result);
    toast(success);
    return result
  } catch (error) {
    toast(error.message, true);
    return null
  }
}

function selectedScopes() {
  return [
    ['keymap', 'scopeKeymap'],
    ['macros', 'scopeMacros'],
    ['colors', 'scopeColors']
  ].filter(([, id]) => $(id).checked).map(([scope]) => scope)
}

async function applyProfile() {
  if (recordingMacro) stopMacroRecording();
  if (!requireCommittedAssignment()) return;
  const scopes = selectedScopes();
  if (!scopes.length) return toast(t('profile.scopeEmpty'), true);
  if (scopes.includes('macros')) {
    const invalidMacro = profile.macros.find(macro => macroRules.sequenceIssue(macro, meta?.usages));
    if (invalidMacro) {
      activeMacro = profile.macros.indexOf(invalidMacro);
      activatePage('macros');
      renderMacros();
      return toast(macroIssueMessage(macroRules.sequenceIssue(invalidMacro, meta?.usages)), true)
    }
  }
  if (!confirm(t('profile.confirmApply'))) return;
  const requestProfile = cloneJson(profile),
    writesLighting = scopes.includes('keymap') || scopes.includes('colors'),
    writesKeymap = scopes.includes('keymap'),
    target = lightingTarget(),
    previousLighting = savedLighting(),
    appliedLighting = writesLighting ? lightingForProfileApply() : null,
    debounceMs = writesKeymap ? currentDebounce() : null;
  if (appliedLighting) requestProfile.lighting = cloneJson(appliedLighting);
  if (writesKeymap) {
    if (!requestProfile.settings || typeof requestProfile.settings !== 'object') requestProfile.settings = {};
    requestProfile.settings.debounce_ms = debounceMs
  }
  const appliedMacroCandidate = scopes.includes('keymap') && scopes.includes('macros') ? {
    device: device(),
    state: macroStateSnapshot(requestProfile)
  } : null;
  const payload = {
    profile: requestProfile,
    confirmed: true,
    scopes
  };
  if (writesLighting && previousLighting) payload.recovery_lighting = cloneJson(previousLighting);
  await doAction('profile', payload, t('profile.applied'), () => {
    if (appliedLighting) rememberLighting(appliedLighting, target);
    if (writesKeymap) {
      rememberDebounce(debounceMs, target);
      keymapDraftDirty = false;
      renderKeymapDraftStatus()
    }
    if (appliedMacroCandidate) {
      appliedMacroSnapshot = appliedMacroCandidate;
      renderMacros()
    }
  })
}
async function downloadJson(data, name) {
  const contents = JSON.stringify(data, null, 2) + '\n',
    nativeSave = window.pywebview?.api?.save_json;
  if (desktopIntegration?.native_export && nativeSave) {
    const result = await nativeSave(contents, name);
    toast(result.saved ? t('profile.exportSaved', {
      name: result.name
    }) : t('profile.exportCancelled'));
    return result
  }
  const blob = new Blob([contents], {
      type: 'application/json'
    }),
    a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
  toast(t('profile.exportSaved', {
    name
  }));
  return {
    saved: true,
    name
  }
}
async function exportProfile() {
  if (!requireCommittedAssignment()) return;
  try {
    await downloadJson(profile, `${$('profileName').value||'spade65-profile'}.json`)
  } catch (error) {
    toast(error.message, true)
  }
}

function renderAllEditors() {
  if (animationTimer || animationStarting) stopAnimation();
  if (timelineTimer) stopTimeline();
  stopMacroRecording({
    notify: false,
    render: false
  });
  selectedKey = null;
  assignmentEditorKey = null;
  assignmentEditorDirty = false;
  pendingMacroAssignment = null;
  activeMacro = 0;
  activeAppLayer = 0;
  keymapDraftDirty = false;
  appliedMacroSnapshot = null;
  lightingMode = null;
  livePreviewColors = null;
  renderLightingControls();
  renderDebounceControl();
  renderMacros();
  renderKeyboard();
  renderColorKeyboard();
  renderAppLayers();
  renderAudioSources();
  refreshLivePreview();
  renderTimeline()
}

function importProfile(file) {
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const data = migrateProfileLighting(JSON.parse(reader.result));
      await api('validate', {
        profile: data
      });
      if (!mayLeaveAssignmentEditor(currentLayer, null)) {
        $('profileFile').value = '';
        return
      }
      profile = data;
      renderSavedProfiles();
      renderAllEditors();
      toast(t('profile.imported'))
    } catch (error) {
      toast(error.message, true)
    }
  };
  reader.readAsText(file)
}

function importVendor(file) {
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const document = JSON.parse(reader.result),
        result = await api('vendor-convert', {
          document,
          profile
        });
      if (!mayLeaveAssignmentEditor(currentLayer, null)) {
        $('vendorFile').value = '';
        return
      }
      profile = migrateProfileLighting(result.profile);
      renderSavedProfiles();
      renderAllEditors();
      toast(t('profile.vendorImported', {
        areas: result.imported.join(', ')
      }))
    } catch (error) {
      toast(error.message, true)
    }
  };
  reader.readAsText(file)
}
async function backupLibrary() {
  if (!requireCommittedAssignment()) return;
  try {
    await downloadJson({
      format: 'spade65-library-v1',
      profiles: storedProfiles(),
      current_profile: profile,
      profile_name: $('profileName').value,
      layout: layoutVariant,
      device_layouts: storedDeviceLayouts(),
      language: currentLanguage
    }, `spade65-library-${new Date().toISOString().slice(0,10)}.json`)
  } catch (error) {
    toast(error.message, true)
  }
}

function restoreLibrary(file) {
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const data = JSON.parse(reader.result);
      if (data.format !== 'spade65-library-v1' || !data.profiles || typeof data.profiles !== 'object' || Array.isArray(data.profiles)) throw new Error(t('profile.unsupportedBackup'));
      for (const item of Object.values(data.profiles)) {
        migrateProfileLighting(item);
        await api('validate', {
          profile: item
        })
      }
      if (data.current_profile) {
        migrateProfileLighting(data.current_profile);
        await api('validate', {
          profile: data.current_profile
        })
      }
      if (!confirm(t('profile.confirmRestore', {
          count: Object.keys(data.profiles).length
        }))) return;
      if (animationTimer || animationStarting) stopAnimation();
      if (timelineTimer) stopTimeline();
      localStorage.setItem('spade65-profiles', JSON.stringify(data.profiles));
      restoreLayoutPreferences(data);
      if (data.current_profile) profile = data.current_profile;
      $('profileName').value = data.profile_name || t('profile.restoredName');
      if (data.language) await setLanguage(data.language);
      renderSavedProfiles();
      renderAllEditors();
      toast(t('profile.libraryRestored'))
    } catch (error) {
      toast(error.message, true)
    }
  };
  reader.readAsText(file)
}

function newProfile() {
  if (!confirm(t('profile.confirmDiscard'))) return;
  profile = migrateProfileLighting(cloneJson(meta.profile));
  colorKeys.clear();
  renderSavedProfiles();
  renderAllEditors();
  toast(t('profile.created'))
}

function setSelectedColor() {
  if (!colorKeys.size) return toast(t('lighting.selectColorKey'), true);
  for (const key of colorKeys) profile.colors[key] = $('colorPicker').value;
  selectCustomLightingDraft();
  renderColorKeyboard();
  renderLayerSummary();
  toast(t('lighting.colorStored', {
    count: colorKeys.size
  }))
}

function clearColors() {
  if (Object.keys(profile.colors).length && !confirm(t('lighting.confirmClearColors'))) return;
  profile.colors = {};
  colorKeys.clear();
  selectCustomLightingDraft();
  renderColorKeyboard();
  renderLayerSummary()
}
async function streamFrame(colors = profile.colors) {
  if (streamBusy) return false;
  streamBusy = true;
  try {
    const requestProfile = cloneJson(profile);
    requestProfile.colors = cloneJson(colors);
    await api('stream', actionPayload({
      profile: requestProfile
    }));
    return true
  } catch (error) {
    stopAnimation();
    stopTimeline();
    toast(error.message, true);
    return false
  } finally {
    streamBusy = false
  }
}

function audioControls() {
  const settings = liveSettings();
  return {
    sensitivity: settings.audio_sensitivity,
    noiseGate: settings.audio_noise_gate,
    smoothing: settings.audio_smoothing
  }
}

function browserAudioSnapshot() {
  if (!audioAnalyser) return null;
  const data = new Uint8Array(audioAnalyser.frequencyBinCount);
  audioAnalyser.getByteFrequencyData(data);
  const nyquist = (audioContext?.sampleRate || 48000) / 2,
    minimumFrequency = 40,
    maximumFrequency = Math.min(16000, nyquist),
    bands = Array.from({
      length: liveEffects.DEFAULT_BAND_COUNT
    }, (_, index) => {
      const ratio = index / Math.max(1, liveEffects.DEFAULT_BAND_COUNT - 1),
        frequency = minimumFrequency * Math.pow(maximumFrequency / minimumFrequency, ratio),
        bin = Math.max(1, Math.min(data.length - 1, Math.round(frequency / nyquist * data.length)));
      return Math.max(data[bin - 1] || 0, data[bin] || 0, data[bin + 1] || 0) / 255
    }),
    level = bands.reduce((sum, value) => sum + value, 0) / Math.max(1, bands.length);
  return {
    scale: 'perceptual',
    level,
    peak: Math.max(0, ...bands),
    bands
  }
}

function currentAudioFrame() {
  const snapshot = browserAudioSnapshot() || audioRawSnapshot || {};
  audioFrame = liveEffects.processAudioSnapshot(snapshot, audioControls(), audioFrame);
  renderAudioMeter(audioFrame);
  return audioFrame
}

function renderAudioMeter(frame = audioFrame) {
  const level = Math.round(Math.max(0, Math.min(1, Number(frame?.peak || frame?.level || 0))) * 100),
    fill = $('audioMeterFill'),
    value = $('audioMeterValue');
  if (fill) fill.style.width = `${level}%`;
  if (value) value.textContent = `${level}%`;
  $('audioMeter')?.setAttribute('aria-valuenow', String(level))
}

function renderAudioSources() {
  const select = $('audioSource');
  if (!select || !profile) return;
  const settings = liveSettings(),
    preferred = settings.audio_source;
  select.innerHTML = '';
  for (const source of audioSourceEntries) {
    const option = document.createElement('option');
    option.value = source.value;
    option.textContent = source.kind === 'system' ? t('lighting.systemAudioSource', {
      name: source.name
    }) : source.id === 'default' ? t('lighting.defaultMicrophone') : t('lighting.microphoneSource', {
      name: source.name
    });
    select.append(option)
  }
  const selected = liveEffects.preferredAudioSource(audioSourceEntries, preferred);
  select.value = selected;
  renderAudioControlState()
}

function renderAudioControlState() {
  const enabled = Boolean($('audioSync')?.checked),
    panel = $('audioControls'),
    selected = audioSourceEntries.find(source => source.value === $('audioSource')?.value),
    hint = $('audioSourceHint');
  if (panel) panel.classList.toggle('disabled-controls', !enabled);
  if (hint) {
    const base = t(selected?.kind === 'system' ? 'lighting.systemAudioHint' : 'lighting.microphoneHint');
    hint.textContent = selected?.kind === 'system' || !audioSystemError ? base : `${t('lighting.systemAudioFallback', {
      error: audioSystemError
    })} ${base}`
  }
  $('audioMeter')?.classList.toggle('active', enabled && Boolean(animationTimer || animationStarting))
}

async function withAudioTimeout(promise, milliseconds) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => timer = setTimeout(() => reject(new Error(t('lighting.audioEnumerationTimeout'))), milliseconds))
    ])
  } finally {
    clearTimeout(timer)
  }
}

async function refreshAudioSources() {
  const entries = [],
    native = window.pywebview?.api;
  audioSystemError = null;
  if (native?.audio_capture_sources) {
    try {
      const result = await withAudioTimeout(native.audio_capture_sources(), 2000);
      if (result?.error) audioSystemError = String(result.error);
      for (const source of result?.sources || []) {
        if (!source || typeof source.id !== 'string' || typeof source.name !== 'string') continue;
        entries.push({
          value: `native:${source.id}`,
          id: source.id,
          name: source.name,
          kind: 'system',
          default: source.default === true
        })
      }
    } catch (error) {
      audioSystemError = error.message || String(error);
      console.warn('Unable to enumerate native audio sources', error)
    }
  } else audioSystemError = t('lighting.systemAudioNativeRequired');
  entries.push({
    value: 'microphone:default',
    id: 'default',
    name: t('lighting.defaultMicrophone'),
    kind: 'microphone'
  });
  audioSourceEntries = entries;
  renderAudioSources();
  if (navigator.mediaDevices?.enumerateDevices) {
    try {
      const devices = await withAudioTimeout(navigator.mediaDevices.enumerateDevices(), 1000);
      for (const device of devices.filter(item => item.kind === 'audioinput' && item.deviceId && item.deviceId !== 'default')) {
        entries.push({
          value: `microphone:${device.deviceId}`,
          id: device.deviceId,
          name: device.label || t('lighting.microphoneNumber', {
            number: entries.filter(item => item.kind === 'microphone').length + 1
          }),
          kind: 'microphone'
        })
      }
    } catch (error) {
      console.warn('Unable to enumerate microphone inputs', error)
    }
  }
  audioSourceEntries = entries;
  renderAudioSources()
}

async function pollNativeAudio(generation) {
  const native = window.pywebview?.api;
  while (audioNativeRunning && generation === audioGeneration) {
    try {
      const snapshot = await native.audio_snapshot();
      if (generation !== audioGeneration) return;
      if (snapshot && typeof snapshot === 'object') audioRawSnapshot = snapshot;
      if (snapshot?.error) throw new Error(snapshot.error)
    } catch (error) {
      if (generation !== audioGeneration) return;
      stopAudio();
      if (animationTimer) stopAnimation();
      toast(t('lighting.audioUnavailable', {
        error: error.message || String(error)
      }), true);
      return
    }
    await new Promise(resolve => setTimeout(resolve, 30))
  }
}

async function beginAudioCapture() {
  if (!audioSourceEntries.length) await refreshAudioSources();
  const settings = liveSettings(),
    selected = $('audioSource')?.value || settings.audio_source,
    source = audioSourceEntries.find(item => item.value === selected) || audioSourceEntries[0];
  if (!source) throw new Error(t('lighting.noAudioSources'));
  const generation = ++audioGeneration;
  audioRawSnapshot = null;
  audioFrame = liveEffects.emptyAudioFrame();
  if (source.kind === 'system') {
    const native = window.pywebview?.api;
    if (!native?.start_audio_capture || !native?.audio_snapshot) throw new Error(t('lighting.systemAudioNativeRequired'));
    await native.start_audio_capture(source.id);
    if (generation !== audioGeneration) {
      await native.stop_audio_capture?.();
      return
    }
    audioNativeRunning = true;
    pollNativeAudio(generation);
    return
  }
  if (!navigator.mediaDevices?.getUserMedia) throw new Error(t('lighting.microphoneUnsupported'));
  const constraints = source.id === 'default' ? true : {
    deviceId: {
      exact: source.id
    },
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false
  };
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: constraints
  });
  if (generation !== audioGeneration) {
    stream.getTracks().forEach(track => track.stop());
    return
  }
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    stream.getTracks().forEach(track => track.stop());
    throw new Error(t('lighting.microphoneUnsupported'))
  }
  audioStream = stream;
  audioContext = new AudioContextClass();
  await audioContext.resume();
  const mediaSource = audioContext.createMediaStreamSource(stream);
  audioAnalyser = audioContext.createAnalyser();
  audioAnalyser.fftSize = 2048;
  audioAnalyser.smoothingTimeConstant = 0;
  mediaSource.connect(audioAnalyser);
  for (const track of stream.getTracks()) track.onended = () => {
    if (generation !== audioGeneration) return;
    stopAudio();
    if (animationTimer) stopAnimation();
    toast(t('lighting.audioSourceEnded'), true)
  }
}

async function startAudio() {
  if (audioAnalyser || audioNativeRunning) return;
  if (!audioStartPromise) audioStartPromise = beginAudioCapture().finally(() => audioStartPromise = null);
  return audioStartPromise
}

function stopAudio() {
  audioGeneration += 1;
  const nativeWasRunning = audioNativeRunning;
  audioNativeRunning = false;
  if (nativeWasRunning) window.pywebview?.api?.stop_audio_capture?.().catch(error => console.warn('Unable to stop native audio capture', error));
  if (audioStream) audioStream.getTracks().forEach(track => {
    track.onended = null;
    track.stop()
  });
  if (audioContext) audioContext.close().catch(() => {});
  audioStream = null;
  audioContext = null;
  audioAnalyser = null;
  audioRawSnapshot = null;
  audioFrame = liveEffects.emptyAudioFrame();
  renderAudioMeter(audioFrame);
  renderAudioControlState()
}

function composeAnimationColors(advance = false) {
  const colors = liveEffects.composeFrame(
    rows, appLayers(), currentAudioFrame(), liveSettings(), animationPhase
  );
  if (advance) animationPhase += 1;
  return colors
}

function refreshLivePreview() {
  if (!profile || !$('liveKeyboard')) return;
  livePreviewColors = composeAnimationColors(false);
  renderLiveKeyboard()
}

function animateColors() {
  const frameColors = composeAnimationColors(true);
  livePreviewColors = frameColors;
  renderLiveKeyboard();
  return streamFrame(frameColors)
}

function hsl(h, s, l) {
  s /= 100;
  l /= 100;
  const k = n => (n + h / 30) % 12,
    a = s * Math.min(l, 1 - l),
    f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return '#' + [f(0), f(8), f(4)].map(x => Math.round(255 * x).toString(16).padStart(2, '0')).join('')
}
async function toggleAnimation() {
  if (animationTimer) return stopAnimation();
  if (animationStarting) return stopAnimation();
  const generation = ++animationGeneration;
  animationStarting = true;
  renderAudioControlState();
  try {
    stopTimeline();
    saveAppLayer();
    if (appLayers().some(layer => layer.enabled !== false && layer.audio)) await startAudio();
    if (generation !== animationGeneration || lightingMode !== 'live') return;
    $('animationBtn').textContent = t('action.stopLivePreview');
    animationTimer = setInterval(animateColors, 1000 / Number($('fps').value));
    animateColors();
    renderLiveEffectStatus()
  } catch (error) {
    if (generation !== animationGeneration) return;
    stopAudio();
    toast(t('lighting.audioUnavailable', {
      error: error.message
    }), true)
  } finally {
    animationStarting = false;
    renderAudioControlState()
  }
}

function stopAnimation() {
  animationGeneration += 1;
  clearInterval(animationTimer);
  animationTimer = null;
  stopAudio();
  refreshLivePreview();
  $('animationBtn').textContent = t('action.startLivePreview');
  renderLiveEffectStatus()
}

function timeline() {
  const settings = profileSettings();
  if (!settings.custom_timeline || typeof settings.custom_timeline !== 'object') settings.custom_timeline = {
    loop: true,
    frames: []
  };
  if (!Array.isArray(settings.custom_timeline.frames)) settings.custom_timeline.frames = [];
  settings.custom_timeline.frames = settings.custom_timeline.frames.slice(0, 200);
  return settings.custom_timeline
}

function renderTimeline() {
  const data = timeline(),
    list = $('timelineList');
  list.innerHTML = '';
  data.frames.forEach((frame, index) => {
    const row = document.createElement('div');
    row.className = 'timeline-frame';
    const label = document.createElement('button');
    label.textContent = t('timeline.frame', {
      number: index + 1,
      count: Object.keys(frame.colors || {}).length
    });
    label.onclick = () => {
      profile.colors = cloneJson(frame.colors || {});
      renderColorKeyboard();
      toast(t('timeline.frameLoaded', {
        number: index + 1
      }))
    };
    const duration = document.createElement('input');
    duration.type = 'number';
    duration.min = 20;
    duration.max = 60000;
    duration.value = frame.duration_ms || 100;
    duration.title = t('timeline.durationTitle');
    duration.setAttribute('aria-label', t('timeline.durationAria', {
      number: index + 1
    }));
    duration.onchange = () => frame.duration_ms = Math.max(20, Math.min(60000, Number(duration.value)));
    const del = document.createElement('button');
    del.textContent = '×';
    del.className = 'danger';
    del.setAttribute('aria-label', t('timeline.removeFrameAria', {
      number: index + 1
    }));
    del.onclick = () => {
      data.frames.splice(index, 1);
      renderTimeline()
    };
    row.append(label, duration, del);
    list.append(row)
  });
  $('timelineEmpty').hidden = Boolean(data.frames.length);
  $('timelineLoop').checked = data.loop !== false;
  $('playTimelineBtn').disabled = !data.frames.length || (!streamingReady() && !timelineTimer);
  $('playTimelineBtn').textContent = t(timelineTimer ? 'action.stopTimeline' : 'action.playTimeline')
}

function captureTimelineFrame() {
  const data = timeline();
  if (data.frames.length >= 200) return toast(t('timeline.maximum'), true);
  data.frames.push({
    duration_ms: 100,
    colors: cloneJson(profile.colors)
  });
  renderTimeline();
  toast(t('timeline.captured'))
}

function playTimelineFrame() {
  const data = timeline();
  if (!timelineTimer || !data.frames.length) return stopTimeline();
  if (timelineIndex >= data.frames.length) {
    if (data.loop !== false) timelineIndex = 0;
    else return stopTimeline()
  }
  const frame = data.frames[timelineIndex++];
  livePreviewColors = cloneJson(frame.colors || {});
  renderLiveKeyboard();
  streamFrame(livePreviewColors);
  renderLiveEffectStatus();
  timelineTimer = setTimeout(playTimelineFrame, Math.max(20, Math.min(60000, Number(frame.duration_ms || 100))))
}

function toggleTimeline() {
  if (timelineTimer) return stopTimeline();
  if (!timeline().frames.length) return;
  stopAnimation();
  timelineIndex = 0;
  timelineTimer = true;
  renderTimeline();
  renderLiveEffectStatus();
  playTimelineFrame()
}

function stopTimeline() {
  if (timelineTimer !== true) clearTimeout(timelineTimer);
  timelineTimer = null;
  timelineIndex = 0;
  refreshLivePreview();
  if ($('playTimelineBtn')) renderTimeline();
  renderLiveEffectStatus()
}

function renderDiagnostics() {
  $('deviceJson').textContent = JSON.stringify(meta.devices, null, 2)
}

function renderAbout() {
  if (meta) $('aboutVersion').textContent = meta.version
}

function renderDesktopIntegration() {
  const platform = $('desktopIntegrationPlatform'),
    closeToTray = $('closeToTray'),
    autoStart = $('autoStartGui'),
    status = $('desktopIntegrationStatus');
  if (!platform || !closeToTray || !autoStart || !status) return;
  if (!desktopIntegration?.available) {
    platform.textContent = t('desktop.browserMode');
    closeToTray.checked = false;
    closeToTray.disabled = true;
    autoStart.checked = false;
    autoStart.disabled = true;
    status.textContent = t('desktop.nativeRequired');
    return
  }

  platform.textContent = t(`service.platform.${desktopIntegration.platform}`);
  closeToTray.checked = Boolean(desktopIntegration.close_to_tray);
  autoStart.checked = Boolean(desktopIntegration.auto_start_enabled);
  if (!desktopIntegration.tray_ready) {
    closeToTray.disabled = true;
    autoStart.disabled = true;
    status.textContent = t('desktop.loading');
    return
  }

  closeToTray.disabled = !desktopIntegration.tray_available;
  autoStart.disabled = !desktopIntegration.auto_start_supported || (!desktopIntegration.tray_available && !desktopIntegration.auto_start_enabled);
  if (desktopIntegration.auto_start_enabled && !desktopIntegration.auto_start_current) status.textContent = t('desktop.autoStartStale');
  else if (!desktopIntegration.tray_available) status.textContent = t('desktop.trayUnavailable');
  else if (desktopIntegration.auto_start_enabled) status.textContent = t('desktop.autoStartEnabled');
  else status.textContent = t('desktop.ready')
}

async function refreshDesktopIntegration() {
  const native = window.pywebview?.api;
  if (!native?.desktop_status) {
    desktopIntegration = {
      available: false
    };
    renderDesktopIntegration();
    return
  }
  try {
    desktopIntegration = await native.desktop_status();
    renderDesktopIntegration()
  } catch (error) {
    desktopIntegration = {
      available: false
    };
    renderDesktopIntegration();
    console.warn('Unable to read desktop integration status', error)
  }
}

async function setDesktopIntegration(method, enabled, successKey) {
  const native = window.pywebview?.api;
  if (!native?.[method]) return;
  try {
    desktopIntegration = await native[method](enabled);
    renderDesktopIntegration();
    toast(t(successKey))
  } catch (error) {
    await refreshDesktopIntegration();
    toast(error.message || String(error), true)
  }
}

const openExternalLink = externalLinks.createHandler(
  () => window.pywebview?.api,
  error => {
    console.warn('Unable to open external link', error);
    toast(t('desktop.externalOpenFailed'), true)
  }
);

function renderServiceSetup() {
  if (!meta?.service_setup) return;
  const setup = meta.service_setup,
    platform = t(`service.platform.${setup.platform}`);
  $('servicePlatform').textContent = platform;
  $('servicePlatform').removeAttribute('data-i18n');
  $('serviceGuideLink').href = externalLinks.guideUrl(currentLanguage);
  $('serviceReleaseWorkflow').hidden = !setup.packaged;
  if (setup.packaged) {
    $('servicePackageNote').textContent = t('service.packageNote', {
      platform
    });
    $('servicePrepareHint').textContent = t('service.prepareHint', {
      configPath: setup.config_path
    });
    $('serviceActivateHint').textContent = t(`service.activateHint.${setup.platform}`, {
      launcherPath: setup.launcher_path
    });
    $('servicePrepareCommands').textContent = setup.prepare_commands;
    $('serviceActivateCommands').textContent = setup.activate_commands
  } else {
    $('servicePackageNote').textContent = t('service.sourceDocsOnly')
  }
}
async function copyServiceCommands(field, successKey) {
  const commands = meta?.service_setup?.[field];
  if (!commands) return;
  try {
    await copyText(field, commands);
    toast(t(successKey))
  } catch (error) {
    toast(t('service.copyFailed'), true)
  }
}

function activatePage(page, updateHash = true) {
  if (!hasOwn(PAGE_HEADERS, page)) return false;
  const header = PAGE_HEADERS[page],
    button = document.querySelector(`#nav button[data-page="${page}"]`),
    section = $(`page-${page}`);
  if (!header || !button || !section) return false;
  if (recordingMacro && page !== 'macros') stopMacroRecording();
  if (pendingMacroAssignment !== null && page !== 'keymap') pendingMacroAssignment = null;
  document.querySelectorAll('#nav button').forEach(item => {
    const active = item === button;
    item.classList.toggle('active', active);
    if (active) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current')
  });
  document.querySelectorAll('.page').forEach(item => item.classList.toggle('active', item === section));
  updatePageHeader(page);
  if (window.matchMedia('(min-width: 641px) and (max-width: 900px)').matches) {
    const navigation = $('nav'),
      navigationBounds = navigation.getBoundingClientRect(),
      buttonBounds = button.getBoundingClientRect();
    navigation.scrollLeft += buttonBounds.left - navigationBounds.left - (navigationBounds.width - buttonBounds.width) / 2
  }
  if (page === 'tester') {
    // Leaving a key held while switching pages would strand it lit.
    testerPressed.clear();
    renderTester()
  }
  if (updateHash && location.hash !== `#${page}`) history.replaceState(null, '', `#${page}`);
  return true
}
document.querySelectorAll('#nav button').forEach(button => button.onclick = () => activatePage(button.dataset.page));
window.addEventListener('hashchange', () => activatePage(location.hash.slice(1), false));
$('testerResetBtn').onclick = resetTester;
document.addEventListener('keydown', testerKeyEvent, true);
document.addEventListener('keyup', testerKeyEvent, true);
window.addEventListener('blur', () => {
  if (recordingMacro) stopMacroRecording();
  if (!testerPressed.size) return;
  testerPressed.clear();
  renderTester()
});
$('copyServicePrepareBtn').onclick = () => copyServiceCommands('prepare_commands', 'service.prepareCopied');
$('copyServiceActivateBtn').onclick = () => copyServiceCommands('activate_commands', 'service.activateCopied');
externalLinks.bind(document, openExternalLink);
$('closeToTray').onchange = event => setDesktopIntegration('set_close_to_tray', event.target.checked, 'desktop.closeToTraySaved');
$('autoStartGui').onchange = event => setDesktopIntegration('set_auto_start', event.target.checked, event.target.checked ? 'desktop.autoStartEnabledSaved' : 'desktop.autoStartDisabledSaved');
document.querySelectorAll('#layerTabs button').forEach(button => button.onclick = () => {
  if (!mayLeaveAssignmentEditor(button.dataset.layer, selectedKey)) return;
  currentLayer = button.dataset.layer;
  document.querySelectorAll('#layerTabs button').forEach(x => x.classList.toggle('active', x === button));
  renderKeyboard()
});
document.querySelectorAll('[data-lighting-mode]').forEach(button => {
  button.onclick = () => chooseLightingMode(button.dataset.lightingMode);
  button.onkeydown = event => {
    const tabs = [...document.querySelectorAll('[data-lighting-mode]')],
      current = tabs.indexOf(button);
    let next = null;
    if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;
    else if (event.key === 'ArrowRight') next = (current + 1) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    if (next === null) return;
    event.preventDefault();
    chooseLightingMode(tabs[next].dataset.lightingMode);
    tabs[next].focus()
  }
});
$('languageSelect').onchange = event => setLanguage(event.target.value);
$('quitBtn').onclick = quitApplication;
for (const id of ['layoutVariant', 'lightingLayoutVariant']) $(id).onchange = e => chooseLayout(e.target.value);
$('deviceSelect').onchange = () => {
  syncLayoutFromSelectedDevice();
  renderConnectionStatus();
  renderMacros()
};
$('refreshBtn').onclick = refresh;
$('assignmentType').onchange = () => {
  assignmentTypeChanged();
  markAssignmentEditorDirty()
};
$('usageSearch').onfocus = event => {
  event.target.select();
  if ($('usageOptions').hidden) openUsagePicker('')
};
$('usageSearch').oninput = event => openUsagePicker(event.target.value);
$('usageSearch').onkeydown = usageSearchKeydown;
$('usageToggle').onclick = () => {
  if (!$('usageOptions').hidden) {
    syncUsageSelection();
    closeUsagePicker();
    return
  }
  $('usageSearch').focus();
  $('usageSearch').select();
  if ($('usageOptions').hidden) openUsagePicker('')
};
$('customUsageInput').oninput = event => {
  $('usageInput').value = event.target.value;
  syncUsageSelection(true);
  markAssignmentEditorDirty()
};
$('customUsageDetails').ontoggle = event => {
  if (!event.target.open) return;
  $('customUsageInput').value = selectedUsage() ? '' : $('usageInput').value.trim()
};
document.addEventListener('pointerdown', event => {
  if ($('usagePicker').contains(event.target) || $('usageOptions').hidden) return;
  syncUsageSelection();
  closeUsagePicker()
});
$('assignBtn').onclick = saveAssignment;
$('discardAssignmentBtn').onclick = discardAssignmentEditorChange;
$('macroAssign').onchange = markAssignmentEditorDirty;
document.querySelectorAll('#modifierWrap input').forEach(input => input.onchange = markAssignmentEditorDirty);
$('goToMacrosFromKeymap').onclick = () => activatePage('macros');
$('winLock').onchange = e => toggleWinLock(e.target.checked);
$('wasdArrows').onchange = e => toggleWasdArrows(e.target.checked);
document.querySelectorAll('.disable-group').forEach(button => button.onclick = () => disableGroup(button.dataset.group));
$('undoDisableBtn').onclick = undoDisabled;
$('newProfileBtn').onclick = newProfile;
$('saveProfileBtn').onclick = saveProfile;
$('deleteProfileBtn').onclick = deleteSavedProfile;
$('savedProfile').onchange = e => loadSavedProfile(e.target.value);
$('exportProfileBtn').onclick = exportProfile;
$('importProfileBtn').onclick = () => $('profileFile').click();
$('profileFile').onchange = e => e.target.files[0] && importProfile(e.target.files[0]);
$('vendorImportBtn').onclick = () => $('vendorFile').click();
$('vendorFile').onchange = e => e.target.files[0] && importVendor(e.target.files[0]);
$('backupLibraryBtn').onclick = backupLibrary;
$('restoreLibraryBtn').onclick = () => $('libraryFile').click();
$('libraryFile').onchange = e => e.target.files[0] && restoreLibrary(e.target.files[0]);
$('applyProfileBtn').onclick = applyProfile;
$('effectSelect').onchange = selectBuiltInLightingDraft;
$('brightness').oninput = e => {
  $('brightnessOut').value = e.target.value;
  updateLightingDraftParameters()
};
$('speed').oninput = e => {
  $('speedOut').value = e.target.value;
  updateLightingDraftParameters()
};
$('colorIndex').onchange = updateLightingDraftParameters;
$('multicolor').onchange = updateLightingDraftParameters;
$('fps').onchange = () => {
  if (!animationTimer) return renderLiveEffectStatus();
  clearInterval(animationTimer);
  animationTimer = setInterval(animateColors, 1000 / Number($('fps').value));
  renderLiveEffectStatus()
};
$('appSpeed').oninput = e => {
  $('appSpeedOut').value = e.target.value;
  saveAppLayer()
};
$('appOpacity').oninput = e => {
  $('appOpacityOut').value = e.target.value;
  saveAppLayer()
};
$('appBandwidth').oninput = e => {
  $('appBandwidthOut').value = e.target.value;
  saveAppLayer()
};
$('appAngle').oninput = e => {
  $('appAngleOut').value = e.target.value;
  saveAppLayer()
};
$('animation').onchange = () => saveAppLayer(true);
for (const id of ['appNumber', 'appGap', 'appFire', 'appCenterX', 'appCenterY', 'appGradient', 'appReverse', 'appBump', 'appBidirectional']) $(id).onchange = () => saveAppLayer();
document.querySelectorAll('.app-color').forEach(input => input.oninput = () => saveAppLayer());
$('audioSync').onchange = audioReactiveChanged;
$('liveBrightness').oninput = event => {
  $('liveBrightnessOut').value = event.target.value;
  saveLiveSettings()
};
$('audioSensitivity').oninput = event => {
  $('audioSensitivityOut').value = event.target.value;
  saveLiveSettings()
};
$('audioNoiseGate').oninput = event => {
  $('audioNoiseGateOut').value = event.target.value;
  saveLiveSettings()
};
$('audioSmoothing').oninput = event => {
  $('audioSmoothingOut').value = event.target.value;
  saveLiveSettings()
};
$('audioMode').onchange = saveLiveSettings;
$('audioSource').onchange = async () => {
  saveLiveSettings(true);
  renderAudioControlState();
  await restartAudioForLivePreview()
};
$('addAppLayerBtn').onclick = addAppLayer;
$('removeAppLayerBtn').onclick = removeAppLayer;
$('setAppRangeBtn').onclick = setAppRange;
$('clearAppRangeBtn').onclick = clearAppRange;
$('applyEffectBtn').onclick = () => {
  selectBuiltInLightingDraft();
  const lighting = cloneJson(lightingDraft),
    target = lightingTarget();
  doAction('rgb', lighting, t('lighting.builtInApplied'), () => {
    rememberLighting(lighting, target)
  })
};
$('setColorBtn').onclick = setSelectedColor;
$('clearColorsBtn').onclick = clearColors;
$('applyColorsBtn').onclick = () => {
  if (!selectCustomLightingDraft()) return toast(t('lighting.addColorFirst'), true);
  const lighting = cloneJson(lightingDraft),
    target = lightingTarget(),
    requestProfile = cloneJson(profile);
  doAction('per-key', {
    profile: requestProfile,
    brightness: lighting.brightness,
    speed: lighting.speed,
    color_index: lighting.color_index,
    multicolor: lighting.multicolor
  }, t('lighting.perKeyApplied'), () => {
    rememberLighting(lighting, target)
  })
};
$('streamOnceBtn').onclick = async () => {
  saveAppLayer();
  const needsAudio = appLayers().some(layer => layer.enabled !== false && layer.audio),
    temporaryAudio = needsAudio && !audioAnalyser && !audioNativeRunning;
  try {
    if (temporaryAudio) {
      await startAudio();
      await new Promise(resolve => setTimeout(resolve, 80))
    }
    if (await animateColors()) $('liveEffectStatus').textContent = t('lighting.framePreviewed')
  } catch (error) {
    toast(t('lighting.audioUnavailable', {
      error: error.message || String(error)
    }), true)
  } finally {
    if (temporaryAudio) stopAudio()
  }
};
$('animationBtn').onclick = toggleAnimation;
$('captureFrameBtn').onclick = captureTimelineFrame;
$('playTimelineBtn').onclick = toggleTimeline;
$('timelineLoop').onchange = e => timeline().loop = e.target.checked;
$('addMacroBtn').onclick = addMacro;
$('deleteMacroBtn').onclick = deleteMacro;
$('addEventBtn').onclick = addEvent;
$('recordMacroBtn').onclick = startMacroRecording;
$('stopMacroBtn').onclick = () => stopMacroRecording();
$('assignMacroToKeyBtn').onclick = assignActiveMacroToKey;
$('prepareMacroApplyBtn').onclick = prepareMacroApply;
$('macroName').onchange = e => {
  if (profile.macros[activeMacro]) {
    profile.macros[activeMacro].name = e.target.value.trim() || t('macro.defaultName', {
      index: profile.macros[activeMacro].index
    });
    renderMacros()
  }
};
$('macroRepeat').onchange = e => {
  if (profile.macros[activeMacro]) {
    profile.macros[activeMacro].repeat = Math.max(0, Math.min(65535, Number(e.target.value) || 0));
    renderMacros()
  }
};
$('debounceBtn').onclick = () => {
  const milliseconds = currentDebounce(),
    target = lightingTarget();
  doAction('debounce', {
    milliseconds
  }, t('settings.debounceApplied'), () => rememberDebounce(milliseconds, target))
};
$('sleepBtn').onclick = () => doAction('sleep', {
  light_off: Number($('lightOff').value),
  hibernate: Number($('hibernate').value)
}, t('settings.timersApplied'));
$('resetBtn').onclick = () => doAction('reset', {
  confirmation: $('resetText').value
}, t('settings.resetSent'));
$('validateBtn').onclick = async () => {
  delete $('validationOutput').dataset.i18n;
  try {
    const result = await api('validate', {
      profile
    });
    $('validationOutput').textContent = JSON.stringify(result, null, 2);
    toast(t('diagnostics.profileValid'))
  } catch (error) {
    $('validationOutput').textContent = error.message;
    toast(error.message, true)
  }
};
async function initialize() {
  await initI18n();
  await refreshDesktopIntegration();
  await refresh();
  const initialPage = location.hash.slice(1);
  activatePage(hasOwn(PAGE_HEADERS, initialPage) ? initialPage : 'device', false);
  refreshAudioSources().catch(error => console.warn('Unable to refresh audio sources', error));
  setInterval(pollDeviceChanges, 2000);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && recordingMacro) stopMacroRecording();
    if (!document.hidden) pollDeviceChanges()
  })
}
window.addEventListener('pywebviewready', async () => {
  await refreshDesktopIntegration();
  await refreshAudioSources()
});
window.addEventListener('beforeunload', stopAudio);
initialize().catch(error => toast(error.message, true));
