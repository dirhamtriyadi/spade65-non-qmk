import importlib.util
import tempfile
import unittest
from pathlib import Path
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
        self.assertIn("group: release-${{", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

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
        self.assertIn('--runtime-file "$runtime_file"', script)

    def test_running_gui_is_reopened_only_with_spade65_marker(self):
        class Response:
            status = 200

            def __init__(self, contents: bytes):
                self.contents = contents

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
        with (
            patch.object(launcher.urllib.request, "urlopen", return_value=Response(valid)),
            patch.object(launcher.webbrowser, "open") as open_browser,
        ):
            self.assertTrue(launcher.reopen_running_gui())
            open_browser.assert_called_once_with(launcher.GUI_URL)
        with (
            patch.object(
                launcher.urllib.request,
                "urlopen",
                return_value=Response(b"<title>another app</title>"),
            ),
            patch.object(launcher.webbrowser, "open") as open_browser,
        ):
            self.assertFalse(launcher.reopen_running_gui())
            open_browser.assert_not_called()

    def test_windows_package_contains_console_cli_and_archive_smoke(self):
        spec = (ROOT / "packaging" / "spade65.spec").read_text(encoding="utf-8")
        script = (ROOT / "packaging" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('name="Spade65CLI"', spec)
        self.assertIn("console=True", spec)
        self.assertIn("Expand-Archive", script)
        self.assertIn("$ArchivedCli --smoke-test", script)

    def test_native_hid_smoke_only_loads_extension_on_required_platforms(self):
        with patch.object(launcher.importlib, "import_module") as import_module:
            launcher.verify_native_hid_load("linux")
            import_module.assert_not_called()
            launcher.verify_native_hid_load("win32")
            launcher.verify_native_hid_load("darwin")
        self.assertEqual(import_module.call_args_list[0].args, ("hid",))
        self.assertEqual(import_module.call_args_list[1].args, ("hid",))

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
        self.assertIn("python-3.13.15-macos11.pkg", prepare)
        self.assertIn(
            "3b7eaf7f29825f796e8267024435540ddf1f17fc9a97ad58095daa7a75bfdcd3",
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
