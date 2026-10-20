# Reporting periods

Accounting doesn't happen in a continuous stream — it happens in **years**.
A fiscal year has an opening balance, twelve months of activity, a closing,
and then the next year starts with the previous year's closing as its
opening. Every financial report is *for a period*; "the balance" without a
date is meaningless.

python-accounting models this with **ReportingPeriod**, and — like
reporting periods themselves — it mostly takes care of itself.

## The open period

When an Entity is created, the library automatically opens its first
reporting period for the current calendar year. Transactions posted through
the session belong to the entity's open period, determined by their
transaction date.

## Rolling forward

Here's the part that would otherwise be your problem: it's January 2027,
your entity's open period is 2026, and you post a transaction dated today.
The library notices — via an event listener — that the transaction's year
doesn't match the open period, and **rolls the period forward**
automatically: 2026 closes, 2027 opens, and the transaction lands where it
belongs.

You never call this. There is no "close the books" API to forget at
midnight on December 31st.

## Why dates matter anyway

The period machinery uses `datetime.today()` internally, which has one
practical consequence for library *consumers*: if your application fakes
dates (fixtures, backdating, replaying history), pass explicit dates to
transactions and reports rather than relying on "today". The period
roll-forward follows the transaction dates you give it.

!!! tip "Year-independent tests"

    If you're writing tests against this library, don't hardcode years.
    Tests that pin `datetime.today()` to a fixed date (see the library's own
    `fixed_today` fixture) stay green across year boundaries; hardcoded
    years don't.

## What periods give the reports

Every report in the suite takes its default window from the entity's open
period. That's why `IncomeStatement(session)` needs no arguments: "the
income statement" *means* the open period's income statement. Explicit
start/end dates are accepted when you need a different window, but the
period is the anchor everything else hangs off.
