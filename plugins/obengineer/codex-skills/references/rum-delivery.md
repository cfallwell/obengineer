# RUM load order and CDN delivery

This reference owns the RUM load-order foundation check and the CDN delivery
recommendation recorded in `architecture.frontend` of contract schema v4.

## Load-order foundation check

The Splunk RUM agent must load and initialize before the front-end framework bootstraps.
Otherwise the first navigation, early resource timings, and bootstrap errors are lost, and
spans started before init carry no session.

The agent must initialize before:

| Framework | Bootstrap call |
|---|---|
| Angular | `bootstrapApplication(...)` or `platformBrowserDynamic().bootstrapModule(...)` |
| React | `createRoot(...).render(...)` or `ReactDOM.render(...)` |
| Vue | `createApp(...).mount(...)` |
| Next.js | `instrumentation-client.(js\|ts)`, or `pages/_document` `<Head>` for the Pages Router |

Load order is correct only when all hold:

- the agent script is in `<head>`, ahead of the application bundle;
- no `async` or `defer` attribute, and no dynamic import, delays init past the bundle;
- `SplunkRum.init(...)` runs exactly once, in one place.

Record the result:

```json
"rumLoadOrder": {
  "status": "incorrect",
  "agentLoad": "Loaded with defer from index.html after main.js.",
  "frameworkBootstrap": "src/main.ts calls bootstrapApplication(AppComponent).",
  "evidence": "The deferred agent initializes after the Angular bundle bootstraps.",
  "evidenceIds": ["SRC-web-index-html", "SRC-web-main-ts"]
}
```

`status` is `correct`, `incorrect`, or `unresolved`. An `incorrect` status requires at least
one foundation work order. Use `unresolved` when the source or production page is not
available; never guess.

## CDN delivery

Prefer injecting the RUM snippet at the CDN edge over adding it to application code. Edge
injection places the agent first in `<head>` on every HTML response, keeps one init across
applications, and changes the token or version without an application release.

Record the recommendation:

```json
"cdnDelivery": {
  "cdn": "fastly",
  "recommendation": "Inject the RUM snippet at the edge on HTML responses.",
  "guidance": "skills/references/rum-delivery.md#fastly"
}
```

`cdn` is `fastly`, `akamai`, `cloudflare`, `cloudfront`, `azure-front-door`,
`google-cloud-cdn`, `other`, `none`, or `unknown`. `guidance` links the matching section
below; use `skills/references/rum-delivery.md#cdn-delivery` for `other`, `none`, or
`unknown`. Never put a RUM token in the recommendation.

### Fastly

Pending guidance: the maintainer will supply the Fastly example.

### Akamai

Pending guidance.

### Cloudflare

Pending guidance.

### CloudFront

Amazon CloudFront. Pending guidance.

### Azure Front Door

Pending guidance.

### Google Cloud CDN

Pending guidance.
