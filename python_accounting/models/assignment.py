# models/assignment.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents an matching between Transactions that have an opposite effect on an Account.

"""

import importlib
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, cast
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, func, String
from sqlalchemy.types import DECIMAL
from python_accounting.mixins import IsolatingMixin, AssigningMixin, ClearingMixin
from python_accounting.models import Balance, Transaction, Base
from python_accounting.config import config
from python_accounting.exceptions import (
    UnassignableTransactionError,
    UnclearableTransactionError,
    NegativeValueError,
    SelfClearanceError,
    UnpostedAssignmentError,
    InvalidAssignmentAccountError,
    InvalidClearanceEntryTypeError,
    CompoundTransactionAssignmentError,
    InsufficientBalanceError,
    OverclearanceError,
    MixedAssignmentError,
)

if TYPE_CHECKING:
    from python_accounting.database.session import AccountingSession
    from python_accounting.models.transaction import TransactionTypeStub


class Assignment(IsolatingMixin, Base):
    """Represents an assigment of a clearable type to an assignable Transaction."""

    __tablename__ = "assignment"

    clearables: ClassVar[list["TransactionTypeStub"]] = [
        Transaction.TransactionType[t]
        for t in config.transactions["clearables"]["types"]
    ]
    """
    (`list` of `Transaction.TransactionType`): A list of Transaction Types
    that can be cleared by assignable Transactions.
    """

    assignables: ClassVar[list["TransactionTypeStub"]] = [
        Transaction.TransactionType[t]
        for t in config.transactions["assignables"]["types"]
    ]
    """
    (`list` of `Transaction.TransactionType`): A list of Transaction Types
    that can have cleareable Transactions assigned to them.
    """

    assignment_date: Mapped[datetime] = mapped_column()
    """(datetime): The date of the Assignment."""
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transaction.id"), nullable=True
    )
    """(int): The id of the assignable Transaction in the Assignment."""
    assigned_id: Mapped[int] = mapped_column()
    """(int): The id of the clearable Transaction|Balance in the Assignment."""
    assigned_type: Mapped[str] = mapped_column(String(255))
    """(str): The class name of the clearable Transaction|Balance in the Assignment."""
    assigned_no: Mapped[str] = mapped_column(String(255))
    """(str): The Transaction number of the clearable Transaction|Balance in the Assignment."""
    amount: Mapped[Decimal] = mapped_column(DECIMAL(precision=13, scale=4))
    """(Decimal): The amount of the Assignment."""

    # relationships
    transaction: Mapped["Transaction"] = relationship(foreign_keys=[transaction_id])
    """(Transaction): The assignable Transaction in the Assignment."""

    def __repr__(self) -> str:
        return f"""Assigning {self.assigned_no}
        to {self.transaction.transaction_no}
        on {self.assignment_date}
        for {self.amount}"""

    def assigned(self, session: "AccountingSession") -> "Transaction | Balance | None":
        """
        Get the clearable Transaction|Balance assigned to this assigment's transaction.

        Args:
            session (Session): The accounting session to which the Assignment belongs.

        Returns:
            Transaction|Balance: The model cleared by this assignment, if found.
        """
        module = (
            importlib.import_module("python_accounting.models")
            if self.assigned_type in [Transaction.__name__, Balance.__name__]
            else importlib.import_module("python_accounting.transactions")
        )
        # The assigned model class is looked up by name at runtime, so the
        # checkers cannot see it; the cast records that the result is always
        # a Transaction (an STI subclass) or a Balance, or None if unfound.
        return cast(
            "Transaction | Balance | None",
            session.get(getattr(module, self.assigned_type), self.assigned_id),
        )

    def validate(self, session: "AccountingSession") -> None:  # noqa: PLR0912
        """
        Validates the Assignment properties.

        Args:
            session (Session): The accounting session to which the Assignment belongs.

        Raises:
            ValueError: If the assignable Transaction or clearable Transaction|Balance could not be found.
            UnassignableTransactionError: If the assignable Transaction type is not one of the assignable types.
            UnclearableTransactionError: If the clearable Transaction type is not one of the clearable types.
            UnpostedAssignmentError: If either the assignable or clearable Transaction is not posted.
            InsufficientBalanceError: If the remaining balance in the assignable Transaction is less than the Assignment amount.
            OverclearanceError: If the Assignment amount is greater than the clearable Transaction|Balance uncleared amount.
            CompoundTransactionAssignmentError: If either the assignable or clearable Journal Entry is a compound Transaction.
            SelfClearanceError: If the assignable and clearable Transaction of the Assignment is the same.
            InvalidAssignmentAccountError: If the assignable Transaction and clearable Transaction|Balance main Accounts are not the same.
            MixedAssignmentError: If either an already Transaction is being cleared or an already cleared Transaction is being assigned.

        Returns:
            None
        """
        if self.amount < 0:
            raise NegativeValueError(self.__class__.__name__)

        transaction = session.get(Transaction, self.transaction_id)
        if not transaction:
            raise ValueError("The Assignment Transaction was not found")

        if transaction.transaction_type not in Assignment.assignables:
            raise UnassignableTransactionError(
                transaction.__class__.__name__,
                [t.value for t in Assignment.assignables],
            )
        # Assignable Transaction types carry AssigningMixin (the config-driven
        # list only names classes that do), so balance() is available below.
        assert isinstance(transaction, AssigningMixin)

        assigned: Balance | Transaction | None
        if self.assigned_type == Balance.__name__:
            assigned = session.get(Balance, self.assigned_id)
            if not assigned:
                raise ValueError("The Assigned Balance was not found")
        else:
            assigned = session.get(Transaction, self.assigned_id)
            if not assigned:
                raise ValueError("The Assigned Transaction was not found")
            if assigned.transaction_type not in Assignment.clearables:
                raise UnclearableTransactionError(
                    assigned.__class__.__name__,
                    [t.value for t in Assignment.clearables],
                )
        # Clearable Transaction types carry ClearingMixin, and Balance does
        # too, so cleared() is available on either branch below.
        assert isinstance(assigned, ClearingMixin)
        self.assigned_no = assigned.transaction_no
        if not transaction.is_posted or not assigned.is_posted:
            raise UnpostedAssignmentError

        if transaction.balance(session) < self.amount:
            raise InsufficientBalanceError(
                transaction.__class__.__name__, self.amount, assigned.__class__.__name__
            )

        if assigned.cleared(session) + self.amount > assigned.amount:
            raise OverclearanceError(assigned.__class__.__name__)

        if transaction.compound or assigned.compound:
            raise CompoundTransactionAssignmentError

        if self.transaction_id == self.assigned_id and isinstance(
            assigned, Transaction
        ):
            raise SelfClearanceError

        if transaction.account_id != assigned.account_id:
            raise InvalidAssignmentAccountError

        if transaction.credited == assigned.credited:
            raise InvalidClearanceEntryTypeError(
                Balance.BalanceType.CREDIT
                if transaction.credited
                else Balance.BalanceType.DEBIT
            )

        query = session.query(func.count(Assignment.id)).filter(
            Assignment.entity_id == self.entity_id
        )

        if query.filter(Assignment.assigned_id == self.transaction_id).scalar() > 0:
            raise MixedAssignmentError("Cleared", "Assigned")

        if (
            query.filter(Assignment.transaction_id == self.assigned_id).scalar() > 0
            and assigned.transaction_type in Assignment.assignables
        ):
            raise MixedAssignmentError(
                "Assigned",
                "Cleared",
            )
