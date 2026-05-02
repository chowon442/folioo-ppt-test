# SlideHTML DSL v1 Validation and Export Gap Audit

This document records the validator/exportability contract used for the DSL migration.

## Current State

- Legacy templates in `slide_templates/` are still accepted through the compatibility wrapper in `app/services/validator.py`.
- DSL fixtures and future migrated templates should be validated through `app/services/slidehtml_validator.py`.
- Placeholder `.pptx` templates are out of scope for this phase.

## DSL Validation Rules

The DSL validator checks three layers:

1. Manifest shape
   - `dsl` must be `slidehtml/v1`
   - `templateId` and `slide.width/height/grid` must exist
   - `allowedKinds`, `defaultExport`, `roles`, and `placeholders` must be internally consistent

2. Deck / slide structure
   - Root must be `article.sh-deck` with `data-sh-dsl="slidehtml/v1"`
   - Each slide must be a `section.sh-slide`
   - Each slide must carry `data-sh-id`, `data-sh-template`, and `data-sh-size`
   - Duplicate `data-sh-id` values are rejected

3. Exportability
   - `text` nodes require `data-sh-fit` and `data-sh-max-lines`
   - `shape` nodes require `data-sh-shape`
   - `chart` nodes require `data-sh-chart-kind` and exactly one `script[type="application/json"]`
   - `table` nodes must be real `<table>` elements and cell content must stay text-only
   - `line` nodes require anchors
   - `flatten` nodes are allowed only as decorative or non-editable content

## Fixture Matrix

The repo now includes fixture-oriented tests under `tests/slidehtml/`:

- `deck.valid.html`
- `slide.invalid.missing_fit.html`
- `slide.invalid.chart_json.html`
- `slide.invalid.table_cell.html`
- `slide.invalid.duplicate_id.html`

Those fixtures cover the most important failure modes:

- missing text fit policy
- malformed chart payload
- illegal table cell content
- duplicate node ids

## Additional Automated Coverage

The migration now has two broader regression checks in addition to the fixture tests:

- `test_html_sanitizer.py`
  - verifies streaming delimiter parsing
  - verifies fallback parsing of a single `.sh-slide` fragment without slide markers
  - verifies hyphenated template ids are preserved

- `test_template_matrix.py`
  - validates all 40 theme/template triplets with the DSL validator
  - enforces canonical manifest keys (`templateId`, `slide`)
  - rejects legacy manifest keys (`template_id`, `slide_size`, `slots`)

## Export Gap Notes

- `text-group`, `svg-shapes`, and `table_wrap` are legacy-only concepts and should not appear in SlideHTML DSL fixtures.
- `metrics_table` should export as a native PPT table.
- `bar_chart` should export as a native PPT chart, not an SVG parse tree.
- Decorative CSS effects such as blur, shadow, blend modes, and complex gradients should be flattened before export.

## Acceptance Criteria

- DSL fixtures pass validation with no errors.
- Invalid fixtures fail with stable issue codes.
- The full 4 themes x 10 slide kinds matrix validates as SlideHTML DSL v1.
- Canonical manifests use `templateId` and `slide` instead of legacy aliases.
- Legacy templates still validate through the compatibility wrapper until the rest of the pipeline is migrated.
