# Decision log — python-accounting 2.0 Remodel

Companion to `docs/SPEC.md` (requirements) and `docs/PLAN.md` (execution order).
Every decision here was pressure-tested with actual probe runs against the repo's
own environment (SQLAlchemy 2.0.54, Python 3.13 venv). Scratch evidence lives in
`/tmp/opencode/` (`mypy-baseline2.txt`, `pyright-modern.json`, `tables-before.txt`,
`probe/`); durable numbers go to `docs/typing-baseline.md` and
`tests/test_schema_snapshot.py` per PLAN tasks T0.1–T0.2.

Baselines this effort must drive to zero, measured 2026-10-16:

| Checker | Command | Result |
|---|---|---|
| pyright 1.1.414 (standard) | `pyright python_accounting tests scripts` | **334 diagnostics** — 251 `reportAttributeAccessIssue`, 45 `reportArgumentType`, 18 `reportUndefinedVariable`, 7 `reportAssignmentType`, 5 `reportReturnType`, 2 `reportIncompatibleMethodOverride`, 2 `reportOptionalMemberAccess`, 4 singletons |
| mypy (strict) | `mypy --strict --explicit-package-bases python_accounting` | **468 errors in 41 files** — 187 `attr-defined`, 88 `no-untyped-def`, 54 `type-arg`, 43 `assignment`, 22 `has-type`, 19 `arg-type`, 18 `name-defined`, 12 `no-any-return`, rest singletons |

---

### D-001 — Checkers: mypy strict (CI gate) + pyright standard (editor/pre-commit gate)

**Status:** accepted · **Date:** 2026-10-16

- **Decision:** both checkers run at zero errors; `py.typed` ships in the wheel; no
  unjustified suppressions; suppressions must be one-line, rule-specific, inline-justified,
  and enumerated in the final report (SPEC §8 A3–A5, A11).
- **Why:** mypy strict is the CI truth machine; pyright standard is what editors (and the
  maintainer's LSP) show live. Running both multiplies confidence and caught real
  divergences during probing (see D-005, D-007).
- **Consequences:** every annotation pattern must satisfy *both* checkers before it is
  adopted. Probe evidence lives below in the per-topic entries.

### D-002 — pyright config vehicle: `pyrightconfig.json`, not `[tool.pyright]`

**Status:** accepted (amends SPEC §7.2) · **Date:** 2026-10-16

- **Context:** the system pyright (1.1.367) cannot parse the repo's `pyproject.toml` at all
  (`Pyproject file parse attempt 6 error: TomlError line 54 col 81`), which also explains
  the LSP noise reported by the user. Bisect probe: a minimal pyproject containing the
  PEP 735 `dev = [{ include-group = ... }, ...]` dependency-group fails under 1.1.367 in
  both single-line and multi-line form; adding a `pyrightconfig.json` next to it makes the
  parse error disappear entirely. Modern pyright (1.1.414, installed and verified) parses
  the same pyproject fine.
- **Decision:** config lives in **`pyrightconfig.json` at repo root**; `[tool.pyright]`
  is *not* used. Checkers are pinned in the `lint` dependency group so CI uses a known-good
  pyright regardless of what editors ship.
- **Contents (exact):**
  ```json
  {
    "include": ["python_accounting", "tests", "scripts"],
    "typeCheckingMode": "standard",
    "pythonVersion": "3.10",
    "venvPath": ".",
    "venv": ".venv"
  }
  ```
- **Consequences:** the same config is read by surface-old and modern pyrights alike
  (the JSON format predates the toml one and has no PEP 735 parsing dependency). One more
  root file; documented in README/AGENTS.md so nobody "cleans it up".
- **Note:** a stale `pyright` binary misreported 624 diagnostics; the authoritative
  1.1.414 baseline is 334. Do not trust old pyrights for numbers.

### D-003 — mypy and the namespace package: `explicit_package_bases = true`

**Status:** accepted · **Date:** 2026-10-16

- **Evidence:** plain `mypy --strict python_accounting` refuses to run: *"Common
  resolutions include: a) adding __init__.py, b) using --explicit-package-bases…"*. The
  repo must keep its namespace-package layout (SPEC §6), so adding `__init__.py` is off
  the table. With the flag, mypy runs cleanly (468-error baseline above).
