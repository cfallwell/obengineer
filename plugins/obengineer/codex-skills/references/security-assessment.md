# Security assessment during analysis

This reference owns the security screening performed by `instrumentation-analyze`.
It is an evidence-driven review of the application surfaces already in analysis scope,
not a penetration test and not authorization to attack production.

## Standards and sources

Use these released editions until a later edition is explicitly adopted and tested:

- [OWASP Top 10:2025](https://owasp.org/Top10/2025/)
- [OWASP API Security Top 10:2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)

Record both editions in document control. Do not silently substitute an older list or
claim full coverage where evidence was unavailable.

## Authorization modes

`security_assessment.mode` in `engagement-inputs.yaml` controls requests:

| Mode | Permitted |
|---|---|
| `passive` | Source, configuration, dependency metadata, supplied artifacts, browser/runtime observation, and requests the normal application flow already makes. Default. |
| `safe-active` | Passive checks plus non-mutating requests to explicitly authorized origins and paths, within the supplied request and rate limits. |
| `none` | No security screening beyond redacting credential-shaped values encountered incidentally. Record the opt-out and its owner. |

Never mutate state, brute force, bypass a tenant boundary, submit destructive forms,
run load, exploit a vulnerability, enumerate another user's objects, or fuzz production.
An observation that would require one of those actions is **Not in evidence** and names
the safe test environment or owner needed to settle it.

## Required coverage

### Exposed credentials and sensitive data

Check source, built bundles, source maps, runtime configuration, HTML, URLs, response
headers and bodies, browser storage, telemetry payloads, logs supplied as evidence, and
repository history available in the authorized checkout for:

- API keys, tokens, passwords, private keys, signed URLs, and inline credentials;
- privileged internal endpoints, hostnames, debug routes, and administrative metadata;
- PII, payment data, session identifiers, and authentication material in URLs,
  browser storage, telemetry, or logs.

Record a credential by type, prefix/shape, location, exposure, and scope. Never reproduce
the value. If a value reached a generated artifact or git history, removal is insufficient:
the finding requires revocation or rotation.

### API inventory and exposure

Build an API inventory from routes, schemas, clients, gateways, captured traffic, and
diagrams. For every API family in evidence, assess:

- authentication and session enforcement;
- object-, property-, and function-level authorization;
- CORS, transport security, cache behavior, and exposed versions/debug endpoints;
- request validation, injection boundaries, SSRF sinks, and unsafe third-party data;
- pagination, rate limits, resource limits, and sensitive business-flow automation;
- inventory ownership, supported versions, and decommissioned endpoints.

Do not infer safety from an endpoint returning `401` once. State what identity, object,
method, and role were actually observed.

### OWASP Web Top 10:2025

The coverage matrix has one row for every category:

1. A01 Broken Access Control
2. A02 Security Misconfiguration
3. A03 Software Supply Chain Failures
4. A04 Cryptographic Failures
5. A05 Injection
6. A06 Insecure Design
7. A07 Authentication Failures
8. A08 Software or Data Integrity Failures
9. A09 Security Logging and Alerting Failures
10. A10 Mishandling of Exceptional Conditions

### OWASP API Security Top 10:2023

The coverage matrix also has one row for every API category:

1. API1 Broken Object Level Authorization
2. API2 Broken Authentication
3. API3 Broken Object Property Level Authorization
4. API4 Unrestricted Resource Consumption
5. API5 Broken Function Level Authorization
6. API6 Unrestricted Access to Sensitive Business Flows
7. API7 Server-Side Request Forgery
8. API8 Security Misconfiguration
9. API9 Improper Inventory Management
10. API10 Unsafe Consumption of APIs

## Coverage matrix

The Findings index begins with:

```markdown
| Standard/category | Surfaces checked | Evidence | Result | Finding |
|---|---|---|---|---|
| OWASP Top 10:2025 A01 | <routes, policy, tests> | <measured or unavailable> | not found | — |
| OWASP API:2023 API1 | <API families and object operations> | <measured or unavailable> | high confidence | F-03 |
```

Allowed results are `confirmed`, `high confidence`, `medium confidence`,
`low confidence`, `not found`, `not in evidence`, and `not applicable`.
`not found` means the named checks ran and found nothing. `not in evidence` means the
run could not perform the check and states what would settle it. `not applicable`
requires a reason.

## Finding and priority routing

Severity describes consequence. Confidence describes evidence. Priority describes
remediation order. Keep all three separate.

- Every `confirmed` or `high confidence` vulnerability is a Critical Finding,
  regardless of whether it is primarily security, privacy, availability, or integrity.
- Every such finding appears in the strategy's P0 remediation summary and links its
  work order.
- A medium- or low-confidence hypothesis goes to open items unless independent evidence
  makes it actionable; do not present it as an exploited vulnerability.
- `P0` is remediation priority and is distinct from observability **Phase 0**, which
  establishes signal trust.

Each P0 row contains finding ID, immediate containment, structural repair,
deadline/trigger, and runnable verification. The strategy references the finding detail
by ID and does not duplicate the evidence.

## Non-remediation boundary

The analysis run writes findings and recommended fixes. It does not rotate credentials,
patch source, alter access controls, change API behavior, or deploy. Runtime remediation
requires a separately accepted work order and the owning security/engineering process.
