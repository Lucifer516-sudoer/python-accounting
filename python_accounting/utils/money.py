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

from sqlalchemy import ColumnElement
from sqlalchemy.orm import Query

if TYPE_CHECKING:
    from python_accounting.models.line_item import LineItem

__all__ = [
    "line_item_posted_tax_amount",
    "line_item_tax_amount",
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
    amount = line_item.amount * line_item.quantity
    if line_item.tax_inclusive:
        return amount - (amount / (1 + line_item.tax.rate / 100))
    return line_item_tax_amount(line_item)
