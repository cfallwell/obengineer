# Critical findings — the review view that must not be buried

Authoring spec for the versioned `findings/` review area defined by
[`analysis-site.md`](analysis-site.md) and represented on the landing page.

A scan of a real application finds things nobody asked about: a credential reachable from
the browser, a consent gate that resolves after the first beacon, an endpoint that answers
without authentication, a trace boundary that breaks so quietly the resulting dashboard
looks healthy. These are the highest-value output of the whole engagement, and they are the
easiest to lose — they arrive as a side effect of looking for something else, so they get
written down where they were found, which is page 180 of an instrumentation document nobody
reads to the end.

**So they get their own landing-page summary and linked review view.** Findings follow the
architecture, technology, and current-telemetry readout and precede the strategy. A reviewer
must encounter them before recommendations or implementation detail.

## What qualifies

The bar is: **a competent engineer on this team, reading this line, would want to act on it
this week.** Not "is it security", not "is it in scope" — would they act.

That admits four classes, and the second and third are the ones people wrongly omit because
they do not feel like security:

| Class | Examples |
|---|---|
| **Exposure** | Credential, token, API key, or private endpoint reachable from client code or an unauthenticated response. Signed URLs with no expiry. An internal hostname in a public bundle |
| **Privacy** | PII in telemetry, in a URL, or in `localStorage`. Consent resolving after data is sent. A third party receiving more than its purpose requires. A session-replay tool recording an unmasked payment field |
| **Correctness that misleads** | A signal that is *wrong in a direction that reads as healthy*: 404 content served under HTTP 200 so error rate looks fine, a broken propagation boundary that turns one journey into two clean-looking traces, a duplicate agent double-counting conversions |
| **Availability and resilience** | A single point of failure the diagram shows and nobody named, a retry storm with no backoff, a DLQ with no consumer, a synchronous call to a third party on the checkout path with no timeout |

Ordinary instrumentation gaps do **not** belong here. "RUM has no identity attribute" is the
subject of the whole document; promoting it to a critical finding devalues the section, and
a section that cries wolf gets skipped exactly like a page-180 paragraph.

## Severity, confidence, OWASP class, and priority

Four levels, and the definition is about consequence and time, not about how alarming it
sounds:

| Severity | Definition | Placement |
|---|---|---|
| **Critical** | Exploitable or exposing now, with no compensating control. Assume it is known to someone outside the team | P0 recommended fixes and the phased plan by finding id |
| **High** | Real exposure or a materially misleading signal, but gated by something — an authenticated path, a low-traffic surface, a partial control | P0 when confirmed or high confidence; otherwise the earliest owned phase |
| **Medium** | Wrong and worth fixing, with bounded blast radius. It will cost an investigation later | Scheduled remediation path |
| **Low** | Hygiene. Record it so it does not get rediscovered as new every run | Reference/open items |

Order the findings index by severity descending. Never by discovery order or source page —
a reader scanning for the worst thing should find it in the
first table row.

Confidence is `confirmed`, `high`, `medium`, or `low` and describes the evidence, not
the consequence. Record the finding class (`exposure`, `privacy`, `misleading signal`,
`availability`, or `security vulnerability`), the applicable OWASP Top 10:2025 and OWASP
API Security Top 10:2023 categories, and remediation priority (`P0`, `P1`, `P2`, or
`backlog`). Every confirmed or high-confidence vulnerability is P0.

**P0 is not observability Phase 0.** P0 is remediation urgency. Phase 0 is the work that
establishes signal trust. A security fix may be P0 even when telemetry is already trusted.

## Shape

Open with the summary table, so the whole picture fits on one page:

```markdown
| # | Severity | Confidence | Priority | Finding class / OWASP | Finding | Exposure | Owning surface |
|---|---|---|---|---|---|---|---|
| F-01 | Critical | confirmed | P0 | Exposure / A02:2025, API8:2023 | Third-party API key served in the boot bundle | Any visitor; key grants <scope> | `apps/web/boot/config.ts` |
| F-02 | High | high | P0 | Privacy / A01:2025 | Consent resolves 1.8s after the first RUM beacon | EU visitors; <n> attributes sent pre-consent | RUM init order |
```

