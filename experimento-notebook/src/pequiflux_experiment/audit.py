"""Independent integrity and acceptance audit for persisted experiment runs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import uuid
from typing import Any, Mapping

from .config import ExperimentConfig, ScenarioConfig, config_hash
from .domain import TRUCK_STAGE_SERVICE_COMPLETED, TRUCK_STAGE_SERVICE_STARTED
from .dispatch import DecisionJustification
from .experiment import LOG_REQUIRED_FIELDS, RESULT_HEADERS, RunBundle, load_run_bundle
from .events import EventRecord
from .replay import ReplayError, _replay_log, snapshot_hash


class AuditError(RuntimeError):
    """Raised when persisted evidence cannot be audited fail-closed."""


# Makespan and throughput-rate are retained as derived floating-point metrics;
# their comparison allows only the final binary representation of the
# producer's documented twelve-place rounding.  Canonical wait summaries below
# are compared exactly and do not use this tolerance.
_DERIVED_FLOAT_TOLERANCE = 1e-12

_CANONICAL_SCENARIO_METADATA_FIELDS: tuple[str, ...] = (
    "scenario_id",
    "stratum",
    "regime",
    "total_trucks",
    "hopper_count",
    "scale_count",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(_canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise
    return digest.hexdigest()


def _required_manifest_mapping(manifest: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = manifest.get(key)
    if not isinstance(value, Mapping):
        raise AuditError(f"manifest field {key!r} must be an object")
    return value


def _parse_scenario_specs(
    manifest: Mapping[str, Any], config: ExperimentConfig
) -> dict[str, Mapping[str, Any]]:
    matrix = _required_manifest_mapping(manifest, "matrix")
    unknown_matrix_keys = set(matrix) - {"scenarios", "scenario_ids", "seeds", "policies"}
    if unknown_matrix_keys:
        raise AuditError(
            "manifest matrix has unknown fields: "
            f"{', '.join(sorted(str(key) for key in unknown_matrix_keys))}"
        )
    scenarios = matrix.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise AuditError("manifest matrix.scenarios must be a non-empty list")
    scenario_ids = matrix.get("scenario_ids")
    if not isinstance(scenario_ids, list) or not scenario_ids:
        raise AuditError("manifest matrix.scenario_ids must be a non-empty list")
    result: dict[str, Mapping[str, Any]] = {}
    observed_ids: list[str] = []
    for raw in scenarios:
        if not isinstance(raw, Mapping):
            raise AuditError("manifest matrix.scenarios must contain objects")
        if set(raw) != set(_CANONICAL_SCENARIO_METADATA_FIELDS):
            raise AuditError("manifest scenario specification has invalid fields")
        scenario_id = raw.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise AuditError("manifest scenario is missing scenario_id")
        if scenario_id in result:
            raise AuditError(f"duplicate scenario_id in manifest: {scenario_id}")
        try:
            scenario = ScenarioConfig(
                truck_count=raw["total_trucks"],
                hopper_count=raw["hopper_count"],
                scale_count=raw["scale_count"],
                regime=raw["regime"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuditError(f"invalid scenario specification: {scenario_id}") from exc
        if scenario.scenario_id != scenario_id:
            raise AuditError(f"scenario specification id is inconsistent: {scenario_id}")
        stratum = raw["stratum"]
        if not isinstance(stratum, str) or stratum not in {"low", "medium", "high"}:
            raise AuditError(f"manifest scenario has invalid stratum: {scenario_id}")
        rho = scenario.truck_count / min(
            36 * scenario.hopper_count,
            72 * scenario.scale_count,
        )
        expected_stratum = "low" if rho < 0.70 else "medium" if rho < 0.85 else "high"
        if stratum != expected_stratum:
            raise AuditError(
                "manifest scenario stratum disagrees with canonical scenario metadata: "
                f"scenario_id={scenario_id} expected={expected_stratum!r} observed={stratum!r}"
            )
        observed_ids.append(scenario_id)
        result[scenario_id] = raw
    if any(not isinstance(identifier, str) or not identifier for identifier in scenario_ids):
        raise AuditError("manifest matrix.scenario_ids must contain non-empty strings")
    if scenario_ids != observed_ids or len(set(scenario_ids)) != len(scenario_ids):
        raise AuditError("manifest matrix.scenario_ids are not unique or disagree with scenarios")
    seeds = matrix.get("seeds")
    if not isinstance(seeds, list) or not seeds:
        raise AuditError("manifest matrix.seeds must be a non-empty list")
    if any(not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in seeds):
        raise AuditError("manifest matrix seeds must contain non-negative integers")
    if len(set(seeds)) != len(seeds):
        raise AuditError("manifest matrix seeds must be unique")
    if any(seed not in config.seeds for seed in seeds):
        raise AuditError("manifest matrix seeds must belong to configuration seeds")
    policies = matrix.get("policies")
    if not isinstance(policies, list) or not policies:
        raise AuditError("manifest matrix.policies must be a non-empty list")
    if any(not isinstance(policy, str) or not policy for policy in policies):
        raise AuditError("manifest matrix policies must contain non-empty strings")
    if len(set(policies)) != len(policies):
        raise AuditError("manifest matrix policies must be unique")
    from .profiles import phase_policies
    if any(policy not in phase_policies(config, manifest.get("phase")) for policy in policies):
        raise AuditError("manifest matrix policies must belong to configuration policies")
    if manifest.get("phase") in {"sensitivity", "exploratory"}:
        from .config import factorial_scenarios
        if (policies != list(phase_policies(config, manifest["phase"]))
                or seeds != list(config.seeds)
                or scenario_ids != [s.scenario_id for s in factorial_scenarios(config)]):
            raise AuditError("exploratory scientific matrix is incomplete")
    expected_rows = manifest.get("expected_rows")
    expected_product = len(scenarios) * len(seeds) * len(policies)
    if expected_rows != expected_product:
        raise AuditError(
            "manifest expected_rows does not equal matrix product: "
            f"expected={expected_product} observed={expected_rows}"
        )
    return result


def _pair_key(scenario_id: object, seed: object, policy: object) -> str:
    return f"{scenario_id}|{seed}|{policy}"


_VALID_JUSTIFICATION_STAGES = frozenset({"gate", "scale_in", "unload", "scale_out"})
_JUSTIFICATION_RULES = frozenset(
    {
        "resource_available",
        "truck_arrived",
        "document_released",
        "stage_compatibility",
        "resource_compatibility",
        "resource_blocked",
        "arrival_window",
        "excluded_candidates",
        "priority_order",
        "priority_score",
        "waiting_window",
        "affinity_score",
        "stability_order",
        "affinity_order",
        "fifo_order",
        "fifo_override",
        "slack_order",
        "cargo_batch",
    }
)

_POLICY_JUSTIFICATION_RULES: dict[str, tuple[str, ...]] = {
    "myopic_predicted_delay": ("waiting_window", "slack_order"),
    "window_without_stability": ("priority_order", "waiting_window", "affinity_order"),
    "batch_by_cargo": ("waiting_window", "cargo_batch"),
    "fifo_strict": (),
    "fifo_flow_faithful": ("waiting_window",),
    "priority_local": ("priority_order",),
    "fixed_score": ("waiting_window", "priority_score", "affinity_score"),
    "lexicographic": (
        "priority_order",
        "waiting_window",
        "stability_order",
        "affinity_order",
    ),
}


def _valid_candidate_evidence(item: Mapping[str, Any]) -> bool:
    if not {
        "truck_id", "cargo_type", "arrival_time", "stage_entry_time", "arrived",
        "eligible", "document_ok", "resource_id", "eligibility_reason", "operation",
    }.issubset(item):
        return False
    for key in ("truck_id", "cargo_type"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            return False
    for key in ("arrival_time", "stage_entry_time"):
        value = item.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            return False
        if not math.isfinite(value) or value < 0:
            return False
    for key in ("arrived", "eligible", "document_ok"):
        if not isinstance(item.get(key), bool):
            return False
    for key in ("resource_id", "eligibility_reason"):
        value = item.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            return False
    operation = item.get("operation")
    return operation is None or (
        isinstance(operation, str) and operation in _VALID_JUSTIFICATION_STAGES
    )


def _observed_exclusion(item: Mapping[str, Any], context: Mapping[str, Any]) -> str | None:
    """Reconstruct hard constraints from persisted facts, independently of dispatch."""
    if not item["arrived"]:
        return "NOT_ARRIVED"
    if item["arrival_time"] > context["now"]:
        return "FUTURE_ARRIVAL"
    if not item["eligible"]:
        return "INELIGIBLE"
    if not item["document_ok"]:
        return "DOCUMENT_BLOCKED"
    if context["operation"] is not None and item["operation"] is not None:
        if item["operation"] != context["operation"]:
            return "OPERATION_MISMATCH"
    if item["resource_id"] is not None and item["resource_id"] != context["resource_id"]:
        return "RESOURCE_MISMATCH"
    if item["cargo_type"] not in context["allowed_cargo_types"]:
        return "CARGO_INCOMPATIBLE"
    return None


def _validate_decision_observation(recommendation, event_time, truck_facts, resources, statuses, last_cargo=None) -> bool:
    """Bind FIFO/cargo evidence to preceding events, not just to itself."""
    context = recommendation["context"]
    resource_id = context["resource_id"]
    resource = resources.get(resource_id)
    if resource is None or context["now"] != event_time:
        return False
    if (context["resource_status"] != statuses[resource_id]
            or context["allowed_cargo_types"] != list(resource.allowed_cargo_types)):
        return False
    if recommendation.get("policy") == "batch_by_cargo":
        if context["affinity_target"] != (last_cargo or {}).get(resource_id):
            return False
    evidence = recommendation["candidate_order"] + [item["candidate"] for item in recommendation["excluded"]]
    for candidate in evidence:
        observed = truck_facts.get(candidate["truck_id"])
        if observed is None or any(candidate[field] != observed[field] for field in observed):
            return False
    return True


def _validate_decision_justification(
    recommendation: Mapping[str, Any],
) -> bool:
    """Validate A2's five fields and their relation to recommendation data."""

    raw_justification = recommendation.get("justification")
    try:
        justification = DecisionJustification.from_dict(raw_justification)
    except (TypeError, ValueError):
        return False

    selected = recommendation.get("selected")
    candidate_ids = recommendation.get("candidate_ids")
    excluded = recommendation.get("excluded")
    resource_id = recommendation.get("resource_id")
    policy = recommendation.get("policy")
    if not isinstance(selected, Mapping):
        return False
    if not isinstance(candidate_ids, list) or not candidate_ids:
        return False
    if not isinstance(excluded, list):
        return False
    if not isinstance(resource_id, str) or not resource_id.strip():
        return False
    if not isinstance(policy, str) or not policy.strip():
        return False
    if type(recommendation.get("schema_version")) is not int or recommendation["schema_version"] != 2:
        return False
    context = recommendation.get("context")
    if not isinstance(context, Mapping) or set(context) != {
        "now", "resource_id", "resource_available", "resource_status", "operation",
        "queue_length", "affinity_target", "allowed_cargo_types",
    }:
        return False
    if context["resource_id"] != resource_id or context["now"] != recommendation.get("now"):
        return False
    now = context["now"]
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now) or now < 0:
        return False
    if context["resource_available"] is not True or context["resource_status"] != "available":
        return False
    if type(context["queue_length"]) is not int or context["queue_length"] < 0:
        return False
    affinity_target = context["affinity_target"]
    if affinity_target is not None and (not isinstance(affinity_target, str) or not affinity_target.strip()):
        return False
    cargo_types = context["allowed_cargo_types"]
    if not isinstance(cargo_types, list) or not cargo_types:
        return False
    if any(not isinstance(value, str) or not value.strip() for value in cargo_types):
        return False
    if len(set(cargo_types)) != len(cargo_types):
        return False

    selected_id = selected.get("truck_id")
    selected_stage = selected.get("operation")
    if not isinstance(selected_id, str) or not selected_id.strip():
        return False
    if not isinstance(selected_stage, str) or selected_stage not in _VALID_JUSTIFICATION_STAGES:
        return False
    if context["operation"] is not None and context["operation"] != selected_stage:
        return False
    truck_stage = justification.truck_stage
    if (
        truck_stage.get("truck_id") != selected_id
        or truck_stage.get("stage") != selected_stage
    ):
        return False
    if justification.resource.get("resource_id") != resource_id:
        return False

    candidate_order = recommendation.get("candidate_order")
    if not isinstance(candidate_order, list) or len(candidate_order) != len(candidate_ids):
        return False
    order_ids: list[str] = []
    for item in candidate_order:
        if not isinstance(item, Mapping):
            return False
        if set(item) != {
            "truck_id",
            "arrival_time",
            "stage_entry_time",
            "cargo_type",
            "eligible",
            "eligibility_reason",
            "stable_order",
            "operation",
            "resource_id",
            "document_ok",
            "arrived",
        }:
            return False
        if not _valid_candidate_evidence(item) or _observed_exclusion(item, context) is not None:
            return False
        if item["stage_entry_time"] > now:
            return False
        item_id = item.get("truck_id")
        if not isinstance(item_id, str) or not item_id.strip():
            return False
        arrival_time = item.get("arrival_time")
        if (
            isinstance(arrival_time, bool)
            or not isinstance(arrival_time, (int, float))
            or not math.isfinite(float(arrival_time))
            or float(arrival_time) < 0
        ):
            return False
        stable_order = item.get("stable_order")
        if isinstance(stable_order, bool) or not isinstance(stable_order, int) or stable_order < 0:
            return False
        operation = item.get("operation")
        if operation is not None and (
            not isinstance(operation, str) or operation not in _VALID_JUSTIFICATION_STAGES
        ):
            return False
        candidate_resource = item.get("resource_id")
        if candidate_resource is not None and (
            not isinstance(candidate_resource, str) or not candidate_resource.strip()
        ):
            return False
        if not isinstance(item.get("document_ok"), bool) or not isinstance(item.get("arrived"), bool):
            return False
        order_ids.append(item_id)
    if order_ids != candidate_ids or len(set(order_ids)) != len(order_ids):
        return False

    excluded_ids: set[str] = set()
    for item in excluded:
        if not isinstance(item, Mapping) or set(item) != {"truck_id", "cause", "reason", "candidate"}:
            return False
        excluded_id = item.get("truck_id")
        exclusion_reason = item.get("reason")
        if (
            not isinstance(excluded_id, str)
            or not excluded_id.strip()
            or excluded_id in candidate_ids
            or excluded_id in excluded_ids
            or not isinstance(exclusion_reason, str)
            or not exclusion_reason.strip()
        ):
            return False
        evidence = item.get("candidate")
        if not isinstance(evidence, Mapping) or not _valid_candidate_evidence(evidence):
            return False
        if evidence["truck_id"] != excluded_id:
            return False
        observed_cause = _observed_exclusion(evidence, context)
        if observed_cause is None or item["cause"] != observed_cause:
            return False
        excluded_ids.add(excluded_id)

    selected_order = next(
        (item for item in candidate_order if item.get("truck_id") == selected_id),
        None,
    )
    if selected_order is None:
        return False
    for key in ("arrival_time", "stage_entry_time", "cargo_type", "eligible", "eligibility_reason",
                "stable_order", "operation", "resource_id", "document_ok", "arrived"):
        if selected.get(key) != selected_order.get(key):
            return False
    fifo_reference = min(
        candidate_order,
        key=lambda item: (
            float(item["stage_entry_time"]),
            item["truck_id"],
        ),
    )["truck_id"]
    if recommendation.get("fifo_reference_truck_id") != fifo_reference:
        return False
    expected_fifo_break = selected_id != fifo_reference
    if justification.fifo_break != expected_fifo_break:
        return False

    rules = tuple(justification.activated_rules)
    # The policy marker is parameterised by the manifest-selected policy.  It
    # is validated against the exact expected sequence below, while the static
    # vocabulary check still rejects every other invented rule.
    if any(
        rule not in _JUSTIFICATION_RULES and not rule.startswith("policy:")
        for rule in rules
    ):
        return False
    expected_rules: list[str] = [
        "resource_available",
        "truck_arrived",
        "document_released",
    ]
    if any(item.get("operation") is not None for item in candidate_order):
        expected_rules.append("stage_compatibility")
    has_resource_compatibility = context["resource_id"] is not None and bool(cargo_types)
    exclusion_causes = tuple(item["cause"] for item in excluded)
    has_resource_block = any(cause in {"RESOURCE_MISMATCH", "CARGO_INCOMPATIBLE"} for cause in exclusion_causes)
    has_arrival_window = "FUTURE_ARRIVAL" in exclusion_causes
    if has_resource_compatibility or has_resource_block:
        expected_rules.append("resource_compatibility")
    if excluded:
        expected_rules.append("excluded_candidates")
    if has_resource_block:
        expected_rules.append("resource_blocked")
    if has_arrival_window:
        expected_rules.append("arrival_window")
    expected_rules.extend(_POLICY_JUSTIFICATION_RULES.get(policy, ()))
    expected_rules.extend(
        (
            f"policy:{policy}",
            "fifo_override" if expected_fifo_break else "fifo_order",
        )
    )
    if rules != tuple(expected_rules):
        return False

    reason = justification.reason
    if not all(
        token in reason for token in (selected_id, selected_stage, resource_id, policy)
    ):
        return False
    reason_lower = reason.casefold()
    if "fifo" not in reason_lower:
        return False
    expected_phrase = "fifo order broken" if expected_fifo_break else "fifo order preserved"
    if expected_phrase not in reason_lower:
        return False
    if any(rule.startswith("priority_") for rule in rules) and "priorit" not in reason_lower:
        return False
    if "waiting_window" in rules and not any(
        token in reason_lower for token in ("waiting", "wait", "window")
    ):
        return False
    if "resource_blocked" in rules and "blocked" not in reason_lower:
        return False
    return True


