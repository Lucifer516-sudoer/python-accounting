# Reports

The goal of any accounting system is to summarize the Transactions that have
occurred for an Entity during a given period of time into information that can
be used to make financial decisions.

python-accounting ships a full reporting suite — every report below is a
single object you construct with a session and print:

<div class="grid cards" markdown>

-   :material-receipt-clock: **Account Statement**
    ---
    A chronological record of everything posted to one account, with a
    running balance.

    [:octicons-arrow-right-24: Statement](account-statement.md)

-   :material-receipt-clock-outline: **Account Schedule**
    ---
    Like a statement, but only the transactions that are still outstanding.

    [:octicons-arrow-right-24: Schedule](account-schedule.md)

-   :material-calendar-clock: **Aging Schedule**
    ---
    All outstanding receivables and payables, bucketed by how long they have
    been outstanding.

    [:octicons-arrow-right-24: Aging](aging-schedule.md)

-   :material-chart-line: **Income Statement**
    ---
    Revenue, cost of sales, operating expenses and the resulting profit for a
    period.

    [:octicons-arrow-right-24: Income](income-statement.md)

-   :material-scale-balance: **Balance Sheet**
    ---
    Assets, liabilities and equity as at a point in time.

    [:octicons-arrow-right-24: Balance](balance-sheet.md)

-   :material-cash-multiple: **Cashflow Statement**
    ---
    Where the cash came from and where it went, split into operating,
    investing and financing activities.

    [:octicons-arrow-right-24: Cashflow](cashflow-statement.md)

-   :material-format-list-numbered: **Trial Balance**
    ---
    Every account and its balance, debits on one side, credits on the other.

    [:octicons-arrow-right-24: Trial balance](trial-balance.md)

</div>

Looking for worked examples instead? See [Examples](examples.md).
