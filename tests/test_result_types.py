"""Shape-pinning tests for the D-016 result types (PLAN T4.0a, red step).

These tests pin the *runtime* dict shapes that the future TypedDicts
(`SectionBalances`, `CategoryBalances`, `TransactionTax`) will declare. The
TypedDicts do not exist yet — deliberately, these tests must not import them.
They guard against key drift during the refactor and pin one concrete numeric
value per method so values cannot silently change.

The Decimal-seeding assertions are expected to FAIL before T4.0a lands:
`Account.section_balances` and `Category.account_balances` seed their
accumulators with `int 0` today. (`Transaction.tax` already seeds
`Decimal(0)`, so its isinstance assertion passes today.)
"""

from datetime import datetime
from decimal import Decimal

import pytest

from python_accounting.database.session import AccountingSession
from python_accounting.models import (
    Account,
    Category,
    Currency,
    Entity,
    LineItem,
    Tax,
    Transaction,
)
from python_accounting.transactions import ClientInvoice


def _post_invoice_on_revenue(
    session: AccountingSession,
    entity: Entity,
    currency: Currency,
    revenue_category: Category,
) -> Account:
    """Mirrors tests/test_category.py:131-210: a client invoice whose line item
    lands on a revenue account, so the revenue account closes at -100."""
    client_category = Category(
        name="Client Category",
        category_account_type=Account.AccountType.RECEIVABLE,
        entity_id=entity.id,
    )
    session.add(client_category)
    session.flush()

    revenue = Account(
        name="revenue account",
        account_type=Account.AccountType.OPERATING_REVENUE,
        currency_id=currency.id,
        category_id=revenue_category.id,
        entity_id=entity.id,
    )
    client = Account(
        name="client account",
        account_type=Account.AccountType.RECEIVABLE,
        currency_id=currency.id,
        category_id=client_category.id,
        entity_id=entity.id,
    )
    session.add_all([revenue, client])
    session.flush()

    invoice = ClientInvoice(
        narration="Test transaction one",
        transaction_date=datetime.now(),
        account_id=client.id,
        entity_id=entity.id,
    )
    session.add(invoice)
    session.commit()

    line_item = LineItem(
        narration="Test line item one",
        account_id=revenue.id,
        amount=100,
        entity_id=entity.id,
    )
    session.add(line_item)
    session.flush()

    invoice.line_items.add(line_item)
    session.add(invoice)
    session.flush()

    invoice.post(session)
    return revenue


