# Reporting slice verification

Objective: display the existing verified descriptive evidence in Jupyter and an
offline export without changing metrics, grouping, status or source artifacts.

Blocking failures: wrong plotted/table values, future/missing values represented as
zero, unsafe metadata, mutable source evidence, overwritten bundles, or notebook
cells implementing a second numerical pipeline. Verify with hand-value parity,
adversarial inputs, error injection, strict typing/lint, full tests, installed-wheel
CLI and actual kernel execution. Limit iteration to three evidence-changing passes
and two hours; no live data, remote deployment or production approval.

## Executed evidence — 2026-09-11

- `make check`: lint/format passed, strict Pyright zero errors, 105 tests passed,
  92.51% package coverage (85% required).
- `make notebook-check`: all cells executed in a real Python 3.12.11 Jupyter
  kernel; inline HTML, Polars tables, individual figures and bundle verification
  succeeded. Executed outputs remain in ignored `build/`; source notebook is clear.
- `make audit build`: dependency/license checks and wheel/sdist build passed.
  Audit found no known vulnerabilities/adverse statuses in 111 non-dev packages.
  Dedicated `uv audit --preview-features audit-command --locked --only-group notebook`
  also passed for 93 packages. Installed notebook-environment license check passed.
- Installed the built wheel in a separate environment with hash-checked locked
  runtime dependencies. Ran `eval`, `render` and `verify-bundle` outside the source
  checkout without Jupyter installed; all passed.
- `cmp` confirmed notebook and installed-wheel source reports and rendered HTML
  were byte-identical for the final synthetic run.
- Visually inspected the synthetic correlation PNG: separate instrument/contract
  groups, readable legend, fixed correlation scale and source/status caption.
- Adversarial tests cover exact chart/table values, nulls/no weights, pagination,
  malformed evidence, injection text, CSV escaping, immutable views, tampered
  bundles, unsafe paths/symlinks, output limits, idempotence, deterministic images
  and injected publication failure preserving unrelated files.

The final synthetic run identity is
`189031e7ab484b01604f8c788330145bf39c75e7f356d096ec87d18e748f7948`.

Early checks caught incorrect Polars column access in a test, notebook formatting,
and incomplete third-party artist stubs. Fixed test/notebook code and confined the
documented stub exception to the rendering adapter (ADR 0002). The dedicated audit
uses `--only-group`, not the unsupported `--group` option. Sandbox kernel startup
required explicit permission for local loopback ports; execution then passed.

## Remaining limits

No remote CI result is claimed for this change. Full narrow/print accessibility,
representative maximum-panel performance, hard process time/memory enforcement,
concurrent rendering, production crash recovery and independent financial approval
remain open. The local kernel warned that its loopback TCP transport is unencrypted;
do not expose it beyond the trusted local machine. Later shared-kernel deployment
requires an explicit transport/access-security decision. No live service, database,
cloud resource or public report endpoint was started.
