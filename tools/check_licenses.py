"""Reject dependencies with prohibited or missing license metadata."""

from __future__ import annotations

import re
from email.message import Message
from importlib.metadata import Distribution, distributions
from typing import cast

DENIED = re.compile(
    r"\b(?:AGPL|GPL|SSPL)\b|GNU (?:Affero )?General Public License", re.I
)


def metadata_value(distribution: Distribution, key: str) -> str:
    """Read optional package metadata without relying on deprecated missing values."""
    value = cast(Message, distribution.metadata).get(key)
    return str(value or "").strip()


def license_evidence(metadata: Message) -> str:
    """Prefer standardized metadata over legacy bundled license notices."""
    expression = str(metadata.get("License-Expression") or "").strip()
    if expression:
        return expression
    classifiers = [
        value
        for value in metadata.get_all("Classifier", [])
        if value.startswith("License ::")
    ]
    if classifiers:
        return " ".join(classifiers)
    license_text = str(metadata.get("License") or "").strip()
    return license_text.splitlines()[0].strip() if license_text else ""


def violations() -> list[str]:
    """Return deterministic license-policy violations for installed packages."""
    findings: list[str] = []
    for distribution in distributions():
        name = metadata_value(distribution, "Name") or "unknown"
        evidence = license_evidence(cast(Message, distribution.metadata))
        if not evidence or evidence.upper() == "UNKNOWN":
            findings.append(f"{name}: missing license metadata")
        elif DENIED.search(evidence):
            findings.append(f"{name}: prohibited license: {evidence}")
    return sorted(set(findings), key=str.casefold)


def main() -> int:
    findings = violations()
    if findings:
        print("License policy violations:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Dependency license policy passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
