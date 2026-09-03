"""Canonical stochastic-input planning, generation and freezing.

The dataset boundary is deliberately separate from policy execution.  A
``FrozenInstance`` contains every draw needed by a day, while
``plan_synthetic_dataset`` only enumerates the factorial and never samples or
writes.  Generation writes the five scientific payloads first, then derives a
cycle-free manifest/checksum/FREEZE chain from their exact bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from typing import Any, Iterable, Mapping

from .config import (
    ExperimentConfig,
    ScenarioConfig,
    canonical_bytes,
    config_as_dict,
    config_hash,
    crn_digest,
    crn_seed,
    factorial_scenarios,
    validate_confirmatory_config,
)
from .domain import (
    FrozenDataset,
    FrozenInstance,
    FrozenResource,
    FrozenServiceTime,
    FrozenTruck,
    canonical_allowed_cargo_types,
)
from .face_validation import FaceValidationReport, validate_face_validation_receipt
from .manifest import (
    canonical_checksum_bytes,
    canonical_file_hash,
    create_run_directory,
    dataset_root_hash,
    write_manifest,
)


class DatasetContractError(ValueError):
    """Raised when a dataset plan, payload or freeze is invalid."""


class FaceValidationError(DatasetContractError):
    """Raised before any namespace is created without approved face evidence."""


class GenerationRejectedError(DatasetContractError):
    """Raised when a candidate is rejected; callers must start a new action."""


@dataclass(frozen=True, slots=True)
class DatasetPlan:
    """Pure cardinality/ordering plan for the complete synthetic dataset."""

    scenarios: tuple[ScenarioConfig, ...]
    seeds: tuple[int, ...]
    policies: tuple[str, ...]
    scenario_indices: tuple[int, ...]
    instance_ids: tuple[str, ...]
    policy_day_keys: tuple[tuple[int, int, str], ...]

    @property
    def scenario_count(self) -> int:
        return len(self.scenarios)

    @property
    def seed_count(self) -> int:
        return len(self.seeds)

    @property
    def instance_count(self) -> int:
        return len(self.instance_ids)

    @property
    def policy_day_count(self) -> int:
        return len(self.policy_day_keys)

    @property
    def headers(self) -> tuple[ScenarioConfig, ...]:
        return self.scenarios

    @property
    def instance_count_per_scenario(self) -> int:
        return self.seed_count

    @property
    def ordered_instance_headers(self) -> tuple[Mapping[str, Any], ...]:
        """Return detached, lightweight headers in canonical plan order."""

        return tuple(
            {
                "instance_id": _instance_id(scenario.scenario_index, seed),
                "scenario_index": scenario.scenario_index,
                "scenario_id": scenario.scenario_id,
                "seed": seed,
            }
            for scenario in self.scenarios
            for seed in self.seeds
        )


@dataclass(frozen=True, slots=True)
class GenerationPlanReceipt:
    """Pure cardinality receipt; it never publishes or loads a dataset."""

    scenario_count: int
    instance_count: int
    policy_day_count: int
    ordered_instance_ids: tuple[str, ...]


def validate_generation_headers(
    headers: Iterable[Mapping[str, Any]],
    expected_plan: DatasetPlan,
) -> GenerationPlanReceipt:
    """Validate only lightweight generation headers against the pure plan."""

    if not isinstance(expected_plan, DatasetPlan):
        raise TypeError("expected_plan must be a DatasetPlan")
    observed = tuple(headers)
    expected = expected_plan.ordered_instance_headers
    if len(observed) != len(expected):
        raise DatasetContractError(
            f"generation headers must contain exactly {len(expected):,} instances"
        )
    observed_ids: list[str] = []
    for ordinal, (header, expected_header) in enumerate(zip(observed, expected)):
        if not isinstance(header, Mapping):
            raise DatasetContractError(f"generation header {ordinal} must be an object")
        if set(header) != set(expected_header):
            raise DatasetContractError(
                f"generation header {ordinal} schema diverges from canonical header"
            )
        if dict(header) != dict(expected_header):
            raise DatasetContractError(
                f"generation header {ordinal} order or identity diverges from canonical plan"
            )
        observed_ids.append(str(header["instance_id"]))
    return GenerationPlanReceipt(
        scenario_count=expected_plan.scenario_count,
        instance_count=expected_plan.instance_count,
        policy_day_count=expected_plan.policy_day_count,
        ordered_instance_ids=tuple(observed_ids),
    )


_PAYLOAD_NAMES: tuple[str, ...] = (
    "scenario_index.parquet",
    "trucks.parquet",
    "service_times.parquet",
    "disruptions.jsonl",
    "rejection_log.jsonl",
)
_REQUIRED_MANIFEST_FIELDS: frozenset[str] = frozenset(
    {
        "dataset_id",
        "phase",
        "protocol_version",
        "config_hash",
        "scenario_index_hash",
        "scenario_count",
        "seed_count",
        "instance_count",
        "cardinalities",
        "crn_version",
        "generator_version",
        "parameters",
        "frozen_parameters",
        "freeze_status",
        "created_at_utc",
        "git_commit",
        "checkout_clean",
        "runtime",
        "payload_hashes",
        "instance_hashes",
        "rejection_count",
        "policy_days_executed",
        "resample_provenance",
        "materialization_mode",
    }
)
_PARQUET_SCHEMA_NAMES: dict[str, tuple[str, ...]] = {
    "scenario_index.parquet": (
        "scenario_index", "scenario_id", "N", "hopper_count", "scale_count",
        "regime", "rho", "stratum", "protocol_version", "config_hash", "generator_version",
    ),
    "trucks.parquet": (
        "instance_id", "scenario_index", "scenario_id", "seed", "truck_id", "arrival_minute",
        "cargo_type", "priority", "document_status", "stage", "eligible_resources", "truck_record_hash",
    ),
    "service_times.parquet": (
        "instance_id", "scenario_index", "scenario_id", "seed", "truck_id", "operation",
        "duration_min", "source_a", "source_mode", "source_b", "draw_key", "crn_version",
        "service_record_hash",
    ),
}
_JSONL_SCHEMA_NAMES: dict[str, tuple[str, ...]] = {
    "disruptions.jsonl": (
        "instance_id", "scenario_index", "scenario_id", "seed", "time", "event_rank",
        "resource_id", "truck_id", "sequence", "event_type", "cause", "operation",
        "duration_min", "return_time", "payload_hash",
    ),
    "rejection_log.jsonl": (
        "dataset_id", "candidate_ordinal", "scenario_index", "instance_id", "seed",
        "generation_attempt", "reason_code", "validator", "observed", "expected",
        "candidate_hash", "automatic_resample_status", "next_action", "timestamp",
    ),
}
_OPERATIONS: tuple[str, ...] = ("gate", "scale_in", "unload", "scale_out")
_RESOURCE_KINDS: tuple[tuple[str, str], ...] = (("gate-1", "gate"),)
_DISRUPTION_EVENT_TYPES: frozenset[str] = frozenset(
    {"document_release", "resource_failure", "priority_change", "rain_start", "rain_end"}
)
_EVENT_RANK_NAMES: frozenset[str] = frozenset(
    {
        "service_completion", "resource_recovery", "rain_end", "resource_failure",
        "rain_start", "document_release", "priority_change", "arrival",
    }
)


def _as_utc(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("now_utc must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime):
        raise TypeError("now_utc must be datetime, ISO-8601 string, or None")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now_utc must include an explicit timezone")
    return value.astimezone(timezone.utc)


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_value(value: Any) -> str:
    return _digest_bytes(canonical_bytes(value))


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]], kind: str | None = None) -> bytes:
    lines: list[str] = []
    expected = _JSONL_SCHEMA_NAMES.get(f"{kind}.jsonl") if kind is not None else None
    for ordinal, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError("JSONL rows must be mappings")
        if expected is not None:
            if set(row) != set(expected):
                raise DatasetContractError(f"{kind} row {ordinal} does not match exact schema")
            if any(row[name] is None for name in expected):
                raise DatasetContractError(f"{kind} row {ordinal} contains a null field")
        lines.append(
            json.dumps(
                dict(row),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    if not lines:
        return b""
    return ("\n".join(lines) + "\n").encode("utf-8")


def _scenario_header(scenario: ScenarioConfig) -> dict[str, Any]:
    return {
        "scenario_index": scenario.scenario_index,
        "scenario_id": scenario.scenario_id,
        "N": scenario.N,
        "hopper_count": scenario.m,
        "scale_count": scenario.b,
        "regime": scenario.regime,
        "rho": scenario.rho,
        "stratum": scenario.stratum,
    }


def _instance_id(scenario_index: int, seed: int) -> str:
    return f"s{scenario_index:02d}-seed{seed:03d}"


def canonical_payload_schemas() -> dict[str, tuple[str, ...]]:
    """Return the exact public Parquet column contract."""

    return dict(_PARQUET_SCHEMA_NAMES)


def plan_synthetic_dataset(config: ExperimentConfig) -> DatasetPlan:
    """Return the complete ordered plan without sampling or filesystem writes."""

    validate_confirmatory_config(config)
    scenarios = factorial_scenarios(config)
    scenario_indices = tuple(scenario.scenario_index for scenario in scenarios)
    instance_ids = tuple(
        _instance_id(scenario.scenario_index, seed)
        for scenario in scenarios
        for seed in config.seeds
    )
    policy_day_keys = tuple(
        (scenario.scenario_index, seed, policy)
        for scenario in scenarios
        for seed in config.seeds
        for policy in config.policies
    )
    return DatasetPlan(
        scenarios=scenarios,
        seeds=tuple(config.seeds),
        policies=tuple(config.policies),
        scenario_indices=scenario_indices,
        instance_ids=instance_ids,
        policy_day_keys=policy_day_keys,
    )


def _rng(config: ExperimentConfig, scenario_index: int, seed: int, attempt: int, entity: str, operation: str):
    """Create a deterministic NumPy generator from the complete CRN tuple."""

    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover - environment dependent
        raise DatasetContractError("numpy is required for synthetic generation") from exc
    return np.random.default_rng(
        crn_seed(config.crn_version, scenario_index, seed, attempt, entity, operation)
    )


def _triangular(
    config: ExperimentConfig,
    scenario_index: int,
    seed: int,
    attempt: int,
    entity: str,
    operation: str,
    distribution: tuple[float, float, float],
) -> tuple[float, str]:
    key = crn_digest(config.crn_version, scenario_index, seed, attempt, entity, operation)
    value = _rng(config, scenario_index, seed, attempt, entity, operation).triangular(*distribution)
    return float(value), key


def _draw_uniform(config: ExperimentConfig, scenario_index: int, seed: int, attempt: int, entity: str, operation: str) -> float:
    return float(_rng(config, scenario_index, seed, attempt, entity, operation).random())


def _resource_records(scenario: ScenarioConfig) -> tuple[FrozenResource, ...]:
    values: list[FrozenResource] = [
        FrozenResource("gate-1", "gate", canonical_allowed_cargo_types("gate-1", "gate")),
    ]
    values.extend(
        FrozenResource(
            f"scale-{index}",
            "scale",
            canonical_allowed_cargo_types(f"scale-{index}", "scale"),
        )
        for index in range(1, scenario.b + 1)
    )
    values.extend(
        FrozenResource(
            f"hopper-{index}",
            "hopper",
            canonical_allowed_cargo_types(f"hopper-{index}", "hopper"),
        )
        for index in range(1, scenario.m + 1)
    )
    return tuple(values)


def _build_instance(
    config: ExperimentConfig,
    scenario: ScenarioConfig,
    seed: int,
    generation_attempt: int = 0,
) -> FrozenInstance:
    """Materialize one complete instance, including all exogenous draws."""

    instance_id = _instance_id(scenario.scenario_index, seed)
    block_weights = (
        config.peak_arrival_weights
        if scenario.regime == "peak"
        else tuple(block[2] for block in config.arrival_blocks)
    )
    block_masses = [weight * (end - start) for (start, end, _), weight in zip(config.arrival_blocks, block_weights)]
    mass_total = sum(block_masses)
    trucks_data: list[dict[str, Any]] = []
    for ordinal in range(1, scenario.N + 1):
        truck_id = f"T-{ordinal:03d}"
        block_rng = _rng(config, scenario.scenario_index, seed, generation_attempt, truck_id, "arrival_block")
        block_index = int(block_rng.choice(len(config.arrival_blocks), p=[mass / mass_total for mass in block_masses]))
        start, end, _weight = config.arrival_blocks[block_index]
        offset = _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, truck_id, "arrival_offset")
        arrival = min(float(config.horizon_minutes), float(start) + offset * float(end - start))
        cargo = "soy" if _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, truck_id, "cargo") < 0.5 else "corn"
        priority_draw = _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, truck_id, "priority")
        if priority_draw < config.priority_probabilities["p2"]:
            priority = 2
        elif priority_draw < config.priority_probabilities["p2"] + config.priority_probabilities["p1"]:
            priority = 1
        else:
            priority = 0
        blocked = _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, truck_id, "document") < config.document_block_probability
        trucks_data.append(
            {
                "instance_id": instance_id,
                "scenario_index": scenario.scenario_index,
                "scenario_id": scenario.scenario_id,
                "seed": seed,
                "truck_id": truck_id,
                "arrival_minute": arrival,
                "cargo_type": cargo,
                "priority": priority,
                "document_status": "BLOCKED" if blocked else "CLEAR",
                "stage": "gate",
                "eligible_resources": ["gate-1"],
                "generation_attempt": generation_attempt,
            }
        )
    trucks_data.sort(key=lambda value: (value["arrival_minute"], value["truck_id"]))
    trucks = tuple(
        FrozenTruck.from_dict({**item, "truck_record_hash": item.get("truck_record_hash")})
        for item in trucks_data
    )

    service_values: list[FrozenServiceTime] = []
    for truck in trucks:
        for operation in _OPERATIONS:
            distribution = tuple(config.service_distributions[operation])
            duration, draw_key = _triangular(
                config,
                scenario.scenario_index,
                seed,
                generation_attempt,
                truck.truck_id,
                operation,
                distribution,
            )
            service_values.append(
                FrozenServiceTime(
                    instance_id=instance_id,
                    scenario_index=scenario.scenario_index,
                    scenario_id=scenario.scenario_id,
                    seed=seed,
                    truck_id=truck.truck_id,
                    operation=operation,
                    duration_min=duration,
                    source_a=distribution[0],
                    source_mode=distribution[1],
                    source_b=distribution[2],
                    draw_key=draw_key,
                    crn_version=config.crn_version,
                    generation_attempt=generation_attempt,
                )
            )

    disruptions: list[dict[str, Any]] = []
    sequence = 0

    def add_disruption(event: dict[str, Any]) -> None:
        nonlocal sequence
        sequence += 1
        payload = dict(event)
        payload.setdefault("instance_id", instance_id)
        payload.setdefault("scenario_index", scenario.scenario_index)
        payload.setdefault("scenario_id", scenario.scenario_id)
        payload.setdefault("seed", seed)
        if "recovery_at" in payload:
            payload["return_time"] = payload.pop("recovery_at")
        payload.setdefault("return_time", 0.0)
        payload.setdefault("duration_min", 0.0)
        payload.setdefault("resource_id", "")
        payload.setdefault("truck_id", "")
        payload.setdefault("operation", "")
        payload["sequence"] = sequence
        payload["payload_hash"] = _digest_value(payload)
        disruptions.append(payload)

    for truck in trucks:
        if truck.document_status == "BLOCKED":
            delay, _draw_key = _triangular(
                config,
                scenario.scenario_index,
                seed,
                generation_attempt,
                truck.truck_id,
                "document_release",
                tuple(config.document_release_distribution),
            )
            add_disruption(
                {
                    "instance_id": instance_id,
                    "time": min(float(config.horizon_minutes), truck.arrival_minute + delay),
                    "event_type": "document_release",
                    "event_rank": config.event_ranks["document_release"],
                    "resource_id": "",
                    "truck_id": truck.truck_id,
                    "cause": "document",
                    "operation": "gate",
                    "duration_min": delay,
                }
            )

    if scenario.regime == "critical_failure":
        resource_id = "hopper-1" if 36 * scenario.m <= 72 * scenario.b else "scale-1"
        start = config.failure_start_window[0] + _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, "yard", "critical_failure_start") * (config.failure_start_window[1] - config.failure_start_window[0])
        duration, _draw_key = _triangular(
            config,
            scenario.scenario_index,
            seed,
            generation_attempt,
            "yard",
            "critical_failure_duration",
            tuple(config.failure_duration_distribution),
        )
        add_disruption(
            {
                "instance_id": instance_id,
                "time": float(start),
                "event_type": "resource_failure",
                "event_rank": config.event_ranks["resource_failure"],
                "resource_id": resource_id,
                "truck_id": "",
                "cause": "critical_failure",
                "operation": "",
                "duration_min": duration,
                "recovery_at": float(start + duration),
            }
        )
    elif _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, "yard", "base_failure") < config.base_failure_probability:
        resources = [resource.resource_id for resource in _resource_records(scenario)]
        resource_index = int(_rng(config, scenario.scenario_index, seed, generation_attempt, "yard", "base_failure_resource").integers(0, len(resources)))
        resource_id = resources[resource_index]
        start = config.failure_start_window[0] + _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, "yard", "failure_start") * (config.failure_start_window[1] - config.failure_start_window[0])
        duration, _draw_key = _triangular(
            config,
            scenario.scenario_index,
            seed,
            generation_attempt,
            "yard",
            "failure_duration",
            tuple(config.failure_duration_distribution),
        )
        add_disruption(
            {
                "instance_id": instance_id,
                "time": float(start),
                "event_type": "resource_failure",
                "event_rank": config.event_ranks["resource_failure"],
                "resource_id": resource_id,
                "truck_id": "",
                "cause": "base_failure",
                "operation": "",
                "duration_min": duration,
                "recovery_at": float(start + duration),
            }
        )

    if scenario.regime == "priority_shift":
        shift_time = config.priority_shift_window[0] + _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, "yard", "priority_shift_time") * (config.priority_shift_window[1] - config.priority_shift_window[0])
        candidates = [truck for truck in trucks if truck.arrival_minute >= shift_time]
        candidates.sort(key=lambda truck: (truck.arrival_minute, truck.truck_id))
        selected = candidates[: math.ceil(config.priority_shift_fraction * scenario.N)]
        for truck in selected:
            add_disruption(
                {
                    "instance_id": instance_id,
                    "time": float(shift_time),
                    "event_type": "priority_change",
                    "event_rank": config.event_ranks["priority_change"],
                    "resource_id": "",
                    "truck_id": truck.truck_id,
                    "cause": "priority_shift",
                    "operation": "",
                }
            )

    if scenario.m >= 2:
        rain_blocks = [
            index
            for index in range(24)
            if _draw_uniform(config, scenario.scenario_index, seed, generation_attempt, "hopper-1", f"rain_block_{index}") < config.rain_probability
        ]
        if rain_blocks:
            start_index = rain_blocks[0]
            previous = rain_blocks[0]
            for index in rain_blocks[1:] + [None]:
                if index is not None and index == previous + 1:
                    previous = index
                    continue
                start = start_index * config.rain_block_minutes
                end = (previous + 1) * config.rain_block_minutes
                add_disruption(
                    {
                        "instance_id": instance_id,
                        "time": float(start),
                        "event_type": "rain_start",
                        "event_rank": config.event_ranks["rain_start"],
                        "resource_id": "hopper-1",
                        "truck_id": "",
                        "cause": "rain",
                        "operation": "",
                        "duration_min": float(end - start),
                        "recovery_at": float(end),
                    }
                )
                add_disruption(
                    {
                        "instance_id": instance_id,
                        "time": float(end),
                        "event_type": "rain_end",
                        "event_rank": config.event_ranks["rain_end"],
                        "resource_id": "hopper-1",
                        "truck_id": "",
                        "cause": "rain",
                        "operation": "",
                        "duration_min": 0.0,
                    }
                )
                if index is not None:
                    start_index = index
                    previous = index

    disruptions.sort(key=lambda item: (
        item["time"],
        item["event_rank"],
        item.get("resource_id", ""),
        item.get("truck_id", ""),
        item["sequence"],
    ))
    return FrozenInstance(
        instance_id=instance_id,
        scenario_index=scenario.scenario_index,
        scenario_id=scenario.scenario_id,
        seed=seed,
        generation_attempt=generation_attempt,
        trucks=trucks,
        resources=_resource_records(scenario),
        service_times=tuple(service_values),
        disruptions=tuple(disruptions),
    )


class _PayloadWriter:
    """Collect deterministic rows for one complete production freeze."""

    def __init__(self) -> None:
        self.instance_rows: list[dict[str, Any]] = []
        self.instance_hashes: list[dict[str, str]] = []
        self.truck_rows: list[dict[str, Any]] = []
        self.service_rows: list[dict[str, Any]] = []
        self.disruption_rows: list[dict[str, Any]] = []
        self.rejection_rows: list[dict[str, Any]] = []
        self.current_instance: FrozenInstance | None = None

    def write_instance(self, instance: FrozenInstance) -> None:
        self.instance_rows.append(
            {
                "instance_id": instance.instance_id,
                "scenario_index": instance.scenario_index,
                "scenario_id": instance.scenario_id,
                "seed": instance.seed,
                "generation_attempt": instance.generation_attempt,
            }
        )
        self.instance_hashes.append(
            {"instance_id": instance.instance_id, "instance_hash": instance.instance_hash or ""}
        )
        self.truck_rows.extend(truck.to_dict() for truck in instance.trucks)
        self.service_rows.extend(service.to_dict() for service in instance.service_times)
        self.disruption_rows.extend(dict(item) for item in instance.disruptions)


def _materialize_production_header(header: FrozenInstance, writer: _PayloadWriter) -> None:
    """Materialize one complete immutable instance into the payload writer."""

    if writer.current_instance is not header:
        raise DatasetContractError("materializer received a different instance header")
    writer.write_instance(header)


def _validate_candidate(candidate: FrozenInstance) -> bool:
    """Private deterministic seam reserved for Task 3 rejection tests."""

    if not isinstance(candidate, FrozenInstance):
        raise TypeError("candidate must be a FrozenInstance")
    return True



def _write_parquet(path: Path, rows: list[Mapping[str, Any]], kind: str) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - environment dependent
        raise DatasetContractError(f"pyarrow is required to write {kind}") from exc
    required = {
        "scenario_index": pa.schema(
            [
                pa.field("scenario_index", pa.int64(), nullable=False),
                pa.field("scenario_id", pa.string(), nullable=False),
                pa.field("N", pa.int64(), nullable=False),
                pa.field("hopper_count", pa.int64(), nullable=False),
                pa.field("scale_count", pa.int64(), nullable=False),
                pa.field("regime", pa.string(), nullable=False),
                pa.field("rho", pa.float64(), nullable=False),
                pa.field("stratum", pa.string(), nullable=False),
                pa.field("protocol_version", pa.string(), nullable=False),
                pa.field("config_hash", pa.string(), nullable=False),
                pa.field("generator_version", pa.string(), nullable=False),
            ]
        ),
        "trucks": pa.schema(
            [
                pa.field("instance_id", pa.string(), nullable=False),
                pa.field("scenario_index", pa.int64(), nullable=False),
                pa.field("scenario_id", pa.string(), nullable=False),
                pa.field("seed", pa.int64(), nullable=False),
                pa.field("truck_id", pa.string(), nullable=False),
                pa.field("arrival_minute", pa.float64(), nullable=False),
                pa.field("cargo_type", pa.string(), nullable=False),
                pa.field("priority", pa.int64(), nullable=False),
                pa.field("document_status", pa.string(), nullable=False),
                pa.field("stage", pa.string(), nullable=False),
                pa.field("eligible_resources", pa.list_(pa.string()), nullable=False),
                pa.field("truck_record_hash", pa.string(), nullable=False),
            ]
        ),
        "service_times": pa.schema(
            [
                pa.field("instance_id", pa.string(), nullable=False),
                pa.field("scenario_index", pa.int64(), nullable=False),
                pa.field("scenario_id", pa.string(), nullable=False),
                pa.field("seed", pa.int64(), nullable=False),
                pa.field("truck_id", pa.string(), nullable=False),
                pa.field("operation", pa.string(), nullable=False),
                pa.field("duration_min", pa.float64(), nullable=False),
                pa.field("source_a", pa.float64(), nullable=False),
                pa.field("source_mode", pa.float64(), nullable=False),
                pa.field("source_b", pa.float64(), nullable=False),
                pa.field("draw_key", pa.string(), nullable=False),
                pa.field("crn_version", pa.string(), nullable=False),
                pa.field("service_record_hash", pa.string(), nullable=False),
            ]
        ),
    }
    schema = required[kind]
    if rows:
        for ordinal, row in enumerate(rows):
            if set(row) != set(schema.names):
                raise DatasetContractError(
                    f"{kind} row {ordinal} does not match exact schema"
                )
            if any(row[name] is None for name in schema.names):
                raise DatasetContractError(f"{kind} row {ordinal} contains a null field")
        table = pa.Table.from_pylist([dict(row) for row in rows], schema=schema)
    else:
        table = pa.Table.from_arrays([pa.array([], type=field.type) for field in schema], schema=schema)
    pq.write_table(
        table,
        path,
        compression="NONE",
        use_dictionary=False,
        write_statistics=False,
        data_page_version="1.0",
        version="2.6",
    )


def _git_inventory() -> tuple[str, bool | None]:
    root = Path(__file__).resolve().parents[3]
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise DatasetContractError("git inventory failed during dataset manifest") from exc
    if not commit:
        raise DatasetContractError("git inventory returned an empty commit")
    return commit, not bool(status.strip())


def _prepare_destination(path: str | Path) -> Path:
    destination = Path(path)
    if destination.exists():
        raise FileExistsError(f"dataset destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _create_staging_directory(destination: Path) -> Path:
    try:
        return Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.staging-",
                dir=str(destination.parent),
            )
        )
    except OSError as exc:
        raise DatasetContractError(
            f"could not create sibling staging directory for {destination}"
        ) from exc


def _validate_approved_face(face_report: Any, config: ExperimentConfig) -> FaceValidationReport:
    if not isinstance(face_report, FaceValidationReport):
        raise FaceValidationError(
            "generate_synthetic_dataset requires a validated FaceValidationReport"
        )
    receipt_path = face_report.receipt_path
    if not isinstance(receipt_path, Path) or not receipt_path.is_file():
        raise FaceValidationError(
            "generate_synthetic_dataset requires a FaceValidationReport with an existing receipt_path"
        )
    pdf_path = Path(__file__).resolve().parents[3] / "main.pdf"
    revalidated = validate_face_validation_receipt(receipt_path, config, pdf_path)
    if revalidated != face_report:
        raise FaceValidationError(
            "FaceValidationReport does not exactly match revalidated receipt evidence"
        )
    if face_report.status != "APPROVED":
        raise FaceValidationError(
            f"generate_synthetic_dataset blocked before namespace: FACE_VALIDATION={face_report.status}; {face_report.cause}"
        )
    if face_report.protocol_version != config.protocol_version:
        raise FaceValidationError("approved face report protocol_version does not match configuration")
    if face_report.config_hash != config_hash(config):
        raise FaceValidationError("approved face report config_hash does not match configuration")
    for name in ("source_document", "source_sha256", "rubric_path", "rubric_version", "rubric_sha256"):
        value = getattr(face_report, name, None)
        if not isinstance(value, str) or not value.strip():
            raise FaceValidationError(f"approved face report is missing {name}")
    for name in ("source_sha256", "rubric_sha256"):
        value = getattr(face_report, name)
        if len(value) != 64 or any(character not in "0123456789abcdefABCDEF" for character in value):
            raise FaceValidationError(f"approved face report {name} is not a SHA-256 digest")
    return face_report


def _build_manifest(
    config: ExperimentConfig,
    plan: DatasetPlan,
    destination: Path,
    now_utc: datetime,
    generator_version: str,
    payload_hashes: tuple[tuple[str, str], ...],
    rejection_count: int,
    *,
    instance_hashes: list[Mapping[str, Any]],
    cardinalities: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    commit, checkout_clean = _git_inventory()
    payload_rows = [{"path": name, "sha256": digest} for name, digest in payload_hashes]
    scenario_hash = dict(payload_hashes)["scenario_index.parquet"]
    runtime = {
        "python_version": platform.python_version(),
        "operating_system": platform.platform(),
        "cpu": {"logical_count": os.cpu_count()},
        "memory": {"total_bytes": None},
        "gpu": {"status": "inventory_only", "devices": []},
    }
    try:
        import psutil

        runtime["memory"] = {"total_bytes": int(psutil.virtual_memory().total)}
    except Exception:
        runtime["memory"] = {"total_bytes": None}
    counts = {
        "scenario_index": plan.scenario_count,
        "instances": plan.instance_count,
        "trucks": 0,
        "service_times": 0,
        "disruptions": 0,
        "rejection_log": rejection_count,
    }
    if cardinalities is not None:
        for name in ("scenario_index", "instances", "trucks", "service_times", "disruptions", "rejection_log"):
            value = cardinalities.get(name, counts[name])
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DatasetContractError(f"manifest cardinality {name} must be a non-negative integer")
            counts[name] = value
    manifest: dict[str, Any] = {
        "dataset_id": destination.name,
        "phase": "synthetic",
        "protocol_version": config.protocol_version,
        "config_hash": config_hash(config),
        "scenario_index_hash": scenario_hash,
        "scenario_count": plan.scenario_count,
        "seed_count": plan.seed_count,
        "instance_count": plan.instance_count,
        "cardinalities": counts,
        "crn_version": config.crn_version,
        "generator_version": generator_version,
        "parameters": config_as_dict(config),
        "frozen_parameters": {
            "horizon_minutes": config.horizon_minutes,
            "buffer_capacity": config.buffer_capacity,
            "ordinary_window": config.ordinary_window,
            "priority_thresholds": list(config.priority_thresholds),
            "service_distributions": config_as_dict(config)["service_distributions"],
        },
        "freeze_status": "FROZEN",
        "created_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": commit,
        "checkout_clean": checkout_clean,
        "runtime": runtime,
        "payload_hashes": payload_rows,
        "rejection_count": rejection_count,
        "policy_days_executed": False,
        "resample_provenance": None,
        "materialization_mode": "full",
        "instance_hashes": [dict(item) for item in instance_hashes],
    }
    return manifest


def _finalize_freeze(destination: Path, manifest: Mapping[str, Any]) -> FrozenDataset:
    metadata = (destination / "manifest.json", destination / "checksums.sha256", destination / "FREEZE.json")
    existing = [path for path in metadata if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing freeze metadata: "
            + ", ".join(path.name for path in existing)
        )
    payload_entries = []
    for name in _PAYLOAD_NAMES:
        payload_entries.append((name, canonical_file_hash(destination / name)))
    checksum_bytes = canonical_checksum_bytes(payload_entries)
    checksums_path = destination / "checksums.sha256"
    checksums_path.write_bytes(checksum_bytes)
    manifest_path = destination / "manifest.json"
    write_manifest(manifest_path, manifest)
    manifest_hash = canonical_file_hash(manifest_path)
    checksums_hash = _digest_bytes(checksum_bytes)
    root_hash = dataset_root_hash(manifest_hash, checksums_hash)
    freeze_payload = {
        "manifest_hash": manifest_hash,
        "checksums_hash": checksums_hash,
        "dataset_root_hash": root_hash,
    }
    (destination / "FREEZE.json").write_bytes(canonical_bytes(freeze_payload))
    # Loading performs the full independent chain/cardinality check.  During
    # generation this path is the sibling staging directory, while the
    # manifest already names the eventual published destination; carry that
    # explicit identity through the private staging boundary.
    return _load_frozen_dataset(
        destination,
        published_dataset_id=str(manifest.get("dataset_id", "")),
    )


def generate_synthetic_dataset(
    config: ExperimentConfig,
    face_report: FaceValidationReport,
    dataset_root: str | Path,
    *,
    now_utc: datetime | str | None = None,
    generator_version: str,
) -> FrozenDataset:
    """Materialize and freeze the complete 3,600-instance synthetic dataset."""

    validate_confirmatory_config(config)
    _validate_approved_face(face_report, config)
    if not isinstance(generator_version, str) or not generator_version.strip():
        raise ValueError("generator_version must be a non-empty string")
    plan = plan_synthetic_dataset(config)
    timestamp = _as_utc(now_utc)
    destination = _prepare_destination(dataset_root)
    staging = _create_staging_directory(destination)
    try:
        writer = _PayloadWriter()
        for scenario in plan.scenarios:
            for seed in plan.seeds:
                instance = _build_instance(config, scenario, seed)
                if not _validate_candidate(instance):
                    raise GenerationRejectedError(
                        f"generation rejected instance_id={instance.instance_id}; EXPLICIT_RESAMPLE_REQUIRED"
                    )
                writer.current_instance = instance
                _materialize_production_header(instance, writer)

        scenarios = []
        for scenario in plan.scenarios:
            row = _scenario_header(scenario)
            row.update(
                {
                    "protocol_version": config.protocol_version,
                    "config_hash": config_hash(config),
                    "generator_version": generator_version,
                }
            )
            scenarios.append(row)
        _write_parquet(staging / "scenario_index.parquet", scenarios, "scenario_index")
        _write_parquet(staging / "trucks.parquet", writer.truck_rows, "trucks")
        _write_parquet(staging / "service_times.parquet", writer.service_rows, "service_times")
        (staging / "disruptions.jsonl").write_bytes(
            _jsonl_bytes(writer.disruption_rows, "disruptions")
        )
        (staging / "rejection_log.jsonl").write_bytes(
            _jsonl_bytes(writer.rejection_rows, "rejection_log")
        )
        payload_hashes = tuple((name, canonical_file_hash(staging / name)) for name in _PAYLOAD_NAMES)
        manifest = _build_manifest(
            config,
            plan,
            destination,
            timestamp,
            generator_version,
            payload_hashes,
            len(writer.rejection_rows),
            instance_hashes=writer.instance_hashes,
            cardinalities={
                "scenario_index": len(scenarios),
                "instances": len(writer.instance_rows),
                "trucks": len(writer.truck_rows),
                "service_times": len(writer.service_rows),
                "disruptions": len(writer.disruption_rows),
                "rejection_log": len(writer.rejection_rows),
            },
        )
        _finalize_freeze(staging, manifest)
        if destination.exists():
            raise FileExistsError(f"dataset destination appeared during generation: {destination}")
        os.replace(staging, destination)
        return load_frozen_dataset(destination, expected_plan=plan)
    except Exception as exc:
        if isinstance(exc, DatasetContractError):
            raise DatasetContractError(
                f"synthetic dataset generation failed; staging retained at {staging}: {exc}"
            ) from exc
        raise DatasetContractError(
            f"synthetic dataset generation failed; staging retained at {staging}"
        ) from exc


def _load_json(path: Path, label: str) -> Any:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise DatasetContractError(f"{label} is missing: {path}") from exc
    except OSError as exc:
        raise DatasetContractError(f"{label} could not be read: {path}") from exc
    if not raw.endswith(b"\n"):
        raise DatasetContractError(f"{label} must use canonical JSON bytes")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_json_object)
    except DatasetContractError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise DatasetContractError(f"{label} is invalid JSON: {path}") from exc
    try:
        canonical = canonical_bytes(value)
    except (TypeError, ValueError) as exc:
        raise DatasetContractError(f"{label} contains non-canonical JSON values") from exc
    if raw != canonical:
        raise DatasetContractError(f"{label} is not canonical JSON")
    return value


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build JSON objects while rejecting duplicate keys at parse time."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DatasetContractError(f"JSON object contains duplicate key: {key}")
        result[key] = value
    return result


def _read_parquet(path: Path, label: str, kind: str | None = None) -> list[dict[str, Any]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - environment dependent
        raise DatasetContractError(f"pyarrow is required to read {label}") from exc
    try:
        table = pq.read_table(path)
        if kind is not None:
            expected_names = _PARQUET_SCHEMA_NAMES[f"{kind}.parquet"]
            if tuple(table.schema.names) != expected_names:
                raise DatasetContractError(
                    f"{label} schema columns must be exactly {expected_names!r}"
                )
            if any(field.nullable for field in table.schema):
                raise DatasetContractError(f"{label} schema fields must be non-nullable")
            expected_types = {
                "scenario_index": pa.int64(), "N": pa.int64(), "hopper_count": pa.int64(),
                "scale_count": pa.int64(), "seed": pa.int64(), "priority": pa.int64(),
                "rho": pa.float64(), "arrival_minute": pa.float64(), "duration_min": pa.float64(),
                "source_a": pa.float64(), "source_mode": pa.float64(), "source_b": pa.float64(),
            }
            for field in table.schema:
                expected = expected_types.get(field.name, pa.list_(pa.string()) if field.name == "eligible_resources" else pa.string())
                if field.type != expected:
                    raise DatasetContractError(
                        f"{label} field {field.name} has unexpected type {field.type}"
                    )
        return table.to_pylist()
    except DatasetContractError:
        raise
    except (OSError, ValueError, RuntimeError, pa.ArrowException) as exc:
        raise DatasetContractError(f"{label} could not be read: {path}") from exc


def _read_jsonl(path: Path, label: str, kind: str | None = None) -> list[dict[str, Any]]:
    try:
        raw_bytes = path.read_bytes()
    except FileNotFoundError as exc:
        raise DatasetContractError(f"{label} is missing: {path}") from exc
    except OSError as exc:
        raise DatasetContractError(f"{label} could not be read: {path}") from exc
    if raw_bytes == b"":
        return []
    if b"\r" in raw_bytes:
        raise DatasetContractError(f"{label} must use canonical LF bytes")
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetContractError(f"{label} is not valid UTF-8") from exc
    rows: list[dict[str, Any]] = []
    expected = _JSONL_SCHEMA_NAMES.get(f"{kind}.jsonl") if kind is not None else None
    lines = raw_bytes.split(b"\n")
    if not raw_bytes.endswith(b"\n"):
        raise DatasetContractError(f"{label} must end with one LF")
    for number, line_bytes in enumerate(lines[:-1], start=1):
        if not line_bytes:
            raise DatasetContractError(f"{label} line {number} is empty")
        try:
            line = line_bytes.decode("utf-8")
            item = json.loads(line, object_pairs_hook=_strict_json_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DatasetContractError(f"{label} line {number} is invalid JSON") from exc
        if not isinstance(item, dict):
            raise DatasetContractError(f"{label} line {number} must be an object")
        if expected is not None:
            if set(item) != set(expected) or any(item.get(name) is None for name in expected):
                raise DatasetContractError(f"{label} line {number} does not match exact schema")
        try:
            canonical_line = canonical_bytes(item)
        except (TypeError, ValueError) as exc:
            raise DatasetContractError(f"{label} line {number} contains non-canonical values") from exc
        if canonical_line != line_bytes + b"\n":
            raise DatasetContractError(f"{label} line {number} is not canonical JSON")
        rows.append(item)
    return rows


def _assert_finite_json(value: Any, label: str) -> None:
    """Reject JSON numbers that are non-finite at the load boundary."""

    if isinstance(value, float):
        if not math.isfinite(value):
            raise DatasetContractError(f"{label} contains a non-finite number")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_finite_json(item, f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_finite_json(item, f"{label}[{index}]")


def _validate_checksum_chain(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    if not path.is_dir():
        raise DatasetContractError(f"frozen dataset directory is missing: {path}")
    manifest_path = path / "manifest.json"
    checksums_path = path / "checksums.sha256"
    freeze_path = path / "FREEZE.json"
    # Check FREEZE first so a header-only or otherwise incomplete artifact is
    # rejected at the publication boundary with a causal FREEZE diagnostic.
    freeze = _load_json(freeze_path, "FREEZE.json")
    manifest = _load_json(manifest_path, "manifest")
    if not isinstance(manifest, dict):
        raise DatasetContractError("manifest root must be an object")
    _assert_finite_json(manifest, "manifest")
    _assert_finite_json(freeze, "FREEZE.json")
    missing_manifest = sorted(_REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing_manifest:
        raise DatasetContractError(
            "manifest is missing required fields: " + ", ".join(missing_manifest)
        )
    unknown_manifest = sorted(set(manifest) - _REQUIRED_MANIFEST_FIELDS)
    if unknown_manifest:
        raise DatasetContractError(
            "manifest contains unexpected fields: " + ", ".join(unknown_manifest)
        )
    if not isinstance(freeze, dict) or set(freeze) != {"manifest_hash", "checksums_hash", "dataset_root_hash"}:
        raise DatasetContractError("FREEZE.json must contain exactly three hash fields")
    try:
        checksum_bytes = checksums_path.read_bytes()
    except FileNotFoundError as exc:
        raise DatasetContractError(f"checksums.sha256 is missing: {checksums_path}") from exc
    try:
        rows = checksum_bytes.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise DatasetContractError("checksums.sha256 is not valid UTF-8") from exc
    if len(rows) != len(_PAYLOAD_NAMES):
        raise DatasetContractError("checksums.sha256 must contain exactly five payloads")
    entries: list[tuple[str, str]] = []
    for row in rows:
        fields = row.split("\t")
        if len(fields) != 2:
            raise DatasetContractError("checksums.sha256 rows must be name<TAB>sha256")
        entries.append((fields[0], fields[1]))
    try:
        if canonical_checksum_bytes(entries) != checksum_bytes:
            raise DatasetContractError("checksums.sha256 is not canonical")
    except (TypeError, ValueError) as exc:
        raise DatasetContractError("checksums.sha256 has invalid payload entries") from exc
    expected_manifest_hash = canonical_file_hash(manifest_path)
    expected_checksums_hash = _digest_bytes(checksum_bytes)
    if freeze.get("manifest_hash") != expected_manifest_hash:
        raise DatasetContractError("FREEZE manifest_hash does not match manifest bytes")
    if freeze.get("checksums_hash") != expected_checksums_hash:
        raise DatasetContractError("FREEZE checksums_hash does not match checksums bytes")
    expected_root = dataset_root_hash(expected_manifest_hash, expected_checksums_hash)
    if freeze.get("dataset_root_hash") != expected_root:
        raise DatasetContractError("FREEZE dataset_root_hash does not match manifest/checksums")
    payload_hashes = manifest.get("payload_hashes")
    expected_payload_rows = [{"path": name, "sha256": digest} for name, digest in entries]
    if payload_hashes != expected_payload_rows:
        raise DatasetContractError("manifest payload hashes do not match checksums.sha256")
    if manifest.get("scenario_index_hash") != dict(entries)["scenario_index.parquet"]:
        raise DatasetContractError(
            "manifest scenario_index_hash does not match scenario_index.parquet checksum"
        )
    if manifest.get("materialization_mode") != "full":
        raise DatasetContractError(
            "strict frozen dataset requires materialization_mode='full'"
        )
    for name, digest in entries:
        try:
            observed = canonical_file_hash(path / name)
        except FileNotFoundError as exc:
            raise DatasetContractError(f"payload is missing: {name}") from exc
        if observed != digest:
            raise DatasetContractError(f"payload hash mismatch for {name}")
    return manifest, dict(entries)


def _expected_scenario_factors() -> tuple[tuple[int, int, int, str], ...]:
    """Return the fixed confirmatory factorial in its protocol order."""

    return tuple(
        (truck_count, hopper_count, scale_count, regime)
        for truck_count in (60, 120, 180)
        for hopper_count in (1, 2, 3)
        for scale_count in (1, 2)
        for regime in ("nominal", "peak", "critical_failure", "priority_shift")
    )


def _manifest_seeds(manifest: Mapping[str, Any]) -> tuple[int, ...]:
    parameters = manifest.get("parameters")
    if not isinstance(parameters, Mapping):
        raise DatasetContractError("manifest parameters must be an object")
    seeds = parameters.get("seeds")
    if not isinstance(seeds, list) or tuple(seeds) != tuple(range(101, 151)):
        raise DatasetContractError("manifest parameters.seeds must be exactly 101..150")
    return tuple(int(seed) for seed in seeds)


def _validate_scenario_rows(
    rows: list[dict[str, Any]],
    manifest: Mapping[str, Any],
    expected_plan: DatasetPlan | None,
) -> dict[int, dict[str, Any]]:
    if len(rows) != 72:
        raise DatasetContractError("scenario_index must contain exactly 72 rows")
    if manifest.get("scenario_count") != 72:
        raise DatasetContractError("manifest scenario_count must be 72")
    if manifest.get("seed_count") != 50:
        raise DatasetContractError("manifest seed_count must be 50")
    if manifest.get("instance_count") != 3_600:
        raise DatasetContractError("manifest instance_count must be 3,600")
    if expected_plan is not None:
        if expected_plan.scenario_count != 72 or expected_plan.seed_count != 50:
            raise DatasetContractError("expected plan is not the complete confirmatory plan")
    factors = _expected_scenario_factors()
    lookup: dict[int, dict[str, Any]] = {}
    for index, (observed, factor) in enumerate(zip(rows, factors)):
        truck_count, hopper_count, scale_count, regime = factor
        expected_id = f"n{truck_count}-m{hopper_count}-b{scale_count}-{regime}"
        expected_rho = truck_count / min(36 * hopper_count, 72 * scale_count)
        expected_stratum = "low" if expected_rho < 0.70 else "medium" if expected_rho < 0.85 else "high"
        if observed.get("scenario_index") != index or observed.get("scenario_id") != expected_id:
            raise DatasetContractError("scenario_index order or ID diverges from the canonical factorial")
        expected_values = {
            "N": truck_count,
            "hopper_count": hopper_count,
            "scale_count": scale_count,
            "regime": regime,
            "rho": expected_rho,
            "stratum": expected_stratum,
        }
        for name, expected in expected_values.items():
            if observed.get(name) != expected:
                raise DatasetContractError(f"scenario_index {name} diverges at row {index}")
        if observed.get("protocol_version") != manifest.get("protocol_version"):
            raise DatasetContractError("scenario_index protocol_version diverges from manifest")
        if observed.get("config_hash") != manifest.get("config_hash"):
            raise DatasetContractError("scenario_index config_hash diverges from manifest")
        if not isinstance(observed.get("generator_version"), str) or not observed["generator_version"].strip():
            raise DatasetContractError("scenario_index generator_version must be non-empty")
        if observed["generator_version"] != manifest.get("generator_version"):
            raise DatasetContractError("scenario_index generator_version diverges from manifest")
        lookup[index] = observed
    if expected_plan is not None:
        for observed, expected in zip(rows, expected_plan.scenarios):
            if observed["scenario_id"] != expected.scenario_id:
                raise DatasetContractError("scenario_index diverges from expected plan")
    cardinalities = manifest.get("cardinalities")
    if not isinstance(cardinalities, Mapping):
        raise DatasetContractError("manifest cardinalities must be an object")
    for name, expected in (("scenario_index", 72), ("instances", 3_600)):
        if cardinalities.get(name) != expected:
            raise DatasetContractError(f"manifest cardinalities.{name} must be {expected:,}")
    rejection_count = manifest.get("rejection_count")
    if isinstance(rejection_count, bool) or not isinstance(rejection_count, int) or rejection_count < 0:
        raise DatasetContractError("manifest rejection_count must be a non-negative integer")
    if cardinalities.get("rejection_log") != rejection_count:
        raise DatasetContractError("manifest rejection_log cardinality diverges from rejection_count")
    return lookup


def _expected_instance_ids(
    manifest: Mapping[str, Any],
    expected_plan: DatasetPlan | None,
) -> tuple[str, ...]:
    if expected_plan is not None:
        expected_ids = expected_plan.instance_ids
    else:
        seeds = _manifest_seeds(manifest)
        expected_ids = tuple(
            f"s{index:02d}-seed{seed:03d}"
            for index in range(72)
            for seed in seeds
        )
    if len(expected_ids) != 3_600 or len(set(expected_ids)) != 3_600:
        raise DatasetContractError("canonical instance plan must contain 3,600 unique IDs")
    return expected_ids


def _read_payloads(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    scenario_rows = _read_parquet(root / "scenario_index.parquet", "scenario_index.parquet", "scenario_index")
    truck_rows = _read_parquet(root / "trucks.parquet", "trucks.parquet", "trucks")
    service_rows = _read_parquet(root / "service_times.parquet", "service_times.parquet", "service_times")
    disruption_rows = _read_jsonl(root / "disruptions.jsonl", "disruptions.jsonl", "disruptions")
    rejection_rows = _read_jsonl(root / "rejection_log.jsonl", "rejection_log.jsonl", "rejection_log")
    for value, label in (
        (scenario_rows, "scenario_index.parquet"),
        (truck_rows, "trucks.parquet"),
        (service_rows, "service_times.parquet"),
        (disruption_rows, "disruptions.jsonl"),
        (rejection_rows, "rejection_log.jsonl"),
    ):
        _assert_finite_json(value, label)
    _validate_jsonl_types(disruption_rows, "disruptions")
    _validate_jsonl_types(rejection_rows, "rejection_log")
    return scenario_rows, truck_rows, service_rows, disruption_rows, rejection_rows


def _validate_jsonl_types(
    rows: list[dict[str, Any]],
    kind: str,
) -> None:
    """Validate the scalar shape of exact JSONL rows after byte parsing."""

    if kind == "disruptions":
        integer_fields = {"scenario_index", "seed", "event_rank", "sequence"}
        number_fields = {"time", "duration_min", "return_time"}
        string_fields = {
            "instance_id", "scenario_id", "resource_id", "truck_id", "event_type",
            "cause", "operation", "payload_hash",
        }
        optional_text_fields = {"resource_id", "truck_id", "operation"}
    elif kind == "rejection_log":
        integer_fields = {"candidate_ordinal", "scenario_index", "seed", "generation_attempt"}
        number_fields = set()
        string_fields = {
            "dataset_id", "instance_id", "reason_code", "validator", "candidate_hash",
            "automatic_resample_status", "next_action", "timestamp",
        }
        optional_text_fields = set()
    else:  # pragma: no cover - private helper called only with known kinds
        raise ValueError(f"unknown JSONL schema kind: {kind}")
    expected = set(_JSONL_SCHEMA_NAMES[f"{kind}.jsonl"])
    for ordinal, row in enumerate(rows):
        for name in integer_fields:
            value = row[name]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DatasetContractError(f"{kind} row {ordinal} field {name} must be a non-negative integer")
        for name in number_fields:
            value = row[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise DatasetContractError(f"{kind} row {ordinal} field {name} must be finite numeric")
        for name in string_fields:
            value = row[name]
            if not isinstance(value, str) or (name not in optional_text_fields and not value.strip()):
                raise DatasetContractError(f"{kind} row {ordinal} field {name} must be non-empty text")
        for name in expected - integer_fields - number_fields - string_fields:
            if row[name] is None:
                raise DatasetContractError(f"{kind} row {ordinal} field {name} must not be null")
        if "payload_hash" in row and (len(row["payload_hash"]) != 64 or any(c not in "0123456789abcdefABCDEF" for c in row["payload_hash"])):
            raise DatasetContractError(f"{kind} row {ordinal} payload_hash must be a SHA-256 digest")
        if "candidate_hash" in row and (len(row["candidate_hash"]) != 64 or any(c not in "0123456789abcdefABCDEF" for c in row["candidate_hash"])):
            raise DatasetContractError(f"{kind} row {ordinal} candidate_hash must be a SHA-256 digest")


def _validate_disruption_event_type(event_type: object) -> str:
    if not isinstance(event_type, str) or event_type not in _DISRUPTION_EVENT_TYPES:
        raise DatasetContractError("disruptions row has an unsupported event_type")
    return event_type


def _validate_full_payloads(
    root: Path,
    manifest: Mapping[str, Any],
    expected_plan: DatasetPlan | None,
    *,
    published_dataset_id: str | None = None,
) -> FrozenDataset:
    expected_dataset_id = root.name if published_dataset_id is None else published_dataset_id
    if not isinstance(expected_dataset_id, str) or not expected_dataset_id.strip():
        raise DatasetContractError("published dataset_id must be non-empty")
    if manifest.get("dataset_id") != expected_dataset_id:
        raise DatasetContractError("manifest dataset_id does not match destination namespace")
    if manifest.get("phase") != "synthetic" or manifest.get("freeze_status") != "FROZEN":
        raise DatasetContractError("dataset manifest must be a frozen synthetic phase")
    if manifest.get("policy_days_executed") is not False:
        raise DatasetContractError("frozen dataset must not contain executed policy-days")
    scenario_rows, truck_rows, service_rows, disruption_rows, rejection_rows = _read_payloads(root)
    scenario_lookup = _validate_scenario_rows(scenario_rows, manifest, expected_plan)
    expected_ids = _expected_instance_ids(manifest, expected_plan)
    expected_id_set = set(expected_ids)
    seeds = _manifest_seeds(manifest)
    by_instance_trucks: dict[str, list[FrozenTruck]] = {}
    by_instance_services: dict[str, list[FrozenServiceTime]] = {}
    by_instance_disruptions: dict[str, list[Mapping[str, Any]]] = {}
    disruption_row_instance_order: list[str] = []
    truck_row_instance_order: list[str] = []
    service_row_instance_order: list[str] = []
    observed_service_order: list[tuple[str, str, str]] = []
    for ordinal, row in enumerate(truck_rows):
        try:
            truck = FrozenTruck.from_dict(row)
        except (TypeError, ValueError) as exc:
            raise DatasetContractError(f"trucks row {ordinal} is invalid") from exc
        if truck.instance_id not in expected_id_set:
            raise DatasetContractError(f"trucks row {ordinal} has an unknown instance_id")
        scenario_index = truck.scenario_index
        if scenario_index not in scenario_lookup:
            raise DatasetContractError(f"trucks row {ordinal} has an unknown scenario_index")
        scenario = scenario_lookup[scenario_index]
        expected_seed = int(truck.instance_id.split("-seed", 1)[1])
        expected_prefix = truck.instance_id.split("-seed", 1)[0]
        if (
            truck.scenario_id != scenario["scenario_id"]
            or truck.seed != expected_seed
            or expected_prefix != f"s{scenario_index:02d}"
        ):
            raise DatasetContractError(f"trucks row {ordinal} identity diverges from instance plan")
        if truck.seed not in seeds:
            raise DatasetContractError(f"trucks row {ordinal} uses an unknown seed")
        truck_row_instance_order.append(truck.instance_id)
        by_instance_trucks.setdefault(truck.instance_id, []).append(truck)
    expected_truck_order = [
        instance_id
        for instance_id in expected_ids
        for _ in range(int(scenario_lookup[int(instance_id.split("-seed", 1)[0][1:])]["N"]))
    ]
    if truck_row_instance_order != expected_truck_order:
        raise DatasetContractError("trucks payload instance order diverges from canonical plan")
    for instance_id in expected_ids:
        scenario_index = int(instance_id.split("-seed", 1)[0][1:])
        expected_count = int(scenario_lookup[scenario_index]["N"])
        records = by_instance_trucks.get(instance_id, [])
        if len(records) != expected_count:
            raise DatasetContractError(f"{instance_id} must contain exactly {expected_count} truck rows")
        truck_ids = [item.truck_id for item in records]
        expected_truck_ids = [f"T-{index:03d}" for index in range(1, expected_count + 1)]
        if set(truck_ids) != set(expected_truck_ids) or len(set(truck_ids)) != expected_count:
            raise DatasetContractError(f"{instance_id} truck IDs are not injective T-001..T-{expected_count:03d}")
        if records != sorted(records, key=lambda item: (item.arrival_minute, item.truck_id)):
            raise DatasetContractError(f"{instance_id} truck rows are not in canonical arrival order")

    frozen_parameters = manifest.get("frozen_parameters")
    if not isinstance(frozen_parameters, Mapping):
        raise DatasetContractError("manifest frozen_parameters must be an object")
    service_distributions = frozen_parameters.get("service_distributions")
    if not isinstance(service_distributions, Mapping) or set(service_distributions) != set(_OPERATIONS):
        raise DatasetContractError("manifest frozen_parameters.service_distributions must cover all four operations")
    expected_distributions: dict[str, tuple[float, float, float]] = {}
    for operation in _OPERATIONS:
        values = service_distributions[operation]
        if not isinstance(values, (list, tuple)) or len(values) != 3:
            raise DatasetContractError(f"manifest service distribution for {operation} must contain three values")
        try:
            distribution = tuple(float(value) for value in values)
        except (TypeError, ValueError) as exc:
            raise DatasetContractError(f"manifest service distribution for {operation} is not numeric") from exc
        if any(not math.isfinite(value) or value < 0 for value in distribution) or not distribution[0] <= distribution[1] <= distribution[2]:
            raise DatasetContractError(f"manifest service distribution for {operation} is invalid")
        expected_distributions[operation] = distribution
    parameters = manifest.get("parameters")
    event_ranks = parameters.get("event_ranks") if isinstance(parameters, Mapping) else None
    if not isinstance(event_ranks, Mapping) or set(event_ranks) != set(_EVENT_RANK_NAMES):
        raise DatasetContractError("manifest parameters.event_ranks must define the canonical event ranks")
    for event_name, rank in event_ranks.items():
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
            raise DatasetContractError(f"manifest event rank for {event_name} must be a non-negative integer")
    horizon_minutes = frozen_parameters.get("horizon_minutes")
    if isinstance(horizon_minutes, bool) or not isinstance(horizon_minutes, (int, float)) or not math.isfinite(float(horizon_minutes)) or horizon_minutes <= 0:
        raise DatasetContractError("manifest frozen_parameters.horizon_minutes must be finite and positive")
    for ordinal, row in enumerate(service_rows):
        try:
            service = FrozenServiceTime.from_dict(row)
        except (TypeError, ValueError) as exc:
            raise DatasetContractError(f"service_times row {ordinal} is invalid") from exc
        if service.instance_id not in expected_id_set:
            raise DatasetContractError(f"service_times row {ordinal} has an unknown instance_id")
        scenario = scenario_lookup.get(service.scenario_index)
        if scenario is None or service.scenario_id != scenario["scenario_id"]:
            raise DatasetContractError(f"service_times row {ordinal} scenario identity diverges")
        expected_seed = int(service.instance_id.split("-seed", 1)[1])
        if service.seed != expected_seed or service.seed not in seeds:
            raise DatasetContractError(f"service_times row {ordinal} seed identity diverges")
        if service.crn_version != manifest.get("crn_version"):
            raise DatasetContractError(f"service_times row {ordinal} CRN version diverges")
        expected_draw_key = crn_digest(
            service.crn_version,
            service.scenario_index,
            service.seed,
            service.generation_attempt,
            service.truck_id,
            service.operation,
        )
        if service.draw_key != expected_draw_key:
            raise DatasetContractError(f"service_times row {ordinal} draw_key diverges from CRN tuple")
        if service.operation not in expected_distributions or expected_distributions[service.operation] != service.distribution:
            raise DatasetContractError(f"service_times row {ordinal} source distribution diverges")
        if service.truck_id not in {truck.truck_id for truck in by_instance_trucks[service.instance_id]}:
            raise DatasetContractError(f"service_times row {ordinal} references an unknown truck")
        service_row_instance_order.append(service.instance_id)
        observed_service_order.append((service.instance_id, service.truck_id, service.operation))
        by_instance_services.setdefault(service.instance_id, []).append(service)
    expected_service_order: list[tuple[str, str, str]] = []
    for instance_id in expected_ids:
        trucks = by_instance_trucks.get(instance_id, [])
        for truck in trucks:
            expected_service_order.extend((instance_id, truck.truck_id, operation) for operation in _OPERATIONS)
    if observed_service_order != expected_service_order:
        raise DatasetContractError("service_times payload order diverges from canonical truck/operation order")
    expected_service_instance_order = [instance_id for instance_id, _truck_id, _operation in expected_service_order]
    if service_row_instance_order != expected_service_instance_order:
        raise DatasetContractError("service_times payload instance order diverges from canonical plan")
    for instance_id in expected_ids:
        services = by_instance_services.get(instance_id, [])
        trucks = by_instance_trucks[instance_id]
        if len(services) != len(trucks) * len(_OPERATIONS):
            raise DatasetContractError(f"{instance_id} must contain exactly four service rows per truck")
        grouped = {truck_id: [item.operation for item in services if item.truck_id == truck_id] for truck_id in {truck.truck_id for truck in trucks}}
        if any(tuple(operations) != _OPERATIONS for operations in grouped.values()):
            raise DatasetContractError(f"{instance_id} service operations are not exactly gate/scale_in/unload/scale_out")

    for ordinal, row in enumerate(disruption_rows):
        instance_id = row.get("instance_id")
        if instance_id not in expected_id_set:
            raise DatasetContractError(f"disruptions row {ordinal} has an unknown instance_id")
        scenario_index = int(instance_id.split("-seed", 1)[0][1:])
        if row.get("scenario_index") != scenario_index or row.get("scenario_id") != scenario_lookup[scenario_index]["scenario_id"] or row.get("seed") != int(instance_id.split("-seed", 1)[1]):
            raise DatasetContractError(f"disruptions row {ordinal} identity diverges from instance plan")
        event_type = _validate_disruption_event_type(row["event_type"])
        if row["event_rank"] != event_ranks[event_type]:
            raise DatasetContractError(f"disruptions row {ordinal} event_rank diverges from event_type")
        event_time = float(row["time"])
        duration = float(row["duration_min"])
        return_time = float(row["return_time"])
        if event_time < 0 or event_time > float(horizon_minutes) or duration < 0 or return_time < 0:
            raise DatasetContractError(f"disruptions row {ordinal} time/duration is outside the horizon")
        if event_type in {"resource_failure", "rain_start", "rain_end"}:
            if not row["resource_id"] or row["truck_id"] or row["operation"]:
                raise DatasetContractError(f"disruptions row {ordinal} resource failure FK is invalid")
            valid_resources = {"gate-1"}
            valid_resources.update(
                f"scale-{index}" for index in range(1, int(scenario_lookup[scenario_index]["scale_count"]) + 1)
            )
            valid_resources.update(
                f"hopper-{index}" for index in range(1, int(scenario_lookup[scenario_index]["hopper_count"]) + 1)
            )
            if row["resource_id"] not in valid_resources:
                raise DatasetContractError(f"disruptions row {ordinal} references an unknown resource")
            if event_type == "rain_end":
                if return_time != 0 or duration != 0:
                    raise DatasetContractError(f"disruptions row {ordinal} rain end semantics are invalid")
            elif return_time < event_time + duration or duration <= 0:
                raise DatasetContractError(f"disruptions row {ordinal} recovery time is incoherent")
        elif event_type in {"document_release", "priority_change"}:
            if not row["truck_id"] or row["resource_id"]:
                raise DatasetContractError(f"disruptions row {ordinal} truck FK is invalid")
            if row["truck_id"] not in {truck.truck_id for truck in by_instance_trucks[instance_id]}:
                raise DatasetContractError(f"disruptions row {ordinal} references an unknown truck")
            if event_type == "document_release" and row["operation"] != "gate":
                raise DatasetContractError(f"disruptions row {ordinal} document release operation must be gate")
            if event_type == "priority_change" and row["operation"]:
                raise DatasetContractError(f"disruptions row {ordinal} priority change operation must be empty")
            if return_time != 0:
                raise DatasetContractError(f"disruptions row {ordinal} non-recovery return_time must be zero")
        expected_cause = {
            "document_release": "document",
            "priority_change": "priority_shift",
            "resource_failure": {"critical_failure", "base_failure"},
            "rain_start": "rain",
            "rain_end": "rain",
        }[event_type]
        if isinstance(expected_cause, set):
            if row["cause"] not in expected_cause:
                raise DatasetContractError(f"disruptions row {ordinal} cause diverges from event_type")
        elif row["cause"] != expected_cause:
            raise DatasetContractError(f"disruptions row {ordinal} cause diverges from event_type")
        observed_hash = row.get("payload_hash")
        payload = dict(row)
        payload.pop("payload_hash", None)
        if observed_hash != _digest_value(payload):
            raise DatasetContractError(f"disruptions row {ordinal} payload_hash mismatch")
        disruption_row_instance_order.append(instance_id)
        by_instance_disruptions.setdefault(instance_id, []).append(row)
    expected_disruption_instance_order = [
        instance_id
        for instance_id in expected_ids
        for _row in by_instance_disruptions.get(instance_id, [])
    ]
    if disruption_row_instance_order != expected_disruption_instance_order:
        raise DatasetContractError("disruptions payload instance order diverges from canonical plan")
    for instance_id, rows in by_instance_disruptions.items():
        sequences = [row["sequence"] for row in rows]
        if sorted(sequences) != list(range(1, len(rows) + 1)):
            raise DatasetContractError(f"{instance_id} disruption sequence is not contiguous")
        if rows != sorted(rows, key=lambda item: (item["time"], item["event_rank"], item["resource_id"], item["truck_id"], item["sequence"])):
            raise DatasetContractError(f"{instance_id} disruptions are not in canonical event order")

    for ordinal, row in enumerate(rejection_rows):
        if row.get("dataset_id") != manifest.get("dataset_id"):
            raise DatasetContractError(f"rejection_log row {ordinal} dataset_id diverges")
        instance_id = row.get("instance_id")
        if instance_id not in expected_id_set:
            raise DatasetContractError(f"rejection_log row {ordinal} has an unknown instance_id")
        scenario_index = int(instance_id.split("-seed", 1)[0][1:])
        if row.get("scenario_index") != scenario_index or row.get("seed") != int(instance_id.split("-seed", 1)[1]):
            raise DatasetContractError(f"rejection_log row {ordinal} identity diverges")
    cardinalities = manifest["cardinalities"]
    observed_cardinalities = {
        "trucks": len(truck_rows),
        "service_times": len(service_rows),
        "disruptions": len(disruption_rows),
        "rejection_log": len(rejection_rows),
    }
    expected_trucks = sum(int(row["N"]) for row in scenario_rows) * len(seeds)
    if observed_cardinalities["trucks"] != expected_trucks:
        raise DatasetContractError("trucks payload cardinality diverges from scenario N values")
    if observed_cardinalities["service_times"] != expected_trucks * len(_OPERATIONS):
        raise DatasetContractError("service_times payload cardinality diverges from trucks")
    for name, observed in observed_cardinalities.items():
        if cardinalities.get(name) != observed:
            raise DatasetContractError(f"manifest cardinalities.{name} does not match {name} payload")
    if len(rejection_rows) != manifest["rejection_count"]:
        raise DatasetContractError("rejection_log row count diverges from rejection_count")
    if manifest.get("resample_provenance") is None and rejection_rows:
        raise DatasetContractError("initial frozen dataset rejection_log must be empty")

    manifest_instance_hashes = manifest.get("instance_hashes")
    if not isinstance(manifest_instance_hashes, list) or len(manifest_instance_hashes) != 3_600:
        raise DatasetContractError("manifest instance_hashes must contain exactly 3,600 entries")
    if [item.get("instance_id") if isinstance(item, Mapping) else None for item in manifest_instance_hashes] != list(expected_ids):
        raise DatasetContractError("manifest instance_hashes order diverges from canonical plan")
    instance_hash_lookup: dict[str, str] = {}
    for item in manifest_instance_hashes:
        if not isinstance(item, Mapping) or set(item) != {"instance_id", "instance_hash"}:
            raise DatasetContractError("manifest instance_hashes rows must contain instance_id and instance_hash")
        digest = item["instance_hash"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise DatasetContractError("manifest instance_hashes values must be SHA-256 digests")
        instance_hash_lookup[str(item["instance_id"])] = digest

    resource_lookup: dict[int, tuple[FrozenResource, ...]] = {}
    for index, row in scenario_lookup.items():
        scenario = ScenarioConfig(
            truck_count=int(row["N"]),
            hopper_count=int(row["hopper_count"]),
            scale_count=int(row["scale_count"]),
            regime=str(row["regime"]),
            scenario_index=index,
        )
        resource_lookup[index] = _resource_records(scenario)
    instances: list[FrozenInstance] = []
    for instance_id in expected_ids:
        scenario_index = int(instance_id.split("-seed", 1)[0][1:])
        seed = int(instance_id.split("-seed", 1)[1])
        scenario = scenario_lookup[scenario_index]
        try:
            instance = FrozenInstance(
                instance_id=instance_id,
                scenario_index=scenario_index,
                scenario_id=str(scenario["scenario_id"]),
                seed=seed,
                generation_attempt=0,
                trucks=tuple(by_instance_trucks[instance_id]),
                resources=resource_lookup[scenario_index],
                service_times=tuple(by_instance_services[instance_id]),
                disruptions=tuple(by_instance_disruptions.get(instance_id, [])),
            )
        except (TypeError, ValueError) as exc:
            raise DatasetContractError(f"could not reconstruct {instance_id}") from exc
        if instance.instance_hash != instance_hash_lookup[instance_id]:
            raise DatasetContractError(f"instance_hash mismatch for {instance_id}")
        instances.append(instance)
    return FrozenDataset(root, manifest, tuple(instances))


def validate_frozen_dataset(
    path: str | Path,
    expected_plan: DatasetPlan | None = None,
) -> FrozenDataset:
    """Strictly validate a complete production freeze."""

    return load_frozen_dataset(path, expected_plan=expected_plan)


def _load_frozen_dataset(
    path: str | Path,
    expected_plan: DatasetPlan | None = None,
    *,
    published_dataset_id: str | None = None,
) -> FrozenDataset:
    root = Path(path)
    manifest, _checksums = _validate_checksum_chain(root)
    return _validate_full_payloads(
        root,
        manifest,
        expected_plan,
        published_dataset_id=published_dataset_id,
    )


def load_frozen_dataset(path: str | Path, expected_plan: DatasetPlan | None = None) -> FrozenDataset:
    """Load a complete, canonical production freeze; never headers or defaults."""

    return _load_frozen_dataset(path, expected_plan=expected_plan)


def freeze_dataset(path: str | Path, manifest: Mapping[str, Any] | None = None) -> FrozenDataset:
    """Finalize a directory containing the five payloads and return its freeze."""

    root = Path(path)
    if not root.is_dir():
        raise DatasetContractError(f"freeze staging directory is missing: {root}")
    existing_metadata = [
        root / "manifest.json",
        root / "checksums.sha256",
        root / "FREEZE.json",
    ]
    if any(item.exists() for item in existing_metadata):
        raise FileExistsError(
            "refusing to overwrite existing freeze metadata: "
            + ", ".join(item.name for item in existing_metadata if item.exists())
        )
    if manifest is None:
        raise DatasetContractError(
            "freeze_dataset requires an explicit manifest; implicit metadata discovery is forbidden"
        )
    if not isinstance(manifest, Mapping):
        raise DatasetContractError("manifest must be a mapping")
    return _finalize_freeze(root, manifest)


def select_pilot_configurations(config: ExperimentConfig) -> tuple[ScenarioConfig, ...]:
    """Select the preregistered 20% pilot by stable scenario hash order."""

    plan = plan_synthetic_dataset(config)
    scenarios = sorted(
        plan.scenarios,
        key=lambda scenario: crn_digest(config.crn_version, scenario.scenario_index, 0, 0, "scenario", "pilot_selection"),
    )
    selected = {scenario.scenario_index for scenario in scenarios[: math.ceil(0.20 * len(plan.scenarios))]}
    return tuple(scenario for scenario in plan.scenarios if scenario.scenario_index in selected)


__all__ = [
    "DatasetContractError",
    "DatasetPlan",
    "FaceValidationError",
    "FrozenDataset",
    "FrozenInstance",
    "GenerationPlanReceipt",
    "GenerationRejectedError",
    "canonical_payload_schemas",
    "freeze_dataset",
    "generate_synthetic_dataset",
    "load_frozen_dataset",
    "plan_synthetic_dataset",
    "select_pilot_configurations",
    "validate_generation_headers",
    "validate_frozen_dataset",
]
