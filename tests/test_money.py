"""Contract tests for the money seam (PLAN T10.2, red step).

`net_ledger`, `net_balance` and `line_item_total` do not exist yet in
`python_accounting.utils.money` (D-017 §2 and §4). These tests encode their
contract so the T10.4 implementation lands against a failing suite:

- `net_ledger(session, *filters)` nets Ledger rows: debits minus credits,
  where the side discrimination (`Ledger.entry_type` against
  `Balance.BalanceType`) lives inside the seam. Callers pass only scope
  filters as SQLAlchemy column expressions.
- `net_balance(session, *filters)` is the same shape over Balance rows
  (`Balance.balance_type` discrimination).
- `line_item_total(line_item)` is the pre-tax extended amount
  `line_item.amount * line_item.quantity`.

Every test here is expected to FAIL at collection (ImportError) until T10.4
lands.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from python_accounting.database.session import AccountingSession
from python_accounting.models import (
    Account,
    Balance,
    Currency,
    Entity,
    Ledger,
    LineItem,
    Transaction,
)
from python_accounting.transactions import ClientInvoice
from python_accounting.utils.money import (
    line_item_total,
    net_balance,
    net_ledger,
)


def _customer_and_revenue(
    session: AccountingSession,
    entity: Entity,
    currency: Currency,
) -> tuple[Account, Account]:
    """Mirrors tests/test_schedule_clearances.py::_accounts (receivable side)."""
    customer = Account(
        name="Test customer",
        account_type=Account.AccountType.RECEIVABLE,
        currency_id=currency.id,
        entity_id=entity.id,
    )
    revenue = Account(
        name="Test revenue",
        account_type=Account.AccountType.OPERATING_REVENUE,
        currency_id=currency.id,
        entity_id=entity.id,
    )
    session.add_all([customer, revenue])
    session.flush()
    return customer, revenue


def _period_start(session: AccountingSession) -> datetime:
    """Start of the entity's open reporting period (year-independent dates)."""
    return session.entity.reporting_period.interval()["start"]


def test_net_ledger_debit_side_is_positive(session, entity, currency, post_document):
    """A posted ClientInvoice debits the receivable and credits the revenue."""
    customer, revenue = _customer_and_revenue(session, entity, currency)
    invoice = post_document(
        ClientInvoice,
        customer,
        revenue,
        _period_start(session) + timedelta(days=5),
        "100",
    )

    receivable_net = net_ledger(
        session,
        Ledger.post_account_id == customer.id,
        Ledger.entity_id == entity.id,
    )
    assert isinstance(receivable_net, Decimal)
    assert receivable_net == Decimal("100")

    assert net_ledger(
        session,
        Ledger.post_account_id == revenue.id,
        Ledger.entity_id == entity.id,
    ) == Decimal("-100")

    # Both sides of the one transaction net to zero: debits == credits.
    assert net_ledger(session, Ledger.transaction_id == invoice.id) == Decimal("0")


def test_net_ledger_date_scoping(session, entity, currency, post_document):
    """transaction_date filters include and exclude ledger rows correctly."""
    customer, revenue = _customer_and_revenue(session, entity, currency)
    start = _period_start(session)
    post_document(ClientInvoice, customer, revenue, start + timedelta(days=5), "100")
    post_document(ClientInvoice, customer, revenue, start + timedelta(days=15), "50")
    cutoff = start + timedelta(days=10)

    scope = [Ledger.post_account_id == customer.id, Ledger.entity_id == entity.id]
    assert net_ledger(session, *scope, Ledger.transaction_date >= cutoff) == Decimal(
        "50"
    )
    assert net_ledger(session, *scope, Ledger.transaction_date <= cutoff) == Decimal(
        "100"
    )
    assert net_ledger(session, *scope) == Decimal("150")


def test_net_ledger_empty_scope_is_zero(session, entity, currency):
    """An account with no ledger rows nets to Decimal 0."""
    customer, _revenue = _customer_and_revenue(session, entity, currency)
    result = net_ledger(
        session,
        Ledger.post_account_id == customer.id,
        Ledger.entity_id == entity.id,
    )
    assert isinstance(result, Decimal)
    assert result == Decimal("0")


def test_net_balance_zero_and_sides(session, entity, currency):
    """Balance rows net by side: debits minus credits, Decimal 0 when empty."""
    bank = Account(
        name="Test bank",
        account_type=Account.AccountType.BANK,
        currency_id=currency.id,
        entity_id=entity.id,
    )
    session.add(bank)
    session.flush()

    period = session.entity.reporting_period
    scope = [
        Balance.account_id == bank.id,
        Balance.entity_id == entity.id,
        Balance.reporting_period_id == period.id,
        Balance.currency_id == currency.id,
    ]

    empty = net_balance(session, *scope)
    assert isinstance(empty, Decimal)
    assert empty == Decimal("0")

    # Opening Balance rows mirror tests/test_account.py:270-304: the date is
    # a year back (before the period start, so validate() accepts it) and
    # currency_id/reporting_period_id are stamped by Balance.validate.
    date = datetime.now() - relativedelta(days=365)
    session.add(
        Balance(
            transaction_date=date,
            transaction_type=Transaction.TransactionType.CLIENT_INVOICE,
            amount=100,
            balance_type=Balance.BalanceType.DEBIT,
            account_id=bank.id,
            entity_id=entity.id,
        )
    )
    session.flush()
    assert net_balance(session, *scope) == Decimal("100")

    session.add(
        Balance(
            transaction_date=date,
            transaction_type=Transaction.TransactionType.JOURNAL_ENTRY,
            amount=25,
            balance_type=Balance.BalanceType.CREDIT,
            account_id=bank.id,
            entity_id=entity.id,
        )
    )
    session.flush()
    assert net_balance(session, *scope) == Decimal("75")


def test_line_item_total_from_posted_document(session, entity, currency, post_document):
    """line_item_total is the extended amount of a persisted line item."""
    customer, revenue = _customer_and_revenue(session, entity, currency)
    invoice = post_document(
        ClientInvoice,
        customer,
        revenue,
        _period_start(session) + timedelta(days=5),
        "100",
    )
    line_item = next(iter(invoice.line_items))
    assert line_item_total(line_item) == line_item.amount * line_item.quantity
    assert line_item_total(line_item) == Decimal("100")


def test_line_item_total_transient_quantity():
    """A transient LineItem with quantity > 1 extends by quantity."""
    line_item = LineItem(amount=Decimal("50"), quantity=3)
    assert line_item_total(line_item) == Decimal("150")
