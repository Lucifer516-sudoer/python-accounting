# models/transaction.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents a financial Transaction.

"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict, cast
from strenum import StrEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy import (
    String,
    ForeignKey,
    Enum,
    Boolean,
    func,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.types import DECIMAL
from python_accounting.mixins import IsolatingMixin
from python_accounting.config import config
from python_accounting.exceptions import (
    InvalidTransactionDateError,
    ClosedReportingPeriodError,
    AdjustingReportingPeriodError,
    RedundantTransactionError,
    MissingLineItemError,
    PostedTransactionError,
    InvalidTransactionTypeError,
)
from python_accounting.models import Recyclable, Account, ReportingPeriod, LineItem

if TYPE_CHECKING:
    from typing import TypeAlias

    from python_accounting.database.session import AccountingSession
    from python_accounting.models.currency import Currency
    from python_accounting.models.ledger import Ledger

    class TransactionType(StrEnum):
        """Stub mirroring the config-driven TransactionType members.

        The real TransactionType is created from config.toml at import time, so
        the type checkers cannot see its members. This class exists only for
        them; tests/test_enum_stubs.py guards it against drifting from the real
        enum.
        """

        CASH_SALE = ""
        CLIENT_INVOICE = ""
        CREDIT_NOTE = ""
        CLIENT_RECEIPT = ""
        CASH_PURCHASE = ""
        SUPPLIER_BILL = ""
        DEBIT_NOTE = ""
        SUPPLIER_PAYMENT = ""
        CONTRA_ENTRY = ""
        JOURNAL_ENTRY = ""

    # Alias for use inside the Transaction class body, where the
    # Transaction.TransactionType class attribute shadows the module-level stub.
    # Explicit TypeAlias so that pyright accepts it in type expressions
    # (e.g. ``type[TransactionTypeStub]``).
    TransactionTypeStub: TypeAlias = TransactionType


transaction_type_enum: "type[TransactionType]" = cast(
    "type[TransactionType]",
    StrEnum(
        "TransactionType",
        [(k, v["label"]) for k, v in config.transactions["types"].items()],
    ),
)


class TaxLine(TypedDict):
    """Shape of one tax entry in :attr:`Transaction.tax`."""

    name: str
    """(str): The name of the Tax."""
    rate: str
    """(str): The rate of the Tax, as a percentage string."""
    amount: Decimal
    """(Decimal): The total amount of the Tax applied to the Transaction."""


class TransactionTax(TypedDict):
    """Shape of the summary returned by :attr:`Transaction.tax`."""

    total: Decimal
    """(Decimal): The total tax applied to the Transaction."""
    taxes: dict[str, TaxLine]
    """(dict): The taxes applied to the Transaction, keyed by tax code."""


class Transaction(IsolatingMixin, Recyclable):
    """Represents a Transaction in the sense of an original source document."""

    # Transaction types
    TransactionType = transaction_type_enum
    """(StrEnum): Transaction Types representing standard source document Transactions."""

    __table_args__ = (UniqueConstraint("transaction_no", "entity_id"),)
    __tablename__ = "transaction"
    __mapper_args__ = {
        "polymorphic_identity": "Transaction",
    }
    # Allow the bare (non-Mapped) dynamic-attribute annotations below (D-011)
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(ForeignKey("recyclable.id"), primary_key=True)
    """(int): The primary key of the Transaction database record."""
    transaction_date: Mapped[datetime] = mapped_column()
    """(datetime): The date of the Transaction."""
    transaction_no: Mapped[str] = mapped_column(String(255), nullable=True)
    """(str): Serially generated indentifier for the Transaction"""
    transaction_type: Mapped[StrEnum] = mapped_column(Enum(TransactionType))
    """(TransactionType): The Transaction type of the Transaction."""
    narration: Mapped[str] = mapped_column(String(1000))
    """(str): A short description of the purpose of the Transaction."""
    reference: Mapped[str] = mapped_column(String(255), nullable=True)
    """(`str`, optional): Identifying information about the Transaction."""
    main_account_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=13, scale=4), default=0
    )
    """
    (`Decimal`, optional): The amount to be posted to the Transaction
    main Account. Only applies to compound (Journal Entry) Transactions.
    """
    credited: Mapped[bool] = mapped_column(Boolean, default=True)
    """
    (`bool`, optional): Determines whether the Transaction amount will
    be posted to the credit side of the main Account. Defaults to True.
    """
    compound: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    (`bool`, optional): Determines whether the (Journal Entry) Transaction amount
    can have Line Items on both sides of the double entry.
    """
    currency_id: Mapped[int] = mapped_column(ForeignKey("currency.id"))
    """(int): The id of the Currency associated with the Transaction."""
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    """(int): The id of the Account model to which Transaction amounts are to be posted."""

    # relationships
    currency: Mapped["Currency"] = relationship(foreign_keys=[currency_id])
    """(Currency): The Currency associated with the Transaction."""
    account: Mapped["Account"] = relationship(foreign_keys=[account_id])
    """(Account): The Account model to which Transaction amounts are to be posted."""
    line_items: Mapped[set["LineItem"]] = relationship(
        back_populates="transaction",
        primaryjoin="Transaction.id==LineItem.transaction_id",
    )
    """(Set): The Line Items models associated with the Transaction."""
    ledgers: Mapped[list["Ledger"]] = relationship(
        back_populates="transaction",
        primaryjoin="Transaction.id==Ledger.transaction_id",
    )
    """(list): The Ledger models associated with the Transaction."""

    # Attributes set dynamically during account statement generation (D-011)
    debit: Decimal
    """(Decimal): The debit amount of the Transaction in an Account statement."""

    credit: Decimal
    """(Decimal): The credit amount of the Transaction in an Account statement."""

    cleared_amount: Decimal
    """(Decimal): The amount of the Transaction that has been cleared."""

    uncleared_amount: Decimal
    """(Decimal): The amount of the Transaction that is still outstanding."""

    age: int
    """(int): The age of the Transaction in days in an Aging Schedule."""

    @validates("line_items", include_removes=True)
    def validate_line_items(
        self, _: str, line_item: "LineItem", is_remove: bool
    ) -> "LineItem":
        """
        Validates adding or removing of Transaction Line Items.

        Raises:
            PostedTransactionError: If the Transaction is posted and Line Items are added or removed from it.
            ValueError: If the unsaved Line Item are added or removed from the Transaction.
        """
        subclass_validate = getattr(self, "_validate_subclass_line_items", None)
        if subclass_validate:
            subclass_validate(line_item)

        if self.is_posted:
            raise PostedTransactionError(
                f"Cannot {'Remove' if is_remove else 'Add'} Line Items from a Posted Transaction."
            )

        if line_item.id is None:
            raise ValueError(
                "Line Item must be persisted to be added to the Transaction."
            )

        if not self.compound and line_item.credited == self.credited:
            line_item.credited = not self.credited
        return line_item

    @validates("ledgers", include_removes=True)
    def validate_ledgers(self, key: str, ledger: "Ledger", is_remove: bool) -> None:
        """
        Validates adding or removing of Transaction Ledgers

        Raises:
            ValueError: If the Transaction Ledgers are manually added or removed.
        """
        raise ValueError(
            f"Transaction ledgers cannot be {'Removed' if is_remove else 'Added'} manually."
        )

    @property
    def tax(self) -> TransactionTax:
        """
        The taxes that have been applied to the transaction.
            - taxes (dict): The taxes applied to the Transaction and their amounts.
            - amount (str): The total tax applied to the Transaction.
        """
        taxes: dict[str, TaxLine] = {}
        total: Decimal = Decimal(0)
        for line_item in iter(self.line_items):
            if line_item.tax_id:
                amount = (
                    line_item.tax.rate * line_item.amount * line_item.quantity / 100
                )
                total += Decimal(amount)
                if line_item.tax.code in taxes:
                    taxes[line_item.tax.code]["amount"] += amount
                else:
                    taxes.update(
                        {
                            line_item.tax.code: {
                                "name": line_item.tax.name,
                                "rate": f"{round(line_item.tax.rate, 2)}%",
                                "amount": amount,
                            }
                        }
                    )
        return {"total": total, "taxes": taxes}

    @property
    def is_posted(self) -> bool:
        """Check if the Transaction has been posted to the ledger"""
        return len(self.ledgers) > 0

    @property
    def amount(self) -> Decimal:
        """The amount of the Transaction."""

        return Decimal(
            sum(
                line_item.amount * line_item.quantity
                + (
                    (line_item.amount * line_item.quantity * line_item.tax.rate / 100)
                    if line_item.tax_id and not line_item.tax_inclusive
                    else 0
                )
                for line_item in iter(self.line_items)
                if line_item.credited != self.credited
            )
        )

    def __repr__(self) -> str:
        return f"{self.account} <{self.transaction_no}>: {self.amount}"

    def _get_main_account(self, session: "AccountingSession") -> Account:
        account = session.get(Account, self.account_id)
        if not account:
            raise ValueError("The main Account is required")
        return account

    def _transaction_no(
        self,
        session: "AccountingSession",
        transaction_type: StrEnum,
        reporting_period: "ReportingPeriod",
    ) -> str:
        next_id = (
            session.query(Transaction)
            .filter(Transaction.transaction_type == transaction_type)
            .filter(Transaction.transaction_date > reporting_period.interval()["start"])
            .with_entities(func.count())
            .execution_options(include_deleted=True)
            .filter(Transaction.entity_id == self.entity_id)
            .scalar()
        ) + getattr(self, "session_index", 1)

        prefix = config.transactions["types"][transaction_type.name][
            "transaction_no_prefix"
        ]
        return f"{prefix}{reporting_period.period_count:02}/{next_id:04}"

    def is_secure(self, session: "AccountingSession") -> bool:
        """Verify that the Transaction's Ledgers have not been tampered with."""
        return all(
            ledger.hash == ledger.get_hash(session.connection())
            for ledger in self.ledgers
        )

    def post(self, session: "AccountingSession") -> None:
        """
        Posts the Transaction to the Ledger.

        Args:
            session (Session): The accounting session to which the Reporting Period
                 belongs.

        Raises:
            MissingLineItemError: If the Transaction has no Line Items.

        Returns:
            None
        """
        from python_accounting.models import (
            Ledger,
        )

        if not self.line_items:
            raise MissingLineItemError

        session.flush()
        Ledger.post(session, self)

    def contribution(self, session: "AccountingSession", account: Account) -> Decimal:
        """
        Gets the amount contributed by the account to the transaction total.

        Args:
            session (Session): The accounting session to which the Reporting Period
                 belongs.
            account (Account): The Account who's contribution is to be found.

        Returns:
            Decimal: The amount posted to the Account by the Transaction.
        """
        from python_accounting.models import (
            Balance,
            Ledger,
        )

        query = (
            session.query(func.sum(Ledger.amount).label("amount"))
            .filter(Ledger.entity_id == self.entity_id)
            .filter(Ledger.transaction_id == self.id)
            .filter(Ledger.currency_id == self.currency_id)
            .filter(Ledger.post_account_id == account.id)
        )
        # NOTE: the Decimal() wrapper is type-checker-only; the precedence
        # defect inside this expression is repaired test-first in T4.4b (D-010).
        return Decimal(
            query.filter(Ledger.entry_type == Balance.BalanceType.DEBIT).scalar()
            or 0
            - query.filter(Ledger.entry_type == Balance.BalanceType.CREDIT).scalar()
            or 0
        )

    def validate(self, session: "AccountingSession") -> None:
        """
        Validates the Transaction properties.

        Args:
            session (Session): The accounting session to which the Balance belongs.

        Raises:
            PostedTransactionError: If Transaction is already posted.
            ClosedReportingPeriodError: If the Transaction date is with a Reporting Period
                in the CLOSED status.
            AdjustingReportingPeriodError: If the Transaction date is with a Reporting Period
                in the ADJUSTING status and is not a Journal Entry.
            InvalidTransactionDateError: If the Transaction date is exactly the beginning of
                the Reporting Period.
            InvalidTransactionTypeError: If the Transaction type is being modified.
            RedundantTransactionError: If the Transaction main Account is also one of its
                Line Items Accounts.

        Returns:
            None
        """

        if self.is_posted:
            raise PostedTransactionError("A Posted Transaction cannot be modified.")

        account = self._get_main_account(session)

        reporting_period = ReportingPeriod.get_period(
            session,
            self.transaction_date,
        )
        self.currency_id = account.currency_id

        if reporting_period.status == ReportingPeriod.Status.CLOSED:
            raise ClosedReportingPeriodError(reporting_period)

        if (
            reporting_period.status == ReportingPeriod.Status.ADJUSTING
            and self.transaction_type != Transaction.TransactionType.JOURNAL_ENTRY
        ):
            raise AdjustingReportingPeriodError(reporting_period)

        if (
            self.transaction_date
            and self.transaction_date == reporting_period.interval()["start"]
        ):
            raise InvalidTransactionDateError

        if self.id and len(inspect(self).attrs.transaction_type.history.deleted) > 0:
            raise InvalidTransactionTypeError

        if not self.transaction_no:
            self.transaction_no = self._transaction_no(
                session, self.transaction_type, reporting_period
            )

        for line_item in self.line_items:
            if line_item.account_id == self.account_id:
                raise RedundantTransactionError(line_item)

    def validate_delete(self, session: "AccountingSession") -> None:
        """
        Validates if the Transaction can be deleted.

        Args:
            session (Session): The accounting session to which the Balance belongs.

        Raises:
            PostedTransactionError: If Transaction is already posted.

        Returns:
            None
        """

        if self.is_posted:
            raise PostedTransactionError("A Posted Transaction cannot be deleted.")
