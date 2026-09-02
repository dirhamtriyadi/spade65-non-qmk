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
PAGE_HEADER_ENTRY = re.compile(
    r"^\s{2}([a-z][a-z0-9-]*): \{\s*\n"
    r"\s+title: '([^']+)',\s*\n"
    r"\s+subtitle: '([^']+)'\s*\n"
    r"\s+\}",
    re.MULTILINE,
)


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


class IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del tag
        identifier = dict(attrs).get("id")
        if identifier:
            self.ids.append(identifier)


class ExternalLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: dict[str, dict[str, str | None]] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if tag == "a" and element_id:
            self.links[element_id] = attributes


class PageRegistryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nav_pages: set[str] = set()
        self.section_pages: set[str] = set()
        self.current_pages: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        page = attributes.get("data-page")
        if tag == "button" and page:
            self.nav_pages.add(page)
            if attributes.get("aria-current") == "page":
                self.current_pages.add(page)
        section_id = attributes.get("id", "")
        if tag == "section" and section_id.startswith("page-"):
            self.section_pages.add(section_id.removeprefix("page-"))


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
            *(f"macro.sequence.{name}" for name in (
                "duplicate",
                "release",
                "held",
                "unknown",
            )),
            *(f"subtitle.{name}" for name in (
                "device",
                "keymap",
                "tester",
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
            "macro.nextStepFix",
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

    def test_navigation_pages_have_complete_safe_header_metadata(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        parser = PageRegistryParser()
        parser.feed(html)
        headers = {
            page: (title, subtitle)
            for page, title, subtitle in PAGE_HEADER_ENTRY.findall(javascript)
        }

        self.assertEqual(parser.nav_pages, parser.section_pages)
        self.assertEqual(parser.nav_pages, set(headers))
        self.assertEqual(parser.current_pages, {"device"})
        self.assertIn("tester", headers)
        self.assertEqual(headers["tester"], ("nav.tester", "subtitle.tester"))

        manifest = load_json(LOCALES / "index.json")
        for language in manifest["languages"]:
            catalog = load_json(LOCALES / f"{language['code']}.json")
            for page, keys in headers.items():
                for key in keys:
                    with self.subTest(language=language["code"], page=page, key=key):
                        self.assertIn(key, catalog)
                        self.assertTrue(catalog[key].strip())

        compact = without_source_whitespace(javascript)
        self.assertIn("if(typeofkey!=='string'||!key)return''", compact)
        self.assertIn("hasOwn(PAGE_HEADERS,initialPage)", compact)
        self.assertNotIn("constsubtitles=", compact)
        self.assertNotIn("constpageLabels=", compact)

    def test_shared_ui_patterns_cover_page_controls_and_responsive_content(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        app_css = (WEB / "app.css").read_text(encoding="utf-8")
        keyboard_css = (WEB / "keyboard.css").read_text(encoding="utf-8")

        for marker in (
            'class="app-header"',
            'class="profile-apply-bar"',
            'class="tester-legend"',
            'class="input-with-unit"',
            'class="table-scroll"',
        ):
            self.assertIn(marker, html)
        for selector in (
            ".app-header",
            ".page.active",
            ".switch-line",
            ".tester-readout",
            ".table-scroll",
            "@media(max-width:640px)",
        ):
            self.assertIn(selector, app_css)
        self.assertNotRegex(app_css, r"(?m)^\.keyboard \{")
        self.assertIn(".keyboard .key:disabled", keyboard_css)
        self.assertIn(".keyboard .key.assigned::after", keyboard_css)

    def test_guided_editors_keep_advanced_controls_out_of_the_main_path(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        app_css = (WEB / "app.css").read_text(encoding="utf-8")
        compact = without_source_whitespace(javascript)

        for marker in (
            'id="keymapEmptyState"',
            'id="keyAssignmentEditor" class="editor-fieldset" disabled hidden',
            'id="lightingPresetPanel"',
            'id="lightingPerKeyPanel"',
            'id="lightingLivePanel"',
            'id="macroListEmpty"',
            'id="macroEditorEmpty"',
            'id="macroRecordingBanner"',
            'id="macroSequenceStatus"',
            'id="assignMacroToKeyBtn"',
            'id="prepareMacroApplyBtn"',
            'class="keyboard-scroll"><div id="testerKeyboard"',
        ):
            self.assertIn(marker, html)
        self.assertGreaterEqual(html.count('class="feature-details"'), 4)
        self.assertIn(".workflow-steps", app_css)
        self.assertIn(".mode-switcher", app_css)
        self.assertIn(".empty-state", app_css)
        self.assertIn(".card .draft-status", app_css)
        self.assertIn(".button-row.flush", app_css)
        disabled_card = app_css.split(".disabled-card {", 1)[1].split("}", 1)[0]
        self.assertIn("display: grid", disabled_card)
        self.assertIn("gap: 12px", disabled_card)
        self.assertIn("chooseLightingMode(button.dataset.lightingMode)", compact)
        self.assertIn("$('keyAssignmentEditor').disabled=!hasSelection", compact)
        self.assertIn("pendingMacroAssignment=macro.index", compact)
        self.assertIn("assignmentEditorKey!==assignmentIdentity()", compact)
        self.assertIn("selected.pid==='0351'", compact)
        self.assertIn("macro.events.length+1+pressedAfter>84", compact)
        self.assertIn("functionmacroSequenceIssue(macro)", compact)
        self.assertIn("macro.events.push({delay_ms:20,usage:'a',pressed:true},{delay_ms:20,usage:'a',pressed:false})", compact)
        self.assertIn("appliedMacroSnapshot?.device===device()", compact)
        self.assertIn("state:macroStateSnapshot(requestProfile)", compact)
        self.assertIn("Math.min(32767", compact)
        self.assertNotIn("macro.events.splice(index,1);break", compact)

        composition = javascript.split("function composeAnimationColors", 1)[1].split(
            "function refreshLivePreview", 1
        )[0]
        playback = javascript.split("function playTimelineFrame()", 1)[1].split(
            "function toggleTimeline", 1
        )[0]
        self.assertIn("frameColors[key]", composition)
        self.assertNotIn("profile.colors[key]", composition)
        self.assertIn("applyMasterBrightness", composition)
        self.assertNotIn("profile.colors =", playback)

        macro_assignment = compact.split(
            "functionassignActiveMacroToKey()", 1
        )[1].split("functionprepareMacroApply()", 1)[0]
        leave_guard = "if(!mayLeaveAssignmentEditor(currentLayer,null))return"
        self.assertIn(leave_guard, macro_assignment)
        self.assertLess(
            macro_assignment.index(leave_guard),
            macro_assignment.index("pendingMacroAssignment=macro.index"),
        )

    def test_html_ids_remain_unique(self) -> None:
        parser = IdParser()
        parser.feed((WEB / "index.html").read_text(encoding="utf-8"))
        duplicates = sorted(
            identifier
            for identifier in set(parser.ids)
            if parser.ids.count(identifier) > 1
        )
        self.assertEqual(duplicates, [])

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

    def test_external_links_use_the_native_bridge_without_breaking_browser_mode(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        compact = without_source_whitespace(javascript)
        parser = ExternalLinkParser()
        parser.feed(html)
        link_ids = (
            "serviceGuideLink",
            "repoLink",
            "updatesLink",
            "releaseNotesLink",
        )
        self.assertEqual(set(parser.links), set(link_ids))
        for link_id in link_ids:
            attributes = parser.links[link_id]
            self.assertEqual(attributes["target"], "_blank")
            self.assertEqual(
                set((attributes["rel"] or "").split()), {"noopener", "noreferrer"}
            )
        self.assertEqual(
            parser.links["serviceGuideLink"]["href"],
            "https://github.com/dirhamtriyadi/spade65-non-qmk/"
            "blob/main/docs/host-features.md",
        )
        self.assertIn("externalLinks.bind(document,openExternalLink)", compact)
        self.assertIn(
            "$('serviceGuideLink').href=externalLinks.guideUrl(currentLanguage)",
            compact,
        )
        self.assertLess(
            html.index('<script src="/external-links.js"></script>'),
            html.index('<script src="/app.js"></script>'),
        )
        self.assertLess(
            html.index('<script src="/clipboard.js"></script>'),
            html.index('<script src="/app.js"></script>'),
        )
        self.assertLess(
            html.index('<script src="/live-effects.js"></script>'),
            html.index('<script src="/app.js"></script>'),
        )

    def test_service_copy_buttons_use_the_canonical_clipboard_bridge(self) -> None:
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        clipboard = (WEB / "clipboard.js").read_text(encoding="utf-8")
        compact = without_source_whitespace(javascript)
        self.assertIn("awaitcopyText(field,commands)", compact)
        self.assertIn(
            "copyServiceCommands('prepare_commands','service.prepareCopied')",
            compact,
        )
        self.assertIn(
            "copyServiceCommands('activate_commands','service.activateCopied')",
            compact,
        )
        self.assertIn("native.copy_service_commands(field)", clipboard)
        self.assertNotIn("native.copy_text", clipboard)

    def test_keyboard_and_lighting_share_device_aware_layout_state(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        javascript = (WEB / "app.js").read_text(encoding="utf-8")
        compact = without_source_whitespace(javascript)
        self.assertIn('id="layoutVariant"', html)
        self.assertIn('id="lightingLayoutVariant"', html)
        self.assertIn('id="usageSearch"', html)
        self.assertIn('role="listbox"', html)
        self.assertIn('id="usageInput" type="hidden"', html)
        self.assertIn('id="customUsageInput"', html)
        self.assertIn('id="macroUsageList"', html)
        self.assertNotIn('id="usageList"', html)
        self.assertIn("usage.setAttribute('list','macroUsageList')", compact)
        self.assertNotIn("a, play-pause, mouse-left, or 0x04", html)
        self.assertIn("usagePicker.resolveUsage", javascript)
        self.assertNotIn("open=Boolean(raw&&!selected)", compact)
        self.assertLess(
            html.index('<script src="/layout-state.js"></script>'),
            html.index('<script src="/app.js"></script>'),
        )
        self.assertLess(
            html.index('<script src="/usage-picker.js"></script>'),
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
