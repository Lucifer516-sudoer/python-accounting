# SPEC — python-accounting 2.0 Remodel

Status: awaiting approval · Date: 2026-10-16 · Target version: 2.0.0

## 1. Why

`python-accounting` is a published double-entry accounting library (PyPI, 1.1.0) with strong
bones — hash-chained ledger, session-injected entity isolation, soft-delete audit trail,
data-driven configuration, 115 tests — and a stale surface:

- No type checker has ever run against it: pyright reports **334 errors** across 84 files.
- Only **45.4%** of functions are fully annotated; the `session` parameter — the most
  important type in a SQLAlchemy library — is unannotated in 45 places.
- File-level docs are one-liners; some headers point at the wrong paths.
- The docs site is a Sphinx installation whose config still says `release = "0.1.0"`
  (package is 1.1.0), with 267 stale generated files and a dead `index.rst` stub.

This remodel makes the library's contract honest and durable: types consumers can trust,
documentation that teaches, and lint/type gates that prevent rot.

## 2. Locked decisions — grill round 1 (2026-10-16)

| # | Decision | Choice |
|---|----------|--------|
| Q1 | Scope | **C** — quality pass + defect fixes + API cleanup. Any further breaking change is surfaced to the user before it lands; default treatment of a public wart is a deprecation alias, never silent removal. |
| Q2 | Python floor | **B** — `requires-python = ">=3.10,<3.14"`; CI matrix shrinks to 3.10–3.13. |
| Q3 | Type checking | **mypy `strict` (CI gate) + pyright `standard` (LSP/editor gate)**, `py.typed` shipped, zero errors in both, no unjustified suppressions. |
| Q4 | Gate hardening | **A** — after the annotation pass, ruff gains `ANN`, `TC`, `RUF`, `PERF`; the four `F821` per-file ignores are deleted (resolved by `TYPE_CHECKING` imports). All existing documented ignores stay. |
| Q5 | Docs engine | **A** — MkDocs + Material for MkDocs (what SQLModel runs) + `mkdocstrings[python]`; RTD-ready config; plugin set kept minimal so a later Zensical 0.1.0 switch is cheap. Look: sleek and impressive (tuned palette, navigation and code-block features). |
| Q6 | Docs content | **B** — full SQLModel-style restructure: Home/quickstart, numbered Learn tutorial, task Guides, generated API Reference, internals Explanation. Existing 641 lines of Markdown are quarry, not scripture. |
| Q7 | Release | User-delegated. Version **2.0.0** (Python-floor drop is a compat change), CHANGELOG entry, release prepared but **not published** — the user pushes the tag. |

## 3. Goals

- **G1** — Every public and internal def in the library fully annotated; `py.typed` inside
  the wheel so downstream consumers (`python-profit`, PyPI users) get real types.
- **G2** — Signatures cannot lie: `Ledger.get_hash` returns `str`; no annotation
  contradicts runtime behavior.
- **G3** — Every module carries a real docstring (role, why it exists, how it fits);
  wrong file headers fixed.
- **G4** — The gates defend the state: ruff (with `ANN`/`TC`/`RUF`/`PERF`), mypy strict,
  pyright standard, pytest, mkdocs `--strict` all green in CI and pre-commit.
- **G5** — Dead code and stale artifacts gone; `AccountingException` correctly spelled
  with a working `AccountingExeption` alias.
- **G6** — Documentation site that a stranger can learn from in SQLModel fashion.

## 4. Non-goals

- **No accounting-semantics changes.** Posting, ledger hashing, clearing/assignment,
  reporting periods, and the `Decimal`-only money rule are untouched except where a
  provable defect is fixed (each with a regression test).
- **No schema/data-model changes, no migrations.**
- **No new features** (auth, multi-tenancy, new reports).
- **No PyPI publish, no tag** — release is prepared only.
- **No doc-snippet execution in CI** (known gap; follow-up material).
- **No Sphinx→Zensical jump now** — Material today, config kept portable.
- **No Python 3.14 support** — follow-up (needs pytest 8 upgrade; droppable scope-creep).
- **No test rewrite** — tests are the safety net; they get lint/type compliance only.
- **No removal of load-bearing quirks**: namespace package (no top-level `__init__.py`),
  `config.toml` at wheel root, deliberate import cycles, `E711` soft-delete filters.

## 5. Users

- **Library consumers** — external developers on PyPI and the sibling `python-profit`
  repo. They see: types in their editor, honest signatures, docs that teach.
- **Maintainer** — one person on a fork; wants gates that catch regressions without
  ceremony (pre-commit mirrors CI).
- **Contributors** — the mkdocs site and enriched module docs are the onboarding surface.

## 6. Constraints and load-bearing quirks (do not break)

| Quirk | Rule |
|---|---|
| `E711` (`== None`) | **Never** rewritten — SQLAlchemy `IS NULL` semantics. Filter sites stay byte-identical. |
| `I001` import order | Stays ignored; import graph stays as-is at runtime. |
| `PLC0415` function-level imports | Stays; cycles broken at runtime, never by reshuffling. |
| Namespace package | `python_accounting/__init__.py` remains absent (`check_wheel_layout.py` asserts this). |
| `config.toml` | Stays at wheel root via hatchling `force-include`. |
| Hash chain | Ledger row shape and hashing algorithm untouched (`smoke_install.py` verifies). |
| `fixed_today` fixture | Freezes only `utils.dates` and `mixins.assigning`; any new clock-touching code must extend that list or take dates explicitly. |
| Money | `Decimal` only; no `float` in amount paths. |
| Suppressions | One-line, rule-specific, with an inline reason. Blanket ignores are forbidden. |
| Packaging guards | `scripts/check_wheel_layout.py` and `scripts/smoke_install.py` keep their strictness (the latter must keep refusing source checkouts). |

