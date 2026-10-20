# utils/money.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Money arithmetic seams shared across the models.

Every amount in PythonAccounting is a Decimal. These helpers keep the two
most-duplicated money computations — netting debit totals against credit
totals, and deriving a line item's tax amount — in one place, so the
Decimal-only rule is enforced at a single seam instead of being re-derived
(and occasionally re-broken) at each call site.

"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Query

    from python_accounting.database.session import AccountingSession
    from python_accounting.models.line_item import LineItem

__all__ = [
    "line_item_posted_tax_amount",
    "line_item_tax_amount",
    "line_item_total",
    "net_balance",
    "net_ledger",
    "signed_sum",
]


def signed_sum(
    query: "Query[Any]",
    debit_expr: "ColumnElement[bool]",
    credit_expr: "ColumnElement[bool]",
) -> Decimal:
    """
    Nets an aggregate query's rows split by a debit/credit discriminator:
    returns the debit total minus the credit total.

    Args:
        query (Query): A ``func.sum`` aggregate query whose rows carry the
            amounts to be netted.
        debit_expr (ColumnElement): Filter selecting the debit rows.
        credit_expr (ColumnElement): Filter selecting the credit rows.

    Returns:
        Decimal: The debit total minus the credit total.
    """
    debit = query.filter(debit_expr).scalar() or 0
    credit = query.filter(credit_expr).scalar() or 0
    return Decimal(debit) - Decimal(credit)


def net_ledger(
    session: "AccountingSession", *filters: "ColumnElement[bool]"
) -> Decimal:
    """
    Nets the Ledger rows matching the given scope filters: the total of debit
    postings minus the total of credit postings.

    The model, the side column and the ``Balance.BalanceType`` discrimination
    live inside this seam; callers state only scope filters (entity, currency,
    account, date). The entity filter is explicit — no auto-injection.

    Args:
        session (AccountingSession): The accounting session to query against.
        *filters (ColumnElement): Scope filters for the Ledger rows.

    Returns:
        Decimal: Debit postings minus credit postings for the scoped rows.
    """
    from python_accounting.models import Balance, Ledger

    query = session.query(func.sum(Ledger.amount).label("amount"))
    for scope_filter in filters:
        query = query.filter(scope_filter)
    return signed_sum(
        query,
        Ledger.entry_type == Balance.BalanceType.DEBIT,
        Ledger.entry_type == Balance.BalanceType.CREDIT,
    )


def net_balance(
    session: "AccountingSession", *filters: "ColumnElement[bool]"
) -> Decimal:
    """
    Nets the Balance (opening balance) rows matching the given scope filters:
    the total of debit balances minus the total of credit balances.

    The model, the side column and the ``Balance.BalanceType`` discrimination
    live inside this seam; callers state only scope filters (entity, currency,
    account, period). The entity filter is explicit — no auto-injection.

    Args:
        session (AccountingSession): The accounting session to query against.
        *filters (ColumnElement): Scope filters for the Balance rows.

    Returns:
        Decimal: Debit balances minus credit balances for the scoped rows.
    """
    from python_accounting.models import Balance

    query = session.query(func.sum(Balance.amount).label("amount"))
    for scope_filter in filters:
        query = query.filter(scope_filter)
    return signed_sum(
        query,
        Balance.balance_type == Balance.BalanceType.DEBIT,
        Balance.balance_type == Balance.BalanceType.CREDIT,
    )


def line_item_total(line_item: "LineItem") -> Decimal:
    """
    The pre-tax extended amount of a line item: its amount times its quantity.

    Args:
        line_item (LineItem): The line item whose total is wanted.

    Returns:
        Decimal: The line item's pre-tax extended amount.
    """
    return line_item.amount * line_item.quantity


def line_item_tax_amount(line_item: "LineItem") -> Decimal:
    """
    The exclusive tax amount for a line item: the Tax rate applied to the
    line item amount times its quantity.

    Args:
        line_item (LineItem): The line item whose tax amount is wanted.

    Returns:
        Decimal: The tax amount at the line item's Tax rate.
    """
    return line_item.tax.rate * line_item.amount * line_item.quantity / 100


def line_item_posted_tax_amount(line_item: "LineItem") -> Decimal:
    """
    The tax amount posted to the ledger for a line item. For tax-inclusive
    line items the tax is extracted from the gross amount; otherwise this is
    the exclusive :func:`line_item_tax_amount`.

    Args:
        line_item (LineItem): The line item whose posted tax amount is wanted.

    Returns:
        Decimal: The tax amount as it is posted to the Ledger.
    """
    amount = line_item_total(line_item)
    if line_item.tax_inclusive:
        return amount - (amount / (1 + line_item.tax.rate / 100))
    return line_item_tax_amount(line_item)
