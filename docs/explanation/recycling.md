# Recycling: soft delete with a memory

In accounting, "delete" is almost always a lie. You don't delete an invoice;
you *reverse* it, and the reversal is itself a record. Regulators, auditors
and future-you all want the original to still exist.

python-accounting takes that seriously: **`session.delete()` never destroys
anything.**

## What actually happens

Every model inherits from `Recyclable`, which carries a `deleted_at`
timestamp. When you call:

```python
session.delete(account)
```

the library:

1. sets `deleted_at` on the row,
2. writes a **`Recycled`** audit row recording *what* was deleted and *when*,
3. commits.

The row is gone from every normal query — but not from the database, and not
from the audit trail.

## The invisible filter

The soft-delete filter is not something you write. It's injected into every
query the session runs by SQLAlchemy's `do_orm_execute` event listener, so
deleted rows are invisible everywhere — `session.query()`, `session.get()`,
relationships, all of it. This is also why `session.get()` is overridden in
the library: the native `Session.get()` can serve rows from the identity
map, bypassing the filter, and that path is deliberately closed off.

## The full lifecycle

```python
session.delete(obj)    # soft delete: sets deleted_at, records Recycled, commits
session.restore(obj)   # undo: clears deleted_at (returns False if destroyed)
session.erase(obj)     # real delete of the row (Recycled record remains)
session.destroy(obj)   # permanent: erases the row AND its audit trail
```

`Assignment` objects are the exception: deleting an assignment routes to
`erase()` automatically, because an assignment is a *correction*, not a
record worth keeping soft-deleted.

!!! warning "Deleted rows are invisible, not gone"

    Anything that queries the database directly — raw SQL, a DBA tool, a
    report written against the connection instead of the session — will see
    soft-deleted rows. The filter lives in the session, not the database.

## Why an audit row *and* a timestamp?

The `deleted_at` column answers "is this row live?". The `Recycled` row
answers "what happened here?" — including for `erase()` and `destroy()`,
which remove the original row entirely. The audit trail outlives the data,
which is the whole point.
