# GLOSSARY

Vocabulary for designing and talking about this codebase. The design terms come from the
codebase-design discipline (deep modules); the project terms name load-bearing mechanics
that only make sense once you've been bitten by them.

## Design terms

**Module** — anything with an interface and an implementation: a function, class, or
package. Not "component", not "service".

**Interface** — everything a caller must know to use a module correctly: type signature,
invariants, ordering constraints, error modes. Not just the method list.

**Implementation** — what's inside a module. Distinct from an **adapter** (a concrete
thing satisfying an interface at a seam).

**Depth** — leverage at the interface: how much behaviour a caller exercises per unit of
interface they learn. Deep = small interface, lots of behaviour behind it. Shallow =
interface nearly as complex as the implementation.

**Seam** — the place where a module's interface lives; where you can alter behaviour
without editing there. Not "boundary".

**Leverage** — what callers get from depth: one implementation pays back across N call
sites and M tests.

**Locality** — what maintainers get from depth: change, bugs, and verification
concentrate in one place.

**Deletion test** — imagine deleting a module. If complexity vanishes, it was a
pass-through; if it reappears across N callers, it was earning its keep.

## Project terms

**Stamped attribute** — a value a library method computes and *writes onto* an ORM object
instead of returning it (e.g. `transaction.age`, `account.closing`). The pre-2.0 contract
between `Account.statement()`/`section_balances()` and their consumers. Being retired in
favour of result types (D-016); the legacy `statement()` shim restamps transaction-level
stamps for compatibility.

**Result type** — a named, typed shape returned by a computation instead of a
string-keyed dict or stamped attributes. Two vehicles: `TypedDict` when dict keys stay
byte-identical (tests keep asserting `result["opening"]`), `@dataclass(frozen=True)` for
genuinely new shapes (`ScheduleRow`, `StatementRow`).

**Schedule / statement halves** — the two disjoint behaviours that used to live in one
157-line `Account.statement(schedule=...)` method: the aging/outstanding half (now
`schedule_outstanding()`, RECEIVABLE/PAYABLE only, mixes `Transaction | Balance` rows) and
the running-balance half (now `statement_running()`).

**Section balances** — the per-section aggregation behind Income Statement / Balance
Sheet / Cashflow (`opening`/`movement`/`closing` + `categories` breakdown). Moved to the
reports layer next to `FinancialStatement` (D-016); `Account.section_balances` remains as
a delegating alias.

**Legacy alias / shim** — a thin delegating method kept so existing callers and tests
keep working after a deepening. One implementation, two entry points; the shim restamps
compatibility attributes before returning the legacy shape.

**Deep seam (the session)** — the `AccountingSession` threading through ~28 library
methods: entity isolation, soft delete, period rollover all ride on it. The one seam the
library already gets right; never replace it with anything narrower.

**Load-bearing quirk** — behaviour that looks like a defect but is load-bearing:
`== None` soft-delete filters (SQLAlchemy `IS NULL` semantics), import order in
`models/__init__.py`, the hash chain's per-row commits, `config.toml` at wheel root.
Documented in AGENTS.md; never "fix" in passing.