def _validate_log_fields(
    line: Mapping[str, Any], event: EventRecord, line_number: int
) -> bool:
    if set(LOG_REQUIRED_FIELDS) - set(line):
        return False
    if not isinstance(line.get("resource_id"), (str, type(None))):
        return False
    if not isinstance(line.get("candidates"), list):
        return False
    if not isinstance(line.get("excluded"), list):
        return False
    if line.get("selection") is not None and not isinstance(line.get("selection"), Mapping):
        return False
    if not isinstance(line.get("explanation"), str):
        return False
    if line.get("operator_decision") is not None and not isinstance(line.get("operator_decision"), str):
        return False
    event_kind = line.get("event_kind")
    if event.kind != event_kind or line.get("kind") != event_kind:
        return False
    payload = event.to_dict()["payload"]
    if not isinstance(payload, Mapping):
        return False

    recommendation: Mapping[str, Any] | None = None
    if event_kind == "DECISION_RECORDED":
        candidate = payload.get("decision")
        if isinstance(candidate, Mapping):
            recommendation = candidate
        else:
            return False
    elif event_kind == "OPERATOR_DECISION":
        candidate = payload.get("recommendation")
        if isinstance(candidate, Mapping):
            recommendation = candidate
        else:
            return False
        if payload.get("operator_mode") != "synthetic_auto_accept":
            return False
        if payload.get("decision") != line.get("operator_decision"):
            return False
        if (
            line.get("operator_decision") != "accept"
            or payload.get("decision") != "accept"
        ):
            return False
    if recommendation is not None:
        selected = recommendation.get("selected")
        candidate_ids = recommendation.get("candidate_ids")
        excluded = recommendation.get("excluded")
        resource_id = recommendation.get("resource_id")
        policy = recommendation.get("policy")
        explanation = recommendation.get("explanation")
        if not isinstance(selected, Mapping):
            return False
        selected_truck_id = selected.get("truck_id")
        if not isinstance(selected_truck_id, str) or not selected_truck_id:
            return False
        if not isinstance(candidate_ids, list) or not candidate_ids:
            return False
        if any(not isinstance(identifier, str) or not identifier for identifier in candidate_ids):
            return False
        if len(set(candidate_ids)) != len(candidate_ids):
            return False
        if selected_truck_id not in candidate_ids:
            return False
        if not isinstance(excluded, list):
            return False
        excluded_ids: set[str] = set()
        for item in excluded:
            if not isinstance(item, Mapping):
                return False
            if set(item) != {"truck_id", "cause", "reason", "candidate"}:
                return False
            identifier = item.get("truck_id")
            reason = item.get("reason")
            if (
                not isinstance(identifier, str)
                or not identifier
                or not isinstance(reason, str)
                or not reason
                or identifier in excluded_ids
            ):
                return False
            excluded_ids.add(identifier)
        if not isinstance(resource_id, str) or not resource_id:
            return False
        if selected.get("resource_id") not in {None, resource_id}:
            return False
        if selected.get("operation") not in {"gate", "scale_in", "unload", "scale_out"}:
            return False
        if not isinstance(policy, str) or not policy:
            return False
        if not isinstance(explanation, str) or not explanation:
            return False
        if not _validate_decision_justification(recommendation):
            return False
        if line.get("resource_id") != resource_id:
            return False
        if line.get("candidates") != candidate_ids:
            return False
        if line.get("excluded") != excluded:
            return False
        if line.get("selection") != selected:
            return False
        if line.get("policy") != policy:
            return False
        if line.get("explanation") != explanation:
            return False
        if event_kind == "DECISION_RECORDED" and line.get("operator_decision") is not None:
            return False
    elif event_kind not in {"DECISION_RECORDED", "OPERATOR_DECISION"}:
        # Non-decision events still carry the canonical envelope, but no
        # recommendation fields may be fabricated on their behalf.
        if line.get("selection") is not None or line.get("candidates") != []:
            return False
        if line.get("excluded") != [] or line.get("explanation") != "":
            return False
        if line.get("operator_decision") is not None:
            return False
    return True


