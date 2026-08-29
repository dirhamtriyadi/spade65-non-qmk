from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDONESIAN_DOCS = DOCS / "id"
README = ROOT / "README.md"
INDONESIAN_README = ROOT / "README.id.md"
PACKAGING_README = ROOT / "packaging" / "README.md"
INDONESIAN_PACKAGING_README = ROOT / "packaging" / "README.id.md"
MARKDOWN_LINK = re.compile(
    r"(?<!!)\[[^\]]+\]\(\s*(?:<(?P<angle>[^>]+)>|(?P<plain>[^)\s]+))"
)
PREVIEW_IMAGES = (
    "docs/images/spade65-overview.png",
    "docs/images/spade65-keyboard.png",
    "docs/images/spade65-lighting.png",
    "docs/images/spade65-macros.png",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def canonical_documents() -> list[Path]:
    return [README, *sorted(DOCS.glob("*.md")), PACKAGING_README]


def counterpart_for(canonical: Path) -> Path:
    if canonical == README:
        return INDONESIAN_README
    if canonical == PACKAGING_README:
        return INDONESIAN_PACKAGING_README
    return INDONESIAN_DOCS / canonical.name


def local_link_targets(document: Path) -> set[Path]:
    targets: set[Path] = set()
    contents = document.read_text(encoding="utf-8")
    for match in MARKDOWN_LINK.finditer(contents):
        raw_target = match.group("angle") or match.group("plain")
        parsed = urlsplit(raw_target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        link_path = PurePosixPath(unquote(parsed.path))
        if link_path.is_absolute():
            continue
        targets.add((document.parent / Path(*link_path.parts)).resolve())
    return targets


def is_localized_document(path: Path) -> bool:
    return (
        path == INDONESIAN_README.resolve()
        or path == INDONESIAN_PACKAGING_README.resolve()
        or path.is_relative_to(INDONESIAN_DOCS.resolve())
    )


class DocumentationTests(unittest.TestCase):
    def test_all_local_markdown_links_resolve(self) -> None:
        documents = sorted(
            {
                *ROOT.glob("*.md"),
                *DOCS.rglob("*.md"),
                *(ROOT / "packaging").glob("*.md"),
            }
        )
        self.assertTrue(documents)
        for document in documents:
            for target in local_link_targets(document):
                with self.subTest(
                    document=document.relative_to(ROOT),
                    target=target,
                ):
                    self.assertTrue(target.exists())

    def test_every_default_document_has_a_reciprocal_indonesian_version(
        self,
    ) -> None:
        canonical_guides = sorted(DOCS.glob("*.md"))
        self.assertTrue(canonical_guides)
        self.assertEqual(
            {guide.name for guide in canonical_guides},
            {guide.name for guide in INDONESIAN_DOCS.glob("*.md")},
        )

        for canonical in canonical_documents():
            counterpart = counterpart_for(canonical)
            with self.subTest(document=canonical.relative_to(ROOT)):
                self.assertTrue(counterpart.is_file())
                self.assertIn(
                    counterpart.resolve(), local_link_targets(canonical)
                )
                self.assertIn(
                    canonical.resolve(), local_link_targets(counterpart)
                )

    def test_default_documents_only_link_to_their_own_language_switch(
        self,
    ) -> None:
        for canonical in canonical_documents():
            expected_switch = counterpart_for(canonical).resolve()
            localized_targets = {
                target
                for target in local_link_targets(canonical)
                if is_localized_document(target)
            }
            with self.subTest(document=canonical.relative_to(ROOT)):
                self.assertEqual(localized_targets, {expected_switch})

    def test_readme_preview_images_are_well_formed_pngs(self) -> None:
        readme = README.read_text(encoding="utf-8")
        for relative_path in PREVIEW_IMAGES:
            image_path = ROOT / relative_path
            with self.subTest(image=relative_path):
                self.assertIn(f'href="{relative_path}"', readme)
                self.assertIn(f'src="{relative_path}"', readme)
                self.assertTrue(image_path.is_file())
                header = image_path.read_bytes()[:33]
                self.assertGreaterEqual(len(header), 33)
                self.assertEqual(header[:8], PNG_SIGNATURE)
                self.assertEqual(struct.unpack(">I", header[8:12])[0], 13)
                self.assertEqual(header[12:16], b"IHDR")
                width, height = struct.unpack(">II", header[16:24])
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)


if __name__ == "__main__":
    unittest.main()
