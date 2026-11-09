# Outcome issues

Reusable defect outcomes are opened or updated in
[`cfallwell/obengineer`](https://github.com/cfallwell/obengineer/issues).

Public repositories still require authenticated write access to create or update an issue.
Use an existing authenticated `gh` session. Never accept a token on the command line and
never add GitHub credentials to engagement inputs.

If `gh auth status` fails, stop before publishing and give the human:

```text
gh auth login --web --hostname github.com
https://github.com/login/device
```

After login, rerun the same previewed publish command.

## Public payload

Allowed:

- canonical reference or rubric row;
- obengineer specification commit;
- outcome/defect class;
- aggregate numerator, denominator, and coverage;
- generic consequence code;
- proposed canonical change;
- stable deduplication marker.

Forbidden:

- customer name or person name;
- production URL, tenant or account id, org id, repository name, or customer taxonomy;
- engagement commit, artifact link, raw query, payload, or credential.

The stable marker is SHA-256 of canonical reference, outcome class, and defect class.
Search open and closed issues for it. Update the matching issue; otherwise create one.
Always show the sanitized title/body preview first; publication requires the exact
human-approved preview SHA-256 in a later invocation. Supply engagement-derived customer,
application, tenant, repository, and taxonomy terms as local `deny_terms`; none are
published. Before writing, the helper verifies `spec_commit` exists in
`cfallwell/obengineer`. The helper is
`skills/instrumentation-verify/scripts/publish_outcome_issue.py`.
