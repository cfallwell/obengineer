# Optional Word analysis summary

The canonical analysis is the linked Markdown site defined by `analysis-site.md`. This
template applies only when a human requests an optional `.docx`.

The Word file is a generated summary under 20 pages. It never becomes the authority for
attributes, metrics, work orders, or per-object detail.

## Source

Generate a temporary summary Markdown file from the accepted version. Do not hand-maintain
it and do not copy deep wiki detail into it.

## Section order

1. Title page
2. Table of contents
3. Analysis summary
4. Site and backend architecture
5. Findings
6. Recommended instrumentation strategy
7. Recommended implementation path
8. Work-order summary
9. Use-case summaries
10. Next steps

Each top-level section is a Word `Heading 1` and starts on a new page. References back to
the linked Markdown site are clickable when the target is a durable repository URL;
relative host-side links remain listed as paths.

## Content limits

- Findings: conclusion, impact, decision, and verification; no long evidence dump.
- Strategy: one summary per applicable layer.
- Work orders: id, outcome, dependencies, status, and unlocks.
- Use cases: why it matters, question answered, created workflow/transaction, and proof.
- No full attribute dictionary, code samples, OWASP matrix, raw evidence, detector
  catalogue, or Terraform detail.
- No licensing or overage figures; those stay in entitlement exposure.
- No empty or `Not in evidence` sections.

The rendered document must be fewer than 20 pages. If it is longer, shorten summaries;
do not remove findings or use cases.

## Completion

Run `render_customer_doc.py` and `verify_render.py`. The optional Word artifact is complete
only when:

- it was generated from the current version;
- it passes structural and credential checks;
- all internal summary references are clickable;
- it is under 20 pages; and
- it states that the linked Markdown analysis and versioned wiki hold the detail.

Cross-Cutting Attributes and Baggage Propagation remains mandatory in the versioned wiki
when applicable; the Word summary links that contract instead of reproducing its code.
