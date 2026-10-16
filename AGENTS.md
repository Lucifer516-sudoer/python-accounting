# AGENTS.md

Double-entry accounting **library** (PyPI: `python-accounting`), not an app. Core written
Nov 2023 – Mar 2024; only lightly maintained since. Sibling repo `python-profit` may consume it.

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
  (libmysqlclient / libpq) to build. **Neither path is exercised by any test or CI job.**

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
