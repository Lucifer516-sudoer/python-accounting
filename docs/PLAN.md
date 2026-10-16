# PLAN — python-accounting 2.0 Remodel

Execution plan for `docs/SPEC.md` under the decisions in `docs/DECISIONS.md`.
Each task is one commit (formatting-only changes are their own commit) and lists its
verification. From T0.2 onward, the schema snapshot test must be green in every commit.

## Ground rules (apply to every task)

- Run, in order, and show output: `ruff format --check` → `ruff check` → `mypy` →
  `pyright` (from T1.1 on) → `pytest`.
- Never reorder `models/__init__.py` imports; never touch an `E711` `== None` site;
  never run `ruff --fix` without a full `pytest` run afterwards (AGENTS.md history).
- One concern per commit; prefixes: `Chore:` / `Fix:` / `Refactor:` / `Test:` / `Docs:`.
- Checker progress is tracked by error count per file (baseline in
  `docs/typing-baseline.md`); a file's count reaching zero is the task's definition of done.

## Phase 0 — Instruments (no behavior change)

- **T0.1** Write `docs/typing-baseline.md`: pyright 334 by rule + top files; mypy 468 by
  rule; exact reproduce commands; warning that stale pyrights misreport (624) and cannot
  parse the pyproject; `AccountingSession.__mro__` baseline line. Commit `Docs: typing baseline`.
- **T0.2** Add `tests/test_schema_snapshot.py`: asserts the 14 table names (D-005 golden
  list) and per-table `[(column, nullable)]` tuples against a golden dict generated
  mechanically from today's metadata. Must pass on first run. Commit `Test: pin schema snapshot`.
  (Also dump `CreateTable(...).compile()` per table to `/tmp/opencode/ddl-before.sql` as a
  working artifact for diffing during phases 3–5.)

## Phase 1 — Toolchain config (one commit)

- **T1.1** `requires-python = ">=3.10,<3.14"`; ruff `target-version = "py310"`; CI matrix
  shrinks to 3.10–3.13 (both workflows); add empty `python_accounting/py.typed`; extend
  `scripts/check_wheel_layout.py` to assert `py.typed` ships (D-012/SPEC 7.7); add
  `pyrightconfig.json` (exact contents in D-002); add `[tool.mypy]` blocks (D-003); pin
  `mypy` + `pyright` in the `lint` dependency group; enable `RUF`/`PERF` **if** fallout is
  trivial, else defer to T7.3 (D-012).
  Verify: A1, A2, A6, A8 still pass; `uv run mypy python_accounting` and `uv run pyright`
  both *run* (they will print the baseline errors — not yet gates). Commit
  `Chore: harden toolchain for 2.0 (mypy, pyright, py.typed, py310)`.
- **CHECKPOINT 1** — user sign-off on `delete -> None` (D-009) before T4.2 lands.

## Phase 2 — Leaf-out pass (prove the loop on small files)

- **T2.1** `exceptions/__init__.py`: `AccountingException` correct spelling; module-level
  `AccountingExeption = AccountingException` alias with comment; annotate; update any
  in-repo users (alias keeps old imports working). Commit
  `Refactor: correct AccountingException spelling, keep alias`.
- **T2.2** `config.py`: annotate `Config` and its methods. Commit `Chore: annotate config`.
- **T2.3** `utils/dates.py`: fix wrong header path; annotate `get_dates`
  (`session: AccountingSession`) with precise tuple return. Commit `Chore: annotate utils.dates`.

## Phase 3 — Models pass (dependency order, file-by-file)

- **T3.0** De-magicize tablenames (D-005): remove directive from `base.py`; add explicit
  `__tablename__` to the 11 auto-named classes; delete the 10 `= None` markers in
  `transactions/`. Verify: snapshot test green (names byte-identical), full pytest green,
  `rg "__tablename__"` audit. Commit `Refactor: explicit __tablename__ on every model`.
- **T3.1–T3.12** Annotate one file per commit in order: `base` → `recyclable` →
  `recycled` → `currency` (group `user` if trivial) → `account` → `category` → `tax` →
  `reporting_period` → `transaction` → `ledger` → `line_item` → `balance` → `assignment` →
  `entity`. Per file: `TYPE_CHECKING` imports + quoted refs (D-004), `| None` + `nullable=`
  pins (D-006), dynamic-attribute declarations (D-011), docstrings for public methods
  touched. Verify per file: its checker count is zero; total counts strictly decrease;
  pytest + snapshot green.

## Phase 4 — Mixins + database layer

- **T4.1** Six mixins (`isolating`, `trading`, `buying`, `selling`, `clearing`,
  `assigning`): annotate; `foreign_keys` string form in `isolating` (D-007) — run the
  5-minute f-string probe first and record the outcome in the commit body. Commits: one per
  mixin or grouped when trivial. Verify: checker counts, pytest (assignment/clearing tests).
