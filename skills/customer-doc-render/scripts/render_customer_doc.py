#!/usr/bin/env python3
"""Render a Markdown deliverable as a customer-reviewable Word document.

The output follows the approved house style recorded in
``references/document-format.json``: a simple title page, then the Table of
Contents on its own page, then every top-level section starting on a new page.
Top-level Markdown sections become Word ``Heading 1`` so the contents list and
the navigation pane read the way a customer architecture review expects.

    python3 render_customer_doc.py GUIDE.md -o Customer-Recommendations.docx

The title page is driven by a block at the top of the Markdown, so no prose
leaks onto it:

    # Document Title

    <!-- title-page
    subtitle: Instrumentation, attribution, and dashboarding
    tagline: Splunk Observability Cloud - OpenTelemetry - RUM
    author: Name, Technical Account Manager
    audience: Customer engineering
    header: Application Analysis
    -->

Any other content between the title and the first section heading is rejected:
it belongs in a body section, not on the title page.

The Markdown is the source of truth. Never hand-edit the .docx; re-render it.

Requires: python-docx (pip install python-docx)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("python-docx is required: pip install python-docx")

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
FORMAT_SPEC = SKILL / "references" / "document-format.json"
HEADER_BANNER = SKILL / "assets" / "header-banner.png"

BODY_FONT = "Calibri"
CODE_FONT = "Consolas"
MUTED = RGBColor(0x6B, 0x74, 0x80)
CODE_SHADE = "F4F5F7"
HEADER_SHADE = "0B3D5C"
INLINE_CODE_SHADE = "EEF1F4"
NOTE_SHADE = "FFF7E6"
CODE_BORDER = "D5D9DE"

# Fallbacks used only when the format spec is unavailable.
DEFAULT_FORMAT = {
    "page": {"page_width_in": 8.5, "page_height_in": 11.0, "top_in": 0.5,
             "bottom_in": 0.5, "left_in": 0.4, "right_in": 0.4,
             "header_in": 0.4, "footer_in": 0.3,
             "different_first_page": True},
    "styles": {
        "Heading 1": {"size_pt": 16.0, "bold": True, "color": "393939"},
        "Heading 2": {"size_pt": 13.0, "bold": True, "color": "7F7F7F"},
        "Heading 3": {"size_pt": 12.0, "bold": False, "color": "EC008C"},
        "Heading 4": {"size_pt": 11.0, "bold": True, "color": "393939"},
    },
    "header_image": {"width_in": 7.66},
}

TITLE_PAGE_FIELDS = ("subtitle", "tagline", "author", "audience", "date",
                     "version", "header")

# Code spans win over every other marker: their contents are literal. Bold is
# tried before italic so `**x**` is not read as an empty italic around `*x*`.
INLINE = re.compile(
    r"(`[^`]+`"
    r"|\*\*(?:[^*]|\*(?!\*))+\*\*"
    r"|(?<!\*)\*(?!\*)(?:\*\*[^*]+\*\*|[^*])+?\*(?!\*)"
    r"|\[[^\]]+\]\([^)]+\))"
)

# Cross-references a reader expects to click, recognised in prose without the
# author writing a link: an appendix by letter, a body section by its number,
# and the same reference written with a section sign. A reference naming a
# section instead of numbering it is written as a Markdown anchor link, because
# a section title is also ordinary vocabulary — "Workflows" and "Business
# Transactions" are Splunk concepts as often as they are headings here, and a
# renderer guessing between the two would link the wrong half.
XREF = re.compile(
    r"(Appendix\s+[A-Z](?![A-Za-z])"
    r"|§\s?\d+(?:\.\d+)?"
    r"|(?<![A-Za-z])[Ss]ections?\s+\d+(?:\s*(?:,|and|to|–|-)\s*\d+)*)"
)
NUMBER = re.compile(r"\d+")
LINK_COLOR = "0563C1"


class TemplateError(RuntimeError):
    """The Markdown cannot be rendered onto the approved template."""


class Targets:
    """Every heading a cross-reference can point at, and how each is addressed.

    Three addresses per document, all resolved from the headings themselves so
    the source never repeats a number the renderer can count:

        anchor    ``[Appendix E](#appendix-e-open-items-and-assumptions)``
        ordinal   ``section 4`` — the fourth top-level section, in order
        appendix  ``Appendix E`` — the heading that opens with that letter
    """

    def __init__(self) -> None:
        self.order: list[dict] = []
        self.by_slug: dict[str, str] = {}
        self.by_ordinal: dict[int, str] = {}
        self.by_appendix: dict[str, str] = {}
        self.sections = 0
        self.links = 0

    def add(self, level: int, text: str, is_section: bool, taken: set[str]) -> dict:
        slug = slugify(text)
        target = {"level": level, "text": text, "slug": slug,
                  "bookmark": bookmark_name(slug, taken)}
        self.order.append(target)
        # A duplicated heading keeps the first slug, matching how a Markdown
        # renderer resolves `#slug` when two headings collide.
        self.by_slug.setdefault(slug, target["bookmark"])
        if is_section:
            self.sections += 1
            self.by_ordinal[self.sections] = target["bookmark"]
            m = re.match(r"Appendix\s+([A-Z])(?![A-Za-z])", text)
            if m:
                self.by_appendix.setdefault(m.group(1), target["bookmark"])
        return target

    def resolve_anchor(self, slug: str) -> str | None:
        return self.by_slug.get(slug.lstrip("#").lower())

    def resolve(self, phrase: str) -> str | None:
        m = re.match(r"Appendix\s+([A-Z])", phrase)
        if m:
            return self.by_appendix.get(m.group(1))
        n = NUMBER.search(phrase)
        return self.by_ordinal.get(int(n.group())) if n else None

    def require(self, phrase: str) -> str:
        """Resolve a cross-reference, or refuse to render.

        A reference to a section that does not exist is what a renumbering
        leaves behind, and it is invisible once the document is a `.docx`:
        the text still reads plausibly and the link goes nowhere.
        """
        bookmark = self.resolve(phrase)
        if bookmark is None:
            raise TemplateError(
                f"cross-reference {phrase!r} points at nothing: the document has "
                f"{self.sections} sections and appendices "
                f"{', '.join(sorted(self.by_appendix)) or '(none)'}"
            )
        self.links += 1
        return bookmark

    def require_anchor(self, url: str, label: str) -> str:
        bookmark = self.resolve_anchor(url)
        if bookmark is None:
            near = [s for s in self.by_slug if url.lstrip("#").lower() in s]
            hint = f"; did you mean #{near[0]}" if near else ""
            raise TemplateError(
                f"anchor link [{label}]({url}) matches no heading in this "
                f"document{hint}"
            )
        self.links += 1
        return bookmark


def collect_targets(lines: list[str], body_start: int, section_level: int) -> Targets:
    """Read the headings before rendering, so a forward reference still resolves."""
    targets, taken, in_fence = Targets(), set(), False
    for line in lines[body_start:]:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6}) +(.*)$", line)
        if m:
            level = len(m.group(1))
            targets.add(level, m.group(2), level <= section_level, taken)
    return targets


# --------------------------------------------------------------------------- #
# low-level docx helpers
# --------------------------------------------------------------------------- #
def shade(element, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element.append(shd)


def set_mono(run, size: float = 8.5) -> None:
    run.font.name = CODE_FONT
    run.font.size = Pt(size)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), CODE_FONT)


def add_bookmark(paragraph, name: str, bookmark_id: int) -> None:
    """Wrap a heading in a bookmark so an internal link has somewhere to land."""
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bookmark_id))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bookmark_id))
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def slugify(text: str) -> str:
    """GitHub's heading slug, so the same anchor works in Markdown and in Word."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s]+", "-", text).strip("-")


def bookmark_name(slug: str, taken: set[str]) -> str:
    """Word bookmarks allow letters, digits and underscores, and stop at 40."""
    base = "_" + re.sub(r"\W", "_", slug)[:38]
    name, n = base, 2
    while name in taken:
        suffix = f"_{n}"
        name, n = base[: 39 - len(suffix)] + suffix, n + 1
    taken.add(name)
    return name


def field(run, instruction: str) -> None:
    """Insert a simple Word field such as PAGE or NUMPAGES."""
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, end):
        run._element.append(el)


