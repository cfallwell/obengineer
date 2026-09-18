# Architecture review — 18 Sep 2026

A review of obengineer as it stands, and answers to the questions raised with it. Written
from the reviewer's seat: what is now true, what was wrong and is fixed, and what should
happen next with enough specificity to be argued with.

Companion reading: [`../design.md`](../design.md) for why the layout is shaped this way.

---

## What changed in this pass

| Change | Why it mattered |
|---|---|
| One name, `obengineer`, in every identifier | Two spellings become two marketplace entries, and a skill whose name changes on merge breaks every prompt that referenced it |
| Human-supplied inputs in one file | Placeholders inside prompts were pasted unfilled, drifted between runs, and vanished with the session |
| Baggage and cardinality given budgets | "Keep cardinality low" loses every argument with a team that wants to group by order id; 2,400 new time series does not |
| An installer and five commands | The clipboard was the runtime; the copy that ran was not the copy under review |
| A Terraform run at three persona levels | A contract specifying fifty objects was a document until someone configured them by hand |
| Agent files reduced to routers | The architect agent was 7,214 words loaded on every run, most of it duplicating references it also linked to |
| One authority for the section list | **This one found a real defect.** See below. |
| A grader separate from the author | The checklist was being filled from intent rather than from the document |

### The defect worth dwelling on

The architect agent required 23 document sections. The canonical template listed 16. The
agent reconciled them with a sentence saying the other seven "go where they belong".

That is not a specification, and the consequence was concrete: a run could omit Course of
action, Missing portfolio components, RUM SPA route changes, Custom meters, Splunk portfolio
mapping, the phased plan, or the non-goals — and still believe it had followed the template,
because the file it was told was authoritative did not mention them.

The interesting part is not the gap. It is that the gap was **invisible while both documents
were long**. Nobody diffs a 526-line agent file against a 330-line template. Removing the
duplication is what surfaced it, which is the strongest available argument for the principle:
one authority per fact is not tidiness, it is the only way disagreements become visible.

There is now a test asserting the section list appears in exactly one file.

---

## Baggage: how to decide what to carry

Full treatment in [`../skills/references/baggage-budget.md`](../../skills/references/baggage-budget.md).
The reasoning, briefly, because it is the question with the most expensive wrong answer.

Baggage is paid for in four places simultaneously: bytes on every hop of every request, a
shared per-request header ceiling it competes for with cookies and `Authorization`, message
attribute slots (Amazon SQS allows ten per message, and trace context plus baggage takes
three), and — if stamped — span attributes across the entire estate.

None of that is alarming for a small set. All of it is ugly at fifteen keys, and the failure
is not a clean error: it is an intermittent rejection from one proxy in one region, weeks
after the change shipped, presenting as an instrumentation bug.

**The budget:** six keys, 512 bytes total, 64 bytes per value, enforced in `setBaggageEntry`
rather than documented.

**The five tests.** A key earns a place only if all five hold:

1. It is needed on spans that do not already know it.
2. The receiver cannot derive it. This eliminates more candidates than the other four combined — region, environment, service version, route, and a tenant already in a JWT the service parses anyway are all derivable, and a Collector transform costs zero header bytes.
3. A **named** dashboard variable, detector `group by`, or documented pivot reads it. "It might be useful" is how six keys become twenty, and nobody ever removes one, because removal means proving a negative across an estate.
4. It is bounded and stable for the request's lifetime. A value that changes mid-request produces spans in one trace that disagree, which is worse than absence: an absent key is a known gap, an inconsistent one is a wrong answer.
5. It is safe in plaintext, in an access log, and at a third party — because baggage is all three, one CORS misconfiguration away.

**Give the rejections somewhere to go**, or they come back as an argument. Tier 2 is
path-scoped propagation: injected at one boundary, carried along one call chain, so the cost
is paid only by requests that benefit. That is the right home for almost every "we need this
in the checkout flow" request. Tier 3 is joined at query time — continue trace, span link,
attribute pivot, or log correlation.

**And the distinction that keeps the set small:** carrying, stamping, and promoting to a
metric dimension are three separate decisions with three separate budgets. The propagator
decides what crosses the wire; the `onStart` allowlist decides what lands on spans; the
cardinality budget decides what becomes a dimension. Conflating them is the mechanism by
which a set of six becomes a set of twenty.

Correlation is never a reason for baggage. That is what `trace_id` is for.

---

## Multi-agent: what to parallelize, and what must stay serial

Yes to parallelism, but the axis matters more than the fact of it, and the naive version
breaks the thing this bundle exists to protect.

### What genuinely parallelizes

