# ADR 0002 — Shared notebook and offline reporting adapter

Status: accepted for the local descriptive slice (2026-09-11).

Use Matplotlib's non-pyplot Figure/Agg API for display and SVG/PNG export, Polars
for notebook tables, and escaped self-contained HTML. JupyterLab/ipykernel are a
separate locked dependency group. Evaluation does not import Jupyter or plotting
code and does not require a running kernel, browser or database. No pandas bridge
or new statistical calculation is introduced by this adapter.

The renderer consumes verified immutable evidence. Report views and table values
are immutable; returned frames/figures are independent presentation objects.
Changes to a displayed figure cannot change evidence or exported bundle values.
Matplotlib's public artist **kwargs are incompletely typed; a scoped
`reportUnknownMemberType` exception is confined to `rendering.py`. Domain and
notebook API boundaries retain strict typing; no global checker relaxation.

Rendering is serial: Matplotlib rc contexts temporarily change process settings
and are not a thread-safe rendering contract. No pyplot global figure registry or
backend selection is changed. Concurrent rendering in one Python process is not
supported; use isolated processes for future workers. Hash-stable SVG IDs and
metadata support deterministic reruns in the same locked environment.

Output directories are exclusively reserved, files written, and the completion
manifest written last. Consumers must verify that manifest. Failures clean up the
directory owned by this attempt; process death can leave an incomplete directory
that must not be consumed or silently overwritten. This is not database-backed
publication, fsync-level crash durability or production recovery. Outputs belong
in trusted local directories; hostile concurrent filesystem writers are outside
this adapter's threat model.

The maintained production template's Python guide and engineering defaults
justify this modular local package and locked CI/kernel workflow. Containers,
Postgres, Airflow and infrastructure-as-code remain deployment gates; no cloud
resources, external database or unauthenticated notebook endpoint are provisioned.

API references: [Matplotlib figure export](https://matplotlib.org/3.10.9/api/_as_gen/matplotlib.figure.Figure.savefig.html)
and [Jupyter installation](https://jupyter.org/install).
