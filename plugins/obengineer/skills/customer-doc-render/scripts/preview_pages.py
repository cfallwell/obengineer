#!/usr/bin/env python3
"""Rasterise the first pages of a PDF into one contact sheet.

Layout problems — a table wider than the page, a section that failed to break, a
title page crowded with prose — are visible in seconds and invisible in a
structural diff. Convert the .docx with LibreOffice first, then:

    python3 preview_pages.py preview/Guide.pdf --pages 4 -o preview/sheet.png

Use --start to land on a section deep in the document — a wide detector table or a
use-case page is where layout actually breaks, and it is never on page 1.

LibreOffice does not execute the Table of Contents field, so the contents page
looks empty here while being correct in Word.

Requires: pymupdf (pip install pymupdf)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("pymupdf is required: pip install pymupdf")

GUTTER = 12
BACKDROP = 220


def contact_sheet(pdf: Path, out: Path, pages: int, dpi: int, columns: int,
                  start: int = 1) -> None:
    doc = pymupdf.open(pdf)
    first = max(0, min(start - 1, doc.page_count - 1))
    last = min(first + pages, doc.page_count)
    tiles = [doc.load_page(i).get_pixmap(dpi=dpi) for i in range(first, last)]
    if not tiles:
        sys.exit(f"{pdf} has no pages")
    count = len(tiles)

    width, height = tiles[0].width, tiles[0].height
    rows = -(-count // columns)
    sheet = pymupdf.Pixmap(
        pymupdf.csRGB,
        pymupdf.IRect(0, 0,
                      width * columns + GUTTER * (columns + 1),
                      height * rows + GUTTER * (rows + 1)),
        False,
    )
    sheet.clear_with(BACKDROP)
    for i, tile in enumerate(tiles):
        tile.set_origin(GUTTER + (i % columns) * (width + GUTTER),
                        GUTTER + (i // columns) * (height + GUTTER))
        sheet.copy(tile, tile.irect)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"wrote {out} (pages {first + 1}–{last} of {doc.page_count})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("contact-sheet.png"))
    ap.add_argument("--pages", type=int, default=4)
    ap.add_argument("--start", type=int, default=1,
                    help="first page to rasterise, 1-based (default: 1)")
    ap.add_argument("--dpi", type=int, default=80)
    ap.add_argument("--columns", type=int, default=2)
    args = ap.parse_args(argv)

    if not args.pdf.is_file():
        sys.exit(f"not a file: {args.pdf}")
    contact_sheet(args.pdf, args.output, args.pages, args.dpi, args.columns,
                  args.start)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
