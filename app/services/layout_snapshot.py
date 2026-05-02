from __future__ import annotations

import json
import re

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


_REMOTE_IMPORT_RE = re.compile(r"@import\s+url\((?:'|\")?https?://[^)]+?\)\s*;?", re.IGNORECASE)


PLAYWRIGHT_CAPTURE_LAYOUT_JS = r"""
() => {
  function parseNumber(input, fallback = 0) {
    const value = parseFloat(input || "");
    return Number.isFinite(value) ? value : fallback;
  }

  function parseJsonScript(node) {
    const script = node.querySelector("script[type='application/json']");
    if (!script || !script.textContent) return null;
    try {
      return JSON.parse(script.textContent);
    } catch (err) {
      return null;
    }
  }

  function parseTableRows(table) {
    const rows = [];
    const rowNodes = table.querySelectorAll(":scope > thead > tr, :scope > tbody > tr, :scope > tr");
    rowNodes.forEach(row => {
      const cells = [];
      row.querySelectorAll(":scope > th, :scope > td").forEach(cell => {
        const cs = getComputedStyle(cell);
        cells.push({
          text: (cell.innerText || "").trim(),
          header: cell.tagName.toLowerCase() === "th",
          align: cs.textAlign || "left",
          fillColor: rgbaToHex(cs.backgroundColor),
          color: rgbaToHex(cs.color),
          fontFamily: cs.fontFamily || null,
          fontSizePx: parseNumber(cs.fontSize, 0),
          fontWeight: cs.fontWeight || "400",
          padding: {
            left: parseNumber(cs.paddingLeft, 0),
            top: parseNumber(cs.paddingTop, 0),
            right: parseNumber(cs.paddingRight, 0),
            bottom: parseNumber(cs.paddingBottom, 0)
          }
        });
      });
      if (cells.length) rows.push(cells);
    });
    return rows.length ? rows : null;
  }

  function rgbaToHex(input) {
    if (!input) return null;
    const m = input.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(",").map(x => x.trim());
    const r = Number(parts[0] || 0);
    const g = Number(parts[1] || 0);
    const b = Number(parts[2] || 0);
    const a = parts.length > 3 ? Math.round(Number(parts[3]) * 255) : null;
    const hex = [r, g, b].map(v => v.toString(16).padStart(2, "0")).join("");
    return a === null ? `#${hex}` : `#${hex}${a.toString(16).padStart(2, "0")}`;
  }

  function parseSlideBg(slide) {
    const bg = getComputedStyle(slide);
    const bgColor = rgbaToHex(bg.backgroundColor);
    const bgImage = bg.backgroundImage || "";
    let gradient = null;
    if (bgImage && bgImage !== "none" && bgImage.includes("linear-gradient")) {
      const angleMatch = bgImage.match(/linear-gradient\s*\(\s*([\d.]+)deg/i);
      const angle = angleMatch ? parseFloat(angleMatch[1]) : 0;
      const colors = [];
      const re = /(rgba?\([^)]+\)|#[0-9a-fA-F]{3,8})/g;
      let m;
      while ((m = re.exec(bgImage)) !== null) {
        colors.push(rgbaToHex(m[1]) || m[1]);
      }
      if (colors.length >= 2) {
        gradient = { angle: angle, colors: [colors[0], colors[colors.length - 1]] };
      }
    }
    return { bgColor, gradient };
  }

  function parseObjectPosition(input) {
    const text = (input || "").trim();
    if (!text) return null;
    const parts = text.split(/\s+/).filter(Boolean);
    if (!parts.length) return null;

    function normalize(value) {
      const lower = value.toLowerCase();
      if (lower.endsWith("%")) return parseNumber(lower, 50);
      if (lower === "left" || lower === "top") return 0;
      if (lower === "center") return 50;
      if (lower === "right" || lower === "bottom") return 100;
      return parseNumber(lower, 50);
    }

    return {
      x: normalize(parts[0]),
      y: normalize(parts[1] || parts[0]),
    };
  }

  function parseFocalPoint(node, cs) {
    const explicit = node.getAttribute("data-sh-focal");
    if (explicit) {
      const [xRaw, yRaw] = explicit.split(",").map(part => parseNumber(part, 0.5));
      return { x: xRaw, y: yRaw };
    }
    const parsed = parseObjectPosition(cs.objectPosition || "");
    if (!parsed) return null;
    return { x: parsed.x / 100, y: parsed.y / 100 };
  }

  function paragraphSpacing(node) {
    const paragraphs = [...node.querySelectorAll(":scope > p")];
    if (!paragraphs.length) return 0;
    let spacing = 0;
    paragraphs.forEach(p => {
      const pcs = getComputedStyle(p);
      spacing = Math.max(
        spacing,
        parseNumber(pcs.marginTop, 0),
        parseNumber(pcs.marginBottom, 0)
      );
    });
    return spacing;
  }

  function hasPseudoContent(node, pseudo) {
    try {
      const pseudoStyle = getComputedStyle(node, pseudo);
      const content = (pseudoStyle.content || "").trim();
      return Boolean(
        content &&
        content !== "none" &&
        content !== "normal" &&
        content !== "\"\"" &&
        content !== "''"
      );
    } catch (_) {
      return false;
    }
  }

  function detectUnsafeVisuals(node, cs) {
    const flags = [];
    const backgroundImage = (cs.backgroundImage || "").trim();
    const boxShadow = (cs.boxShadow || "").trim();
    const filter = (cs.filter || "").trim();
    const backdropFilter = (cs.backdropFilter || "").trim();
    const mixBlendMode = (cs.mixBlendMode || "").trim();

    if (backgroundImage && backgroundImage !== "none") flags.push("background-image");
    if (boxShadow && boxShadow !== "none") flags.push("box-shadow");
    if (filter && filter !== "none") flags.push("filter");
    if (backdropFilter && backdropFilter !== "none") flags.push("backdrop-filter");
    if (mixBlendMode && mixBlendMode !== "normal") flags.push("mix-blend-mode");
    if (hasPseudoContent(node, "::before")) flags.push("pseudo-before");
    if (hasPseudoContent(node, "::after")) flags.push("pseudo-after");

    return flags;
  }

  function buildFillAndStroke(cs) {
    const fillColor = rgbaToHex(cs.backgroundColor);
    const borderWidth = parseNumber(cs.borderLeftWidth, 0);
    const borderStyle = cs.borderLeftStyle || "none";
    const borderColor = rgbaToHex(cs.borderLeftColor);
    return {
      fill: {
        color: fillColor,
        opacity: parseNumber(cs.opacity, 1),
      },
      stroke: {
        width: borderWidth,
        style: borderStyle,
        color: borderColor,
      }
    };
  }

  const slides = [...document.querySelectorAll(".sh-slide")];

  return {
    dsl: "slidehtml/v1",
    slides: slides.map(slide => {
      const slideRect = slide.getBoundingClientRect();
      const bg = parseSlideBg(slide);
      const nodes = [...slide.querySelectorAll("[data-sh-id][data-sh-kind]")].map((node, nodeIndex) => {
        const rect = node.getBoundingClientRect();
        const cs = getComputedStyle(node);
        const explicitZRaw = node.getAttribute("data-sh-z");
        const computedZRaw = cs.zIndex;
        let z = nodeIndex;
        if (explicitZRaw !== null && explicitZRaw !== "") {
          z = Number(explicitZRaw);
        } else if (computedZRaw && computedZRaw !== "auto" && !Number.isNaN(Number(computedZRaw))) {
          z = Number(computedZRaw) * 1000 + nodeIndex;
        }

        const fillStroke = buildFillAndStroke(cs);
        const kind = node.getAttribute("data-sh-kind");
        const unsafeVisuals = detectUnsafeVisuals(node, cs);
        let exportMode = node.getAttribute("data-sh-export") || "auto";
        let fallback = node.getAttribute("data-sh-fallback") || null;
        if (
          unsafeVisuals.length &&
          !["flatten", "svg"].includes(kind || "") &&
          !["png", "svg"].includes(String(exportMode).toLowerCase())
        ) {
          exportMode = "png";
          fallback = "png";
        }

        return {
          id: node.getAttribute("data-sh-id"),
          kind: kind,
          role: node.getAttribute("data-sh-role"),
          export: exportMode,
          fallback: fallback,
          placeholder: node.getAttribute("data-sh-placeholder") || null,
          computedUnsafeVisuals: unsafeVisuals,
          z: z,
          rotation: Number(node.getAttribute("data-sh-rotate") || 0),
          box: {
            left: rect.left - slideRect.left,
            top: rect.top - slideRect.top,
            width: rect.width,
            height: rect.height
          },
          padding: {
            left: parseNumber(cs.paddingLeft, 0),
            top: parseNumber(cs.paddingTop, 0),
            right: parseNumber(cs.paddingRight, 0),
            bottom: parseNumber(cs.paddingBottom, 0)
          },
          fill: fillStroke.fill,
          stroke: fillStroke.stroke,
          backgroundColor: rgbaToHex(cs.backgroundColor),
          opacity: parseNumber(cs.opacity, 1),
          border: {
            width: parseNumber(cs.borderLeftWidth, 0),
            style: cs.borderLeftStyle || "none",
            color: rgbaToHex(cs.borderLeftColor)
          },
          borderRadiusPx: parseNumber(cs.borderTopLeftRadius, 0),
          textStyle: ["text", "table"].includes(node.getAttribute("data-sh-kind")) ? {
            fontFamily: cs.fontFamily,
            fontSizePx: parseNumber(cs.fontSize, 0),
            fontWeight: cs.fontWeight,
            fontStyle: cs.fontStyle,
            lineHeightPx: parseNumber(cs.lineHeight || cs.fontSize, 0),
            letterSpacingPx: parseNumber(cs.letterSpacing, 0),
            paragraphSpacingPx: paragraphSpacing(node),
            textAlign: cs.textAlign,
            valign: node.getAttribute("data-sh-valign") || "top",
            color: rgbaToHex(cs.color)
          } : null,
          paragraphSpacingPx: paragraphSpacing(node),
          lineHeightPx: parseNumber(cs.lineHeight || cs.fontSize, 0),
          letterSpacingPx: parseNumber(cs.letterSpacing, 0),
          verticalAlign: node.getAttribute("data-sh-valign") || "top",
          fit: node.getAttribute("data-sh-fit") || null,
          maxLines: node.getAttribute("data-sh-max-lines") || null,
          minFont: node.getAttribute("data-sh-min-font") || null,
          maxFont: node.getAttribute("data-sh-max-font") || null,
          html: node.outerHTML || "",
          text: (node.innerText || "").trim(),
          tag: node.tagName.toLowerCase(),
          src: node.getAttribute("src") || node.getAttribute("data-sh-src") || node.getAttribute("data-sh-rendered-src") || null,
          renderedSrc: null,
          renderedMimeType: null,
          cropMode: node.getAttribute("data-sh-fit") || cs.objectFit || null,
          focalPoint: parseFocalPoint(node, cs),
          chartTemplate: node.getAttribute("data-sh-chart-template") || null,
          chartKind: node.getAttribute("data-sh-chart-kind") || null,
          chartData: parseJsonScript(node),
          shapeType: node.getAttribute("data-sh-shape") || null,
          lineType: node.getAttribute("data-sh-line-kind") || null,
          lineFrom: node.getAttribute("data-sh-from") || null,
          lineTo: node.getAttribute("data-sh-to") || null,
          arrowStart: node.getAttribute("data-sh-arrow-start") || null,
          arrowEnd: node.getAttribute("data-sh-arrow-end") || null,
          from: node.getAttribute("data-sh-from") || null,
          to: node.getAttribute("data-sh-to") || null,
          tableRows: node.tagName.toLowerCase() === "table" ? parseTableRows(node) : null
        };
      });

      return {
        id: slide.getAttribute("data-sh-id"),
        template: slide.getAttribute("data-sh-template"),
        bgColor: bg.bgColor,
        bgGradient: bg.gradient,
        nodes
      };
    })
  };
}
"""