- **Decision — `[tool.mypy]` block (exact):**
  ```toml
  [tool.mypy]
  python_version = "3.10"
  strict = true
  explicit_package_bases = true

  [[tool.mypy.overrides]]
  module = ["tests.*"]
  disallow_untyped_defs = false
  disallow_incomplete_defs = false
  check_untyped_defs = true
  ```
- **Why the override:** SPEC §4 ("tests get lint/type compliance only") — tests are
  checked (A4) but are not rewritten into fully-annotated code. `check_untyped_defs = true`
  keeps real type checking active inside them.
- **Consequences:** `uv run mypy python_accounting` (strict) and `uv run mypy tests`
  (relaxed) are the canonical commands (SPEC A3/A4). If mypy is ever run from a different
  cwd, revisit `mypy_path`.

### D-004 — Cross-model references: `TYPE_CHECKING` imports + quoted `Mapped["X"]`

**Status:** accepted · **Date:** 2026-10-16

- **Decision:** every forward reference in `Mapped[...]` / `relationship(...)` stays
  **quoted**; the name is imported only under `if TYPE_CHECKING:` so it never reaches
  runtime. `from __future__ import annotations` is **not** added to the model layer.
- **Why:** SQLAlchemy evaluates `Mapped` annotations at runtime (`declared_scan`); ruff's
  `TC` rules would happily move a needed import into `TYPE_CHECKING` and produce a
  runtime `MappedAnnotationError`. Quoted names are resolved by SQLAlchemy's registry
  fallback instead, so a type-checking-only import is safe. Probe: a `Base` + mixin +
  model mirror with a TYPE_CHECKING import and quoted refs mapped, `configure_mappers()`
  succeeded, `create_all()` worked, relationship targets resolved — under mypy strict,
  pyright, and at runtime.
- **Ruff guard (exact):**
  ```toml
  [tool.ruff.lint.flake8-type-checking]
  runtime-evaluated-base-classes = ["python_accounting.models.base.Base"]
  ```
  With this, ruff `TC` offered zero move-to-TYPE_CHECKING findings in the probe package.
  `future-annotations` stays disabled; `quote-annotations` stays disabled.
- **Consequences:** the `F821` per-file ignores (`models/*.py`, `mixins/*.py`,
  `database/session_overrides.py`) become unnecessary and are deleted in the same commit
  that enables the `TC` rules (PLAN T7.x) — never before, or every commit in between is red.

### D-005 — `__tablename__` de-magicization (amends SPEC §7 deliverable 10)

**Status:** accepted · **Date:** 2026-10-16

- **Context:** `Base` carries `@declared_attr.directive def __tablename__(cls) -> str`
  returning `cls.__name__.lower()`. Probe results:
  - Under pyright, **every** subclass assignment next to the directive errors
    (`__tablename__ = "x"` → `reportAssignmentType`; `: str` and `ClassVar` variants →
    `reportIncompatibleVariableOverride`). mypy tolerates plain assignment but rejects the
    `ClassVar` variant. A directive that blocks its own subclasses from declaring the
    attribute is not doing us any favors.
  - The `__init_subclass__` auto-naming alternative **fails at runtime**: SQLAlchemy's
    `DeclarativeBase.__init_subclass__` maps the class inside `super()` before the hook can
    inject a name → `InvalidRequestError: Class H1 does not have a __table__ or __tablename__`.
  - A clean `DeclarativeBase` (no directive) with explicit names is green under both
    checkers and maps correctly. A single-table-inheritance child with **no** `__tablename__`
    at all maps to the parent's table and round-trips (`rows: ['T1', 'T2']`, one table `t`).
  - Keeping `__tablename__ = None` after the directive is gone makes **mypy** error
    (`Incompatible types in assignment (None vs str) [assignment]`). The 10 transaction
    subclasses all carry that marker today.