Stable ids (`F-01`) matter more than they look: the phased plan, the work order appendix, the
wiki note, and the customer's own ticket all need to refer to the same finding six months
later, and "the one about the key" does not survive a reorganisation.

Then **one linked detail page per finding**, with all six parts and in this order. The order is the argument:
what happened, where, who can reach it, what it costs, what to do, how to know it worked.

1. **Observed** — what was measured, with the evidence. A request and its response shape, a line of bundle output, a timing pair. Not an inference presented as an observation.
2. **Files and surfaces involved** — the specific path, bundle, route, endpoint, queue, or configuration key. If the exact file is unknown, say which artifact contains it and what would locate it. "Somewhere in the front end" is not a finding anyone can pick up.
3. **Exposure** — who can reach it and what it grants. Be concrete about the boundary: any visitor, any authenticated user, any employee with read access to the log index, the third party itself. Name the scope of what the exposed thing can do, because "an API key" is not a severity until you know whether it reads a public catalogue or writes orders.
4. **Risk if unaddressed** — the consequence in the customer's terms, and the second-order one. A leaked key is a bill and a takedown; PII in a log index is a retention-period problem that grows every day the log is retained, which is why the clock matters.
5. **Remediation path** — numbered concrete steps, in the order they can actually be done, distinguishing the **stop-the-bleeding** step from the **structural** one. Rotating a key is not the fix; moving the secret server-side is. Say both, and say which comes first. If the structural fix needs a decision the team has not made, name the decision and give the interim control.
6. **Verification** — how anyone confirms the fix, as something runnable: a request that should now fail, a bundle grep that should return nothing, a Tag Spotlight view that should show the attribute, a search that should return zero results.

## Handling a credential you find

**Record the finding. Never the value.** Not in the document, not in the wiki, not in a
commit message, not in a scratch file, not quoted in a chat summary.

Write the identifier and the shape — "a Google Maps browser key, `AIza…` prefix, in
`config.runtime.json` served from the CDN" — which is enough to locate and rotate it and not
enough to use. If a value has already been written somewhere in this session's output,
removing it from the file is not sufficient; say so in the finding, because it is in history
now and rotation is the only remedy.

The same rule covers the reverse direction: a finding never instructs anyone to paste a
credential into a follow-up run to "confirm" it.

## Where findings go afterwards

A finding is not done when it is written. It has these destinations:

- **The strategy and implementation path**, by id, for every confirmed or high-confidence
  vulnerability. The row names containment, structural repair, trigger, and verification.
- **A Phase 0 work order or later phase**, by id, when the finding blocks signal trust or
  implementation. A documented exposure with no schedule is documented, not addressed.
- **A wiki note** under `findings/`, so the next run knows it existed and can report it as still-open, fixed, or regressed rather than discovering it again as new. See [`agent-wiki.md`](agent-wiki.md).
- **`Changes in V<N>` on the next landing page**, with its current state. A finding that
  silently disappears between versions is the worst outcome available: the reader cannot
  tell whether it was fixed or dropped.

## Warning signs

- **A critical findings section with nothing in it and no statement of what was checked.** Either the scan was shallow or the section is decoration. Name the classes examined and the result.
- **Every finding is Medium.** Severity that never varies is not severity, and it means nobody decided.
- **A finding whose remediation is "review this".** Review is what produced the finding. The remediation is what changes.
- **The word "potential" doing load-bearing work.** Either it is reachable, or it is reachable under a condition you should name.
- **A finding that only makes sense to the person who found it.** It will be read by someone triaging forty items, cold, on a Monday.
- **The same finding duplicated inside a use case as a caveat.** One authority. The
  finding detail owns it; use cases reference its id.
