#!/usr/bin/env python3
"""Derive a reusable format spec from a customer-approved Word document.

The renderer must be able to reproduce an approved house style without the
approved document being present. This script reads one .docx and writes the
formatting facts the renderer needs — page geometry, heading sizes and colours,
title-page layout, header/footer wiring, and how sections break — to a JSON
spec, plus any header images to an assets directory.

    python3 extract_docx_format.py Approved.docx \
        --spec ../references/document-format.json \
        --assets ../assets

Only formatting is copied. Body text, tenant sensitivity labels, author names,
and revision history are deliberately left behind: the output is a style
contract, not a copy of the source document.

Requires: python-docx (pip install python-docx)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("python-docx is required: pip install python-docx")

HEADING_STYLES = ("Heading 1", "Heading 2", "Heading 3", "Heading 4")


def twips_to_inches(value: str | None) -> float | None:
    return round(int(value) / 1440, 3) if value else None


def page_geometry(doc) -> dict:
    section = doc.sections[0]
    sect_pr = section._sectPr
    pg_mar = sect_pr.find(qn("w:pgMar"))
    geometry = {
        "page_width_in": round(section.page_width / 914400, 3),
        "page_height_in": round(section.page_height / 914400, 3),
        "different_first_page": sect_pr.find(qn("w:titlePg")) is not None,
    }
    for edge in ("top", "right", "bottom", "left", "header", "footer"):
        geometry[f"{edge}_in"] = twips_to_inches(
            pg_mar.get(qn(f"w:{edge}")) if pg_mar is not None else None)
    return geometry


def style_spec(doc) -> dict:
    out: dict[str, dict] = {}
    for name in HEADING_STYLES + ("Normal",):
        try:
            style = doc.styles[name]
        except KeyError:
            continue
        font = style.font
        colour = None
        if font.color is not None and font.color.rgb is not None:
            colour = str(font.color.rgb)
        out[name] = {
            "font": font.name,
            "size_pt": font.size.pt if font.size else None,
            "bold": font.bold,
            "color": colour,
        }
    # docDefaults, not the Normal style, usually carries the body typeface.
    default = doc.styles.element.find(qn("w:docDefaults"))
    if default is not None:
        fonts = default.find(f"{qn('w:rPrDefault')}/{qn('w:rPr')}/{qn('w:rFonts')}")
        if fonts is not None:
            out.setdefault("docDefaults", {})["font"] = fonts.get(qn("w:ascii"))
    return out


def title_page_spec(doc) -> dict:
    """Describe the run of paragraphs before the first page break."""
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        leading = sum(r.text.count("\n") for r in para.runs)
        sizes = [r.font.size.pt for r in para.runs if r.font.size]
        broke = any(br.get(qn("w:type")) == "page"
                    for br in para._p.iter(qn("w:br")))
        if text:
            lines.append({
                "text_shape": classify_title_line(text),
                "size_pt": max(sizes) if sizes else None,
                "bold": any(r.font.bold for r in para.runs),
                "alignment": str(para.alignment),
                "blank_lines_before": leading,
            })
        if broke:
            break
    return {"lines": lines, "ends_with_page_break": True}


def classify_title_line(text: str) -> str:
    lowered = text.lower()
    for label in ("author", "audience", "date", "version", "prepared"):
        if lowered.startswith(label):
            return f"{label}-field"
    if "•" in text or "|" in text:
        return "product-line"
    return "title-or-subtitle"


def break_mechanism(doc) -> dict:
    """Report how the source starts each top-level section on a new page."""
    own, preceding, none = 0, 0, 0
    paragraphs = doc.paragraphs
    for i, para in enumerate(paragraphs):
        if para.style.name != "Heading 1":
            continue
        ppr = para._p.find(qn("w:pPr"))
        if ppr is not None and ppr.find(qn("w:pageBreakBefore")) is not None:
            own += 1
            continue
        prev = paragraphs[i - 1] if i else None
        if prev is not None and any(br.get(qn("w:type")) == "page"
                                    for br in prev._p.iter(qn("w:br"))):
            preceding += 1
        else:
            none += 1
    return {
        "section_style": "Heading 1",
        "with_page_break_before_property": own,
        "with_explicit_break_in_previous_paragraph": preceding,
        "with_no_break": none,
        # The renderer standardises on the property: it cannot be orphaned by an
        # edit to neighbouring content and it never leaves a blank page behind.
        "renderer_uses": "w:pageBreakBefore on the section heading",
    }


# Word stores header/footer decoration as VML shapes, so the flattened text
# carries geometry keywords and EMU offsets alongside the real label.
VML_NOISE = {"top", "right", "bottom", "left", "center", "margin", "page"}


def footer_texts(path: Path) -> list[str]:
    labels: set[str] = set()
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not re.match(r"word/(footer|header)\d*\.xml$", name):
                continue
            text = re.sub(r"<[^>]+>", " ", zf.read(name).decode("utf-8"))
            for token in re.split(r"\s{2,}", text):
                token = token.strip()
                if (token and len(token) < 60
                        and re.search(r"[A-Za-z]", token)
                        and token.lower() not in VML_NOISE):
                    labels.add(token)
    return sorted(labels)


def extract_images(path: Path, assets: Path) -> list[str]:
    written = []
    assets.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        header_rels = [n for n in zf.namelist()
                       if re.match(r"word/_rels/header\d*\.xml\.rels$", n)]
        targets: set[str] = set()
        for rel in header_rels:
            body = zf.read(rel).decode("utf-8")
            targets.update(re.findall(r'Target="(media/[^"]+)"', body))
        for target in sorted(targets):
            src = f"word/{target}"
            if src not in zf.namelist():
                continue
            out = assets / f"header-banner{Path(target).suffix}"
            with zf.open(src) as fh, out.open("wb") as dst:
                shutil.copyfileobj(fh, dst)
            written.append(out.name)
    return written


def header_image_size(path: Path) -> dict | None:
    """Width and height of the first-page header artwork, in inches."""
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            if not re.match(r"word/header\d*\.xml$", name):
                continue
            body = zf.read(name).decode("utf-8")
            m = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', body)
            if m:
                return {"width_in": round(int(m.group(1)) / 914400, 2),
                        "height_in": round(int(m.group(2)) / 914400, 2)}
    return None


def build_spec(path: Path, assets: Path | None) -> dict:
    doc = Document(str(path))
    spec = {
        "derived_from": path.name,
        "note": ("Formatting only. Regenerate with extract_docx_format.py when "
                 "the customer approves a new house style."),
        "page": page_geometry(doc),
        "styles": style_spec(doc),
        "title_page": title_page_spec(doc),
        "sections": break_mechanism(doc),
        "header_footer_labels": footer_texts(path),
    }
    banner = header_image_size(path)
    if banner:
        spec["header_image"] = banner
    if assets is not None:
        spec["assets"] = extract_images(path, assets)
    return spec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path, help="approved source document")
    ap.add_argument("--spec", type=Path, help="write the JSON spec here")
    ap.add_argument("--assets", type=Path, help="write header images here")
    args = ap.parse_args(argv)

    if not args.docx.is_file():
        sys.exit(f"not a file: {args.docx}")
    spec = build_spec(args.docx, args.assets)
    text = json.dumps(spec, indent=2) + "\n"
    if args.spec:
        args.spec.parent.mkdir(parents=True, exist_ok=True)
        args.spec.write_text(text)
        print(f"wrote {args.spec}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