| Work | Fan-out | Why it is safe |
|---|---|---|
| Front-end scan, diagram-driven backend map, existing-portfolio inventory | Three subagents, within run 1 | Independent evidence sources; none names anything |
| Per-journey use-case drafting | One subagent per ranked flow, within run 2 | Each drafts against an **already-fixed** attribute dictionary |
| Per-language shared-library sections | One per language in scope | Same contract, different SDK |
| Implementation slices in different repositories | One per repository, run 3 | Different code owners, different review queues |
| Run 3 and run 4 | Concurrent | Instrumentation lands in repositories, configuration lands in a tenant |

### What must not

**Naming is a serial section, and the attribute schema is the lock.** Two agents drafting
use cases concurrently will invent `order.id` and `orderId` for the same concept, or promote
the same tag to a dimension twice and double-count the MTS budget. The contract exists
precisely to prevent that, so parallelizing the part that creates names defeats it.

The rule: **fan out to gather and to draft; serialize to name.** Concretely, the dictionary
and the schema are written once, by one agent, before any per-journey fan-out begins. A
subagent that needs a key that does not exist returns a request for it rather than creating
it.

### Handoffs: make the gate a predicate, not a person

The current gates are not bureaucracy — two of them are where the human's judgment is
genuinely load-bearing, and one is not:

| Gate | Keep it human? |
|---|---|
| Analysis → guide | **No.** The question is "is the analysis complete", which is mechanical: the checklist passes and no open item blocks a decision. |
| Guide → implement | **Yes.** "Will we implement this?" is a commitment, and implementing an unaccepted contract spends engineering trust that does not come back. |
| Guide → configure | **Yes**, same reason, plus it touches a tenant. |
| `terraform plan` → `apply` | **Yes**, always. |

So: auto-handoff where the gate is a predicate the run can evaluate about itself, human gate
where the gate is a commitment. Run 1 should proceed into run 2 automatically when
`$deliverable-review` passes and no open item is marked blocking, and stop with the specific
question when it does not.

### The bigger prize is context isolation, not speed

A subagent that reads a 4 MB bundle and returns thirty lines of findings keeps the 4 MB out
of the parent's context. That is worth more than the wall-clock saving, and it is the same
mechanism as the context-window answer below.

### What handoff needs that does not exist yet

A machine-readable state file. Each run should write `run-state.json`: what it produced,
what it asserted with what provenance, what it could not answer, and its checklist result.
Today run 2 re-derives from run 1's prose, which is both expensive and lossy — an assertion
in a paragraph has no provenance, so run 2 cannot tell a measurement from an inference.

---

## Context engineering

### Done in this pass

- **Agent files route.** 7,214 words to 1,709 for the architect, with a 2,500-word cap and a test. Depth moved to references that are read per language and per step rather than per run.
- **One authority per fact**, tested. The section list, the decision engine, the platform expertise, and the layout spec each live in exactly one file.
- **Prompts are no longer pasted.** Previously the prompt was pasted *and* the agent file loaded, so the same doctrine arrived twice.
- **Inputs are structured.** A YAML file the run reads specific fields from, rather than a paragraph it has to interpret.

### Next, in order of value

1. **Slice the guide for implementation.** Run 3 currently reads a 20,000-word contract to find one workflow's spec. Emit `workflows/<name>.md` per workflow at the end of run 2, and have run 3 load one slice plus the schema. The full guide stays the customer artifact; the slices are the implementer's interface.
2. **An evidence ledger.** `evidence.json`, one record per measurement: what was observed, where, when, and by which method. Claims in the deliverable cite records. This makes provenance survive the handoff, kills the "was that measured or inferred" question, and lets a re-run check the claim instead of re-deriving it.
3. **Conditional loading, stated in the skill.** Skills should say "read the messaging reference only if `backends.buses` is non-empty". Right now a Go API with no browser still pulls front-end material into context.
4. **Cap `SKILL.md` length, with depth in references.** The description limit is already tested; the body is not. The renderer skill is 190 lines and is the outlier worth watching.
5. **Structured outputs where prose is not the product.** The dictionary, the detector catalogue, and the dimension lists are tables that later runs parse. Emitting them as JSON alongside the Markdown removes a re-parsing step and a class of transcription error.

### What to shrink, with numbers

| Cost | Before | Now | Next |
|---|---|---|---|
| Architect agent, loaded every run | 7,214 words | 1,709 | — |
| Prompt, previously pasted alongside it | ~1,100 words duplicated | 0 | — |
| Implementer's view of the contract | The whole guide | The whole guide | One workflow slice plus the schema |
| Front-end evidence in the parent context | The full bundle | The full bundle | Subagent returns findings only |
| Platform expertise | Always loaded | Loaded when the language is in scope | Gated by an explicit condition |

Two anti-patterns to avoid while chasing this. Do not compress by deleting the reasoning:
a rule without its reason gets argued with in every engagement, and re-arguing it costs more
than the tokens saved. And do not summarize references into the agent file "for convenience"
— that is exactly how the 7,214 words accumulated, one convenience at a time.

