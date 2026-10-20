# models/account.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents an Account, the basic unit of accounting that groups the transactions of an Entity.
"""

import warnings
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict, cast
from strenum import StrEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased
from sqlalchemy import String, ForeignKey, Enum, func, inspect, or_, exc
from python_accounting.models.recyclable import Recyclable
from python_accounting.models.reporting_period import ReportingPeriod
from python_accounting.mixins import IsolatingMixin, ClearingMixin
from python_accounting.config import config
from python_accounting.exceptions import (
    InvalidCategoryAccountTypeError,
    InvalidAccountTypeError,
    HangingTransactionsError,
)
from python_accounting.utils.dates import get_dates
from python_accounting.utils.money import signed_sum

if TYPE_CHECKING:
    from typing import TypeAlias

    from python_accounting.database.session import AccountingSession
    from python_accounting.models.balance import Balance
    from python_accounting.models.category import Category
    from python_accounting.models.currency import Currency
    from python_accounting.models.transaction import Transaction

    class AccountType(StrEnum):
        """Stub mirroring the config-driven AccountType members.

        The real AccountType is created from config.toml at import time, so the
        type checkers cannot see its members. This class exists only for them;
        tests/test_enum_stubs.py guards it against drifting from the real enum.
        """

        NON_CURRENT_ASSET = ""
        CONTRA_ASSET = ""
        INVENTORY = ""
        BANK = ""
        CURRENT_ASSET = ""
        RECEIVABLE = ""
        NON_CURRENT_LIABILITY = ""
        CONTROL = ""
        CURRENT_LIABILITY = ""
        PAYABLE = ""
        RECONCILIATION = ""
        EQUITY = ""
        OPERATING_REVENUE = ""
        OPERATING_EXPENSE = ""
        NON_OPERATING_REVENUE = ""
        DIRECT_EXPENSE = ""
        OVERHEAD_EXPENSE = ""
        OTHER_EXPENSE = ""

    # Alias for use inside the Account class body, where the Account.AccountType
    # class attribute shadows the module-level stub. Explicit TypeAlias so that
    # pyright accepts it in type expressions (e.g. ``type[AccountTypeStub]``).
    AccountTypeStub: TypeAlias = AccountType


account_type_enum: "type[AccountType]" = cast(
    "type[AccountType]",
    StrEnum(
        "AccountType", [(k, v["label"]) for k, v in config.accounts["types"].items()]
    ),
)


class SectionCategory(TypedDict):
    """Shape of one category entry in :meth:`Account.section_balances`."""

    id: int
    """(int): The Category id, or 0 for an uncategorised Account."""
    total: Decimal
    """(Decimal): The sum of the closing balances of the Category's Accounts."""
    accounts: list["Account"]
    """(list of Account): The Accounts belonging to the Category."""


class SectionBalances(TypedDict):
    """Shape of the summary returned by :meth:`Account.section_balances`."""

    opening: Decimal
    """(Decimal): The sum of opening balances of Accounts in the section."""
    movement: Decimal
    """(Decimal): The movement of the balances of Accounts in the section."""
    closing: Decimal
    """(Decimal): The sum of the closing balances of Accounts in the section."""
    categories: dict[str, SectionCategory]
    """(dict): The Accounts belonging to the section separated by Category."""


@dataclass(frozen=True)
class ScheduleRow:
    """One outstanding entry in :meth:`Account.schedule_outstanding`.

    ``entry`` is the outstanding object itself: a clearable ``Transaction``, or
    a ``Balance`` brought down from a previous Reporting Period.
    """

    entry: "Transaction | Balance"
    """(Transaction | Balance): The outstanding Transaction or opening Balance."""
    cleared_amount: Decimal
    """(Decimal): The amount of the entry cleared as at the schedule end date."""
    uncleared_amount: Decimal
    """(Decimal): The amount of the entry still outstanding as at the end date."""
    age: int
    """(int): The age of the entry in days, as at the schedule end date."""


@dataclass(frozen=True)
class OutstandingSchedule:
    """Result of :meth:`Account.schedule_outstanding`."""

    transactions: list[ScheduleRow]
    """(list of ScheduleRow): The outstanding entries, FIFO by transaction date."""
    total_amount: Decimal
    """(Decimal): The total amount of the entries in the schedule."""
    cleared_amount: Decimal
    """(Decimal): The amount of the entries in the schedule that has been cleared."""
    uncleared_amount: Decimal
    """(Decimal): The amount of the entries in the schedule still outstanding."""