def _raise_missing_decision_log(path: Path, name: str) -> None:
    """Raise an audit error whose cause is the original missing-file error."""

    try:
        path.stat()
    except FileNotFoundError as exc:
        raise AuditError(f"missing decision log: {name}") from exc
    raise AuditError(f"missing decision log: {name}")


def _derived_log_metrics(details: Any) -> dict[str, int | float]:
    """Derive the canonical metrics from the replay evidence.

    Waiting is accumulated per truck at each of the four service starts.  A
    truck that is released, waiting, and still incomplete at the hard horizon
    contributes the residual ``horizon - ready_time`` once; an in-flight
    service does not receive a speculative residual.  This mirrors the DES
    state machine while keeping the audit independent of producer metrics.
    """

    final_snapshot = details.final_snapshot
    total_trucks = len(final_snapshot.trucks)
    if total_trucks <= 0:
        raise AuditError("persisted decision log has no trucks in final snapshot")

    # The public log terminates at the fixed protocol boundary.  Requiring the
    # explicit payload prevents an arbitrary earlier/later END_OF_DAY from
    # silently changing censored metrics.
    end_events = [event for event in details.events if event.kind == "END_OF_DAY"]
    if len(end_events) != 1 or details.events[-1].kind != "END_OF_DAY":
        raise AuditError("persisted decision log must contain one terminal END_OF_DAY")
    end_event = end_events[0]
    end_payload = end_event.to_dict()["payload"]
    horizon_value = end_payload.get("horizon_minutes")
    if (
        isinstance(horizon_value, bool)
        or not isinstance(horizon_value, (int, float))
        or not math.isfinite(float(horizon_value))
        or float(horizon_value) != 720.0
        or float(end_event.time) != 720.0
        or float(final_snapshot.clock) != 720.0
        or not final_snapshot.ended
        or final_snapshot.running
    ):
        raise AuditError("END_OF_DAY does not match the canonical 720-minute horizon")
    horizon = 720.0

    ready_times: dict[str, float] = {}
    arrived_ids: set[str] = set()
    released_ids: set[str] = set()
    completed_ids: set[str] = set()
    accumulated_wait: dict[str, float] = {
        truck_id: 0.0 for truck_id in final_snapshot.trucks
    }
    active_services: dict[str, tuple[str, str]] = {}
    active_resources: dict[str, str] = {}
    scale_occupancy = 0
    max_scale_occupancy = 0
    first_arrival_time: float | None = None
    scale_capacity = sum(
        resource.kind == "scale" for resource in final_snapshot.resources.values()
    )
    if scale_capacity <= 0:
        raise AuditError("final snapshot has no physical scale resource")
    completion_times: list[float] = []

    for event in details.events:
        payload = event.to_dict()["payload"]
        truck_id = payload.get("truck_id")
        operation = payload.get("operation")
        if event.kind == "TRUCK_ARRIVED":
            if not isinstance(truck_id, str) or truck_id not in final_snapshot.trucks:
                raise AuditError(
                    f"arrival references unknown truck at event {event.sequence}:{event.kind}"
                )
            arrival_time = float(payload["arrival_time"])
            if first_arrival_time is None:
                first_arrival_time = arrival_time
            else:
                first_arrival_time = min(first_arrival_time, arrival_time)
            arrived_ids.add(truck_id)
            # A document-blocked truck is not eligible for service waiting
            # until its explicit release event.
            if payload.get("document_ok") is True:
                ready_times[truck_id] = float(payload["arrival_time"])
                released_ids.add(truck_id)
            else:
                ready_times.pop(truck_id, None)
            continue

        if event.kind == "DOCUMENT_RELEASED":
            if not isinstance(truck_id, str) or truck_id not in arrived_ids:
                raise AuditError(
                    f"document release precedes arrival at event {event.sequence}:{event.kind}"
                )
            ready_times[truck_id] = float(event.time)
            released_ids.add(truck_id)
            continue

        if event.kind == "SERVICE_STARTED":
            if (
                not isinstance(truck_id, str)
                or truck_id not in ready_times
                or truck_id in active_services
            ):
                raise AuditError(
                    "cannot derive waiting time for service start: "
                    f"event {event.sequence}:{event.kind}"
                )
            if not isinstance(operation, str) or operation not in {
                "gate",
                "scale_in",
                "unload",
                "scale_out",
            }:
                raise AuditError(
                    f"service start has no canonical operation at event {event.sequence}:{event.kind}"
                )
            resource_id = payload.get("resource_id")
            if not isinstance(resource_id, str) or resource_id not in final_snapshot.resources:
                raise AuditError(
                    f"service start references unknown resource at event {event.sequence}:{event.kind}"
                )
            if resource_id in active_resources:
                raise AuditError(
                    "replayed resource occupancy became invalid at "
                    f"event {event.sequence}:{event.kind}"
                )
            wait = max(0.0, float(event.time) - ready_times[truck_id])
            if not math.isfinite(wait):
                raise AuditError(
                    f"derived waiting time is not finite at event {event.sequence}:{event.kind}"
                )
            accumulated_wait[truck_id] += wait
            active_services[truck_id] = (operation, resource_id)
            active_resources[resource_id] = truck_id
            if operation in {"scale_in", "scale_out"}:
                scale_occupancy += 1
                max_scale_occupancy = max(max_scale_occupancy, scale_occupancy)
                if scale_occupancy > scale_capacity:
                    raise AuditError(
                        "replayed scale capacity exceeded at "
                        f"event {event.sequence}:{event.kind}"
                    )
            continue

        if event.kind == "SERVICE_COMPLETED":
            if not isinstance(truck_id, str) or truck_id not in active_services:
                raise AuditError(
                    "service completion has no matching active service at "
                    f"event {event.sequence}:{event.kind}"
                )
            resource_id = payload.get("resource_id")
            expected_operation, expected_resource = active_services[truck_id]
            if (
                operation != expected_operation
                or resource_id != expected_resource
            ):
                raise AuditError(
                    "service completion does not match active service at "
                    f"event {event.sequence}:{event.kind}"
                )
            del active_services[truck_id]
            del active_resources[expected_resource]
            if operation in {"scale_in", "scale_out"}:
                scale_occupancy -= 1
                if scale_occupancy < 0:
                    raise AuditError(
                        "replayed scale occupancy became negative at "
                        f"event {event.sequence}:{event.kind}"
                    )
            completion_times.append(float(event.time))
            if operation == "scale_out":
                completed_ids.add(truck_id)
            else:
                ready_times[truck_id] = float(event.time)
                released_ids.add(truck_id)

    # Every terminal busy resource must correspond to one in-flight service;
    # active services are explicitly valid at the hard observation horizon.
    final_active_resources = {
        resource_id
        for resource_id, resource in final_snapshot.resources.items()
        if resource.status == "busy"
    }
    if final_active_resources != set(active_resources):
        raise AuditError(
            "final resource occupancy is incoherent with replayed services: "
            f"expected={sorted(active_resources)} observed={sorted(final_active_resources)}"
        )
    for truck_id, (_, resource_id) in active_services.items():
        truck = final_snapshot.trucks.get(truck_id)
        if (
            truck is None
            or truck.stage != TRUCK_STAGE_SERVICE_STARTED
            or truck.resource_id != resource_id
        ):
            raise AuditError(
                f"final active service is incoherent for truck {truck_id}"
            )
    if scale_occupancy != sum(
        1
        for truck_id, (operation, _) in active_services.items()
        if operation in {"scale_in", "scale_out"}
    ):
        raise AuditError("final scale occupancy is incoherent with active services")

    completed_trucks = sum(
        truck.stage == TRUCK_STAGE_SERVICE_COMPLETED
        for truck in final_snapshot.trucks.values()
    )
    final_completed_ids = {
        truck_id
        for truck_id, truck in final_snapshot.trucks.items()
        if truck.stage == TRUCK_STAGE_SERVICE_COMPLETED
    }
    if final_completed_ids != completed_ids:
        raise AuditError(
            "final completed-truck state is incoherent with replayed completions"
        )
    if active_services and completed_trucks == total_trucks:
        raise AuditError("all trucks are complete while a service remains active")

    waits: list[float] = []
    censored_wait = 0.0
    for truck_id in sorted(final_snapshot.trucks):
        value = accumulated_wait[truck_id]
        if (
            truck_id in arrived_ids
            and truck_id in released_ids
            and truck_id not in completed_ids
            and truck_id not in active_services
        ):
            if truck_id not in ready_times:
                raise AuditError(f"censored truck has no ready time: {truck_id}")
            residual = max(0.0, horizon - ready_times[truck_id])
            value += residual
            censored_wait += residual
        waits.append(value)

    ordered = sorted(waits)
    p95_index = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    mean_wait = round(sum(waits) / len(waits), 12)
    p95_wait = round(ordered[p95_index], 12)
    throughput = completed_trucks
    if first_arrival_time is None:
        raise AuditError("cannot derive makespan: no TRUCK_ARRIVED event before the hard horizon")
    if not completion_times:
        raise AuditError("cannot derive makespan: no SERVICE_COMPLETED event before the hard horizon")
    makespan = max(completion_times) - first_arrival_time
    if not math.isfinite(makespan) or makespan <= 0.0:
        raise AuditError(
            "cannot derive makespan: last SERVICE_COMPLETED is not after first TRUCK_ARRIVED"
        )
    makespan = round(makespan, 12)
    throughput_rate = round(throughput / makespan, 12) if makespan > 0 else 0.0
    return {
        "event_count": len(details.events),
        "total_trucks": total_trucks,
        "completed_trucks": completed_trucks,
        "throughput": throughput,
        "scale_occupancy_peak": max_scale_occupancy,
        "makespan_minutes": makespan,
        "throughput_rate": throughput_rate,
        "mean_wait_minutes": mean_wait,
        "p95_wait_minutes": p95_wait,
        "censored_wait_minutes": round(censored_wait, 12),
    }


