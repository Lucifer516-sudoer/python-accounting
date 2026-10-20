"""Schema snapshot: table names and per-column nullability are pinned.

Any annotation or mapping change that alters generated DDL fails here
(SPEC A10, DECISIONS D-005/D-006). The golden values below were captured
mechanically from ``Base.metadata`` on 2026-10-16, before the 2.0 remodel,
and must stay byte-identical: table names are the public contract that
constrains the ``__tablename__`` de-magicization, and nullability is the
per-column contract that the ``| None`` annotation pass must not move.

Update this file only as part of a deliberate, recorded schema change.
"""

import python_accounting.transactions  # noqa: F401
from sqlalchemy.orm import configure_mappers

from python_accounting.models import Base

GOLDEN: dict[str, list[tuple[str, bool]]] = {
    "account": [
        ("account_code", False),
        ("account_type", False),
        ("category_id", True),
        ("currency_id", False),
        ("description", True),
        ("entity_id", False),
        ("id", False),
        ("name", False),
    ],
    "assignment": [
        ("amount", False),
        ("assigned_id", False),
        ("assigned_no", False),
        ("assigned_type", False),
        ("assignment_date", False),
        ("created_at", False),
        ("entity_id", False),
        ("id", False),
        ("transaction_id", True),
        ("updated_at", False),
    ],
    "balance": [
        ("account_id", False),
        ("amount", False),
        ("balance_type", False),
        ("currency_id", False),
        ("entity_id", False),
        ("id", False),
        ("reference", True),
        ("reporting_period_id", False),
        ("transaction_date", False),
        ("transaction_no", False),
        ("transaction_type", False),
    ],
    "category": [
        ("category_account_type", False),
        ("entity_id", False),
        ("id", False),
        ("name", False),
    ],
    "currency": [
        ("code", False),
        ("entity_id", False),
        ("id", False),
        ("name", False),
    ],
    "entity": [
        ("currency_id", True),
        ("id", False),
        ("locale", False),
        ("mid_year_balances", False),
        ("multi_currency", False),
        ("name", False),
        ("reporting_period_id", True),
        ("year_start", False),
    ],
    "ledger": [
        ("amount", False),
        ("currency_id", False),
        ("entity_id", False),
        ("entry_type", False),
        ("folio_account_id", False),
        ("hash", True),
        ("id", False),
        ("line_item_id", True),
        ("post_account_id", False),
        ("tax_id", True),
        ("transaction_date", False),
        ("transaction_id", False),
    ],
    "line_item": [
        ("account_id", False),
        ("amount", False),
        ("credited", False),
        ("entity_id", False),
        ("id", False),
        ("narration", False),
        ("quantity", False),
        ("tax_id", True),
        ("tax_inclusive", False),
        ("transaction_id", True),
    ],
    "recyclable": [
        ("created_at", False),
        ("deleted_at", True),
        ("destroyed_at", True),
        ("id", False),
        ("recycled_type", False),
        ("updated_at", False),
    ],
    "recycled": [
        ("created_at", False),
        ("entity_id", False),
        ("id", False),
        ("recycled_id", False),
        ("restored_at", True),
        ("updated_at", False),
    ],
    "reporting_period": [
        ("calendar_year", False),
        ("entity_id", False),
        ("id", False),
        ("period_count", False),
        ("status", False),
    ],
    "tax": [
        ("account_id", True),
        ("code", False),
        ("entity_id", False),
        ("id", False),
        ("name", False),
        ("rate", False),
    ],
    "transaction": [
        ("account_id", False),
        ("compound", False),
        ("credited", False),
        ("currency_id", False),
        ("entity_id", False),
        ("id", False),
        ("main_account_amount", False),
        ("narration", False),
        ("reference", True),
        ("transaction_date", False),
        ("transaction_no", True),
        ("transaction_type", False),
    ],
    "user": [
        ("created_at", False),
        ("email", False),
        ("entity_id", False),
        ("id", False),
        ("name", False),
        ("updated_at", False),
    ],
}


def test_schema_snapshot() -> None:
    """Table names and per-column nullability match the 2.0 baseline exactly."""
    configure_mappers()
    tables = Base.metadata.tables

    assert sorted(tables) == sorted(GOLDEN), (
        f"table-name drift: {sorted(tables)} != {sorted(GOLDEN)}"
    )

    for name, golden_columns in GOLDEN.items():
        actual = sorted((col.name, bool(col.nullable)) for col in tables[name].columns)
        assert actual == golden_columns, (
            f"schema drift in table {name!r}: expected {golden_columns}, got {actual}"
        )
