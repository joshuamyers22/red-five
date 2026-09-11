"""Thin command-line delivery adapter."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .contracts import ContractError
from .evaluation import evaluate
from .reporting import (
    publish,
    seal_report,
    software_versions,
    source_identity,
    verify_report,
)
from .signal_io import read_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="red-five")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "eval", help="evaluate supplied signals and optional weights"
    )
    run.add_argument("input", type=Path)
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--analysis-plan", required=True, type=Path)
    run.add_argument("--lock", type=Path, default=Path("uv.lock"))
    run.add_argument("--weights", type=Path)
    run.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser(
        "verify", help="verify report content and identity hashes"
    )
    verify.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    code = source_identity()
    try:
        if args.command == "verify":
            report = verify_report(read_bytes(args.input))
        else:
            report = evaluate(
                read_bytes(args.input),
                read_bytes(args.config),
                read_bytes(args.analysis_plan),
                read_bytes(args.lock),
                code_identity=code,
                software=software_versions(),
                weight_bytes=None if args.weights is None else read_bytes(args.weights),
            )
            publish(args.output, seal_report(report))
        print(
            json.dumps(
                {
                    "run_id": report["run_id"],
                    "status": report["status"],
                    "output": None if args.command == "verify" else str(args.output),
                }
            )
        )
    except (ContractError, OSError) as error:
        event: dict[str, object] = {
            "schema_version": 1,
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": "ERROR",
            "event": "evaluation_failed",
            "service": "red-five",
            "environment": "local",
            "release": code["package_version"],
            "revision": code["source_sha256"],
            "operation": args.command,
            "outcome": "error",
            "error_code": "INPUT_INVALID"
            if isinstance(error, ContractError)
            else "IO_FAILED",
            "error_type": type(error).__name__,
            "retryable": False,
            "message": str(error)
            if isinstance(error, ContractError)
            else "local file operation failed",
        }
        print(json.dumps(event), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
