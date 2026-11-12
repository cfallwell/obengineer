# Outcome metrics

Every rate publishes numerator, denominator, and measurement coverage. A percentage alone
is not an outcome record.

```text
rate = misses / (met + misses)
measurement_coverage = (met + misses) / eligible_opportunities
```

`unmeasurable` lowers coverage and is neither a pass nor a miss. Human-approved
unremediable criteria are absent from machine result rows and metric denominators; they
remain in the human exclusion/notification record.

| Metric | Miss numerator | Eligible denominator | Collection point |
|---|---|---|---|
| Schema miss rate | Distinct `(contract commit, work order, repository, attribute key)` opportunities absent from accepted schema | All decidable custom-attribute opportunities introduced or changed by the work order | Layer-1 schema check before implementation merge |
| Dimension miss rate | Distinct `(first apply, panel, dimension key)` checks where the required dimension is absent/unindexed and empties the query | All decidable dimension-dependent panel/key checks reaching their first representative verification window | First `/ob-verify` after manual Terraform apply |
| Detector disarm rate | First-armed detectors later changed enabled→disabled for `threshold-invalid`, `signal-untrusted`, or `noise` | All detectors first armed in the cohort and completing the agreed window | Terraform apply/state record plus next verification |
| Not-in-evidence reversal rate | Accepted `not_in_evidence` claims later proven present | All decidable, nonexcluded claims reassessed | Stable unresolved ledger IDs rechecked by `/ob-verify` |

Opportunities have stable IDs and are deduplicated before aggregation. Results and
opportunities are appended to `provenance-ledger.json`; public GitHub issues contain only
anonymized aggregates.
