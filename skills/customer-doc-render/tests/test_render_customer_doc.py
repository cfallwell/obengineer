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

FIXTURE = """# Implementation Recommendations — Acme Storefront — 2026-01-01 — v1

<!-- title-page
subtitle: Instrumentation, Attribution, and Dashboarding Best Practices
tagline: Splunk Observability Cloud • OpenTelemetry • RUM
author: A. Engineer, Technical Account Manager
audience: Acme storefront engineering
date: 2026-01-01
version: v1
header: Implementation Recommendations
-->

## Purpose and Scope

This specifies instrumentation for the **Acme** storefront. Money is in minor units.
See the [Splunk RUM docs](https://docs.splunk.com/observability/) for the agent.

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
"""


def has_break(paragraph) -> bool:
    return render.has_page_break_before(paragraph)


@pytest.fixture
def rendered(tmp_path):
    md = tmp_path / "guide.md"
    md.write_text(FIXTURE)
    docx = tmp_path / "guide.docx"
    counts = render.build(md, docx)
    return md, docx, counts


def test_counts_match_source(rendered):
    _, _, counts = rendered
    assert counts["sections"] == 3          # three H2 sections
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
    assert lines[0].startswith("Implementation Recommendations — Acme Storefront")
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
    assert any("Implementation Recommendations" in p.text for p in header.paragraphs)
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
