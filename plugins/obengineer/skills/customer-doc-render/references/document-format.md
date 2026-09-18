# Approved customer document format

The house style for a customer-facing observability deliverable. Every number
here was measured from a customer-approved Word document with
`scripts/extract_docx_format.py` and is stored machine-readably in
[`document-format.json`](document-format.json). This file is the authority when
no approved sample is available: a fresh session must be able to produce the same
document from these values alone.

`document-format.json` describes how the page looks.
[`document-template.md`](../../references/document-template.md) describes which
sections the document contains and in what order. They are independent: format
is layout, template is content.

## Page

| Property | Value |
|---|---|
| Page size | US Letter, 8.5 × 11 in |
| Top / bottom margin | 0.5 in |
| Left / right margin | 0.4 in |
| Header distance | 0.4 in |
| Footer distance | 0.3 in (the approved sample records 0, because it anchors its footer in a text box; a plain footer paragraph needs clearance from the page edge) |
| Different first page | yes (`w:titlePg`) |

## Page 1 — the title page

Seven short centred lines at most, and no prose:

| Line | Size | Weight |
|---|---|---|
| Document title | 22 pt | bold |
| Subtitle | 16 pt | regular |
| Product line (`Splunk Observability Cloud • OpenTelemetry • RUM`) | 12 pt | regular, muted |
| `Author: <name>, <role>` | 11 pt | regular, muted |
| `Audience: <who>` | 11 pt | regular, muted |
| `Date: <yyyy-mm-dd>` | 11 pt | regular, muted |
| `Version: <vN>` | 11 pt | regular, muted |

The title sits roughly a third of the way down the page; the remaining lines sit
low. The approved sample achieves this with runs of empty lines; the renderer uses
paragraph spacing, which survives a font change.

The first page carries a banner image across the top of the header
(`assets/header-banner.png`, 7.66 in wide) with the document class beside it —
`Implementation Recommendations` for a guide, `Application Analysis` for an
analysis memo. `w:titlePg` keeps the banner off every other page.

**Nothing else belongs on page 1.** Application identifiers, environment scanned,
realm, percentile standard, in-scope languages, evidence basis, and token-handling
notes are content. They belong in a body section — conventionally
`### Document control and evidence basis` under Purpose and Scope — where they get
a heading, a page, and a contents entry.

## Page 2 — the Table of Contents

`Table of Contents` as `Heading 1` with a page break before it, then a
`TOC \o "1-3" \h \z \u` field. `w:updateFields` is set in `settings.xml` so Word
populates it on open rather than showing a placeholder.

Depth 3 is deliberate: it lists sections, their subsections, and the code
subsections inside `Cross-Cutting Attributes and Baggage Propagation`, which is
how a reader finds the baggage code without scrolling.

## Body

| Level | Style | Size | Colour | Behaviour |
|---|---|---|---|---|
| Markdown `##` | `Heading 1` | 16 pt bold | `#393939` | starts a new page |
| Markdown `###` | `Heading 2` | 13 pt bold | `#7F7F7F` | flows |
| Markdown `####` | `Heading 3` | 12 pt | `#EC008C` | flows |
| Markdown `#####` | `Heading 4` | 11 pt bold | `#393939` | flows |

The one-level shift between Markdown and Word matters: the Markdown title owns the
title page, so a top-level Markdown section must land on Word `Heading 1`.
Rendering `##` as `Heading 2` leaves the contents list and the navigation pane
indented a level too deep and no `Heading 1` anywhere in the body — the single most
visible way a render fails to look like the approved document.

### How sections break

Set `w:pageBreakBefore` on the section heading. Do not put an explicit
`<w:br w:type="page"/>` in the preceding paragraph: that break belongs to a
paragraph that may later be edited or deleted, and it produces a blank page
whenever the previous section already ended at a page boundary. The approved
sample used explicit breaks and, as the extracted spec records, missed three of
its own sections that way.

The renderer reads the flag back off every section heading before saving and
raises if one is missing, which is what makes this a guarantee rather than an
intention.

## Footer

`Confidential` centred on page 1; `Confidential  |  Page <n> of <m>` on every page
after it, 8 pt, muted. Page numbers matter even though the approved sample omits
them: a Table of Contents that lists page numbers is only useful if the reader can
find the page.

## Body typography

Calibri 10.5 pt, line spacing 1.08, 6 pt after each paragraph. The approved sample
defaults to Arial because it passed through LibreOffice; Calibri is the Word
default and is what the customer sees in the rest of the deliverable set. Code is
Consolas 8.5 pt in a shaded single-cell table.
