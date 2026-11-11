# React Router

Load only when `react-router` or `react-router-dom` is observed. Mount one host-owned
component using `useLocation()` (v6+) or `history.listen` (v5). On completed navigation,
classify bounded page/BT values, update global attributes/baggage, and emit `route.change`.
Remotes never mount another listener.
