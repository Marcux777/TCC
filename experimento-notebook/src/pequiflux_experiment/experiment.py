"""Execution, persistence, and loading of paired experiment matrices.

The matrix boundary deliberately keeps the emulator responsible for the
simulation and keeps this module responsible for the run namespace and its
durable evidence.  A run is self-contained: every decision log carries the
initial snapshot needed by :mod:`pequiflux_experiment.replay`, while the CSV
contains one row for each scenario/seed/policy cell.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import uuid
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from .config import (
    ExperimentConfig,
    ScenarioConfig,
    config_hash,
    factorial_scenarios,
    validate_confirmatory_config,
)
from .digital_model import DigitalModel
from .dataset import derive_controlled_projection
from .domain import YardSnapshot, FrozenInstance, ExecutionControls, EventLatentLedger
from .emulator import DayResult, run_day
from .events import EventRecord
from .metrics import MetricRow, compute_policy_day_metrics, METRIC_SCALAR_FIELDS, INTEGER_METRIC_FIELDS
from .manifest import build_manifest, create_run_directory
from .policies import DispatchPolicy
from .statistics import canonical_scenario_metadata

INPUT_IDENTITY_FIELDS = (
    "instance_id", "instance_hash", "execution_instance_hash",
    "dataset_root_hash", "control_hash",
)


RESULT_HEADERS: tuple[str, ...] = (
    "scenario_id",
    "seed",
    "policy",
    "config_hash",
    *INPUT_IDENTITY_FIELDS,
    "stratum",
    "regime",
    "hopper_count",
    "scale_count",
    "log_file",
    "log_sha256",
    "metrics_file",
    "metrics_sha256",
    *METRIC_SCALAR_FIELDS,
    "initial_state_hash",
    "final_state_hash",
    "replay_state_hash",
    "a1_pass",
    "a2_fields_complete",
    "a2_structural_pass",
    "replay_pass",
)

EXECUTION_PHASES: tuple[str, ...] = (
    "validation",
    "pilot",
    "execute-confirmatory",
)

LOG_REQUIRED_FIELDS: tuple[str, ...] = (
    "run_id",
    "scenario_id",
    "seed",
    "policy",
    "config_hash",
    *INPUT_IDENTITY_FIELDS,
    "event_id",
    "event_kind",
    "kind",
    "sequence",
    "time",
    "resource_id",
    "candidates",
    "excluded",
    "selection",
    "explanation",
    "operator_decision",
    "state_before_hash",
    "state_after_hash",
    "payload",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _snapshot_hash(snapshot: YardSnapshot) -> str:
    if not isinstance(snapshot, YardSnapshot):
        raise TypeError("snapshot must be a YardSnapshot")
    return hashlib.sha256(_canonical_json(snapshot.canonical_dict()).encode("utf-8")).hexdigest()


def _atomic_write_text(path: str | Path, content: str) -> None:
    """Write and atomically publish one UTF-8 text artifact.

    The temporary file is a sibling of the destination, so ``Path.replace``
    has the same filesystem atomicity boundary as the final artifact.  A
    failed flush or replace is allowed to propagate with its original cause.
    """

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(destination)


def _atomic_write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(path, _canonical_json(value) + "\n")


def _path_component(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value or ":" in value:
        raise ValueError(f"{name} must be a path-safe component")
    return value


def _git_metadata() -> tuple[str, bool]:
    """Return the current checkout identity without mutating the repository."""

    repository = Path(__file__).resolve().parents[3]
    try:
        commit_process = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        status_process = subprocess.run(
            ["git", "status", "--porcelain", "--", "experimento-notebook"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("git metadata detection failed") from exc

    commit = commit_process.stdout.strip()
    if not commit:
        raise RuntimeError("git metadata detection returned an empty commit")
    _path_component("commit", commit)
    return commit, not bool(status_process.stdout.strip())


def _normalise_scenarios(scenarios: Iterable[ScenarioConfig]) -> tuple[ScenarioConfig, ...]:
    if isinstance(scenarios, (str, bytes, bytearray)):
        raise TypeError("scenarios must be an iterable of ScenarioConfig")
    try:
        values = tuple(scenarios)
    except TypeError as exc:
        raise TypeError("scenarios must be an iterable of ScenarioConfig") from exc
    if not values:
        raise ValueError("scenarios must not be empty")
    if any(not isinstance(value, ScenarioConfig) for value in values):
        raise TypeError("scenarios must contain ScenarioConfig values")
    ids = [value.scenario_id for value in values]
    if len(set(ids)) != len(ids):
        raise ValueError("scenarios must have unique scenario_id values")
    for scenario_id in ids:
        _path_component("scenario_id", scenario_id)
    return values


def _derived_scenario_metadata(scenario: ScenarioConfig) -> Mapping[str, Any]:
    """Derive persisted scenario metadata for validation and pilot runs."""

    if not isinstance(scenario, ScenarioConfig):
        raise TypeError("scenario must be a ScenarioConfig")
    rho = scenario.truck_count / min(
        36 * scenario.hopper_count,
        72 * scenario.scale_count,
    )
    if not math.isfinite(rho):
        raise RuntimeError(
            f"scenario produced a non-finite nominal load index: scenario_id={scenario.scenario_id}"
        )
    if rho < 0.70:
        stratum = "low"
    elif rho < 0.85:
        stratum = "medium"
    else:
        stratum = "high"
    return {
        "scenario_id": scenario.scenario_id,
        "truck_count": scenario.truck_count,
        "total_trucks": scenario.truck_count,
        "hopper_count": scenario.hopper_count,
        "scale_count": scenario.scale_count,
        "regime": scenario.regime,
        "stratum": stratum,
    }


def _normalise_seeds(seeds: Iterable[int]) -> tuple[int, ...]:
    if isinstance(seeds, (str, bytes, bytearray)):
        raise TypeError("seeds must be an iterable of integers")
    try:
        values = tuple(seeds)
    except TypeError as exc:
        raise TypeError("seeds must be an iterable of integers") from exc
    if not values:
        raise ValueError("seeds must not be empty")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("seeds must contain non-negative integers")
    if len(set(values)) != len(values):
        raise ValueError("seeds must be unique")
    return values


def _normalise_policies(
    policies: Iterable[str | DispatchPolicy],
    config: ExperimentConfig,
) -> tuple[str | DispatchPolicy, ...]:
    if isinstance(policies, (str, bytes, bytearray)):
        raise TypeError("policies must be an iterable of policy names")
    try:
        values = tuple(policies)
    except TypeError as exc:
        raise TypeError("policies must be an iterable of policy names") from exc
    if not values:
        raise ValueError("policies must not be empty")
    names: list[str] = []
    for value in values:
        if isinstance(value, DispatchPolicy):
            name = value.name
        elif isinstance(value, str):
            name = value
        else:
            raise TypeError("policies must contain names or DispatchPolicy values")
        if name not in config.policies:
            raise ValueError(f"policy is not in the configured panel: {name!r}")
        _path_component("policy", name)
        names.append(name)
    if len(set(names)) != len(names):
        raise ValueError("policies must be unique")
    return values


def _validate_confirmatory_matrix(
    scenarios: tuple[ScenarioConfig, ...],
    seeds: tuple[int, ...],
    policies: tuple[str, ...],
    config: ExperimentConfig,
) -> Mapping[str, Mapping[str, Any]]:
    """Enforce the exact 72 x 50 x 5 matrix at the execution boundary."""

    validate_confirmatory_config(config)
    expected_scenarios = factorial_scenarios(config)
    if scenarios != expected_scenarios:
        raise ValueError(
            "execute-confirmatory requires the canonical 72-scenario factorial "
            f"in configuration order; observed={len(scenarios)}"
        )
    if seeds != config.seeds:
        raise ValueError(
            "execute-confirmatory requires all 50 canonical seeds 101..150 "
            f"in configuration order; observed={seeds!r}"
        )
    if policies != config.policies:
        raise ValueError(
            "execute-confirmatory requires all five canonical policies "
            f"in configuration order; observed={policies!r}"
        )
    return canonical_scenario_metadata(config)


def _mapping_copy(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("mapping value expected")
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class RunBundle:
    """Immutable handles and parsed rows for one persisted matrix run."""

    run_dir: Path
    manifest_path: Path
    results_path: Path
    logs_dir: Path
    audit_path: Path
    results: tuple[Mapping[str, Any], ...]
    manifest: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("run_dir", "manifest_path", "results_path", "logs_dir", "audit_path"):
            value = getattr(self, name)
            if not isinstance(value, Path):
                object.__setattr__(self, name, Path(value))
        rows = tuple(self.results)
        if any(not isinstance(row, Mapping) for row in rows):
            raise TypeError("results must contain mappings")
        object.__setattr__(
            self,
            "results",
            tuple(_mapping_copy(row) for row in rows),
        )
        if not isinstance(self.manifest, Mapping):
            raise TypeError("manifest must be a mapping")
        object.__setattr__(self, "manifest", _mapping_copy(self.manifest))

    @property
    def run_id(self) -> str:
        return self.run_dir.name

    @property
    def decision_logs_dir(self) -> Path:
        return self.logs_dir

    @property
    def log_dir(self) -> Path:
        return self.logs_dir

    @property
    def results_csv(self) -> Path:
        return self.results_path

    @property
    def log_paths(self) -> tuple[Path, ...]:
        return tuple(sorted(self.logs_dir.glob("*.jsonl")))


def _normalise_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise TypeError("result row must be a mapping")
    missing = [header for header in RESULT_HEADERS if header not in row]
    if missing:
        raise ValueError(f"result row missing fields: {', '.join(missing)}")
    normalised = dict(row)
    for key in ("seed", "hopper_count", "scale_count", *INTEGER_METRIC_FIELDS):
        value = normalised[key]
        if isinstance(value, bool):
            raise ValueError(f"{key} must be an integer, not bool")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be an integer") from exc
        if not math.isfinite(numeric) or not numeric.is_integer():
            raise ValueError(f"{key} must be an integer")
        normalised[key] = int(numeric)
        if normalised[key] < 0:
            raise ValueError(f"{key} must be non-negative")
    if normalised["event_count"] <= 0:
        raise ValueError("event_count must be positive")
    if normalised["total_trucks"] <= 0:
        raise ValueError("total_trucks must be positive")
    if normalised["hopper_count"] <= 0:
        raise ValueError("hopper_count must be positive")
    if normalised["scale_count"] <= 0:
        raise ValueError("scale_count must be positive")
    if normalised["completed_trucks"] > normalised["total_trucks"]:
        raise ValueError("completed_trucks cannot exceed total_trucks")
    if normalised["throughput"] != normalised["completed_trucks"]:
        raise ValueError("throughput must equal trucks completed within the horizon")
    if normalised["remaining_trucks"] != normalised["total_trucks"] - normalised["completed_trucks"]:
        raise ValueError("remaining_trucks must reconcile with the observed truck population")
    for key in (field for field in METRIC_SCALAR_FIELDS if field not in INTEGER_METRIC_FIELDS):
        if isinstance(normalised[key], bool):
            raise ValueError(f"{key} must be numeric, not bool")
        normalised[key] = float(normalised[key])
        if not math.isfinite(normalised[key]) or normalised[key] < 0:
            raise ValueError(f"{key} must be finite and non-negative")
    for key in ("a1_pass", "a2_fields_complete", "a2_structural_pass", "replay_pass"):
        value = normalised[key]
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered not in {"true", "false"}:
                raise ValueError(f"{key} must be true or false")
            value = lowered == "true"
        if not isinstance(value, bool):
            raise TypeError(f"{key} must be bool")
        normalised[key] = value
    for key in (
        "scenario_id",
        *INPUT_IDENTITY_FIELDS,
        "policy",
        "config_hash",
        "stratum",
        "regime",
        "log_file",
        "metrics_file",
        "log_sha256",
        "metrics_sha256",
        "initial_state_hash",
        "final_state_hash",
        "replay_state_hash",
    ):
        if not isinstance(normalised[key], str) or not normalised[key]:
            raise ValueError(f"{key} must be a non-empty string")
    if normalised["stratum"] not in {"low", "medium", "high"}:
        raise ValueError("stratum must be one of low, medium, high")
    for key in (
        "config_hash",
        *INPUT_IDENTITY_FIELDS[1:],
        "log_sha256",
        "metrics_sha256",
        "initial_state_hash",
        "final_state_hash",
        "replay_state_hash",
    ):
        if not _SHA256_RE.fullmatch(normalised[key]):
            raise ValueError(f"{key} must be a lowercase SHA-256 digest")
    return normalised


def _read_results_csv(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != RESULT_HEADERS:
                received = tuple(reader.fieldnames or ())
                raise ValueError(
                    "results.csv headers do not match canonical headers: "
                    f"expected={RESULT_HEADERS!r} received={received!r}"
                )
            rows = tuple(_normalise_row(row) for row in reader)
    except FileNotFoundError:
        raise
    except (OSError, csv.Error, TypeError, ValueError):
        raise
    return rows


def _csv_text(rows: Sequence[Mapping[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=RESULT_HEADERS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        normalised = _normalise_row(row)
        serialised: dict[str, Any] = {}
        for key in RESULT_HEADERS:
            value = normalised[key]
            if isinstance(value, bool):
                serialised[key] = "true" if value else "false"
            else:
                serialised[key] = value
        writer.writerow(serialised)
    return stream.getvalue()


def _decision_fields(event: EventRecord) -> dict[str, Any]:
    payload = event.to_dict()["payload"]
    resource_id = payload.get("resource_id")
    candidates: list[Any] = []
    excluded: list[Any] = []
    selection: Mapping[str, Any] | None = None
    explanation = ""
    operator_decision: str | None = None

    if event.kind == "DECISION_RECORDED":
        recommendation = payload.get("decision")
        if isinstance(recommendation, Mapping):
            resource_id = recommendation.get("resource_id", resource_id)
            candidates = list(recommendation.get("candidate_ids", ()))
            excluded = list(recommendation.get("excluded", ()))
            selected = recommendation.get("selected")
            if isinstance(selected, Mapping):
                selection = dict(selected)
            explanation = str(recommendation.get("explanation", ""))
    elif event.kind == "OPERATOR_DECISION":
        operator_decision = payload.get("decision") if isinstance(payload.get("decision"), str) else None
        recommendation = payload.get("recommendation")
        if isinstance(recommendation, Mapping):
            resource_id = recommendation.get("resource_id", resource_id)
            candidates = list(recommendation.get("candidate_ids", ()))
            excluded = list(recommendation.get("excluded", ()))
            selected = recommendation.get("selected")
            if isinstance(selected, Mapping):
                selection = dict(selected)
            explanation = str(recommendation.get("explanation", ""))

    return {
        "resource_id": resource_id,
        "candidates": candidates,
        "excluded": excluded,
        "selection": selection,
        "explanation": explanation,
        "operator_decision": operator_decision,
    }


def _log_lines(
    result: DayResult,
    *,
    run_id: str,
    checksum: str,
) -> tuple[str, str, str, str, bool, bool]:
    """Build canonical enriched JSONL and return text plus state evidence."""

    initial_snapshot = result.initial_snapshot
    initial_hash = _snapshot_hash(initial_snapshot)
    model = DigitalModel.from_snapshot(initial_snapshot, scenario=result.scenario)
    lines: list[str] = []
    all_fields_complete = True
    for original_event in result.events:
        event = original_event
        event_payload = event.to_dict()["payload"]
        if event.kind == "RUN_STARTED":
            event_payload = {
                **event_payload,
                "initial_snapshot": initial_snapshot.canonical_dict(),
            }
            event = EventRecord(
                time=event.time,
                sequence=event.sequence,
                kind=event.kind,
                payload=event_payload,
            )

        before_hash = _snapshot_hash(model.snapshot())
        fields = _decision_fields(event)
        try:
            model.apply(event)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "persisted decision log could not be replayed while being built: "
                f"run_id={run_id} scenario_id={result.scenario_id} "
                f"seed={result.seed} policy={result.policy_name} "
                f"event={event.sequence}:{event.kind}"
            ) from exc
        after_hash = _snapshot_hash(model.snapshot())
        if event.kind in {"DECISION_RECORDED", "OPERATOR_DECISION"}:
            all_fields_complete = all_fields_complete and bool(
                fields["selection"]
                and fields["explanation"]
                and fields["candidates"]
            )
            if event.kind == "OPERATOR_DECISION":
                all_fields_complete = all_fields_complete and fields["operator_decision"] == "accept"

        line: dict[str, Any] = {
            "run_id": run_id,
            "scenario_id": result.scenario_id,
            "seed": result.seed,
            "policy": result.policy_name,
            "config_hash": checksum,
            **{field: getattr(result, field) for field in INPUT_IDENTITY_FIELDS},
            "event_id": f"{event.sequence}:{event.kind}",
            "event_kind": event.kind,
            "kind": event.kind,
            "sequence": event.sequence,
            "time": event.time,
            **fields,
            "state_before_hash": before_hash,
            "state_after_hash": after_hash,
            "payload": event_payload,
        }
        if tuple(line) != LOG_REQUIRED_FIELDS:
            # Keep this invariant explicit: the audit schema and producer
            # schema must evolve together instead of accepting a partial row.
            missing = [field for field in LOG_REQUIRED_FIELDS if field not in line]
            raise RuntimeError(f"decision log line schema is incomplete: {missing}")
        lines.append(_canonical_json(line))

    if not lines:
        raise RuntimeError(
            f"empty event stream for scenario_id={result.scenario_id} "
            f"seed={result.seed} policy={result.policy_name}"
        )
    replayed = model.snapshot()
    replay_hash = _snapshot_hash(replayed)
    expected_hash = _snapshot_hash(result.final_snapshot)
    if replay_hash != expected_hash:
        raise RuntimeError(
            "final replay diverged while building decision log: "
            f"scenario_id={result.scenario_id} seed={result.seed} "
            f"policy={result.policy_name} expected={expected_hash} observed={replay_hash}"
        )
    return (
        "\n".join(lines) + "\n",
        initial_hash,
        expected_hash,
        replay_hash,
        all_fields_complete,
        bool(lines[-1]),
    )


def _result_row(
    result: DayResult,
    *,
    checksum: str,
    scenario_metadata: Mapping[str, Any],
    log_file: str,
    log_sha256: str,
    initial_hash: str,
    final_hash: str,
    replay_hash: str,
    a2_fields_complete: bool,
    persisted_metrics: MetricRow,
    metrics_file: str,
    metrics_sha256: str,
) -> dict[str, Any]:
    if not isinstance(persisted_metrics, MetricRow):
        raise TypeError("persisted_metrics must be a complete canonical MetricRow")
    if persisted_metrics.log_sha256 != log_sha256:
        raise RuntimeError("canonical metrics reference different persisted event bytes")
    metrics = persisted_metrics.scalars
    if not isinstance(scenario_metadata, Mapping):
        raise TypeError("scenario_metadata must be a mapping")
    expected_total_trucks = scenario_metadata.get("total_trucks")
    if expected_total_trucks is None:
        # Confirmatory metadata is supplied by statistics.canonical_scenario_metadata,
        # whose source-facing name remains ``truck_count``.  The persisted
        # receipt uses the canonical result-column name ``total_trucks``.
        expected_total_trucks = scenario_metadata.get("truck_count")
    if not isinstance(expected_total_trucks, int) or expected_total_trucks <= 0:
        raise RuntimeError(
            f"scenario metadata has invalid total_trucks: scenario_id={result.scenario_id}"
        )
    observed_total_trucks = metrics["total_trucks"]
    if observed_total_trucks != expected_total_trucks:
        raise RuntimeError(
            "simulation total_trucks does not match canonical scenario metadata: "
            f"scenario_id={result.scenario_id} expected={expected_total_trucks} "
            f"observed={observed_total_trucks}"
        )
    a1_pass = (
        result.hard_constraint_violations == 0
        and int(metrics["hard_constraint_violations"]) == 0
        and result.max_scale_occupancy <= result.scenario.scale_count
    )
    row: dict[str, Any] = {
        "scenario_id": result.scenario_id,
        "seed": result.seed,
        "policy": result.policy_name,
        "config_hash": checksum,
        **{field: getattr(result, field) for field in INPUT_IDENTITY_FIELDS},
        "stratum": scenario_metadata["stratum"],
        "regime": scenario_metadata["regime"],
        "hopper_count": scenario_metadata["hopper_count"],
        "scale_count": scenario_metadata["scale_count"],
        "log_file": log_file,
        "log_sha256": log_sha256,
        "metrics_file": metrics_file,
        "metrics_sha256": metrics_sha256,
        **metrics,
        "initial_state_hash": initial_hash,
        "final_state_hash": final_hash,
        "replay_state_hash": replay_hash,
        "a1_pass": a1_pass,
        "a2_fields_complete": bool(a2_fields_complete),
        "a2_structural_pass": bool(a2_fields_complete),
        "replay_pass": final_hash == replay_hash,
    }
    return _normalise_row(row)


def _manifest_for_run(
    config: ExperimentConfig,
    *,
    run_dir: Path,
    phase: str,
    commit: str,
    checkout_clean: bool,
    scenarios: tuple[ScenarioConfig, ...],
    seeds: tuple[int, ...],
    policies: tuple[str, ...],
    log_entries: Mapping[str, Mapping[str, Any]],
    now_utc: Any,
) -> dict[str, Any]:
    checksum = config_hash(config)
    manifest = build_manifest(
        config,
        phase,
        commit,
        checksum,
        run_dir=run_dir,
        command="run_experiment_matrix",
        profile=phase,
        artifacts={
            "manifest": "manifest.json",
            "results": "results.csv",
            "audit": "audit.json",
            "logs": "logs",
            "decision_logs": "logs",
            "metrics": "metrics",
        },
        checkout_clean=checkout_clean,
        now_utc=now_utc,
    )
    manifest.update(
        {
            "expected_rows": len(scenarios) * len(seeds) * len(policies),
            "matrix": {
                "scenarios": [
                    {
                        "scenario_id": metadata["scenario_id"],
                        "stratum": metadata["stratum"],
                        "regime": metadata["regime"],
                        "total_trucks": metadata["total_trucks"],
                        "hopper_count": metadata["hopper_count"],
                        "scale_count": metadata["scale_count"],
                    }
                    for scenario in scenarios
                    for metadata in (_derived_scenario_metadata(scenario),)
                ],
                "scenario_ids": [scenario.scenario_id for scenario in scenarios],
                "seeds": list(seeds),
                "policies": list(policies),
            },
            "result_headers": list(RESULT_HEADERS),
            "log_headers": list(LOG_REQUIRED_FIELDS),
            "decision_logs": dict(log_entries),
            "logs": dict(log_entries),
            "log_hashes": {
                name: descriptor["sha256"] for name, descriptor in log_entries.items()
            },
            "a2": {
                "structural_status": "automated",
                "human_audit_status": "pending",
                "required_fields": list(LOG_REQUIRED_FIELDS),
            },
            "human_audit_status": "pending",
            "operator_mode": "synthetic_auto_accept",
            "global_acceptance_status": "pending",
            "human_review_evidence": None,
        }
    )
    return manifest


def _input_provenance(instances, controls, event_latents, *, kind, **evidence):
    return {
        "kind": kind,
        "dataset_root_hash": controls.source_dataset_root_hash,
        "event_latents_sha256": event_latents.event_latents_sha256,
        "controls": controls.to_dict(),
        "instances": [
            {"instance_id": item.instance_id, "scenario_id": item.scenario_id,
             "seed": item.seed, "instance_hash": item.instance_hash}
            for item in instances
        ],
        **evidence,
    }


def run_experiment_matrix(
    scenarios: Iterable[ScenarioConfig],
    seeds: Iterable[int],
    policies: Iterable[str | DispatchPolicy],
    config: ExperimentConfig,
    runs_root: str | Path,
    phase: str = "validation",
    now_utc: Any = None,
    *,
    dataset_path: str | Path | None = None,
    expected_dataset_root_hash: str | None = None,
    controls: ExecutionControls | None = None,
    face_receipt_path: str | Path | None = None,
    capacity_receipt: Any = None,
) -> RunBundle:
    """Execute scientific cells exclusively from a revalidated, pinned freeze.

    Pilot and confirmation require human face evidence and a current capacity
    receipt. All prerequisites are checked before creating a run namespace.
    Engineering fixtures use the explicitly non-confirmatory validation API.
    """
    from .dataset import load_frozen_dataset, select_pilot_configurations
    from .face_validation import validate_face_validation_receipt

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    validate_confirmatory_config(config)
    if phase not in EXECUTION_PHASES:
        raise ValueError("phase must be one of validation, pilot, execute-confirmatory")
    scenarios = _normalise_scenarios(scenarios)
    seeds = _normalise_seeds(seeds)
    policies = _normalise_policies(policies, config)
    if phase == "execute-confirmatory":
        if any(isinstance(policy, DispatchPolicy) for policy in policies):
            raise ValueError("execute-confirmatory requires canonical policy names, not policy objects")
        _validate_confirmatory_matrix(scenarios, seeds, policies, config)
    if dataset_path is None or expected_dataset_root_hash is None:
        raise ValueError("dataset_path and expected_dataset_root_hash are required; no internal generation")
    if phase == "pilot" and (scenarios != select_pilot_configurations(config)
                             or seeds != config.seeds or policies != config.policies):
        raise ValueError("pilot requires the canonical 15 scenarios, 50 seeds and five policies")
    dataset = load_frozen_dataset(dataset_path, expected_dataset_root_hash=expected_dataset_root_hash)
    if dataset.manifest["config_hash"] != config_hash(config):
        raise ValueError("frozen dataset configuration does not match execution configuration")
    if not isinstance(controls, ExecutionControls):
        raise TypeError("explicit ExecutionControls are required")
    if controls.source_dataset_root_hash != expected_dataset_root_hash:
        raise ValueError("controls source_dataset_root_hash does not match pinned dataset")
    if dataset.event_latents is None or controls.event_latents_sha256 != dataset.event_latents.event_latents_sha256:
        raise ValueError("controls event_latents_sha256 does not match frozen dataset")
    if (controls.ordinary_window != config.ordinary_window
            or controls.buffer_capacity != config.buffer_capacity
            or controls.threshold_multiplier != Decimal("1.00") or controls.intensity != "base"):
        raise ValueError("matrix executor requires explicit canonical baseline controls")
    selected_keys = {(scenario.scenario_id, seed) for scenario in scenarios for seed in seeds}
    instances = tuple(item for item in dataset.instances if (item.scenario_id, item.seed) in selected_keys)
    evidence = {"dataset_path": str(dataset.path.resolve())}
    workload = None
    if phase in {"pilot", "execute-confirmatory"}:
        if face_receipt_path is None:
            raise ValueError("face_receipt_path is required before scientific execution")
        face = validate_face_validation_receipt(
            face_receipt_path, config, Path(__file__).resolve().parents[3] / "main.pdf"
        )
        if not face.approved:
            raise ValueError(f"scientific execution blocked: FACE_VALIDATION={face.status}; {face.cause}")
        if capacity_receipt is None:
            raise ValueError("capacity_receipt is required before scientific execution")
        from .profiles import ConfirmatoryWorkload
        workload = ConfirmatoryWorkload.from_dataset(dataset, config, phase=phase)
        evidence["face_validation"] = face.as_dict()
        evidence["capacity_receipt"] = capacity_receipt.to_dict()
    return _run_materialized_matrix(
        scenarios, seeds, policies, config, runs_root, phase, now_utc,
        instances=instances, controls=controls, event_latents=dataset.event_latents,
        input_provenance=_input_provenance(instances, controls, dataset.event_latents,
                                          kind="frozen_dataset", **evidence),
        capacity_receipt=capacity_receipt, workload=workload,
    )


def run_validation_matrix(
    instances: Iterable[FrozenInstance],
    policies: Iterable[str | DispatchPolicy],
    config: ExperimentConfig,
    runs_root: str | Path,
    *,
    controls: ExecutionControls,
    event_latents: EventLatentLedger,
    now_utc: Any = None,
) -> RunBundle:
    """Run explicit engineering fixtures; this API cannot select a scientific phase."""
    values = tuple(instances)
    scenarios = {}
    for item in values:
        if not isinstance(item, FrozenInstance):
            raise TypeError("instances must contain FrozenInstance values")
        if not item.instance_id.startswith("validation-"):
            raise ValueError("run_validation_matrix accepts only explicit validation fixtures")
        scenarios[item.scenario_id] = ScenarioConfig(
            truck_count=len(item.trucks),
            hopper_count=sum(resource.kind == "hopper" for resource in item.resources),
            scale_count=sum(resource.kind == "scale" for resource in item.resources),
            regime=item.scenario_id.rsplit("-", 1)[-1], scenario_index=item.scenario_index,
        )
    return _run_materialized_matrix(
        tuple(scenarios.values()), tuple(dict.fromkeys(item.seed for item in values)),
        policies, config, runs_root, "validation", now_utc,
        instances=values, controls=controls, event_latents=event_latents,
        input_provenance=_input_provenance(values, controls, event_latents, kind="validation_fixture"),
    )


def _run_materialized_matrix(
    scenarios: Iterable[ScenarioConfig],
    seeds: Iterable[int],
    policies: Iterable[str | DispatchPolicy],
    config: ExperimentConfig,
    runs_root: str | Path,
    phase: str = "validation",
    now_utc: Any = None,
    *,
    instances: Sequence[FrozenInstance],
    controls: ExecutionControls,
    event_latents: EventLatentLedger,
    input_provenance: Mapping[str, Any],
    capacity_receipt: Any = None,
    workload: Any = None,
) -> RunBundle:
    """Execute and persist one deterministic paired matrix.

    No result is selected from an existing run and no cell is retried.  A
    collision at the namespace boundary or a failure in any cell propagates
    immediately with its context.

    Validation runs may execute supplied policy objects. Scientific runs have
    already checked the canonical policy panel and their input prerequisites.
    """

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    phase_component = _path_component("phase", phase)
    if phase_component not in EXECUTION_PHASES:
        raise ValueError(
            "phase must be one of validation, pilot, execute-confirmatory; "
            "load-confirmatory is a load-only profile"
        )
    if phase_component == "execute-confirmatory":
        # Validate every frozen protocol field before normalising inputs or
        # creating a run namespace. Validation retains reduced-matrix semantics.
        validate_confirmatory_config(config)
    scenario_values = _normalise_scenarios(scenarios)
    seed_values = _normalise_seeds(seeds)
    unknown_seeds = sorted(set(seed_values) - set(config.seeds))
    if unknown_seeds:
        raise ValueError(
            "seeds are outside the configured protocol: "
            f"{unknown_seeds}"
        )
    policy_values = _normalise_policies(policies, config)
    policy_names = tuple(
        value.name if isinstance(value, DispatchPolicy) else value
        for value in policy_values
    )
    if phase_component == "execute-confirmatory":
        if any(isinstance(value, DispatchPolicy) for value in policy_values):
            raise ValueError("execute-confirmatory requires canonical policy names, not policy objects")
        canonical_metadata = _validate_confirmatory_matrix(
            scenario_values,
            seed_values,
            policy_names,
            config,
        )
    else:
        canonical_metadata = {
            scenario.scenario_id: _derived_scenario_metadata(scenario)
            for scenario in scenario_values
        }
    if not isinstance(runs_root, (str, Path)):
        raise TypeError("runs_root must be a string or Path")
    root = Path(runs_root)
    checksum = config_hash(config)
    if not isinstance(controls, ExecutionControls) or not isinstance(event_latents, EventLatentLedger):
        raise TypeError("explicit ExecutionControls and EventLatentLedger are required")
    if controls.event_latents_sha256 != event_latents.event_latents_sha256:
        raise ValueError("controls do not identify the consumed event-latent ledger")
    instance_map = {}
    for instance in instances:
        if not isinstance(instance, FrozenInstance):
            raise TypeError("instances must contain FrozenInstance values")
        key = (instance.scenario_id, instance.seed)
        if key in instance_map:
            raise ValueError(f"duplicate frozen instance for {key}")
        instance_map[key] = instance
    expected_keys = {(scenario.scenario_id, seed) for scenario in scenario_values for seed in seed_values}
    if set(instance_map) != expected_keys:
        raise ValueError("materialized instances must match the requested matrix exactly")
    expected_inputs = {}
    for scenario in scenario_values:
        for seed in seed_values:
            instance = instance_map[(scenario.scenario_id, seed)]
            if (len(instance.trucks) != scenario.truck_count
                    or instance.scenario_index != scenario.scenario_index):
                raise ValueError("frozen instance dimensions do not match requested scenario")
            # Prove ledger membership and the controlled projection before any
            # namespace or policy is reached. Retain only its identity, once per
            # instance, for comparison with every worker result below.
            projection = derive_controlled_projection(instance, event_latents, controls)
            expected_inputs[(scenario.scenario_id, seed)] = {
                "scenario_id": scenario.scenario_id,
                "seed": seed,
                "instance_id": instance.instance_id,
                "instance_hash": instance.instance_hash,
                "execution_instance_hash": projection.instance.instance_hash,
                "dataset_root_hash": controls.source_dataset_root_hash,
                "control_hash": controls.control_hash,
                "controlled_view_hash": projection.controlled_view_hash,
                "event_overlay_hash": projection.event_overlay_hash,
            }
    commit, checkout_clean = _git_metadata()
    if phase_component in {"pilot", "execute-confirmatory"}:
        from .capacity import require_capacity
        require_capacity(capacity_receipt, workload=workload, requirements=config.capacity, run_root=root)
    run_dir = create_run_directory(
        root,
        phase_component,
        commit,
        checksum,
        now_utc=now_utc,
    )
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "metrics").mkdir()

    result_rows: list[dict[str, Any]] = []
    log_entries: dict[str, dict[str, Any]] = {}
    for scenario in scenario_values:
        for seed in seed_values:
            for policy_name, policy_value in zip(policy_names, policy_values, strict=True):
                instance = instance_map[(scenario.scenario_id, seed)]
                result = run_day(instance, policy_value, controls, event_latents)
                expected = {**expected_inputs[(scenario.scenario_id, seed)],
                            "policy_name": policy_name, "controls": controls}
                mismatches = {
                    field: {"expected": value, "observed": getattr(result, field)}
                    for field, value in expected.items() if getattr(result, field) != value
                }
                if mismatches:
                    raise RuntimeError(
                        "worker result does not identify its consumed frozen input: "
                        f"instance_id={instance.instance_id}; policy={policy_name}; mismatches={mismatches}"
                    )
                log_filename = (
                    f"{scenario.scenario_id}__seed_{seed}__policy_{policy_name}.jsonl"
                )
                _path_component("log filename", log_filename)
                log_path = logs_dir / log_filename
                log_text, initial_hash, final_hash, replay_hash, a2_complete, _ = _log_lines(
                    result,
                    run_id=run_dir.name,
                    checksum=checksum,
                )
                _atomic_write_text(log_path, log_text)
                persisted_metrics = compute_policy_day_metrics(log_path)
                metrics_file = f"metrics/{log_filename.removesuffix('.jsonl')}.json"
                metrics_text = _canonical_json(persisted_metrics.to_dict()) + "\n"
                _atomic_write_text(run_dir / metrics_file, metrics_text)
                metrics_digest = hashlib.sha256(metrics_text.encode("utf-8")).hexdigest()
                log_digest = hashlib.sha256(log_text.encode("utf-8")).hexdigest()
                log_entries[log_filename] = {
                    "path": f"logs/{log_filename}",
                    "sha256": log_digest,
                    "run_id": run_dir.name,
                    "scenario_id": scenario.scenario_id,
                    "seed": seed,
                    "policy": policy_name,
                    "config_hash": checksum,
                    **{field: getattr(result, field) for field in INPUT_IDENTITY_FIELDS},
                }
                result_rows.append(
                    _result_row(
                        result,
                        checksum=checksum,
                        scenario_metadata=canonical_metadata[scenario.scenario_id],
                        log_file=log_filename,
                        log_sha256=log_digest,
                        initial_hash=initial_hash,
                        final_hash=final_hash,
                        replay_hash=replay_hash,
                        a2_fields_complete=a2_complete,
                        persisted_metrics=persisted_metrics,
                        metrics_file=metrics_file,
                        metrics_sha256=metrics_digest,
                    )
                )

    expected_rows = len(scenario_values) * len(seed_values) * len(policy_values)
    if len(result_rows) != expected_rows:
        raise RuntimeError(
            f"matrix cardinality mismatch before persistence: expected {expected_rows}, "
            f"observed {len(result_rows)}"
        )
    manifest = _manifest_for_run(
        config,
        run_dir=run_dir,
        phase=phase_component,
        commit=commit,
        checkout_clean=checkout_clean,
        scenarios=scenario_values,
        seeds=seed_values,
        policies=policy_names,
        log_entries=log_entries,
        now_utc=now_utc,
    )
    manifest["schema_version"] = 4
    manifest["input_provenance"] = dict(input_provenance)
    manifest["non_confirmatory"] = phase_component != "execute-confirmatory"
    _atomic_write_text(run_dir / "results.csv", _csv_text(result_rows))
    _atomic_write_json(run_dir / "manifest.json", manifest)

    # Import lazily to keep experiment.py usable while the audit module imports
    # the canonical result/log schema constants above.
    from .audit import audit_run

    report = audit_run(run_dir)
    if not report.overall_pass:
        from .audit import AuditError

        raise AuditError(
            "automated audit failed before releasing run bundle: "
            f"run_id={run_dir.name} diagnostics={report.diagnostics!r}"
        )
    return load_run_bundle(run_dir)


def load_run_bundle(run_dir: str | Path) -> RunBundle:
    """Load a persisted bundle without discovering or substituting another run."""

    if not isinstance(run_dir, (str, Path)):
        raise TypeError("run_dir must be a string or Path")
    directory = Path(run_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"run directory does not exist: {directory}")
    manifest_path = directory / "manifest.json"
    results_path = directory / "results.csv"
    logs_dir = directory / "logs"
    audit_path = directory / "audit.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest root must be an object")
    rows = _read_results_csv(results_path)
    if not logs_dir.is_dir():
        raise FileNotFoundError(f"decision log directory does not exist: {logs_dir}")
    return RunBundle(
        run_dir=directory,
        manifest_path=manifest_path,
        results_path=results_path,
        logs_dir=logs_dir,
        audit_path=audit_path,
        results=rows,
        manifest=manifest,
    )


__all__ = [
    "EXECUTION_PHASES",
    "LOG_REQUIRED_FIELDS",
    "RESULT_HEADERS",
    "RunBundle",
    "load_run_bundle",
    "run_experiment_matrix",
    "run_validation_matrix",
]
