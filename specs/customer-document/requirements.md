# Customer instrumentation document — requirements

Traceable requirements for the deliverable format. The authoring spec is
`../../skills/references/document-template.md`; this file is what a reviewer checks
against, and each requirement names the test or command that proves it.

## Artifacts

| ID | Requirement | Verified by |
|---|---|---|
| R1 | A guide run emits Markdown, a `.docx` rendered from that Markdown, and `attribute-schema.json` | Pre-delivery checklist rows 1 and `attribute-schema.json` row |
| R2 | The `.docx` is never hand-authored; it is regenerated from the committed Markdown | `verify_render.py` structural comparison |
| R3 | The `.docx` carries a field-driven Table of Contents that Word refreshes on open | `verify_render.py` TOC and `updateFields` checks |
| R4 | Every section heading starts a new page | `verify_render.py` page-break check |
| R5 | No credential-shaped value reaches the document | `verify_render.py` secret scan; `tests/test_skill_contracts.py::test_no_credentials_committed` |

## Structure

| ID | Requirement | Verified by |
|---|---|---|
| R6 | Section order follows the canonical template | Architect agent contract table; reviewer |
| R7 | `<Frontend> and Backend Architecture (Observed)` is a body section near the front, not an appendix | `test_template_puts_architecture_in_front_and_dictionary_at_back` |
| R8 | The attribute dictionary is Appendix A and open items are Appendix B, both at the back | same test |
| R9 | `Cross-Cutting Attributes and Baggage Propagation` is present as a top-level section | `test_cross_cutting_section_is_mandatory_everywhere` |
| R10 | That section carries the attribute-set table and all five code subsections | `test_cross_cutting_reference_carries_all_five_code_subsections` |
| R11 | The stamp processor iterates an explicit key allowlist | same test (`const KEYS`) |
| R12 | A missing-evidence section keeps its heading and states **Not in evidence** | Architect agent doctrine; reviewer |

## Content

| ID | Requirement | Verified by |
|---|---|---|
| R13 | One `BT:` heading per business transaction with exhaustive dotted-kebab workflows | Completeness bar; reviewer |
| R14 | Every use case has span events, metrics, a dashboard panel list, detectors, and a labelled join | Completeness bar; reviewer |
| R15 | Every join is labelled continue trace, span link, or attribute pivot | Completeness bar; reviewer |
| R16 | Dimension-eligible and attribute-only lists are stated with a cardinality rationale | Completeness bar; reviewer |
| R17 | The PII deny list is byte-identical to `deny` in `attribute-schema.json` | Pre-delivery checklist row; reviewer diff |
| R18 | Every exit criterion in the phase plan is a query a TAM can run | Reviewer |