def _build_deck_html(slides_html: list[str], theme_id: str) -> str:
    from app.services.template_loader import template_loader

    all_css = _REMOTE_IMPORT_RE.sub("", template_loader.all_css(theme_id))
    slides_markup = "\n".join(slides_html)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
{all_css}
body {{ margin:0; padding:0; }}
</style>
</head>
<body>
{slides_markup}
</body>
</html>"""


def _load_layout_schema() -> dict | None:
    from app.services.template_loader import template_loader

    schema_path = template_loader._dir.parent / "schemas" / "slidehtml.layout-snapshot.schema.json"
    if schema_path.is_file():
        return json.loads(schema_path.read_text(encoding="utf-8"))
    return None


def _validate_snapshot(snapshot: dict) -> None:
    schema = _load_layout_schema()
    if jsonschema and schema:
        jsonschema.validate(snapshot, schema)


async def capture_layout_snapshot(slides_html: list[str], theme_id: str = "default") -> dict:
    from app.services.playwright_node import run_playwright_job

    html = _build_deck_html(slides_html, theme_id)
    snapshot = await run_playwright_job(
        mode="snapshot",
        html=html,
        capture_script=PLAYWRIGHT_CAPTURE_LAYOUT_JS,
        viewport={"width": 1280, "height": 720},
    )
    assert isinstance(snapshot, dict)
    _validate_snapshot(snapshot)
    return snapshot
