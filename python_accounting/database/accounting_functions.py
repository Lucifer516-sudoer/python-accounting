# database/accounting_functions.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
This mixin providses accounting specific functionality to the standard sqlachemy session.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from python_accounting.models import Entity, ReportingPeriod


class AccountingFunctionsMixin(Session):
    """
    Accounting functions class.

    Attributes:
        entity (Entity): The Entity currently associated with the session. Set by
            EventListenersMixin's transient_to_pending listener; read here to scope
            reporting-period queries.
    """

    entity: "Entity"

    def _year_period(self, year: int) -> "ReportingPeriod | None":
        """
        Gets the ReportingPeriod for the given calendar year, ignoring entity isolation
        (periods are looked up for the session's entity explicitly).

        Args:
            year (int): The calendar year of the period.

        Returns:
            ReportingPeriod: The period for the year, if it exists.
        """
        return self.scalars(
            select(ReportingPeriod)
            .where(ReportingPeriod.calendar_year == year)
            .where(ReportingPeriod.entity_id == self.entity.id)
            .execution_options(ignore_isolation=True)
        ).first()

    def _set_reporting_period(self) -> None:
        """
        Sets the session Entity's reporting period to the current year, creating and
        rolling forward periods as needed.

        Returns:
            None
        """
        year = datetime.today().year
        existing = self._year_period(year)

        if existing:
            self.entity.reporting_period_id = existing.id
        else:
            # transission the previous period to adjusting status if one exists
            previous_period = self._year_period(year - 1)
            if (
                previous_period
                and previous_period.status == ReportingPeriod.Status.OPEN
            ):
                previous_period.status = ReportingPeriod.Status.ADJUSTING
                self.add(previous_period)
                self.flush()

            past_periods = (
                self.query(ReportingPeriod)
                .filter(ReportingPeriod.entity_id == self.entity.id)
                .with_entities(func.count())
                .execution_options(ignore_isolation=True)
                .scalar()
            )

            self.add(
                ReportingPeriod(
                    calendar_year=year,
                    period_count=past_periods + 1,
                    entity_id=self.entity.id,
                )
            )
            self.flush()

            # The period was just created and flushed, so the lookup cannot
            # return None here.
            period = self._year_period(year)
            assert period is not None
            self.entity.reporting_period = period
        self.commit()