def force_page_break_before(paragraph) -> None:
    """Set w:pageBreakBefore directly, and prove it landed.

    python-docx exposes this as a tri-state property that silently accepts a
    value; writing the element ourselves and reading it back means a section
    heading can never ship without its break.
    """
    ppr = paragraph._p.get_or_add_pPr()
    for existing in ppr.findall(qn("w:pageBreakBefore")):
        ppr.remove(existing)
    el = OxmlElement("w:pageBreakBefore")
    el.set(qn("w:val"), "true")
    # Word requires pPr children in schema order; pageBreakBefore comes early.
    ppr.insert(0, el)
    if ppr.find(qn("w:pageBreakBefore")) is None:  # pragma: no cover - guard
        raise TemplateError("failed to set a page break on a section heading")


def has_page_break_before(paragraph) -> bool:
    ppr = paragraph._p.find(qn("w:pPr"))
    if ppr is None:
        return False
    el = ppr.find(qn("w:pageBreakBefore"))
    if el is None:
        return False
    return el.get(qn("w:val")) not in ("false", "0", "off")


def wrap_as_link(paragraph, label: str, *, anchor: str | None = None,
                 url: str | None = None, base_size=None, bold=False,
                 italic=False) -> None:
    """Render a label's own runs, then move them inside a `w:hyperlink`.

    Rendering first means a link label keeps its `code`, **bold**, and *italic*
    formatting instead of printing the markers, which matters because the
    document links section titles and several of those titles are identifiers.
    """
    before = list(paragraph._p)
    write_inline(paragraph, label, base_size=base_size, bold=bold, italic=italic,
                 _unescape=False, _link=True)
    moved = [el for el in list(paragraph._p) if el not in before]

    link = OxmlElement("w:hyperlink")
    if anchor is not None:
        link.set(qn("w:anchor"), anchor)
    else:
        link.set(qn("r:id"), paragraph.part.relate_to(
            url,
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
            is_external=True,
        ))
    for el in moved:
        paragraph._p.remove(el)
        link.append(el)
    paragraph._p.append(link)


