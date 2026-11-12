# Usage and enforced-limit exposure

This compatibility-named reference defines the account-team appendix for measured
consumption. It never accepts contractual entitlement from `obconfig.yaml`.

Include the appendix when direct tenant measurement returns current usage or an enforced
`sf.org.limit.*` value, or when bounded recommendation arithmetic produces a material
projected cost. Label separately:

| Column | Meaning |
|---|---|
| Current usage | Direct measured organization usage |
| Enforced system limit | Direct measured platform enforcement value; not a contract |
| Proposed cost | Derived bounded recommendation arithmetic |
| System headroom | Limit minus usage/reserve/proposed cost |
| Contractual entitlement | Unavailable unless a separate measured Billing/Subscription Usage API or approved export supports it |

Never relabel an enforced limit as purchased entitlement, contractual headroom, license
overage, or commercial commitment. MCP-only or human-stated values do not satisfy the
direct-measurement row.

The customer-facing strategy may show technical dimension arithmetic but not commercial
claims. This appendix records source, timestamp, scope, direct-attempt disposition, and
limitations. It offers technical levers (classify, aggregate, defer, or remove a
nonessential promotion) without recommending a purchase.
