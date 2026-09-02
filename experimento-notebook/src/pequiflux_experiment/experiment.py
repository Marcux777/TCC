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
from .domain import YardSnapshot
from .emulator import DayResult, run_day
from .events import EventRecord
from .manifest import build_manifest, create_run_directory
from .policies import DispatchPolicy, make_policy
from .statistics import canonical_scenario_metadata


RESULT_HEADERS: tuple[str, ...] = (
    "scenario_id",
    "seed",
    "policy",
    "config_hash",
    "stratum",
    "regime",
    "hopper_count",
    "scale_count",
    "log_file",
    "log_sha256",
    "event_count",
    "total_trucks",
    "completed_trucks",
    "throughput",
    "mean_wait_minutes",
    "p95_wait_minutes",
    "censored_wait_minutes",
    "makespan_minutes",
    "throughput_rate",
    "scale_utilization_peak",
    "hard_constraint_violations",
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
    "human_decision",
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
) -> tuple[str, ...]:
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
    return tuple(names)


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
    for key in (
        "seed",
        "event_count",
        "total_trucks",
        "hopper_count",
        "scale_count",
        "completed_trucks",
        "throughput",
        "scale_utilization_peak",
        "hard_constraint_violations",
    ):
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
    if normalised["throughput"] > normalised["completed_trucks"]:
        raise ValueError("throughput cannot exceed completed_trucks")
    for key in (
        "mean_wait_minutes",
        "p95_wait_minutes",
        "censored_wait_minutes",
        "makespan_minutes",
        "throughput_rate",
    ):
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
        "policy",
        "config_hash",
        "stratum",
        "regime",
        "log_file",
        "log_sha256",
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
        "log_sha256",
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
    human_decision: str | None = None

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
        human_decision = payload.get("decision") if isinstance(payload.get("decision"), str) else None
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
        "human_decision": human_decision,
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
                all_fields_complete = all_fields_complete and fields["human_decision"] == "accept"

        line: dict[str, Any] = {
            "run_id": run_id,
            "scenario_id": result.scenario_id,
            "seed": result.seed,
            "policy": result.policy_name,
            "config_hash": checksum,
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
) -> dict[str, Any]:
    metrics = result.metrics
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
    observed_total_trucks = metrics.get("total_trucks")
    if observed_total_trucks != expected_total_trucks:
        raise RuntimeError(
            "simulation total_trucks does not match canonical scenario metadata: "
            f"scenario_id={result.scenario_id} expected={expected_total_trucks} "
            f"observed={observed_total_trucks}"
        )
    a1_pass = (
        result.hard_constraint_violations == 0
        and int(metrics.get("hard_constraint_violations", 0)) == 0
        and result.max_scale_occupancy <= result.scenario.scale_count
    )
    row: dict[str, Any] = {
        "scenario_id": result.scenario_id,
        "seed": result.seed,
        "policy": result.policy_name,
        "config_hash": checksum,
        "stratum": scenario_metadata["stratum"],
        "regime": scenario_metadata["regime"],
        "hopper_count": scenario_metadata["hopper_count"],
        "scale_count": scenario_metadata["scale_count"],
        "log_file": log_file,
        "log_sha256": log_sha256,
        "event_count": len(result.events),
        "total_trucks": expected_total_trucks,
        "completed_trucks": int(metrics["completed_trucks"]),
        "throughput": int(metrics["throughput"]),
        "mean_wait_minutes": float(metrics["mean_wait_minutes"]),
        "p95_wait_minutes": float(metrics["p95_wait_minutes"]),
        "censored_wait_minutes": float(metrics["censored_wait_minutes"]),
        "makespan_minutes": float(metrics["makespan_minutes"]),
        "throughput_rate": float(metrics["throughput_rate"]),
        "scale_utilization_peak": int(result.max_scale_occupancy),
        "hard_constraint_violations": int(result.hard_constraint_violations),
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
        }
    )
    return manifest


def run_experiment_matrix(
    scenarios: Iterable[ScenarioConfig],
    seeds: Iterable[int],
    policies: Iterable[str | DispatchPolicy],
    config: ExperimentConfig,
    runs_root: str | Path,
    phase: str = "validation",
    now_utc: Any = None,
) -> RunBundle:
    """Execute and persist one deterministic paired matrix.

    No result is selected from an existing run and no cell is retried.  A
    collision at the namespace boundary or a failure in any cell propagates
    immediately with its context.
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
        # creating a run namespace.  Validation and pilot intentionally retain
        # their reduced-matrix semantics.
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
    if phase_component == "execute-confirmatory":
        canonical_metadata = _validate_confirmatory_matrix(
            scenario_values,
            seed_values,
            policy_values,
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
    commit, checkout_clean = _git_metadata()
    run_dir = create_run_directory(
        root,
        phase_component,
        commit,
        checksum,
        now_utc=now_utc,
    )
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=False)

    result_rows: list[dict[str, Any]] = []
    log_entries: dict[str, dict[str, Any]] = {}
    for scenario in scenario_values:
        for seed in seed_values:
            for policy_name in policy_values:
                result = run_day(scenario, seed, make_policy(policy_name))
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
                log_digest = hashlib.sha256(log_text.encode("utf-8")).hexdigest()
                log_entries[log_filename] = {
                    "path": f"logs/{log_filename}",
                    "sha256": log_digest,
                    "run_id": run_dir.name,
                    "scenario_id": scenario.scenario_id,
                    "seed": seed,
                    "policy": policy_name,
                    "config_hash": checksum,
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
        policies=policy_values,
        log_entries=log_entries,
        now_utc=now_utc,
    )
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
]
