# Accounts

An **Account** is a place money can live. The full list of an entity's
accounts is the **chart of accounts**, and every transaction in the ledger
moves money between exactly two of them.

## Account types

Every account has exactly one type, and the type is not a free-form string —
it comes from `Account.AccountType`, which is driven by the library's
`config.toml`. The standard set covers the whole balance sheet and income
statement:

| Group | Types |
|---|---|
| Balance sheet | `BANK`, `EQUITY`, `NON_CURRENT_ASSET`, `CURRENT_ASSET`, `INVENTORY`, `RECEIVABLE`, `CONTROL`, `PAYABLE`, `CURRENT_LIABILITY`, `NON_CURRENT_LIABILITY` |
| Income statement | `OPERATING_REVENUE`, `OPERATING_EXPENSE`, `DIRECT_EXPENSE`, `OTHER_INCOME`, `OTHER_EXPENSE`, `CONTRA_INCOME`, `CONTRA_EXPENSE` |

The type decides three things at once:

1. **Which report section** the account appears in (assets, revenue, …)
2. **Which account code range** it gets (accounts are auto-numbered per type)
3. **Which side of the ledger** debits and credits increase it

## Creating accounts

```python
from python_accounting.models import Account

bank = Account(
    name="Bank Account",
    account_type=Account.AccountType.BANK,
    currency_id=currency.id,
    entity_id=entity.id,
)
revenue = Account(
    name="Revenue Account",
    account_type=Account.AccountType.OPERATING_REVENUE,
    currency_id=currency.id,
    entity_id=entity.id,
)
client = Account(
    name="Client Account",
    account_type=Account.AccountType.RECEIVABLE,
    currency_id=currency.id,
    entity_id=entity.id,
)
supplier = Account(
    name="Supplier Account",
    account_type=Account.AccountType.PAYABLE,
    currency_id=currency.id,
    entity_id=entity.id,
)
session.add_all([bank, revenue, client, supplier])
session.commit()
```

Notice the account codes: you didn't set them. Each type has a code range in
`config.toml` (bank accounts start at 1000, receivables at 1100, and so on),
and the library numbers new accounts within their range automatically.

## Categories

Accounts of the same type can be grouped into **Categories** — for example,
grouping several `OPERATING_EXPENSE` accounts into "Payroll" and "Rent".
Categories are optional, but reports organize accounts by category when one
is set, which is what makes a balance sheet readable instead of a wall of
names.

## Balances

An account's balance is *computed*, never stored as a mutable number — it is
the sum of its ledger entries. You can ask for balances over any window:

```python
from python_accounting.models import Account

account = session.get(Account, bank.id)

# Balance movement between two dates
movement = account.balance_movement(session, start_date, end_date)

# Opening and closing balances for a period
opening = account.opening_balance(session, end_date)
closing = account.closing_balance(session, end_date)
```

Because balances are derived from the ledger, and the ledger is
hash-chained, a balance can't be wrong without the tamper being detectable.
See [how the hash chain works](../explanation/ledger-hashing.md).

!!! tip "The control account"

    The `CONTROL` account type is special: it's where tax amounts are held
    between collection and remittance. You'll meet it in
    [Taxes](04-taxes.md).

Next: moving money between accounts — transactions.
