#!/usr/bin/env python
"""Install smoke test for the python-accounting wheel.

Runs a full double-entry round-trip against the *installed* package:

  * asserts the import resolves to site-packages, never to a source checkout
    (a checkout has ``python_accounting/`` next to ``pyproject.toml``, so a
    plain ``uv run`` would smoke test the source tree instead of the wheel);
  * imports ``config``, which only succeeds when ``config.toml`` sits at the
    root of site-packages -- the wheel layout that a source checkout cannot
    verify (see ``scripts/check_wheel_layout.py``);
  * creates the schema, posts a journal entry and verifies the ledger hash
    chain with ``Transaction.is_secure()``.

Databases: in-memory sqlite, plus any URLs given as arguments or listed in the
whitespace-separated ``SMOKE_URLS`` environment variable, e.g.::

    SMOKE_URLS="postgresql+psycopg2://user:pass@host/db mysql+mysqldb://..." \
        python scripts/smoke_install.py

Exits 0 if every database round-trips, 1 otherwise.
"""

import importlib.metadata
import importlib.util
import os
import pathlib
import sys
from datetime import datetime
from decimal import Decimal

SQLITE_URL = "sqlite://"


def assert_installed() -> None:
    """Refuse to smoke test a source checkout: only an installed wheel counts."""
    spec = importlib.util.find_spec("python_accounting")
    locations = list(getattr(spec, "submodule_search_locations", None) or [])
    if not locations:
        raise SystemExit(
            "python_accounting is not importable. Install the wheel first:\n"
            "    uv build --wheel\n"
            "    uv venv /tmp/smoke\n"
            "    uv pip install --python /tmp/smoke/bin/python dist/*.whl\n"
            "    /tmp/smoke/bin/python scripts/smoke_install.py\n"
        )
    for location in locations:
        parent = pathlib.Path(location).parent
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            raise SystemExit(
                f"python_accounting is imported from a source checkout ({parent}),\n"
                "not from an installed wheel. config.toml is resolved as\n"
                "<package>/../config.toml, so only an installed package exercises the\n"
                "real resolution path. Install the wheel into a clean environment:\n"
                "\n"
                "    uv build --wheel\n"
                "    uv venv /tmp/smoke\n"
                "    uv pip install --python /tmp/smoke/bin/python dist/*.whl\n"
                "    /tmp/smoke/bin/python scripts/smoke_install.py\n"
            )


def roundtrip(url: str) -> None:
    """Create a schema, post a journal entry and verify the ledger hash chain."""
    from sqlalchemy import create_engine

    from python_accounting.database.session import get_session
    from python_accounting.models import Account, Base, Currency, Entity, LineItem
    from python_accounting.transactions import JournalEntry

    engine = create_engine(url)
    Base.metadata.create_all(engine)

    with get_session(engine) as session:
        entity = Entity(name="Smoke Entity")
        session.add(entity)
        session.commit()

        currency = Currency(name="US Dollars", code="USD", entity_id=entity.id)
        session.add(currency)
        session.commit()

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

        entry = JournalEntry(
            narration="Smoke journal entry",
            transaction_date=datetime.now(),
            account_id=bank.id,
            entity_id=entity.id,
        )
        session.add(entry)
        session.flush()

        line = LineItem(
            narration="Smoke line item",
            account_id=revenue.id,
            amount=Decimal("100"),
            entity_id=entity.id,
        )
        session.add(line)
        session.flush()
        entry.line_items.add(line)
        session.flush()
        entry.post(session)

        ledger = entry.ledgers[0]
        assert ledger.post_account.name == "Bank Account"
        assert ledger.folio_account.name == "Revenue Account"
        assert ledger.line_item.amount == Decimal("100")
        assert ledger.hash, "the ledger hash was not recorded on insert"
        assert entry.is_secure(session), "the ledger hash chain failed to verify"

    engine.dispose()


def main() -> int:
    assert_installed()

    from python_accounting.config import config

    # Importing config at all proves config.toml resolved from site-packages;
    # these keys prove the right file was read.
    assert config.hashing["algorithm"], "config.toml was not loaded"
    assert config.dates["short"], "config.toml was not loaded"

    version = importlib.metadata.version("python-accounting")
    print(f"python-accounting {version} on Python {sys.version.split()[0]}")

    urls = sys.argv[1:] + os.environ.get("SMOKE_URLS", "").split()
    for url in [SQLITE_URL, *urls]:
        roundtrip(url)
        print(f"smoke OK: {url}")

    print(f"install smoke passed for {1 + len(urls)} database(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