## 7. Deliverables

1. Fully annotated library + `python_accounting/py.typed`; `TYPE_CHECKING` import
   structure that retires the `F821` per-file ignores.
2. `[tool.mypy]` config (in `pyproject.toml`) + `pyrightconfig.json` at repo root
   (amended 2026-10-16 after probe: stale pyrights cannot parse PEP 735
   `dependency-groups`; the JSON config is version-proof — see DECISIONS D-002),
   checkers pinned in the `lint` dependency group; zero-error gates wired into
   pre-commit and CI.
3. Expanded ruff ruleset (`ANN`, `TC`, `RUF`, `PERF`) with all existing ignores preserved
   and documented.
4. Defect fixes, each its own commit, each with a test where behavior is touched:
   `Ledger.get_hash` signature/docstring; `Transaction.contribution()` rewritten
   explicitly with a behavior-preservation test; `Category` module docstring; three
   wrong file headers; dead `database_init()` + module-level `engine` removed.
5. `AccountingException` class with `AccountingExeption` alias (old name keeps working;
   CHANGELOG deprecation note).
6. MkDocs site: `mkdocs.yml`, restructured content (Home, Getting Started, Learn,
   Guides, API Reference via mkdocstrings, Explanation/internals), Material theme tuned;
   Sphinx artifacts removed (`docs/conf.py`, `docs/requirements.txt`, `docs/Makefile`,
   dead `index.rst`, stale `docs/_build/`); `.readthedocs.yaml` migrated to MkDocs.
7. `scripts/check_wheel_layout.py` extended to assert `py.typed` ships.
8. `docs/SPEC.md`, `docs/DECISIONS.md`, `docs/PLAN.md` — dev docs excluded from the
   built site.
9. Version 2.0.0, classifiers and `requires-python` updated, CHANGELOG entry; README
   refreshed with docs links.
10. `__tablename__` de-magicization (amended 2026-10-16 after probe): the
    `declared_attr.directive` on `Base` is removed; the 11 classes that relied on
    auto-naming get explicit `__tablename__` strings; the 10 `__tablename__ = None`
    markers in `transactions/` are deleted (STI children need no marker). Table names
    are byte-identical — guarded by a schema snapshot test (see DECISIONS D-005).

## 8. Acceptance criteria (definition of done)

Every line below must show passing output in the final report:

| # | Command / check | Expected |
|---|---|---|
| A1 | `uv run ruff format --check .` | clean |
| A2 | `uv run ruff check .` | `All checks passed` — with `ANN`/`TC`/`RUF`/`PERF` enabled, `F821` ignores deleted |
| A3 | `uv run mypy python_accounting` (strict) | zero errors |
| A4 | `uv run mypy tests` (non-strict) | zero errors |
| A5 | `uv run pyright` (standard; package + tests + scripts) | zero errors |
| A6 | `uv run pytest` | ≥115 passed, no skips added |
| A7 | `uv run mkdocs build --strict` | exit 0, zero warnings |
| A8 | `uv run python scripts/check_wheel_layout.py` | passes; asserts `py.typed` in wheel, `config.toml` at root, no top-level `__init__.py` |
| A9 | `uv run pre-commit run --all-files` | all hooks pass |
| A10 | Semantics: ledger hash chain verifies, soft-delete filter sites untouched, import order unchanged, table names + column nullability unchanged | byte-level diff review + schema snapshot test + `smoke_install.py` green in Docker |
| A11 | Suppressions: every `# type: ignore` / pyright ignore has inline justification; none in the public API surface | reported in final summary |

## 9. Risks

| Risk | Mitigation |
|---|---|
| mypy strict × SQLAlchemy dynamics (mixins, `declared_attr`, session overrides) | Architect-designed patterns first; suppressions only at named seams; tests as the behavior gate. |
| `TYPE_CHECKING` imports change runtime import order | Runtime graph reviewed as unchanged; full test suite + wheel smoke after the structural commit. |
| Scope creep through "any other warts we find" | Every additional breaking change is reported at a checkpoint before it lands. |
| mkdocstrings/griffe on a namespace package | Skeleton site proves the pattern before any content is written. |
| Pre-commit gets painfully slow | New hooks kept purpose-scoped; docs build stays in CI. |
| Hidden consumers of removed dead code | Removal listed in CHANGELOG with rationale (2.0.0 justifies it). |

## 10. Out of scope / follow-ups

- Zensical 0.1.0 migration (Nov 5, 2026) once the release line settles.
- Python 3.14 support (pytest 8 upgrade) and the `,<3.14` cap.
- Trusted publishing for `publish.yml` (drops `PYPI_API_TOKEN`).
- Doc-snippet execution in CI.
- Renaming remaining `Recyclable`/`Recycled`-era naming warts beyond documented scope.
