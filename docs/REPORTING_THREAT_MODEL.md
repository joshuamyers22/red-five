# Reporting threat boundaries

Assets: proprietary model identities, immutable evidence, developer machine and
kernel, and public repository contents.

- Treat JSON/metadata as untrusted: verify digests, validate supported types/ranges
  and bound rows/text/bytes. Hashes do not authenticate publishers or market data.
- Escape HTML/SVG, disable TeX/math interpretation of labels, and escape dangerous
  CSV text. Never embed executable input or fetch remote assets. Tables, figures
  and status derive from the same evidence.
- Require trusted output parents and completion manifests. Reject symlinks, unsafe
  filenames, unlisted files and conflicting output. Hostile concurrent writers and
  forged hashes are outside the local adapter's protection.
- Jupyter executes Python by design: trust notebooks, retain token authentication,
  bind to loopback, and stop kernels after use. Never publish tokens or private
  executed notebooks/report bundles.
- Rendering is bounded and serial. Production workers need process-level resource
  limits and isolated storage. Process death may leave incomplete output; never
  consume a bundle without a verified completion manifest.
- Frozen dependencies, audits, pinned CI actions and installed-wheel smoke tests
  reduce supply-chain risk; scans are point-in-time evidence, not guarantees.

Test evidence: `tests/test_visualization.py`. Shared-deployment recovery/access
controls remain open in `INFRASTRUCTURE.md` and the project plan.