@dataclass(frozen=True)
class StatementRow:
    """One posted entry in :meth:`Account.statement_running`."""

    entry: "Transaction"
    """(Transaction): The posted Transaction."""
    balance: Decimal
    """(Decimal): The running balance of the Account after the entry."""
    debit: Decimal
    """(Decimal): The debit contribution of the entry to the Account."""
    credit: Decimal
    """(Decimal): The credit contribution of the entry to the Account."""


@dataclass(frozen=True)
class AccountStatement:
    """Result of :meth:`Account.statement_running`."""

    opening_balance: Decimal
    """(Decimal): The balance of the Account at the beginning of the period."""
    transactions: list[StatementRow]
    """(list of StatementRow): The posted Transactions, in transaction date order."""
    closing_balance: Decimal
    """(Decimal): The running balance after the last entry (0 if there are none)."""


class Account(IsolatingMixin, Recyclable):
    """Represents an account which groups related Transactions."""

    if TYPE_CHECKING:
        # Transient per-session numbering counter, set by the
        # transient_to_pending listener in database/event_listeners.py and read
        # via getattr(self, "session_index", 1). Declared under TYPE_CHECKING
        # only: at runtime it is a plain instance attribute, and a bare
        # annotation on a mapped class would require __allow_unmapped__.
        session_index: int

        # Outstanding-amount bracket dict stamped by reports/aging_schedule.py
        # (D-016 §6 keeps this report-owned stamping). Runtime instance
        # attribute only, hence the TYPE_CHECKING declaration.
        balances: dict[str, Decimal]

    __tablename__ = "account"

    # Chart of Accounts types
    AccountType: ClassVar["type[AccountTypeStub]"] = account_type_enum
    """(StrEnum): Account Types as defined by IFRS and GAAP."""

    # Account Types that can be used in Purchasing Transactions
    purchasables: ClassVar[list["AccountTypeStub"]] = [
        account_type_enum[t] for t in config.accounts["purchasables"]["types"]
    ]
    """
    (`list` of `Account.AccountType`): A list of Account
    Types that can be used in purchasing Transactions.
    """

    __mapper_args__ = {"polymorphic_identity": "Account"}

    id: Mapped[int] = mapped_column(ForeignKey("recyclable.id"), primary_key=True)
    """(int): The primary key of the Account database record."""
    name: Mapped[str] = mapped_column(String(255))
    """(str): The label of the Account."""
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    """(`str`, optional): A narration of the purpose of the Account."""
    account_code: Mapped[int] = mapped_column()
    """(int): A serially generated code based on the type of the Account."""
    account_type: Mapped[StrEnum] = mapped_column(Enum(AccountType))
    """(AccountType): The type of the Account."""
    currency_id: Mapped[int] = mapped_column(ForeignKey("currency.id"))
    """(int): The id of the Currency model associated with the Account."""
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), nullable=True)
    """(`int`, optional): The id of the Category model to which the Account belongs."""

    # relationships
    currency: Mapped["Currency"] = relationship(foreign_keys=[currency_id])
    """(Currency): The Currency associated with the Account."""
    category: Mapped["Category | None"] = relationship(foreign_keys=[category_id])
    """(`Category`, optional): The Category to which the Account belongs."""

    def _get_account_code(self, session: "AccountingSession") -> int:
        current_count = int(
            session.query(Account)
            .filter(Account.entity_id == self.entity_id)
            .filter(Account.account_type == self.account_type)
            .with_entities(func.count())
            .scalar()
            or 0
        )

        return (
            int(config.accounts["types"][self.account_type.name]["account_code"])
            + current_count
            + int(getattr(self, "session_index", 1))
        )

    def __repr__(self) -> str:
        return f"{self.account_type} {self.name} <{self.account_code}>"

    def balance_movement(
        self, session: "AccountingSession", start_date: datetime, end_date: datetime
    ) -> Decimal:
        """
        Get the change in the account balance between the given dates.

        Args:
            session (Session): The accounting session to which the Account belongs.
            start_date (datetime): The earliest transaction date for Transaction amounts to be
                included in the balance.
            end_date (datetime): The latest transaction date for Transaction amounts to be included
                in the balance.

        Returns:
            Decimal: The difference between the balance of the Account at the start date and
            end date.
        """
        from python_accounting.models import (
            Balance,
            Ledger,
        )

        start_date, end_date, _, _ = get_dates(session, start_date, end_date)

        query = (
            session.query(func.sum(Ledger.amount).label("amount"))
            .filter(Ledger.currency_id == self.currency_id)
            .filter(Ledger.transaction_date >= start_date)
            .filter(Ledger.transaction_date <= end_date)
            .filter(Ledger.post_account_id == self.id)
            .filter(Ledger.entity_id == self.entity_id)
        )
        return signed_sum(
            query,
            Ledger.entry_type == Balance.BalanceType.DEBIT,
            Ledger.entry_type == Balance.BalanceType.CREDIT,
        )

    @staticmethod
    def section_balances(
        session: "AccountingSession",
        account_types: "list[AccountTypeStub]",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        full_balance: bool = True,
    ) -> SectionBalances:
        """
        Deprecated alias for
        python_accounting.reports.financial_statement.section_balances, kept for
        backwards compatibility. New code should call the reports-layer function
        directly; unlike earlier versions of this method, it does not stamp
        opening/closing/movement attributes onto the Account objects.

        Args:
            session (Session): The accounting session to which the Account belongs.
            account_types (`list` of `Account.AccountType`): The Account types
                belonging to the section.
            start_date (datetime): The earliest transaction date for Transaction amounts to be
                included in the balance.
            end_date (datetime): The latest transaction date for Transaction amounts to be included
                in the balance.
            full_balance (bool): Whether to include opening balance amounts in the balance.

        Returns:
            SectionBalances: A summary of the total opening, balance movement and closing
            balance, which details of totals by Category and the Accounts contained in
            each Category.
        """
        from python_accounting.reports.financial_statement import section_balances

        return section_balances(
            session, account_types, start_date, end_date, full_balance
        )

    def opening_balance(
        self, session: "AccountingSession", year: int | None = None
    ) -> Decimal:
        """
        Gets the the opening balance for the account for the given year.

        Args:
            session (Session): The accounting session to which the Account belongs.
            year (int): The calendar year for which to retrieve the opening balance.

        Returns:
            Decimal: The total opening balance of the Account for the year.

        """
        from python_accounting.models import (
            Balance,
        )

        period_id = (
            ReportingPeriod.get_period(
                session, datetime(year, session.entity.year_start, 1, 0, 0, 0)
            ).id
            if year
            else session.entity.reporting_period_id
        )
        query = (
            session.query(func.sum(Balance.amount).label("amount"))
            .filter(Balance.currency_id == self.currency_id)
            .filter(Balance.reporting_period_id == period_id)
            .filter(Balance.account_id == self.id)
            .filter(Balance.entity_id == self.entity_id)
        )
        return signed_sum(
            query,
            Balance.balance_type == Balance.BalanceType.DEBIT,
            Balance.balance_type == Balance.BalanceType.CREDIT,
        )

    def closing_balance(
        self, session: "AccountingSession", end_date: datetime | None = None
    ) -> Decimal:
        """
        Gets the the closing balance of the Account as at the given date.

        Args:
            session (Session): The accounting session to which the Account belongs.
            end_date (datetime): The latest transaction date for Transaction
                amounts to be included in the balance.

        Returns:
            Decimal: The total opening balance of the Account for the year.

        """

        start_date, end_date, _, _ = get_dates(session, None, end_date)

        return self.opening_balance(session, end_date.year) + self.balance_movement(
            session, start_date, end_date
        )

    def schedule_outstanding(
        self,
        session: "AccountingSession",
        end_date: datetime | None = None,
    ) -> OutstandingSchedule:
        """
        Gets the outstanding clearable Transactions of the Account, aged as at the
        end date, on a FIFO basis.

        Args:
            session (Session): The accounting session to which the Account belongs.
            end_date (datetime): The latest transaction date for Transaction amounts to
                be included in the schedule. Assignments are included through the end date.

        Raises:
            InvalidAccountTypeError: If the Account type is not Receivable or Payable.

        Returns:
            OutstandingSchedule: The outstanding entries (clearable Transactions and
            opening Balances) of the Account as at the end date, each with its cleared,
            uncleared and age values, together with the total, cleared and uncleared
            amounts of the schedule.
        """
        from python_accounting.models import (
            Assignment,
            Balance,
            Ledger,
            Transaction,
        )

        if self.account_type not in [
            Account.AccountType.RECEIVABLE,
            Account.AccountType.PAYABLE,
        ]:
            raise InvalidAccountTypeError(
                "Only Receivable and Payable Accounts can have a statement/schedule."
            )
        _, end_date, _, period_id = get_dates(session, None, end_date)

        rows: list[ScheduleRow] = []
        total_amount: Decimal = Decimal(0)
        cleared_total: Decimal = Decimal(0)
        uncleared_total: Decimal = Decimal(0)

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", "SELECT statement has a cartesian product.*", exc.SAWarning
            )
            ledger = aliased(Ledger, flat=True)
            transactions = (
                session.query(Transaction)
                .join(ledger, ledger.transaction_id == Transaction.id)
                .filter(Transaction.currency_id == self.currency_id)
                .filter(Transaction.transaction_date <= end_date)
                .filter(
                    or_(
                        ledger.post_account_id == self.id,
                        ledger.folio_account_id == self.id,
                    )
                )
                .filter(Transaction.entity_id == self.entity_id)
                .filter(Ledger.entity_id == self.entity_id)
                .filter(Transaction.transaction_type.in_(Assignment.clearables))
            )
            balances = (
                session.query(Balance)
                .filter(Balance.account_id == self.id)
                .filter(Balance.reporting_period_id == period_id)
                .filter(Balance.entity_id == self.entity_id)
                .order_by(Balance.transaction_date)
                .all()
            )

            for transaction in list(balances) + list(
                transactions.order_by(Transaction.transaction_date).distinct()
            ):
                # Every clearable Transaction type carries ClearingMixin via its STI
                # subclass (ClientInvoice/SupplierBill/JournalEntry); the base does not
                # declare it. assignment.py:166 asserts the same invariant.
                cleared = cast("ClearingMixin", transaction).cleared(
                    session, end_date=end_date
                )
                if transaction.amount - cleared == 0 or (
                    transaction.transaction_type
                    == Transaction.TransactionType.JOURNAL_ENTRY
                    and (
                        (
                            self.account_type == Account.AccountType.RECEIVABLE
                            and transaction.credited
                        )
                        or (
                            self.account_type == Account.AccountType.PAYABLE
                            and not transaction.credited
                        )
                    )
                ):
                    continue
                row = ScheduleRow(
                    entry=transaction,
                    cleared_amount=cleared,
                    uncleared_amount=transaction.amount - cleared,
                    age=(end_date - transaction.transaction_date).days,
                )
                rows.append(row)
                total_amount += transaction.amount
                cleared_total += row.cleared_amount
                uncleared_total += row.uncleared_amount

        return OutstandingSchedule(
            transactions=rows,
            total_amount=total_amount,
            cleared_amount=cleared_total,
            uncleared_amount=uncleared_total,
        )

    def statement_running(
        self,
        session: "AccountingSession",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> AccountStatement:
        """
        Gets a chronological listing of the Transactions posted to the Account between
        the dates given, with their running balance and debit/credit contributions.

        Args:
            session (Session): The accounting session to which the Account belongs.
            start_date (datetime): The earliest transaction date for Transaction amounts
                to be included in the statement.
            end_date (datetime): The latest transaction date for Transaction amounts to
                be included in the statement.

        Returns:
            AccountStatement: The opening balance of the Account, its Transactions in
            the period with their running balance and debit/credit contributions, and
            the closing balance.
        """
        from python_accounting.models import (
            Ledger,
            Transaction,
        )

        start_date, end_date, _, _ = get_dates(session, start_date, end_date)
        opening_balance = self.opening_balance(session, end_date.year)

        rows: list[StatementRow] = []
        balance: Decimal = opening_balance
        closing_balance: Decimal = Decimal(0)

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", "SELECT statement has a cartesian product.*", exc.SAWarning
            )
            ledger = aliased(Ledger, flat=True)
            transactions = (
                session.query(Transaction)
                .join(ledger, ledger.transaction_id == Transaction.id)
                .filter(Transaction.currency_id == self.currency_id)
                .filter(Transaction.transaction_date <= end_date)
                .filter(
                    or_(
                        ledger.post_account_id == self.id,
                        ledger.folio_account_id == self.id,
                    )
                )
                .filter(Transaction.entity_id == self.entity_id)
                .filter(Ledger.entity_id == self.entity_id)
                .filter(Transaction.transaction_date >= start_date)
                .order_by(Transaction.transaction_date)
                .distinct()
            )
            for transaction in transactions:
                contribution = transaction.contribution(session, self)
                balance += contribution
                debit, credit = (
                    (Decimal(0), abs(contribution))
                    if contribution < 0
                    else (contribution, Decimal(0))
                )
                closing_balance = balance
                rows.append(
                    StatementRow(
                        entry=transaction,
                        balance=balance,
                        debit=debit,
                        credit=credit,
                    )
                )

        return AccountStatement(
            opening_balance=opening_balance,
            transactions=rows,
            closing_balance=closing_balance,
        )

    def statement(
        self,
        session: "AccountingSession",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        schedule: bool = False,
    ) -> dict[str, Any]:
        """
        Gets a chronological listing of the Transactions posted to the Account between
            the dates given.

        Legacy interface: delegates to :meth:`schedule_outstanding` (schedule mode) or
        :meth:`statement_running` (statement mode) and restamps each row's computed
        values onto its entry for backwards compatibility. New code should call the
        typed methods directly.

        Args:
            session (Session): The accounting session to which the Account belongs.
            start_date (datetime): The earliest transaction date for Transaction amounts
                to be included in the statement.
            end_date (datetime): The latest transaction date for Transaction amounts to
                be included in the statement.
            schedule (bool): Whether to exclude assignable Transactions and only list
                clearable Transactions with outstanding amounts. Assignments are included
                through the end date.

        Raises:
            InvalidAccountTypeError: If the Account type is not Receivable or Payable.

        Returns:
            dict: With a A summary of the opening and closing balance in the case of
            a statement, the total, cleared and uncleared amounts if its a schedule
            together with a list of Transactions.

            Statements.
                - opening_balance (Decimal): The balance of the Account at the beginning of the statement period.
                - transactions (list): Transactions posted to the Account during the period.
                - closing_balance (Decimal): The balance of the Account at the end of the statement period.
            Schedule.
                - transactions (list): Outstanding clearable Transactions posted to the Account as at the end date.
                - total_amount (Decimal): The total amount of the Transactions in the Schdeule.
                - cleared_amount (Decimal): The amount of the Transactions in the Schdeule that has been cleared.
                - uncleared_amount (Decimal): The amount of the Transactions in the Schdeule that is still outstanding.
        """
        if schedule:
            schedule_result = self.schedule_outstanding(session, end_date)
            for row in schedule_result.transactions:
                row.entry.cleared_amount = row.cleared_amount
                row.entry.uncleared_amount = row.uncleared_amount
                row.entry.age = row.age
            return {
                "transactions": [row.entry for row in schedule_result.transactions],
                "total_amount": schedule_result.total_amount,
                "cleared_amount": schedule_result.cleared_amount,
                "uncleared_amount": schedule_result.uncleared_amount,
            }
        running_result = self.statement_running(session, start_date, end_date)
        for statement_row in running_result.transactions:
            entry = statement_row.entry
            # The running-balance stamp cannot be declared on Transaction: the
            # name collides with AssigningMixin.balance() across the MRO of the
            # assigning subclasses. Set dynamically, as the legacy code did.
            setattr(entry, "balance", statement_row.balance)  # noqa: B010
            entry.debit = statement_row.debit
            entry.credit = statement_row.credit
        return {
            "opening_balance": running_result.opening_balance,
            "transactions": [
                statement_row.entry for statement_row in running_result.transactions
            ],
            "closing_balance": running_result.closing_balance,
        }

    def validate(self, session: "AccountingSession") -> None:
        """
        Validates the Account properties.

        Args:
            session (Session): The accounting session to which the Account belongs.

        Raises:
            InvalidCategoryAccountTypeError: If the account type of the Account
                does not match that of its assigned Category.

        Returns:
            None
        """
        from python_accounting.models import (
            Category,
        )

        self.name = self.name.title()
        if (
            self.account_code is None
            or len(inspect(self).attrs.account_type.history.deleted) > 0
        ):
            self.account_code = self._get_account_code(session)

        if self.category_id:
            category = session.get(Category, self.category_id)
            assert category is not None
            if self.account_type != category.category_account_type:
                raise InvalidCategoryAccountTypeError(
                    self.account_type.value, category.category_account_type.value
                )

    def validate_delete(self, session: "AccountingSession") -> None:
        """
        Validates if the account can be deleted.

        Args:
            session (Session): The accounting session to which the Account belongs.

        Raises:
            HangingTransactionsError: If the Account has had Transactions during the
                current Reporting period.

        Returns:
            None
        """
        from python_accounting.models import (
            Ledger,
        )

        if (
            session.query(func.count(Ledger.id))
            .filter(Ledger.entity_id == self.entity_id)
            .filter(
                or_(
                    Ledger.post_account_id == self.id,
                    Ledger.folio_account_id == self.id,
                )
            )
            .scalar()
            > 0
        ):
            raise HangingTransactionsError("Account")
