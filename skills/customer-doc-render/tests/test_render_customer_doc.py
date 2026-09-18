"""Round-trip tests for the customer document renderer.

Renders a fixture that exercises every construct the guide uses, then asserts the
verifier passes on it and fails on a deliberately damaged copy.

    python3 -m pytest "obengineer/skills/customer-doc-render/tests" -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


render = _load("render_customer_doc")
verify = _load("verify_render")
Document = pytest.importorskip("docx").Document
qn = pytest.importorskip("docx.oxml.ns").qn

FIXTURE = """# Application Analysis — Acme Storefront — 2026-01-01 — v1

<!-- title-page
subtitle: Observed architecture, findings, and instrumentation recommendations
tagline: Splunk Observability Cloud • OpenTelemetry • RUM
author: A. Engineer, Technical Account Manager
audience: Acme storefront engineering
date: 2026-01-01
version: v1
header: Application Analysis
-->

## Purpose and Scope

This specifies instrumentation for the **Acme** storefront. Money is in minor units.
See the [Splunk RUM docs](https://docs.splunk.com/observability/) for the agent.

The attribute dictionary is Appendix A, the processor is described in section 2, and
sections 1 and 3 carry the scope and the detectors. Naming follows
[**Detectors Catalog**](#detectors-catalog) and the code in
[the SpanProcessor](#the-spanprocessor).

A literal `section 3` inside a query is a string, not a reference.

Severity follows a rule: *Critical* means a customer cannot finish, *Minor* means a
ticket. The `acme.market` wildcard `cart.item.*` is an identifier, not emphasis.

- `checkout.review.load` *(`reviewOrder` — **today returns 400 in production**)*

1. First numbered item
2. Second numbered item

### Document control and evidence basis

| Field | Value |
|---|---|
| Application identifier | `acme-storefront` |
| Percentile standard | **p90** |

## Cross-Cutting Attributes and Baggage Propagation

- Set the attribute once, where the value is first known.
- Write it into **W3C Baggage** so `traceparent` and `baggage` propagate.

### Cross-cutting attribute set

| Attribute | Type | Set at | Dimension? | Notes |
|---|---|---|---|---|
| `acme.account_id` | string | login success | No | Mirrored to `enduser.id` |
| `acme.market` | string | Collector (OTTL) | Yes | Derived from `url.path` |

### The SpanProcessor

#### Provider bootstrap

```ts
const KEYS = ['acme.account_id'] as const;

export class BaggageStampProcessor {
  onStart(span, ctx) {
    // A blank line above proves code-block line spacing stays even.
    for (const k of KEYS) span.setAttribute(k, read(ctx, k));
  }
}
```

## Detectors Catalog

| Detector | Trigger | Group by |
|---|---|---|
| Order error rate | > 2% for 5 min | `acme.market` |
| Cardinality guard | promoted keys per Appendix A | `acme.market` |

## Appendix A: Master Attribute Dictionary

Every key the document promotes, with the section that introduced it (section 2).
"""


def has_break(paragraph) -> bool:
    return render.has_page_break_before(paragraph)


def links(container) -> list[tuple[str, str]]:
    """Every internal link in a paragraph or table cell, as (anchor, text)."""
    out = []
    for el in container._element.iter(qn("w:hyperlink")):
        anchor = el.get(qn("w:anchor"))
        if anchor:
            out.append((anchor, "".join(t.text or "" for t in el.iter(qn("w:t")))))
    return out


def bookmark_of(docx, heading: str) -> str:
    para = next(p for p in Document(docx).paragraphs
                if p.style.name.startswith("Heading") and p.text == heading)
    start = para._p.findall(qn("w:bookmarkStart"))
    assert start, f"{heading!r} carries no bookmark"
    return start[0].get(qn("w:name"))


@pytest.fixture
def rendered(tmp_path):
    md = tmp_path / "guide.md"
    md.write_text(FIXTURE)
    docx = tmp_path / "guide.docx"
    counts = render.build(md, docx)
    return md, docx, counts


def test_counts_match_source(rendered):
    _, _, counts = rendered
    assert counts["sections"] == 4          # three body sections and one appendix
    assert counts["tables"] == 3
    assert counts["code_blocks"] == 1


def test_every_section_starts_a_new_page(rendered):
    _, docx, counts = rendered
    doc = Document(docx)
    sections = [p for p in doc.paragraphs
                if p.style.name == "Heading 1" and p.text != "Table of Contents"]
    assert len(sections) == counts["sections"]
    assert all(has_break(p) for p in sections)


def test_a_top_level_section_is_word_heading_1(rendered):
    """The defect this guards: `##` rendering as Heading 2, which leaves the
    contents list indented a level too deep and no Heading 1 in the body."""
    _, docx, _ = rendered
    doc = Document(docx)
    levels = {p.text: p.style.name for p in doc.paragraphs
              if p.style.name.startswith("Heading")}
    assert levels["Purpose and Scope"] == "Heading 1"
    assert levels["Cross-Cutting Attributes and Baggage Propagation"] == "Heading 1"
    assert levels["Document control and evidence basis"] == "Heading 2"
    assert levels["Provider bootstrap"] == "Heading 3"


def test_title_page_is_simple_and_precedes_the_contents(rendered):
    _, docx, _ = rendered
    doc = Document(docx)
    paragraphs = list(doc.paragraphs)
    toc = next(i for i, p in enumerate(paragraphs)
               if p.text.strip() == "Table of Contents")
    lines = [p.text.strip() for p in paragraphs[:toc] if p.text.strip()]
    assert lines[0].startswith("Application Analysis — Acme Storefront")
    assert "Author: A. Engineer, Technical Account Manager" in lines
    assert "Version: v1" in lines
    assert len(lines) <= verify.MAX_TITLE_PAGE_LINES
    assert paragraphs[toc].style.name == "Heading 1"
    assert has_break(paragraphs[toc])


def test_first_page_header_and_footers(rendered):
    _, docx, _ = rendered
    section = Document(docx).sections[0]
    assert section.different_first_page_header_footer
    header = section.first_page_header
    assert "graphic" in header.paragraphs[0]._p.xml, "banner image missing"
    assert any("Application Analysis" in p.text for p in header.paragraphs)
    assert "Confidential" in section.first_page_footer.paragraphs[0].text
    assert "Page" in section.footer.paragraphs[0].text


def test_prose_above_the_first_section_is_rejected(tmp_path):
    """A simple title page is part of the format, so front matter that would
    crowd it is an authoring error rather than something to render anyway."""
    md = tmp_path / "crowded.md"
    md.write_text(
        "# Title\n\n"
        "**Application identifier:** `acme` — taken from the resource tag.\n"
        "**Realm observed:** `us1`.\n\n"
        "## Section\n\ntext\n"
    )
    with pytest.raises(render.TemplateError) as exc:
        render.build(md, tmp_path / "crowded.docx")
    assert "between the title and the first section heading" in str(exc.value)


def test_unknown_title_page_field_is_rejected(tmp_path):
    md = tmp_path / "typo.md"
    md.write_text(
        "# Title\n\n<!-- title-page\nsubtitel: typo\n-->\n\n## Section\n\ntext\n")
    with pytest.raises(render.TemplateError) as exc:
        render.build(md, tmp_path / "typo.docx")
    assert "unknown title-page field" in str(exc.value)


def test_bold_wrapping_code_keeps_both_and_prints_no_backticks(rendered):
    """The defect this guards: **`code`** rendering as literal **`code`**."""
    _, docx, _ = rendered
    doc = Document(docx)
    for para in doc.paragraphs:
        assert "**" not in para.text, f"literal bold marker survived: {para.text[:60]}"


def test_italics_render_as_italics_and_not_as_asterisks(rendered):
    """The defect this guards: *Critical* shipping as literal *Critical*, which
    happened on a 145-page deliverable because nothing checked single markers."""
    _, docx, _ = rendered
    doc = Document(docx)
    runs = [r for p in doc.paragraphs for r in p.runs]

    emphasised = {r.text for r in runs if r.italic}
    assert {"Critical", "Minor"} <= emphasised

    # A wildcard inside an identifier is monospace, not emphasis, and the two
    # must not be confused: `cart.item.*` … `acme.market` would otherwise read
    # as one italic span swallowing the text between them.
    wildcard = next(r for r in runs if r.text == "cart.item.*")
    assert wildcard.font.name == "Consolas" and not wildcard.italic

    # Italic wrapping a code span and a bold span at once.
    nested = next(r for r in runs if r.text == "reviewOrder")
    assert nested.italic and nested.font.name == "Consolas"
    assert any(r.italic and r.bold and "returns 400" in r.text for r in runs)

    for para in doc.paragraphs:
        literal = [r.text for r in para.runs
                   if "*" in r.text and r.font.name != "Consolas"]
        assert not literal, f"literal italic marker survived: {literal}"


def test_bold_and_code_spans_may_wrap_across_source_lines(tmp_path):
    """Prose wraps at 80 columns; a **bold span** wraps with it. A line-based
    parser sees two unbalanced halves and prints the markers literally."""
    md = tmp_path / "wrapped.md"
    md.write_text(
        "# Title\n\n## Section\n\n"
        "**No message bus is observable from the browser, so the bus technology\n"
        "is Not in evidence** and the `nuskin.market` key must arrive by\n"
        "baggage instead.\n"
    )
    docx = tmp_path / "wrapped.docx"
    render.build(md, docx)
    doc = Document(docx)
    prose = [p for p in doc.paragraphs if "message bus" in p.text]
    assert len(prose) == 1, "wrapped lines must rejoin into one paragraph"
    assert "**" not in prose[0].text
    assert "`" not in prose[0].text
    assert any(r.bold for r in prose[0].runs)
    assert any(r.font.name == "Consolas" for r in prose[0].runs)
    assert verify.check(md, docx, 2) == []


def test_an_appendix_and_a_numbered_section_are_clickable(rendered):
    """A reader in Word clicks `Appendix A` and lands on Appendix A."""
    _, docx, counts = rendered
    doc = Document(docx)
    prose = next(p for p in doc.paragraphs if "attribute dictionary is" in p.text)
    found = dict((text, anchor) for anchor, text in links(prose))

    assert found["Appendix A"] == bookmark_of(docx, "Appendix A: Master Attribute Dictionary")
    assert found["section 2"] == bookmark_of(
        docx, "Cross-Cutting Attributes and Baggage Propagation")
    # A phrase carrying one number links whole; several numbers link one by one,
    # so "sections 1 and 3" reaches both rather than only the first.
    assert found["1"] == bookmark_of(docx, "Purpose and Scope")
    assert found["3"] == bookmark_of(docx, "Detectors Catalog")
    assert "and sections 1 and 3 carry the scope" in prose.text
    assert counts["xrefs"] == 8


def test_a_named_reference_is_an_anchor_link_that_keeps_its_formatting(rendered):
    """Section titles are also ordinary vocabulary, so naming one is an explicit
    link in the source — and the label keeps its bold rather than printing it."""
    _, docx, _ = rendered
    doc = Document(docx)
    prose = next(p for p in doc.paragraphs if "Naming follows" in p.text)
    found = dict((text, anchor) for anchor, text in links(prose))
    assert found["Detectors Catalog"] == bookmark_of(docx, "Detectors Catalog")
    assert found["the SpanProcessor"] == bookmark_of(docx, "The SpanProcessor")
    assert "**" not in prose.text
    bold = [el for el in prose._element.iter(qn("w:hyperlink"))
            if el.findall(".//" + qn("w:b"))]
    assert bold, "a bold link label lost its weight"


def test_a_reference_inside_a_table_cell_is_clickable(rendered):
    _, docx, _ = rendered
    cell = next(c for t in Document(docx).tables for row in t.rows for c in row.cells
                if "promoted keys per" in c.text)
    assert links(cell) == [
        (bookmark_of(docx, "Appendix A: Master Attribute Dictionary"), "Appendix A")]


def test_a_reference_in_a_code_span_stays_a_string(rendered):
    """`section 3` in a query is a literal, and linking it would be wrong."""
    _, docx, _ = rendered
    prose = next(p for p in Document(docx).paragraphs if "inside a query" in p.text)
    assert [text for _, text in links(prose)] == []
    literal = next(r for r in prose.runs if r.text == "section 3")
    assert literal.font.name == "Consolas"


def test_headings_are_destinations_and_never_link_to_themselves(rendered):
    _, docx, _ = rendered
    for para in Document(docx).paragraphs:
        if not para.style.name.startswith("Heading") or not para.text:
            continue
        if para.text == "Table of Contents":
            continue
        assert para._p.findall(qn("w:bookmarkStart")), f"no bookmark: {para.text}"
        assert not links(para), f"a heading links out of itself: {para.text}"


def test_a_bookmark_never_lands_in_front_of_the_paragraph_properties(rendered):
    """WordprocessingML wants `w:pPr` first. A bookmark inserted before it renders
    correctly in LibreOffice and makes Word offer to repair the file, so the
    defect would only ever be found by the customer opening it."""
    md, docx, _ = rendered
    doc = Document(docx)
    for para in doc.paragraphs:
        ppr = para._p.find(qn("w:pPr"))
        if ppr is not None:
            assert para._p.index(ppr) == 0, (
                f"content precedes w:pPr in {para.text[:40]!r}")

    # And the verifier says so if it ever regresses.
    para = next(p for p in doc.paragraphs if p._p.findall(qn("w:bookmarkStart")))
    mark = para._p.findall(qn("w:bookmarkStart"))[0]
    para._p.remove(mark)
    para._p.insert(0, mark)
    damaged = docx.with_name("misordered.docx")
    doc.save(damaged)
    failures = verify.check(md, damaged, 2)
    assert any("before w:pPr" in f for f in failures), failures


def test_a_reference_to_a_section_that_does_not_exist_is_refused(tmp_path):
    """What a renumbering leaves behind: text that still reads and a link that
    goes nowhere. In Word it is invisible until a customer clicks it."""
    md = tmp_path / "stale.md"
    md.write_text("# Title\n\n## Only Section\n\nDetail is in section 4.\n")
    with pytest.raises(render.TemplateError) as exc:
        render.build(md, tmp_path / "stale.docx")
    assert "points at nothing" in str(exc.value)
    assert "1 sections" in str(exc.value)


def test_an_anchor_link_with_no_heading_is_refused_with_the_near_miss(tmp_path):
    md = tmp_path / "dead.md"
    md.write_text(
        "# Title\n\n## Detectors Catalog\n\nSee [the catalogue](#detectors).\n")
    with pytest.raises(render.TemplateError) as exc:
        render.build(md, tmp_path / "dead.docx")
    assert "matches no heading" in str(exc.value)
    assert "#detectors-catalog" in str(exc.value)


def test_verifier_catches_a_reference_that_stopped_being_a_link(rendered):
    md, docx, _ = rendered
    doc = Document(docx)
    para = next(p for p in doc.paragraphs if "attribute dictionary is" in p.text)
    link = next(el for el in para._element.iter(qn("w:hyperlink")))
    link.getparent().remove(link)
    damaged = docx.with_name("unlinked.docx")
    doc.save(damaged)
    failures = verify.check(md, damaged, 2)
    assert any("cross-reference count" in f for f in failures), failures


def test_verifier_catches_a_link_that_lands_nowhere(rendered):
    md, docx, _ = rendered
    doc = Document(docx)
    para = next(p for p in doc.paragraphs if "attribute dictionary is" in p.text)
    link = next(el for el in para._element.iter(qn("w:hyperlink")))
    link.set(qn("w:anchor"), "_appendix_z_that_was_deleted")
    damaged = docx.with_name("dangling.docx")
    doc.save(damaged)
    failures = verify.check(md, damaged, 2)
    assert any("point at no bookmark" in f for f in failures), failures


def test_verifier_catches_a_heading_with_no_bookmark(rendered):
    md, docx, _ = rendered
    doc = Document(docx)
    para = next(p for p in doc.paragraphs
                if p.style.name == "Heading 1" and p.text == "Detectors Catalog")
    for el in para._p.findall(qn("w:bookmarkStart")):
        para._p.remove(el)
    damaged = docx.with_name("unbookmarked.docx")
    doc.save(damaged)
    failures = verify.check(md, damaged, 2)
    assert any("carry no bookmark" in f for f in failures), failures


def test_verifier_passes_on_a_clean_render(rendered):
    md, docx, _ = rendered
    assert verify.check(md, docx, 2) == []


def test_verifier_catches_a_missing_page_break(rendered):
    md, docx, _ = rendered
    doc = Document(docx)
    for para in doc.paragraphs:
        if para.style.name == "Heading 1" and para.text != "Table of Contents":
            ppr = para._p.get_or_add_pPr()
            for el in ppr.findall(qn("w:pageBreakBefore")):
                ppr.remove(el)
            break
    damaged = docx.with_name("damaged.docx")
    doc.save(damaged)
    failures = verify.check(md, damaged, 2)
    assert any("pageBreakBefore" in f for f in failures), failures


def test_renderer_refuses_to_save_without_the_break(rendered, monkeypatch):
    """The guarantee: a break that failed to apply raises instead of shipping."""
    md, docx, _ = rendered
    monkeypatch.setattr(render, "has_page_break_before", lambda p: False)
    with pytest.raises(render.TemplateError) as exc:
        render.build(md, docx.with_name("never-saved.docx"))
    assert "new page" in str(exc.value)


def test_verifier_flags_a_credential(tmp_path):
    # Assembled at runtime: a credential-shaped literal must not be committed,
    # not even the vendor's documentation example.
    fake_key = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    md = tmp_path / "leak.md"
    md.write_text(
        FIXTURE.replace(
            "## Detectors Catalog",
            f"## Detectors Catalog\n\nToken: {fake_key}\n",
        )
    )
    docx = tmp_path / "leak.docx"
    render.build(md, docx)
    failures = verify.check(md, docx, 2)
    assert any("access key" in f for f in failures), failures


def test_fence_aware_heading_census_ignores_comments_in_code(tmp_path):
    """A `#` comment inside a fence must not be counted as a heading."""
    md = tmp_path / "fence.md"
    md.write_text(
        "# Title\n\n## Section\n\n```yaml\n# not a heading\nprocessors: []\n```\n"
    )
    parsed = verify.parse_markdown(md, 2)
    assert [h[1] for h in parsed["headings"]] == ["Title", "Section"]
    assert parsed["sections"] == [(2, "Section")]
    assert parsed["code_blocks"] == 1


def test_format_spec_is_committed_and_drives_the_render():
    """A fresh session must reproduce the layout with no approved sample present."""
    spec = render.load_format(None)
    assert spec["page"]["page_width_in"] == 8.5
    assert spec["styles"]["Heading 1"]["size_pt"] == 16.0
    assert spec["styles"]["Heading 3"]["color"] == "EC008C"
    # Heading 4 is unformatted in the approved sample; the fallback fills it in.
    assert spec["styles"]["Heading 4"]["size_pt"] is not None
    assert render.FORMAT_SPEC.is_file()
    assert render.HEADER_BANNER.is_file()