---

## Reinforcement learning: build the grader first

There is no fine-tuning loop available here, and proposing one would be the wrong answer.
What *is* available is everything RL needs before it becomes possible, and each piece is
useful on its own — which is the only honest reason to build it.

**1. An executable rubric.** Done: [`../skills/deliverable-review/SKILL.md`](../../skills/deliverable-review/SKILL.md).
The completeness bar was already a rubric; it was just being applied by the author, from
memory. A grader separate from the author is the reward function, and it has value with or
without any learning attached.

**2. Outcome signal from the next phase.** The strongest signal is not whether the document
looked complete but whether it survived contact with implementation. Four measurements, all
cheap and all diagnostic:

| Metric | What it indicts |
|---|---|
| **Schema miss rate** — attributes added during implementation that the contract lacked | The analysis missed a journey, or the dictionary was written too early |
| **Dimension miss rate** — dashboard panels empty on first apply | A `group by` was specified on a key that never became a dimension |
| **Detector disarm rate** — detectors armed then turned off | Thresholds were invented rather than baselined |
| **`Not in evidence` reversal rate** — sections marked absent that turned out to exist | The scan was too shallow, and the checklist rewarded the heading over the work |

**3. Preference data, for free.** The diff between the generated document and the one the
customer accepted is the highest-quality signal available, and it is currently discarded.
Store it. Every human edit is a labelled correction.

**4. The learning step, today, is editing the specification.** A defect class that recurs
across three engagements is not an author problem — it is a reference that fails to prevent
it. That is why `$deliverable-review` reports defects **by rubric row**: the aggregate points
at the file to fix. This is slower than gradient descent and it compounds in the same
direction.

**5. If real RL is wanted later**, the grader, the trajectories, and the preference diffs are
the dataset. Building them is the prerequisite either way, so start there and decide later.

---

## Closing the loop: analysis → recommendation → implementation → verification

The pipeline is currently open-ended. Four runs produce a contract, code, and configuration,
and then **nothing checks whether the tenant now answers the questions the contract
promised**. That missing edge is why it is a pipeline rather than a loop.

### Add run 5: verify

The mechanism already exists, because the phase plan's exit criteria were deliberately
written as queries a TAM can run: Tag Spotlight shows the tag, a test trace crosses every bus
with one `trace_id`, a platform search by `trace_id` returns the log, a ThousandEyes test
covers the public path. Run 5 executes them against the tenant through the MCP servers
already described in `.mcp.optional.json`, and reports met, unmet, or unmeasurable.

Its output is what makes the loop turn:

| Verify result | Feeds |
|---|---|
| Exit criterion unmet, instrumentation missing | The next slice for run 3 |
| Exit criterion unmet, configuration missing | The next plan for run 4 |
| Criterion unmeasurable | An open item, and a correction to the criterion — an exit criterion nobody can check should never have shipped |
| A finding contradicting the contract | An **amendment** to the guide, versioned, not a rewrite |
| The four outcome metrics above | The engagement's outcome record, and the aggregate |

### Amend, do not rewrite

A rewritten contract loses the customer's acceptance and restarts the review. So the guide is
versioned, amendments are appended with a changelog, and the `.docx` is re-rendered from the
amended Markdown — which the render pipeline already guarantees cannot disagree with it.

### Two kinds of drift, two detectors

- **Configuration drift.** `terraform plan` on a schedule, in the existing tree. Non-empty plan means someone changed a dashboard or detector by hand, which is worth knowing before it is worth arguing about.
- **Instrumentation drift.** Does every attribute in `attribute-schema.json` still appear on spans? A service refactored without its stamp processor fails silently, and the symptom shows up months later as an `UNKNOWN` bucket in a dashboard nobody trusts any more.

### What this becomes

Five runs with two human gates and one predicate gate: intake and analysis proceed
automatically; a human accepts the contract; implementation and configuration run in parallel;
verification closes the loop and schedules the next slice. Each cycle narrows the gap between
what the contract promised and what the tenant can answer, and each cycle emits the four
metrics that say whether the previous one was any good.

---

## Open questions for the humans

1. **Should intake ask for entitlement, or read it?** An MCP server could read subscription usage directly, which is better data and one less thing to ask. It also needs a token with more scope than a documentation run should hold. Worth a decision rather than a default.
2. **Where do outcome records live?** They are cross-engagement by nature and customer-specific by content. A shared aggregate with anonymised defect classes is probably right, but "probably" is not a policy.
3. **How many personas is right?** Three is defensible and product managers will ask for a fourth. The answer should be a rule — a persona exists when it *excludes* something the others include — not a count.
4. **Does run 5 get write access to a tenant?** It needs read to verify. It does not need write, and it should not have it, but somebody will ask for auto-remediation and the refusal should be written down before it is requested.
