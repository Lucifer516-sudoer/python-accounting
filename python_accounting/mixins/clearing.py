# mixins/clearing.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Provides functionality to clearable Transactions for assignment to assignable Transactions.

"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Mapped

    from python_accounting.database.session import AccountingSession
    from python_accounting.models.assignment import Assignment


class ClearingMixin:
    """
    This class provides clearable Transactions functionality for assigning them to
    assignable Transactions.
    """

    if TYPE_CHECKING:
        # Host-class attributes this mixin relies on. Declared under
        # TYPE_CHECKING only: at runtime the concrete classes (Transaction STI
        # subclasses, Balance) provide them via their own mappings, and the
        # skipped block keeps SQLAlchemy from seeing duplicate declarations.
        id: Mapped[int]
        entity_id: Mapped[int]

    def cleared(
        self, session: "AccountingSession", end_date: datetime | None = None
    ) -> Decimal:
        """
        Gets how much of the Transaction amount has been cleared by assignable Transactions.

        Args:
            session (Session): The accounting session to which the Transaction belongs.
            end_date (datetime, optional): Include assignments at or before this timestamp.
                Defaults to all assignments.

        Returns:
            Decimal: The total amount of assignments made against Transaction.
        """
        from python_accounting.models import (
            Assignment,
        )

        query = (
            session.query(func.sum(Assignment.amount).label("amount"))
            .filter(Assignment.entity_id == self.entity_id)
            .filter(Assignment.assigned_id == self.id)
            .filter(Assignment.assigned_type == self.__class__.__name__)
        )
        if end_date is not None:
            query = query.filter(Assignment.assignment_date <= end_date)

        return Decimal(query.scalar() or 0)

    def clearances(self, session: "AccountingSession") -> list["Assignment"]:
        """
        Gets the assignments made to clear the Transaction.

        Args:
            session (Session): The accounting session to which the Transaction belongs.

        Returns:
            A List of assignments made to clear the Transaction.
        """
        from python_accounting.models import (
            Assignment,
        )

        return list(
            session.scalars(
                select(Assignment)
                .filter(Assignment.assigned_id == self.id)
                .filter(Assignment.assigned_type == self.__class__.__name__)
            ).all()
        )

    def unclear(self, session: "AccountingSession") -> None:
        """
        Removes all assignments made to clear this Transaction.

        Args:
            session (Session): The accounting session to which the Transaction belongs.

        Returns:
            None
        """
        for clearance in self.clearances(session):
            session.delete(clearance)
