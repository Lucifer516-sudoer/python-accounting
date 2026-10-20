# Reports

Everything you've posted is now sitting in a hash-chained ledger. Reports
are how it becomes information. Every report is an object you construct with
a session, print, and — because they're `__repr__`-driven — you get a
formatted statement, not a dump of objects.

## Income statement

```python
from python_accounting.reports import IncomeStatement

income_statement = IncomeStatement(session)
print(income_statement)
```

The income statement aggregates the operating revenue, operating expense,
direct expense, other income and other expense sections for the entity's
current reporting period, and computes the profit. Accounts are organized by
category where categories are set.

## Balance sheet

```python
from python_accounting.reports import BalanceSheet

balance_sheet = BalanceSheet(session)
print(balance_sheet)
```

Assets, liabilities and equity as at a point in time. The balance sheet
closes the loop on double entry: its totals balance *because* every
transaction you posted balanced — the report is arithmetic, not hope.

## The rest of the suite

| Report | Purpose | Guide |
|---|---|---|
| `TrialBalance` | Every account and its balance, debits vs credits | [Trial Balance](../guides/trial-balance.md) |
| `CashflowStatement` | Operating / investing / financing cash movements | [Cashflow Statement](../guides/cashflow-statement.md) |
| `AgingSchedule` | Outstanding receivables/payables by age bracket | [Aging Schedule](../guides/aging-schedule.md) |
| `Account.statement()` | Chronological record for one account | [Account Statement](../guides/account-statement.md) |
| `Account.statement(schedule=True)` | Only outstanding transactions | [Account Schedule](../guides/account-schedule.md) |

## Periods, not dates

Reports are always *for a reporting period*. The session's entity has an
open period; when you post transactions dated in a new calendar year, the
library rolls the period forward automatically. You can pass explicit dates
to most reports, but the default window is the open period — which is
usually exactly what you want.

## Where the numbers come from

One thing worth internalizing: **reports never mutate anything**. They read
balances and ledger entries, group them by the sections defined in
`config.toml`, and format the result. If a report looks wrong, the error is
in postings, not in the report — and the ledger hash chain will tell you if
someone edited the postings behind the library's back.

---

**That's the tutorial.** You've seen the whole arc: entity → accounts →
transactions → taxes → clearing → reports. The [Guides](../guides/index.md)
go deeper on each report, the [Explanation](../explanation/index.md)
section covers *why* the machinery is built the way it is, and the
[API reference](../reference/index.md) has every class and method.
