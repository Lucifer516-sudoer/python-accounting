"""The public exception surface: corrected spelling and the kept alias.

2.0.0 renamed the base class to ``AccountingException`` while keeping
``AccountingExeption`` as a deprecated alias (SPEC G5, DECISIONS D-013).
Both spellings must stay importable and refer to the same class, so that
consumer code written against the historical spelling keeps working.
"""

import pytest

from python_accounting.exceptions import (
    AccountingException,
    AccountingExeption,
    MissingEntityError,
)


def test_alias_is_the_same_class():
    """The historical misspelt name is an alias, not a separate class."""
    assert AccountingExeption is AccountingException


def test_old_spelling_catches_raised_exceptions():
    """Code written against the old spelling still catches raised exceptions."""
    with pytest.raises(AccountingExeption):
        raise MissingEntityError()