- **T4.2** Session layer (D-008, D-009): record MRO baseline, then
  `SessionOverridesMixin(Session)`, `EventListenersMixin(AccountingFunctionsMixin)`,
  `AccountingFunctionsMixin(Session)`; declare `entity: "Entity"`; widened `get`; `delete`
  per checkpoint 1; `restore/destroy/erase` signatures; `get_session -> AccountingSession`.
  Verify: MRO functionally unchanged; **full** pytest; import-order diff review (SPEC A10).
  Commit `Refactor: type the session layer honestly`.
- **T4.3** Delete dead code: `database/database_init.py` + module-level engine in
  `database/engine.py` (grep first that nothing imports them). Commit
  `Chore: remove dead database_init and import-time engine`.
- **T4.4** Defect fixes, one commit each:
  a) `Ledger.get_hash -> str` + corrected docstring;
  b) `contribution()` — tester writes the dual-sided failing test first, then fix
  `(debit or 0) - (credit or 0)` (D-010);
  c) `Category` module docstring; `transactions/__init__.py` header typo.
  (`utils/dates.py` and `engine.py` headers were handled in T2.3/T4.3.)

## Phase 5 — Transactions + reports

- **T5.1** `transactions/`: `__init__` + 10 subclasses — remaining `**kw: Any`,
  `main_account_types: list[Account.AccountType]`, `journal_entry` helpers.
- **T5.2** `reports/`: `FinancialStatement.__init__` + declared attributes (sections,
  results, totals, …); `income_statement`, `balance_sheet`, `cashflow_statement`,
  `trial_balance`, `aging_schedule`. Verify: report test files green; counts zero.

## Phase 6 — Scripts + tests

- **T6.1** Annotate `scripts/check_wheel_layout.py` and `scripts/smoke_install.py`.
- **T6.2** Tests: annotate `conftest.py` fixtures where needed; clear the pyright test
  errors (mostly attribute-access fallout from the library — re-check after phases 3–5);
  `mypy tests` (non-strict) zero. No test rewrites (SPEC §4). Verify: A4, A5, A6.

## Phase 7 — Ruff rule families on

- **T7.1** Enable `TC` + the `runtime-evaluated-base-classes` guard (D-004); delete the
  `F821` per-file ignores (verify the actual entry count first); fix fallout.
- **T7.2** Enable `ANN`; fix fallout (returns/params on remaining helpers).
- **T7.3** `RUF` + `PERF` (if deferred from T1.1). Any pure-formatting fallout is its own
  commit. Verify: A1, A2, A6 green after each.

## Phase 8 — Hooks + CI

- **T8.1** Pre-commit: add local hooks for `mypy` (package, strict) and `pyright`
  (single-version; purpose-scoped, `require_serial`).
- **T8.2** CI: add mypy + pyright steps (single job/version to keep the matrix fast).
- **T8.3** Run the full gate A1–A11 end-to-end and enumerate every suppression
  (`grep "type: ignore\|pyright: ignore"`) for the final report.

## Phase 9 — Docs site + release prep

- **T9.1** Skeleton `mkdocs.yml` (Material + mkdocstrings; dev docs excluded from nav) +
  `docs` dependency group swap (Sphinx → mkdocs/material/mkdocstrings pins); prove a
  skeleton build with one API page renders the namespace package. `mkdocs build --strict`.
- **T9.2** Content restructure (SPEC Q6): Home/quickstart; Getting Started; numbered
  Learn tutorial; Guides (reports, tax, compound entries — existing 641 lines are quarry);
  API Reference via mkdocstrings; Explanation (ledger hashing, recycling, isolation,
  reporting periods).
- **T9.3** Remove Sphinx: `docs/conf.py`, `docs/requirements.txt`, `docs/Makefile`,
  `docs/make.bat`, `docs/index.rst`, `docs/_build/`; migrate `.readthedocs.yaml` to MkDocs.
- **T9.4** Release prep: version 2.0.0, classifiers (3.10–3.13), CHANGELOG entry
  (breaking: Python floor, `delete` return, exception spelling + alias, dead-code removal,
  `__tablename__` explicitness), README refreshed with docs links. **No publish —
  user pushes the tag.** `publish.yml` untouched (follow-up).

## Checkpoints requiring the user

1. `delete -> None` (T4.2).
2. Any further public-surface breakage found mid-pass — surfaced before landing; default
   handling is a deprecation alias, never silent removal.
3. Any `| None` change that cannot be made DDL-neutral.
4. T4.2 (session layer) lands only after full pytest + import-diff review evidence is shown.

## Invariant guards (how each is enforced per commit)

| Invariant | Guard |
|---|---|
| Table names + column nullability | `tests/test_schema_snapshot.py` (from T0.2) |
| `E711` filter sites byte-identical | `git diff` review; sites named in DECISIONS |
| Import order (`models/__init__.py` etc.) | diff review; wheel smoke as backstop |
| Hash chain | existing ledger/is_secure tests + `smoke_install.py` |
| Money is `Decimal` | annotation review; no `float` introduced |
| Public API surface | `__all__`/README diff review; CHANGELOG lines |
