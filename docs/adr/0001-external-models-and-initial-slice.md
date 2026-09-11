# ADR 0001 — Evaluate supplied models and portfolios

Date: 2026-09-11. Status: accepted scope from owner; initial implementation choice.

Use `red-five` as project/CLI name and `red_five` as Python import name. Build from
the local production template's `python-data-quant` archetype. The owner's explicit
scope keeps return residualization and portfolio weighting upstream and includes
one time-series evaluation model per instrument/contract.

Start with strict local CSV/config boundaries, pure descriptive calculations,
conditional supplied-weight accounting, and immutable JSON evidence. The local
adapter provides a walking skeleton without making Postgres or Airflow a dependency
of domain calculations. The full plan still schedules those adapters later.

Do not invent significance/acceptance policy while domain choices are unresolved.
Missing optional weights do not prevent signal diagnostics, but cannot produce
portfolio economics. Inherited standalone regression utilities are scaffolding
tools, not an internal replacement for the owner's upstream workflow.

Consequences: no production verdict, inference, portfolio construction, model
fitting, fill simulation, or capacity claim in v0.1.0. Follow-on features must
respect the same external-output and instrument/contract boundaries.