- **Decision:** remove the directive from `Base`; add explicit `__tablename__` strings to
  the 11 previously auto-named classes (`account`, `assignment`, `balance`, `category`,
  `currency`, `entity`, `ledger`, `recyclable`, `recycled`, `tax`, `user`); delete the 10
  `__tablename__ = None` markers in `transactions/` (STI children need no marker).
- **Invariant:** table names are byte-identical. Golden list captured:
  `account | assignment | balance | category | currency | entity | ledger | line_item |
  recyclable | recycled | reporting_period | tax | transaction | user` (14 tables —
  `/tmp/opencode/tables-before.txt`). Guard: new `tests/test_schema_snapshot.py` asserting
  table names and column nullability (PLAN T0.2, SPEC A10).
- **Consequences:** explicit greppable names everywhere; `Base` loses its only
  `declared_attr` member; the schema snapshot test must be green before and after.

### D-006 — Nullability lives in the annotation; DDL is pinned separately

**Status:** accepted · **Date:** 2026-10-16

- **Evidence (probe-confirmed):** SQLAlchemy infers `nullable` from the annotation when
  `nullable=` is absent. `Mapped[str]` → `NOT NULL`; `Mapped[str | None]` → nullable.
  So *adding* `| None` to an unpinned column silently flips generated DDL.
- **Decision:** every column becomes `Mapped[X | None]` *iff* its current effective
  nullability is nullable, and **every** annotation change that touches optionality pins
  `nullable=` explicitly in the same `mapped_column(...)` call. Relationships follow
  `Mapped["X | None"]` for nullable FKs; collections stay `Mapped[list["X"]]`.
- **Consequences:** the schema snapshot test (T0.2) is the mechanical guard; `git diff`
  review confirms `nullable=` pins landed. Violations are a checkpoint item (SPEC §9).

### D-007 — `foreign_keys` inside `declared_attr`: string-qualified form

**Status:** accepted (string form); dynamic variant verified at T4.1 · **Date:** 2026-10-16

- **Evidence:** `relationship("Entity", foreign_keys=[cls.entity_id])` inside a
  `declared_attr` is flagged by **both** checkers (mypy `[list-item]`, pyright
  `reportArgumentType`). Annotating `cls` as `type["Mixin"]` makes pyright *worse*
  (`reportGeneralTypeIssues`: parameter must be a supertype). The **string form**
  `foreign_keys="SomeClass.attr"` is clean under both checkers and resolves at runtime.
- **Decision:** prefer the string form in the mixin seam; the concrete class name is
  interpolated inside the `declared_attr` (`foreign_keys=f"{cls.__name__}.entity_id"`).
  A 5-minute probe at T4.1 confirms the f-string variant under both checkers + runtime
  before the commit; if it fails on any site, that single site gets **one** documented
  inline suppression, enumerated in the final report — no other fallback.
- **Consequences:** `mixins/isolating.py:28` and any relationship using bare attribute
  lists (triaged during the models pass) adopt the string form.

### D-008 — Session layer composition: mixins inherit `Session` at runtime

**Status:** accepted, MRO verification at T4.2 · **Date:** 2026-10-16

- **Decision:** `SessionOverridesMixin(Session)`, `EventListenersMixin(AccountingFunctionsMixin)`,
  `AccountingFunctionsMixin(Session)`; `AccountingSession` keeps its current MRO shape;
  `entity: "Entity"` is declared where the listener-read attribute lives.
- **Why:** the three mixins call `super()` and touch `self.*` session APIs; giving them the
  real base class types every `self.` site with zero casts, zero conditional bases, zero
  Protocols. Rejected: conditional `TYPE_CHECKING` bases (fights `warn_unreachable`),
  Protocol-typed `self` (must be a declared base), `cast` sprinkles. Merging the three
  mixins into `AccountingSession` is cleaner long-term but out of 2.0 scope (no additional
  checker benefit; deletes modules for no gain).
- **Verification:** baseline MRO recorded before the change
  (`python -c "from python_accounting.database.session import AccountingSession as A; print(A.__mro__)"`)
  must be functionally unchanged after; full pytest is the behavior gate.

### D-009 — Session API signatures

**Status:** accepted; `delete` return change = user checkpoint · **Date:** 2026-10-16

