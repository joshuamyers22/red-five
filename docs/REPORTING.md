# Graphical and notebook reporting — v1

`load_report(path)` verifies report and run-identity hashes, validates supported
descriptive fields and returns an immutable `ReportView`. `display(view)` in
Jupyter displays its offline HTML representation; `view.html()` returns that
fragment explicitly. No network, fitted model, trading weights or new metric is
needed. Only current `insufficient-evidence` reports with no verdict are supported.

## Views

| API | Content |
|---|---|
| `view.table("summary")` | Run, cutoff, mode, target, horizon, calendar, status, reasons and limitations |
| `view.table("signals")` | Separate group identities, correlations, counts and unavailable reasons |
| `view.table("economics")` | Supplied intervals, exact decimal returns/costs/turnover and constituent counts |
| `view.figure("correlations")` | Per-group Pearson/Spearman dots on a fixed [-1, 1] scale |
| `view.figure("coverage")` | Eligible, immature and missing-mature counts |
| `view.figure("returns")` | Supplied gross/net interval returns, not a NAV path |
| `view.figure("costs")` | Trading/holding costs in fractions of pre-trade NAV |

Tables are new Polars frames; changes to them do not change the report. Accounting
amounts remain strings to preserve exact Decimal values. Figures convert those
amounts to float for display only, retain grouping/order, and never fill absent
metrics with zero. Each figure includes source identity/status and has a full-value
HTML/CSV table. Individual returned figures can be styled interactively, but those
edits do not modify evidence or the standard export theme.

Use `page=1`, etc. for subsequent 20-group pages. HTML/export includes all pages.
This first adapter rejects more than 200 signal groups or 200 economic intervals,
text longer than 1024 characters, and accounting amounts beyond ±1e30. Those are
display bounds, not approved risk limits. Source input is capped at 16 MiB and the
bundle at 32 MiB. A cooperative 60-second budget is checked between render units;
it is not a hard process timeout. Large production panels need a later measured
streaming/pagination contract. Matplotlib rendering is serial within a process.

## Export and verification

`view.export(path)` and `red-five render report.json --output-dir path` produce
`index.html`, the exact source `report.json`, three CSV tables, SVG/PNG figures and
`manifest.json`. The manifest records file hashes, source identity, renderer/source
version, Matplotlib version, pagination and CSV conventions. Identical output is
idempotent within the same pinned environment; differing output is never replaced.
Use a fresh path after renderer/source upgrades. PNG/SVG byte equality across
different platforms is not promised.

CSV uses UTF-8, explicit headers and `\N` for null. Untrusted strings starting with
spreadsheet operators, apostrophes/backslashes, or containing tabs/newlines receive
a leading apostrophe; strip exactly one such prefix to recover original text.
Numeric metrics are not rounded. Decimal text values, including negative amounts,
follow the text escape rule. Import identifier and amount columns as text;
spreadsheets otherwise may reinterpret dates, leading zeros or precision. Canonical
JSON always retains unmodified values. HTML/SVG metadata is escaped and TeX/math
interpretation is disabled for untrusted labels.

`red-five verify-bundle path` checks schema, bounded file inventory, safe names,
symlinks, hashes and the bound source report. Consumers require a valid manifest,
written last. Failed publication cleans up its own directory; a killed process can
leave an incomplete directory requiring operator review. No fsync-level recovery
or hostile filesystem concurrency claim is made. Hashes detect change, not
authorship or financial correctness.

Keep real bundles and executed notebooks out of this public repository. Default
examples use ignored `build/`. No export uploads or publishes data. No quantiles,
breadth, inference, paired marginal utility, NAV or drawdown are fabricated when
their evidence is absent. See [ADR 0002](adr/0002-notebook-reporting.md).
