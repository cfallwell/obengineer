---
name: customer-doc-render
description: >-
  Render a Markdown deliverable as a customer-reviewable Word document on the
  approved house style: a simple title page, the Table of Contents on its own
  page, every top-level section starting on a new page as Word Heading 1, a
  first-page banner header, and a Confidential footer with page numbers. Then
  prove the render matches its source. Use when the user types
  $customer-doc-render, asks to "make this a Word doc", "convert the guide to
  docx", "produce a customer-review document", asks for "sections on new
  pages", "a title page", or "a table of contents", or when any instrumentation
  guide is being delivered for architecture review. Reads Markdown and writes
  .docx only; never edits the Markdown source.
metadata:
  author: obengineer
  version: 0.2.0
  category: observability
---

# Customer Doc Render — Markdown to reviewable Word

## Overview

Customer architecture reviews happen in Word, not in a terminal. Engineers work
from Markdown. Maintaining both by hand guarantees they drift, and a drifted
deliverable is worse than no deliverable because the reader cannot tell which one
is true.

This skill makes the Markdown the single source and the `.docx` a build artifact.
Every guide delivery produces both, and the Word file is always regenerated —
never edited.

The layout is not a matter of taste. It is recorded in
[`references/document-format.json`](references/document-format.json) and described
in [`references/document-format.md`](references/document-format.md), so the same
document comes out of a fresh session with no approved sample to copy from.

## The three rules that make it a customer document

1. **A simple title page.** Title, subtitle, product line, author, audience, date, version. Nothing else. No metadata dump, no evidence basis, no scope notes.
2. **The Table of Contents on its own page**, immediately after the title page, as a field Word refreshes on open.
3. **Every top-level section starts on a new page**, as Word `Heading 1`.

The renderer enforces all three. It refuses to build a document that breaks
rule 1, and it refuses to save one that breaks rule 3.

## When to use

- Any run of `instrumentation-analyze` (the analysis is not delivered until both renderings exist).
- The analysis memo from `instrumentation-analyze`, when the customer wants to review findings before the contract.
- Any Markdown deliverable heading to a review meeting.

## Process

### Step 1 — Give the source a title-page block

The renderer expects ordinary Markdown: ATX headings, pipe tables, fenced code
blocks, `-`/`*` bullets, `1.` ordered lists, `>` blockquotes, `**bold**`,
`` `code` ``, and `[links](url)`.

The first line is the document title, and the title page is declared explicitly
so prose cannot leak onto it:

```markdown
# Instrumentation Guide — <App> — <date> — v3

<!-- title-page
subtitle: Instrumentation, attribution, and dashboarding
tagline: Splunk Observability Cloud • Splunk Enterprise • ThousandEyes • OpenTelemetry
author: <Name, Role>
audience: <Customer> engineering, platform SRE, and the Splunk TAM
date: 2026-09-17
version: v3
header: Application Analysis
-->

## Purpose and Scope
```

Every field is optional except the title. `header` sets the text beside the
first-page banner.

**Any other content between the title and the first `##` is an error.** The
renderer stops and names the offending lines. Application identifiers, realms,
percentile standards, evidence basis, and token-handling notes are real content:
file them in a body section — `### Document control and evidence basis` under
Purpose and Scope is the conventional home — where they get a heading, a page,
and a contents entry.

### Step 2 — Render

```bash
python3 scripts/render_customer_doc.py docs/observability/analysis-<app>-<date>.md \
    -o "docs/observability/<Customer>-<App>-Analysis-<date>.docx"
```

Markdown `##` becomes Word `Heading 1` and starts a new page; `###` becomes
`Heading 2`; `####` becomes `Heading 3`. That one-level shift is deliberate: the
Markdown title owns the title page, so the contents list and the Word navigation
pane read the way a customer architecture review expects instead of being indented
a level too deep.

| Flag | Use |
|---|---|
| `--section-level 1` | The source uses `#` for sections rather than `##` |
| `--footer ""` | No confidentiality label, page numbers only |
| `--no-toc` | Short memo that does not need contents |
| `--toc-depth 2` | Contents lists sections and subsections only |
| `--no-banner` | Suppress the first-page banner image |
| `--format-spec <path>` | Render onto a different approved house style |

