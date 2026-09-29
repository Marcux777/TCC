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
from .dispatch import DecisionJustification
from .experiment import LOG_REQUIRED_FIELDS, RESULT_HEADERS, RunBundle, load_run_bundle
from .events import EventRecord
from .replay import ReplayError, _replay_log, snapshot_hash


class AuditError(RuntimeError):
    """Raised when persisted evidence cannot be audited fail-closed."""


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
    if any(policy not in config.policies for policy in policies):
        raise AuditError("manifest matrix policies must belong to configuration policies")
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
    }
)

_POLICY_JUSTIFICATION_RULES: dict[str, tuple[str, ...]] = {
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


def _observed_exclusion(
    item: Mapping[str, Any], context: Mapping[str, Any]
) -> tuple[str, str] | None:
    """Reconstruct hard constraints from persisted facts, independently of dispatch."""
    if not item["arrived"]:
        return "NOT_ARRIVED", "truck not arrived"
    if item["arrival_time"] > context["now"]:
        return "FUTURE_ARRIVAL", "truck arrival is in the future"
    if not item["eligible"]:
        return "INELIGIBLE", item["eligibility_reason"] or "candidate is not eligible"
    if not item["document_ok"]:
        return "DOCUMENT_BLOCKED", "document blocked"
    if context["operation"] is not None and item["operation"] is not None:
        if item["operation"] != context["operation"]:
            return "OPERATION_MISMATCH", "operation mismatch"
    if item["resource_id"] is not None and item["resource_id"] != context["resource_id"]:
        return "RESOURCE_MISMATCH", "resource mismatch"
    if item["cargo_type"] not in context["allowed_cargo_types"]:
        return "CARGO_INCOMPATIBLE", f"cargo type {item['cargo_type']!r} is incompatible with resource"
    return None


def _validate_decision_observation(recommendation, event_time, truck_facts, resources, statuses) -> bool:
    """Bind FIFO/cargo evidence to preceding events, not just to itself."""
    context = recommendation["context"]
    resource_id = context["resource_id"]
    resource = resources.get(resource_id)
    if resource is None or context["now"] != event_time:
        return False
    if (context["resource_status"] != statuses[resource_id]
            or context["allowed_cargo_types"] != list(resource.allowed_cargo_types)):
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
        observed_exclusion = _observed_exclusion(evidence, context)
        if observed_exclusion is None or (item["cause"], exclusion_reason) != observed_exclusion:
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

    # Schema 2 persists canonical evidence, not unrestricted prose. Reconstruct
    # the entire reason here so retaining valid tokens cannot hide invented claims.
    fifo_sentence = (
        f"FIFO order broken: {selected_id} precedes {fifo_reference}"
        if expected_fifo_break else "FIFO order preserved"
    )
    expected_reason = (
        f"Selected truck {selected_id} for stage {selected_stage} on resource "
        f"{resource_id} under policy {policy}; {fifo_sentence}"
    )
    policy_rules = _POLICY_JUSTIFICATION_RULES.get(policy, ())
    if policy_rules:
        expected_reason += f"; applied rules: {', '.join(policy_rules)}"
    if has_resource_block:
        expected_reason += "; a resource assignment was blocked by compatibility constraints"
    return justification.reason == expected_reason + "."


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


def _metric_interval_union(intervals, horizon):
    """Construct occupied spans by integrating endpoint multiplicities."""
    endpoints = {}
    for begin, end in intervals:
        begin, end = max(0.0, begin), min(horizon, end)
        if end <= begin:
            continue
        endpoints[begin] = endpoints.get(begin, 0) + 1
        endpoints[end] = endpoints.get(end, 0) - 1
    spans, occupancy, opened = [], 0, None
    for instant, change in sorted(endpoints.items()):
        previous = occupancy
        occupancy += change
        if previous == 0 and occupancy > 0:
            opened = instant
        elif previous > 0 and occupancy == 0:
            spans.append((opened, instant))
        if occupancy < 0:
            raise AuditError("metric interval accounting has negative occupancy")
    if occupancy:
        raise AuditError("metric interval accounting is not closed")
    return spans


def _derived_log_metrics(details: Any):
    """Reconstruct every metric from event facts, independently of metrics.py.

    Only the declarative metric schema and immutable result DTO are shared.
    Truck time partitions, resource interval unions, queue observations and
    admission diagnostics are rebuilt here; no producer reducer or CSV value
    supplies an expected measurement.
    """
    from .config import CANONICAL_CONFIRMATORY_FIELDS
    from .domain import ExecutionControls
    from .metrics import INTEGER_METRIC_FIELDS, METRIC_DEFINITIONS, MetricRow

    events = tuple(details.events)
    if not events or events[0].kind != "RUN_STARTED" or events[-1].kind != "END_OF_DAY":
        raise AuditError("metric evidence requires a closed RUN_STARTED/END_OF_DAY log")
    horizon = events[-1].payload["horizon_minutes"]
    if type(horizon) not in (int, float) or horizon != 720 or events[-1].time != horizon or events[0].time != 0:
        raise AuditError("metric evidence does not cover the canonical 720-minute horizon")
    horizon = float(horizon)
    for sequence, event in enumerate(events, 1):
        if event.sequence != sequence or not 0 <= event.time <= horizon:
            raise AuditError("metric evidence sequence or observation window is invalid")
        if sequence > 1 and event.time < events[sequence - 2].time:
            raise AuditError("metric evidence time regresses")
        if (event.kind == "RUN_STARTED" and sequence != 1) or (event.kind == "END_OF_DAY" and sequence != len(events)):
            raise AuditError("metric evidence has repeated observation boundaries")
    start = events[0].to_dict()["payload"]
    initial = start["initial_snapshot"]
    trucks, resources = initial["trucks"], initial["resources"]
    if not isinstance(trucks, Mapping) or not trucks or not isinstance(resources, Mapping) or not resources:
        raise AuditError("metric reconstruction requires nonempty initial inventories")
    controls = ExecutionControls(**start["execution_controls"])
    admission_mode = start["admission_mode"]
    if admission_mode not in {"full_queue", "mandatory_window"}:
        raise AuditError("metric evidence has an invalid admission_mode")

    operations = ("gate", "scale_in", "unload", "scale_out")
    kinds = {"gate": "gate", "scale_in": "scale", "unload": "hopper", "scale_out": "scale"}
    threshold = tuple(CANONICAL_CONFIRMATORY_FIELDS["priority_thresholds"])
    facts = {}
    for identifier, item in trucks.items():
        if (not isinstance(identifier, str) or not identifier or item["arrived"] is not False
                or item["next_operation"] != "gate" or type(item["document_ok"]) is not bool
                or type(item["priority"]) is not int or item["priority"] not in (0, 1, 2)
                or not isinstance(item["cargo_type"], str) or not item["cargo_type"]
                or type(item["arrival_time"]) not in (int, float)
                or not 0 <= item["arrival_time"] <= horizon):
            raise AuditError(f"invalid initial metric truck facts: {identifier}")
        facts[identifier] = {
            "arrival": item["arrival_time"], "arrived": False, "document": item["document_ok"],
            "priority": item["priority"], "cargo": item["cargo_type"], "operation": "gate",
            "entered": item["arrival_time"], "ready": None, "departure": None,
            "waits": [], "services": [], "document_hold": 0.0,
        }
    statuses = {}
    for identifier, item in resources.items():
        cargo = item["allowed_cargo_types"]
        if (not isinstance(identifier, str) or not identifier or item["status"] != "available"
                or item["kind"] not in {"gate", "scale", "hopper"} or not isinstance(cargo, (list, tuple))
                or not cargo or len(set(cargo)) != len(cargo)
                or any(not isinstance(value, str) or not value for value in cargo)):
            raise AuditError(f"invalid initial metric resource facts: {identifier}")
        statuses[identifier] = "available"

    active, occupied, recorded, accepted, previous_orders = {}, {}, {}, {}, {}
    service_spans = {identifier: [] for identifier in resources}
    failure_spans = {identifier: [] for identifier in resources}
    cause_spans = {identifier: [] for identifier in resources}
    failed_at, cause_ids = {}, set()
    completions, comparison_displacements = [], []
    counters = {name: 0 for name in (
        "decision_count", "fifo_break_count", "raw_fifo_break_count", "avoidable_fifo_break_count",
        "queue_comparison_count", "comparable_candidate_count", "queue_inversion_count",
        "max_queue_displacement", "replanning_count", "ordinary_window_activation_count",
        "mandatory_candidate_count", "mandatory_decision_count",
        "critical_expansion_candidate_count", "critical_expansion_decision_count",
        "operator_accept_count", "operator_reject_count", "dispatch_block_count", "command_count",
        "scale_occupancy_peak", "max_queue_length", "max_buffer_occupancy", "max_buffer_reservation",
    )}

    def occupancy():
        queues = {operation: 0 for operation in operations}
        inbound = outbound = 0
        for identifier, fact in facts.items():
            if not fact["arrived"] or fact["operation"] == "done":
                continue
            operation = fact["operation"]
            serving = identifier in active
            if not serving:
                queues[operation] += 1
            inbound += operation in {"scale_in", "unload"}
            outbound += (operation == "unload" and serving) or (operation == "scale_out" and not serving)
        return queues, inbound, outbound

    def queue_for(resource_id):
        if resource_id not in resources:
            raise AuditError(f"metric decision references unknown resource {resource_id}")
        resource = resources[resource_id]
        _, inbound, outbound = occupancy()
        raw = sorted(
            (identifier for identifier, fact in facts.items()
             if fact["arrived"] and identifier not in active and fact["operation"] != "done"
             and kinds[fact["operation"]] == resource["kind"]),
            key=lambda identifier: (facts[identifier]["entered"], identifier),
        )
        feasible = []
        for identifier in raw:
            fact = facts[identifier]
            operation = fact["operation"]
            capacity_ok = (
                inbound < controls.buffer_capacity if operation == "gate" else
                inbound <= controls.buffer_capacity if operation == "scale_in" else
                outbound < controls.buffer_capacity if operation == "unload" else True
            )
            if fact["document"] and fact["cargo"] in resource["allowed_cargo_types"] and capacity_ok:
                feasible.append(identifier)
        return raw, feasible

    for event in events[1:-1]:
        payload, now, kind = event.to_dict()["payload"], event.time, event.kind
        identifier = payload.get("truck_id")
        resource_id = payload.get("resource_id")
        if identifier is not None and identifier not in facts:
            raise AuditError(f"metric event references unknown truck {identifier}")
        if resource_id is not None and resource_id not in resources:
            raise AuditError(f"metric event references unknown resource {resource_id}")
        if kind == "TRUCK_ARRIVED":
            fact = facts[identifier]
            if (fact["arrived"] or now != fact["arrival"] or payload["arrival_time"] != now
                    or payload["priority"] != fact["priority"] or payload["cargo_type"] != fact["cargo"]
                    or payload["document_ok"] is not fact["document"]):
                raise AuditError("metric arrival evidence disagrees with the initial inventory")
            fact["arrived"] = True
            if fact["document"]:
                fact["ready"] = now
        elif kind == "DOCUMENT_RELEASED":
            fact = facts[identifier]
            if not fact["arrived"] or fact["document"] or fact["operation"] != "gate":
                raise AuditError("metric document release is not a valid blocked-truck transition")
            fact.update(document=True, ready=now, entered=now, document_hold=now-fact["arrival"])
        elif kind == "PRIORITY_CHANGED":
            priority = payload["priority"]
            if type(priority) is not int or priority not in (0, 1, 2) or facts[identifier]["operation"] == "done":
                raise AuditError("metric priority observation is invalid")
            facts[identifier]["priority"] = priority
        elif kind == "DECISION_RECORDED":
            recommendation = payload["decision"]
            resource_id = recommendation["resource_id"]
            raw, feasible = queue_for(resource_id)
            if statuses[resource_id] != "available":
                raise AuditError("metric decision requires an available resource")
            order = tuple(candidate["truck_id"] for candidate in recommendation["candidate_order"])
            if not order or len(set(order)) != len(order) or tuple(recommendation["candidate_ids"]) != order:
                raise AuditError("metric decision candidate identities are incomplete or duplicated")
            mandatory = [truck for truck in feasible if facts[truck]["priority"] == 2]
            admitted = feasible
            if admission_mode == "mandatory_window":
                if mandatory:
                    admitted = mandatory
                    counters["mandatory_candidate_count"] += len(mandatory)
                    counters["mandatory_decision_count"] += 1
                else:
                    prefix = feasible[:controls.ordinary_window]
                    beyond = [
                        truck for truck in feasible[controls.ordinary_window:]
                        if now-facts[truck]["entered"] > threshold[facts[truck]["priority"]]*float(controls.threshold_multiplier)
                    ]
                    admitted = prefix + beyond
                    counters["ordinary_window_activation_count"] += len(feasible) > controls.ordinary_window
                    counters["critical_expansion_candidate_count"] += len(beyond)
                    counters["critical_expansion_decision_count"] += bool(beyond)
            if set(order) != set(admitted):
                raise AuditError("metric candidate set disagrees with independently reconstructed admission")
            for candidate in recommendation["candidate_order"]:
                fact = facts[candidate["truck_id"]]
                if candidate["stage_entry_time"] != fact["entered"] or candidate["operation"] != fact["operation"]:
                    raise AuditError("metric candidate position disagrees with its event-derived stage")
            selected = recommendation["selected"]
            selected_id = selected["truck_id"]
            if selected_id not in order or selected["resource_id"] != resource_id:
                raise AuditError("metric selection is outside the admitted queue")
            fifo = min(order, key=lambda truck: (facts[truck]["entered"], truck))
            broke_fifo = selected_id != fifo
            if recommendation["justification"]["fifo_break"] is not broke_fifo:
                raise AuditError("metric FIFO justification disagrees with reconstructed order")
            counters["decision_count"] += 1
            counters["fifo_break_count"] += broke_fifo
            raw_break = selected_id != raw[0]
            counters["raw_fifo_break_count"] += raw_break
            counters["avoidable_fifo_break_count"] += (
                raw_break and raw[0] in feasible
                and (admission_mode == "full_queue" or not mandatory or raw[0] in mandatory)
            )
            if resource_id in previous_orders:
                previous = previous_orders[resource_id]
                shared = set(previous) & set(order)
                left = {truck: index for index, truck in enumerate(truck for truck in previous if truck in shared)}
                right = {truck: index for index, truck in enumerate(truck for truck in order if truck in shared)}
                common = sorted(shared)
                inversions = sum(
                    (left[a]-left[b])*(right[a]-right[b]) < 0
                    for index, a in enumerate(common) for b in common[index+1:]
                )
                movements = [abs(left[truck]-right[truck]) for truck in common]
                counters["queue_comparison_count"] += 1
                counters["comparable_candidate_count"] += len(common)
                counters["queue_inversion_count"] += inversions
                counters["replanning_count"] += bool(inversions)
                counters["max_queue_displacement"] = max(counters["max_queue_displacement"], max(movements, default=0))
                comparison_displacements.append(sum(movements)/len(movements) if movements else 0.0)
            previous_orders[resource_id] = order
            if selected_id in recorded or selected_id in accepted:
                raise AuditError("metric recommendation overwrites a pending command")
            recorded[selected_id] = recommendation
        elif kind == "OPERATOR_DECISION":
            recommendation = payload["recommendation"]
            selected_id = recommendation["selected"]["truck_id"]
            if recorded.pop(selected_id, None) != recommendation:
                raise AuditError("metric operator response has no identical recorded recommendation")
            if payload["decision"] == "accept":
                counters["operator_accept_count"] += 1
                accepted[selected_id] = recommendation["selected"]
            elif payload["decision"] == "reject":
                counters["operator_reject_count"] += 1
            else:
                raise AuditError("metric operator response is unsupported")
        elif kind == "SERVICE_STARTED":
            fact, operation, duration = facts[identifier], payload["operation"], payload["duration_minutes"]
            if (identifier in active or resource_id in occupied or statuses[resource_id] != "available"
                    or operation != fact["operation"] or identifier not in queue_for(resource_id)[1]
                    or type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0
                    or fact["ready"] is None or now < fact["ready"]):
                raise AuditError("metric service start violates physical eligibility or time accounting")
            command = accepted.pop(identifier, None)
            if command is None or command["resource_id"] != resource_id or command["operation"] != operation:
                raise AuditError("metric service start has no corresponding accepted command")
            fact["waits"].append(now-fact["ready"])
            fact["entered"] = now
            active[identifier] = (operation, resource_id, now, duration)
            occupied[resource_id] = identifier
            statuses[resource_id] = "busy"
            counters["command_count"] += 1
            counters["scale_occupancy_peak"] = max(
                counters["scale_occupancy_peak"], sum(resources[key]["kind"] == "scale" for key in occupied),
            )
        elif kind == "SERVICE_COMPLETED":
            service = active.pop(identifier, None)
            operation = payload["operation"]
            if (service is None or service[:2] != (operation, resource_id)
                    or occupied.get(resource_id) != identifier or now != service[2]+service[3]):
                raise AuditError("metric completion does not match the observed service interval")
            fact = facts[identifier]
            fact["services"].append(now-service[2])
            service_spans[resource_id].append((service[2], now))
            position = operations.index(operation)
            fact["operation"] = operations[position+1] if position < 3 else "done"
            fact["entered"] = fact["ready"] = now
            if fact["operation"] == "done":
                fact["departure"] = now
            del occupied[resource_id]
            statuses[resource_id] = "available"
            completions.append(now)
        elif kind == "DISRUPTION_RECORDED":
            identity = (resource_id, payload["latent_id"])
            if identity in cause_ids or statuses[resource_id] == "busy":
                raise AuditError("metric disruption is duplicated or preempts a service")
            cause_ids.add(identity)
            effective, recovery = payload["effective_failure_start"], payload["recovery_time"]
            if effective != now or type(recovery) not in (int, float) or not math.isfinite(recovery):
                raise AuditError("metric disruption interval is invalid")
            if recovery > effective:
                cause_spans[resource_id].append((effective, recovery))
        elif kind == "RESOURCE_FAILED":
            if statuses[resource_id] != "available":
                raise AuditError("metric downtime begins on an unavailable resource")
            failed_at[resource_id] = now
            statuses[resource_id] = "failed"
        elif kind == "RESOURCE_RECOVERED":
            if statuses[resource_id] != "failed":
                raise AuditError("metric recovery has no active failure")
            failure_spans[resource_id].append((failed_at.pop(resource_id), now))
            statuses[resource_id] = "available"
        elif kind == "DISPATCH_BLOCKED":
            if resource_id is None:
                raise AuditError("metric blocked dispatch has no physical resource")
            counters["dispatch_block_count"] += 1
        else:
            raise AuditError(f"metric reconstruction does not handle event {kind}")

        queues, inbound, outbound = occupancy()
        counters["max_queue_length"] = max(counters["max_queue_length"], *queues.values())
        counters["max_buffer_occupancy"] = max(
            counters["max_buffer_occupancy"], inbound, *(queues[operation] for operation in operations[1:]),
        )
        counters["max_buffer_reservation"] = max(counters["max_buffer_reservation"], inbound, outbound)
        if max(counters["max_buffer_occupancy"], counters["max_buffer_reservation"]) > controls.buffer_capacity:
            raise AuditError("metric event history exceeds a physical buffer capacity")
    if recorded or accepted:
        raise AuditError("metric observation ends with an unfinished decision/command")
    if not counters["decision_count"] or not counters["queue_comparison_count"]:
        raise AuditError("metric decision/stability denominator is undefined")

    truck_rows, waits, complete_system, censored_system = {}, [], [], []
    censored_waits, holds = [], []
    for identifier in sorted(facts):
        fact = facts[identifier]
        if not fact["arrived"]:
            raise AuditError(f"metric evidence is missing a scheduled arrival: {identifier}")
        censored_wait = censored_service = 0.0
        if identifier in active:
            _, resource_id, begin, duration = active[identifier]
            if begin+duration <= horizon:
                raise AuditError("metric evidence is missing a completion inside the horizon")
            censored_service = horizon-begin
            fact["services"].append(censored_service)
            service_spans[resource_id].append((begin, horizon))
        elif fact["document"] and fact["departure"] is None:
            censored_wait = horizon-fact["ready"]
            fact["waits"].append(censored_wait)
        if not fact["document"]:
            fact["document_hold"] = horizon-fact["arrival"]
        wait, service, hold = sum(fact["waits"]), sum(fact["services"]), fact["document_hold"]
        censored = fact["departure"] is None
        observed = (horizon if censored else fact["departure"])-fact["arrival"]
        if not math.isclose(observed, wait+service+hold, rel_tol=0, abs_tol=1e-8):
            raise AuditError(f"metric truck time partition does not reconcile: {identifier}")
        waits.append(wait)
        holds.append(hold)
        censored_waits.append(censored_wait)
        (censored_system if censored else complete_system).append(observed)
        truck_rows[identifier] = {
            "wait_minutes": round(float(wait), 12), "censored_wait_minutes": round(float(censored_wait), 12),
            "service_minutes": round(float(service), 12), "censored_service_minutes": round(float(censored_service), 12),
            "document_hold_minutes": round(float(hold), 12), "observed_system_time_minutes": round(float(observed), 12),
            "system_time_censored": censored,
        }
    if not complete_system:
        raise AuditError("completed-system-time metric denominator is undefined")
    if not completions:
        raise AuditError("observed makespan is undefined without service completions")

    resource_rows, busy_values, down_values = {}, [], []
    for resource_id in sorted(resources):
        if resource_id in failed_at:
            failure_spans[resource_id].append((failed_at[resource_id], horizon))
        down_spans = _metric_interval_union(failure_spans[resource_id], horizon)
        if down_spans != _metric_interval_union(cause_spans[resource_id], horizon):
            raise AuditError(f"metric downtime disagrees with independent disruption union: {resource_id}")
        busy_spans = _metric_interval_union(service_spans[resource_id], horizon)
        if any(max(a, c) < min(b, d) for a, b in busy_spans for c, d in down_spans):
            raise AuditError("metric service overlaps resource downtime")
        busy = sum(end-begin for begin, end in busy_spans)
        down = sum(end-begin for begin, end in down_spans)
        available, idle = horizon-down, horizon-down-busy
        if available <= 0 or idle < 0:
            raise AuditError("metric net utilization denominator or idle interval is invalid")
        busy_values.append(busy)
        down_values.append(down)
        values = {
            "gross_minutes": horizon, "busy_minutes": busy, "down_minutes": down,
            "available_minutes": available, "idle_minutes": idle,
            "gross_utilization": busy/horizon, "net_utilization": busy/available,
            "net_idle_fraction": idle/available, "gross_idle_fraction": idle/horizon,
        }
        resource_rows[resource_id] = {"kind": resources[resource_id]["kind"], **{
            name: round(float(value), 12) for name, value in values.items()
        }}

    def percentile(values, probability):
        ordered = sorted(values)
        location = (len(ordered)-1)*probability
        index = math.floor(location)
        fraction = location-index
        return ordered[index] + fraction*(ordered[min(index+1, len(ordered)-1)]-ordered[index])

    def middle(values):
        ordered = sorted(values)
        index = len(ordered)//2
        return ordered[index] if len(ordered) % 2 else (ordered[index-1]+ordered[index])/2

    total_wait, busy, down = sum(waits), sum(busy_values), sum(down_values)
    gross = horizon*len(resources)
    available = gross-down
    observed_makespan = max(completions)-min(fact["arrival"] for fact in facts.values())
    if observed_makespan <= 0:
        raise AuditError("observed makespan is not positive")
    scalar = {
        **counters, "event_count": len(events), "total_trucks": len(facts),
        "completed_trucks": len(complete_system), "remaining_trucks": len(censored_system),
        "throughput": len(complete_system), "throughput_per_hour": len(complete_system)/(horizon/60),
        "horizon_minutes": int(horizon), "hard_constraint_violations": 0,
        "mean_wait_minutes": total_wait/len(waits), "p50_wait_minutes": middle(waits),
        "p95_wait_minutes": sorted(waits)[math.ceil(.95*len(waits))-1],
        "iqr_wait_minutes": percentile(waits, .75)-percentile(waits, .25),
        "total_wait_minutes": total_wait, "censored_wait_minutes": sum(censored_waits),
        "document_hold_minutes": sum(holds), "observed_makespan_minutes": observed_makespan,
        "median_system_time_minutes": middle(complete_system), "mean_system_time_minutes": sum(complete_system)/len(complete_system),
        "iqr_system_time_minutes": percentile(complete_system, .75)-percentile(complete_system, .25),
        "observed_system_time_minutes": sum(
            (horizon if facts[key]["departure"] is None else facts[key]["departure"])-facts[key]["arrival"]
            for key in sorted(facts)
        ),
        "censored_system_time_minutes": sum(censored_system), "censored_system_trucks": len(censored_system),
        "completed_system_trucks": len(complete_system), "resource_busy_minutes": busy,
        "resource_down_minutes": down, "resource_available_minutes": available,
        "resource_idle_minutes": available-busy, "resource_gross_minutes": gross,
        "gross_utilization": busy/gross, "net_utilization": busy/available,
        "net_idle_fraction": (available-busy)/available, "gross_idle_fraction": (available-busy)/gross,
        "fifo_break_rate": counters["fifo_break_count"]/counters["decision_count"],
        "mean_queue_displacement": sum(comparison_displacements)/counters["queue_comparison_count"],
        "replanning_frequency_per_hour": counters["replanning_count"]/(horizon/60),
        "co2_estimated_kg": total_wait/60*1.0*.8*10.18,
        "co2_sensitivity_low_kg": total_wait/60*1.0*.5*10.18,
        "co2_sensitivity_high_kg": total_wait/60*1.0*1.0*10.18,
    }
    # No field is defaulted from the producer's schema: an unimplemented field
    # causes the DTO's exact-coverage validation to fail.
    for name, value in scalar.items():
        if isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise AuditError(f"independently derived metric is invalid: {name}")
    scalar = {name: value if name in INTEGER_METRIC_FIELDS else round(float(value), 12) for name, value in scalar.items()}
    return MetricRow(_sha256(details.log_path), scalar, resource_rows, truck_rows, METRIC_DEFINITIONS)


def _validate_a2_manifest(manifest: Mapping[str, Any]) -> bool:
    """Validate the explicit automated/human A2 status contract."""

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
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 4:
        raise AuditError("run manifest schema_version must be 4")
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
        for line_number, (line, event) in enumerate(zip(details.lines, details.events), start=1):
            for field in _INPUT_IDENTITY_FIELDS:
                if line.get(field) != row[field]:
                    raise AuditError(f"log input provenance mismatch: {log_name} line={line_number} field={field}")
            if event.kind == "RUN_STARTED":
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
                    recommendation, event.time, truck_facts, observed_resources, resource_statuses,
                ):
                    raise AuditError(f"A2 decision observation disagrees with events: {log_name} line={line_number}")
            elif event.kind == "TRUCK_ARRIVED":
                truck_facts[event.payload["truck_id"]] = {
                    "arrival_time": event.payload["arrival_time"], "cargo_type": event.payload["cargo_type"],
                    "stage_entry_time": event.time,
                }
            elif event.kind in {"DOCUMENT_RELEASED", "SERVICE_STARTED", "SERVICE_COMPLETED"}:
                truck_facts[event.payload["truck_id"]]["stage_entry_time"] = event.time
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
        try:
            calculated = _derived_log_metrics(details)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise AuditError(f"persisted metrics cannot be independently reconstructed: {log_name}") from exc
        expected_metrics_file = f"metrics/{log_name.removesuffix('.jsonl')}.json"
        if row["metrics_file"] != expected_metrics_file:
            raise AuditError(f"metrics artifact path mismatch: {log_name}")
        metrics_path = bundle.run_dir / expected_metrics_file
        if metrics_path.resolve().parent != (bundle.run_dir / "metrics").resolve():
            raise AuditError(f"metrics artifact escapes run directory: {log_name}")
        if _sha256(metrics_path) != row["metrics_sha256"]:
            raise AuditError(f"metrics artifact SHA-256 mismatch: {log_name}")
        try:
            observed_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            # Canonical JSON distinguishes booleans from numeric measurements
            # and checks the complete scalar/detail/definition contract.
            if _canonical_json(observed_metrics) != _canonical_json(calculated.to_dict()):
                raise AuditError(f"metrics artifact does not reconcile with independently reconstructed log: {log_name}")
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise AuditError(f"metrics artifact is not a valid complete observation: {log_name}") from exc
        for metric, value in calculated.scalars.items():
            if row[metric] != value:
                raise AuditError(
                    f"persisted metric {metric} does not reconcile with independently reconstructed log: "
                    f"{log_name} expected={value} observed={row[metric]}"
                )
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
