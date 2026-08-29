import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "packaging" / "linux_legal_inventory.py"
SPEC = importlib.util.spec_from_file_location(
    "spade65_linux_legal_inventory", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
legal = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = legal
SPEC.loader.exec_module(legal)


class FakeInspector:
    def __init__(self, packages):
        self.packages = packages

    def package_for_path(self, source):
        return self.packages.get(source)


class LinuxLegalInventoryTests(unittest.TestCase):
    def test_linux_build_generates_inventory_and_official_jobs_are_strict(self):
        build_script = (ROOT / "packaging" / "build_linux.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("packaging/linux_legal_inventory.py", build_script)
        self.assertIn("SPADE65_STRICT_LINUX_LEGAL", build_script)
        self.assertIn("--strict-dpkg", build_script)
        self.assertIn(legal.MANIFEST_NAME, build_script)

        for workflow_name in ("release.yml", "test.yml"):
            workflow = (
                ROOT / ".github" / "workflows" / workflow_name
            ).read_text(encoding="utf-8")
            self.assertIn('SPADE65_STRICT_LINUX_LEGAL: "1"', workflow)

    def test_pinned_appimage_licenses_are_verbatim(self):
        expected = {
            "AppImage-type2-runtime-75849dc-LICENSE": (
                "aa154fc9070614bbe7921f89db11efd1"
                "dba7a1f3a41685958110e2230f9c0ca1"
            ),
            "AppImage-appimagetool-1.9.1-LICENSE": (
                "d726eb47bb96b7e7f8971a1431575ab4"
                "fd8780b5d2efde3552c70ef71469015f"
            ),
        }
        for filename, digest in expected.items():
            contents = (ROOT / "licenses" / filename).read_bytes()
            self.assertEqual(hashlib.sha256(contents).hexdigest(), digest)

        script = (ROOT / "packaging" / "build_linux.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("commit 75849dc", script)
        for filename in expected:
            self.assertIn(filename, script)

    def test_loads_pyinstaller_collect_tuple(self):
        with tempfile.TemporaryDirectory() as directory:
            toc = Path(directory) / "COLLECT-00.toc"
            toc.write_text(
                "([('libalpha.so', '/usr/lib/libalpha.so', 'BINARY'), "
                "('alias.so', 'libalpha.so', 'SYMLINK')],)\n",
                encoding="utf-8",
            )
            records = legal.load_collect_records(toc)

        self.assertEqual(
            records,
            [
                legal.CollectRecord(
                    "libalpha.so", "/usr/lib/libalpha.so", "BINARY"
                ),
                legal.CollectRecord("alias.so", "libalpha.so", "SYMLINK"),
            ],
        )

    def test_strict_inventory_copies_dpkg_copyright_and_maps_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system_root = root / "system"
            library = system_root / "lib" / "libalpha.so.1"
            library.parent.mkdir(parents=True)
            library.write_bytes(b"ELF")
            copyright_file = root / "docs" / "libalpha1" / "copyright"
            copyright_file.parent.mkdir(parents=True)
            copyright_file.write_text("Alpha license\n", encoding="utf-8")
            info = legal.PackageInfo(
                "libalpha1:amd64", "1.2.3-1", copyright_file
            )
            output = root / "legal"

            manifest = legal.generate_inventory(
                [legal.CollectRecord("libalpha.so.1", str(library), "BINARY")],
                output,
                project_root=root / "project",
                python_prefix=root / "python",
                strict_dpkg=True,
                inspector=FakeInspector({library: info}),
                system_roots=(system_root,),
            )

            copied = output / "dpkg-copyright" / "libalpha1_amd64.copyright"
            self.assertEqual(copied.read_text(encoding="utf-8"), "Alpha license\n")
            self.assertTrue(manifest["complete_system_mapping"])
            self.assertEqual(manifest["mapped_system_native_binary_count"], 1)
            self.assertEqual(
                manifest["records"][0]["dpkg_package"], "libalpha1:amd64"
            )
            serialized = json.loads(
                (output / legal.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(serialized["packages"][0]["version"], "1.2.3-1")

    def test_strict_inventory_fails_for_unmapped_system_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system_root = root / "system"
            library = system_root / "libmissing.so"
            library.parent.mkdir()
            library.write_bytes(b"ELF")
            output = root / "legal"

            with self.assertRaisesRegex(
                legal.InventoryError, "no owning dpkg package"
            ):
                legal.generate_inventory(
                    [
                        legal.CollectRecord(
                            "libmissing.so", str(library), "BINARY"
                        )
                    ],
                    output,
                    project_root=root / "project",
                    python_prefix=root / "python",
                    strict_dpkg=True,
                    inspector=FakeInspector({}),
                    system_roots=(system_root,),
                )

            manifest = json.loads(
                (output / legal.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertFalse(manifest["complete_system_mapping"])
            self.assertEqual(manifest["issues"][0]["reason"], "no owning dpkg package")

    def test_non_dpkg_build_writes_labeled_source_path_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system_root = root / "system"
            library = system_root / "libmanual.so"
            library.parent.mkdir()
            library.write_bytes(b"ELF")
            output = root / "legal"

            manifest = legal.generate_inventory(
                [legal.CollectRecord("libmanual.so", str(library), "BINARY")],
                output,
                project_root=root / "project",
                python_prefix=root / "python",
                strict_dpkg=False,
                inspector=None,
                system_roots=(system_root,),
            )

            self.assertEqual(manifest["mode"], "source-path-only")
            self.assertIn(
                "package ownership and system-library license completeness "
                "have not been verified",
                manifest["notice"],
            )
            self.assertEqual(manifest["records"][0]["source_path"], str(library))
            readme = (output / legal.README_NAME).read_text(encoding="utf-8")
            self.assertIn("Mode: source-path-only", readme)

    def test_dpkg_inspector_reads_package_version_and_direct_copyright(self):
        with tempfile.TemporaryDirectory() as directory:
            doc_root = Path(directory)
            copyright_file = doc_root / "libalpha1" / "copyright"
            copyright_file.parent.mkdir()
            copyright_file.write_text("license", encoding="utf-8")

            def run(command):
                if command[1] == "-S":
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        "libalpha1:amd64: /usr/lib/libalpha.so.1\n",
                        "",
                    )
                if command[1] == "-W":
                    return subprocess.CompletedProcess(
                        command, 0, "libalpha1:amd64\t1.2.3-1\n", ""
                    )
                self.fail(f"unexpected command: {command}")

            inspector = legal.DpkgInspector(
                "dpkg-query", runner=run, doc_root=doc_root
            )
            info = inspector.package_for_path(Path("/usr/lib/libalpha.so.1"))

        self.assertEqual(
            info,
            legal.PackageInfo("libalpha1:amd64", "1.2.3-1", copyright_file),
        )

    def test_cli_rejects_strict_mode_without_dpkg_query(self):
        with patch.object(legal.shutil, "which", return_value=None):
            self.assertEqual(
                legal.main(
                    [
                        "--toc",
                        "missing.toc",
                        "--output-dir",
                        "unused",
                        "--strict-dpkg",
                    ]
                ),
                1,
            )


if __name__ == "__main__":
    unittest.main()
