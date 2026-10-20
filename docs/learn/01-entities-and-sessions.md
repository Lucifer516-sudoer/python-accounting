# Entities & Sessions

In double-entry bookkeeping, *the books belong to someone*. Before a single
account exists, you need to know whose books they are. In python-accounting
that someone is an **Entity** — a company, a sole trader, a charity, any
legal or organizational unit that keeps its own books.

## The Entity

```python
from python_accounting.models import Entity

entity = Entity(name="Example Company")
```

That's it. An Entity has a name, and everything else in the database will
reference it: accounts, transactions, taxes, reporting periods.

## The session knows whose books it's keeping

You never pass `entity` around manually. Instead, the **session** is bound
to an entity the first time you add one to it, and from that moment every
query through that session is automatically filtered to that entity:

```python
from python_accounting.database import get_session
from python_accounting.models import Entity, Currency

with get_session(engine) as session:
    entity = Entity(name="Example Company")
    session.add(entity)
    session.commit()  # the session is now bound to this entity

    currency = Currency(name="US Dollars", code="USD", entity_id=entity.id)
    session.add(currency)
    session.commit()
```

This is the library's answer to multi-tenancy: one database can hold many
companies, and a session for Company A physically cannot see Company B's
rows. Not "is filtered out by your WHERE clause" — the filter is injected
into every query the session runs, including `session.get()`. If you try to
add a row with `entity_id=None`, you get a `MissingEntityError`.

!!! note "One database, many companies"

    To keep books for a second company, open a second session and add a
    second Entity to it. The two companies' data coexist in the same
    database, invisible to each other. See
    [Entity isolation](../explanation/entity-isolation.md) for how the
    machinery works.

## The Reporting Period opens itself

Accounting happens in *years*. When you commit the first Entity, the library
automatically creates its first **Reporting Period** — the accounting year
the books live in. When January 1st rolls around and you post a transaction
dated in the new year, the library rolls the period forward for you.

You will rarely touch `ReportingPeriod` directly, but it's why transaction
dates matter and why reports are always *for a period*.

## Currencies

Money in python-accounting is always in a currency, and always a `Decimal`.
An Entity can keep books in several currencies; every Account and
Transaction declares which one it uses:

```python
from python_accounting.models import Currency

usd = Currency(name="US Dollars", code="USD", entity_id=entity.id)
eur = Currency(name="Euros", code="EUR", entity_id=entity.id)
session.add_all([usd, eur])
session.commit()
```

!!! warning "No floats, ever"

    Amounts are `Decimal` end to end. If you pass a `float` where an amount
    is expected, you'll get errors rather than silently wrong arithmetic —
    `0.1 + 0.2` is not a thing your balance sheet should have opinions about.

## What we have so far

- An **Entity** — the company whose books these are
- A **Currency** — the unit every amount is denominated in
- A **Reporting Period** — opened automatically, rolled forward automatically

Next: the chart of accounts — the places money can live.
