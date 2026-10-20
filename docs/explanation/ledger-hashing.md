# The ledger hash chain

A database can be edited. `UPDATE ledger SET amount = 999 WHERE id = 42` is
a perfectly legal SQL statement, and no application-level validation will
ever see it. For accounting data that's not a bug — it's an *existential
threat*: the books are only worth anything if you can prove nobody cooked
them.

python-accounting's answer is a **hash chain** — the same idea behind
blockchains and signed certificate logs, applied to your ledger.

## How it works

Every `Ledger` row carries a `hash` column. When a row is inserted, an
`after_insert` listener computes its hash from:

- the row's own content — transaction date, entry type, amount (rounded to
  4 decimal places and normalized), entity, transaction, currency, both
  accounts, line item and tax
- **the hash of the previous row** (`id - 1`), or a configured salt for the
  very first row

```python
digest = hashlib.sha256(
    ",".join(
        str(field)
        for field in [
            transaction_date, entry_type, amount,
            previous_row_hash,  # ← the chain
            entity_id, transaction_id, currency_id,
            post_account_id, folio_account_id, line_item_id, tax_id,
        ]
    ).encode()
).hexdigest()
```

Each row's hash therefore *depends* on every row before it. Change any
field in any row and its own hash no longer matches — and every hash after
it is invalidated too, because they all embedded the tampered row's hash.

## What this buys you

- **Tamper detection.** You can't prove who changed a row, but you can
  prove *that* it changed, and exactly where the chain breaks.
- **No trusted-admin problem.** Even someone with direct database access
  can't alter history without leaving evidence.
- **Derived data you can trust.** Account balances and reports are computed
  from the ledger. If the chain verifies, the balances are the arithmetic
  of untampered postings.

## What it doesn't buy you

- **Immutability.** The chain detects tampering; it doesn't prevent it.
  Pair it with database permissions for that.
- **Non-repudiation.** There's no per-user signature, so you know *what*
  changed, not *who*.

## The cost — and why it's worth it

The chain makes ledger rows effectively append-only: any change to the
*shape* of ledger data (columns, hashing algorithm, the fields that feed the
digest) breaks verification for existing data. That's why the hashing
algorithm and row shape are treated as frozen public API in this library —
the smoke test in the Docker build verifies the chain end to end on every
release.

!!! note "Configuration"

    The algorithm and salt come from `config.toml` (`[hashing]`), so the
    defaults can be tuned per deployment — but only *before* data exists.
    Changing them after the fact breaks every existing chain.