def write_xref_text(paragraph, text: str, targets: "Targets", base_size=None,
                    bold=False, italic=False) -> None:
    """Link `Appendix E`, `section 4`, and `sections 5 and 6` where they appear.

    A phrase carrying one number links whole, so the click target is the words a
    reader recognises. A phrase carrying several links each number, so
    "sections 5 and 6" reaches both rather than only the first.
    """
    for token in XREF.split(text):
        if not token:
            continue
        if not XREF.fullmatch(token):
            plain(paragraph, token, base_size, bold, italic)
            continue
        numbers = NUMBER.findall(token)
        if len(numbers) <= 1:
            bookmark = targets.require(token)
            wrap_as_link(paragraph, token, anchor=bookmark, base_size=base_size,
                         bold=bold, italic=italic)
            continue
        for part in re.split(r"(\d+)", token):
            if not part:
                continue
            if part.isdigit():
                wrap_as_link(paragraph, part,
                             anchor=targets.require(f"section {part}"),
                             base_size=base_size, bold=bold, italic=italic)
            else:
                plain(paragraph, part, base_size, bold, italic)


def plain(paragraph, text: str, base_size, bold, italic, link=False) -> None:
    run = paragraph.add_run(text)
    if bold:
        run.bold = True
    if italic:
        run.italic = True
    if base_size:
        run.font.size = Pt(base_size)
    run.font.name = BODY_FONT
    if link:
        run.font.color.rgb = RGBColor.from_string(LINK_COLOR)
        run.font.underline = True
    if text != text.strip():
        run._element.findall(qn("w:t"))[0].set(qn("xml:space"), "preserve")