def _validate_a2_manifest(manifest: Mapping[str, Any]) -> bool:
    """Validate the explicit automated/human A2 status contract."""

    from .governance import COMPUTATIONAL_PROTOCOL, study_scope
    configuration = _required_manifest_mapping(manifest, "configuration")
    if manifest.get("protocol_version") != configuration.get("protocol_version"):
        raise AuditError("manifest protocol_version disagrees with configuration")
    if configuration.get("protocol_version") == COMPUTATIONAL_PROTOCOL:
        config = ExperimentConfig(**dict(configuration))
        if manifest.get("study_scope") != study_scope(config):
            raise AuditError("v2 study_scope differs from the computational protocol")
        if manifest.get("phase") != "validation":
            provenance = _required_manifest_mapping(manifest, "input_provenance")
            expected_face = {"status": "NOT_EVALUATED", "required": False,
                             "scope": study_scope(config)}
            if provenance.get("face_validation") != expected_face:
                raise AuditError("v2 scientific provenance must identify face as NOT_EVALUATED")
        a2 = _required_manifest_mapping(manifest, "a2")
        if (manifest.get("human_audit_status") != "not_evaluated"
                or a2.get("human_audit_status") != "not_evaluated"):
            raise AuditError("v2 human_audit_status must be not_evaluated; complete requires a verified human review")
        if (a2.get("structural_status") != "automated"
                or a2.get("required_fields") != list(LOG_REQUIRED_FIELDS)):
            raise AuditError("v2 A2 requires all canonical automated structural fields")
        if (manifest.get("operator_mode") != "synthetic_auto_accept"
                or manifest.get("global_acceptance_status") != "pending"
                or manifest.get("human_review_evidence") is not None):
            raise AuditError("v2 computational audit cannot approve human or global acceptance")
        return False
    root_status = manifest.get("human_audit_status")
    if root_status not in {"pending", "complete"}:
        raise AuditError(
            "manifest human_audit_status must be explicitly 'pending' or 'complete'"
        )
    a2 = _required_manifest_mapping(manifest, "a2")
    nested_status = a2.get("human_audit_status")
    if nested_status not in {"pending", "complete"}:
        raise AuditError(
            "manifest a2.human_audit_status must be explicitly 'pending' or 'complete'"
        )
    if nested_status != root_status:
        raise AuditError(
            "manifest human_audit_status disagrees with manifest.a2.human_audit_status"
        )
    if a2.get("structural_status") != "automated":
        raise AuditError("manifest a2.structural_status must be 'automated'")
    required_fields = a2.get("required_fields")
    if not isinstance(required_fields, list) or required_fields != list(LOG_REQUIRED_FIELDS):
        raise AuditError("manifest a2.required_fields do not match canonical log fields")
    if root_status != "pending":
        raise AuditError("human_audit_status complete requires a verified human review workflow; automated runs cannot approve it")
    if manifest.get("operator_mode") != "synthetic_auto_accept":
        raise AuditError("manifest operator_mode must identify synthetic_auto_accept")
    if manifest.get("global_acceptance_status") != "pending" or manifest.get("human_review_evidence") is not None:
        raise AuditError("automated runs must retain pending global acceptance and no human review evidence")
    return True