class TestResultTypes:
    """Pins the dict shapes that the T4.0a TypedDicts will formalize."""

    def test_section_balances_top_level_keys(self, session, entity, currency):
        """Account.section_balances returns exactly the SectionBalances keys."""
        category = Category(
            name="Revenue Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()
        _post_invoice_on_revenue(session, entity, currency, category)

        result = Account.section_balances(
            session, [Account.AccountType.OPERATING_REVENUE]
        )
        assert sorted(result.keys()) == [
            "categories",
            "closing",
            "movement",
            "opening",
        ]

    def test_section_balances_category_entry_keys(self, session, entity, currency):
        """Each section_balances category entry has exactly the pinned keys."""
        category = Category(
            name="Revenue Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()
        _post_invoice_on_revenue(session, entity, currency, category)

        result = Account.section_balances(
            session, [Account.AccountType.OPERATING_REVENUE]
        )
        assert len(result["categories"]) == 1
        entry = result["categories"][category.name]
        assert sorted(entry.keys()) == ["accounts", "id", "total"]

    def test_section_balances_decimal_seeding(self, session, entity, currency):
        """Empty section_balances accumulators must be Decimal, not int (RED today)."""
        result = Account.section_balances(session, [Account.AccountType.BANK])
        assert isinstance(result["opening"], Decimal)
        assert isinstance(result["movement"], Decimal)
        assert isinstance(result["closing"], Decimal)

    def test_section_balances_values_unchanged(self, session, entity, currency):
        """Pins the concrete values exactly as tests/test_account.py:528-533 does."""
        category = Category(
            name="Revenue Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()
        revenue = _post_invoice_on_revenue(session, entity, currency, category)

        result = Account.section_balances(
            session, [Account.AccountType.OPERATING_REVENUE]
        )
        assert result["opening"] == 0
        assert result["movement"] == 100
        assert result["closing"] == -100
        assert result["categories"][category.name]["total"] == -100
        assert result["categories"][category.name]["accounts"] == [revenue]

    def test_account_balances_keys(self, session, entity, currency):
        """Category.account_balances returns exactly the CategoryBalances keys."""
        category = Category(
            name="Revenue Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()
        _post_invoice_on_revenue(session, entity, currency, category)

        result = category.account_balances(session)
        assert sorted(result.keys()) == ["accounts", "total"]

    def test_account_balances_decimal_seeding(self, session, entity, currency):
        """Empty account_balances total must be Decimal, not int (RED today)."""
        category = Category(
            name="Empty Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()

        result = category.account_balances(session)
        assert isinstance(result["total"], Decimal)

    def test_account_balances_values_unchanged(self, session, entity, currency):
        """Pins the concrete values exactly as tests/test_category.py:212-216 pins."""
        category = Category(
            name="Revenue Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()
        revenue = _post_invoice_on_revenue(session, entity, currency, category)

        result = category.account_balances(session)
        assert result["total"] == -100
        assert result["accounts"] == [revenue]

    def test_transaction_tax_keys(self, session, entity, currency):
        """Transaction.tax returns exactly the TransactionTax keys."""
        transaction = self._taxed_journal_entry(
            session, entity, currency, taxes=[10, 15]
        )

        result = transaction.tax
        assert sorted(result.keys()) == ["taxes", "total"]

    def test_transaction_tax_entry_keys(self, session, entity, currency):
        """Each Transaction.tax entry has exactly the pinned keys."""
        transaction = self._taxed_journal_entry(session, entity, currency, taxes=[10])

        result = transaction.tax
        assert len(result["taxes"]) == 1
        entry = result["taxes"]["OTPT1"]
        assert sorted(entry.keys()) == ["amount", "name", "rate"]

    def test_transaction_tax_decimal_seeding(self, session, entity, currency):
        """Transaction.tax total must be Decimal (already seeded — passes today)."""
        transaction = self._taxed_journal_entry(session, entity, currency, taxes=[])

        result = transaction.tax
        assert isinstance(result["total"], Decimal)
        assert result["total"] == Decimal(0)

    def test_transaction_tax_values_unchanged(self, session, entity, currency):
        """Pins the concrete values exactly as tests/test_transaction.py:587-599 does."""
        transaction = self._taxed_journal_entry(
            session, entity, currency, taxes=[10, 15]
        )

        result = transaction.tax
        assert result["total"] == Decimal(40)
        assert result["taxes"] == {
            "OTPT1": {
                "name": "Output Vat one",
                "rate": "10.00%",
                "amount": Decimal(10),
            },
            "OTPT2": {
                "name": "Output Vat two",
                "rate": "15.00%",
                "amount": Decimal(30),
            },
        }

    @staticmethod
    def _taxed_journal_entry(
        session: AccountingSession, entity: Entity, currency: Currency, taxes: list[int]
    ) -> Transaction:
        """Mirrors tests/test_transaction.py:505-585: a journal entry with one
        line item per tax rate; returns the unposted transaction."""
        account1 = Account(
            name="test transaction account",
            account_type=Account.AccountType.OPERATING_EXPENSE,
            currency_id=currency.id,
            entity_id=entity.id,
        )
        account2 = Account(
            name="test line item account",
            account_type=Account.AccountType.BANK,
            currency_id=currency.id,
            entity_id=entity.id,
        )
        account3 = Account(
            name="test taxation account",
            account_type=Account.AccountType.CONTROL,
            currency_id=currency.id,
            entity_id=entity.id,
        )
        session.add_all([account1, account2, account3])
        session.flush()

        tax_words = ["one", "two", "three", "four"]
        taxes_models = [
            Tax(
                name=f"Output Vat {tax_words[index]}",
                code=f"OTPT{index + 1}",
                account_id=account3.id,
                rate=rate,
                entity_id=entity.id,
            )
            for index, rate in enumerate(taxes)
        ]
        session.add_all(taxes_models)
        session.flush()

        transaction = Transaction(
            narration="Test transaction one",
            transaction_date=datetime.now(),
            account_id=account1.id,
            transaction_type=Transaction.TransactionType.JOURNAL_ENTRY,
            entity_id=entity.id,
        )
        session.add(transaction)

        line_items = [
            LineItem(
                narration=f"Test line item {index + 1}",
                account_id=account2.id,
                amount=100 * (index + 1),
                tax_id=tax.id,
                entity_id=entity.id,
            )
            for index, tax in enumerate(taxes_models)
        ]
        session.add_all(line_items)
        session.flush()

        for line_item in line_items:
            transaction.line_items.add(line_item)
        session.add(transaction)
        session.commit()

        return transaction


class TestStampRetirement:
    """T4.0c (D-016 §4): the balance methods stop stamping Account objects.

    The reports-layer ``section_balances`` accumulates locally and returns the
    ``SectionBalances`` dict; ``Category.account_balances`` accumulates locally
    too. The stamped ``account.opening/closing/movement/balance`` attributes are
    retired — reading them must raise ``AttributeError``.
    """

    def _section_setup(
        self, session: AccountingSession, entity: Entity, currency: Currency
    ) -> Account:
        """Category + one revenue account with a posted invoice; returns the account."""
        category = Category(
            name="Revenue Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()
        return _post_invoice_on_revenue(session, entity, currency, category)

    def test_section_balances_does_not_stamp(self, session, entity, currency):
        """Account.section_balances must not stamp opening/closing/movement."""
        revenue = self._section_setup(session, entity, currency)

        Account.section_balances(session, [Account.AccountType.OPERATING_REVENUE])

        for attr in ("opening", "closing", "movement"):
            with pytest.raises(AttributeError):
                getattr(revenue, attr)

    def test_account_balances_does_not_stamp(self, session, entity, currency):
        """Category.account_balances must not stamp balance."""
        category = Category(
            name="Revenue Category",
            category_account_type=Account.AccountType.OPERATING_REVENUE,
            entity_id=entity.id,
        )
        session.add(category)
        session.commit()
        revenue = _post_invoice_on_revenue(session, entity, currency, category)

        category.account_balances(session)

        assert not hasattr(revenue, "balance")

    def test_section_balances_alias_delegates(self, session, entity, currency):
        """Account.section_balances returns the same dict as the reports function."""
        from python_accounting.reports.financial_statement import (
            section_balances as report_section_balances,
        )

        self._section_setup(session, entity, currency)

        assert Account.section_balances(
            session, [Account.AccountType.OPERATING_REVENUE]
        ) == report_section_balances(session, [Account.AccountType.OPERATING_REVENUE])
