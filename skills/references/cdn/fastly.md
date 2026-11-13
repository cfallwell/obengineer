# Fastly: inject Splunk RUM and Session Recording with ESI

This is the reference implementation for injecting Splunk Browser RUM at a CDN edge. It
covers Fastly classic VCL with an Edge Side Include (ESI) in the origin `<head>`. Other
CDN references in [this directory](README.md) follow the same section structure. The
analysis cites this file from `architecture.frontend.cdnDelivery.guidance`; the load-order
check it satisfies lives in [`../rum-delivery.md`](../rum-delivery.md).

Values in angle brackets are placeholders. Take every one from the customer's environment
(Fastly service, Splunk Observability organization, and origin source). Never copy a token
into the analysis, tickets, chat, or exported VCL.

| Placeholder | Meaning |
|---|---|
| `<site-host>` | Public host that serves the storefront HTML, for example `www.example.com` |
| `<application-name>` | Target RUM `applicationName`, matching dashboards and MetricSets |
| `<legacy-application-name>` | `applicationName` the bundled agent reports today, if any |
| `<realm>` | Splunk Observability realm, for example `us1` |
| `<rum-access-token>` | RUM ingest-only access token, stored in a Fastly private dictionary |
| `<prefix>` | Customer prefix for new snippets and cookies, for example `acme` |
| `<base-version>` | Active Fastly service version cloned to the draft |
| `<storefront-backend>` | Generated backend that serves storefront HTML |
| `<default-backend>` | Generated default backend (often a CMS origin) |
| `<highest-condition-backend>` | Backend whose request condition has the highest existing priority |
| `<shield-pop>` | Shield POP configured for the storefront backend |
| `<market-codes>` | Alternation of storefront market path prefixes, for example `us\|ca\|mx` |
| `<other-api-prefixes>` | Additional API path prefixes that must never receive the snippet |
| `<brand>` | Value for the `site.brand` global attribute |

> **Do not rewrite HTML in classic VCL.**
> Fastly VCL can change headers, synthesize whole responses, and process ESI includes. It
> cannot parse or patch origin HTML bodies. Image Optimizer, gzip, shielding, and
> `beresp.do_stream` make a `vcl_deliver` body rewrite even less viable. Configuration
> belongs in VCL; placement in `<head>` belongs to ESI (recommended) or a thin Compute
> `HTMLRewritingStream` in front of VCL.

## 1. Purpose and decision

Inject Splunk Browser RUM and Session Recording instrumentation and configuration at
Fastly rather than compiling them into the storefront bundle. A typical starting point is
an `@splunk/otel-web` agent bundled inside a large main bundle: the first RUM beacon fires
seconds after navigation, session recording is always on, and `applicationName` does not
match the dashboards.

Moving init to the edge fixes three foundation problems at once: RUM becomes the first
script in `<head>`, configuration (sample rates, recorder mode, kill switch) can change
without a storefront deploy, and session recording can follow an on-demand plus sampled
policy instead of 100% replay.

### 1.1 The split of responsibility

| Layer | Where | Job |
|---|---|---|
| Control plane | The Fastly VCL service | Flags, first-party scripts, CSP additions, path allowlist, 10-second ESI fragment for the kill switch |
| Injection | ESI include in the storefront `<head>` (recommended) or Compute HTML rewriter | Place the snippet as the first child of `<head>` |
| Origin cleanup | Storefront and micro-frontends | Remove `SplunkRum.init` / `SessionRecorder.init` from the main bundle so Fastly is the only initializer |

> **Origin still has required work.**
> When RUM already initializes from the storefront bundle, Fastly injection without
> turning that off will double-init (the SDK logs "SplunkRum already init()ed" and late
> beacons still fire). Removing bundle init and always-on replay is not optional even if
> ESI is perfect.

### 1.2 Why ESI, not Compute, is the default

A mature Fastly service is usually a large classic VCL configuration: many backends,
shielding, NGWAF snippets, Image Optimizer, gzip policy, and market-specific cache rules.
Rebuilding that in Compute is unnecessary. ESI is the VCL-native way to splice a short,
independently cached fragment into HTML Fastly already serves.

- The storefront must change anyway to strip bundle init. Adding one ESI include in the
  SSR `<head>` is the smallest extra hook.
- The include is expanded on every HTML response when `beresp.do_esi` is set, including
  cache HITs. Flags live in the fragment (10 s TTL), not in the cached page (for example,
  5 min).
- A kill switch is then a dictionary flip: `rum.client.*` stops within about two minutes
  with no purge of storefront HTML.
- Use Compute `HTMLRewritingStream` only if the product team refuses any origin HTML tag.
  Put Compute in front of the VCL service; do not migrate backends, WAF, or Image
  Optimizer.

## 2. Where to inject

Reuse the existing storefront host and path family. Do not paint the storefront RUM token
onto admin, assets, APIs, or other brands. Build this table from the service's generated
VCL; the rows below show the shape.

| Host / path | Backend today | Inject? |
|---|---|---|
| `<site-host>` `/{cc}/{lang}/…` storefront HTML | `<storefront-backend>` | Yes — primary |
| `<site-host>` `/storefront/client/*` | Storefront | No — JS bundles |
| `<site-host>` `/assets/`, `/sitemap*`, `robots.txt` | Static / sitemap / synthetic | No |
| `<site-host>` object-storage buckets | Object storage | No |
| `<site-host>` CMS paths (`/content`, `/etc`, `/apps`, `/libs`) | `<default-backend>` | No — different application |
| Commerce admin host | Admin backend | No — separate token and app |
| Event or campaign hosts | Their own backends | Later, own `applicationName` |
| Other brands or regional properties | Their own backends | No |
| Content platform host and paths | `<highest-condition-backend>` | Optional phase 2 |

## 3. Target bootstrap behavior

Do not copy the current production init. The edge bootstrap must match safe foundation
defaults.

| Control | Typical bundled state | Edge bootstrap |
|---|---|---|
| Load point | Inside the main bundle; first beacon seconds after navigation | First script in `<head>`, first-party `/__o11y` |
| `applicationName` | `<legacy-application-name>` | `<application-name>` |
| Session recorder | Always on (`enableSessionRecorder=true`) | On-demand + 5% / 1% / 0% by SLA tier |
| `sessionsSampleRate` | 100% | tier1 0.50 / tier2 0.10 / tier3 0.05 |
| Kill switch | Storefront deploy | `rum_controls.enabled` or cookie `<prefix>_rum=off` |
| Incumbent browser agent (for example, Instana) | First in `<head>` | Splunk first; the incumbent remains a separate origin flag |
| Agent version | Old version bundled | Pin a tested v3.x from the Splunk CDN; never `latest` |