_INPUT_IDENTITY_FIELDS = (
    "instance_id", "instance_hash", "execution_instance_hash", "dataset_root_hash", "control_hash",
)


def _require_digest(value: object, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise AuditError(f"invalid SHA-256 in input provenance: {label}")


def _validate_input_provenance(manifest, expected_pairs):
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 3:
        raise AuditError("run manifest schema_version must be 3")
    provenance = _required_manifest_mapping(manifest, "input_provenance")
    if provenance.get("kind") not in {"frozen_dataset", "validation_fixture"}:
        raise AuditError("input provenance kind is invalid")
    if provenance["kind"] == "validation_fixture" and manifest.get("phase") != "validation":
        raise AuditError("validation fixture cannot supply a scientific phase")
    for key in ("dataset_root_hash", "event_latents_sha256"):
        _require_digest(provenance.get(key), key)
    controls = _required_manifest_mapping(provenance, "controls")
    if set(controls) != {
        "ordinary_window", "buffer_capacity", "threshold_multiplier", "intensity",
        "source_dataset_root_hash", "event_latents_sha256", "control_hash",
    }:
        raise AuditError("input provenance controls fields are invalid")
    if (controls["source_dataset_root_hash"] != provenance["dataset_root_hash"]
            or controls["event_latents_sha256"] != provenance["event_latents_sha256"]):
        raise AuditError("input provenance controls disagree with source digests")
    material = {key: value for key, value in controls.items() if key != "control_hash"}
    digest = hashlib.sha256((_canonical_json(material) + "\n").encode("utf-8")).hexdigest()
    if controls["control_hash"] != digest:
        raise AuditError("input provenance control_hash does not match controls")
    entries = provenance.get("instances")
    if not isinstance(entries, list) or not entries:
        raise AuditError("input provenance instances must be a non-empty list")
    instances = {}
    identifiers = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {"instance_id", "scenario_id", "seed", "instance_hash"}:
            raise AuditError("input provenance instance descriptor is invalid")
        identifier = entry["instance_id"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers:
            raise AuditError("input provenance instance_id is missing or duplicated")
        if not isinstance(entry["scenario_id"], str) or type(entry["seed"]) is not int:
            raise AuditError("input provenance instance scenario/seed is invalid")
        _require_digest(entry["instance_hash"], identifier)
        pair = (entry["scenario_id"], entry["seed"])
        if pair in instances:
            raise AuditError("input provenance instance scenario/seed is duplicated")
        instances[pair] = entry
        identifiers.add(identifier)
    if set(instances) != expected_pairs:
        raise AuditError("input provenance instances do not match matrix scenario/seed grid")
    return provenance, instances


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Machine-checkable audit outcome for a run namespace."""

    run_dir: Path
    expected_rows: int
    observed_rows: int
    pair_key_unique: bool
    config_hashes: tuple[str, ...]
    log_count_expected: int
    log_count_observed: int
    log_sha256_pass: bool
    headers_pass: bool
    monotonic_time_pass: bool
    a2_fields_pass: bool
    a1_pass: bool
    replay_pass: bool
    a2_structural_pass: bool
    a2_human_audit_pending: bool
    a1_violations: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @property
    def a2_human_pending(self) -> bool:
        """Short alias retained for callers that use the compact field name."""

        return self.a2_human_audit_pending

    @property
    def sha256_pass(self) -> bool:
        return self.log_sha256_pass

    @property
    def pairing_pass(self) -> bool:
        return self.pair_key_unique and self.observed_rows == self.expected_rows

    @property
    def a1_violation_count(self) -> int:
        return len(self.a1_violations)

    @property
    def overall_pass(self) -> bool:
        """Pass of automated checks only; never human or global approval."""
        return self.a1_pass and self.a2_structural_pass and self.replay_pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_directory": str(self.run_dir),
            "expected_rows": self.expected_rows,
            "observed_rows": self.observed_rows,
            "pair_key_unique": self.pair_key_unique,
            "config_hashes": list(self.config_hashes),
            "one_config_hash": len(self.config_hashes) == 1,
            "log_count_expected": self.log_count_expected,
            "log_count_observed": self.log_count_observed,
            "log_sha256_pass": self.log_sha256_pass,
            "headers_pass": self.headers_pass,
            "monotonic_time_pass": self.monotonic_time_pass,
            "a2_fields_pass": self.a2_fields_pass,
            "a1_pass": self.a1_pass,
            "a1_violations": list(self.a1_violations),
            "replay_pass": self.replay_pass,
            "a2_structural_pass": self.a2_structural_pass,
            "a2_human_audit_pending": self.a2_human_audit_pending,
            "human_evaluation_status": "pending" if self.a2_human_audit_pending else "not_evaluated",
            "overall_pass": self.overall_pass,
            "acceptance_scope": "automated_structural_checks_only",
            "global_acceptance_status": "pending",
            "operator_mode": "synthetic_auto_accept",
            "diagnostics": list(self.diagnostics),
        }


def _audit_bundle(bundle: RunBundle) -> AuditReport:
    manifest = bundle.manifest
    if manifest.get("run_id") != bundle.run_id:
        raise AuditError("manifest run_id does not match run directory")
    config_checksum = manifest.get("config_hash")
    if not isinstance(config_checksum, str) or len(config_checksum) != 64:
        raise AuditError("manifest config_hash is missing or invalid")
    configuration = manifest.get("configuration")
    if not isinstance(configuration, Mapping):
        raise AuditError("manifest configuration is missing or invalid")
    try:
        manifest_config = ExperimentConfig(**dict(configuration))
        recomputed_config_hash = config_hash(manifest_config)
    except (TypeError, ValueError) as exc:
        raise AuditError("manifest configuration failed validation") from exc
    if recomputed_config_hash != config_checksum:
        raise AuditError(
            "manifest config_hash does not match canonical configuration: "
            f"expected={recomputed_config_hash} observed={config_checksum}"
        )
    expected_rows = manifest.get("expected_rows")
    if isinstance(expected_rows, bool) or not isinstance(expected_rows, int) or expected_rows <= 0:
        raise AuditError("manifest expected_rows is missing or invalid")
    human_audit_pending = _validate_a2_manifest(manifest)
    matrix = _required_manifest_mapping(manifest, "matrix")
    scenarios = _parse_scenario_specs(manifest, manifest_config)
    matrix_seeds = matrix.get("seeds")
    matrix_policies = matrix.get("policies")
    if not isinstance(matrix_seeds, list) or not isinstance(matrix_policies, list):
        raise AuditError("manifest matrix seeds and policies must be lists")
    provenance, instances = _validate_input_provenance(
        manifest, {(scenario_id, seed) for scenario_id in scenarios for seed in matrix_seeds},
    )
    projections = {}
    if provenance["kind"] == "frozen_dataset":
        from .dataset import load_frozen_dataset, derive_controlled_projection
        from .domain import ExecutionControls
        from .profiles import sensitivity_bootstrap
        frozen = load_frozen_dataset(provenance["dataset_path"],
            expected_dataset_root_hash=provenance["dataset_root_hash"])
        controls = ExecutionControls(**dict(provenance["controls"]))
        if (frozen.manifest["config_hash"] != config_checksum
                or frozen.event_latents.event_latents_sha256 != provenance["event_latents_sha256"]):
            raise AuditError("frozen dataset identity differs from scientific provenance")
        if manifest.get("phase") in {"sensitivity", "exploratory"}:
            if manifest.get("descriptive_bootstrap") != sensitivity_bootstrap(controls):
                raise AuditError("descriptive bootstrap identity differs from controls/ledger")
        for source in frozen.instances:
            pair = (source.scenario_id, source.seed)
            if pair not in instances:
                continue
            if source.instance_hash != instances[pair]["instance_hash"]:
                raise AuditError("scientific source instance differs from frozen dataset")
            projection = derive_controlled_projection(source, frozen.event_latents, controls)
            projections[pair] = {
                "controlled_view_hash": projection.controlled_view_hash,
                "event_overlay_hash": projection.event_overlay_hash,
                "execution_instance_hash": projection.instance.instance_hash,
            }
        if set(projections) != set(instances):
            raise AuditError("scientific provenance has instances absent from frozen dataset")
    # ``decision_logs`` is the canonical manifest field.  A secondary alias
    # must not become a recovery path if the canonical inventory is damaged.
    log_mapping_value = manifest.get("decision_logs")
    if not isinstance(log_mapping_value, Mapping):
        raise AuditError("manifest decision_logs must be an object")

    rows = tuple(bundle.results)
    if len(rows) != expected_rows:
        raise AuditError(
            f"incomplete results grid: expected {expected_rows} rows, observed {len(rows)}"
        )
    expected_keys = {
        _pair_key(scenario_id, seed, policy)
        for scenario_id in scenarios
        for seed in matrix_seeds
        for policy in matrix_policies
    }
    row_keys: list[str] = []
    headers_pass = True
    config_hashes: set[str] = set()
    a1_violations: list[str] = []
    diagnostics: list[str] = []
    row_by_log: dict[str, Mapping[str, Any]] = {}
    execution_hashes: dict[tuple[str, int], str] = {}
    for index, row in enumerate(rows, start=1):
        row_key = _pair_key(row.get("scenario_id"), row.get("seed"), row.get("policy"))
        row_keys.append(row_key)
        config_hashes.add(str(row.get("config_hash")))
        log_file = row.get("log_file")
        if not isinstance(log_file, str) or not log_file:
            raise AuditError(f"result row {index} has no log_file")
        if log_file in row_by_log:
            raise AuditError(f"duplicate log_file in results.csv: {log_file}")
        row_by_log[log_file] = row
        if row.get("config_hash") != config_checksum:
            raise AuditError(
                f"result row {index} config hash differs from manifest: {row.get('config_hash')}"
            )
        pair = (row.get("scenario_id"), row.get("seed"))
        instance = instances.get(pair)
        if instance is None:
            raise AuditError(f"result row {index} has no input provenance instance")
        for field, expected in (
            ("instance_id", instance["instance_id"]),
            ("instance_hash", instance["instance_hash"]),
            ("dataset_root_hash", provenance["dataset_root_hash"]),
            ("control_hash", provenance["controls"]["control_hash"]),
        ):
            if row.get(field) != expected:
                raise AuditError(f"result input provenance mismatch: row={index} field={field}")
        execution_hash = row.get("execution_instance_hash")
        _require_digest(execution_hash, f"row {index} execution_instance_hash")
        if execution_hashes.setdefault(pair, execution_hash) != execution_hash:
            raise AuditError(f"paired policies consumed different execution instances: {pair}")
        if not row.get("a1_pass") or int(row.get("hard_constraint_violations", 0)) != 0:
            a1_violations.append(
                f"{row_key}: hard_constraint_violations={row.get('hard_constraint_violations')}"
            )
        scenario_id = row.get("scenario_id")
        if scenario_id not in scenarios:
            raise AuditError(f"result row {index} references unknown scenario: {scenario_id}")
        canonical_metadata = scenarios[scenario_id]
        for field in _CANONICAL_SCENARIO_METADATA_FIELDS:
            observed = row.get(field)
            expected = canonical_metadata[field]
            if observed != expected:
                raise AuditError(
                    "canonical scenario metadata mismatch: "
                    f"run_id={bundle.run_id} row={index} scenario_id={scenario_id!r} "
                    f"field={field} expected={expected!r} observed={observed!r}"
                )

    pair_key_unique = len(row_keys) == len(set(row_keys))
    if not pair_key_unique:
        raise AuditError("duplicate pair key in results.csv")
    if set(row_keys) != expected_keys:
        missing = sorted(expected_keys - set(row_keys))
        extra = sorted(set(row_keys) - expected_keys)
        raise AuditError(f"paired grid does not match manifest: missing={missing} extra={extra}")
    if len(config_hashes) != 1:
        raise AuditError(f"results contain multiple configuration hashes: {sorted(config_hashes)}")

    expected_log_names = set(log_mapping_value)
    if expected_log_names != set(row_by_log):
        missing = sorted(set(row_by_log) - expected_log_names)
        extra = sorted(expected_log_names - set(row_by_log))
        raise AuditError(f"decision log manifest does not match results: missing={missing} extra={extra}")

    actual_log_names = {path.name for path in bundle.logs_dir.glob("*.jsonl")}
    if actual_log_names != expected_log_names:
        missing = sorted(expected_log_names - actual_log_names)
        extra = sorted(actual_log_names - expected_log_names)
        if missing:
            _raise_missing_decision_log(bundle.logs_dir / missing[0], missing[0])
        raise AuditError(f"unexpected decision log: {extra[0]}")

    log_sha_pass = True
    monotonic_pass = True
    a2_fields_pass = True
    replay_pass = True
    for log_name in sorted(expected_log_names):
        descriptor = log_mapping_value[log_name]
        if not isinstance(descriptor, Mapping):
            raise AuditError(f"decision log descriptor is invalid: {log_name}")
        relative_path = descriptor.get("path")
        expected_digest = descriptor.get("sha256")
        row = row_by_log.get(log_name)
        for field, expected in (
            ("run_id", bundle.run_id),
            ("scenario_id", row.get("scenario_id")),
            ("seed", row.get("seed")),
            ("policy", row.get("policy")),
            ("config_hash", config_checksum),
            *((field, row.get(field)) for field in _INPUT_IDENTITY_FIELDS),
        ):
            if descriptor.get(field) != expected:
                raise AuditError(
                    f"decision log descriptor identity mismatch: {log_name} field={field}"
                )
        if not isinstance(relative_path, str) or not relative_path:
            raise AuditError(f"decision log {log_name} has an invalid path")
        expected_relative_path = f"logs/{log_name}"
        if Path(relative_path).as_posix() != expected_relative_path:
            raise AuditError(
                f"decision log descriptor path mismatch: {log_name} "
                f"expected={expected_relative_path} observed={relative_path}"
            )
        log_path = bundle.run_dir / relative_path
        resolved_run = bundle.run_dir.resolve()
        resolved_log = log_path.resolve()
        if resolved_run != resolved_log.parent and resolved_run not in resolved_log.parents:
            raise AuditError(f"decision log path escapes run directory: {log_name}")
        if not log_path.is_file():
            _raise_missing_decision_log(log_path, log_name)
        observed_digest = _sha256(log_path)
        if not isinstance(expected_digest, str) or observed_digest != expected_digest:
            log_sha_pass = False
            raise AuditError(
                f"decision log SHA-256 mismatch: {log_name} expected={expected_digest} observed={observed_digest}"
            )
        if row.get("log_sha256") != observed_digest:
            log_sha_pass = False
            raise AuditError(f"results log_sha256 mismatch: {log_name}")
        try:
            details = _replay_log(log_path)
        except (FileNotFoundError, ReplayError) as exc:
            replay_pass = False
            raise AuditError(f"replay failed for decision log: {log_name}") from exc

        if (
            details.run_id != bundle.run_id
            or details.log_path.resolve() != log_path.resolve()
            or details.scenario_id != row.get("scenario_id")
            or details.seed != row.get("seed")
            or details.policy != row.get("policy")
            or details.config_hash != config_checksum
        ):
            raise AuditError(f"decision log identity does not match persisted receipts: {log_name}")
        previous_time = -float("inf")
        truck_facts = {
            identifier: {"arrival_time": truck.arrival_time, "cargo_type": truck.cargo_type,
                         "stage_entry_time": truck.stage_entry_time}
            for identifier, truck in details.initial_snapshot.trucks.items()
        }
        observed_resources = details.initial_snapshot.resources
        resource_statuses = {identifier: resource.status for identifier, resource in observed_resources.items()}
        last_cargo = {}
        for line_number, (line, event) in enumerate(zip(details.lines, details.events), start=1):
            for field in _INPUT_IDENTITY_FIELDS:
                if line.get(field) != row[field]:
                    raise AuditError(f"log input provenance mismatch: {log_name} line={line_number} field={field}")
            if event.kind == "RUN_STARTED":
                if projections:
                    expected_projection = projections[(row["scenario_id"], row["seed"])]
                    if any(event.payload.get(key) != value for key, value in expected_projection.items()):
                        raise AuditError(f"RUN_STARTED projection differs from frozen controls/ledger: {log_name}")
                if event.payload.get("operator_mode") != manifest["operator_mode"]:
                    raise AuditError(f"RUN_STARTED operator mode mismatch: {log_name}")
                if event.to_dict()["payload"].get("execution_controls") != provenance["controls"]:
                    raise AuditError(f"RUN_STARTED execution controls mismatch: {log_name}")
                for field in _INPUT_IDENTITY_FIELDS:
                    if event.payload.get(field) != row[field]:
                        raise AuditError(f"RUN_STARTED input provenance mismatch: {log_name} field={field}")
                if event.payload.get("event_latents_sha256") != provenance["event_latents_sha256"]:
                    raise AuditError(f"RUN_STARTED event-latent provenance mismatch: {log_name}")
            if not _validate_log_fields(line, event, line_number):
                a2_fields_pass = False
                raise AuditError(
                    f"A2 decision fields are incoherent: {log_name} line {line_number}"
                )
            if event.kind in {"DECISION_RECORDED", "OPERATOR_DECISION"}:
                recommendation = event.to_dict()["payload"][
                    "decision" if event.kind == "DECISION_RECORDED" else "recommendation"
                ]
                if not _validate_decision_observation(
                    recommendation, event.time, truck_facts, observed_resources, resource_statuses, last_cargo,
                ):
                    raise AuditError(f"A2 decision observation disagrees with events: {log_name} line={line_number}")
            elif event.kind == "TRUCK_ARRIVED":
                truck_facts[event.payload["truck_id"]] = {
                    "arrival_time": event.payload["arrival_time"], "cargo_type": event.payload["cargo_type"],
                    "stage_entry_time": event.time,
                }
            elif event.kind in {"DOCUMENT_RELEASED", "SERVICE_STARTED", "SERVICE_COMPLETED"}:
                truck_facts[event.payload["truck_id"]]["stage_entry_time"] = event.time
                if event.kind == "SERVICE_COMPLETED":
                    last_cargo[event.payload["resource_id"]] = truck_facts[event.payload["truck_id"]]["cargo_type"]
            if event.kind in {"SERVICE_STARTED", "SERVICE_COMPLETED", "RESOURCE_FAILED", "RESOURCE_RECOVERED"}:
                resource_statuses[event.payload["resource_id"]] = {
                    "SERVICE_STARTED": "busy", "SERVICE_COMPLETED": "available",
                    "RESOURCE_FAILED": "failed", "RESOURCE_RECOVERED": "available",
                }[event.kind]
            if event.time < previous_time:
                monotonic_pass = False
                raise AuditError(
                    f"event time regresses in decision log: {log_name} line {line_number}"
                )
            previous_time = event.time
        from .metrics import compute_policy_day_metrics
        try:
            calculated = compute_policy_day_metrics(log_path)
        except (ValueError, TypeError, KeyError) as exc:
            raise AuditError(f"persisted metrics cannot be reconstructed: {log_name}") from exc
        expected_metrics_file = f"metrics/{log_name.removesuffix('.jsonl')}.json"
        if row["metrics_file"] != expected_metrics_file:
            raise AuditError(f"metrics artifact path mismatch: {log_name}")
        metrics_path = bundle.run_dir / expected_metrics_file
        if metrics_path.resolve().parent != (bundle.run_dir / "metrics").resolve():
            raise AuditError(f"metrics artifact escapes run directory: {log_name}")
        if _sha256(metrics_path) != row["metrics_sha256"]:
            raise AuditError(f"metrics artifact SHA-256 mismatch: {log_name}")
        if json.loads(metrics_path.read_text(encoding="utf-8")) != calculated.to_dict():
            raise AuditError(f"metrics artifact does not reconcile with log: {log_name}")
        for metric, value in calculated.scalars.items():
            if row[metric] != value:
                raise AuditError(f"persisted metric {metric} does not reconcile with log: {log_name} expected={value} observed={row[metric]}")
        derived = _derived_log_metrics(details)
        for metric in (
            "event_count",
            "total_trucks",
            "completed_trucks",
            "throughput",
            "scale_occupancy_peak",
        ):
            if row.get(metric) != derived[metric]:
                raise AuditError(
                    f"persisted metric {metric} does not reconcile with log: {log_name} "
                    f"expected={derived[metric]} observed={row.get(metric)}"
                )
        for metric in (
            "mean_wait_minutes",
            "p95_wait_minutes",
            "censored_wait_minutes",
        ):
            # ``derived`` already applies the producer's round(..., 12).
            # Equality on the parsed canonical float rejects every distinct
            # persistible value, including sub-tolerance deltas.
            if float(row.get(metric)) != float(derived[metric]):
                raise AuditError(
                    f"persisted metric {metric} does not reconcile with log: {log_name} "
                    f"expected={derived[metric]} observed={row.get(metric)}"
                )
        if not math.isclose(
            float(row.get("makespan_minutes")),
            float(derived["makespan_minutes"]),
            rel_tol=0.0,
            abs_tol=_DERIVED_FLOAT_TOLERANCE,
        ):
            raise AuditError(f"persisted metric makespan_minutes does not reconcile with log: {log_name}")
        if not math.isclose(
            float(row.get("throughput_rate")),
            float(derived["throughput_rate"]),
            rel_tol=0.0,
            abs_tol=_DERIVED_FLOAT_TOLERANCE,
        ):
            raise AuditError(f"persisted metric throughput_rate does not reconcile with log: {log_name}")
        replay_hash = snapshot_hash(details.final_snapshot)
        initial_hash = snapshot_hash(details.initial_snapshot)
        if (
            row.get("initial_state_hash") != initial_hash
            or row.get("final_state_hash") != replay_hash
            or row.get("replay_state_hash") != replay_hash
            or not row.get("replay_pass")
        ):
            replay_pass = False
            raise AuditError(f"final replay equivalence failed: {log_name}")
        expected_scale_count = scenarios[row.get("scenario_id")].get("scale_count")
        if isinstance(expected_scale_count, int) and int(row.get("scale_occupancy_peak", 0)) > expected_scale_count:
            a1_violations.append(
                f"{_pair_key(row.get('scenario_id'), row.get('seed'), row.get('policy'))}: scale capacity exceeded"
            )

    if not headers_pass:
        raise AuditError("results.csv headers are invalid")
    a2_structural_pass = (
        len(rows) == expected_rows
        and pair_key_unique
        and len(config_hashes) == 1
        and log_sha_pass
        and a2_fields_pass
        and monotonic_pass
        and replay_pass
    )
    report = AuditReport(
        run_dir=bundle.run_dir,
        expected_rows=expected_rows,
        observed_rows=len(rows),
        pair_key_unique=pair_key_unique,
        config_hashes=tuple(sorted(config_hashes)),
        log_count_expected=len(expected_log_names),
        log_count_observed=len(expected_log_names),
        log_sha256_pass=log_sha_pass,
        headers_pass=headers_pass,
        monotonic_time_pass=monotonic_pass,
        a2_fields_pass=a2_fields_pass,
        a1_pass=not a1_violations,
        replay_pass=replay_pass,
        a2_structural_pass=a2_structural_pass,
        a2_human_audit_pending=human_audit_pending,
        a1_violations=tuple(a1_violations),
        diagnostics=tuple(diagnostics),
    )
    return report


def audit_run(run_dir: str | Path) -> AuditReport:
    """Audit only the artifacts in ``run_dir`` and persist ``audit.json``."""

    if not isinstance(run_dir, (str, Path)):
        raise TypeError("run_dir must be a string or Path")
    directory = Path(run_dir)
    try:
        bundle = load_run_bundle(directory)
    except AuditError:
        raise
    except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuditError(
            f"cannot load run bundle for audit: {directory}: {exc}"
        ) from exc
    report = _audit_bundle(bundle)
    _atomic_write_json(directory / "audit.json", report.to_dict())
    return report


__all__ = ["AuditError", "AuditReport", "audit_run"]
