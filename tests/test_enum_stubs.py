"""Guards the type-checker enum stubs against drifting from the runtime enums.

The real AccountType/TransactionType/BalanceType/BalanceTransactions enums are
created from config.toml at import time, so the type checkers cannot see their
members. Each is mirrored by a TYPE_CHECKING-only stub class (see the module
docstrings in python_accounting/models/). Nothing at runtime connects the two,
so these tests compare the stub member names (read from source) against the
real enum's members.
"""

import ast
from pathlib import Path

import pytest

from python_accounting.models import Account, Balance, Transaction

MODELS_DIR = Path(__file__).parent.parent / "python_accounting" / "models"


def _stub_members(filename: str, class_name: str) -> set[str]:
    """Return the member names assigned in a stub class found in filename."""
    source = (MODELS_DIR / filename).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                statement.targets[0].id
                for statement in node.body
                if isinstance(statement, ast.Assign)
                and isinstance(statement.targets[0], ast.Name)
            }
    raise AssertionError(f"{class_name} stub not found in {filename}")


@pytest.mark.parametrize(
    "filename,class_name,runtime_enum",
    [
        ("account.py", "AccountType", Account.AccountType),
        ("transaction.py", "TransactionType", Transaction.TransactionType),
        ("balance.py", "BalanceType", Balance.BalanceType),
        ("balance.py", "BalanceTransactions", Balance.BalanceTransactions),
    ],
)
def test_stub_members_match_runtime_enum(filename, class_name, runtime_enum):
    """The stub's member names must equal the runtime enum's, in both directions."""
    assert _stub_members(filename, class_name) == {m.name for m in runtime_enum}
