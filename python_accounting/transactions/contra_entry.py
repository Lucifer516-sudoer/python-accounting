# transactions/contra_entry.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents a Contra Entry Transaction.

"""

from typing import Any
from python_accounting.models import Transaction
from python_accounting.mixins.trading import TradingMixin


class ContraEntry(TradingMixin, Transaction):
    """Class for the Contra Entry Transaction."""

    __mapper_args__ = {
        "polymorphic_identity": Transaction.TransactionType.CONTRA_ENTRY,
    }

    def __init__(self, **kw: Any) -> None:
        from python_accounting.models import (
            Account,
        )

        self.line_item_types = [Account.AccountType.BANK]
        self.main_account_types = [Account.AccountType.BANK]
        self.account_type_map = {
            "ContraEntry": Account.AccountType.BANK,
        }

        self.credited = False
        self.transaction_type = Transaction.TransactionType.CONTRA_ENTRY
        self.no_tax = True
        super().__init__(**kw)
