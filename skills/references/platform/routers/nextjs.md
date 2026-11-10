# Next.js routing

Load only when Next.js router evidence exists. App Router uses `usePathname()` in one
host client component; Pages Router subscribes once to `routeChangeComplete` in `_app`.
Classify bounded page/BT values and emit `route.change` after navigation completion.