- `get`: **one widened signature** mirroring the base —
  `get(self, entity: type[_O] | Mapper[_O], ident: Any, **kwargs: Any) -> _O | None`.
  Probe: the narrow `type[_O]`-only signature fails **both** checkers; the widened one is
  **clean in both with zero ignores**. No overload ladder (callers don't branch on
  `include_deleted=`).
- `delete`: base contract is `delete(instance: object) -> None`; the override currently
  returns `bool` for a value **no test or internal caller reads** (internal callers
  discard it: `_ = [session.delete(a) for a in ...]`). Honest signature = `-> None`
  (behavior change in the strict sense, invisible to every in-repo caller — awaiting
  user sign-off as checkpoint 1; fallback if declined: keep `bool` + the single
  documented combined suppression
  `# type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]`,
  probe-confirmed to satisfy both checkers on one line).
- `restore -> bool` (the `False` for destroyed records is informative);
  `destroy -> None`, `erase -> None` (they always succeed or raise; no caller reads a
  value). `get_session(...)` returns `AccountingSession`, not `Session`.
- Combined-ignore syntax (one line) is the canonical **fallback** only — never on the
  public surface silently.

### D-010 — `Transaction.contribution()` is defective; rewrite with a regression test

**Status:** accepted · **Date:** 2026-10-16

- **Evidence:** the expression parses as `(debit or (0 - credit)) or 0` — when the debit
  sum is non-zero it is returned and the credit sum is **ignored**; the intended net
  (debits minus credits) only accidentally holds for single-sided accounts. Tests only
  exercise single-sided accounts (test_transaction.py:751–753, test_journal_entry.py:168–171),
  which is why the bug lives.
- **Decision:** rewrite explicitly as `(debit or 0) - (credit or 0)`; add a **dual-sided
  regression test** that fails against the old code (write the test first). TDD order per
  PLAN T4.4. Caller audited: `models/account.py:394` (statement generation).

### D-011 — Dynamically-set attributes become plain annotations

**Status:** accepted · **Date:** 2026-10-16

- Report and model instances get attributes assigned by library code at runtime
  (`account.opening/closing/movement`, report `sections/results/session/totals...`).
- **Decision:** declare them as annotation-only instance attributes on the owning class
  (`cleared_amount: Decimal`). Setter semantics and pre-set `AttributeError` behavior are
  unchanged. Rejected: properties (changes semantics), real columns (schema change),
  `ClassVar` (wrong meaning).
- **Implementation note (2026-10-17, landed with the account pass):** on a declarative
  class, a bare (non-`Mapped`) annotation makes SQLAlchemy's Annotated Declarative Table
  form raise `MappedAnnotationError` at mapper configuration time. Every mapped class
  carrying dynamic-attribute annotations must therefore declare
  `__allow_unmapped__ = True` (e.g. `class Account`). Caught by the full pytest run —
  mapper configuration is exercised there, so a missing marker fails loudly, never silently.

### D-012 — Gate sequencing: annotations first, then ruff `ANN/TC/RUF/PERF`, hooks last

**Status:** accepted · **Date:** 2026-10-16

- Enabling `ANN` before the annotation pass leaves every commit red; enabling hooks before
  zero-error forces `--no-verify`. Order (PLAN phases): annotate → enable extras + delete
  `F821` ignores → wire hooks/CI. `RUF`/`PERF` are evaluated at T1.1 and only ship early
  if their fallout is trivial; otherwise they land with the rest in phase 7.
- Standing rules: formatter-only changes are their own commit; never mix `--fix` with
  `--unsafe-fixes`; run the full test suite after any `--fix` (AGENTS.md history).

### D-013 — Scope guardrails (what changed vs. 1.1.0)

**Status:** accepted · **Date:** 2026-10-16

- Public-surface changes in 2.0.0, each with its own commit and CHANGELOG line:
  `AccountingException` spelling + `AccountingExeption` alias (deprecation note);
  `Ledger.get_hash -> str` (was an annotation lie); `delete` return type (D-009);
  `requires-python >= 3.10`; dead `database_init()` + module-level engine removed.
