import hashlib
import io
import importlib.util
import tempfile
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build = load_script("spade65_packaging_build", "packaging/build.py")
versions = load_script("spade65_packaging_versions", "packaging/check_version.py")
launcher = load_script("spade65_packaging_launcher", "packaging/launcher.py")


class PackagingTests(unittest.TestCase):
    def test_desktop_launcher_uses_the_reserved_local_gui_port(self):
        self.assertEqual(launcher.GUI_HOST, "127.0.0.1")
        self.assertEqual(launcher.GUI_PORT, 8765)
        self.assertEqual(launcher.GUI_URL, "http://127.0.0.1:8765/")

    def test_no_argument_executable_uses_the_shared_gui_coordinator(self):
        with (
            patch.object(launcher.sys, "argv", ["Spade65"]),
            patch.object(launcher.multiprocessing, "freeze_support"),
            patch.object(launcher, "has_visible_console", return_value=True),
            patch.object(launcher, "launch_gui") as launch_gui,
        ):
            self.assertEqual(launcher.main(), 0)
        launch_gui.assert_called_once_with(
            host="127.0.0.1", port=8765, mode="desktop"
        )

    def test_no_argument_startup_error_is_reported_without_a_traceback_escape(self):
        failure = RuntimeError("foreign service owns port")
        with (
            patch.object(launcher.sys, "argv", ["Spade65"]),
            patch.object(launcher.multiprocessing, "freeze_support"),
            patch.object(launcher, "has_visible_console", return_value=False),
            patch.object(
                launcher,
                "ensure_standard_streams",
                return_value=Path("/logs/launcher.log"),
            ),
            patch.object(launcher, "launch_gui", side_effect=failure),
            patch.object(launcher, "report_windowed_failure") as report,
        ):
            self.assertEqual(launcher.main(), 1)
        report.assert_called_once_with(failure, Path("/logs/launcher.log"))

    def test_noninteractive_cli_failure_does_not_create_a_popup(self):
        with (
            patch.object(launcher.sys, "argv", ["Spade65", "probe"]),
            patch.object(launcher.multiprocessing, "freeze_support"),
            patch.object(launcher, "has_visible_console", return_value=False),
            patch.object(launcher, "ensure_standard_streams", return_value=None),
            patch("spade65.cli.main", return_value=2),
            patch.object(launcher, "show_startup_error") as show_error,
        ):
            self.assertEqual(launcher.main(), 2)
        show_error.assert_not_called()

    def test_noninteractive_explicit_gui_failure_is_visible(self):
        with (
            patch.object(launcher.sys, "argv", ["Spade65", "gui"]),
            patch.object(launcher.multiprocessing, "freeze_support"),
            patch.object(launcher, "has_visible_console", return_value=False),
            patch.object(
                launcher,
                "ensure_standard_streams",
                return_value=Path("/logs/launcher.log"),
            ),
            patch("spade65.cli.main", return_value=1),
            patch.object(launcher, "show_startup_error") as show_error,
        ):
            self.assertEqual(launcher.main(), 1)
        show_error.assert_called_once()

    def test_windowed_launcher_replaces_missing_standard_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "launcher.log"
            with (
                patch.object(launcher.sys, "stdout", None),
                patch.object(launcher.sys, "stderr", None),
            ):
                self.assertEqual(
                    launcher.ensure_standard_streams(log_path=log_path), log_path
                )
                streams = (launcher.sys.stdout, launcher.sys.stderr)
                self.assertTrue(all(stream is not None for stream in streams))
                self.assertIs(streams[0], streams[1])
                streams[0].close()
            self.assertIn("Spade65 launcher", log_path.read_text(encoding="utf-8"))
        launcher._DEVNULL_STREAMS.clear()

    def test_non_tty_stream_is_preserved_and_mirrored_to_the_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "launcher.log"
            inherited = io.StringIO()
            with (
                patch.object(launcher.sys, "stdout", inherited),
                patch.object(launcher.sys, "stderr", inherited),
            ):
                self.assertFalse(launcher.has_visible_console())
                launcher.ensure_standard_streams(
                    log_path=log_path, force_log=True
                )
                print("visible diagnostic", file=launcher.sys.stderr)
                launcher.sys.stderr.flush()
                launcher._DEVNULL_STREAMS[-1].close()
            self.assertIn("visible diagnostic", inherited.getvalue())
            self.assertIn(
                "visible diagnostic", log_path.read_text(encoding="utf-8")
            )
        launcher._DEVNULL_STREAMS.clear()

    def test_native_commands_use_platform_scripts(self):
        root = Path("/source")

        def executable(name: str) -> str | None:
            return {"bash": "/bin/bash", "pwsh": "C:/pwsh.exe"}.get(name)

        linux = build.native_command(
            "linux", root=root, find_executable=executable
        )
        macos = build.native_command(
            "macos", root=root, find_executable=executable
        )
        windows = build.native_command(
            "windows", root=root, find_executable=executable
        )
        self.assertEqual(Path(linux[-1]), root / "packaging" / "build_linux.sh")
        self.assertEqual(Path(macos[-1]), root / "packaging" / "build_macos.sh")
        self.assertEqual(
            Path(windows[-1]), root / "packaging" / "build_windows.ps1"
        )

    def test_architecture_guard_rejects_mislabeled_build(self):
        build.validate_architecture("linux", "x86_64")
        build.validate_architecture("windows", "AMD64")
        build.validate_architecture("macos", "arm64")
        with self.assertRaisesRegex(RuntimeError, "requires an x86_64 host"):
            build.validate_architecture("linux", "aarch64")

    def test_source_version_requires_pyproject_and_package_to_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "spade65").mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nversion = "1.2.3"\n', encoding="utf-8"
            )
            package = root / "spade65" / "__init__.py"
            package.write_text('__version__ = "1.2.3"\n', encoding="utf-8")
            self.assertEqual(versions.matching_source_version(root), "1.2.3")
            package.write_text('__version__ = "1.2.4"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source versions disagree"):
                versions.matching_source_version(root)

    def test_python_310_version_parser_fallback(self):
        contents = '[build-system]\nrequires = []\n\n[project]\nversion = "2.3.4"\n'
        with patch.object(versions, "tomllib", None):
            self.assertEqual(versions.project_version_from_text(contents), "2.3.4")

    def test_dispatcher_uses_current_python_and_checks_exact_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifacts" / build.ARTIFACTS["linux"]
            artifact.parent.mkdir()
            artifact.write_bytes(b"AppImage")
            with (
                patch.object(build, "ROOT", root),
                patch.object(build, "platform_family", return_value="linux"),
                patch.object(build, "validate_architecture"),
                patch.object(build, "native_command", return_value=["bash", "build"]),
                patch.object(build.subprocess, "run") as run,
            ):
                self.assertEqual(build.main([]), 0)
        _, keyword_arguments = run.call_args
        self.assertEqual(keyword_arguments["cwd"], root)
        self.assertEqual(
            keyword_arguments["env"]["SPADE65_BUILD_PYTHON"], build.sys.executable
        )
        self.assertTrue(keyword_arguments["check"])

    def test_release_commands_have_explicit_repository_context(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("GH_REPO: ${{ github.repository }}", workflow)
        self.assertIn("needs.validate.outputs.commit", workflow)
        self.assertIn("needs: [validate, windows, linux, macos]", workflow)
        self.assertIn("format('refs/tags/{0}', inputs.tag)", workflow)
        self.assertIn("Tag ${RELEASE_TAG} moved after validation", workflow)
        self.assertIn("already published; refusing overwrite", workflow)
        self.assertIn("node --check spade65/web/app.js", workflow)
        self.assertIn("node --check spade65/web/layout-state.js", workflow)
        self.assertIn("node --check spade65/web/key-events.js", workflow)
        self.assertIn("node --check spade65/web/usage-picker.js", workflow)
        self.assertIn("node --check spade65/web/external-links.js", workflow)
        self.assertIn("node --check spade65/web/clipboard.js", workflow)
        self.assertIn("node --check spade65/web/live-effects.js", workflow)
        self.assertIn("node tests/layout_state.test.js", workflow)
        self.assertIn("node tests/key_events.test.js", workflow)
        self.assertIn("node tests/usage_picker.test.js", workflow)
        self.assertIn("node tests/external_links.test.js", workflow)
        self.assertIn("node tests/clipboard.test.js", workflow)
        self.assertIn("node tests/live_effects.test.js", workflow)
        self.assertIn("group: release-${{", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertEqual(workflow.count("retention-days: 1"), 3)

        cleanup = (
            ROOT / ".github" / "workflows" / "release-artifact-cleanup.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflows: [release]", cleanup)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", cleanup)
        self.assertIn("actions: write", cleanup)
        self.assertIn("actions/runs/${run_id}/artifacts", cleanup)
        self.assertIn("actions/artifacts/${artifact_id}", cleanup)
        self.assertIn("workflows/release.yml/runs?status=completed", cleanup)

    def test_jenkins_fallback_keeps_native_release_guardrails(self):
        pipeline = (ROOT / "Jenkinsfile").read_text(encoding="utf-8")

        self.assertIn("agent none", pipeline)
        self.assertIn("skipDefaultCheckout(true)", pipeline)
        self.assertIn("disableConcurrentBuilds()", pipeline)
        self.assertIn("buildDiscarder(logRotator(", pipeline)
        self.assertIn("artifactNumToKeepStr: '3'", pipeline)
        self.assertIn("name: 'BUILD_DESKTOP'", pipeline)
        self.assertIn("defaultValue: false", pipeline)
        self.assertIn("name: 'PUBLISH_RELEASE'", pipeline)
        self.assertIn("PUBLISH_RELEASE requires RELEASE_TAG", pipeline)
        self.assertIn("Publishing is forbidden from pull-request jobs", pipeline)
        self.assertIn("allowed only from the main branch job", pipeline)

        self.assertIn("name 'PLATFORM'", pipeline)
        self.assertIn("values 'linux', 'windows', 'macos'", pipeline)
        self.assertIn("name 'PYTHON_VERSION'", pipeline)
        self.assertIn("values '3.10', '3.13'", pipeline)
        for label in ("linux", "windows", "macos"):
            self.assertIn(f"agent {{ label '{label}' }}", pipeline)

        self.assertIn("SPADE65_STRICT_LINUX_LEGAL = '1'", pipeline)
        self.assertIn("python3.13 packaging/check_version.py", pipeline)
        self.assertEqual(pipeline.count("packaging/build.py"), 2)
        self.assertIn(r"packaging\build.py", pipeline)
        for artifact in build.ARTIFACTS.values():
            self.assertIn(artifact, pipeline)
        self.assertIn("archiveArtifacts(", pipeline)
        self.assertIn("fingerprint: true", pipeline)

        self.assertIn(
            "GH_REPO = 'dirhamtriyadi/spade65-non-qmk'", pipeline
        )
        self.assertEqual(
            pipeline.count("credentialsId: 'spade65-github-token'"), 2
        )
        self.assertIn("already published; refusing overwrite", pipeline)
        self.assertIn("Tag ${RELEASE_TAG} moved after validation", pipeline)
        self.assertIn("Unexpected release remote", pipeline)
        self.assertIn("Draft contains unexpected assets", pipeline)
        self.assertIn("test \"$asset_count\" -eq 3", pipeline)
        self.assertIn("node --check spade65/web/external-links.js", pipeline)
        self.assertIn(r"node --check spade65\web\external-links.js", pipeline)
        self.assertIn("node --check spade65/web/clipboard.js", pipeline)
        self.assertIn(r"node --check spade65\web\clipboard.js", pipeline)
        self.assertIn("node --check spade65/web/live-effects.js", pipeline)
        self.assertIn(r"node --check spade65\web\live-effects.js", pipeline)
        self.assertIn("node tests/external_links.test.js", pipeline)
        self.assertIn(r"node tests\external_links.test.js", pipeline)
        self.assertIn("node tests/clipboard.test.js", pipeline)
        self.assertIn(r"node tests\clipboard.test.js", pipeline)
        self.assertIn("node tests/live_effects.test.js", pipeline)
        self.assertIn(r"node tests\live_effects.test.js", pipeline)

        test_workflow = (
            ROOT / ".github" / "workflows" / "test.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "node --check spade65/web/external-links.js", test_workflow
        )
        self.assertIn("node tests/external_links.test.js", test_workflow)
        self.assertIn(
            "node --check spade65/web/clipboard.js", test_workflow
        )
        self.assertIn("node tests/clipboard.test.js", test_workflow)
        self.assertIn(
            "node --check spade65/web/live-effects.js", test_workflow
        )
        self.assertIn("node tests/live_effects.test.js", test_workflow)

    def test_linux_packager_pins_tool_and_embedded_runtime(self):
        script = (ROOT / "packaging" / "build_linux.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0",
            script,
        )
        self.assertIn(
            "1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf",
            script,
        )
        self.assertIn(
            "https://github.com/AppImage/type2-runtime/releases/download/"
            "continuous/runtime-x86_64",
            script,
        )
        self.assertNotIn(
            "https://api.github.com/repos/AppImage/type2-runtime/releases/assets/",
            script,
        )
        self.assertIn('--runtime-file "$runtime_file"', script)
        for forbidden in (
            "Qt6Graphs",
            "Qt6DataVisualization",
            "Qt6Quick3D",
            "Qt6QuickTimeline",
            "Qt6VirtualKeyboard",
            "Qt6WaylandCompositor",
        ):
            self.assertIn(forbidden, script)
        self.assertIn("Forbidden GPL-only Qt module", script)
        self.assertIn("Unexpected HIDAPI payload", script)
        self.assertIn("hidapi.libs", script)
        self.assertIn("Host-bound Linux runtime entered the bundle", script)
        for library in (
            "libstdc++.so",
            "libgcc_s.so",
            "libgbm.so",
            "libfontconfig.so",
            "libfreetype.so",
            "libexpat.so",
            "libX11.so",
            "libX11-xcb.so",
            "libasound.so",
            "libEGL.so",
            "libGL.so",
            "libdrm",
            "libvulkan.so",
            "libva.so",
            "libxcb.so",
            "libwayland-client.so",
            "libglapi.so",
            "libharfbuzz.so",
        ):
            self.assertIn(library, script)
        self.assertIn("Required Qt/XCB runtime was not bundled", script)
        for library in (
            "libxcb-shape.so.0",
            "libxcb-image.so.0",
            "libxcb-xkb.so.1",
            "libxcb-icccm.so.4",
            "libxkbcommon-x11.so.0",
            "libxcb-util.so.1",
            "libxcb-cursor.so.0",
            "libxcb-keysyms.so.1",
            "libxcb-render-util.so.0",
        ):
            self.assertIn(library, script)

        for workflow_path in (
            ROOT / ".github" / "workflows" / "test.yml",
            ROOT / ".github" / "workflows" / "release.yml",
        ):
            workflow = workflow_path.read_text(encoding="utf-8")
            for package in (
                "libstdc++6",
                "libgcc-s1",
                "libgbm1",
                "libfontconfig1",
                "libfreetype6",
                "libexpat1",
                "libx11-6",
                "libx11-xcb1",
                "libasound2",
            ):
                self.assertIn(package, workflow)

    def test_release_artifacts_include_legal_notices_and_qt_license_texts(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("licenses/** -text -whitespace", attributes)
        notice = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("| PySide6 | 6.11.2 | LGPL-3.0-only |", notice)
        self.assertIn("pyside-setup.git/tag/?h=v6.11.2", notice)
        self.assertIn("--appimage-extract", notice)
        expected_hashes = {
            "GPL-3.0.txt": (
                "3972dc9744f6499f0f9b2dbf76696f2"
                "ae7ad8af9b23dde66d6af86c9dfb36986"
            ),
            "LGPL-3.0.txt": (
                "e3a994d82e644b03a792a930f5740026"
                "58412f62407f5fee083f2555c5f23118"
            ),
            "LGPL-2.1.txt": (
                "1ccf09bf2f598308df4bed9cd8e9657d"
                "c5cd0973d2800318f2e241486e2edf3f"
            ),
            "Qt-6.11.2-LICENSE.Chromium": (
                "368cca1106be99d39ecd32a38d8305585"
                "d802a475effb66380b91ffc9bcf709b"
            ),
            "QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html": (
                "5955053bf94c385b85ab38c2c8ea016a"
                "ac72f4c5828fc346838f3066ac1f25fb"
            ),
            "GFDL-1.3-no-invariants-only.txt": (
                "110535522396708cea37c72a802c5e7e"
                "81391139f5f7985631c93ef242b206a4"
            ),
            "PERMISSIVE-LICENSES.txt": (
                "5e308284bedb66ce3f41b3bedab3c785"
                "e943244a133c5e2dd24befa3cdff9b36"
            ),
            "NUMPY-2.1.3-LINUX-WHEEL-LICENSE.txt": (
                "c002bd26de7dc7aa464250a0de063d58"
                "fe55974452e4389e5c21c350a820bf06"
            ),
            "NUMPY-2.5.2-LINUX-WHEEL-LICENSES.txt": (
                "eca21ebc64b5bbebf4b23a47e2ff0458"
                "31f97926f6262b5f9b6aa606c77c7e23"
            ),
            "PYTHON-3.12.txt": (
                "32da2c84981c2eed6276b12e8f6427c"
                "229f97ba44bd6445a3752e0238acc9071"
            ),
            "PYTHON-3.13.txt": (
                "93c2662e7c314ed238efd37a7cc6b8c4"
                "349f3257a1ef06858795af71a66692cd"
            ),
            "PYINSTALLER.txt": (
                "84ab6847d0967ab916f0e9580a53b66e"
                "51c9e45afb21a53b0ad2c89f6af26ffd"
            ),
        }
        for filename, expected_hash in expected_hashes.items():
            contents = (ROOT / "licenses" / filename).read_bytes()
            self.assertEqual(hashlib.sha256(contents).hexdigest(), expected_hash)

        permissive = (ROOT / "licenses" / "PERMISSIVE-LICENSES.txt").read_text(
            encoding="utf-8"
        )
        for component in (
            "pywebview 6.2.1",
            "Bottle 0.13.4",
            "proxy_tools 0.1.0",
            "cython-hidapi 0.15.0",
            "QtPy 2.4.3",
            "pythonnet 3.1.0",
            "clr_loader 0.3.1",
            "cffi 2.1.1",
            "pycparser 3.0",
            "PyObjC 12.2.2",
            "Microsoft WebView2 SDK 1.0.3856.49",
            "SoundCard 0.4.6",
            "pysysaudio 0.1.3",
        ):
            self.assertIn(component, permissive)
        self.assertIn(
            "CPython 3.12.10",
            (ROOT / "licenses" / "PYTHON-3.12.txt").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "CPython 3.13.15",
            (ROOT / "licenses" / "PYTHON-3.13.txt").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Bootloader Exception",
            (ROOT / "licenses" / "PYINSTALLER.txt").read_text(encoding="utf-8"),
        )
        numpy_notices = (
            ROOT / "licenses" / "NUMPY-2.5.2-LINUX-WHEEL-LICENSES.txt"
        ).read_text(encoding="utf-8")
        self.assertEqual(numpy_notices.count("Wheel path:"), 17)
        self.assertIn("Name: OpenBLAS", numpy_notices)
        self.assertIn("GCC RUNTIME LIBRARY EXCEPTION", numpy_notices)
        qtwebengine_notices = (
            ROOT / "licenses" / "QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html"
        ).read_text(encoding="utf-8")
        self.assertIn("all 126 unique third-party attribution", qtwebengine_notices)
        self.assertEqual(qtwebengine_notices.count("Primary source:"), 126)
        self.assertIn("GNU LIBRARY GENERAL PUBLIC LICENSE", qtwebengine_notices)
        self.assertIn("Chromium License", qtwebengine_notices)

        windows = (ROOT / "packaging" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        linux = (ROOT / "packaging" / "build_linux.sh").read_text(
            encoding="utf-8"
        )
        macos = (ROOT / "packaging" / "build_macos.sh").read_text(
            encoding="utf-8"
        )
        for filename in (
            "THIRD-PARTY-NOTICES.md",
            "GPL-3.0.txt",
            "LGPL-3.0.txt",
            "LGPL-2.1.txt",
            "Qt-6.11.2-LICENSE.Chromium",
            "QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html",
            "GFDL-1.3-no-invariants-only.txt",
            "PERMISSIVE-LICENSES.txt",
            "NUMPY-2.1.3-LINUX-WHEEL-LICENSE.txt",
            "NUMPY-2.5.2-LINUX-WHEEL-LICENSES.txt",
            "PYTHON-3.12.txt",
            "PYTHON-3.13.txt",
            "PYINSTALLER.txt",
        ):
            self.assertIn(filename, windows)
            self.assertIn(filename, linux)
            self.assertIn(filename, macos)
        self.assertIn("usr/share/doc/spade65", linux)
        self.assertIn("Contents/Resources/Legal", macos)
        self.assertIn("$SmokeDirectory $RelativePath", windows)
        self.assertIn("$mount_dir/THIRD-PARTY-NOTICES.md", macos)

    def test_running_gui_is_activated_only_with_spade65_marker(self):
        class Response:
            def __init__(self, contents: bytes, status: int = 200):
                self.contents = contents
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit: int) -> bytes:
                return self.contents[:limit]

        valid = (
            b'<meta name="spade65-token" '
            b'content="abcdefghijklmnopqrstuvwxyz123456">'
            b'<title>Spade65 Control Center</title>'
        )
        with patch.object(
            launcher.LOCALHOST_OPENER,
            "open",
            side_effect=(Response(valid), Response(b'{"ok": true}')),
        ) as open_local:
            self.assertTrue(launcher.activate_running_gui())
        request = open_local.call_args_list[1].args[0]
        self.assertEqual(request.full_url, f"{launcher.GUI_URL}api/activate")
        self.assertEqual(
            request.get_header("X-spade65-token"),
            "abcdefghijklmnopqrstuvwxyz123456",
        )

        for response in (
            Response(b"<title>another app</title>"),
            Response(valid, status=503),
        ):
            with (
                self.subTest(status=response.status),
                patch.object(
                    launcher.LOCALHOST_OPENER,
                    "open",
                    return_value=response,
                ),
                patch.object(launcher.webbrowser, "open") as open_browser,
            ):
                self.assertFalse(launcher.activate_running_gui())
                self.assertFalse(launcher.reopen_running_gui_in_browser())
                open_browser.assert_not_called()

    def test_launcher_local_requests_never_use_environment_proxies(self):
        self.assertFalse(
            any(
                isinstance(handler, urllib.request.ProxyHandler)
                for handler in launcher.LOCALHOST_OPENER.handlers
            )
        )

    def test_verified_legacy_session_uses_browser_compatibility_fallback(self):
        with (
            patch.object(
                launcher,
                "running_gui_token",
                return_value="abcdefghijklmnopqrstuvwxyz123456",
            ),
            patch.object(launcher.webbrowser, "open", return_value=True) as open_browser,
        ):
            self.assertTrue(launcher.reopen_running_gui_in_browser())
        open_browser.assert_called_once_with(launcher.GUI_URL)

        with (
            patch.object(
                launcher,
                "running_gui_token",
                return_value="abcdefghijklmnopqrstuvwxyz123456",
            ),
            patch.object(launcher.webbrowser, "open", return_value=False),
        ):
            self.assertFalse(launcher.reopen_running_gui_in_browser())

    def test_release_builds_install_and_bundle_the_desktop_runtime(self):
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        spec = (ROOT / "packaging" / "spade65.spec").read_text(encoding="utf-8")
        release = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        test_workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('"pywebview==6.2.1"', project)
        self.assertIn("PySide6==6.11.2", project)
        self.assertIn("SoundCard==0.4.6", project)
        self.assertIn("numpy==2.1.3", project)
        self.assertIn("numpy==2.5.2", project)
        self.assertIn("pysysaudio==0.1.3", project)
        self.assertIn("python_version < '3.13'", project)
        self.assertIn("pythonnet==3.1.0", project)
        self.assertIn(
            '"clr_loader==0.3.1; sys_platform == \'win32\'"', project
        )
        self.assertIn(
            '"cffi==2.1.1; sys_platform == \'linux\' or sys_platform == \'win32\'"',
            project,
        )
        self.assertIn(
            '"pycparser==3.0; sys_platform == \'linux\' or sys_platform == \'win32\'"',
            project,
        )
        self.assertIn("pyobjc-core==12.2.2", project)
        self.assertNotIn("pywebview[qt6]", project)
        self.assertIn('"webview.platforms.qt"', spec)
        self.assertIn('"soundcard.pulseaudio"', spec)
        self.assertIn('"webview.platforms.winforms"', spec)
        self.assertIn('"webview.platforms.cocoa"', spec)
        self.assertIn('"pysysaudio._pysysaudio_native"', spec)
        self.assertIn("AUDIO_DATA_FILES", spec)
        self.assertIn('collect_data_files("soundcard")', spec)
        self.assertNotIn('hiddenimports=["hid"', spec)
        self.assertIn('"qtpy.QtDataVisualization"', spec)
        self.assertIn('"PySide6.QtDataVisualization"', spec)
        self.assertIn('ROOT / "packaging" / "hooks"', spec)
        self.assertIn("LINUX_HOST_RUNTIME_LIBRARIES", spec)
        self.assertIn("analysis.binaries = [", spec)
        for library in (
            "libstdc++.so.6",
            "libgcc_s.so.1",
            "libgbm.so.1",
            "libfontconfig.so.1",
            "libfreetype.so.6",
            "libexpat.so.1",
            "libX11.so.6",
            "libX11-xcb.so.1",
            "libasound.so.2",
            "libpulse.so.0",
        ):
            self.assertIn(library, spec)
        hook_root = ROOT / "packaging" / "hooks"
        qml_hook = (hook_root / "hook-PySide6.QtQml.py").read_text(
            encoding="utf-8"
        )
        gui_hook = (hook_root / "hook-PySide6.QtGui.py").read_text(
            encoding="utf-8"
        )
        positioning_hook = (
            hook_root / "hook-PySide6.QtPositioning.py"
        ).read_text(encoding="utf-8")
        self.assertIn("add_qt6_dependencies", qml_hook)
        self.assertNotIn("collect_qtqml_files", qml_hook)
        self.assertIn("/plugins/qmltooling/", qml_hook)
        self.assertIn("_allowed_plugins", gui_hook)
        self.assertNotIn("virtualkeyboard", gui_hook.casefold())
        self.assertIn("binaries = []", positioning_hook)
        self.assertIn("NSMicrophoneUsageDescription", spec)
        self.assertIn("NSAudioCaptureUsageDescription", spec)
        self.assertIn("NSAllowsLocalNetworking", spec)
        self.assertEqual(release.count(".[cross-platform,desktop]"), 1)
        self.assertGreaterEqual(release.count(".[desktop]"), 2)
        self.assertIn("  windows-package:", test_workflow)
        self.assertIn("  linux-package:", test_workflow)
        self.assertIn("  macos-package:", test_workflow)
        self.assertEqual(release.count('python-version: "3.12.10"'), 1)
        self.assertEqual(test_workflow.count('python-version: "3.12.10"'), 1)

        javascript = (ROOT / "spade65" / "web" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("structuredClone", javascript)
        self.assertNotIn("Object.hasOwn(", javascript)
        launcher = (ROOT / "packaging" / "launcher.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"external-links.js"', launcher)
        self.assertIn('"clipboard.js"', launcher)
        self.assertIn('"live-effects.js"', launcher)

    def test_windows_package_contains_console_cli_and_archive_smoke(self):
        spec = (ROOT / "packaging" / "spade65.spec").read_text(encoding="utf-8")
        script = (ROOT / "packaging" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('name="Spade65CLI"', spec)
        self.assertIn("console=True", spec)
        self.assertIn("Expand-Archive", script)
        self.assertIn("Start-Process -FilePath $ArchivedGui", script)
        self.assertIn("-Wait -PassThru", script)
        self.assertIn("$ArchivedCli --smoke-test", script)
        self.assertIn("Remove-SmokeDirectory", script)
        self.assertIn("Start-Sleep -Milliseconds 500", script)

    def test_official_linux_builds_install_headless_egl_runtime(self):
        required_packages = (
            "libegl1",
            "libgl1",
            "libxcb-shape0",
            "libxcb-image0",
            "libxcb-xkb1",
            "libxcb-icccm4",
            "libxkbcommon-x11-0",
            "libxcb-util1",
            "libxcb-cursor0",
            "libxcb-keysyms1",
            "libxcb-render-util0",
            "libpulse0",
        )
        test_workflow = (
            ROOT / ".github" / "workflows" / "test.yml"
        ).read_text(encoding="utf-8")
        release_workflow = (
            ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        scoped_jobs = (
            (
                "test.yml",
                test_workflow.split("  linux-package:\n", 1)[1].split(
                    "\n  macos-package:\n", 1
                )[0],
                test_workflow.split("  windows-package:\n", 1)[1].split(
                    "\n  linux-package:\n", 1
                )[0],
            ),
            (
                "release.yml",
                release_workflow.split("  linux:\n", 1)[1].split(
                    "\n  macos:\n", 1
                )[0],
                release_workflow.split("  windows:\n", 1)[1].split(
                    "\n  linux:\n", 1
                )[0],
            ),
        )
        for workflow_name, linux_job, windows_job in scoped_jobs:
            workflow = {
                "test.yml": test_workflow,
                "release.yml": release_workflow,
            }[workflow_name]
            self.assertEqual(
                workflow.count("Install Linux desktop runtime prerequisites"), 1
            )
            self.assertNotIn(
                "Install Linux desktop runtime prerequisites", windows_job
            )
            self.assertIn(
                "sudo apt-get install --no-install-recommends --yes", linux_job
            )
            for package in required_packages:
                self.assertIn(package, linux_job)

    def test_native_hid_smoke_only_loads_extension_on_required_platforms(self):
        with patch.object(launcher.importlib, "import_module") as import_module:
            launcher.verify_native_hid_load("linux")
            import_module.assert_not_called()
            launcher.verify_native_hid_load("win32")
            launcher.verify_native_hid_load("darwin")
        self.assertEqual(import_module.call_args_list[0].args, ("hid",))
        self.assertEqual(import_module.call_args_list[1].args, ("hid",))

    def test_native_audio_smoke_loads_dependencies_without_opening_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            package.joinpath("pulseaudio.py.h").write_text(
                "typedef int pa_context;", encoding="utf-8"
            )
            soundcard_spec = SimpleNamespace(
                submodule_search_locations=[directory]
            )
            with (
                patch.object(launcher.importlib, "import_module") as import_module,
                patch.object(
                    launcher.importlib.util,
                    "find_spec",
                    return_value=soundcard_spec,
                ) as find_spec,
            ):
                launcher.verify_native_audio_load("linux")
            self.assertEqual(
                [call.args for call in import_module.call_args_list],
                [("numpy",), ("cffi",)],
            )
            find_spec.assert_called_once_with("soundcard")

        with patch.object(launcher.importlib, "import_module") as import_module:
            launcher.verify_native_audio_load("win32")
            launcher.verify_native_audio_load("darwin")
        self.assertEqual(
            [call.args for call in import_module.call_args_list],
            [
                ("pysysaudio._pysysaudio_native",),
                ("pysysaudio._pysysaudio_native",),
            ],
        )

    def test_macos_release_uses_verified_universal_python_and_hid_build(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        macos_job = workflow.split("  macos:\n", 1)[1].split(
            "\n  publish:\n", 1
        )[0]
        for mode in ("download", "install", "verify", "venv"):
            self.assertIn(
                f"bash packaging/prepare_macos_ci.sh {mode}", macos_job
            )
        self.assertIn("bash packaging/build_macos_hidapi.sh", macos_job)
        self.assertNotIn("actions/setup-python@", macos_job)

        prepare = (ROOT / "packaging" / "prepare_macos_ci.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("python-3.12.10-macos11.pkg", prepare)
        self.assertIn(
            "8373e58da4ea146b3eb1c1f9834f19a319440b6b679b06050b1f9ee3237aa8e4",
            prepare,
        )
        self.assertIn("shasum -a 256 -c -", prepare)
        self.assertGreaterEqual(
            prepare.count("-verify_arch x86_64 arm64"), 3
        )

        test_workflow = (
            ROOT / ".github" / "workflows" / "test.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("  macos-package:", test_workflow)
        self.assertIn("python packaging/build.py", test_workflow)

        hid_build = (ROOT / "packaging" / "build_macos_hidapi.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('--no-binary=:all:', hid_build)
        self.assertIn("--no-build-isolation", hid_build)
        self.assertIn(
            "ecbc265cbe8b7b88755f421e0ba25f084091ec550c2b90ff9e8ddd4fcd540311",
            hid_build,
        )
        self.assertIn("shasum -a 256 -c -", hid_build)
        self.assertIn("macosx_11_0_universal2.whl", hid_build)
        self.assertGreaterEqual(
            hid_build.count("-verify_arch x86_64 arm64"), 2
        )


if __name__ == "__main__":
    unittest.main()
