"""Tests for the typed Account statement seam (PLAN T4.0b, decision D-016).

`Account.statement()` splits into `schedule_outstanding()` (the aging half,
returning an `OutstandingSchedule` of frozen `ScheduleRow`s) and
`statement_running()` (the running-balance half, returning an
`AccountStatement` of frozen `StatementRow`s). The legacy `statement()`
remains as a restamping shim whose dict shape must stay byte-identical.

The result dataclasses live in `python_accounting.models.account`. They are
resolved as module attributes inside each test, only after the new Account
method has already been called, so that before T4.0b lands every test fails
with AttributeError (the missing method) instead of an ImportError at
collection time.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from python_accounting.exceptions import InvalidAccountTypeError
from python_accounting.models import (
    Account,
    Assignment,
    Balance,
    Transaction,
    account as account_models,
)
from python_accounting.transactions import (
    CashPurchase,
    CashSale,
    ClientInvoice,
    ClientReceipt,
)


def _accounts(session, entity, currency, payable=False):
    """Mirrors tests/test_schedule_clearances.py::_accounts."""
    account = Account(
        name="Test supplier" if payable else "Test customer",
        account_type=(
            Account.AccountType.PAYABLE if payable else Account.AccountType.RECEIVABLE
        ),
        currency_id=currency.id,
        entity_id=entity.id,
    )
    line_account = Account(
        name="Test expense" if payable else "Test revenue",
        account_type=(
            Account.AccountType.OPERATING_EXPENSE
            if payable
            else Account.AccountType.OPERATING_REVENUE
        ),
        currency_id=currency.id,
        entity_id=entity.id,
    )
    bank = Account(
        name="Test bank",
        account_type=Account.AccountType.BANK,
        currency_id=currency.id,
        entity_id=entity.id,
    )
    session.add_all([account, line_account, bank])
    session.flush()
    return account, line_account, bank


def _assign(session, subject, payment, date, amount):
    """Mirrors tests/test_schedule_clearances.py::_assign."""
    assignment = Assignment(
        assignment_date=date,
        transaction_id=payment.id,
        assigned_id=subject.id,
        assigned_type=subject.__class__.__name__,
        entity_id=subject.entity_id,
        amount=Decimal(amount),
    )
    session.add(assignment)
    session.commit()


def _post_running_entries(session, entity, currency, post_document):
    """Posts two cash sales and one cash purchase to a new bank account.

    Returns (bank, [sale1, sale2, purchase]) with ledger effects on `bank` of
    +100, +50 and -30 respectively.
    """
    bank = Account(
        name="Test bank",
        account_type=Account.AccountType.BANK,
        currency_id=currency.id,
        entity_id=entity.id,
    )
    revenue = Account(
        name="Test revenue",
        account_type=Account.AccountType.OPERATING_REVENUE,
        currency_id=currency.id,
        entity_id=entity.id,
    )
    expense = Account(
        name="Test expense",
        account_type=Account.AccountType.OPERATING_EXPENSE,
        currency_id=currency.id,
        entity_id=entity.id,
    )
    session.add_all([bank, revenue, expense])
    session.flush()

    year = datetime.now().year
    sale1 = post_document(CashSale, bank, revenue, datetime(year, 1, 10), "100")
    sale2 = post_document(CashSale, bank, revenue, datetime(year, 1, 20), "50")
    purchase = post_document(CashPurchase, bank, expense, datetime(year, 1, 25), "30")
    return bank, [sale1, sale2, purchase]


class TestAccountStatement:
    """The typed schedule/running seam and the legacy statement() shim."""

    def test_schedule_outstanding_rows_and_aggregates(
        self, session, entity, currency, post_document
    ):
        """schedule_outstanding returns frozen ScheduleRows with Decimal aggregates."""
        year = datetime.now().year
        account, revenue, bank = _accounts(session, entity, currency)
        invoice = post_document(
            ClientInvoice, account, revenue, datetime(year, 1, 15), "100"
        )
        payment = post_document(
            ClientReceipt, account, bank, datetime(year, 1, 20), "40"
        )
        _assign(session, invoice, payment, datetime(year, 1, 20), "40")

        cutoff = datetime(year, 1, 31)
        result = account.schedule_outstanding(session, end_date=cutoff)

        assert isinstance(result, account_models.OutstandingSchedule)
        assert len(result.transactions) == 1

        row = result.transactions[0]
        assert isinstance(row, account_models.ScheduleRow)
        assert row.entry is invoice
        assert isinstance(row.cleared_amount, Decimal)
        assert isinstance(row.uncleared_amount, Decimal)
        assert row.cleared_amount == Decimal("40")
        assert row.uncleared_amount == Decimal("60")
        assert row.age == (cutoff - invoice.transaction_date).days == 16

        assert isinstance(result.total_amount, Decimal)
        assert isinstance(result.cleared_amount, Decimal)
        assert isinstance(result.uncleared_amount, Decimal)
        assert result.total_amount == sum(r.entry.amount for r in result.transactions)
        assert result.cleared_amount == sum(
            r.cleared_amount for r in result.transactions
        )
        assert result.uncleared_amount == sum(
            r.uncleared_amount for r in result.transactions
        )
        assert result.total_amount == Decimal("100")
        assert result.cleared_amount == Decimal("40")
        assert result.uncleared_amount == Decimal("60")

    def test_statement_running_rows_and_totals(
        self, session, entity, currency, post_document
    ):
        """statement_running returns StatementRows with a running balance."""
        bank, entries = _post_running_entries(session, entity, currency, post_document)

        result = bank.statement_running(session)

        assert isinstance(result, account_models.AccountStatement)
        assert isinstance(result.opening_balance, Decimal)
        assert result.opening_balance == 0

        assert len(result.transactions) == 3
        for i, entry in enumerate(entries):
            row = result.transactions[i]
            assert isinstance(row, account_models.StatementRow)
            assert row.entry is entry
            assert isinstance(row.balance, Decimal)
            assert isinstance(row.debit, Decimal)
            assert isinstance(row.credit, Decimal)

        assert result.transactions[0].debit == Decimal("100")
        assert result.transactions[0].credit == 0
        assert result.transactions[0].balance == Decimal("100")

        assert result.transactions[1].debit == Decimal("50")
        assert result.transactions[1].credit == 0
        assert result.transactions[1].balance == Decimal("150")

        assert result.transactions[2].debit == 0
        assert result.transactions[2].credit == Decimal("30")
        assert result.transactions[2].balance == Decimal("120")

        assert isinstance(result.closing_balance, Decimal)
        assert result.closing_balance == result.transactions[-1].balance
        assert result.closing_balance == Decimal("120")

        # The start-date filter keeps only transactions on/after start_date;
        # the opening balance stays the year's opening, not a mid-period one.
        filtered = bank.statement_running(
            session, start_date=datetime(datetime.now().year, 1, 20)
        )
        assert [row.entry for row in filtered.transactions] == entries[1:]
        assert filtered.opening_balance == 0
        assert filtered.closing_balance == Decimal("20")

    def test_statement_schedule_alias_equivalence(
        self, session, entity, currency, post_document
    ):
        """Legacy schedule-mode statement() rows are the new ScheduleRow entries."""
        year = datetime.now().year
        account, revenue, bank = _accounts(session, entity, currency)
        first = post_document(
            ClientInvoice, account, revenue, datetime(year, 1, 10), "100"
        )
        second = post_document(
            ClientInvoice, account, revenue, datetime(year, 1, 20), "60"
        )
        payment = post_document(
            ClientReceipt, account, bank, datetime(year, 1, 25), "40"
        )
        _assign(session, first, payment, datetime(year, 1, 25), "40")

        end_date = datetime(year, 1, 31)
        schedule = account.schedule_outstanding(session, end_date=end_date)
        legacy = account.statement(session, None, end_date, True)

        assert isinstance(schedule, account_models.OutstandingSchedule)
        assert len(legacy["transactions"]) == len(schedule.transactions) == 2

        for i, row in enumerate(schedule.transactions):
            legacy_entry = legacy["transactions"][i]
            assert legacy_entry is row.entry
            assert legacy_entry.cleared_amount == row.cleared_amount
            assert legacy_entry.uncleared_amount == row.uncleared_amount
            assert legacy_entry.age == row.age

        assert legacy["transactions"][0] is first
        assert legacy["transactions"][1] is second
        assert legacy["total_amount"] == schedule.total_amount == Decimal("160")
        assert legacy["cleared_amount"] == schedule.cleared_amount == Decimal("40")
        assert legacy["uncleared_amount"] == schedule.uncleared_amount == Decimal("120")

    def test_statement_running_alias_equivalence(
        self, session, entity, currency, post_document
    ):
        """Legacy statement() rows are the new StatementRow entries, restamped."""
        bank, _ = _post_running_entries(session, entity, currency, post_document)

        legacy = bank.statement(session)
        running = bank.statement_running(session)

        assert isinstance(running, account_models.AccountStatement)
        assert legacy["opening_balance"] == running.opening_balance == 0
        assert len(legacy["transactions"]) == len(running.transactions) == 3

        for i, row in enumerate(running.transactions):
            legacy_entry = legacy["transactions"][i]
            assert legacy_entry is row.entry
            assert legacy_entry.balance == row.balance
            assert legacy_entry.debit == row.debit
            assert legacy_entry.credit == row.credit

        assert legacy["closing_balance"] == running.closing_balance == Decimal("120")

    def test_schedule_includes_opening_balance_row(self, session, entity, currency):
        """An opening Balance appears as a ScheduleRow whose entry is the Balance."""
        year = datetime.now().year
        account, _, _ = _accounts(session, entity, currency)
        balance = Balance(
            transaction_date=datetime(year - 1, 12, 15),
            transaction_type=Transaction.TransactionType.CLIENT_INVOICE,
            amount=Decimal("100"),
            balance_type=Balance.BalanceType.DEBIT,
            account_id=account.id,
            entity_id=entity.id,
        )
        session.add(balance)
        session.flush()

        cutoff = datetime(year, 1, 31)
        result = account.schedule_outstanding(session, end_date=cutoff)

        assert isinstance(result, account_models.OutstandingSchedule)
        assert len(result.transactions) == 1

        row = result.transactions[0]
        assert isinstance(row, account_models.ScheduleRow)
        assert row.entry is balance
        assert row.cleared_amount == 0
        assert row.uncleared_amount == Decimal("100")
        assert row.age == (cutoff - balance.transaction_date).days == 47

        assert result.total_amount == Decimal("100")
        assert result.cleared_amount == 0
        assert result.uncleared_amount == Decimal("100")

    def test_schedule_outstanding_rejects_non_clearing_account(
        self, session, entity, currency
    ):
        """schedule_outstanding is the aging half: Receivable/Payable only."""
        bank = Account(
            name="Test bank",
            account_type=Account.AccountType.BANK,
            currency_id=currency.id,
            entity_id=entity.id,
        )
        session.add(bank)
        session.flush()

        with pytest.raises(InvalidAccountTypeError):
            bank.schedule_outstanding(session)

    def test_empty_account_decimal_seeding(self, session, entity, currency):
        """Empty results seed Decimal(0), never int, in both halves."""
        year = datetime.now().year
        receivable = Account(
            name="Test customer",
            account_type=Account.AccountType.RECEIVABLE,
            currency_id=currency.id,
            entity_id=entity.id,
        )
        bank = Account(
            name="Test bank",
            account_type=Account.AccountType.BANK,
            currency_id=currency.id,
            entity_id=entity.id,
        )
        session.add_all([receivable, bank])
        session.flush()

        schedule = receivable.schedule_outstanding(
            session, end_date=datetime(year, 1, 31)
        )
        assert schedule.transactions == []
        assert isinstance(schedule.total_amount, Decimal)
        assert schedule.total_amount == 0
        assert isinstance(schedule.cleared_amount, Decimal)
        assert schedule.cleared_amount == 0
        assert isinstance(schedule.uncleared_amount, Decimal)
        assert schedule.uncleared_amount == 0

        statement = bank.statement_running(session)
        assert statement.transactions == []
        assert isinstance(statement.opening_balance, Decimal)
        assert statement.opening_balance == 0
        assert isinstance(statement.closing_balance, Decimal)
        assert statement.closing_balance == 0
