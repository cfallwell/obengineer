---
name: deliverable-review
description: >-
  Grade a produced instrumentation deliverable against the completeness bar and
  the pre-delivery checklist before a human sees it — every required section
  present, the cross-cutting section with all five code subsections, no dimension
  list without cardinality arithmetic, no baggage key without a named consumer, no
  join without a labelled type, the dictionary agreeing with the schema, and no
  credential anywhere. Returns a pass or a numbered list of defects with the file
  and line for each. Use when the user types $deliverable-review, asks whether a
  guide or analysis is ready, asks what is missing from a deliverable, or at the
  end of any run that produced one. Reads and reports; does not rewrite.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Deliverable Review — the checklist, executed

## Overview

Every run in this bundle ends with a checklist that the run itself is supposed to fill in.
That is self-assessment by the party with the strongest incentive to pass, and it fails the
same way every time: the checklist gets ticked from memory rather than from the document,
and the section that is missing is the one the author forgot they were meant to write.

So the grader is separate from the author. This skill reads the artifacts as a reviewer
would — no memory of writing them, no assumption that a heading exists because it was
intended — and returns a pass or a numbered defect list.

The rubric is not invented here. It is
[`../references/document-template.md`](../references/document-template.md): the section
order, the completeness bar, and the pre-delivery checklist. **If the rubric and this skill
disagree, the rubric wins** and this file is what needs fixing.

## Why a separate grader is worth the round trip

| Without | With |
|---|---|
| The checklist is filled from intent | It is filled from the document |
| A missing section is discovered by the customer | It is discovered before delivery, by name and line |
| "Cardinality is important" counts as cardinality guidance | A dimension list with no MTS arithmetic is a defect with a line number |
| Every run's quality depends on the author's attention that day | Quality has a floor that does not move |
| Nothing is measurable across engagements | Defect counts by class accumulate, and the references get fixed where they actually fail |

That last row is the one that compounds. A defect class that recurs across engagements is
not an author problem, it is a **specification problem** — the reference that was supposed to
prevent it is unclear, and the fix belongs there.

## Process

### Step 1 — Establish what should exist

Read the rubric's section list. Read `engagement-inputs.yaml` to learn which sections are
conditional and how each condition resolved:

| Condition | Sections it governs |
|---|---|
| A browser exists | RUM placement, RUM SPA / client route changes, ad attribution |
| A client router is in evidence | RUM SPA / client route changes must carry **code**, not prose |
| A bus exists | Messaging Observability, and one `Messaging boundary — <bus>` subsection per bus |
| Log Observer Connect is entitled | Log Observer Connect panels; otherwise they must **not** appear |
| Session replay accepted in writing | Always-on replay may be recommended; otherwise it must not be |

A conditional section that is absent is a defect. A conditional section present as
`Not in evidence` **with the evidence that would settle it** is a pass. A conditional section
present as `Not in evidence` with nothing else is a defect — it is a heading pretending to be
an answer.

### Step 2 — Walk the completeness bar, row by row

Every row of the rubric's completeness bar, against the document rather than against
recollection. For each defect record: the row, the file, the line, and the smallest change
that fixes it.

Do not stop at the first defect. A review that returns one problem gets one fix and another
review; a review that returns all of them gets one revision.

### Step 3 — Check the things only a machine will check

These are the checks a human reviewer reliably skips, which makes them the most valuable
part of the pass:

- **Dictionary against schema.** Every attribute in Appendix A appears in `attribute-schema.json` and the reverse, with the same `dimension` verdict on both sides. A disagreement here means the implementer and the customer are reading different contracts.
- **Every baggage key has a named consumer.** A dashboard variable, a detector `group by`, or a documented pivot. No consumer, no baggage — this is the check that keeps the set at six.
- **Every dimension-eligible key has arithmetic.** Distinct values, metrics, services, MTS cost. A promotion with no number cannot be approved, only waved through.
- **Every meter has three to six bounded dimensions**, and no identity key among them.
- **Every use-case join carries a label**: continue trace, span link, or attribute pivot. And span links appear **only** for webhooks, batch consume, DLQ redrive, schedulers, and scatter/gather.
- **One percentile** across the whole document. Two percentiles is two definitions of slow.
- **Every workflow name matches `standards.workflow_naming`**, and every `workflow.step` enumeration is bounded and stated.
- **The APM Business Workflow tag is named**, once, with its value shape. A TAM cannot configure a description.
- **No credential.** Token shapes, `-----BEGIN`, long random strings, and anything the deny list names. This check fails the deliverable outright rather than adding a defect row.
- **Cross-references resolve.** A guide that cites a section number that does not exist was reorganised without being re-read.

### Step 4 — Verify the rendered artifact, not just the Markdown

Run `verify_render.py`. Then confirm what it does not: the `.docx` is newer than the
Markdown it came from, and no one has hand-edited it. A `.docx` edited after rendering is a
second source of truth, and it will disagree with the Markdown within a week.

### Step 5 — Report

```
FAIL — 4 defects, 1 blocking

BLOCKING
  1. Credential-shaped value at INSTRUMENTATION-GUIDE.md:412
     Row: "No ingest token, secret, or credential value anywhere"
     Fix: replace with ${SPLUNK_ACCESS_TOKEN}

DEFECTS
  2. Dimension list has no MTS arithmetic (line 588)
     Row: "A dimension list with no cardinality arithmetic"
     Fix: add distinct values x metrics x services per row, against headroom
  3. session.market in baggage with no named consumer (line 233)
     ...
```

Order by blocking first, then by rubric order. Name the row, so the defect is traceable to
the rubric rather than to the reviewer's taste — and so a recurring defect class is visible
as a specification problem rather than an author problem.

Then, in one line: the defect count by class, appended to the engagement's outcome record.
That line is the only thing that makes quality measurable across engagements.

## Warning signs

- **The review passes on the first attempt, every time.** Then it is checking presence of headings and not their content, and it has become decoration.
- **A defect is reported without a line number.** Unactionable; the author will re-read the whole document and find nothing.
- **The reviewer rewrites the document.** Then there is no independent grader, only a second author. Report and stop.
- **A rubric row is skipped as "not applicable" without the input that makes it so.** Applicability comes from `engagement-inputs.yaml`, not from judgement in the moment.
- **The same defect class appears in three engagements.** Stop fixing documents and fix the reference that was supposed to prevent it.

## Non-goals

- Does not rewrite, reorder, or improve the deliverable. It grades. The author fixes.
- Does not judge whether the *design* is right for the target — only whether the contract is complete, internally consistent, and safe. A complete guide can still be the wrong guide, and that is a human's call.
- Does not read a tenant. Whether the telemetry actually arrived is a different question from whether the document specified it.
