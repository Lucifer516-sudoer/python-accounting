# AGENTS.md

Double-entry accounting **library** (PyPI: `python-accounting`), not an app. Core written
Nov 2023 – Mar 2024; only lightly maintained since. Sibling repo `python-profit` may consume it.

## 2.0 remodel status (updated 2026-10-20)

The contract is `docs/SPEC.md` (acceptance A1–A11) + `docs/DECISIONS.md` (D-001…D-016)
+ `docs/PLAN.md` (T0–T9). Read all three before touching anything.

**One agent session at a time on this repo.** On 2026-10-17 two sessions raced on the
same working tree: one committed under the other and edited files mid-verification.
Before starting work, confirm no other session is live; before committing, re-check
`git status` and `git log -1`.

**Plan reorder (user-approved 2026-10-20):** Phase 9 (docs site, T9.1–T9.3) was pulled
ahead of T4.1. The MkDocs site is live (`mkdocs.yml`, Material + mkdocstrings;
`uv run mkdocs build --strict` is zero-warning; Sphinx artifacts deleted;
`.readthedocs.yaml` migrated). T9.4 (release prep) stays at the end.

**Account deepening (user-approved 2026-10-20, D-016):** architecture review picked
Candidate 1 (split `Account.statement`, retire account stamps) with Candidate 2 (typed
dicts) riding along, landing as PLAN T4.0a–T4.0c BEFORE T4.1 — the mixins pass annotates
the settled shape. Candidate 4 (money seam, `utils/money.py`) is sequenced as T4.4a2,
just before the T4.4b `contribution()` fix so D-010 lands on `signed_sum()`. Fact
dossier: `/tmp/opencode/deepening-dossier.md`; vocabulary: `GLOSSARY.md`.

**Phase 3.5 DONE (2026-10-20):** T4.0a `e608c74` (typed result dicts), T4.0b `e450a94`
(split statement into schedule_outstanding/statement_running + restamping shim;
Balance gained `__allow_unmapped__` + cleared_amount/uncleared_amount/age stamps;
Transaction.balance stamp does NOT exist — collides with AssigningMixin.balance(), the
shim uses `setattr(entry, "balance", ...)`), T4.0c `646da17` (section_balances moved to
reports/financial_statement.py as a module-level function; Account.section_balances is
a delegating alias; the four account stamps + `__allow_unmapped__` deleted from
Account). **T4.1 DONE (2026-10-20):** all six mixins 0/0 in both checkers.
**T4.2–T4.4 DONE (2026-10-20):** see Progress below.

