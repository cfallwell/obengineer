# Browser and RUM

Load only when a production browser or WebView is in evidence.

Use the Splunk RUM Browser Agent with one host-owned `init`, a kill switch, early dedicated
loading, and an explicit instrumentation allowlist. Module-federation remotes and
micro-frontends consume the shared provider and never initialize another.

Auto-instrumentation does not capture client navigation. When router evidence exists, load
only that router's reference:

- [React Router](routers/react-router.md)
- [Next.js](routers/nextjs.md)
- [Vue Router](routers/vue.md)
- [Angular Router](routers/angular.md)
- [History API](routers/history-api.md)

Implement one host-owned listener that:

- classifies bounded `page.type` and `<org>.bt` values, never raw paths;
- updates global attributes and approved baggage;
- emits one `route.change` span per completed navigation; and
- is absent from remotes.

Session replay detail loads only when entitlement exists and always-on or sampled behavior
was accepted in writing. With no browser, keep the required document heading and write
`Not in evidence` plus the evidence needed; emit no browser code.
