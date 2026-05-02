from __future__ import annotations

import json
import unittest
from pathlib import Path


THEMES_ROOT = Path("slide_templates/themes")


class TemplateMatrixTests(unittest.TestCase):
    def test_all_theme_template_triplets_have_strong_manifest_contract(self):
        manifests = sorted(THEMES_ROOT.rglob("manifest.json"))
        self.assertEqual(len(manifests), 40, "expected 40 theme/template manifests")

        for manifest_path in manifests:
            template_dir = manifest_path.parent
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("templateId", manifest, str(manifest_path))
            self.assertIn("slide", manifest, str(manifest_path))
            self.assertNotIn("template_id", manifest, str(manifest_path))
            self.assertNotIn("slide_size", manifest, str(manifest_path))
            self.assertNotIn("slots", manifest, str(manifest_path))
            self.assertTrue((template_dir / "slide.html").is_file(), str(manifest_path))

            theme_id = manifest_path.parent.parent.name
            placeholders = manifest.get("placeholders") or {}
            placeholder_map = manifest.get("placeholderMap") or {}

            self.assertEqual(
                manifest.get("pptxTemplate"),
                f"pptx/{theme_id}.pptx",
                str(manifest_path),
            )
            self.assertTrue(placeholders, str(manifest_path))
            self.assertTrue(placeholder_map, str(manifest_path))
            self.assertTrue(
                set(placeholder_map.values()).issubset(placeholders.keys()),
                str(manifest_path),
            )


if __name__ == "__main__":
    unittest.main()
