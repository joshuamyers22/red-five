"""Application use case coordinating validated snapshots and pure calculations."""

from __future__ import annotations

from .contracts import ContractError, EvaluationConfig
from .economics import account_weights
from .reporting import SCHEMA, canonical
from .signal_io import digest, json_object, parse_predictions, parse_weights
from .standalone import evaluate_groups


def evaluate(
    signal_bytes: bytes,
    config_bytes: bytes,
    plan_bytes: bytes,
    lock_bytes: bytes,
    *,
    code_identity: dict[str, str],
    software: dict[str, str],
    weight_bytes: bytes | None = None,
) -> dict[str, object]:
    declaration = json_object(config_bytes)
    config = EvaluationConfig.parse(declaration)
    predictions = parse_predictions(signal_bytes, config)
    weights = () if weight_bytes is None else parse_weights(weight_bytes, config)
    periods = {
        (r.instrument_id, r.contract_id, r.decision_time, r.label_start, r.label_end)
        for r in predictions
    }
    if any(
        (r.instrument_id, r.contract_id, r.decision_time, r.label_start, r.label_end)
        not in periods
        for r in weights
    ):
        raise ContractError(
            "supplied weight interval is not represented in the signal panel"
        )
    identity: dict[str, object] = {
        "signals_sha256": digest(signal_bytes),
        "weights_sha256": None if weight_bytes is None else digest(weight_bytes),
        "config_sha256": digest(config_bytes),
        "config": declaration,
        "analysis_plan_sha256": digest(plan_bytes),
        "lock_sha256": digest(lock_bytes),
        "code": code_identity,
        "software": software,
    }
    return {
        "schema_version": SCHEMA,
        "run_id": digest(canonical(identity)),
        "identity": identity,
        "status": "insufficient-evidence",
        "verdict": None,
        "reason_codes": ["decision-policy-not-configured", "descriptive-analysis-only"],
        "data_status": "valid",
        "mode": config.mode,
        "group_fields": (
            ["model_id", "instrument_id", "contract_id"]
            if config.mode == "time_series"
            else ["model_id", "decision_time"]
        ),
        "standalone": evaluate_groups(predictions, config),
        "economics": account_weights(weights),
        "limitations": [
            "Timestamp checks do not authenticate upstream availability or prove OOS.",
            "No residualizer, allocation fitting, significance or acceptance policy.",
            "Economics is supplied-interval accounting, not fills or capacity.",
            "Quantiles, breadth, marginal inference and live registry are deferred.",
        ],
    }