def write_inline(paragraph, text: str, base_size=None, bold=False, italic=False,
                 targets: "Targets | None" = None, _unescape=True, _link=False):
    """Emit runs for `code`, **bold**, *italic*, and [links](url) in one paragraph.

    Recurses into bold and italic spans so **`code`** keeps both the weight and
    the monospace face instead of printing literal backticks. When `targets` is
    supplied, plain text is also scanned for cross-references and each one
    becomes a link into the document.
    """
    if _unescape:
        text = text.replace("\\|", "|").replace("\\_", "_").replace("\\*", "*")
    for token in INLINE.split(text):
        if not token:
            continue
        if token.startswith("`") and token.endswith("`") and len(token) > 1:
            run = paragraph.add_run(token[1:-1])
            set_mono(run, (base_size or 10.5) - 1.5)
            shade(run._element.get_or_add_rPr(), INLINE_CODE_SHADE)
        elif token.startswith("**") and token.endswith("**"):
            write_inline(paragraph, token[2:-2], base_size=base_size, bold=True,
                         italic=italic, targets=targets, _unescape=False,
                         _link=_link)
            continue
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            write_inline(paragraph, token[1:-1], base_size=base_size, bold=bold,
                         italic=True, targets=targets, _unescape=False,
                         _link=_link)
            continue
        elif token.startswith("[") and "](" in token:
            label, url = token[1:-1].split("](", 1)
            if url.startswith("#"):
                if targets is None:
                    raise TemplateError(
                        f"anchor link {token!r} cannot be resolved here; "
                        "anchor links belong in body content")
                wrap_as_link(paragraph, label,
                             anchor=targets.require_anchor(url, label),
                             base_size=base_size, bold=bold, italic=italic)
            else:
                wrap_as_link(paragraph, label, url=url, base_size=base_size,
                             bold=bold, italic=italic)
            continue
        elif targets is not None and XREF.search(token):
            write_xref_text(paragraph, token, targets, base_size=base_size,
                            bold=bold, italic=italic)
            continue
        else:
            plain(paragraph, token, base_size, bold, italic, link=_link)
            continue
        if bold:
            run.bold = True
        if italic:
            run.italic = True
        if base_size:
            run.font.size = Pt(base_size)
        if _link:
            run.font.color.rgb = RGBColor.from_string(LINK_COLOR)
            run.font.underline = True
        if run.font.name is None:
            run.font.name = BODY_FONT


