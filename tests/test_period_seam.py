"""Contract tests for the period seam (PLAN T10.2, red step).

`ReportingPeriod.for_year` (D-017 §1) and the `Dates` NamedTuple (D-017 §3)
do not exist yet. These tests encode their contract so the T10.3
implementation lands against a failing suite:

- `ReportingPeriod.for_year(session, year)` is equivalent to
  `ReportingPeriod.get_period(session, datetime(year, session.entity.year_start, 1, 0, 0, 0))`
  — a lookup that raises MissingReportingPeriodError when the year has no
  period, never a factory.
- `get_dates` returns a `Dates` NamedTuple with fields (start_date,
  end_date, period_start, period_id); positional unpacking keeps working.

Every test here is expected to FAIL at collection (ImportError) until T10.3
lands.
"""

from datetime import datetime

import pytest

from python_accounting.exceptions import MissingReportingPeriodError
from python_accounting.models import ReportingPeriod
from python_accounting.utils.dates import Dates, get_dates


def test_for_year_matches_get_period(session, entity):
    """for_year resolves the same period as the sentinel-date get_period call."""
    period = session.entity.reporting_period
    year = period.calendar_year
    expected = ReportingPeriod.get_period(
        session, datetime(year, session.entity.year_start, 1, 0, 0, 0)
    )
    actual = ReportingPeriod.for_year(session, year)
    assert actual.id == expected.id
    assert actual.calendar_year == year


def test_for_year_missing_period_raises(session, entity):
    """for_year is a lookup, not a factory: absent years raise."""
    missing_year = session.entity.reporting_period.calendar_year - 5
    with pytest.raises(MissingReportingPeriodError):
        ReportingPeriod.for_year(session, missing_year)


def test_dates_is_a_named_tuple(session, entity, fixed_today):
    """get_dates returns a Dates instance; positional unpacking still works."""
    result = get_dates(session)
    assert isinstance(result, Dates)
    assert result._fields == ("start_date", "end_date", "period_start", "period_id")
    assert result.period_id == result[-1]

    start_date, end_date, period_start, period_id = get_dates(session)
    assert start_date == result.start_date
    assert end_date == result.end_date
    assert period_start == result.period_start
    assert period_id == result.period_id


def test_dates_defaults(session, entity, fixed_today):
    """Without explicit dates: end is today at end-of-day, start is period start."""
    result = get_dates(session)
    assert result.end_date == fixed_today.replace(
        hour=23, minute=59, second=59, microsecond=999999
    )
    assert result.start_date == result.period_start
    assert result.period_start == datetime(
        fixed_today.year, session.entity.year_start, 1, 0, 0, 0
    )
    assert result.period_id == session.entity.reporting_period.id


def test_dates_explicit_range(session, entity, fixed_today):
    """Explicit start/end are honored; end gets the end-of-day treatment."""
    start = datetime(fixed_today.year, 1, 5)
    end = datetime(fixed_today.year, 1, 20)
    result = get_dates(session, start_date=start, end_date=end)
    assert result.start_date == start
    assert result.end_date == datetime(fixed_today.year, 1, 20, 23, 59, 59, 999999)
    assert result.period_start == datetime(
        fixed_today.year, session.entity.year_start, 1, 0, 0, 0
    )
    assert result.period_id == session.entity.reporting_period.id