### Step 3 — Verify, do not eyeball

```bash
python3 scripts/verify_render.py docs/observability/analysis-<app>-<date>.md \
    "docs/observability/<Customer>-<App>-Analysis-<date>.docx"
```

The verifier is fence-aware, so YAML and SignalFlow comments inside code blocks are
never miscounted as headings — a real defect that silently inflates section counts.
It fails the render when:

- heading, table, or code-block counts disagree with the source;
- a top-level section did not land on `Heading 1`;
- any section heading is missing `w:pageBreakBefore`;
- the title page carries more than seven lines, or any line long enough to be prose;
- Markdown markers leaked as literal text (`**bold**` or backticks printed in prose — what happens when bold wraps a code span and the two are not composed);
- a credential-shaped value reached the document (JWT, opaque hex token, cloud access key, private-key block, or a URL with inline credentials);
- there is no Table of Contents field, or Word will not refresh it on open.

Exit code 0 means the artifact is deliverable. Do not hand over a `.docx` that has
not passed.

### Step 4 — Optional visual check

When the layout itself is in question — a very wide table, a long code block — render
to PDF and look at the pages rather than guessing:

```bash
soffice --headless --convert-to pdf --outdir /tmp/preview "<file>.docx"
pdftoppm -r 90 -png -f 1 -l 3 /tmp/preview/<file>.pdf /tmp/preview/page
```

LibreOffice does not execute the Table of Contents field, so the contents page looks
empty in the PDF while being correct in Word. That is expected; check it in Word if
the contents are what you are verifying.

## Adopting a different house style

When a customer approves a new sample document, derive the spec from it rather
than eyeballing sizes:

```bash
python3 scripts/extract_docx_format.py Approved.docx \
    --spec references/document-format.json --assets assets
```

The extractor copies formatting only — page geometry, heading sizes and colours,
title-page shape, header artwork, footer labels, and how sections break. It
deliberately leaves behind body text, author names, revision history, and
Microsoft Purview sensitivity labels, which carry tenant identifiers and have no
place in a committed template.

## Formatting decisions worth knowing

| Behaviour | Why |
|---|---|
| Section breaks use `w:pageBreakBefore` on the heading | An explicit break in the preceding paragraph gets orphaned when neighbouring content is edited, and leaves a blank page when the previous section already ended at a page boundary. The approved sample used explicit breaks and missed three sections as a result |
| The renderer re-reads the flag before saving | A page break that failed to apply raises instead of shipping, which is what makes "every section on a new page" a guarantee rather than an intention |
| Ordered lists print the literal source number | One shared Word numbering style keeps counting across every list in the document, so a "Guardrails" list opens at 30 instead of 1 |
| Blank lines inside code blocks get a monospace space run | Otherwise they inherit the body font's line height and the block gains uneven gaps |
| Code blocks are single-cell shaded tables | Reads as a box, keeps its border, and still breaks across pages cleanly |
| Table header rows set `tblHeader` | A 44-row registry spanning pages stays readable |
| Tables use autofit layout | Word sizes columns to content instead of splitting evenly |
| The banner sits in a first-page-only header | `w:titlePg` keeps it off the body pages, matching the approved sample |
| `updateFields` is set in settings.xml | Word populates the contents and page counts on open, without the reader pressing F9 |

## Warning signs

- **The `.docx` is newer than the Markdown.** Someone edited the Word file. Discard those edits, fix the Markdown, re-render.
- **`template error: N line(s) sit between the title and the first section heading`.** Front matter is being used as a title page. Move it into a body section.
- **Sections render as `Heading 2`.** The source is being rendered with `--section-level 1`, or the title `#` is missing so the level shift is off by one.
- **The verifier reports leaked backticks and the paragraph is not a code box.** Bold wrapping a code span; the inline parser must recurse into bold rather than emitting its contents raw.
- **Section count is one higher than expected.** A `#` comment inside a fenced code block is being read as a heading; confirm the fence is closed.

## Non-goals

- Does not edit, reformat, or lint the Markdown source.
- Does not produce PowerPoint, PDF, or HTML. PDF is available for previewing only.
- Does not invent a house style. It renders the one recorded in `references/document-format.json`.
