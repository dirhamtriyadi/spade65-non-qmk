**English** · [Bahasa Indonesia](id/localization.md)

# GUI localization

The GUI uses JSON catalogs bundled with the application. English (`en`) is both
the canonical and default language, and Bahasa Indonesia (`id`) has been
available since version `0.6.0`. The sidebar selection is stored in
`localStorage` under the `spade65-language` key. Since v0.7.0, the standalone
window has used an application-specific WebView profile with
`private_mode=False`, so the selection remains in effect after reopening the GUI
at the same localhost origin. Desktop storage resides in Windows Local AppData
and Linux XDG data; on macOS, Cocoa WebKit uses the persistent default website
data store managed by the operating system for the application bundle ID.

The `gui --browser` mode and browser fallback use the browser profile's
`localStorage`, which is separate from WebView storage. A library backup includes
the language code, and export downloads remain supported in the desktop window;
restore reapplies the language if that locale is still supported. Backup and
restore are also the safe way to transfer profiles and language preferences
between a WebView and a browser. The browser language is not detected
automatically.

If the manifest or selected locale cannot be loaded, the GUI returns to English.
English text embedded in the HTML is also the earliest fallback so the page
remains usable if catalogs cannot be served.

## File structure

```text
spade65/web/
├── index.html
├── app.js
└── locales/
    ├── index.json
    ├── en.json
    └── id.json
```

`locales/index.json` is the language manifest:

```json
{
  "default": "en",
  "languages": [
    {"code": "en", "name": "English"},
    {"code": "id", "name": "Bahasa Indonesia"}
  ]
}
```

Each filename must match its `code`, use only letters, digits, `_`, or `-`, and
end in `.json`. The server serves only this safe filename pattern. Locale files
are included through setuptools package data and PyInstaller data collection, so
catalog changes apply to both source installations and desktop packages.

## String conventions

Every locale must contain the same keys as `en.json`. Use stable keys based on
their area and meaning, such as `nav.device`, `action.applyProfile`, or
`profile.savedLocal`; do not use an English sentence as a key.

For static HTML text, select the attribute appropriate to the target:

```html
<h3 data-i18n="safety.title">Safety status</h3>
<input data-i18n-placeholder="keymap.usagePlaceholder"
       placeholder="a, play-pause, mouse-left, or 0x04">
<button data-i18n-title="action.remove" title="Remove">×</button>
<select data-i18n-aria-label="device.select" aria-label="Device"></select>
```

- `data-i18n` replaces `textContent`;
- `data-i18n-placeholder` replaces `placeholder`;
- `data-i18n-title` replaces `title`;
- `data-i18n-aria-label` replaces `aria-label`.

Keep a meaningful English fallback in the markup. Do not attach `data-i18n` to
an element containing child nodes that must be preserved, because replacing its
`textContent` removes those children.

Dynamically created strings in `app.js` must use the `t()` helper:

```javascript
toast(t('profile.savedLocal', {name}));
```

Interpolation uses named placeholders in the form `{name}`. Placeholder names
and counts must be identical in every language. Do not concatenate translated
fragments to form a sentence; provide one complete key so word order can differ
between languages. After the language changes, call the relevant dynamic
renderers from `renderLocalizedDynamic()` so lists and statuses already on the
screen are updated as well.

Backend text, device names, paths, HID keycodes, literal confirmation tokens such
as `RESET SPADE65`/`APPLY PROFILE`, and JSON diagnostic contents do not need
translation. When a UI message wraps a backend error, translate the UI portion
and insert the error details as a placeholder.

## Adding a language

For example, to add Japanese with the code `ja`:

1. Copy `spade65/web/locales/en.json` to
   `spade65/web/locales/ja.json`.
2. Translate every value without changing keys or `{...}` placeholders.
3. Add `{"code": "ja", "name": "日本語"}` to the `languages` array in
   `locales/index.json`. This name is displayed in the language selector.
4. Run the tests and catalog checks below.
5. Open the desktop window, change the language, close and relaunch the
   application, and verify that the selection persists.
6. Repeat with `gui --browser`, then inspect every page, dialog, toast,
   placeholder, title, export download, and accessibility label.

There is no need to change the backend, route list, `pyproject.toml`, or
PyInstaller spec for each new language as long as the file follows the naming
pattern above. English must remain the `default`, canonical key set, and
fallback.

## Documentation language convention

English is also the canonical documentation language. `README.md`, every
top-level guide in `docs/`, and `packaging/README.md` must be written in English
and must link to other English guides by default. Their maintained Indonesian
counterparts are `README.id.md`, `docs/id/<name>.md`, and
`packaging/README.id.md`. The language switch at the top of each document is the
only canonical-page link that should enter the Indonesian documentation tree.

Create or update the English document first, then apply the same factual and
safety changes to its Indonesian counterpart. Keep command lines, paths,
confirmation tokens, and protocol identifiers unchanged. Legal notices that
reproduce third-party terms remain in their original English form. README
preview screenshots should show the GUI in its default English locale.

## Validation

Run the full test suite, JavaScript syntax check, and catalog consistency check:

```bash
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py packaging tests
node --check spade65/web/app.js
```

For a quick check that catalogs can be read and have identical keys:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path("spade65/web/locales")
manifest = json.loads((root / "index.json").read_text(encoding="utf-8"))
catalogs = {
    item["code"]: json.loads(
        (root / f'{item["code"]}.json').read_text(encoding="utf-8")
    )
    for item in manifest["languages"]
}
english = set(catalogs["en"])
for code, catalog in catalogs.items():
    assert set(catalog) == english, (code, english ^ set(catalog))
print(f"{len(catalogs)} locales, {len(english)} keys: OK")
PY
```

In addition to key parity, human review remains necessary for terminology,
label length in narrow layouts, plurals and context, and placeholder accuracy.
