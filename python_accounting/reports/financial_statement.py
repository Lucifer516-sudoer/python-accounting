# reports/financial_statement.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents an abstraction of a financial statement according to IFRS/GAAP.

"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from strenum import StrEnum
from sqlalchemy import select
from python_accounting.config import config as configuration
from python_accounting.models import Account
from python_accounting.models.account import SectionBalances
from python_accounting.utils.dates import get_dates

if TYPE_CHECKING:
    from python_accounting.database.session import AccountingSession
    from python_accounting.models.account import AccountTypeStub


def section_balances(
    session: "AccountingSession",
    account_types: "list[AccountTypeStub]",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    full_balance: bool = True,
) -> SectionBalances:
    """
    Gets the opening, movement and closing balances of the accounts of the given section
    (account types), organized by category.

    Args:
        session (Session): The accounting session to which the Account belongs.
        account_types (`list` of `Account.AccountType`): The Account types
            belonging to the section.
        start_date (datetime): The earliest transaction date for Transaction amounts to be
            included in the balance.
        end_date (datetime): The latest transaction date for Transaction amounts to be included
            in the balance.
        full_balance (bool): Whether to include opening balance amounts in the balance.

    Returns:
        SectionBalances: A summary of the total opening, balance movement and closing
        balance, which details of totals by Category and the Accounts contained in
        each Category.
            - opening (Decimal): The sum of opening balances of Accounts in the section.
            - movement (Decimal): The movememt of the balances of Accounts in the section.
            - closing (Decimal): The sum of opening closing of Accounts in the section.
            - categories (dict): The Accounts belonging to the section separated by Category.
    """
    balances: SectionBalances = {
        "opening": Decimal(0),
        "movement": Decimal(0),
        "closing": Decimal(0),
        "categories": {},
    }
    start_date, end_date, period_start, _ = get_dates(session, start_date, end_date)

    for account in session.scalars(
        select(Account).filter(Account.account_type.in_(account_types))
    ).all():
        opening = account.opening_balance(
            session, end_date.year
        ) + account.balance_movement(session, period_start, start_date)
        movement = account.balance_movement(session, start_date, end_date)
        closing = opening + movement if full_balance else movement
        display_movement = movement * -1  # cashflow statement display
        if closing != 0 or display_movement != 0:
            category_id, category_name = (
                (0, Account.AccountType[account.account_type.name].value)
                if account.category is None
                else (account.category_id, account.category.name)
            )
            if category_name in balances["categories"]:
                balances["categories"][category_name]["total"] += closing
                balances["categories"][category_name]["accounts"].append(account)
            else:
                balances["categories"].update(
                    {
                        category_name: {
                            "id": category_id,
                            "total": closing,
                            "accounts": [account],
                        }
                    }
                )
            balances["opening"] += opening
            balances["movement"] += display_movement
            balances["closing"] += closing
    return balances


class FinancialStatement:
    """This class is an abstract representation of a Financial Statement as defined by IFRS and GAAP."""

    config: str
    """(str): The configuration section for the report."""
    start_date: datetime
    """(datetime): The earliest transaction date for Transaction amounts to be included
    in the report. Set by every concrete statement's __init__ via get_dates."""
    end_date: datetime
    """(datetime): The latest transaction date for Transaction amounts to be included in the report."""

    # The sections/results enums are built per instance from config.toml at
    # runtime, so the base cannot know their members. Each concrete statement
    # narrows these with a TYPE_CHECKING stub class (D-015 pattern, instance
    # level); Any here keeps the override compatible in both checkers.
    sections: Any
    """(StrEnum): The sections of the report."""
    results: Any
    """(StrEnum): The results of the report."""

    # printing
    printout: tuple[Any, ...]
    """(tuple): The sections to be printed out."""
    width: int
    """(int): The width of the report printout."""
    indent: str = " " * configuration.reports["indent_length"]
    """(str): The indent between report sections."""
    subtotal: str = "_" * configuration.reports["result_length"]
    """(str): The underline for report subtotals."""
    grandtotal: str = "=" * configuration.reports["result_length"]
    """(str): The underline for report grand totals."""

    def __init__(self, session: "AccountingSession") -> None:
        self.session = session
        self.title = configuration.reports[self.config]["title"]

        # Financial Statement Sections
        self.sections = StrEnum(
            "Sections",
            [
                (k, v["label"])
                for k, v in configuration.reports[self.config]["sections"].items()
            ],
        )

        # Financial Statement Results
        self.results = StrEnum(
            "Results",
            list(configuration.reports[self.config]["results"].items()),
        )

        section_names = [section.name for section in self.sections]

        self.accounts: dict[str, dict[str, Any]] = {k: {} for k in section_names}
        """(dict): The Accounts in the sections of the report, by Account category."""
        # Keys are config-driven section names plus the synthetic "debit"/"credit"
        # scalars; values are label-keyed dicts or Decimals — heterogeneous by
        # design (D-016), so the honest annotation is a plain dict.
        self.balances: dict[str, Any] = {k: {} for k in section_names}
        """(dict): The total balances of the Accounts in the sections of the report, by Account category."""
        self.totals: dict[str, Decimal] = dict.fromkeys(section_names, Decimal(0))
        """(dict): The Total balances of Accounts in the sections of the report."""
        self.result_amounts: dict[str, Decimal] = {}
        """(dict): The amounts results of the report."""

        self.balances.update({"debit": 0, "credit": 0})

    def __str__(self) -> str:
        template = "{}\n" * len(self.printout)
        return template.format(*self.printout)

    def _get_sections(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        full_balance: bool = True,
    ) -> None:
        for section, content in configuration.reports[self.config]["sections"].items():
            for account_type in content["account_types"]:
                balances = Account.section_balances(
                    self.session, [account_type], start_date, end_date, full_balance
                )
                account_name = Account.AccountType[account_type].value
                if balances["closing"] != 0:
                    self.accounts[section][account_name] = balances["categories"]
                    self.balances[section][account_name] = balances["closing"]
                    self.totals[section] += balances["closing"]
                    self.balances[
                        "debit" if balances["closing"] >= 0 else "credit"
                    ] += balances["closing"]

    def _print_title(self) -> str:
        period = (
            f"""For the period: {self.start_date.strftime(configuration.dates["long"])} to {self.end_date.strftime(configuration.dates["long"])}"""
            if hasattr(self, "start_date")
            else f"As at {self.end_date.strftime(configuration.dates['long'])}"
        )
        self.width = max(len(period), 45)
        return f"""\n{self.session.entity.name.center(self.width)}\n{self.title.center(self.width)}\n{period.center(self.width)}"""

    def _print_section(self, section: StrEnum, factor: int = 1) -> str:
        content = f"\n{section.value}"

        for account_type, balance in self.balances[section.name].items():
            label = f"\n{self.indent}{account_type}"
            content += f"{label}{balance * factor:>{self.width - len(label) + 1}}"
        return content

    def _print_result(self, result: StrEnum, grandtotal: bool = False) -> str:
        return f"""{f"{self.subtotal:>{self.width}}"}\n{result}{f"{self.result_amounts[result.name]:>{self.width - len(result)}}"}\n{f"{self.grandtotal:>{self.width}}" if grandtotal else ""}"""

    def _print_total(
        self, section: StrEnum, factor: int = 1, grandtotal: bool = False
    ) -> str:
        label = f"Total {section.value}"
        return f"""{f"{self.subtotal:>{self.width}}"}\n{label}{f"{self.totals[section.name] * factor:>{self.width - len(label)}}"}\n{f"{self.grandtotal:>{self.width}}" if grandtotal else ""}"""
