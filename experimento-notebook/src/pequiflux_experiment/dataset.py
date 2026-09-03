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
from typing import Any, Callable, Iterable, Mapping

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
from .manifest import (
    canonical_checksum_bytes,
    canonical_file_hash,
    create_run_directory,
    dataset_root_hash,
    write_checksums,
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
        "rejection_count",
        "policy_days_executed",
        "resample_provenance",
        "materialization_mode",
    }
)
_OPERATIONS: tuple[str, ...] = ("gate", "scale_in", "unload", "scale_out")
_RESOURCE_KINDS: tuple[tuple[str, str], ...] = (("gate-1", "gate"),)


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


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    lines: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("JSONL rows must be mappings")
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
            }
        )
    trucks_data.sort(key=lambda value: (value["arrival_minute"], value["truck_id"]))
    trucks = tuple(FrozenTruck.from_dict(item) for item in trucks_data)

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
                    seed=seed,
                    truck_id=truck.truck_id,
                    operation=operation,
                    duration_min=duration,
                    distribution=distribution,
                    draw_key=draw_key,
                    crn_version=config.crn_version,
                )
            )

    disruptions: list[dict[str, Any]] = []
    sequence = 0

    def add_disruption(event: dict[str, Any]) -> None:
        nonlocal sequence
        sequence += 1
        payload = dict(event)
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
                    "priority": 2,
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
    """Collect deterministic rows while allowing a header-only test seam."""

    def __init__(self, *, header_only: bool) -> None:
        self.header_only = header_only
        self.header_rows: list[dict[str, Any]] = []
        self.truck_rows: list[dict[str, Any]] = []
        self.service_rows: list[dict[str, Any]] = []
        self.disruption_rows: list[dict[str, Any]] = []
        self.rejection_rows: list[dict[str, Any]] = []
        self.current_instance: FrozenInstance | None = None

    def write_header(self, header: Mapping[str, Any]) -> None:
        if not isinstance(header, Mapping):
            raise TypeError("header must be a mapping")
        self.header_rows.append(dict(header))

    def write_instance(self, instance: FrozenInstance) -> None:
        self.header_rows.append(
            {
                "instance_id": instance.instance_id,
                "generation_attempt": instance.generation_attempt,
            }
        )
        if self.header_only:
            return
        self.truck_rows.extend(truck.to_dict() for truck in instance.trucks)
        self.service_rows.extend(service.to_dict() for service in instance.service_times)
        self.disruption_rows.extend(dict(item) for item in instance.disruptions)


def _materialize_production_header(header: FrozenInstance, writer: _PayloadWriter) -> None:
    """Default full materializer; tests may replace this with a header spy."""

    if writer.current_instance is not header:
        raise DatasetContractError("materializer received a different instance header")
    writer.write_instance(header)


_materialize_production_header._production_materializer = True  # type: ignore[attr-defined]