Load the core agent synchronously as the first JS resource. Lazy-load
`splunk-otel-web-session-recorder.js` only when a trigger or sample fires. Idle homepage
sessions must send zero `/v1/rumreplay` posts.

The RUM access token is an ingest-only browser credential. It will appear in the synthetic
init JavaScript — that is how Browser RUM works. Store it in a Fastly private dictionary
(`rum_secrets`), not in exported VCL and not in storefront or micro-frontend artifacts.
Rotate it independently of storefront releases.

## 4. Architecture

### 4.1 Request flow

1. Browser `GET https://<site-host>/us/en/…`
2. `vcl_recv` marks `X-Rum-Eligible=1` for storefront HTML and evaluates `<prefix>_rum`
   cookies.
3. Existing VCL picks `<storefront-backend>` (unchanged) and may shield via `<shield-pop>`.
4. On the edge hop only (`fastly.ff.visits_this_service == 0`), `vcl_fetch` sets
   `beresp.do_esi=true` for 200 `text/html`.
5. Fastly expands `<!--esi <esi:include src="/__o11y/esi.html" /> -->`.
6. The include is a subrequest through the same service. `vcl_recv` matches
   `/__o11y/esi.html` and issues `error 802`.
7. `vcl_error` synthesizes a short HTML fragment from `rum_controls` / `rum_secrets`
   (10 s TTL).
8. Browser receives storefront HTML with two first-party `<script>` tags at the top of
   `<head>`.
9. `splunk-otel-web.js` is fetched from Fastly, which proxies and caches Splunk's CDN for
   1 day.
10. `splunk-rum-init.js` is another 802 synthetic. It inits `SplunkRum` and wires
    on-demand recording.

### 4.2 First-party paths

| Path | Source | Cache |
|---|---|---|
| `/__o11y/esi.html` | Synthetic (`error 802`) | 10 seconds, `Surrogate-Key o11y-rum-init` |
| `/__o11y/splunk-rum-init.js` | Synthetic (`error 802`) | 10 seconds, same key |
| `/__o11y/splunk-otel-web.js` | Backend `F_Splunk_O11y_CDN` → pinned v3 agent | 1 day, key `o11y-rum-agent` |
| `/__o11y/splunk-otel-web-session-recorder.js` | Same backend, recorder file | 1 day, same key |

First-party hosting avoids ad-blockers that drop `cdn.observability.splunkcloud.com` and
keeps CSP simpler (`script-src 'self'`).

### 4.3 Why flags must not be baked into cached HTML

Existing fetch logic often caches HTML responses for minutes (and forces some markets
uncacheable). If the init snippet were concatenated into the cached object, disabling RUM
would require a purge of every storefront URL. ESI keeps the page cache warm and puts
enabled / sample rates only in the 10-second fragment.

## 5. Conflicts to check in the existing VCL

| Existing behavior | Risk if ignored | Rule |
|---|---|---|
| Storefront is shielded via `<shield-pop>` | ESI would run at shield and again at the edge | Set `do_esi` and eligibility only when `fastly.ff.visits_this_service == 0` |
| Fetch gzips `text/html` | Broken ESI or double-compressed body | ESI is compatible with gzip. Never also set `beresp.do_stream` on those objects |
| `beresp.do_stream` for wmv/pdf/ppt/mp4 | Streaming disables ESI | Keep streaming for media; never ESI those extensions |
| `Set-Cookie` → pass | Signed-in HTML is uncacheable | Still set `do_esi` on the pass object so cart/checkout get the snippet |
| Markets with `cacheable=false` | None for injection | Injection still works; kill switch is even faster |
| NGWAF calls `edge_security` in miss/pass | WAF may inspect the Splunk CDN fetch | Synthetics never fetch origin. Allow `cdn.observability.splunkcloud.com` |
| Image Optimizer on gif/png/jpg/webp | Wasted rewrite on images | Eligibility regex excludes those extensions |
| `X-Redirect-To` handled in `vcl_deliver` as 302 | Snippet on a redirect body | Do not ESI or add CSP on redirect / synthetic error pages |
| `vcl_log` HEC to Splunk Cloud | Confused with RUM | That pipeline is CDN access logs, not Browser RUM. Leave it unchanged |
| Incumbent agent still first in origin `<head>` | It patches fetch/XHR before Splunk | ESI prepend puts Splunk first. Turn the incumbent's origin flag off after 48 h of coverage |

## 6. VCL control plane (summary)

