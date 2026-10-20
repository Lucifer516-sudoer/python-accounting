# mixins/trading.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Provides functionality to Transactions that can by and sell goods and services for an Entity.

"""

from typing import TYPE_CHECKING

from python_accounting.exceptions import (
    InvalidMainAccountError,
    InvalidLineItemAccountError,
    InvalidTaxChargeError,
)

if TYPE_CHECKING:
    from python_accounting.database.session import AccountingSession
    from python_accounting.models.account import AccountTypeStub
    from python_accounting.models.line_item import LineItem
    from python_accounting.models.transaction import Transaction

    # This mixin is only ever combined with Transaction, which provides
    # _get_main_account() and the validate() this mixin chains into via
    # super(). Statically inheriting Transaction lets both type checkers
    # resolve that cooperative super() call and the host methods; at runtime
    # the base stays object, so the concrete classes' MRO (e.g.
    # ClientInvoice(SellingMixin, ClearingMixin, Transaction)) is unchanged.
    _CooperativeBase = Transaction
else:
    _CooperativeBase = object


class TradingMixin(_CooperativeBase):
    """
    This class provides validation for transactions that trade goods and services
    for an entity.
    """

    line_item_types: list["AccountTypeStub"]
    """(`list` of `Account.AccountType`): The Account types allowed on the subclass's line items."""
    main_account_types: list["AccountTypeStub"]
    """(`list` of `Account.AccountType`): The Account types allowed as the subclass's main account."""
    account_type_map: dict[str, "AccountTypeStub"]
    """(dict): Maps each subclass's name to the Account type its main account must have."""

    def _validate_subclass_line_items(self, line_item: "LineItem") -> "LineItem":
        """
        Validates a line item against the subclass's allowed line item Account types.

        Args:
            line_item (LineItem): The line item being validated.

        Raises:
            InvalidLineItemAccountError: If the line item's Account type is not
                one of the subclass's line item types.
            InvalidTaxChargeError: If the subclass does not allow tax but the
                line item has a Tax.

        Returns:
            LineItem: The validated line item.
        """
        if line_item.account.account_type not in self.line_item_types:
            raise InvalidLineItemAccountError(
                self.__class__.__name__,
                [t.value for t in self.line_item_types],
            )
        if getattr(self, "no_tax", False) and line_item.tax_id:
            raise InvalidTaxChargeError(self.__class__.__name__)
        return line_item

    def validate(self, session: "AccountingSession") -> None:
        """
        Validates the trading Transaction properties.

        Args:
            session (Session): The accounting session to which the Transaction belongs.

        Raises:
            InvalidMainAccountError: If the main Account's type is not one of the
                types mapped for the subclass.

        Returns:
            None
        """

        account = self._get_main_account(session)

        if account.account_type not in self.main_account_types:
            raise InvalidMainAccountError(
                self.__class__.__name__,
                self.account_type_map[self.__class__.__name__],
            )
        super().validate(session)