- Everything else is additive/repair: annotations, docstrings, explicit `__tablename__`
  (same names), docs site swap (Sphinx → MkDocs), gate hardening.
- Never touched: `E711` filter sites, `I001` import order (incl. `models/__init__.py`
  bind order), runtime import graph, hash-chain row shape, `config.toml` wheel-root
  placement, namespace-package layout, `Decimal`-only money paths, `PLC0415` imports.

### D-014 — Docs site: MkDocs + Material + mkdocstrings; dev docs excluded

**Status:** accepted · **Date:** 2026-10-16

- `mkdocs.yml` + Material for MkDocs + `mkdocstrings[python]`; RTD config migrated to
  MkDocs; plugin set kept minimal (Zensical 0.1.0 is Nov 5, 2026 — portability matters).
- `docs/SPEC.md`, `docs/DECISIONS.md`, `docs/PLAN.md`, `docs/typing-baseline.md` are dev
  docs: committed, excluded from the built site.
- griffe/mkdocstrings on a namespace package (`python_accounting` has no top-level
  `__init__.py`, deliberately) is proven on a skeleton build before content is written
  (PLAN T9.1).
- No doc-snippet execution in CI (SPEC §4).

### D-015 — Config-driven enums are mirrored by TYPE_CHECKING stubs + a cast

**Status:** accepted · **Date:** 2026-10-16

- **Context:** `Account.AccountType`, `Transaction.TransactionType`,
  `Balance.BalanceType` and `Balance.BalanceTransactions` are created at import time by
  `StrEnum("Name", {...})` from `config.toml`. The type checkers saw only the
  `strenum.StrEnum` factory result, so member access across the repo (~500 sites) was a
  checker error (`reportAttributeAccessIssue` / `attr-defined`).
- **Decision:** each enum gets (a) a `TYPE_CHECKING`-only stub class with the same
  member names (placeholder values; never executed) and (b) a module-level
  `cast("type[Stub]", StrEnum(...))` assigned to the former class attribute. Member
  access, `.name`/`.value`, iteration, and subscripting (`account_type_enum["BANK"]`)
  resolve in mypy strict and pyright standard with zero suppressions.
- **Rejected:** per-site ignores (~500 sites); leaving the factory untyped. Probe
  corrections that cost time and are now baked in: stub members must use a value
  (pyright rejects `= ...`), the member list must be complete, and the factory gets a
  list of `(name, value)` tuples (mypy wants `Sequence[Any]`; runtime accepts tuples).
- **Guard:** `tests/test_enum_stubs.py` compares stub member names (read from source
  via `ast`) with the runtime enum members in both directions — drift in either
  direction fails the suite.
- **Evidence:** landing commit moved mypy 414 → 339 and pyright 317 → 198; 122 tests
  pass; runtime enum values and iteration unchanged (full suite + hash-chain tests).
- **Implementation notes (2026-10-17, landed with the account/category passes):**
  three details are load-bearing and were each proven by checker probe:
  (a) each class attribute is declared `EnumName: ClassVar["type[Stub]"] = enum_var`.
  The explicit annotation is **required** — without it mypy's fixpoint in modules
  analyzed mid-import-cycle (`category`, `income_statement`, `balance_sheet`, 19
  `has-type` errors) fails with `Cannot determine type of AccountType`; the
  `ClassVar` wrapper is what keeps SQLAlchemy from treating the annotation as a
  mapping directive (SA skips ClassVar-annotated attributes when mapping).
  (b) inside the owning class body the stub is reachable through an explicit
  `StubName: TypeAlias = StubName` alias declared in the `TYPE_CHECKING` block,
  because the class attribute shadows the module-level stub name.
  (c) the class attribute **cannot** be used in type-expression positions —
  pyright rejects any annotated attribute there (`reportInvalidTypeForm`).
  Annotation positions must import the stub class under `TYPE_CHECKING` instead
  (`account_type: "AccountType"`); value positions (`Account.AccountType.BANK`)
  stay untouched. First fix of this kind: `reports/aging_schedule.py`.

### D-016 — Account deepening: result types replace stamped attributes and string-keyed dicts

**Status:** accepted (grill rounds 1–2, user approved all defaults) · **Date:** 2026-10-20