Add new custom snippets named `<prefix>_rum_*`. Do not edit Fastly-generated blocks
(`#--FASTLY RECV BEGIN` internals, `ngwaf_config_*`, Image Optimizer). Exact paste-ready
snippet text, UI click-path, priorities, and backend condition are in
[Appendix A](#appendix-a-exact-esi-implementation-on-fastly).

| Snippet / object | Type / priority | Change |
|---|---|---|
| `rum_controls` | Dictionary (plain) | enabled, recorder_mode, sample rates, realm, application name, pinned agent version |
| `rum_secrets` | Private dictionary | `rum_access_token` only |
| `F_Splunk_O11y_CDN` | Backend + condition priority 30 | Proxy pinned Splunk CDN files; must win after the highest existing condition (priority 20 in the reference service) |
| `<prefix>_rum_recv` | recv / 110 | Mark `X-Rum-Eligible`; `error 802` for `esi.html` and `init.js` |
| `<prefix>_rum_fetch` | fetch / 110 | `do_esi` on eligible 200 HTML; cache agent JS 1 day |
| `<prefix>_rum_error` | error / 110 | Synthetic fragment + init JS from dictionaries |
| `<prefix>_rum_deliver` | deliver / 110 | Extend the existing `connect-src` for rum-ingest; skip redirects |

### 6.1 Cookie overrides

Use a dedicated cookie. Do not reuse maintenance or debug cookies already in the VCL.

| Cookie | Effect |
|---|---|
| `<prefix>_rum=off` | Hard kill. Fragment is empty. No agent tags. |
| `<prefix>_rum=force` | QA: init even if dictionary `enabled=false` is not set; `sessionsSampleRate=1`. |
| `<prefix>_replay=force` | Support takeover: start session recorder immediately. |

## 7. Origin changes (required)

1. Add the ESI include as the first child of `<head>` in the storefront SSR shell
   ([A.6](#a6-storefront-ssr-change)).
2. Delete `SplunkRum.init`, `SplunkSessionRecorder.init`, and `@splunk/otel-web` from the
   main bundle.
3. Confirm mini-cart and checkout federation builds do not ship `rumAccessToken` or
   `enableSessionRecorder`.
4. On SPA route changes, call `SplunkRum.setGlobalAttributes` for `page.type` /
   `page.sla_tier` only — never init again. ESI does not re-run on client navigations.
5. After 48 hours of Splunk coverage, turn off the incumbent browser agent's origin flag.
6. Align `applicationName` to `<application-name>` and `deploymentEnvironment` to
   `prod | stage | test`.

## 8. Security, privacy, and CSP

- **Token:** Store `rum_access_token` in `rum_secrets` (private). It is ingest-only and
  will be visible to any browser that receives the fragment — treat it as rotatable, not
  as an admin credential.
- **Logging:** Do not log the token in `vcl_log`. Existing HEC log lines often serialize
  many headers; do not add `rum_secrets` to them.
- **CSP:** Allow `script-src 'self'` for `/__o11y`. Allow `connect-src
  https://rum-ingest.<realm>.signalfx.com` and
  `https://rum-ingest.<realm>.observability.splunkcloud.com` (Splunk domain change as of
  March 2026). Session recorder lazy-load typically also needs `worker-src 'self' blob:`.
- **Audit:** Audit the live storefront `Content-Security-Policy` before activation. Extend
  the existing `connect-src` (or the `default-src` it falls back to) in place; a second
  `connect-src` directive is ignored by browsers and does not authorize ingest.
- **Replay:** Session recording captures DOM. Keep `recorder_mode` at `on_demand` or
  `sampled`. Never ship `always`. Mask password and payment fields in recorder config if
  checkout is in scope.

## 9. Rollout

1. Clone service version `<base-version>` to a new draft. Add dictionaries, backend, and
   snippets. Do not activate.
2. On the draft host, `GET /__o11y/splunk-otel-web.js` and `/__o11y/splunk-rum-init.js`.
   Expect 200, 1 day / 10 s cache, no `Set-Cookie`.
3. Storefront UAT: ESI include + bundle init removed. Confirm one `SplunkRum.init`,
   `sf_application=<application-name>`, zero `/v1/rumreplay` on idle home.
4. Activate Fastly on one market first. Compare RUM-on vs RUM-off LCP / INP (gates:
   +50 ms / +20 ms p90).
5. Ramp the remaining markets.
6. Kill-switch drill: set `rum_controls.enabled=false`. Confirm `rum.client.*` stops
   within two minutes in Metric Finder.

### 9.1 Success criteria

- Homepage HTML has the two `/__o11y` scripts as the first JS in `<head>`, before other
  third-party tags.
- First POST to `/v1/rum` p90 < 1000 ms on home (WebPageTest + field).
- The main bundle no longer contains `SplunkRum.init` or `@splunk/otel-web`.
- Idle home: zero `/v1/rumreplay` in 30 s, repeated 10 times.
- Forced JS error or `<prefix>_replay=force` starts the recorder once.
- Dictionary `enabled=false` empties the ESI fragment on the next page view after
  fragment TTL.

### 9.2 Rollback

- Immediate: `rum_controls.enabled = false`, or cookie `<prefix>_rum=off` for a tester.
- Replay only: `rum_controls.recorder_mode = off`.
- Fastly: roll the service version back. ESI comments left in storefront HTML are inert
  when `do_esi` is false.
- Do not re-enable bundle init as the first rollback — that restores always-on replay.

## 10. Compute alternative (not the default)

If the storefront cannot add the ESI include, put a thin Fastly Compute service in front of
the VCL service and stream-rewrite `<head>` with `HTMLRewritingStream` (js-compute 3.35+).
Leave backends, NGWAF, Image Optimizer, and shielding in VCL. Unset `Content-Length` after
rewrite. Still serve `/__o11y` from VCL so flags stay in one place.

*Compute rewriter sketch — only if ESI is refused*

```javascript
import { HTMLRewritingStream } from "fastly:html-rewriter";

const rewriter = new HTMLRewritingStream().onElement("head", (el) => {
  el.prepend(
    `<script src="/__o11y/splunk-otel-web.js" crossorigin="anonymous"></script>
     <script src="/__o11y/splunk-rum-init.js" defer></script>`,
    { escapeHTML: false }
  );
});
// Pipe the VCL service's HTML through rewriter. Do not rebuild the VCL service in Compute.
```

## Appendix A. Exact ESI implementation on Fastly

This appendix is the runbook. Follow it in order on a cloned draft of service version
`<base-version>`. Do not edit live. Do not paste production tokens into tickets, chat, or
exported VCL.

### A.1 How Fastly ESI works (what you are implementing)

Edge Side Includes are an XML-like tag set Fastly can expand while serving HTML. Classic
VCL cannot search-and-replace the body. It can, when `beresp.do_esi` is true, find ESI tags
and replace each include with the body of a subrequest.

Fastly supports a subset: `esi:include`, `esi:comment`, `esi:remove`, `esi:vars`, and
`esi:choose` / `esi:when` / `esi:otherwise`. You only need include + the HTML comment
wrapper.

The comment wrapper is required:

*What the storefront puts in `<head>`. Fastly strips the comment and executes the include.*

```html
<!--esi
  <esi:include src="/__o11y/esi.html" />
-->
```

If `do_esi` is false (ineligible path, shield hop, non-HTML, error status), the browser
sees a normal HTML comment and does nothing. That is the safe fallback for CMS paths,
assets, and non-production origins that are not behind Fastly.

#### A.1.1 Parent request versus ESI subrequest

This is the most common implementation mistake. The include is a new request to the same
Fastly service. It re-enters `vcl_recv` with URL `/__o11y/esi.html`. It does not inherit
`req.http.X-Rum-Eligible` from the parent. It does inherit the client's cookies.

- **Parent request:** decide whether to set `beresp.do_esi` (eligibility, status 200,
  `text/html`, edge hop only).
- **Subrequest:** decide what HTML to synthesize (enabled flag, `<prefix>_rum=off`,
  token). Read dictionaries and cookies here, not the parent header.
- Never set the storefront backend on the subrequest. `error 802` must fire in recv before
  generated backend conditions overwrite routing.

#### A.1.2 Why agent JS cannot use error 802 for routing alone

Custom recv snippets run inside `#--FASTLY RECV BEGIN` before the generated backend
conditions. Those conditions default the backend to `<default-backend>` and then override
it (for example, storefront priority 10, `<highest-condition-backend>` priority 20). A recv
snippet that sets `req.backend = F_Splunk_O11y_CDN` will be overwritten.

Therefore: `esi.html` and `splunk-rum-init.js` use `error 802` (immediate synthetic —
never reaches backend selection). The two Splunk agent files use a Fastly Request
Condition attached to `F_Splunk_O11y_CDN` at priority 30 so it wins after priority 20.

### A.2 Prerequisites

- Fastly role that can edit the service, create dictionaries, backends, conditions, and
  VCL snippets, and activate versions.
- Splunk Observability realm `<realm>` RUM access token (ingest-only). Separate UAT and
  production tokens if possible.
- Pinned agent version from
  [splunk-otel-js-web releases](https://github.com/signalfx/splunk-otel-js-web/releases) —
  test v3.x in UAT. The examples below use `v3` as the major pin.
- Storefront change window for the `<head>` include and removal of bundle init.
- A draft Fastly version cloned from `<base-version>`, never a direct edit of the active
  version.
- Confirm NGWAF fail-open behavior is unchanged. Do not copy or edit `ngwaf_config_*`
  snippets.

### A.3 Create dictionaries

#### A.3.1 rum_controls (plain dictionary)

1. Fastly UI → Deliver → the service → Data → Dictionaries → Create dictionary.
2. Name: `rum_controls`. Type: Dictionary (not private). Write items:

   | Item | Value | Notes |
   |---|---|---|
   | `enabled` | `true` | Kill switch. `false` empties `esi.html`. |
   | `recorder_mode` | `on_demand` | `off` \| `on_demand` \| `sampled`. Do not use `always`. |
   | `sample_tier1` | `0.50` | `sessionsSampleRate` for checkout/cart/PDP |
   | `sample_tier2` | `0.10` | home, PLP, search |
   | `sample_tier3` | `0.05` | account / other |
   | `replay_sample_tier1` | `0.05` | Used only when `recorder_mode` is `sampled` |
   | `replay_sample_tier2` | `0.01` | |
   | `replay_sample_tier3` | `0.00` | |
   | `application_name` | `<application-name>` | Must match dashboards / MetricSets |
   | `environment` | `prod` | `prod` \| `stage` \| `test` — not "production" / "testing" |
   | `realm` | `<realm>` | The customer's existing RUM realm |
   | `agent_version` | `v3` | Major pin. Move to `v3.x.y` after UAT sign-off |

3. Save. Dictionary updates on an activated service are live without a new VCL version.
   That is the kill switch.

#### A.3.2 rum_secrets (private dictionary)

1. Data → Dictionaries → Create dictionary → Private.
2. Name: `rum_secrets`.
3. Item `rum_access_token` = `<rum-access-token>` (the UAT or production RUM ingest
   token). Never the org API token.
4. Private dictionaries are write-only in the UI after save. Record rotation in the
   secrets manager, not in a repository.

### A.4 Create the Splunk CDN backend

1. Origins → Create host.
2. Name: `F_Splunk_O11y_CDN` (the UI may show it as `Splunk_O11y_CDN`; generated VCL
   prefixes `F_`).
3. Address: `cdn.observability.splunkcloud.com`
4. Port 443. Enable TLS. Certificate hostname and SNI:
   `cdn.observability.splunkcloud.com`. Minimum TLS 1.2. Always check certificate.
5. Override host header: `cdn.observability.splunkcloud.com`. Always use host header: yes.
6. Connect timeout 1s, first byte 15s, between bytes 10s, max connections 200.
7. Shield: none (or leave default). Do not send this host through `<shield-pop>`.
8. Health check: dummy `HEAD /` is fine, matching other backends in the service.

Then create the condition that selects this backend after all existing conditions:

1. Conditions → Create → Request.
2. Name: `Rum agent from Splunk CDN`
3. Apply if: `req.http.X-Rum-Asset == "1"`. Match the marker that
   `<prefix>_rum_recv` sets, not the `/__o11y/` path: the recv snippet rewrites the URL to
   `/o11y-gdi-rum/...` before generated backend selection runs, so a path condition would
   no longer match and the request would stay on the origin backend.
4. Priority: 30 (higher than the highest existing request condition, which is 20 in the
   reference service).
5. Attach the condition to `F_Splunk_O11y_CDN` as the destination for matching requests.
6. Also create a Header / Request setting on that condition: set
   `req.http.host = "cdn.observability.splunkcloud.com"`; rewrite URL to the pinned CDN
   path (see [A.5.1](#a51-snippet-prefix_rum_recv--type-recv-priority-110)). If you prefer
   all rewrite logic in VCL, put the URL rewrite in `<prefix>_rum_recv` and keep only the
   backend condition at priority 30.

> **Backend condition priority is mandatory.**
> If this condition is priority 10, the storefront condition (also 10, later in the file)
> or `<highest-condition-backend>` (20) can steal `/__o11y/splunk-otel-web.js` and send it
> to the storefront or content origin. You will get a 404 HTML page with a JS content-type
> and RUM will never boot. Verify with `curl -I` that the `Fastly-Debug-Path` / `X-Cache`
> object is the Splunk CDN host.

### A.5 Create VCL snippets

Fastly UI → VCL snippets → Create snippet. Type must match the table. Priority 110 so
they run after existing custom snippets (100) and still inside the Fastly macros. Do not
use type "none" unless you are prepared to maintain raw VCL.

#### A.5.1 Snippet `<prefix>_rum_recv` — type recv, priority 110

*`<prefix>_rum_recv`*

```vcl
# First-party agent files: mark for the prio-30 backend condition, then rewrite the URL.
if (req.url.path ~ "^/__o11y/splunk-otel-web(-session-recorder)?\.js$") {
  set req.http.host = "cdn.observability.splunkcloud.com";
  set req.http.X-Rum-Asset = "1";
  unset req.http.Cookie;
  if (req.url.path ~ "session-recorder") {
    set req.url = "/o11y-gdi-rum/" table.lookup(rum_controls, "agent_version", "v3") "/splunk-otel-web-session-recorder.js";
  } else {
    set req.url = "/o11y-gdi-rum/" table.lookup(rum_controls, "agent_version", "v3") "/splunk-otel-web.js";
  }
}

# Config + ESI fragment: synthetic. Must error BEFORE generated backend selection.
if (req.url.path == "/__o11y/splunk-rum-init.js" || req.url.path == "/__o11y/esi.html") {
  error 802 "RUM bootstrap";
}

# HTML eligibility: storefront family only. Edge hop only.
if (fastly.ff.visits_this_service == 0
    && req.restarts == 0
    && req.http.host == "<site-host>"
    && req.method ~ "^(GET|HEAD)$"
    && (req.url.path ~ "(?i)^/(<market-codes>)/[a-z]{2}(/|$)"
        || req.url.path ~ "(?i)^/(login|logout)/callback")
    && req.url.path !~ "^/storefront/client/"
    && req.url.path !~ "^/assets/"
    && req.url.path !~ "^/(api|rest|<other-api-prefixes>)/"
    && req.url.ext !~ "(?i)^(js|mjs|css|map|json|xml|txt|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf|mp4|webm)$"
) {
  set req.http.X-Rum-Eligible = "1";
}

if (req.http.Cookie ~ "(^|;\s*)<prefix>_rum=off(;|$)") {
  unset req.http.X-Rum-Eligible;
  set req.http.X-Rum-Kill = "1";
}
if (req.http.Cookie ~ "(^|;\s*)<prefix>_rum=force(;|$)") {
  set req.http.X-Rum-Force = "1";
}
```

Confirm status 802 is unused in the current VCL before adopting it. Services commonly use
custom statuses for Force SSL, maintenance pages, redirects, robots, IP blocks, and
integrity checks (for example 801, 601/699, 650, 900, 901, 550). Do not reuse those.

#### A.5.2 Snippet `<prefix>_rum_fetch` — type fetch, priority 110

*`<prefix>_rum_fetch`*

```vcl
if (req.http.X-Rum-Asset) {
  set beresp.cacheable = true;
  set beresp.ttl = 1d;
  set beresp.http.Cache-Control = "public, max-age=86400";
  set beresp.http.Surrogate-Key = "o11y-rum-agent";
  unset beresp.http.Set-Cookie;
}

if (req.http.X-Rum-Eligible
    && beresp.status == 200
    && beresp.http.Content-Type ~ "text/html"
    && !beresp.http.Set-Cookie
    && !req.http.X-Redirect-To) {
  set beresp.do_esi = true;
  set beresp.do_stream = false;
}
```

Signed-in storefront responses often send `Set-Cookie`, which later in `vcl_fetch` forces
pass. If you observe cart/checkout HTML without the snippet, add a second branch that sets
`do_esi` when `X-Rum-Eligible` even if `Set-Cookie` is present, and still force
`do_stream` false. Do not ESI 301/302/4xx/5xx or Image Optimizer responses.

*Use this broader fetch branch if pass responses skip ESI*

```vcl
# Optional follow-up if checkout HTML is passed because of Set-Cookie:
if (req.http.X-Rum-Eligible
    && beresp.status == 200
    && beresp.http.Content-Type ~ "text/html"
    && !req.http.X-Redirect-To) {
  set beresp.do_esi = true;
  set beresp.do_stream = false;
}
```

#### A.5.3 Snippet `<prefix>_rum_error` — type error, priority 110

This snippet must run before the generic 403/404 handlers in the existing error snippet.
Priority 110 on type error runs after an existing error snippet at 100 — if 802 is
swallowed, lower this snippet to priority 90 so it runs first, or add the 802 block at the
top of the existing error snippet.

Fragment (path `/__o11y/esi.html`):

*`<prefix>_rum_error` wrapper — replace the init placeholder with
[A.5.4](#a54-synthetic-init-javascript-body-of-splunk-rum-initjs)*

```vcl
if (obj.status == 802) {
  declare local var.enabled STRING;
  declare local var.token STRING;
  set var.enabled = table.lookup(rum_controls, "enabled", "false");
  set var.token   = table.lookup(rum_secrets, "rum_access_token", "");

  if (req.http.Cookie ~ "(^|;\s*)<prefix>_rum=off(;|$)") {
    set var.enabled = "false";
  }
  if (req.http.Cookie ~ "(^|;\s*)<prefix>_rum=force(;|$)" ) {
    set var.enabled = "true";
  }

  set obj.status = 200;
  set obj.response = "OK";
  set obj.http.Cache-Control = "public, max-age=10";
  set obj.http.Surrogate-Control = "max-age=10";
  set obj.http.Surrogate-Key = "o11y-rum-init";

  if (req.url.path == "/__o11y/esi.html") {
    set obj.http.Content-Type = "text/html; charset=utf-8";
    if (var.enabled == "true") {
      synthetic {"<script src="/__o11y/splunk-otel-web.js" crossorigin="anonymous"></script>
<script src="/__o11y/splunk-rum-init.js"></script>"};
    } else {
      synthetic {""};
    }
    return (deliver);
  }

  set obj.http.Content-Type = "application/javascript; charset=utf-8";
  synthetic {"/* init JS — paste the full file from A.5.4 */"};
  return (deliver);
}
```

Do not put `defer` on the init script if the core agent script above it is synchronous.
Init must run immediately after `SplunkRum` is defined. Guidance to defer competing third
parties does not apply to this two-tag pair.

#### A.5.4 Synthetic init JavaScript (body of splunk-rum-init.js)

Paste this into the `synthetic {" ... "}` for `/__o11y/splunk-rum-init.js`. VCL string
concatenation inserts dictionary values. In a Fastly long string, `"}` closes the literal
and `{"` reopens it, so those delimiters emit no JavaScript quotes. Every interpolated
string therefore uses `""} json.escape(...) {""`: the extra `"` on each side becomes the
JavaScript quote, and `json.escape` keeps a stray `"` or `\` in a dictionary value from
breaking the script. The enabled flag is emitted as a bare `true` or `false` with Fastly's
`if()` expression, so the kill switch compares a boolean, not a string. If you prefer zero VCL interpolation inside the
JS, emit a small JSON config in a first `<script>` and keep this file static — the version
below is one snippet. Adjust the route rules and `ignoreUrls` to the customer's site.

*Complete synthetic body for `/__o11y/splunk-rum-init.js`*

```vcl
synthetic {"
(function () {
  if (window.__SPLUNK_RUM_BOOTED__) return;
  window.__SPLUNK_RUM_BOOTED__ = true;
  window.__FEATURE_RUM_ENABLED__ = "} if(var.enabled == "true", "true", "false") {";
  window.__RUM_TOKEN__ = ""} json.escape(var.token) {"";
  window.__ENV__ = ""} json.escape(table.lookup(rum_controls, "environment", "prod")) {"";
  if (!window.__FEATURE_RUM_ENABLED__ || typeof SplunkRum === "undefined") return;

  var rules = [
    { re: /^\/[a-z]{2}\/[a-z]{2}\/checkout(\/|$)/i, type: "checkout", sla: "tier1" },
    { re: /^\/[a-z]{2}\/[a-z]{2}\/cart(\/|$)/i,     type: "cart",     sla: "tier1" },
    { re: /^\/[a-z]{2}\/[a-z]{2}\/product\//i,      type: "pdp",      sla: "tier1" },
    { re: /^\/[a-z]{2}\/[a-z]{2}\/category\//i,     type: "plp",      sla: "tier2" },
    { re: /^\/[a-z]{2}\/[a-z]{2}\/search/i,         type: "search",   sla: "tier2" },
    { re: /^\/[a-z]{2}\/[a-z]{2}\/?$/i,             type: "home",     sla: "tier2" },
    { re: /^\/[a-z]{2}\/[a-z]{2}\/(myaccount|account)/i, type: "account", sla: "tier3" }
  ];
  var p = { type: "other", sla: "none" };
  for (var i = 0; i < rules.length; i++) {
    if (rules[i].re.test(location.pathname)) { p = rules[i]; break; }
  }
  window.__PAGE_TYPE__ = p.type;
  window.__PAGE_SLA_TIER__ = p.sla;

  var sample = p.sla === "tier1" ? ""} json.escape(table.lookup(rum_controls, "sample_tier1", "0.50")) {""
             : p.sla === "tier2" ? ""} json.escape(table.lookup(rum_controls, "sample_tier2", "0.10")) {""
             : ""} json.escape(table.lookup(rum_controls, "sample_tier3", "0.05")) {"";
  if (document.cookie.indexOf("<prefix>_rum=force") !== -1) sample = "1";

  SplunkRum.init({
    realm: ""} json.escape(table.lookup(rum_controls, "realm", "<realm>")) {"",
    rumAccessToken: window.__RUM_TOKEN__,
    applicationName: ""} json.escape(table.lookup(rum_controls, "application_name", "<application-name>")) {"",
    deploymentEnvironment: window.__ENV__,
    sessionsSampleRate: Number(sample),
    bufferSize: 100,
    bufferTimeout: 4000,
    globalAttributes: {
      "page.type": p.type,
      "page.sla_tier": p.sla,
      "page.locale": document.documentElement.lang || "unknown",
      "site.brand": "<brand>",
      "rum.inject": "fastly-esi"
    },
    instrumentations: {
      document: true, interactions: true, xhr: true, fetch: true,
      websocket: false, postload: false, longtask: true,
      connectivity: false, visibility: true, webvitals: true
    },
    ignoreUrls: [
      /assets\.adobedtm\.com/, /googletagmanager\.com/, /doubleclick\.net/,
      /cdn\.optimizely\.com/, /eum\.instana\.io/, /rum-ingest\..*signalfx\.com/,
      /rum-ingest\..*observability\.splunkcloud\.com/, /\/__o11y\//
    ]
  });

  var recMode = ""} json.escape(table.lookup(rum_controls, "recorder_mode", "on_demand")) {"";
  var recSample = p.sla === "tier1" ? ""} json.escape(table.lookup(rum_controls, "replay_sample_tier1", "0.05")) {""
                : p.sla === "tier2" ? ""} json.escape(table.lookup(rum_controls, "replay_sample_tier2", "0.01")) {""
                : ""} json.escape(table.lookup(rum_controls, "replay_sample_tier3", "0.00")) {"";
  var recStarted = false;
  function startRecordingOnce(reason) {
    if (recStarted || recMode === "off") return;
    recStarted = true;
    var s = document.createElement("script");
    s.src = "/__o11y/splunk-otel-web-session-recorder.js";
    s.crossOrigin = "anonymous";
    s.onload = function () {
      if (!window.SplunkSessionRecorder) return;
      SplunkSessionRecorder.init({
        realm: ""} json.escape(table.lookup(rum_controls, "realm", "<realm>")) {"",
        rumAccessToken: window.__RUM_TOKEN__,
        recorder: "splunk"
      });
      SplunkRum.setGlobalAttributes({
        "session.recording.mode": reason === "sampled" ? "sampled" : "on_demand",
        "session.recording.trigger": reason
      });
    };
    document.head.appendChild(s);
  }
  if (recMode === "on_demand" || recMode === "sampled") {
    window.addEventListener("error", function () { startRecordingOnce("js_error"); });
    window.addEventListener("unhandledrejection", function () { startRecordingOnce("unhandled_promise"); });
    if (p.type === "checkout") startRecordingOnce("checkout_entry");
    if (document.cookie.indexOf("<prefix>_replay=force") !== -1) startRecordingOnce("support_takeover");
    else if (recMode === "sampled" && Math.random() < Number(recSample)) startRecordingOnce("sampled");
  }
})();
"};
```

#### A.5.5 Snippet `<prefix>_rum_deliver` — type deliver, priority 110

*`<prefix>_rum_deliver` — extend the effective connect-src, never duplicate it*

```vcl
if (req.http.X-Rum-Eligible && !req.http.X-Redirect-To && resp.status == 200) {
  declare local var.ingest STRING;
  set var.ingest = " https://rum-ingest.<realm>.signalfx.com https://rum-ingest.<realm>.observability.splunkcloud.com";
  if (resp.http.Content-Security-Policy ~ "(?i)(^|;)\s*connect-src(\s|;|$)") {
    # Append the ingest hosts inside the existing connect-src directive.
    set resp.http.Content-Security-Policy = regsub(resp.http.Content-Security-Policy,
      "(?i)((?:^|;)\s*connect-src[^;]*)", "\1" var.ingest);
  } else if (resp.http.Content-Security-Policy ~ "(?i)(^|;)\s*default-src\s+([^;]*)") {
    # connect-src currently falls back to default-src: copy its sources so nothing the
    # page already connects to is blocked.
    set resp.http.Content-Security-Policy = resp.http.Content-Security-Policy
      "; connect-src " re.group.2 var.ingest;
  }
}
```

Browsers honor only the first `connect-src` in a policy and ignore duplicates, so
appending a second directive does not authorize RUM. The snippet edits the existing
directive in place. When the policy has no `connect-src`, connections fall back to
`default-src`, so the new directive starts from those sources. If the existing directive
is `connect-src 'none'`, stop and agree the policy with the site owner: `'none'` cannot be
combined with hosts. If the storefront has no CSP, do not invent a site-wide policy in
Fastly as part of this change. Apply the same edit to `Content-Security-Policy-Report-Only`
if the site uses it. Confirm rum-ingest and `script-src 'self'` (or the first-party host)
in a pre-production HAR before activation.

### A.6 Storefront SSR change

File: the storefront root layout that emits `<head>` (App Router `layout.tsx` or Pages
Router `_document` / `_app`, whichever owns the first `<head>`).

Place this as the first child of `<head>`, before the incumbent agent, tag managers, and
any `modulepreload` of the main bundle:

*Storefront SSR — first child of head*

```html
<head>
  <!--esi
    <esi:include src="/__o11y/esi.html" />
  -->
  <!-- existing incumbent agent / tag manager / Next.js tags follow -->
</head>
```

- `src` is a same-origin relative path. Fastly resolves it on the current host
  (`<site-host>`). Do not use a full `https://<site-host>` URL unless you want an extra
  Host lookup.
- Do not nest the include inside a React component that client-renders. ESI is processed
  on the HTML Fastly received from origin / cache, not on client navigations.
- Whitespace inside `<!--esi ... -->` is fine. The include tag must be well-formed XML:
  space before `/>`, quoted `src`.
- Do not add `<esi:include>` without the `<!--esi` wrapper. Some origin or WAF paths will
  emit the raw tag to the browser.
- After this ships, grep the storefront and micro-frontend artifacts for `SplunkRum.init`,
  `SplunkSessionRecorder`, `@splunk/otel-web`, and `rumAccessToken`. Those must be gone
  from production bundles.

#### A.6.1 Optional esi:remove fallback

Only needed if a non-Fastly environment would otherwise show the raw include. The comment
wrapper already hides it from browsers.

```html
<!--esi
  <esi:include src="/__o11y/esi.html" />
-->
<esi:remove>
  <!-- non-Fastly preview: no RUM -->
</esi:remove>
```

### A.7 Compile, diff, and activate a draft

1. In the Fastly UI, open the draft version → Show VCL. Search for `<prefix>_rum_recv`,
   `error 802`, `F_Splunk_O11y_CDN`, and `do_esi`.
2. Confirm generated order in `vcl_recv`: the rum recv snippet (`error 802`) appears
   before "default conditions" / `set req.backend`. Confirm the priority 30 condition
   appears after the highest existing condition.
3. Confirm `vcl_error` handles 802 before 403/404/650.
4. Do not activate. Use Fastly's version hostname or a hosts-file / header test
   (`Fastly-Debug: 1`) against the draft.

### A.8 Verification (do these in order)

#### A.8.1 Fragment and init — no storefront required

*Direct path checks*

```bash
# Replace HOST with the draft or <site-host> once activated.

curl -sS -D- -o /tmp/esi.html \
  "https://HOST/__o11y/esi.html" | sed -n '1,20p'
# Expect: HTTP/2 200, content-type text/html, cache-control max-age=10
# Body: two script tags when rum_controls.enabled=true

curl -sS -D- -o /tmp/init.js \
  "https://HOST/__o11y/splunk-rum-init.js" | sed -n '1,20p'
# Expect: application/javascript, max-age=10, contains <application-name>
# Must NOT contain the org API token. Must contain the RUM ingest token.

curl -sS -D- -o /tmp/agent.js \
  "https://HOST/__o11y/splunk-otel-web.js" | sed -n '1,25p'
# Expect: 200, application/javascript, max-age=86400
# First bytes should be the Splunk agent, not storefront HTML.

curl -sS -D- "https://HOST/__o11y/esi.html" \
  -H "Cookie: <prefix>_rum=off"
# Expect: 200, empty body (kill switch).
```

#### A.8.2 ESI expansion on a real storefront page

*Confirm Fastly expanded the include*

```bash
curl -sS -D- \
  -H "Fastly-Debug: 1" \
  "https://HOST/us/en/" \
  | tee /tmp/home.headers \
  | python3 -c 'import sys; d=sys.stdin.read(); print("esi comment left?", "<!--esi" in d); print("script injected?", "/__o11y/splunk-otel-web.js" in d); print("raw include leaked?", "<esi:include" in d)'

# Pass:
#   esi comment left? False
#   script injected? True
#   raw include leaked? False
#
# If "esi comment left? True" → do_esi was not set (eligibility, shield hop,
# content-type, status, or streaming).
# If "raw include leaked? True" → missing <!--esi wrapper or origin escaped it.
```

Also curl an asset and a CMS path and confirm no `/__o11y` scripts: `/assets/…`,
`/storefront/client/main-bundle…`, and a CMS page under `/content/…`.

#### A.8.3 Browser

1. Clean profile, `<site-host>/us/en/`. DevTools Network: `splunk-otel-web.js` and
   `splunk-rum-init.js` from the first-party host, not the Splunk CDN hostname.
2. Initiator is the HTML document, not the main bundle.
3. First POST `https://rum-ingest.<realm>.signalfx.com/v1/rum` (or the
   `observability.splunkcloud.com` ingest host) within 1 s p90.
4. Idle 30 s: zero posts to `/v1/rumreplay`. Repeat 10 times.
5. In console: `throw new Error('rum-probe')`. Confirm `session-recorder.js` loads once
   and a rumreplay POST occurs.
6. Set cookie `<prefix>_rum=off`, hard reload. No agent, no ingest. Delete cookie.
7. SPA click to a PDP: no second download of `splunk-otel-web.js`; no second init.
   `page.type` becomes `pdp` via `setGlobalAttributes` (storefront hook).
8. Splunk Observability → Digital Experience → Real user monitoring → Sessions. Filter
   `sf_application=<application-name>`, `rum.inject=fastly-esi`.

### A.9 Shielding, gzip, and cache — ESI-specific rules

- **Shield:** Eligibility and `do_esi` are gated on
  `fastly.ff.visits_this_service == 0`. The shield stores storefront HTML without
  expanding ESI. The edge expands on deliver to the client.
- **Gzip:** Fastly decompresses gzip HTML, runs ESI, recompresses. The existing gzip
  policy can stay. `do_stream` must stay false on ESI objects.
- **Two TTLs:** Parent HTML TTL stays as the existing fetch logic set it (minutes, or
  uncacheable). Fragment TTL is 10 s. Purge `Surrogate-Key o11y-rum-init` to force flag
  changes immediately.
- **Hash:** Do not add rum flags to `vcl_hash`. Varying HTML on `enabled` would explode
  cache cardinality and defeat the fragment design.
- **Redirects:** `X-Redirect-To` is applied in `vcl_deliver` after fetch. Those responses
  must not have `do_esi`. Eligibility already skips when the header is set in recv;
  campaign or vanity redirects that set the header later still must not ESI — the fetch
  snippet checks `!req.http.X-Redirect-To`.
- **Limits:** Fastly limits ESI includes per page (typically dozens; you use one). Nested
  includes are not required. Do not ESI the agent JS files.

### A.10 NGWAF and Image Optimizer

Leave `ngwaf_config_init` / `miss` / `pass` / `deliver` untouched. `error 802` never calls
`edge_security`. The agent proxy does miss/pass to `F_Splunk_O11y_CDN`; if NGWAF blocks
that host, add it to the existing WAF allow behavior rather than copying the vendor
snippet.

Image Optimizer is keyed on image extensions and is already excluded from
`X-Rum-Eligible`. Do not set `x-fastly-imageopto-api` on `/__o11y/*`.

### A.11 Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `<!--esi` still in view-source | `do_esi` false: shield hop, not `text/html`, status ≠ 200, stream, or `X-Rum-Eligible` missing | `Fastly-Debug: 1`. Check hop count, content-type, fetch snippet. |
| `<esi:include` visible in the page | Missing `<!--esi` wrapper, or origin HTML-escaped the tag | Emit a raw comment from SSR, not a React text node. |
| `/__o11y/splunk-otel-web.js` is storefront HTML | Backend condition priority ≤ 20; storefront/origin stole the path | Set condition priority 30. `curl -I` and confirm CDN JS. |
| 802 never fires; `/__o11y/esi.html` is a 404 from origin | Recv snippet after error path, or snippet not in this version | Show VCL. `error 802` must appear before `return(lookup)`. |
| 802 handled as 403/404 | Existing error snippet runs first and returns on unknown statuses | Handle 802 at priority 90 or at the top of the existing error snippet. |
| Double RUM beacons | Main bundle still calls `SplunkRum.init` | Remove bundle init. Grep the shipped bundle. |
| Always-on rumreplay | Bundle still calls `SessionRecorder.init`, or `recorder_mode=always` | Remove bundle recorder init. Dictionary must be `on_demand` or `sampled`. |
| Kill switch does nothing for 5 minutes | Flags baked into cached HTML, or fragment TTL too long | Confirm `esi.html` `Cache-Control` is 10 s. Purge `o11y-rum-init`. |
| RUM works on home, not checkout | `Set-Cookie` pass skipped `do_esi` | Use the broader fetch branch in [A.5.2](#a52-snippet-prefix_rum_fetch--type-fetch-priority-110). |
| CSP violations in console | `connect-src` / `worker-src` / `script-src` missing | HAR the CSP header. Add ingest hosts and `worker-src blob:`. |
| `sf_application` still `<legacy-application-name>` | Old bundle init still running, or dictionary not applied | View-source the fragment. Confirm the `application_name` item. |
| UAT sessions in production | Shared token or environment string | Separate `rum_secrets` per service / environment. |

### A.12 Activation checklist

| # | Check | Owner |
|---|---|---|
| 1 | Draft VCL compiles; 802, `do_esi`, priority 30 backend present in Show VCL | CDN |
| 2 | `rum_secrets` set on UAT; `rum_controls.enabled=true` on UAT only | SRE |
| 3 | curl fragment, init, agent JS, and `<prefix>_rum=off` as in [A.8.1](#a81-fragment-and-init--no-storefront-required) | CDN |
| 4 | Storefront UAT: ESI include first in `<head>`; bundle grep clean | Storefront |
| 5 | Browser: first beacon < 1 s; zero idle rumreplay; error trigger records | Observability |
| 6 | CSP / NGWAF / Image Optimizer / redirects / other properties / admin unchanged | CDN |
| 7 | Activate the Fastly version on one market; 24 h canary vs Core Web Vitals gates | CDN + Observability |
| 8 | Kill-switch drill; Metric Finder `rum.client.*` stops ≤ 2 min | SRE |
| 9 | Ramp remaining markets; then turn off the incumbent browser agent | All |

### A.13 Rollback commands

*Rollback — prefer (1) over (4)*

```bash
# 1) Immediate, no VCL activate — dictionary write
# Fastly UI → rum_controls → enabled = false
# or Fastly API dictionary item update.

# 2) Tester-only
# In the browser console on <site-host>:
document.cookie = "<prefix>_rum=off; path=/; secure; samesite=lax";
location.reload();

# 3) Purge fragment if a bad init is cached
# Fastly UI → Purge → Surrogate Key: o11y-rum-init

# 4) Version rollback
# Fastly UI → versions → activate the previous known-good VCL.
# Storefront ESI comments are then inert.
```

## Appendix B. Out of scope and follow-ups

- Admin, event, regional, CMS, and content-platform properties get their own
  `applicationName` and tokens if RUM is required later.
- Interactive-ready page metrics, MetricSets, and SLA detectors remain storefront and
  observability work. ESI only delivers the agent.
- Do not use this VCL to inject other browser agents, Adobe Launch, or GTM. Splunk must
  load first; those remain origin flags.
- Maintenance synthetic pages stay without RUM unless the product team asks for downtime
  RUM.
- Compute `HTMLRewritingStream` is the fallback if the storefront refuses the ESI include.
  See [section 10](#10-compute-alternative-not-the-default).
