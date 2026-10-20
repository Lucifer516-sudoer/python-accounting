# Transactions

Nothing in the ledger is ever written directly. Money moves through
**Transactions**, and each transaction is a small, validated story:
*what happened, when, between which accounts, for how much*.

## The shape of a transaction

A transaction has a **main account** — the account the money flows through —
and one or more **Line Items**, each pointing at the account on the *other
side* of the entry. The library knows, per transaction type, which side the
main account lands on; the line items always go to the opposite side. That's
how double entry is enforced: you can't post an unbalanced entry because the
two sides are derived from the same amounts.

There are ten transaction types, each a subclass of `Transaction` in
`python_accounting.transactions`:

| Type | Meaning | Main account side |
|---|---|---|
| `CashSale` | You sold something, cash received | Debit |
| `CashPurchase` | You bought something, cash paid | Credit |
| `ClientInvoice` | You invoiced a client (receivable) | Debit |
| `ClientReceipt` | The client paid | Credit |
| `SupplierBill` | A supplier invoiced you (payable) | Credit |
| `SupplierPayment` | You paid the supplier | Debit |
| `CreditNote` | You refunded/credited a client | Credit |
| `DebitNote` | The supplier credited you | Debit |
| `ContraEntry` | Money moved between your own accounts | — |
| `JournalEntry` | The accountant's escape hatch | You choose |

## Posting a sale

```python
from datetime import datetime
from python_accounting.models import LineItem
from python_accounting.transactions import CashSale

sale = CashSale(
    narration="Sale of goods",
    transaction_date=datetime.now(),
    currency_id=currency.id,
    entity_id=entity.id,
    main_account_id=bank.id,
)
session.add(sale)
session.commit()

line_item = LineItem(
    description="Sale of goods",
    amount=100,
    account_id=revenue.id,
)
session.add(line_item)
session.commit()

sale.LineItems.append(line_item)
session.commit()

sale.post(session)  # writes the Ledger rows
```

Walk through what happened:

1. The `CashSale` was created with the **bank** as main account.
2. A `LineItem` of 100 was attached, pointing at the **revenue** account.
3. `post()` wrote the ledger entries: **debit bank 100, credit revenue 100**.

The bank balance went up by 100, revenue went up by 100, and the books
balance — because both sides came from the same line item.

!!! warning "Don't create bare Transactions"

    `Transaction` itself can technically be instantiated, but doing so
    bypasses the validation rules built into the subclasses and can produce
    incorrect bookkeeping. Always use the concrete types.

## The Ledger

`post()` writes rows into the **Ledger** — the immutable, hash-chained
record of every posting. Each row knows the transaction, the account, the
amount, the side (debit or credit), and the hash of the row before it.
Change anything directly in the database and the chain stops verifying.

You can read the ledger for an account or transaction, but you never write
it by hand:

```python
from python_accounting.models import Ledger

entries = session.query(Ledger).filter(
    Ledger.transaction_id == sale.id
).all()
```

## Compound transactions

One transaction, many line items — a payroll run, a rent payment split
across accounts. Just attach more line items; the totals still balance
because every line item posts to both sides. The `JournalEntry` is the one
type that lets *you* choose the main account's side via `credited=True/False`.
See [Compound Transactions](../guides/compound-transactions.md) for the full
walkthrough.

Next: taxes — and the control account that holds them.