**Context.** Architecture review (2026-10-20, report at
`/tmp/opencode/architecture-review-20261020-090222.html`, fact dossier at
`/tmp/opencode/deepening-dossier.md`) found the dominant friction: data contracts between
`Account` and its six consumers expressed as stamped attributes and string-keyed dicts.
`Account.statement()` is 157 lines forking on a `schedule` flag into two disjoint reports;
`section_balances()` is a reports concern living on the model. Evidence that made the
aggressive option safe: **no downstream consumer exists on disk** (`python-profit` absent,
`kanakku` has zero references), and the four account stamps (`opening`/`closing`/
`movement`/`balance`) have **zero readers** outside the stamping code itself.

**Decisions (each grill-approved):**

1. **Split, don't fork.** `statement()` splits into `schedule_outstanding()` (aging half,
   RECEIVABLE/PAYABLE only) and `statement_running()` (running-balance half), both staying
   as `Account` methods — a models→reports seam here would create a second import
   inversion like the fragile `models/balance.py:34` one. `section_balances()` moves to
   the reports layer next to `FinancialStatement` (its 4 callers are all reports);
   `Account.section_balances` remains as a delegating alias.
2. **Result types.** `OutstandingSchedule` (rows: `ScheduleRow(entry: Transaction |
   Balance, cleared_amount, uncleared_amount, age)`) and `AccountStatement` (rows:
   `StatementRow(entry: Transaction, balance, debit, credit)`) are frozen dataclasses —
   genuinely new shapes. `SectionBalances`, `CategoryBalances`, `TransactionTax` are
   TypedDicts — dict keys stay byte-identical so existing tests asserting
   `result["opening"]` etc. stay green untouched. `FinancialStatement.balances` stays a
   plain dict: its keys are config-driven *data* (section names, labels, heterogeneous
   `"debit"`/`"credit"` scalars); a TypedDict would lie. Naming follows the
   `OpeningTrialBalance` precedent (plain nouns, no `Result` suffix).
3. **Legacy aliases = single implementation + shim.** `statement()` becomes a ~10-line
   dispatcher: calls the new method, restamps each row's computed values onto `row.entry`
   (transaction-level stamps only), returns the legacy dict shape. The old loop body is
   not duplicated. `section_balances` alias delegates without stamping.
4. **Account stamps retired entirely.** The new implementations accumulate locally and
   never stamp; the four D-011 bare annotations (`account.py:122–129`) and
   `__allow_unmapped__` (account.py:98 — needed solely for those four) are deleted.
   CHANGELOG break line under 2.0.0. Transaction-level stamps (`debit`/`credit`/
   `cleared_amount`/`uncleared_amount`/`age`) STAY declared and the shim keeps restamping
   them — 30+ test assertions read them.
5. **`Decimal(0)` seeding.** All new accumulators seed `Decimal(0)` (today they start as
   `int 0`; `0 == Decimal(0)` keeps tests green; `OpeningTrialBalance` already does this).
