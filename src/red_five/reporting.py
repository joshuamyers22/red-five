"""Deterministic evidence identity and non-overwriting local publication."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from importlib.metadata import version
from pathlib import Path

from .contracts import ContractError
from .signal_io import MAX_BYTES, digest, json_object, read_bytes

SCHEMA = "red-five-signal-report/v1"


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def source_identity() -> dict[str, str]:
    root = Path(__file__).parent
    files = {p.name: digest(p.read_bytes()) for p in sorted(root.glob("*.py"))}
    return {
        "package_version": version("red-five"),
        "source_sha256": digest(canonical(files)),
    }


def software_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        **{name: version(name) for name in ("numpy", "polars", "statsmodels")},
    }


def seal_report(report: dict[str, object]) -> bytes:
    return canonical({**report, "report_sha256": digest(canonical(report))})


def verify_report(content: bytes) -> dict[str, object]:
    report = json_object(content)
    expected = report.pop("report_sha256", None)
    if report.get("schema_version") != SCHEMA or expected != digest(canonical(report)):
        raise ContractError("report schema or content digest mismatch")
    if report.get("run_id") != digest(canonical(report.get("identity"))):
        raise ContractError("report run identity mismatch")
    return report


def publish(path: Path, content: bytes) -> None:
    """Publish a complete file atomically; identical reruns are idempotent."""
    if len(content) > MAX_BYTES:
        raise ContractError("report exceeds 16 MiB output limit")
    verify_report(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ContractError("output may not be a symlink")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
            temporary = Path(staged.name)
            staged.write(content)
            staged.flush()
            os.fsync(staged.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or read_bytes(path) != content:
                raise ContractError(
                    "output already exists with different evidence"
                ) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
