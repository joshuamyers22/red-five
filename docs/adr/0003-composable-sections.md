# ADR 0003 — Independent evidence sections and presentation panels

Status: accepted for the local notebook workflow, 2026-09-11.

Add a versioned immutable section artifact rather than synthesizing a fake full
report with uncomputed values. Independent evaluation and extraction share the
existing numerical functions and table shape; tests establish value parity while
allowing lineage identities to differ. Coverage explicitly skips correlations.
Economics requires alignment evidence but does not invoke standalone diagnostics.

Separate `SectionResult`, `Selection`, `Panel`, and `PlotOptions`. Changing a
selection reorders/subsets existing display rows, not the numerical sample.
Exact Polars tables remain available; HTML precision is presentation-only.
Matplotlib rendering accepts a structural plot-source protocol, so old full
reports and new panels use the same artist implementation. Caller-owned axes
retain their figure and unrelated content; compatible overlays are explicit.

New partial manifests record selected sections and display specifications. Reuse
the original bounded, non-overwriting publication adapter; add partial inventory
and CSV/source reconciliation checks. Do not reinterpret a completed partial
bundle as full-report acceptance. Invalid computations raise typed errors instead
of emitting successful section evidence. No failed-section history store is added.

No new dependency, service, widget framework or cloud resource is needed. CI
executes both notebooks and the section API from an installed wheel. Optional
widgets, custom artist/layout capture, durable failure history and production
worker isolation remain future decisions. The public repository retains synthetic
examples only; local notebook state is not production release evidence.