def _write_parquet(path: Path, rows: list[Mapping[str, Any]], kind: str) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - environment dependent
        raise DatasetContractError(f"pyarrow is required to write {kind}") from exc
    schemas = {
        "scenario_index": pa.schema(
            [
                pa.field("scenario_index", pa.int64()),
                pa.field("scenario_id", pa.string()),
                pa.field("N", pa.int64()),
                pa.field("hopper_count", pa.int64()),
                pa.field("scale_count", pa.int64()),
                pa.field("regime", pa.string()),
                pa.field("rho", pa.float64()),
                pa.field("stratum", pa.string()),
                pa.field("protocol_version", pa.string()),
                pa.field("config_hash", pa.string()),
                pa.field("generator_version", pa.string()),
            ]
        ),
        "trucks": pa.schema(
            [
                pa.field("instance_id", pa.string()),
                pa.field("scenario_index", pa.int64()),
                pa.field("scenario_id", pa.string()),
                pa.field("seed", pa.int64()),
                pa.field("truck_id", pa.string()),
                pa.field("arrival_minute", pa.float64()),
                pa.field("cargo_type", pa.string()),
                pa.field("priority", pa.int64()),
                pa.field("document_status", pa.string()),
                pa.field("stage", pa.string()),
                pa.field("eligible_resources", pa.list_(pa.string())),
                pa.field("truck_record_hash", pa.string()),
            ]
        ),
        "service_times": pa.schema(
            [
                pa.field("instance_id", pa.string()),
                pa.field("scenario_index", pa.int64()),
                pa.field("seed", pa.int64()),
                pa.field("truck_id", pa.string()),
                pa.field("operation", pa.string()),
                pa.field("duration_min", pa.float64()),
                pa.field("distribution", pa.list_(pa.float64())),
                pa.field("draw_key", pa.string()),
                pa.field("crn_version", pa.string()),
                pa.field("service_record_hash", pa.string()),
            ]
        ),
    }
    schema = schemas[kind]
    if rows:
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
        if not destination.is_dir():
            raise FileExistsError(f"dataset destination is not a directory: {destination}")
        if any(destination.iterdir()):
            raise FileExistsError(f"dataset destination already exists and is not empty: {destination}")
    else:
        destination.mkdir(parents=True, exist_ok=False)
    return destination


def _build_manifest(
    config: ExperimentConfig,
    plan: DatasetPlan,
    destination: Path,
    now_utc: datetime,
    generator_version: str,
    payload_hashes: tuple[tuple[str, str], ...],
    rejection_count: int,
    *,
    materialization_mode: str,
    instance_headers: list[Mapping[str, Any]],
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
        "materialization_mode": materialization_mode,
    }
    if materialization_mode == "header-only-test":
        manifest["instance_headers"] = [dict(item) for item in instance_headers]
    return manifest


def _finalize_freeze(destination: Path, manifest: Mapping[str, Any]) -> FrozenDataset:
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
    # Loading performs the full independent chain/cardinality check.
    return load_frozen_dataset(destination)


def generate_synthetic_dataset(
    config: ExperimentConfig,
    face_report: Any,
    dataset_root: str | Path,
    *,
    now_utc: datetime | str | None = None,
    generator_version: str,
    rejection_injector: Callable[[str], bool] | None = None,
) -> FrozenDataset:
    """Materialize and freeze the complete 3,600-instance synthetic dataset."""

    validate_confirmatory_config(config)
    if getattr(face_report, "status", None) != "APPROVED":
        status = getattr(face_report, "status", "UNKNOWN")
        cause = getattr(face_report, "cause", "approved face-validation receipt is required")
        raise FaceValidationError(
            f"generate_synthetic_dataset blocked before namespace: FACE_VALIDATION={status}; {cause}"
        )
    if not isinstance(generator_version, str) or not generator_version.strip():
        raise ValueError("generator_version must be a non-empty string")
    plan = plan_synthetic_dataset(config)
    timestamp = _as_utc(now_utc)
    destination = _prepare_destination(dataset_root)
    materializer = _materialize_production_header
    header_only = not bool(getattr(materializer, "_production_materializer", False))
    writer = _PayloadWriter(header_only=header_only)
    for scenario in plan.scenarios:
        for seed in plan.seeds:
            instance = (
                FrozenInstance(
                    instance_id=_instance_id(scenario.scenario_index, seed),
                    scenario_index=scenario.scenario_index,
                    scenario_id=scenario.scenario_id,
                    seed=seed,
                    generation_attempt=0,
                    trucks=(),
                    resources=(),
                    service_times=(),
                    disruptions=(),
                )
                if header_only
                else _build_instance(config, scenario, seed)
            )
            if rejection_injector is not None and rejection_injector(instance.instance_id):
                raise GenerationRejectedError(
                    f"generation rejected instance_id={instance.instance_id}; EXPLICIT_RESAMPLE_REQUIRED"
                )
            writer.current_instance = instance
            materializer(instance, writer)
            if header_only and not writer.header_rows:
                raise DatasetContractError("header materializer did not emit an instance header")

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
    _write_parquet(destination / "scenario_index.parquet", scenarios, "scenario_index")
    _write_parquet(destination / "trucks.parquet", writer.truck_rows, "trucks")
    _write_parquet(destination / "service_times.parquet", writer.service_rows, "service_times")
    (destination / "disruptions.jsonl").write_bytes(_jsonl_bytes(writer.disruption_rows))
    (destination / "rejection_log.jsonl").write_bytes(_jsonl_bytes(writer.rejection_rows))
    payload_hashes = tuple((name, canonical_file_hash(destination / name)) for name in _PAYLOAD_NAMES)
    materialization_mode = "header-only-test" if header_only else "full"
    manifest = _build_manifest(
        config,
        plan,
        destination,
        timestamp,
        generator_version,
        payload_hashes,
        len(writer.rejection_rows),
        materialization_mode=materialization_mode,
        instance_headers=writer.header_rows,
        cardinalities={
            "scenario_index": len(scenarios),
            "instances": len(writer.header_rows),
            "trucks": len(writer.truck_rows),
            "service_times": len(writer.service_rows),
            "disruptions": len(writer.disruption_rows),
            "rejection_log": len(writer.rejection_rows),
        },
    )
    return _finalize_freeze(destination, manifest)


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetContractError(f"{label} is missing: {path}") from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise DatasetContractError(f"{label} is invalid JSON: {path}") from exc


