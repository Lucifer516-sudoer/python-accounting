# utils/dates.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Provides accounting specific date utilities.

"""

from datetime import datetime
from typing import TYPE_CHECKING

from python_accounting.models.reporting_period import ReportingPeriod

if TYPE_CHECKING:
    from python_accounting.database.session import AccountingSession


def get_dates(
    session: "AccountingSession",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[datetime, datetime, datetime, int]:
    """
    Returns the start, end and period start dates given the inputs provided.

    Args:
        session (AccountingSession): The session used to resolve the reporting period.
        start_date (datetime): The start date, defaulting to the period start date.
        end_date (datetime): The end date, defaulting to today and normalized to the
            last microsecond of the day.
    Returns:
        tuple: The start date, the end date, the period start date and the period id.
    """
    end_date = end_date or datetime.today()
    period = ReportingPeriod.get_period(
        session, datetime(end_date.year, session.entity.year_start, 1, 0, 0, 0)
    )
    period_start = period.interval()["start"]
    start_date = start_date or period_start

    return (
        start_date,
        end_date.replace(hour=23, minute=59, second=59, microsecond=999999),
        period_start,
        period.id,
    )