# --------------------------------------------------------------------------- #
# block builders
# --------------------------------------------------------------------------- #
def add_code_block(doc, lines: list[str], language: str) -> None:
    """A shaded single-cell table, so the block reads as a box and breaks cleanly."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    cell = table.cell(0, 0)
    tc_pr = cell._tc.get_or_add_tcPr()
    shade(tc_pr, CODE_SHADE)

    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), CODE_BORDER)
        borders.append(el)
    tc_pr.append(borders)

    if language:
        tag = cell.paragraphs[0]
        tag.paragraph_format.space_after = Pt(2)
        run = tag.add_run(language.upper())
        run.font.size = Pt(7)
        run.bold = True
        run.font.color.rgb = MUTED
        run.font.name = BODY_FONT
        first = cell.add_paragraph()
    else:
        first = cell.paragraphs[0]

    while lines and not lines[-1].strip():
        lines.pop()

    for i, line in enumerate(lines):
        para = first if i == 0 else cell.add_paragraph()
        fmt = para.paragraph_format
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        fmt.line_spacing = 1.0
        # A blank line needs a monospace run, or it inherits Normal's larger
        # line height and the block gains uneven gaps.
        run = para.add_run(line if line.strip() else " ")
        set_mono(run)
        if line.startswith(" ") or not line.strip():
            run._element.findall(qn("w:t"))[0].set(qn("xml:space"), "preserve")
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip() for c in cells]


def add_table(doc, rows: list[list[str]], targets: "Targets | None" = None) -> None:
    header, body = rows[0], rows[2:]
    cols = max(len(r) for r in rows)
    table = doc.add_table(rows=1, cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    # Let Word size columns to their content rather than splitting evenly.
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "autofit")
    tbl_pr.append(layout)
    width = OxmlElement("w:tblW")
    width.set(qn("w:type"), "pct")
    width.set(qn("w:w"), "5000")
    tbl_pr.append(width)

    hdr = table.rows[0]
    hdr._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))  # repeat per page
    for i in range(cols):
        cell = hdr.cells[i]
        shade(cell._tc.get_or_add_tcPr(), HEADER_SHADE)
        para = cell.paragraphs[0]
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after = Pt(2)
        run = para.add_run(re.sub(r"[`*]", "", header[i] if i < len(header) else ""))
        run.bold = True
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.name = BODY_FONT

    for raw in body:
        cells = table.add_row().cells
        for i in range(cols):
            para = cells[i].paragraphs[0]
            para.paragraph_format.space_before = Pt(1)
            para.paragraph_format.space_after = Pt(1)
            write_inline(para, raw[i] if i < len(raw) else "", base_size=8.5,
                         targets=targets)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def add_toc(doc, depth: int = 3) -> None:
    run = doc.add_paragraph().add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = rf'TOC \o "1-{depth}" \h \z \u'
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Right-click and choose Update Field to build the contents."
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, sep, placeholder, end):
        run._element.append(el)


def force_field_update(doc) -> None:
    """Ask Word to populate the TOC and page counts when the file is opened."""
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    doc.settings.element.append(update)


# --------------------------------------------------------------------------- #
# front matter
# --------------------------------------------------------------------------- #
def parse_title_page(lines: list[str], body_start: int) -> dict:
    """Read the title-page block and reject anything else above the first section.

    A simple title page is part of the approved format, so prose that would
    crowd it is an error the author has to fix rather than something the
    renderer quietly dumps onto page 1.
    """
    fields: dict[str, str] = {}
    stray: list[str] = []
    in_block = False

    for line in lines[1:body_start]:
        text = line.strip()
        if not text:
            continue
        if text.startswith("<!--"):
            in_block = "title-page" in text
            if in_block and text.endswith("-->"):
                in_block = False
            continue
        if text == "-->":
            in_block = False
            continue
        if in_block:
            if text.endswith("-->"):
                text, in_block = text[:-3].strip(), False
                if not text:
                    continue
            key, _, value = text.partition(":")
            key = key.strip().lower()
            if key not in TITLE_PAGE_FIELDS:
                raise TemplateError(
                    f"unknown title-page field {key!r}; allowed fields are "
                    + ", ".join(TITLE_PAGE_FIELDS)
                )
            fields[key] = value.strip()
        else:
            stray.append(text)

    if stray:
        preview = "; ".join(s[:60] for s in stray[:3])
        raise TemplateError(
            f"{len(stray)} line(s) sit between the title and the first section "
            f"heading: {preview}\n"
            "The approved format uses a simple title page. Move this content "
            "into a body section, or declare it inside the "
            "<!-- title-page ... --> block."
        )
    return fields


# --------------------------------------------------------------------------- #
# document assembly
# --------------------------------------------------------------------------- #
def load_format(path: Path | None) -> dict:
    spec = json.loads(json.dumps(DEFAULT_FORMAT))
    source = path or FORMAT_SPEC
    if source.is_file():
        loaded = json.loads(source.read_text())
        for key in ("page", "styles", "header_image"):
            if key in loaded:
                spec.setdefault(key, {}).update(
                    {k: v for k, v in loaded[key].items() if v is not None})
        # A heading the approved document left unformatted keeps our fallback.
        for name, values in DEFAULT_FORMAT["styles"].items():
            merged = spec["styles"].setdefault(name, {})
            for k, v in values.items():
                if merged.get(k) is None:
                    merged[k] = v
    return spec


def apply_styles(doc, spec: dict) -> None:
    styles = doc.styles
    styles["Normal"].font.name = BODY_FONT
    styles["Normal"].font.size = Pt(10.5)
    styles["Normal"].paragraph_format.space_after = Pt(6)
    styles["Normal"].paragraph_format.line_spacing = 1.08
    for name, values in spec["styles"].items():
        if not name.startswith("Heading"):
            continue
        try:
            style = styles[name]
        except KeyError:  # pragma: no cover - default template has Heading 1-9
            continue
        style.font.name = BODY_FONT
        if values.get("size_pt"):
            style.font.size = Pt(values["size_pt"])
        style.font.bold = bool(values.get("bold"))
        if values.get("color"):
            style.font.color.rgb = RGBColor.from_string(values["color"])


def apply_page_setup(doc, spec: dict) -> None:
    page = spec["page"]
    section = doc.sections[0]
    section.page_width = Inches(page["page_width_in"])
    section.page_height = Inches(page["page_height_in"])
    section.left_margin = Inches(page["left_in"])
    section.right_margin = Inches(page["right_in"])
    section.top_margin = Inches(page["top_in"])
    section.bottom_margin = Inches(page["bottom_in"])
    section.header_distance = Inches(max(page.get("header_in") or 0.4, 0.3))
    # The approved document anchors its footer in a text box and records a zero
    # distance; a plain footer paragraph needs clearance from the page edge.
    section.footer_distance = Inches(max(page.get("footer_in") or 0.3, 0.3))
    section.different_first_page_header_footer = bool(
        page.get("different_first_page", True))


def add_first_page_header(section, spec: dict, label: str, banner: Path | None) -> None:
    para = section.first_page_header.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    para.paragraph_format.space_after = Pt(0)
    if banner and banner.is_file():
        width = (spec.get("header_image") or {}).get("width_in", 7.66)
        para.add_run().add_picture(str(banner), width=Inches(width))
    if label:
        line = section.first_page_header.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = line.add_run(label)
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED
        run.font.name = BODY_FONT


def add_footers(section, label: str) -> None:
    """`Confidential` on page 1; `Confidential | Page n of m` after it."""
    first = section.first_page_footer.paragraphs[0]
    first.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if label:
        run = first.add_run(label)
        run.font.size = Pt(8)
        run.font.color.rgb = MUTED
        run.font.name = BODY_FONT

    para = section.footer.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if label:
        para.add_run(f"{label}  |  ")
    para.add_run("Page ")
    field(para.add_run(), "PAGE")
    para.add_run(" of ")
    field(para.add_run(), "NUMPAGES")
    for run in para.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = MUTED
        run.font.name = BODY_FONT


def add_title_page(doc, spec: dict, title: str, fields: dict) -> None:
    """Five centred lines and nothing else, matching the approved layout."""
    accent = RGBColor.from_string(
        spec["styles"].get("Heading 1", {}).get("color") or "393939")

    def line(text: str, size: float, *, bold=False, space_before=0.0,
             color=None) -> None:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(space_before)
        para.paragraph_format.space_after = Pt(2)
        run = para.add_run(text)
        run.font.size = Pt(size)
        run.bold = bold
        run.font.name = BODY_FONT
        run.font.color.rgb = color or accent

    # The approved title page drops the title roughly eight lines down, then
    # sets the remaining facts low on the page.
    line(title, 22, bold=True, space_before=170)
    if fields.get("subtitle"):
        line(fields["subtitle"], 16)
    if fields.get("tagline"):
        line(fields["tagline"], 12, space_before=200, color=MUTED)
    for key in ("author", "audience", "date", "version"):
        if fields.get(key):
            label = key.capitalize()
            line(f"{label}: {fields[key]}", 11, color=MUTED)


def build(md_path: Path, out_path: Path, *, section_level: int = 2,
          footer: str = "Confidential", toc: bool = True,
          toc_depth: int = 3, format_spec: Path | None = None,
          banner: Path | None = HEADER_BANNER) -> dict:
    lines = md_path.read_text().split("\n")
    spec = load_format(format_spec)

    doc = Document()
    apply_styles(doc, spec)
    apply_page_setup(doc, spec)

    title_text = re.sub(r"[`*#]", "", lines[0]).strip() if lines else out_path.stem
    doc.core_properties.title = title_text

    body_start = next(
        (i for i, l in enumerate(lines)
         if re.match(r"^#{1,%d} " % section_level, l) and i > 0),
        len(lines),
    )
    fields = parse_title_page(lines, body_start)
    # Read every heading first: a reference to Appendix E resolves from
    # page 3, which it cannot do if the targets are discovered as they arrive.
    targets = collect_targets(lines, body_start, section_level)

    section = doc.sections[0]
    add_first_page_header(section, spec, fields.get("header", ""), banner)
    add_footers(section, footer)
    add_title_page(doc, spec, title_text, fields)

    # ---- contents ---------------------------------------------------------
    if toc:
        contents = doc.add_heading(level=1)
        force_page_break_before(contents)
        write_inline(contents, "Table of Contents")
        add_toc(doc, toc_depth)
    force_field_update(doc)

    # ---- body -------------------------------------------------------------
    counts = {"sections": 0, "headings": 0, "tables": 0, "code_blocks": 0,
              "xrefs": 0}
    section_headings = []
    heading_index = 0
    i = body_start
    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            language = line[3:].strip()
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            add_code_block(doc, block, language)
            counts["code_blocks"] += 1
            continue

        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            if len(rows) >= 2:
                add_table(doc, rows, targets)
                counts["tables"] += 1
            continue

        i += 1
        if not line.strip() or line.startswith("<!--"):
            continue

        m = re.match(r"^(#{1,6}) +(.*)$", line)
        if m:
            md_level = len(m.group(1))
            is_section = md_level <= section_level
            # The Markdown title owns the title page, so a top-level Markdown
            # section maps to Word Heading 1 and the contents list reads the way
            # the approved document does.
            word_level = max(1, min(md_level - 1, 4)) if section_level >= 2 \
                else max(1, min(md_level, 4))
            para = doc.add_heading(level=word_level)
            para.paragraph_format.space_before = Pt(0 if is_section else 14)
            para.paragraph_format.space_after = Pt(6)
            para.paragraph_format.keep_with_next = True
            if is_section:
                force_page_break_before(para)
                section_headings.append(para)
                counts["sections"] += 1
            # Headings are link destinations, not link sources: a bookmark, and
            # no cross-reference scan, so a heading named "Appendix B" does not
            # link to itself.
            write_inline(para, m.group(2))
            add_bookmark(para, targets.order[heading_index]["bookmark"],
                         heading_index + 1)
            heading_index += 1
            counts["headings"] += 1
            continue

        if re.match(r"^(---+|\*\*\*+|___+)$", line.strip()):
            continue

        if line.startswith("> "):
            quote = [line[2:].strip()]
            while i < len(lines) and lines[i].startswith("> "):
                quote.append(lines[i][2:].strip())
                i += 1
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Inches(0.3)
            para.paragraph_format.space_before = Pt(6)
            shade(para._p.get_or_add_pPr(), NOTE_SHADE)
            write_inline(para, " ".join(quote), base_size=10, targets=targets)
            continue

        # Prose wraps across source lines, and a **bold span** or `code span`
        # may wrap with it. Rejoin the continuation lines before parsing inline
        # markers, or an unbalanced half-marker prints literally.
        def take_continuation() -> str:
            nonlocal i
            parts: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if (not nxt.strip()
                        or nxt.startswith(("```", "|", "> ", "#", "<!--"))
                        or re.match(r"^\s*(?:[-*+]|\d+\.) +", nxt)
                        or re.match(r"^(---+|\*\*\*+|___+)$", nxt.strip())):
                    break
                parts.append(nxt.strip())
                i += 1
            return " ".join(parts)

        m = re.match(r"^(\s*)[-*+] +(.*)$", line)
        if m:
            nested = len(m.group(1)) >= 2
            para = doc.add_paragraph(
                style="List Bullet 2" if nested else "List Bullet")
            para.paragraph_format.space_after = Pt(3)
            write_inline(para, " ".join(filter(None,
                                              [m.group(2), take_continuation()])),
                         targets=targets)
            continue

        m = re.match(r"^(\s*)(\d+)\. +(.*)$", line)
        if m:
            # The literal source number, not Word auto-numbering: a single
            # "List Number" style keeps counting across every list in the
            # document instead of restarting at each one.
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Inches(0.5)
            para.paragraph_format.first_line_indent = Inches(-0.25)
            para.paragraph_format.space_after = Pt(3)
            run = para.add_run(f"{m.group(2)}.\t")
            run.bold = True
            run.font.name = BODY_FONT
            write_inline(para, " ".join(filter(None,
                                              [m.group(3), take_continuation()])),
                         targets=targets)
            continue

        write_inline(doc.add_paragraph(),
                     " ".join(filter(None, [line.strip(), take_continuation()])),
                     targets=targets)

    # ---- the guarantee ----------------------------------------------------
    missing = [p.text[:60] for p in section_headings if not has_page_break_before(p)]
    if missing:
        raise TemplateError(
            "section headings would not start on a new page: " + repr(missing))
    counts["xrefs"] = targets.links

    doc.save(out_path)
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown", type=Path, help="source Markdown file")
    ap.add_argument("-o", "--output", type=Path,
                    help="output .docx (default: alongside the Markdown)")
    ap.add_argument("--section-level", type=int, default=2, choices=(1, 2),
                    help="Markdown heading level that starts a new page (default 2)")
    ap.add_argument("--footer", default="Confidential",
                    help="footer label before the page number ('' for none)")
    ap.add_argument("--no-toc", action="store_true",
                    help="omit the Table of Contents page")
    ap.add_argument("--toc-depth", type=int, default=3,
                    help="deepest heading level in the Table of Contents")
    ap.add_argument("--format-spec", type=Path, default=None,
                    help=f"house-style spec (default {FORMAT_SPEC.name})")
    ap.add_argument("--no-banner", action="store_true",
                    help="omit the first-page header banner")
    args = ap.parse_args(argv)

    if not args.markdown.is_file():
        sys.exit(f"not a file: {args.markdown}")
    out = args.output or args.markdown.with_suffix(".docx")
    try:
        counts = build(args.markdown, out,
                       section_level=args.section_level,
                       footer=args.footer,
                       toc=not args.no_toc,
                       toc_depth=args.toc_depth,
                       format_spec=args.format_spec,
                       banner=None if args.no_banner else HEADER_BANNER)
    except TemplateError as exc:
        sys.exit(f"template error: {exc}")
    print(f"wrote {out}")
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
