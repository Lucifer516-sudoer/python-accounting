# Typing baseline — python-accounting 2.0 remodel

Dev doc (excluded from the built site). Captured 2026-10-16 on branch
`remodel/2.0`, base commit `e22689c`. These are the numbers the remodel drives
to zero (SPEC A3–A5). Every phase must strictly decrease the totals; a file
reaching zero errors is that file's definition of done (PLAN ground rules).

## Reproduce

```bash
# pyright 1.1.414 (standard, package + tests + scripts)
# until T1.1 pins it in the `lint` group, use the scratch venv:
/tmp/opencode/pyrightenv/bin/pyright --outputjson \
    --pythonpath .venv/bin/python python_accounting tests scripts
# after T1.1:  uv run pyright        (config from pyrightconfig.json)

# mypy 2.4.0 (strict, namespace package)
uv run --with mypy mypy --strict --explicit-package-bases \
    --python-executable .venv/bin/python python_accounting
# after T1.1:  uv run mypy python_accounting   (config from [tool.mypy])
```

Machine-readable artifacts from the baseline run:
`/tmp/opencode/pyright-modern.json`, `/tmp/opencode/mypy-baseline2.txt`,
`/tmp/opencode/ddl-before.sql` (create_all DDL, 14 tables),
`/tmp/opencode/tables-before.txt` (golden table list).

## pyright 1.1.414 — 334 diagnostics

| Count | Rule |
|---:|---|
| 251 | `reportAttributeAccessIssue` |
| 45 | `reportArgumentType` |
| 18 | `reportUndefinedVariable` |
| 7 | `reportAssignmentType` |
| 5 | `reportReturnType` |
| 2 | `reportIncompatibleMethodOverride` |
| 2 | `reportOptionalMemberAccess` |
| 1 | `reportPossiblyUnboundVariable` |
| 1 | `reportInvalidTypeForm` |
| 1 | `reportOperatorIssue` |
| 1 | `reportCallIssue` |

Top files: `reports/income_statement.py` 34, `test_account.py` 27,
`test_transaction.py` 22, `reports/balance_sheet.py` 20,
`reports/cashflow_statement.py` 20, `models/account.py` 18,
`database/accounting_functions.py` 15, `test_balance.py` 15,
`reports/trial_balance.py` 13, `database/event_listeners.py` 10,
`database/session_overrides.py` 9, then 7s and 6s across mixins/models/reports.

## mypy 2.4.0 strict — 468 errors in 41 files

| Count | Rule |
|---:|---|
| 187 | `attr-defined` |
| 88 | `no-untyped-def` |
| 54 | `type-arg` |
| 43 | `assignment` |
| 22 | `has-type` |
| 19 | `arg-type` |
| 18 | `name-defined` |
| 12 | `no-any-return` |
| 5 | `var-annotated` |
| 5 | `return-value` |
| 4 | `misc` |
| 2 each | `valid-type`, `operator`, `index`, `import-untyped`, `dict-item` |
| 1 | `list-item` |

Top files: `models/account.py` 51, `reports/income_statement.py` 42,
`reports/balance_sheet.py` 37, `reports/cashflow_statement.py` 30,
`models/ledger.py` 25, `reports/financial_statement.py` 21,
`models/transaction.py` 20, `reports/trial_balance.py` 16,
`models/balance.py` 16, `exceptions/__init__.py` 16,
`database/accounting_functions.py` 16, `models/reporting_period.py` 15,
`database/session_overrides.py` 15, `mixins/assigning.py` 14,
`models/category.py` 13, `database/event_listeners.py` 13,
`mixins/clearing.py` 12, `config.py` 12.

## Warnings

- **Stale pyrights misreport.** The system `/usr/bin/pyright` is 1.1.367; it
  cannot parse this repo's `pyproject.toml` (PEP 735 `dependency-groups`) and
  then reports 624 diagnostics including phantom ones. It also means an editor
  running it shows bogus import errors (`sqlalchemy` "unresolved") because it
  never resolves the venv. Shipping `pyrightconfig.json` (D-002) silences the
  parse failure; the pinned 1.1.414 in the `lint` group is the authority.
- **`--explicit-package-bases` is mandatory** for mypy on this namespace
  package (no top-level `__init__.py`, D-003). Plain `mypy --strict` refuses
  to run at all.
- Do not trust numbers from any checker whose config is not the one above.

## Runtime invariants recorded at baseline

```
AccountingSession -> SessionOverridesMixin -> EventListenersMixin
-> AccountingFunctionsMixin -> Session -> _SessionClassMethods
-> EventTarget -> object
```

The T4.2 session-layer refactor must leave this shape functionally unchanged
(D-008); full pytest is the behavior gate.

14 tables (D-005 golden list, byte-identical target):
`account, assignment, balance, category, currency, entity, ledger, line_item,
recyclable, recycled, reporting_period, tax, transaction, user`.
