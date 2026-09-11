# Local infrastructure and production gates

Red Five follows the production template's `python-data-quant` archetype:
Python 3.12, src-layout package, frozen uv lock, Polars, Ruff, strict Pyright,
pytest/coverage, wheel/sdist, pinned GitHub Actions, dependency/license checks,
secret scanning and release-readiness checklist. See `Makefile` and
`.github/workflows/`; a configured workflow is not evidence it passed remotely.

## Local research environment

- `make setup` installs the locked development environment.
- `make check` validates formatting, typing and deterministic tests.
- `make notebook` installs the locked optional notebook group and starts JupyterLab
  on loopback with its normal token authentication. Do not disable authentication,
  bind to a public interface or commit the token URL. Stop it with Ctrl-C.
- `make notebook-check` executes the synthetic notebook into ignored `build/`.
- `make audit build` checks runtime dependencies/licenses and builds packages.
  CI separately audits the notebook dependency group after its execution check.

No credentials are needed for synthetic examples. Keep licensed/private inputs
outside Git and report bundles in ignored `build/`; tracked notebooks have no
saved outputs. The repository is public: notebook/report publication is a separate
data-release decision. `verify-bundle` checks integrity, not publisher identity.

## Before any scheduled or shared deployment

Choose hosting, workload/data size, licensed inputs, retention, access roles and an
operational owner first. Then add a non-root digest-pinned container, selected
infrastructure-as-code, secret management, migrations, Postgres snapshot/recovery
tests, isolated batch workers, bounded retries/timeouts, artifact storage,
freshness alerts, backup/restore targets and exercised rollback. The project plan
defines those dependencies; a speculative Docker or cloud scaffold does not close
them. Branch protection, required reviewers and signing need owner-selected policy
before protected releases; this change does not alter GitHub account settings.
