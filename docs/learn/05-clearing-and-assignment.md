# Clearing & Assignment

Here's a bookkeeping problem that trips up every naive implementation: a
client owes you 100. They pay 40. Later they pay 60. The receivable account
is now zero — but *which invoice* was paid, and how much of it is still
outstanding?

python-accounting answers with **Balances** and **Assignments**.

## Balances: the receivable's memory

When you post a `ClientInvoice`, the library records a **Balance** for the
receivable account — a memory of "this much is outstanding, from this
transaction". Payments post balances too, on the other side. The account
balance is the net; the individual balances are the *details*.

## Assignment: matching one against the other

An **Assignment** says "this balance offsets that one". It's the explicit
act of matching a payment against an invoice:

```python
from python_accounting.models import Assignment

assignment = Assignment(
    session=session,
    assigning_id=client_receipt.id,
    assigned_id=client_invoice.id,
    assigned_type=client_invoice.__class__.__name__,
)
session.add(assignment)
session.commit()
```

After this assignment:

- The invoice's **cleared amount** is 40
- Its **uncleared amount** is 60
- The receipt's amount is fully used

The library validates every assignment: you can't assign more than the
assigning balance has to give, or more than the assigned balance needs, and
not every transaction type is assignable (you can't "pay off" a cash sale —
it never had an outstanding balance to begin with; trying raises
`UnassignableTransactionError`).

## Why this matters: statements and aging

Because outstanding amounts are tracked per transaction, the library can
answer the questions accountants actually ask:

- **Account statement** — everything posted to the account, with running
  balance. See [Account Statement](../guides/account-statement.md).
- **Account schedule** — only the transactions that are *still outstanding*,
  with their `cleared_amount`, `uncleared_amount` and `age`. See
  [Account Schedule](../guides/account-schedule.md).
- **Aging schedule** — all outstanding balances bucketed by age: current,
  31–90 days, 91–180 days, and so on. The brackets are configurable in
  `config.toml`. See [Aging Schedule](../guides/aging-schedule.md).

That last one is the dunning list — who to chase, and how hard.

## Clearances

The assignments against a balance are its **clearances**. The `ClearingMixin`
gives any assignable object:

```python
cleared = invoice.cleared(session)      # Decimal: how much has been offset
clearances = invoice.clearances(session)  # the assignments themselves
```

Next: turning all of this into financial reports.
