from __future__ import annotations

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).parents[1]
WEB = ROOT / "spade65" / "web"
LOCALES = WEB / "locales"
I18N_ATTRIBUTES = {
    "data-i18n",
    "data-i18n-placeholder",
    "data-i18n-title",
    "data-i18n-aria-label",
}
VARIABLE = re.compile(r"\{([A-Za-z0-9_]+)\}")
LITERAL_T_CALL = re.compile(r"(?<![A-Za-z0-9_$])t\(\s*(['\"])([^'\"]+)\1")


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def without_source_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", value)


class TranslationKeyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.keys: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del tag
        for name, value in attrs:
            if name in I18N_ATTRIBUTES:
                assert value, f"{name} must contain a translation key"
                self.keys.add(value)


class I18nTests(unittest.TestCase):
    def test_locale_manifest_has_english_default_and_catalogs(self) -> None:
        manifest = load_json(LOCALES / "index.json")
        self.assertEqual(manifest["default"], "en")
        languages = manifest["languages"]
        self.assertIsInstance(languages, list)
        codes = [language["code"] for language in languages]
        self.assertIn("en", codes)
        self.assertIn("id", codes)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(
            all(re.fullmatch(r"[A-Za-z0-9_-]+", code) for code in codes)
        )
        self.assertTrue(all((LOCALES / f"{code}.json").is_file() for code in codes))

    def test_locale_catalogs_have_identical_keys_and_placeholders(self) -> None:
        english = load_json(LOCALES / "en.json")
        self.assertTrue(english)
        manifest = load_json(LOCALES / "index.json")
        for language in manifest["languages"]:
            code = language["code"]
            catalog = load_json(LOCALES / f"{code}.json")
            with self.subTest(language=code):
                self.assertEqual(set(catalog), set(english))
            for key, english_text in english.items():
                with self.subTest(language=code, key=key):
                    translated_text = catalog[key]
                    self.assertIsInstance(english_text, str)
                    self.assertTrue(english_text.strip())
                    self.assertIsInstance(translated_text, str)
                    self.assertTrue(translated_text.strip())
                    self.assertEqual(
                        set(VARIABLE.findall(translated_text)),
                        set(VARIABLE.findall(english_text)),
                    )

    def test_html_translation_attributes_exist_in_english_catalog(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        english = load_json(LOCALES / "en.json")
        parser = TranslationKeyParser()
        parser.feed(html)
        self.assertTrue(parser.keys)
        self.assertLessEqual(parser.keys, set(english))
        self.assertIn('<html lang="en">', html)
        self.assertIn('id="languageSelect"', html)
        self.assertIn(
            'id="deviceSelect" aria-label="Select device interface" '
            'data-i18n-aria-label="device.select"',
            html,
        )
        self.assertEqual(english["device.select"], "Select device interface")

    def test_literal_javascript_translation_keys_exist(self) -> None:
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        english = load_json(LOCALES / "en.json")
        used = {match.group(2) for match in LITERAL_T_CALL.finditer(javascript)}
        self.assertTrue(used)
        self.assertLessEqual(used, set(english))

    def test_dynamic_javascript_translation_keys_exist(self) -> None:
        english = load_json(LOCALES / "en.json")
        dynamic_keys = {
            *(f"usageGroup.{name}" for name in (
                "Keyboard",
                "Numpad",
                "Media",
                "Browser/System",
                "Mouse",
                "Keyboard control",
            )),
            *(f"group.{name}" for name in (
                "numbers",
                "letters",
                "symbols",
                "controls",
                "allKeys",
            )),
            *(f"animation.{name}" for name in (
                "wave",
                "conic",
                "spiral",
                "cycle",
                "linearWave",
                "ripple",
                "breathe",
                "rain",
                "fire",
                "trigger",
            )),
            *(f"effect.{name}" for name in (
                "neon-stream",
                "fixed",
                "breathe",
                "ripples-shining",
                "rainbow-wheel",
                "ripple-band-up-down",
                "reaction",
                "two-block",
                "random-color",
                "double-wave",
                "retro-snake",
                "double-spiral",
                "ripple-band",
                "kamehameha",
                "wave-90",
                "intersect",
                "shadow-disappear",
                "follow",
                "snake-up-down",
                "custom",
            )),
            *(f"subtitle.{name}" for name in (
                "device",
                "keymap",
                "lighting",
                "macros",
                "settings",
                "diagnostics",
            )),
            "action.record",
            "action.stopRecording",
            "action.playTimeline",
            "action.stopTimeline",
            "action.startAnimation",
            "action.stopAnimation",
            "keymap.winDisabled",
            "keymap.winRestored",
            "keymap.wasdSwapped",
            "keymap.wasdRestored",
            *(f"service.platform.{name}" for name in (
                "linux",
                "windows",
                "macos",
            )),
            *(f"service.activateHint.{name}" for name in (
                "linux",
                "windows",
                "macos",
            )),
        }
        self.assertLessEqual(dynamic_keys, set(english))

    def test_i18n_runtime_keeps_english_fallback_and_persists_choice(self) -> None:
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        compact = without_source_whitespace(javascript)
        self.assertIn("DEFAULT_LANGUAGE='en'", compact)
        self.assertIn("spade65-language", compact)
        self.assertIn("catalogs[DEFAULT_LANGUAGE]?.[key]", compact)
        self.assertIn(
            "localStorage.setItem(I18N_STORAGE_KEY,currentLanguage)", compact
        )
        self.assertIn("document.documentElement.lang=currentLanguage", compact)
        self.assertIn("window.pywebview?.api?.save_json", compact)

    def test_keyboard_and_lighting_share_device_aware_layout_state(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        compact = without_source_whitespace(javascript)
        self.assertIn('id="layoutVariant"', html)
        self.assertIn('id="lightingLayoutVariant"', html)
        self.assertLess(
            html.index('<script src="/layout-state.js"></script>'),
            html.index('<script src="/app.js"></script>'),
        )
        self.assertIn("spade65-device-layouts-v1", compact)
        self.assertIn("syncLayoutFromSelectedDevice(false)", compact)
        self.assertIn("$('deviceSelect').onchange", compact)
        self.assertIn("setInterval(pollDeviceChanges,2000)", compact)
        self.assertIn("snapshot===deviceSnapshot", compact)
        self.assertIn("device_layouts:storedDeviceLayouts()", compact)
        self.assertIn("Array.isArray(data.profiles)", compact)
        self.assertNotIn(
            "layoutVariant=localStorage.getItem('spade65-layout')", compact
        )


if __name__ == "__main__":
    unittest.main()
