from __future__ import annotations

import unittest

from app.services.html_sanitizer import consume_complete_slides, parse_slides


class HtmlSanitizerTests(unittest.TestCase):
    def test_consume_complete_slides_handles_hyphenated_templates(self):
        buffer = """
<!-- SLIDE id="1" template="project-card" -->
<section class="slide sh-slide" data-template="project-card"></section>
<!-- SLIDE id="2" template="bar_chart" -->
<section class="slide sh-slide" data-template="bar_chart"></section>
""".strip()

        slides, remainder = consume_complete_slides(buffer)

        self.assertEqual(remainder, "")
        self.assertEqual(
            slides,
            [
                {
                    "id": 1,
                    "template": "project-card",
                    "html": '<section class="slide sh-slide" data-template="project-card"></section>',
                },
                {
                    "id": 2,
                    "template": "bar_chart",
                    "html": '<section class="slide sh-slide" data-template="bar_chart"></section>',
                },
            ],
        )

    def test_consume_complete_slides_keeps_incomplete_tail(self):
        buffer = """
<!-- SLIDE id="1" template="cover" -->
<section class="slide sh-slide" data-template="cover"></section>
<!-- SLIDE id="2" template="quote" -->
<section class="slide sh-slide" data-template="quote">
""".strip()

        slides, remainder = consume_complete_slides(buffer)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]["template"], "cover")
        self.assertIn('template="quote"', remainder)
        self.assertIn('data-template="quote"', remainder)

    def test_parse_slides_falls_back_to_single_section_without_marker(self):
        raw = """
```html
<section class="slide sh-slide" data-template="two-column" data-sh-template="two-column"></section>
```
""".strip()

        slides = parse_slides(raw)

        self.assertEqual(
            slides,
            [
                {
                    "id": 1,
                    "template": "two-column",
                    "html": '<section class="slide sh-slide" data-template="two-column" data-sh-template="two-column"></section>',
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
