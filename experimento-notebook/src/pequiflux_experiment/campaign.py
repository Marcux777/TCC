"""Full notebook campaign: fixed phases, descriptive diagnostics and stress grid.

No sampling, retries, parameter selection or promotion into H1 occurs here.
Scientific execution continues to use the frozen-input and capacity boundaries.
"""

from decimal import Decimal
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from .audit import audit_run
from .capacity import CapacityGateError, inspect_capacity
from .config import canonical_bytes, config_hash, factorial_scenarios
from .dataset import select_pilot_configurations
from .domain import ExecutionControls
from .experiment import load_run_bundle, run_experiment_matrix, _atomic_write_json
from .profiles import ConfirmatoryWorkload, phase_policies, sensitivity_bootstrap
from .statistics import BOOTSTRAP_ITERATIONS, _stable_seed, PRIMARY_COMPARATORS


def campaign_plan(config):
    """Quantities are planned work, not measurements or completed runs."""
    scenarios = factorial_scenarios(config)
    pilot = select_pilot_configurations(config)
    return pd.DataFrame([
        {"phase": phase, "controls": controls, "scenarios": len(selected),
         "seeds": len(config.seeds), "policies": len(phase_policies(config, phase)),
         "policy_days": controls * len(selected) * len(config.seeds) * len(phase_policies(config, phase)),
         "output_lower_bound_bytes": controls * 32768 * sum(s.truck_count for s in selected)
             * len(config.seeds) * len(phase_policies(config, phase))}
        for phase, controls, selected in (
            ("pilot", 1, pilot), ("execute-confirmatory", 1, scenarios),
            ("sensitivity", 54, scenarios), ("exploratory", 1, scenarios))
    ])


def principal_storage_requirement(config, output_parent):
    """Necessary lower bound of the existing gate, before expensive generation.

    This does not issue a capacity receipt or replace the runtime inspection.
    Dataset bytes are still unknown and must be added by the real workload.
    """
    plan = campaign_plan(config).set_index("phase")
    output_bytes = int(plan.loc["execute-confirmatory", "output_lower_bound_bytes"])
    required = math.ceil(config.capacity.disk_margin * output_bytes) + config.capacity.disk_reserve_gib * 1024**3
    free = shutil.disk_usage(Path(output_parent).resolve(strict=True)).free
    return {"required_bytes_without_dataset": required, "free_bytes": free,
            "decision": "BLOCKED" if free < required else "RUNTIME_INSPECTION_REQUIRED",
            "note": "Necessary principal gate only; dataset, other phases and runtime checks remain."}


def baseline_controls(dataset, config):
    return ExecutionControls.build(ordinary_window=config.ordinary_window,
        buffer_capacity=config.buffer_capacity, threshold_multiplier=Decimal("1.00"),
        intensity="base", source_dataset_root_hash=dataset.dataset_hash,
        event_latents_sha256=dataset.event_latents.event_latents_sha256)


def stress_grid(dataset):
    """Complete controls in the prospective H0/buffer/threshold/intensity order."""
    return tuple(ExecutionControls.build(ordinary_window=h, buffer_capacity=b,
        threshold_multiplier=Decimal(t), intensity=i,
        source_dataset_root_hash=dataset.dataset_hash,
        event_latents_sha256=dataset.event_latents.event_latents_sha256)
        for h, b, t, i in product((4, 6, 8), (8, 12, 16),
                                  ("0.75", "1.00", "1.25"), ("base", "high")))


def run_phase(dataset, config, runs_root, *, phase, controls):
    workload = ConfirmatoryWorkload.from_dataset(dataset, config, phase=phase,
        controls=controls if phase in {"sensitivity", "exploratory"} else None)
    receipt = inspect_capacity(workload, config.capacity, runs_root)
    if receipt.decision != "PASS":
        raise CapacityGateError(f"capacity blocked; original receipt: {receipt.path}")
    return run_experiment_matrix(
        select_pilot_configurations(config) if phase == "pilot" else factorial_scenarios(config),
        config.seeds, phase_policies(config, phase), config, runs_root,
        phase=phase, dataset_path=dataset.path,
        expected_dataset_root_hash=dataset.dataset_hash, controls=controls,
        capacity_receipt=receipt)


