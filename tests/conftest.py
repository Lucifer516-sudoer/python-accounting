from collections.abc import Callable, Iterator
from datetime import datetime, tzinfo
from decimal import Decimal

import pytest
from pytest import MonkeyPatch
from sqlalchemy import Engine, create_engine
from python_accounting.models import (
    Account,
    Base,
    Currency,
    Entity,
    LineItem,
    Transaction,
)
from python_accounting.database.session import AccountingSession, get_session
from python_accounting.config import config


@pytest.fixture
def engine() -> Engine:
    database = config.database
    engine = create_engine(database["url"], echo=database["echo"])
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine: Engine) -> Iterator[AccountingSession]:
    with get_session(engine) as session:
        yield session


@pytest.fixture
def entity(session: AccountingSession) -> Entity:
    entity = Entity(name="Test Entity")
    session.add(entity)
    session.commit()
    fetched = session.get(Entity, entity.id)
    assert fetched is not None
    return fetched


@pytest.fixture
def currency(session: AccountingSession, entity: Entity) -> Currency:
    currency = Currency(name="US Dollars", code="USD", entity_id=entity.id)
    session.add(currency)
    session.commit()
    fetched = session.get(Currency, currency.id)
    assert fetched is not None
    return fetched


@pytest.fixture
def post_document(session: AccountingSession) -> Callable[..., Transaction]:
    """Returns a function that posts a single line document to the given account."""

    def post(
        document_type: type[Transaction],
        account: Account,
        line_account: Account,
        date: datetime,
        amount: str | int | Decimal,
    ) -> Transaction:
        document = document_type(
            narration="Test document",
            transaction_date=date,
            account_id=account.id,
            entity_id=account.entity_id,
        )
        session.add(document)
        session.flush()
        line = LineItem(
            narration="Test line",
            account_id=line_account.id,
            amount=Decimal(amount),
            entity_id=account.entity_id,
        )
        session.add(line)
        session.flush()
        document.line_items.add(line)
        session.flush()
        document.post(session)
        return document

    return post


@pytest.fixture
def fixed_today(monkeypatch: MonkeyPatch) -> datetime:
    """Freezes today to midday on 31 January of the current year for reports and bulk assignment."""
    year = datetime.now().year

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "FixedDateTime":
            return cls(year, 1, 31, 12, tzinfo=tz)

        @classmethod
        def today(cls) -> "FixedDateTime":
            return cls.now()

    monkeypatch.setattr("python_accounting.utils.dates.datetime", FixedDateTime)
    monkeypatch.setattr("python_accounting.mixins.assigning.datetime", FixedDateTime)
    return FixedDateTime.today()