def _read_parquet(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - environment dependent
        raise DatasetContractError(f"pyarrow is required to read {label}") from exc
    try:
        return pq.read_table(path).to_pylist()
    except (OSError, ValueError, RuntimeError) as exc:
        raise DatasetContractError(f"{label} could not be read: {path}") from exc


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DatasetContractError(f"{label} is missing: {path}") from exc
    if raw == "":
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(raw.splitlines(), start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetContractError(f"{label} line {number} is invalid JSON") from exc
        if not isinstance(item, dict):
            raise DatasetContractError(f"{label} line {number} must be an object")
        rows.append(item)
    if not raw.endswith("\n"):
        raise DatasetContractError(f"{label} must end with one LF")
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
    manifest_path = path / "manifest.json"
    checksums_path = path / "checksums.sha256"
    freeze_path = path / "FREEZE.json"
    manifest = _load_json(manifest_path, "manifest")
    freeze = _load_json(freeze_path, "FREEZE.json")
    if not isinstance(manifest, dict):
        raise DatasetContractError("manifest root must be an object")
    _assert_finite_json(manifest, "manifest")
    _assert_finite_json(freeze, "FREEZE.json")
    missing_manifest = sorted(_REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing_manifest:
        raise DatasetContractError(
            "manifest is missing required fields: " + ", ".join(missing_manifest)
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
    for name, digest in entries:
        try:
            observed = canonical_file_hash(path / name)
        except FileNotFoundError as exc:
            raise DatasetContractError(f"payload is missing: {name}") from exc
        if observed != digest:
            raise DatasetContractError(f"payload hash mismatch for {name}")
    return manifest, dict(entries)


def _validate_scenario_rows(rows: list[dict[str, Any]], manifest: Mapping[str, Any], expected_plan: DatasetPlan | None) -> None:
    if expected_plan is not None:
        if len(rows) != expected_plan.scenario_count:
            raise DatasetContractError(f"scenario_index must contain {expected_plan.scenario_count} rows")
        for observed, expected in zip(rows, expected_plan.scenarios):
            if observed.get("scenario_index") != expected.scenario_index or observed.get("scenario_id") != expected.scenario_id:
                raise DatasetContractError("scenario_index order or ID diverges from the canonical factorial")
            if observed.get("N") != expected.N or observed.get("hopper_count") != expected.m or observed.get("scale_count") != expected.b or observed.get("regime") != expected.regime:
                raise DatasetContractError("scenario_index factor levels diverge from the canonical factorial")
            if observed.get("rho") != expected.rho or observed.get("stratum") != expected.stratum:
                raise DatasetContractError("scenario_index rho/stratum diverges from the canonical protocol")
    if manifest.get("scenario_count") != 72:
        raise DatasetContractError("manifest scenario_count must be 72")
    if manifest.get("seed_count") != 50:
        raise DatasetContractError("manifest seed_count must be 50")
    if manifest.get("instance_count") != 3_600:
        raise DatasetContractError("manifest instance_count must be 3,600")
    cardinalities = manifest.get("cardinalities")
    if not isinstance(cardinalities, Mapping):
        raise DatasetContractError("manifest cardinalities must be an object")
    expected_cardinalities = {
        "scenario_index": 72,
        "instances": 3_600,
    }
    for name, expected in expected_cardinalities.items():
        if cardinalities.get(name) != expected:
            raise DatasetContractError(
                f"manifest cardinalities.{name} must be {expected:,}"
            )
    rejection_count = manifest.get("rejection_count")
    if isinstance(rejection_count, bool) or not isinstance(rejection_count, int) or rejection_count < 0:
        raise DatasetContractError("manifest rejection_count must be a non-negative integer")
    if cardinalities.get("rejection_log") != rejection_count:
        raise DatasetContractError("manifest rejection_log cardinality diverges from rejection_count")


def validate_frozen_dataset(
    path: str | Path,
    expected_plan: DatasetPlan | None = None,
    strict_production: bool = False,
) -> FrozenDataset:
    """Validate the complete freeze and return its immutable dataset view."""

    root = Path(path)
    if not root.is_dir():
        message = "production freeze requires 3,600 instances and a FREEZE.json"
        raise DatasetContractError(message)
    if strict_production and expected_plan is not None and not (root / "manifest.json").exists():
        raise DatasetContractError(
            f"incomplete frozen dataset: expected {expected_plan.instance_count:,} instances"
        )
    try:
        manifest, _checksums = _validate_checksum_chain(root)
    except DatasetContractError:
        raise
    if manifest.get("phase") != "synthetic" or manifest.get("freeze_status") != "FROZEN":
        raise DatasetContractError("dataset manifest must be a frozen synthetic phase")
    if manifest.get("policy_days_executed") is not False:
        raise DatasetContractError("frozen dataset must not contain executed policy-days")
    scenario_rows = _read_parquet(root / "scenario_index.parquet", "scenario_index.parquet")
    _assert_finite_json(scenario_rows, "scenario_index.parquet")
    _validate_scenario_rows(scenario_rows, manifest, expected_plan)
    if strict_production and manifest.get("instance_count") != 3_600:
        raise DatasetContractError("strict production freeze requires exactly 3,600 instances")
    mode = manifest.get("materialization_mode", "full")
    trucks = _read_parquet(root / "trucks.parquet", "trucks.parquet")
    services = _read_parquet(root / "service_times.parquet", "service_times.parquet")
    disruptions = _read_jsonl(root / "disruptions.jsonl", "disruptions.jsonl")
    rejection_rows = _read_jsonl(root / "rejection_log.jsonl", "rejection_log.jsonl")
    _assert_finite_json(trucks, "trucks.parquet")
    _assert_finite_json(services, "service_times.parquet")
    _assert_finite_json(disruptions, "disruptions.jsonl")
    _assert_finite_json(rejection_rows, "rejection_log.jsonl")
    cardinalities = manifest["cardinalities"]
    observed_cardinalities = {
        "trucks": len(trucks),
        "service_times": len(services),
        "disruptions": len(disruptions),
        "rejection_log": len(rejection_rows),
    }
    for name, observed in observed_cardinalities.items():
        if cardinalities.get(name) != observed:
            raise DatasetContractError(
                f"manifest cardinalities.{name} does not match {name} payload"
            )
    if len(rejection_rows) != manifest["rejection_count"]:
        raise DatasetContractError("rejection_log row count diverges from rejection_count")
    if mode == "full":
        if len({row.get("instance_id") for row in trucks}) != manifest.get("instance_count"):
            raise DatasetContractError("trucks payload does not cover all 3,600 instances")
        if len(services) != len(trucks) * 4:
            raise DatasetContractError("service_times payload must contain four rows per truck")
    elif mode == "header-only-test":
        headers = manifest.get("instance_headers")
        if not isinstance(headers, list) or len(headers) != 3_600:
            raise DatasetContractError("header-only test freeze must enumerate exactly 3,600 instances")
    else:
        raise DatasetContractError(f"unknown materialization_mode: {mode!r}")
    if expected_plan is not None:
        observed_ids = (
            [str(item.get("instance_id")) for item in manifest.get("instance_headers", [])]
            if mode == "header-only-test"
            else sorted({str(item.get("instance_id")) for item in trucks})
        )
        if mode == "header-only-test":
            expected_ids = list(expected_plan.instance_ids)
            if observed_ids != expected_ids:
                raise DatasetContractError("instance header order diverges from the canonical plan")
        elif set(observed_ids) != set(expected_plan.instance_ids):
            raise DatasetContractError("instance IDs diverge from the canonical plan")
    return load_frozen_dataset(root)


def _instance_from_header(header: Mapping[str, Any], manifest: Mapping[str, Any]) -> FrozenInstance:
    instance_id = header.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id:
        raise DatasetContractError("instance header has no instance_id")
    try:
        prefix, seed_text = instance_id.split("-seed", 1)
        scenario_index = int(prefix[1:])
        seed = int(seed_text)
    except (ValueError, IndexError) as exc:
        raise DatasetContractError(f"invalid instance_id {instance_id!r}") from exc
    scenario_id = next(
        (
            str(row["scenario_id"])
            for row in manifest.get("scenario_index_rows", [])
            if row.get("scenario_index") == scenario_index
        ),
        f"scenario-index-{scenario_index}",
    )
    return FrozenInstance(
        instance_id=instance_id,
        scenario_index=scenario_index,
        scenario_id=scenario_id,
        seed=seed,
        generation_attempt=int(header.get("generation_attempt", 0)),
        trucks=(),
        resources=(),
        service_times=(),
        disruptions=(),
    )


def load_frozen_dataset(path: str | Path, expected_plan: DatasetPlan | None = None) -> FrozenDataset:
    """Load a validated freeze; no generator or implicit latest discovery is used."""

    root = Path(path)
    manifest, _checksums = _validate_checksum_chain(root)
    if manifest.get("phase") != "synthetic" or manifest.get("freeze_status") != "FROZEN":
        raise DatasetContractError("dataset manifest must be a frozen synthetic phase")
    if manifest.get("policy_days_executed") is not False:
        raise DatasetContractError("frozen dataset must not contain executed policy-days")
    scenario_rows = _read_parquet(root / "scenario_index.parquet", "scenario_index.parquet")
    _assert_finite_json(scenario_rows, "scenario_index.parquet")
    if expected_plan is None:
        expected_plan = None
    _validate_scenario_rows(scenario_rows, manifest, expected_plan)
    manifest_with_rows = dict(manifest)
    manifest_with_rows["scenario_index_rows"] = scenario_rows
    mode = manifest.get("materialization_mode", "full")
    truck_rows = _read_parquet(root / "trucks.parquet", "trucks.parquet")
    service_rows = _read_parquet(root / "service_times.parquet", "service_times.parquet")
    disruption_rows = _read_jsonl(root / "disruptions.jsonl", "disruptions.jsonl")
    rejection_rows = _read_jsonl(root / "rejection_log.jsonl", "rejection_log.jsonl")
    _assert_finite_json(truck_rows, "trucks.parquet")
    _assert_finite_json(service_rows, "service_times.parquet")
    _assert_finite_json(disruption_rows, "disruptions.jsonl")
    _assert_finite_json(rejection_rows, "rejection_log.jsonl")
    by_instance_trucks: dict[str, list[FrozenTruck]] = {}
    by_instance_services: dict[str, list[FrozenServiceTime]] = {}
    by_instance_disruptions: dict[str, list[Mapping[str, Any]]] = {}
    for row in truck_rows:
        truck = FrozenTruck.from_dict(row)
        by_instance_trucks.setdefault(truck.instance_id, []).append(truck)
    for row in service_rows:
        service = FrozenServiceTime(
            instance_id=row["instance_id"],
            scenario_index=row["scenario_index"],
            seed=row["seed"],
            truck_id=row["truck_id"],
            operation=row["operation"],
            duration_min=row["duration_min"],
            distribution=row["distribution"],
            draw_key=row["draw_key"],
            crn_version=row["crn_version"],
            service_record_hash=row.get("service_record_hash"),
        )
        by_instance_services.setdefault(service.instance_id, []).append(service)
    for row in disruption_rows:
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str):
            raise DatasetContractError("disruption row has no instance_id")
        by_instance_disruptions.setdefault(instance_id, []).append(row)
    instances: list[FrozenInstance] = []
    if mode == "header-only-test":
        for header in manifest.get("instance_headers", []):
            instances.append(_instance_from_header(header, manifest_with_rows))
    else:
        instance_ids = sorted(by_instance_trucks, key=lambda value: (
            int(value.split("-seed", 1)[0][1:]),
            int(value.split("-seed", 1)[1]),
        ))
        scenario_lookup = {row["scenario_index"]: row for row in scenario_rows}
        resource_lookup: dict[int, tuple[FrozenResource, ...]] = {}
        for row in scenario_rows:
            resources: list[FrozenResource] = [FrozenResource("gate-1", "gate", ("soy", "corn"))]
            resources.extend(FrozenResource(f"scale-{i}", "scale", ("soy", "corn")) for i in range(1, int(row["scale_count"]) + 1))
            resources.extend(FrozenResource(f"hopper-{i}", "hopper", ("soy", "corn")) for i in range(1, int(row["hopper_count"]) + 1))
            resource_lookup[int(row["scenario_index"])] = tuple(resources)
        for instance_id in instance_ids:
            rows = by_instance_trucks[instance_id]
            first = rows[0]
            scenario_index = int(first.scenario_index)
            instances.append(
                FrozenInstance(
                    instance_id=instance_id,
                    scenario_index=scenario_index,
                    scenario_id=str(first.scenario_id),
                    seed=int(first.seed),
                    generation_attempt=0,
                    trucks=tuple(sorted(rows, key=lambda item: (item.arrival_minute, item.truck_id))),
                    resources=resource_lookup[scenario_index],
                    service_times=tuple(sorted(by_instance_services.get(instance_id, []), key=lambda item: (item.truck_id, item.operation))),
                    disruptions=tuple(sorted(by_instance_disruptions.get(instance_id, []), key=lambda item: (item["time"], item.get("event_rank", 0), item.get("resource_id", ""), item.get("truck_id", ""), item.get("sequence", 0)))),
                )
            )
    return FrozenDataset(root, manifest_with_rows, tuple(instances))


def freeze_dataset(path: str | Path, manifest: Mapping[str, Any] | None = None) -> FrozenDataset:
    """Finalize a directory containing the five payloads and return its freeze."""

    root = Path(path)
    if manifest is None:
        manifest = _load_json(root / "manifest.json", "manifest")
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
    "GenerationRejectedError",
    "freeze_dataset",
    "generate_synthetic_dataset",
    "load_frozen_dataset",
    "plan_synthetic_dataset",
    "select_pilot_configurations",
    "validate_frozen_dataset",
]
