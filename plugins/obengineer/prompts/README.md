# obengineer run contracts

Commands are short entry points. These prompts own the ordered run behavior.

| Stage | Command | Prompt | Result |
|---|---|---|---|
| Inputs | `/ob-start` (first run) or `/ob-analyze` (reruns) | [00](00-load-obconfig.md) | Secure local config validation, full artifact hash, redacted summary, and digest-bound proceed gate |
| Analysis | `/ob-analyze` (dispatched by `/ob-start`, or rerun directly after editing inputs) | [01](01-analyze-application.md) + [02](02-build-instrumentation-wiki.md) | Immutable `[V<N>]` linked analysis, versioned wiki, and all work orders in one PR |
| Implement | `/ob-implement` | [03](03-implement-instrumentation.md) | One Ready work order across mapped repository legs |
| Terraform | `/ob-terraform` | [04](04-generate-observability-as-code.md) | Import-aware plan; never apply |
| Verify | `/ob-verify` | [05](05-verify-accepted-contract.md) | Read-only accepted exit-criterion results |

Analysis runs Prompt 02 before review. There is no separate generate step. The reviewed
analysis PR already contains the full proposed work-order queue.

Acceptance is an explicit `yes` after PR review. The agent binds it to a deterministic
content digest, marks eligible work orders Ready, and merges only with that authorization.
The human never copies a commit SHA or provides a name.

The final analysis response contains one host-native documentation link followed by concise
next steps. It never starts a browser or localhost server and never pastes the analysis
into chat.
