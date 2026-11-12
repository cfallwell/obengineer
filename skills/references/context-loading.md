# Conditional context loading

Load doctrine by evidence, not by possibility. Absent technology gets no dedicated landing
link or detail page. Record its enabling condition and the evidence needed on Reference /
Suggested additions without loading or emitting irrelevant code.

Record every decision in `provenance-ledger.json` under
`context_profile.predicates` and `context_profile.loaded_references`.

| Predicate | Load |
|---|---|
| Production browser or WebView exists | browser/RUM reference |
| Router evidence exists | only that router's route-change material |
| `backends.languages` contains a language | exactly that language reference |
| `backends.buses` contains a bus | exactly that bus inject/extract reference |
| Deploy target or production inventory identifies a cloud/runtime | exactly that cloud/runtime reference |
| An off-box DNS/CDN/SaaS path exists | ThousandEyes reference |
| ITSI or Enterprise Security is found in tenant evidence | that product reference |
| Logs require trace correlation and direct tenant evidence confirms LOC availability | Log Observer Connect reference |
| Direct tenant evidence confirms replay and separate written acceptance exists | session-replay detail |
| A user-facing canary question exists | Synthetics detail |

Unknown language, bus, runtime, or ownership creates an unresolved ledger entry and a
human question. It does not authorize loading every reference.

The analysis coordinator always loads the analysis-site contract, security assessment,
critical findings, provenance ledger, and accepted cross-cutting attribute-set contract.
Code variants inside cross-cutting sections are conditional: no browser means no browser
bootstrap/login snippet; no IdP means no identity-success snippet; no bus means no
inject/extract snippet. The canonical contract records applicability and the renderer omits
inapplicable pages rather than producing a `Not in evidence` page.

The ledger validator rejects a loaded reference whose predicate is explicitly false.
