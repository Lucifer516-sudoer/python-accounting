# Getting started

## Installation

python-accounting requires Python 3.10+ and installs from PyPI:

```bash
pip install python-accounting
```

The library ships with SQLite support built in. The MySQL and Postgres
drivers are optional extras because both need system headers
(`libmysqlclient` / `libpq`) to build — install the one you need:

=== "Postgres"

    ```bash
    pip install python-accounting[postgres]
    ```

=== "MySQL"

    ```bash
    pip install python-accounting[mysql]
    ```

## The 30-second mental model

Everything in python-accounting hangs off three ideas:

1. **An `Entity` is a company.** Every row in the database belongs to one,
   and every query is automatically filtered to the entity your session is
   bound to.
2. **`Account`s hold money.** They form a chart of accounts, typed by
   `Account.AccountType` (BANK, RECEIVABLE, OPERATING_REVENUE, …).
3. **`Transaction`s move money.** Each transaction type (CashSale,
   ClientInvoice, SupplierBill, …) posts its `LineItem`s to the ledger —
   debits on one side, credits on the other, always balanced.

You talk to all of it through an `AccountingSession` — a SQLAlchemy session
that knows which entity it serves, soft-deletes instead of destroying, and
hash-chains every ledger row on insert.

## Create the engine

```python
from python_accounting.database import get_engine

engine = get_engine("sqlite:///accounting.db")
```

## First session

```python
from python_accounting.database import get_session
from python_accounting.models import Entity, Currency

with get_session(engine) as session:
    entity = Entity(name="Example Company")
    session.add(entity)
    session.commit()
    # Creating the first Entity automatically opens its first
    # Reporting Period — the accounting year the books live in.

    currency = Currency(name="US Dollars", code="USD", entity_id=entity.id)
    session.add(currency)
    session.commit()
```

From here, follow the [Learn tutorial](learn/index.md) to build a full chart
of accounts and post real transactions — or jump straight to the
[Guides](guides/index.md) if you already know double-entry bookkeeping and
just want the API.

## Where to next

- [Learn — the tutorial](learn/index.md): six short chapters, entities to reports.
- [Guides](guides/index.md): task-oriented pages for reports, taxes, compound entries.
- [Explanation](explanation/index.md): *why* the ledger is hash-chained, how
  soft delete works, what entity isolation really does.
- [API reference](reference/index.md): every public module, generated from
  the source.
