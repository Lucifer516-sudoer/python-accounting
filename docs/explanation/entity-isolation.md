# Entity isolation

One database, many companies. That's the deployment most accounting systems
want — but it's also the deployment where a missing `WHERE entity_id = ?`
leaks Company A's invoices into Company B's reports. In accounting, that's
not just a bug; it's a breach.

python-accounting makes the leak **structurally impossible**.

## The mechanism

Every query that goes through an `AccountingSession` passes through
SQLAlchemy's `do_orm_execute` event, where the library injects an
entity-isolation filter — `WHERE entity_id = <session's entity>` — into the
statement. The same listener injects the soft-delete filter described in
[Recycling](recycling.md).

The consequences are deliberate:

- **You never write the filter.** There is no `filter_by(entity_id=...)`
  discipline to forget. The session does it, every time, on every statement.
- **`session.get()` can't bypass it.** The native `Session.get()` can serve
  rows straight from the identity map without emitting SQL — which would
  skip the injected filter. The library overrides `get()` to route through
  `select()` instead, so even identity-map hits are isolated.
- **Adding a row without an entity fails.** The session's `entity` attribute
  is set automatically when the first object transitions from transient to
  pending. An object with `entity_id=None` raises `MissingEntityError`
  rather than silently becoming everyone's data.

## Opting out — deliberately

Some operations legitimately need to cross entities: migrations, global
admin tooling, data repair. The filters can be toggled through engine
execution options, threaded into the session:

```python
engine = get_engine(url, execution_options={"ignore_isolation": True})
```

The same mechanism controls `include_deleted`. Both flags live in
`session.info`, so a session knows exactly which rules it's currently
exempt from — and the exemption is visible at the call site, not buried in
a query.

## Why not row-level security?

Postgres RLS is a great tool, but it's database-specific, and
python-accounting runs on SQLite, MySQL and Postgres alike. The
session-injected filter gives the same guarantee on every backend, and it
composes with the soft-delete filter in one place. If you deploy on Postgres
and want belt-and-braces, RLS stacks cleanly *on top* — the library won't
get in its way.