6. **Out of scope.** `AgingSchedule`'s own `account.balances` bracket-dict stamping stays
   (report's documented output shape, tests pin it); AgingSchedule only migrates to
   consume `ScheduleRow.age`/`.uncleared_amount`. `bulk_assign` migrates to consume the
   schedule rows from day one.
7. **Sequencing.** Lands as PLAN T4.0a–T4.0c, BEFORE T4.1 (six mixins annotate the
   settled shape). Candidate 4 (money seam, `utils/money.py`) is sequenced as T4.4a2,
   just before the T4.4b `contribution()` fix so D-010 lands on `signed_sum()`.
8. **Tests.** ~2 new test files proving the new seam + alias delegation; zero existing
   test edits unless a test breaks.

**Load-bearing constraints honored:** no mapped columns added (D-011 mechanics untouched
beyond deleting Account's four annotations); schedule-mode rows keep duck-typing
`Transaction | Balance` (Balance rows are opening-balance entries;
`test_schedule_clearances.py:66` asserts a Balance appears); hash chain, `E711` sites,
import order, `Decimal`-only money all untouched.

**Consequences:** the implicit contract between `Account` and its consumers becomes
explicit, typed interfaces; mypy/pyright can verify what only dict-key folklore knew
before. Vocabulary recorded in `GLOSSARY.md`.

---

### D-017 — Post-2.0 deepening: period resolution, netting seam, line item total

**Status:** accepted (grill round 1, user approved all defaults) · **Date:** 2026-10-20

**Context.** Post-2.0 architecture review (report at
`/tmp/opencode/architecture-review-20261020-1425.html`) ranked the remaining friction.
The user picked the top cluster: period resolution ×4 spellings (finding 1), aggregate
query construction beyond `signed_sum` (finding 2), the positional `get_dates` quadruple
(finding 12), and the `line_item.amount * quantity` duplication (finding 15). All
defaults approved; target is **zero existing-test edits**.

**Decisions:**

1. **Period seam = `ReportingPeriod.for_year(session, year)` classmethod**, next to
   `get_period`. It consolidates exactly two sites that build the sentinel date
   `datetime(year, session.entity.year_start, 1, 0, 0, 0)`: `utils/dates.py:get_dates`
   and `Account.opening_balance`. **Descope correction (Q5):** the session mixin's
   `_year_period` (accounting_functions.py:32-48) is NOT consolidated — it queries
   `calendar_year == year` directly with the load-bearing `ignore_isolation=True`
   execution option, not the sentinel-date construction; delegation would change the
   query. The rollover listener's live clock (finding 10) stays, as a separate concern.
2. **Netting seam = two per-model functions in `utils/money.py`**:
   `net_ledger(session, *filters)` / `net_balance(session, *filters)`. The model, the
   side column, the `Balance.BalanceType` enum and the aggregate query construction live
   inside the seam; callers state only scope filters (entity/currency/account/date).
   `signed_sum` stays public and is consumed internally. Callers migrated:
   `Account.balance_movement`, `Account.opening_balance`, `Transaction.contribution`.
   **Entity filter stays EXPLICIT in caller filters** — byte-identical SQL; no
   auto-entity injection.
3. **`get_dates` returns a NamedTuple `Dates`** (fields `start_date`, `end_date`,
   `period_start`, `period_id`) from `utils/dates.py`. Positional unpacking keeps
   working, so all ~9 call sites and tests stay byte-identical with zero edits.
4. **Line item total = `line_item_total(line_item) -> Decimal`** in `utils/money.py`,
   absorbing the four `line_item.amount * line_item.quantity` spellings:
   `Transaction.amount` property, `Ledger._post_simple`, `JournalEntry.get_compound_entries`,
   and `line_item_posted_tax_amount`'s own local.
5. **`Balance.opening_trial_balance` hand-bucketing LEAVE as-is** + this note: it
   sign-buckets (debit vs credit by sign of the balance) rather than nets by
   `BalanceType`, so `net_balance` does not apply; the function is near-dead
   (tests-only). Recorded so a future explorer doesn't re-suggest it.
6. **Process:** docs first (this entry + GLOSSARY + PLAN Phase 10), then tester writes
   seam tests RED (`tests/test_money.py`, `for_year`/`Dates` tests), then implement
   period seam, then netting + line item total. AGENTS.md updated after each landing.

**Load-bearing constraints honored:** `Decimal`-only money; hash-chain row shape
untouched; `E711` sites untouched; import order untouched (money.py keeps models imports
function-level/TYPE_CHECKING per the existing PLC0415 pattern); no schema change.

---

## Probe index (scratch, `/tmp/opencode/`)

| Artifact | Content |
|---|---|
| `mypy-baseline2.txt` | mypy strict 468-error baseline with `--explicit-package-bases` |
| `pyright-modern.json` | pyright 1.1.414 334-diagnostic baseline (authoritative) |
| `pyright-baseline.json`, `mypy-baseline.txt` | first-run baselines from stale pyright 1.1.367 — **unreliable, kept for the TOML-bug story only** |
| `tables-before.txt` | 14-table golden list |
| `probe/` | probe package: declared_attr+TYPE_CHECKING, session overrides, DDL trap, tablename variants (incl. runtime round-trip), foreign_keys variants |
