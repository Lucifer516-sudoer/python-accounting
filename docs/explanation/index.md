---
title: Explanation
---

# Explanation

The Guides tell you *how* to do things. This section tells you *why* the
library is built the way it is — the design decisions, the guarantees they
buy you, and the trade-offs behind them.

<div class="grid cards" markdown>

-   :material-link-variant: **The ledger hash chain**
    ---

    How every posting is chained to the last, and why editing the database
    directly is detectable — not just forbidden.

    [:octicons-arrow-right-24: Hash chain](ledger-hashing.md)

-   :material-undo-variant: **Recycling: soft delete with a memory**
    ---

    Why `session.delete()` never destroys anything, and what the `Recycled`
    audit trail records.

    [:octicons-arrow-right-24: Recycling](recycling.md)

-   :material-domain: **Entity isolation**
    ---

    How one database serves many companies without a single query leaking
    between them.

    [:octicons-arrow-right-24: Isolation](entity-isolation.md)

-   :material-calendar-month: **Reporting periods**
    ---

    Why accounting happens in years, and how the books roll forward on
    their own.

    [:octicons-arrow-right-24: Periods](reporting-periods.md)

</div>
