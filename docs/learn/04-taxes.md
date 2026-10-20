# Taxes

Sales tax, VAT, GST — whatever your jurisdiction calls it, the mechanics are
the same: you collect money on behalf of the tax authority, you hold it, and
you remit it. python-accounting models that with a **Tax** object and a
**control account**.

## The Tax object

A `Tax` has a name, a code, a rate, and — crucially — the account where the
collected tax is held:

```python
from python_accounting.models import Tax, Account

tax_account = Account(
    name="Tax Account",
    account_type=Account.AccountType.CONTROL,
    currency_id=currency.id,
    entity_id=entity.id,
)
session.add(tax_account)
session.commit()

output_tax = Tax(
    name="Output Vat",
    code="OUPT",
    account_id=tax_account.id,
    rate=10,
    entity_id=entity.id,
)
input_tax = Tax(
    name="Input Vat",
    code="INPT",
    account_id=tax_account.id,
    rate=10,
    entity_id=entity.id,
)
session.add_all([output_tax, input_tax])
session.commit()
```

- **Output tax** is the tax you charge customers on sales.
- **Input tax** is the tax you pay suppliers on purchases.
- The **control account** accumulates both; its balance is what you owe (or
  are owed) at remittance time.

## Attaching tax to a line item

Taxes attach to **Line Items**, not transactions:

```python
from python_accounting.models import LineItem
from python_accounting.transactions import CashSale

sale = CashSale(
    narration="Taxed sale",
    transaction_date=datetime.now(),
    currency_id=currency.id,
    entity_id=entity.id,
    main_account_id=bank.id,
)
session.add(sale)
session.commit()

line_item = LineItem(
    description="Taxed sale",
    amount=100,
    account_id=revenue.id,
    tax_id=output_tax.id,
)
session.add(line_item)
session.commit()

sale.LineItems.append(line_item)
session.commit()
sale.post(session)
```

When this posts, the library writes **three** ledger entries, not two:

- **Debit bank 110** — what the customer actually paid
- **Credit revenue 100** — what you actually earned
- **Credit tax account 10** — what you now owe the tax authority

The tax amount is computed from the rate, posted to the tax's account, and
the books still balance — because the extra 10 came from somewhere (the
customer) and went somewhere (the control account).

## Tax inclusive vs tax exclusive

By default, taxes are **exclusive**: the tax is added *on top* of the line
item amount, as above. Some invoices quote tax *inside* the amount — "100
including VAT". Set `tax_inclusive=True` on the line item and the library
splits the amount instead of extending it:

```python
line_item = LineItem(
    description="Taxed sale",
    amount=100,
    account_id=revenue.id,
    tax_id=output_tax.id,
    tax_inclusive=True,  # 100 includes the tax
)
```

Now the entries are:

- **Debit bank 100** — what the customer paid
- **Credit revenue 90.91** — the net amount
- **Credit tax account 9.09** — the tax hidden inside the 100

Same total, different split. The full worked example is in
[Tax Inclusive Transactions](../guides/tax-inclusive.md).

## Remitting

When you remit, the control account's balance tells you what to pay. A
`JournalEntry` or contra movement zeroes it out against your bank account —
the control account should land back at zero, or the difference is exactly
your reconciliation problem.

Next: matching invoices against receipts — clearing and assignment.