def _bootstrap_median(values, seed):
    # Same paired 5,000 resamples; batches bound peak allocation, not sample size.
    rng = np.random.default_rng(seed)
    estimates = np.empty(BOOTSTRAP_ITERATIONS)
    for start in range(0, BOOTSTRAP_ITERATIONS, 100):
        count = min(100, BOOTSTRAP_ITERATIONS - start)
        indices = rng.integers(0, len(values), size=(count, len(values)))
        estimates[start:start + count] = np.median(values[indices], axis=1)
    return np.percentile(estimates, [2.5, 97.5]).tolist()


def paired_diagnostics(frame, *, reference="lexicographic", comparators=PRIMARY_COMPARATORS,
                       strata=True, bootstrap=None):
    """Descriptive paired effects; never p-values, selection, or an H1 decision."""
    keys = ["scenario_id", "seed"]
    if frame.duplicated(keys + ["policy"]).any():
        raise ValueError("INVALID_INPUT: duplicate policy-day")
    reports = []
    groups = frame.groupby("stratum", sort=True) if strata else [("all", frame)]
    for stratum, group in groups:
        ref = group[group.policy == reference].set_index(keys).sort_index()
        if ref.empty:
            raise ValueError("INVALID_INPUT: empty reference panel")
        for comparator in comparators:
            comp = group[group.policy == comparator].set_index(keys).sort_index()
            if not ref.index.equals(comp.index):
                raise ValueError("INVALID_INPUT: incomplete paired panel")
            for identity in ("config_hash", "dataset_root_hash", "instance_hash", "execution_instance_hash", "control_hash"):
                if not ref[identity].equals(comp[identity]):
                    raise ValueError(f"INVALID_INPUT: paired {identity} differs")
            denominator = comp.p95_wait_minutes.to_numpy(dtype=float)
            if np.any(denominator <= 0):
                raise ValueError("INVALID_INPUT: non-positive p95 denominator")
            gain = np.array([float((Decimal(str(c)) - Decimal(str(r))) / Decimal(str(c)))
                             for c, r in zip(comp.p95_wait_minutes, ref.p95_wait_minutes, strict=True)])
            guard = (ref.throughput.to_numpy(dtype=float) - comp.throughput.to_numpy(dtype=float)
                     + np.maximum(2, .02 * ref.total_trucks.to_numpy(dtype=float)))
            if not np.isfinite(gain).all() or not np.isfinite(guard).all():
                raise ValueError("INVALID_INPUT: non-finite paired metrics")
            seed = bootstrap["seed"] if bootstrap is not None else _stable_seed(str(stratum), comparator)
            low, high = _bootstrap_median(gain, seed)
            q1, median, q3 = np.percentile(gain, [25, 50, 75])
            reports.append({"stratum": stratum, "reference": reference, "comparator": comparator,
                "pairs": len(ref), "gain_median": median, "gain_q1": q1, "gain_q3": q3,
                "gain_iqr": q3-q1, "gain_ci95_low": low, "gain_ci95_high": high,
                "throughput_guard_median": float(np.median(guard)),
                "bootstrap_seed": seed, "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
                "bootstrap_version": bootstrap["version"] if bootstrap is not None else "pilot-descriptive.v1",
                "analysis": "descriptive_not_H1"})
    return pd.DataFrame(reports)


def analyse_pilot(bundle, config):
    audited = audit_run(bundle.run_dir)
    persisted = load_run_bundle(bundle.run_dir)
    expected = {(s.scenario_id, seed, p) for s in select_pilot_configurations(config)
                for seed in config.seeds for p in config.policies}
    observed = {(r["scenario_id"], r["seed"], r["policy"]) for r in persisted.results}
    if (not audited.overall_pass or persisted.manifest["phase"] != "pilot"
            or persisted.manifest["config_hash"] != config_hash(config)
            or observed != expected or len(persisted.results) != len(expected)):
        raise ValueError("INVALID_INPUT: pilot requires the complete audited prospective panel")
    return paired_diagnostics(pd.DataFrame(persisted.results))


