# mixins/assigning.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Provides functionality to assignable Transactions for clearing clearable Transactions.

"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Mapped

    from python_accounting.database.session import AccountingSession
    from python_accounting.mixins.clearing import ClearingMixin
    from python_accounting.models.account import Account
    from python_accounting.models.assignment import Assignment


class AssigningMixin:
    """
    This class provides assignable Transactions functionality for
    clearing clearable Transactions.

    """

    if TYPE_CHECKING:
        # Host-class attributes this mixin relies on. Declared under
        # TYPE_CHECKING only: at runtime the concrete classes (Transaction STI
        # subclasses) provide them via their own mappings/properties, and the
        # skipped block keeps SQLAlchemy from seeing duplicate declarations.
        id: Mapped[int]
        entity_id: Mapped[int]
        account: Mapped["Account"]
        amount: Decimal

    def balance(self, session: "AccountingSession") -> Decimal:
        """
        Gets how much of the Transaction amount is remaining available for assigning
            to clearable Transactions.

        Args:
            session (Session): The accounting session to which the Transaction belongs.

        Returns:
            Decimal: The difference between the Transaction
            amount and the total amount of assignments made to it.
        """

        from python_accounting.models import (
            Assignment,
        )

        return self.amount - Decimal(
            (
                session.query(func.sum(Assignment.amount).label("amount"))
                .filter(Assignment.transaction_id == self.id)
                .filter(Assignment.entity_id == self.entity_id)
            ).scalar()
            or 0
        )

    def assignments(self, session: "AccountingSession") -> list["Assignment"]:
        """
        Gets the assignments made on the Transaction.

        Args:
            session (Session): The accounting session to which the Transaction belongs.

        Returns:
            A List of assignments made for the Transaction.
        """
        from python_accounting.models import (
            Assignment,
        )

        return list(
            session.scalars(
                select(Assignment).filter(Assignment.transaction_id == self.id)
            ).all()
        )

    def unassign(self, session: "AccountingSession") -> None:
        """
        Removes all assignments made to this Transaction.

        Args:
            session (Session): The accounting session to which the Transaction belongs.

        Returns:
            None
        """
        for assignment in self.assignments(session):
            session.delete(assignment)

    def bulk_assign(self, session: "AccountingSession") -> None:
        """
        Assigns the Transaction's amount to all outstanding clearable Transactions for the
        main account on a FIFO basis.
        Remaining allocation capacity includes all assignments, including future dates.

        Args:
            session (Session): The accounting session to which the Transaction belongs.

        Returns:
            None
        """

        from python_accounting.models import (
            Assignment,
        )

        balance = self.balance(session)

        for row in self.account.schedule_outstanding(session).transactions:
            clearable = row.entry
            if balance == 0:
                break

            # Clearable schedule rows are Transaction STI subclasses carrying
            # ClearingMixin or Balance (which has it too), so cleared() is
            # available on either union member (same precedent as
            # models/assignment.py's isinstance assert).
            uncleared_amount = clearable.amount - cast(
                "ClearingMixin", clearable
            ).cleared(session)
            if uncleared_amount == 0:
                continue

            assignment = Assignment(
                assignment_date=datetime.now(),
                transaction_id=self.id,
                assigned_id=clearable.id,
                assigned_type=clearable.__class__.__name__,
                entity_id=self.entity_id,
            )

            assignment.amount = (
                balance if uncleared_amount > balance else uncleared_amount
            )
            balance -= assignment.amount
            session.add(assignment)
            session.flush()
