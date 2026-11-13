# CDN RUM injection references

Each file here shows how to inject the Splunk Browser RUM agent at one CDN's edge so the
agent is the first script in `<head>` on every HTML response. The analysis links the
matching file from `architecture.frontend.cdnDelivery.guidance`; the load-order check and
the recommendation rules live in [`../rum-delivery.md`](../rum-delivery.md).

| CDN | `cdn` value | Reference | Status |
|---|---|---|---|
| Fastly | `fastly` | [`fastly.md`](fastly.md) | Available — reference implementation |
| Akamai | `akamai` | — | Pending; to be added later |
| Cloudflare | `cloudflare` | — | Pending; to be added later |
| Amazon CloudFront | `cloudfront` | — | Pending; to be added later |
| Azure Front Door | `azure-front-door` | — | Pending; to be added later |
| Google Cloud CDN | `google-cloud-cdn` | — | Pending; to be added later |

Until a CDN has its own file, cite `skills/references/cdn/README.md` as the guidance and
adapt the Fastly structure. Use `skills/references/rum-delivery.md#cdn-delivery` for
`other`, `none`, or `unknown`.

## How to add a CDN reference

Name the file `<cdn value>.md` (for example `cloudflare.md`), add it to the table above,
and replace the pending text for that CDN in [`../rum-delivery.md`](../rum-delivery.md).
Mirror the sections of [`fastly.md`](fastly.md) so engineers find the same thing in the
same place:

1. **Header** — the CDN and injection mechanism, a link back to this index, and a
   placeholder table. Every customer value is a placeholder (`<site-host>`, `<realm>`,
   `<rum-access-token>`, `<application-name>`) taken from the customer's environment.
2. **Purpose and decision** — why edge injection, the split of responsibility between the
   CDN control plane, the injection point, and origin cleanup, and why this mechanism is
   the default over the alternative.
3. **Where to inject** — host and path families that receive the snippet, and those that
   must not.
4. **Target bootstrap behavior** — load point, `applicationName`, sampling, recorder mode,
   kill switch, and agent version pin.
5. **Architecture** — request flow, first-party paths with cache TTLs, and why flags stay
   out of cached HTML.
6. **Conflicts to check** — existing CDN behavior (shielding, compression, streaming, WAF,
   image optimization, redirects) and the rule for each.
7. **Control plane summary** — every configuration object, rule, or script with its type
   and order, plus cookie overrides.
8. **Origin changes** — the `<head>` hook and removal of any bundled init.
9. **Security, privacy, and CSP** — token storage, logging, CSP additions, replay masking.
10. **Rollout** — draft, verify, canary, ramp, kill-switch drill, success criteria, and
    rollback.
11. **Alternative mechanism** — when the default cannot be used.
12. **Appendix A: exact implementation** — prerequisites, step-by-step configuration with
    paste-ready code blocks, verification commands, troubleshooting table, activation
    checklist, and rollback commands.
13. **Appendix B: out of scope** — properties and follow-ups the reference does not cover.

Never include a real token, realm, organization id, host, or customer name.
