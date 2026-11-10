# Browser History API

Load only when client navigation uses `pushState`, `replaceState`, or `popstate` without a
framework router. Install one host wrapper/listener, preserve native behavior, classify
bounded page/BT values, and emit `route.change`. Never install it in multiple bundles.
