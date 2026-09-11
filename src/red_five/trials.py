"""Transactional local trial journal; no completeness or remote immutability claim."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .contracts import ContractError, identifier
from .quantiles import QuantileConfig
from .reporting import canonical, software_versions, source_identity
from .sections import SectionResult
from .signal_io import MAX_BYTES, digest, json_object
from .temporal import FoldSection, FoldSpec, evaluate_fold_section
from .visualization import Cell, Table, mapping, text_cell

MAX_EVENTS = 1000
SCHEMA = "red-five-trial-event/v1"


def _read(connection: sqlite3.Connection) -> list[dict[str, object]]:
    if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
        raise ContractError("unsupported trial journal schema")
    count, size = connection.execute(
        "SELECT count(*), coalesce(sum(length(content)), 0) FROM events"
    ).fetchone()
    if count > MAX_EVENTS or size > MAX_BYTES:
        raise ContractError("trial journal exceeds event/byte capacity")
    records = connection.execute(
        "SELECT sequence, content, event_sha256 FROM events ORDER BY sequence LIMIT ?",
        (MAX_EVENTS + 1,),
    ).fetchall()
    if len(records) > MAX_EVENTS:
        raise ContractError("trial journal exceeds 1000 events")
    result: list[dict[str, object]] = []
    previous: str | None = None
    states: dict[str, str] = {}
    requests: dict[str, dict[str, object]] = {}
    total = 0
    for index, (number, content, stored) in enumerate(records, start=1):
        if not isinstance(content, bytes):
            raise ContractError("invalid journal event storage")
        total += len(content)
        if total > MAX_BYTES:
            raise ContractError("trial journal exceeds 16 MiB")
        event = json_object(content)
        if (
            number != index
            or stored != digest(content)
            or event.get("previous") != previous
            or event.get("schema_version") != SCHEMA
        ):
            raise ContractError("trial journal chain mismatch")
        trial_id = identifier(event.get("trial_id"), "trial_id")
        kind = event.get("kind")
        if kind == "registered":
            if trial_id in states:
                raise ContractError("duplicate trial registration")
            requests[trial_id] = mapping(event.get("payload"))
        elif kind in ("computed", "unavailable", "failed"):
            if states.get(trial_id) != "registered":
                raise ContractError("invalid trial state transition")
            payload = mapping(event.get("payload"))
            if kind != "failed":
                section = SectionResult(canonical(mapping(payload.get("section"))))
                if section.status != kind:
                    raise ContractError("trial outcome does not match section")
                request = requests[trial_id]
                identity = mapping(json_object(section.content)["identity"])
                if (
                    section.name != request["section_name"]
                    or any(
                        identity.get(key) != request.get(key)
                        for key in (
                            "signals_sha256",
                            "config_sha256",
                            "analysis_plan_sha256",
                            "lock_sha256",
                            "fold",
                            "code",
                            "software",
                        )
                    )
                    or (
                        section.name == "quantiles"
                        and section.diagnostics.get("policy") != request["quantiles"]
                    )
                ):
                    raise ContractError(
                        "trial result does not match registered request"
                    )
        else:
            raise ContractError("invalid trial event kind")
        states[trial_id] = text_cell(kind)
        result.append({**event, "event_sha256": stored})
        previous = stored
    return result


@dataclass(frozen=True)
class TrialLedger:
    path: Path

    def _check_path(self) -> None:
        if self.path.is_symlink() or any(p.is_symlink() for p in self.path.parents):
            raise ContractError("trial journal paths may not contain symlinks")

    def events(self) -> tuple[dict[str, object], ...]:
        """Fresh verified snapshot; registered-only trials are visibly unfinished."""
        self._check_path()
        if not self.path.exists():
            return ()
        with closing(
            sqlite3.connect(self.path.absolute().as_uri() + "?mode=ro", uri=True)
        ) as conn:
            conn.execute("BEGIN")
            return tuple(_read(conn))

    def _append(self, trial_id: str, kind: str, payload: dict[str, object]) -> None:
        self._check_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=5)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if not tables:
                conn.execute(
                    "CREATE TABLE events (sequence INTEGER PRIMARY KEY, "
                    "content BLOB NOT NULL, event_sha256 TEXT NOT NULL)"
                )
                conn.execute("PRAGMA user_version=1")
            events = _read(conn)
            prior = [e for e in events if e["trial_id"] == trial_id]
            if kind == "registered" and prior:
                raise ContractError(
                    "trial_id already registered; use a new ID for a new attempt"
                )
            if kind != "registered" and (
                not prior or prior[-1]["kind"] != "registered"
            ):
                raise ContractError("trial must be registered and unfinished")
            if len(events) >= MAX_EVENTS - (1 if kind == "registered" else 0):
                raise ContractError("trial journal event capacity reached")
            event = {
                "schema_version": SCHEMA,
                "trial_id": trial_id,
                "kind": kind,
                "recorded_at": datetime.now(UTC).isoformat(),
                "previous": events[-1]["event_sha256"] if events else None,
                "payload": payload,
            }
            content = canonical(event)
            if len(content) > MAX_BYTES:
                raise ContractError("trial event exceeds 16 MiB")
            conn.execute(
                "INSERT INTO events VALUES (?, ?, ?)",
                (len(events) + 1, content, digest(content)),
            )
            _read(conn)  # Validate the prospective whole chain before commit.
            conn.commit()

    def table(self) -> Table:
        latest: dict[str, dict[str, object]] = {}
        declarations: dict[str, dict[str, object]] = {}
        for event in self.events():
            trial_id = text_cell(event["trial_id"])
            latest[trial_id] = event
            if event["kind"] == "registered":
                declarations[trial_id] = mapping(event["payload"])
        rows: list[tuple[Cell, ...]] = []
        for trial_id, event in latest.items():
            request = declarations[trial_id]
            payload = mapping(event["payload"])
            section = mapping(payload["section"]) if "section" in payload else {}
            rows.append(
                (
                    trial_id,
                    text_cell(request["family_id"]),
                    text_cell(request["section_name"]),
                    text_cell(mapping(request["fold"])["fold_id"]),
                    text_cell(event["kind"]),
                    text_cell(event["recorded_at"]),
                    text_cell(section["section_id"]) if section else None,
                    "unknown",
                    "unverified",
                )
            )
        return Table(
            (
                "trial_id",
                "family_id",
                "section",
                "fold_id",
                "status",
                "recorded_at",
                "section_id",
                "historical_search_completeness",
                "upstream_out_of_sample",
            ),
            tuple(rows),
        )

    def run(
        self,
        trial_id: str,
        family_id: str,
        name: FoldSection,
        signal_bytes: bytes,
        config_bytes: bytes,
        plan_bytes: bytes,
        lock_bytes: bytes,
        *,
        fold: FoldSpec,
        quantiles: QuantileConfig | None = None,
    ) -> SectionResult:
        """Register before computation; completed, unavailable and failed are retained.

        Crashes/interruptions may leave a registered-only trial; never retry under
        that ID. A failed completion write raises instead of returning evidence.
        """
        identifier(trial_id, "trial_id")
        identifier(family_id, "family_id")
        self._append(
            trial_id,
            "registered",
            {
                "family_id": family_id,
                "section_name": name,
                "fold": asdict(fold),
                "quantiles": None if quantiles is None else asdict(quantiles),
                "signals_sha256": digest(signal_bytes),
                "config_sha256": digest(config_bytes),
                "analysis_plan_sha256": digest(plan_bytes),
                "lock_sha256": digest(lock_bytes),
                "code": source_identity(),
                "software": software_versions(),
                "historical_search_completeness": "unknown",
                "upstream_out_of_sample": "unverified",
            },
        )
        try:
            result = evaluate_fold_section(
                name,
                signal_bytes,
                config_bytes,
                plan_bytes,
                lock_bytes,
                fold=fold,
                quantiles=quantiles,
            )
        except Exception as error:
            # Do not persist exception text: it may include private inputs or paths.
            self._append(trial_id, "failed", {"error_type": type(error).__name__})
            raise
        self._append(trial_id, result.status, {"section": json_object(result.content)})
        return result
