---
title: Home
hide:
  - navigation
  - toc
---

# python-accounting

<style>
  .md-typeset h1 { display: none; }
</style>

<div class="hero" markdown>

<div class="hero-inner" markdown>

# Double-entry accounting, <span class="gradient-text">without the spreadsheet</span>

**python-accounting** is the most comprehensive double-entry bookkeeping
library for Python. Ledgers, journals, taxes, clearing, financial reports
compatible with IFRS and GAAP — and a hash chain that catches anyone who
touches the database behind your back.

[:material-rocket-launch: Get started](getting-started.md){ .md-button .md-button--primary }
[:material-book-open-variant: Learn](learn/index.md){ .md-button }
[:material-api: API reference](reference/index.md){ .md-button }

</div>

</div>

<div class="grid cards" markdown>

-   :material-database-lock: **Tamper-evident by design**
    ---

    Every posting is hash-chained to the one before it. Direct database
    edits don't just look wrong — they *verify* wrong.

    [:octicons-arrow-right-24: How the hash chain works](explanation/ledger-hashing.md)

-   :material-domain: **Multi-entity, isolated**
    ---

    One database, many companies. Every query is automatically filtered to
    the session's entity — cross-tenant leaks are structurally impossible.

    [:octicons-arrow-right-24: Entity isolation](explanation/entity-isolation.md)

-   :material-undo-variant: **Soft delete, full audit trail**
    ---

    `session.delete()` never destroys anything. It records *who* deleted
    *what*, and `restore()` brings it back.

    [:octicons-arrow-right-24: Recycling](explanation/recycling.md)

-   :material-chart-box-outline: **IFRS & GAAP reports**
    ---

    Income statement, balance sheet, cashflow, trial balance, aging
    schedules — generated from your ledger in a few lines.

    [:octicons-arrow-right-24: Reports](guides/index.md)

-   :material-currency-usd: **Decimal to the bone**
    ---

    Money is `Decimal` everywhere. No floats drift into your balance sheet,
    ever.

    [:octicons-arrow-right-24: Why it matters](explanation/index.md)

-   :material-cog-outline: **Config-driven**
    ---

    Account types, code ranges, transaction prefixes, report sections and
    aging brackets come from a TOML file you can edit — not hardcoded
    constants.

    [:octicons-arrow-right-24: Configuration](guides/index.md)

</div>

## Quickstart

Install the library:

```bash
pip install python-accounting
```

Create an entity, a currency, a chart of accounts, and post your first
transaction:

```python
from python_accounting.database import get_session
from python_accounting.models import (
    Account, Currency, Entity, Tax, Transaction, LineItem
)
from python_accounting.transactions import CashSale

with get_session(engine) as session:
    # One entity = one company. The session is bound to it from now on.
    entity = Entity(name="Example Company")
    session.add(entity)
    session.commit()  # a Reporting Period is set up automatically

    currency = Currency(name="US Dollars", code="USD", entity_id=entity.id)
    session.add(currency)
    session.commit()

    # The chart of accounts
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
    session.add_all([bank, revenue])
    session.commit()

    # Sell something for cash
    sale = CashSale(
        narration="Sale of goods",
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
    sale.post(session)

    print(bank.balance(session))  # 100
```

That's the whole loop: **Entity → Accounts → Transaction → LineItems → post**.
The [Learn tutorial](learn/index.md) walks through it step by step, and the
[Guides](guides/index.md) cover reports, taxes and compound entries.
