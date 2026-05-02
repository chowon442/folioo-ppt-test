from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.models.slidehtml import TemplateManifest
from app.services.slidehtml_normalizer import normalize_slide_html
from app.services.slidehtml_validator import (
    SlideHTMLValidator,
    validate_html,
)
from app.services.validator import validate_export_slide_html, validate_slide_html


FIXTURES = Path(__file__).with_name("fixtures")


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def read_json_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class SlideHTMLValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read_json_fixture("manifest.valid.json")

    def test_manifest_fixture_is_valid(self):
        report = SlideHTMLValidator(self.manifest).validate_manifest()
        self.assertTrue(report.valid)
        self.assertEqual(report.errors, [])

    def test_valid_deck_fixture_passes(self):
        report = SlideHTMLValidator(self.manifest).validate_html(
            read_fixture("deck.valid.html")
        )
        self.assertTrue(report.valid)
        self.assertEqual(report.errors, [])

    def test_wrapper_routes_dsl_html(self):
        result = validate_slide_html(read_fixture("deck.valid.html"), self.manifest)
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_invalid_fixtures_report_expected_codes(self):
        cases = [
            ("slide.invalid.missing_fit.html", "text.fit.missing"),
            ("slide.invalid.chart_json.html", "chart.json.invalid"),
            ("slide.invalid.table_cell.html", "table.cell.tag.invalid"),
            ("slide.invalid.duplicate_id.html", "id.duplicate"),
        ]
        for filename, code in cases:
            with self.subTest(filename=filename):
                report = validate_html(read_fixture(filename), self.manifest)
                self.assertFalse(report.valid)
                self.assertTrue(
                    any(error.code == code for error in report.errors),
                    msg=f"expected {code} in {report.errors}",
                )

    def test_wrapper_still_accepts_current_dsl_templates(self):
        cover_manifest = read_json_fixture("manifest.cover.valid.json")
        cover_html = (
            Path("slide_templates/themes/default/cover/slide.html")
            .read_text(encoding="utf-8")
        )
        result = validate_slide_html(cover_html, cover_manifest)
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_normalized_export_html_passes_strict_validation(self):
        bar_manifest = TemplateManifest.model_validate(
            json.loads(
                Path("slide_templates/themes/default/bar_chart/manifest.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        raw_html = Path("slide_templates/themes/default/bar_chart/slide.html").read_text(
            encoding="utf-8"
        )
        normalized_html = normalize_slide_html(raw_html, bar_manifest, 1)

        self.assertIn('data-sh-export-mode="strict"', normalized_html)
        self.assertNotIn("bc-axis", normalized_html)
        self.assertNotIn("bc-bars", normalized_html)

        result = validate_slide_html(normalized_html, bar_manifest)
        self.assertTrue(result.valid, msg=str(result.errors))
        self.assertEqual(result.errors, [])

    def test_strict_export_requires_ids_exports_and_safe_fit_modes(self):
        cover_manifest = TemplateManifest.model_validate(
            read_json_fixture("manifest.cover.valid.json")
        )
        strict_html = """
        <section class="slide sh-slide"
                 data-template="cover"
                 data-sh-dsl="slidehtml/v1"
                 data-sh-id="slide-01"
                 data-sh-template="cover"
                 data-sh-size="1280x720"
                 data-sh-export-mode="strict">
          <div data-sh-kind="text"
               data-sh-role="title"
               data-sh-fit="split"
               data-sh-max-lines="2">
            <p>Broken title</p>
          </div>
        </section>
        """.strip()

        report = SlideHTMLValidator(cover_manifest).validate_html(strict_html)
        error_codes = {issue.code for issue in report.errors}

        self.assertFalse(report.valid)
        self.assertIn("id.missing.strict", error_codes)
        self.assertIn("export.missing.strict", error_codes)
        self.assertIn("text.fit.invalid.strict", error_codes)

    def test_strict_export_rejects_chart_preview_scaffold(self):
        bar_manifest = TemplateManifest.model_validate(
            json.loads(
                Path("slide_templates/themes/default/bar_chart/manifest.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        strict_chart_html = """
        <section class="slide sh-slide"
                 data-template="bar_chart"
                 data-sh-dsl="slidehtml/v1"
                 data-sh-id="slide-01"
                 data-sh-template="bar_chart"
                 data-sh-size="1280x720"
                 data-sh-export-mode="strict">
          <div data-sh-kind="chart"
               data-sh-id="chart-01"
               data-sh-role="chart"
               data-sh-export="native"
               data-sh-fallback="native>svg>png"
               data-sh-chart-kind="bar"
               data-sh-chart-template="bar-01">
            <script type="application/json">
              {"categories":["A"],"series":[{"name":"S","values":[1]}]}
            </script>
            <div class="preview-dom">preview scaffold</div>
          </div>
        </section>
        """.strip()

        report = SlideHTMLValidator(bar_manifest).validate_html(strict_chart_html)

        self.assertFalse(report.valid)
        self.assertTrue(
            any(issue.code == "chart.preview.dom" for issue in report.errors),
            msg=f"expected chart.preview.dom in {report.errors}",
        )

    def test_export_wrapper_routes_strict_html(self):
        bar_manifest = TemplateManifest.model_validate(
            json.loads(
                Path("slide_templates/themes/default/bar_chart/manifest.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        raw_html = Path("slide_templates/themes/default/bar_chart/slide.html").read_text(
            encoding="utf-8"
        )
        normalized_html = normalize_slide_html(raw_html, bar_manifest, 1)

        result = validate_export_slide_html(normalized_html, bar_manifest)

        self.assertTrue(result.valid, msg=str(result.errors))
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