**T5.1 + T5.2 DONE (2026-10-20):** transactions/ `076a68c`; reports/ in three
commits — FinancialStatement base `361c2b0`, four statements `983a331`,
AgingSchedule `c8c0e2d`. **`mypy python_accounting` is now ZERO (was 468 at
baseline).** Remaining checker errors are tests-only: pyright 13 (float/int
literals assigned to Mapped[Decimal] attrs, test_base is_callable,
test_category TypedDict int literals), mypy tests 106 (mostly "call to untyped
function in typed context" — test helper defs need annotations; T6.2 scope).

Progress: T0–T8 done. T4.1 mixins (isolating `e7de7dd`, clearing `f842cc1`,
assigning `75d6d56`, trading `d90e936`, buying+selling `e83cfed`), T4.2 session
layer `5e886c3` (delete -> None user-approved), T4.3 dead code `e4e86d2`,
get_engine `3d2cb62`, T4.4a2 money seam `526f1f3` (`utils/money.py`:
signed_sum + line_item_tax_amount + line_item_posted_tax_amount; also fixed 2
pre-existing ledger.py errors — Tax.account_id nullable vs NOT NULL ledger
posts, assert-guarded), T4.4a get_hash `7dd4ebb` (earlier), T4.4b contribution
`a12abac` (D-010 fixed test-first: dual-sided test RED with Decimal("150.0000")
== 50, then routed through signed_sum), T4.4c header typo `99cf289`.
T6.1 scripts (no commit needed — already 0/0), T6.2 tests (`441e4c6` pyright
13→0 Decimal-wrapped literals + assert-guards; `1635b8b` mypy tests 106→0 via
ExceptionInfo renames + helper/conftest annotations + named-seam casts).
T7.1 TC rules + F821 per-file ignores deleted `3528552`; T7.2 ANN `b6a5da6`
(ANN401 global ignore for SQLAlchemy seams; tests per-file-ignore ANN);
T7.3 RUF+PERF `a348546` (RUF012 global ignore — ClassVar on `__mapper_args__`
is rejected by both checkers; 3 ClassVar config lists kept).
T8.1 pre-commit mypy+pyright hooks `2ccfd0f`→`2cccd0f`; T8.2 CI typecheck
steps `83ec638` (test.yml steps + python-package.yml dedicated 3.12 job).
T8.3 full gate A1–A9 green end-to-end; suppression inventory (A11): 1×
`type: ignore[assignment]` (line_item.py:94, documented), 0× `pyright:
ignore`, 3× `noqa` (account.py:628 B010, assignment.py:113 PLR0912,
ledger.py:99 PLR0913 — all inline-justified).
Current totals: **mypy package 0 / mypy tests 0 / pyright 0 / pytest 148 /
ruff format 93 files clean / ruff check All checks passed / mkdocs --strict
zero warnings / pre-commit 18 hooks green.**

T9.4 DONE (2026-10-20): release prep `4ec2edd` — version 2.0.0 (uv.lock
regenerated for the bump), CHANGELOG 2.0.0 entry (breaking: Python floor,
delete->None, account stamps retired, AccountingException spelling + alias,
dead database_init/engine removal, explicit __tablename__; fixes:
contribution() D-010, get_hash annotation; additions: typed result shapes,
checker gates, MkDocs site), README refreshed (3.10+ floor, docs blurb,
148 tests, v2.0.0 tag example). **The T0–T9 remodel is COMPLETE.** No publish
— the user pushes the tag (`v2.0.0`); publish.yml untouched (trusted
publishing is a follow-up).

T5.2 patterns worth reusing (reports/): instance-level config-driven StrEnums
are typed by per-subclass TYPE_CHECKING stub classes + `sections: "_Sections"`
declarations in the class body under TYPE_CHECKING, with the BASE declaring
`sections: Any` so the narrowing override is compatible in both checkers
(D-015 adapted from class-level to instance-level). Report `Accounts` enums
are `ClassVar["type[AccountTypeStub]"] = cast(...)` and passed to
section_balances via `list(IncomeStatement.Accounts)` — iterating the enum
class yields the same members the bare class did.

Hard-won lessons baked into the code (do not undo):

- `line_item.__init__` keeps `quantity = 1` (int) with a documented
  `# type: ignore[assignment]`. A Decimal quantity turns `amount` into Decimal and
  `Decimal / float` raises in `Ledger._post_simple`, because tests set `Tax.rate`
  as a float pre-flush. The DECIMAL column coerces on flush. The earlier
  `cast(Decimal, 1)` was a type lie — replaced by the explicit ignore (A11 form).
- Config-driven enums (D-015): TYPE_CHECKING stub class + module-level
  `cast("type[Stub]", StrEnum(...))` + `ClassVar["type[StubAlias]"]` class attr +
  in-block `StubAlias: TypeAlias = Stub`. The ClassVar annotation is required for
  mypy's fixpoint in mid-import-cycle modules. See `models/account.py` /
  `models/balance.py` for the canonical pattern.
- All quoted annotations (`Mapped["X"]`, `"tuple[Ledger, Ledger]"`) must be QUOTED —
  annotations evaluate at class-definition time and there is no
  `from __future__ import annotations` in this repo.
- Cooperative `super()` in a plain mixin (trading.py): give the mixin a
  TYPE_CHECKING-conditional base — `_CooperativeBase = Transaction` under
  TYPE_CHECKING, `object` at runtime — so both checkers resolve the chained
  `super().validate()` and host methods while the runtime MRO stays byte-identical.
  Full suite green proves mapper config is unaffected. See `mixins/trading.py`.
- zsh eats backticks in `git commit -m` messages (command substitution). Use single
  quotes or a heredoc.

Next up: T4.2 session layer (**user checkpoint pending: `delete -> None`**, D-009),
T4.3 dead-code removal, T4.4a2 money seam (`utils/money.py`, D-016 §7), T4.4b
`contribution()` test-first fix (D-010 — the precedence bug is deliberately still
present, wrapped in `Decimal(...)` with a NOTE comment).

## Setup — this will bite you

```bash
uv sync --all-groups    # required; deps are NOT vendored
uv run ruff format --check .   # CI gate, MUST pass
uv run ruff check .            # CI gate, MUST pass
uv run pytest                  # 115 tests, sqlite in-memory, no services needed
```

- Toolchain is **uv** (not poetry). `uv sync` creates `.venv`; `uv run` auto-syncs it.
  `uv lock` regenerates `uv.lock`; `uv lock --check` asserts it matches `pyproject.toml`.
- Dependency groups: `test`, `lint`, `docs`, `dev`. `uv sync --all-groups` gets everything.
- **Required order:** `ruff format --check` then `ruff check` then `pytest`. Any new finding fails CI.
- Single test: `uv run pytest tests/test_account.py::TestAccount::test_x`
  (`testpaths = ["tests"]` is set in `pyproject.toml`).
- A specific Python version: `uv run --python 3.9 pytest` (uv downloads the interpreter).
- **Formatter:** `ruff format` at `line-length = 88`. Run it yourself before committing —
  the pre-commit hook only *checks*. Reformatting is a commit of its own, never mixed into
  unrelated work.
- **pylint was removed** in the ruff migration; ruff's `PL` rules (PLR0912/0913/0914/0915/0917)
  are the replacement for the design checks pylint used to enforce.
- `tox.ini` was removed: with uv managing the environment and the CI matrix covering 3.9–3.13,
  tox's isolation was meaningless (it would have silently tested `.venv`, not its own env).

## Ruff is not a drop-in for pylint — three traps

Each of these cost real debugging time during the migration. All three are recorded in
`pyproject.toml` next to the rule they disable, with the reasoning inline.

1. **`E711` (`== None`) must stay ignored. Never "fix" these 68 sites.** The soft-delete filter in
   `database/event_listeners.py` is literally `cls.deleted_at == None`. On an instrumented
   attribute SQLAlchemy overloads `__eq__`, so `== None` compiles to `WHERE deleted_at IS NULL`,
   while `is None` is an ordinary Python identity test that compiles to `WHERE false`. The fix
   makes every row in the database invisible, and it type-checks fine while doing it.
2. **`I001` (isort) must stay ignored — import order is load-bearing.**
   `python_accounting/models/__init__.py` has to import `.base` before `.account`, because
   `account.py`, `assignment.py` and `balance.py` all do `from python_accounting.models import Base`.
   Sorting alphabetically puts `account` first and the package stops importing entirely. isort
   reordered 54 files before this was caught. Re-enable it only once the import graph is acyclic.
3. **`ruff check --fix` has broken this code once already.** UP015 rewrote
   `open(config_file, "r", -1, "UTF-8")` into `open(config_file, -1, "UTF-8")`, moving the
   buffering argument into the `mode` slot, which made the package unimportable. Always run the
   test suite after `--fix`; never `--fix` and `--unsafe-fixes` in the same breath as a commit.

Suppressions are now `# noqa: <CODE>` (e.g. `# noqa: PLR0913`), not `# pylint: disable=`.
There are only two left in the library; most of the 107 old pylint comments had no ruff
equivalent and were deleted outright.

## Pre-commit

`uv run pre-commit install` (once) installs the hook; it runs on every commit.

- Hooks mirror the CI gate: **ruff format + ruff check + pytest** as whole-project hooks, plus
  hygiene (trailing whitespace, EOF, merge conflicts, yaml/toml/json parse, large files, private
  keys, debug statements), `uv lock --check`, and a wheel-layout assertion.
- `scripts/check_wheel_layout.py` guards a **load-bearing packaging invariant** — see below.
- Fix what's fixable (`uv run pre-commit run --all-files`) rather than `--no-verify`.

## Architecture you cannot guess from filenames

- **`python_accounting/__init__.py` is deliberately absent** (removed in `a859be1`); the package is a
  namespace package. Don't "fix" the missing init file. `check_wheel_layout.py` asserts it stays gone.
- **`config.toml` at repo root is shipped package data and must sit at the *root of the wheel*.**
  `python_accounting/config.py` resolves it as `<package>/../config.toml` at import time, i.e. from
  the root of `site-packages`. A source checkout therefore cannot catch a packaging regression —
  the library imports fine locally and breaks for everyone who pip-installs it. The build backend is
  **hatchling** with `[tool.hatch.build.targets.wheel.force-include]`. Don't change build systems
  without re-running `scripts/check_wheel_layout.py`.
  Account types, account-code ranges, transaction prefixes, report sections and aging brackets are
  **data-driven from this file**, not hardcoded. Change behavior by editing it.
- **Global query filters are injected by SQLAlchemy `do_orm_execute` listeners** in
  `database/event_listeners.py`, not by the models: soft-delete filter on `Recyclable`, and
  entity isolation filter on `IsolatingMixin`. Consequences:
  - `session.get()` is overridden to route through `select()` *specifically* because the native
    `Session.get()` identity-map path bypasses these filters. Do not reintroduce the native path.
  - `session.entity` is auto-set on `transient_to_pending`. Adding an object with `entity_id=None`
    raises `MissingEntityError`.
  - Toggle filters via engine execution options `ignore_isolation` / `include_deleted`
    (threaded through `get_session` into `session.info`).
- **`session.delete()` is a soft delete**, not a delete: sets `deleted_at`, records a `Recycled`
  row, commits. Use `erase()` for a real delete, `destroy()` for permanent, `restore()` to undo.
  `Assignment` deletes route to `erase()` automatically.
- `Ledger` rows are hash-chained on insert (`after_insert` listener) to detect direct DB tampering.
  Any change to ledger data shape breaks hash verification.
- Reporting periods are auto-created/rolled forward by an event listener when `datetime.today().year`
  no longer matches the entity's open period.
- Money is **`Decimal`** throughout. Never introduce `float` in amount paths.

## Testing quirks

- Reuse fixtures in `tests/conftest.py` instead of rebuilding them: `engine`, `session`, `entity`,
  `currency`, `post_document`, `fixed_today`.
- **`fixed_today` only freezes two modules**: `python_accounting.utils.dates` and
  `python_accounting.mixins.assigning`. New code calling `datetime.now()`/`today()` in any *other*
  module will stay live and make tests year-dependent — either add that module to the monkeypatch
  list or pass dates explicitly.
- Reporting-period tests were deliberately made year-independent in `23716cb`. Don't reintroduce
  hardcoded years.
- Tests use in-memory sqlite. The MySQL/Postgres drivers are **optional extras**
  (`pip install python-accounting[mysql]` / `[postgres]`) because both need system headers
  (libmysqlclient / libpq) to build. **pytest never touches them**; the CI `docker` job and
  `docker compose up --build --abort-on-container-exit --exit-code-from drivers` are the
  only coverage the driver paths get.

## Ship artifacts (wheel smoke, Docker)

- The gate proves the *source tree* works; only a container or a clean venv proves the
  *wheel* does. `scripts/smoke_install.py` refuses to run against a checkout (it looks for
  `pyproject.toml`/`.git` next to the package directory) — do not weaken that guard, it is
  the whole point. It also exercises the `config.toml`-from-site-packages resolution a
  checkout cannot.
- `Dockerfile` stages: `builder` (wheel) → `smoke` (default target; installs the wheel as
  UID 10001 and runs the smoke test) → `drivers` (adds the mysql/postgres extras).
  `.dockerignore` keeps the context to what the build reads; a new file the wheel needs must
  be allowed there or the container build breaks while local builds stay green.
- `docker-compose.yml` + `.env.example`: Postgres and MySQL plus the `drivers` runner.
  Compose interpolates `${VAR:-default}`; never hardcode credentials in the compose file.
- CI: `wheel-smoke` installs the built wheel into a clean venv on 3.12 only (the build job
  covers 3.9–3.13 from source); `docker` builds the image, asserts it is non-root, and runs
  the compose flow.

## Conventions

- Every module starts with the same 6-line header (`# <path>` + MIT copyright). Preserve it. It
  references an `AUTHORS` file that does not exist — leave the reference alone, it's pre-existing.
- Local `# noqa: <CODE>` comments are used instead of loosening `[tool.ruff.lint]`. Follow that.
- Commit message convention is mixed: `Chore: ...` / `Fix: ...` (recent) and `Update: ...` (old).
  Recent commits use conventional prefixes.

## Known debt (verified, unfixed)

- **`docs/_build/` (267 files) and `dist/` (6 wheels/sdists) were tracked in git** and are now
  untracked + ignored. `dist/` and `docs/_build/` still exist on disk from before.
- `.github/workflows/publish.yml` still uses `PYPI_API_TOKEN` rather than trusted publishing;
  the contradictory `id-token: write` permission was removed and the upgrade path is commented.
- `pyproject.toml` excludes Python 3.14 (`requires-python = ">=3.9,<3.14"`); SQLAlchemy is capped
  `>=2.0.23,<2.1` (locked at 2.0.54).
