# Angular Router

Load only when Angular Router is observed. Subscribe once in the host to successful
`NavigationEnd` events, classify bounded page/BT values, update global attributes/baggage,
and emit one `route.change` span. Ignore cancelled/error events except as explicit errors.