def run_sensitivity(dataset, config, runs_root, output_directory, *, grid):
    expected = stress_grid(dataset)
    if tuple(grid) != expected:
        raise ValueError("sensitivity requires all 54 explicit controls in canonical order")
    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=False)
    identity = {"phase": "sensitivity", "status": "RUNNING", "expected_cells": 54,
        "source_dataset_root_hash": dataset.dataset_hash,
        "event_latents_sha256": dataset.event_latents.event_latents_sha256,
        "grid_hash": hashlib.sha256(canonical_bytes([c.to_dict() for c in expected])).hexdigest(),
        "base_control_hash": expected[26].control_hash,
        "high_control_hash": expected[27].control_hash,
        "config_hash": config_hash(config), "cells": []}
    _atomic_write_json(destination / "manifest.json", identity)
    diagnostics = []
    try:
        for index, controls in enumerate(expected):
            bundle = run_phase(dataset, config, runs_root, phase="sensitivity", controls=controls)
            bootstrap = sensitivity_bootstrap(controls)
            table = paired_diagnostics(pd.DataFrame(bundle.results), strata=False, bootstrap=bootstrap)
            projection_rows = []
            for row in bundle.results:
                with (bundle.logs_dir / row["log_file"]).open(encoding="utf-8") as stream:
                    start = json.loads(stream.readline())
                if start["event_kind"] != "RUN_STARTED":
                    raise ValueError("INVALID_INPUT: first log event is not RUN_STARTED")
                projection_rows.append({"scenario_id": row["scenario_id"], "seed": row["seed"],
                    "policy": row["policy"], "instance_hash": row["instance_hash"],
                    "source_dataset_root_hash": row["dataset_root_hash"],
                    "event_latents_sha256": start["payload"]["event_latents_sha256"],
                    "controlled_view_hash": start["payload"]["controlled_view_hash"],
                    "event_overlay_hash": start["payload"]["event_overlay_hash"]})
            projection_path = destination / f"projections-{index:02d}.csv"
            pd.DataFrame(projection_rows).to_csv(projection_path, index=False)
            joint = bool(((table.gain_median > 0) & (table.throughput_guard_median > 0)).all())
            table.insert(0, "cell", index)
            table.insert(1, "control_hash", controls.control_hash)
            table.to_csv(destination / f"cell-{index:02d}.csv", index=False)
            diagnostics.append(table)
            identity["cells"].append({"cell": index, "run_id": bundle.run_id,
                "run_directory": str(bundle.run_dir.resolve()), "controls": controls.to_dict(),
                "rows": len(bundle.results), "joint_positive": joint,
                "descriptive_bootstrap": bootstrap,
                "projections": projection_path.name,
                "projections_sha256": hashlib.sha256(projection_path.read_bytes()).hexdigest(),
                "manifest_sha256": hashlib.sha256(bundle.manifest_path.read_bytes()).hexdigest()})
            _atomic_write_json(destination / "manifest.json", identity)
    except Exception as exc:
        identity.update(status="INCOMPLETE", error=f"{type(exc).__name__}: {exc}", decision="INVALID_INPUT")
        _atomic_write_json(destination / "manifest.json", identity)
        raise
    count = sum(item["joint_positive"] for item in identity["cells"])
    identity.update(status="COMPLETE", jointly_positive_cells=count, joint_fraction=count/54,
                    decision="ROBUST" if count/54 >= .75 else "NON_ROBUST")
    pd.concat(diagnostics, ignore_index=True).to_csv(destination / "diagnostics.csv", index=False)
    _atomic_write_json(destination / "manifest.json", identity)
    return identity


def exploratory_summary(bundle, config):
    if not audit_run(bundle.run_dir).overall_pass:
        raise ValueError("exploratory analysis requires passing audit")
    persisted = load_run_bundle(bundle.run_dir)
    if persisted.manifest["phase"] != "exploratory" or persisted.manifest["config_hash"] != config_hash(config):
        raise ValueError("exploratory analysis requires matching phase/configuration")
    frame = pd.DataFrame(persisted.results)
    frame = frame.sort_values(["scenario_id", "seed", "policy"])
    bootstrap = persisted.manifest["descriptive_bootstrap"]
    records = []
    for (stratum, policy), group in frame.groupby(["stratum", "policy"], sort=True):
        for metric in ("p95_wait_minutes", "throughput", "co2_estimated_kg"):
            values = group[metric].to_numpy(dtype=float)
            if not np.isfinite(values).all():
                raise ValueError("INVALID_INPUT: non-finite exploratory metric")
            q1, median, q3 = np.percentile(values, [25, 50, 75])
            low, high = _bootstrap_median(values, bootstrap["seed"])
            records.append({"stratum": stratum, "policy": policy, "metric": metric,
                "days": len(values), "median": median, "iqr": q3-q1,
                "ci95_low": low, "ci95_high": high,
                "bootstrap_seed": bootstrap["seed"], "bootstrap_version": bootstrap["version"],
                "bootstrap_iterations": BOOTSTRAP_ITERATIONS, "analysis": "descriptive_not_H1"})
    return pd.DataFrame(records)
