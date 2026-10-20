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
from typing import TYPE_CHECKING, NamedTuple

from python_accounting.models.reporting_period import ReportingPeriod

if TYPE_CHECKING:
    from python_accounting.database.session import AccountingSession


class Dates(NamedTuple):
    """The reporting dates and period resolved for a session (D-017).

    A NamedTuple so positional unpacking keeps working for existing callers,
    while new code can use named attribute access.
    """

    start_date: datetime
    end_date: datetime
    period_start: datetime
    period_id: int


def get_dates(
    session: "AccountingSession",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> Dates:
    """
    Returns the start, end and period start dates given the inputs provided.

    Args:
        session (AccountingSession): The session used to resolve the reporting period.
        start_date (datetime): The start date, defaulting to the period start date.
        end_date (datetime): The end date, defaulting to today and normalized to the
            last microsecond of the day.
    Returns:
        Dates: The start date, the end date, the period start date and the period id.
    """
    end_date = end_date or datetime.today()
    period = ReportingPeriod.for_year(session, end_date.year)
    period_start = period.interval()["start"]
    start_date = start_date or period_start

    return Dates(
        start_date,
        end_date.replace(hour=23, minute=59, second=59, microsecond=999999),
        period_start,
        period.id,
    )
