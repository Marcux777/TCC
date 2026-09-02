from pathlib import Path
import csv
import hashlib
import json

import pytest

from pequiflux_experiment.config import POLICY_NAMES, load_config
from pequiflux_experiment.emulator import run_day, tiny_scenario
from pequiflux_experiment.experiment import (
    _log_lines,
    load_run_bundle,
    run_experiment_matrix,
)
from pequiflux_experiment.audit import AuditError, AuditReport, audit_run
from pequiflux_experiment.policies import make_policy
import pequiflux_experiment.audit as audit_module


PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


def build_validation_bundle(tmp_path: Path):
    return run_experiment_matrix(
        scenarios=[tiny_scenario()],
        seeds=[101, 102],
        policies=POLICY_NAMES,
        config=load_config(CONFIG_PATH),
        runs_root=tmp_path,
        phase="validation",
        now_utc="2026-09-01T12:00:00Z",
    )


def test_validation_bundle_is_complete_replayable_and_auditable(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)

    assert len(bundle.results) == 10
    assert bundle.manifest_path.exists()
    assert bundle.results_path.exists()
    assert bundle.logs_dir.exists()
    assert len(tuple(bundle.logs_dir.glob("*.jsonl"))) == 10

    report = audit_run(bundle.run_dir)

    assert report.a1_pass is True
    assert report.a2_structural_pass is True
    assert report.a2_human_audit_pending is True
    assert report.replay_pass is True


def test_missing_log_fails_without_fallback(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)
    missing_log = next(bundle.logs_dir.glob("*.jsonl"))
    missing_name = missing_log.name
    missing_log.unlink()

    with pytest.raises(AuditError, match=f"missing decision log.*{missing_name}") as exc_info:
        audit_run(bundle.run_dir)
    assert isinstance(exc_info.value.__cause__, FileNotFoundError)


def _rewrite_log_and_receipts(bundle, mutate):
    log_path = next(bundle.logs_dir.glob("*.jsonl"))
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    mutate(lines)
    content = "\n".join(
        json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for line in lines
    ) + "\n"
    log_path.write_text(content, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    manifest_path = bundle.manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    descriptor = manifest["decision_logs"][log_path.name]
    descriptor["sha256"] = digest
    manifest["logs"][log_path.name]["sha256"] = digest
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    rows = list(csv.DictReader(bundle.results_path.open("r", encoding="utf-8", newline="")))
    for row in rows:
        if row["log_file"] == log_path.name:
            row["log_sha256"] = digest
    with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_run_matrix_rejects_failed_automated_audit_even_when_human_pending(
    tmp_path: Path, monkeypatch
):
    failed_report = AuditReport(
        run_dir=tmp_path,
        expected_rows=10,
        observed_rows=10,
        pair_key_unique=True,
        config_hashes=("0" * 64,),
        log_count_expected=10,
        log_count_observed=10,
        log_sha256_pass=True,
        headers_pass=True,
        monotonic_time_pass=True,
        a2_fields_pass=False,
        a1_pass=True,
        replay_pass=True,
        a2_structural_pass=False,
        a2_human_audit_pending=True,
    )
    monkeypatch.setattr(audit_module, "audit_run", lambda _run_dir: failed_report)

    with pytest.raises(AuditError, match="automated audit"):
        build_validation_bundle(tmp_path)


def test_audit_rejects_incoherent_enriched_decision_fields(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)

    def mutate(lines):
        decision = next(line for line in lines if line["event_kind"] == "DECISION_RECORDED")
        decision["selection"]["truck_id"] = "T-999"

    _rewrite_log_and_receipts(bundle, mutate)
    with pytest.raises(AuditError, match="A2|decision|selection"):
        audit_run(bundle.run_dir)


def test_audit_reconciles_event_count_with_persisted_log(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)
    rows = list(csv.DictReader(bundle.results_path.open("r", encoding="utf-8", newline="")))
    rows[0]["event_count"] = str(int(rows[0]["event_count"]) + 1)
    with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(AuditError, match="event_count"):
        audit_run(bundle.run_dir)


@pytest.mark.parametrize(
    "metric",
    ["mean_wait_minutes", "p95_wait_minutes", "censored_wait_minutes"],
)
def test_audit_reconciles_wait_metrics_with_persisted_log(tmp_path: Path, metric: str):
    bundle = build_validation_bundle(tmp_path)
    rows = list(csv.DictReader(bundle.results_path.open("r", encoding="utf-8", newline="")))
    rows[0][metric] = str(float(rows[0][metric]) + 1.0)
    with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(AuditError, match=metric):
        audit_run(bundle.run_dir)


def test_results_persist_censored_wait_metric_and_roundtrip(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)

    with bundle.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert "censored_wait_minutes" in rows[0]

    loaded = load_run_bundle(bundle.run_dir)
    assert "censored_wait_minutes" in loaded.results[0]


def test_audit_derives_accumulated_wait_and_active_horizon(tmp_path: Path):
    scenario = tiny_scenario(truck_count=120, hoppers=1, scales=1)
    result = run_day(scenario, 101, make_policy("fifo_strict"))
    log_text, *_ = _log_lines(
        result,
        run_id="active-horizon",
        checksum="0" * 64,
    )
    log_path = tmp_path / "active-horizon.jsonl"
    log_path.write_text(log_text, encoding="utf-8", newline="\n")

    details = audit_module._replay_log(log_path)
    assert details.final_snapshot.clock == 720.0
    assert any(resource.status == "busy" for resource in details.final_snapshot.resources.values())

    derived = audit_module._derived_log_metrics(details)
    assert derived["mean_wait_minutes"] == result.metrics["mean_wait_minutes"]
    assert derived["p95_wait_minutes"] == result.metrics["p95_wait_minutes"]
    assert derived["censored_wait_minutes"] == result.metrics["censored_wait_minutes"]
    first_arrival = min(
        float(event.payload["arrival_time"])
        for event in result.events
        if event.kind == "TRUCK_ARRIVED"
    )
    last_completion = max(
        float(event.time)
        for event in result.events
        if event.kind == "SERVICE_COMPLETED"
    )
    expected_makespan = round(last_completion - first_arrival, 12)
    expected_rate = round(result.completed_trucks / expected_makespan, 12)
    assert derived["makespan_minutes"] == expected_makespan
    assert result.metrics["makespan_minutes"] == expected_makespan
    assert derived["throughput_rate"] == expected_rate
    assert result.metrics["throughput_rate"] == expected_rate


@pytest.mark.parametrize(
    ("metric", "delta"),
    [
        ("mean_wait_minutes", 1e-13),
        ("mean_wait_minutes", 1e-12),
        ("p95_wait_minutes", 1e-13),
    ],
)
def test_audit_rejects_sub_tolerance_wait_metric_adulteration(
    tmp_path: Path, metric: str, delta: float
):
    bundle = build_validation_bundle(tmp_path)
    rows = list(csv.DictReader(bundle.results_path.open("r", encoding="utf-8", newline="")))
    rows[0][metric] = str(float(rows[0][metric]) + delta)
    with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(AuditError, match=metric):
        audit_run(bundle.run_dir)


def test_audit_rejects_non_finite_persisted_metric(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)
    rows = list(csv.DictReader(bundle.results_path.open("r", encoding="utf-8", newline="")))
    rows[0]["mean_wait_minutes"] = "nan"
    with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(AuditError, match="finite|NaN|metric"):
        audit_run(bundle.run_dir)


def test_audit_requires_explicit_consistent_human_audit_status(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)
    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    del manifest["human_audit_status"]
    bundle.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(AuditError, match="human_audit_status"):
        audit_run(bundle.run_dir)


def test_audit_cross_checks_log_descriptor_identity(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)
    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    log_name = next(iter(manifest["decision_logs"]))
    manifest["decision_logs"][log_name]["policy"] = "wrong-policy"
    bundle.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(AuditError, match="identity|descriptor|policy"):
        audit_run(bundle.run_dir)


def test_audit_validates_matrix_types_uniqueness_and_product(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)
    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    manifest["matrix"]["seeds"] = [101, 102, 101]
    bundle.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(AuditError, match="matrix|unique|seeds"):
        audit_run(bundle.run_dir)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("stratum", "high"),
        ("regime", "peak"),
        ("total_trucks", 999),
        ("hopper_count", 99),
        ("scale_count", 99),
    ],
)
def test_audit_rejects_result_metadata_that_disagrees_with_manifest(
    tmp_path: Path, field: str, replacement: object
):
    bundle = build_validation_bundle(tmp_path)
    rows = list(csv.DictReader(bundle.results_path.open("r", encoding="utf-8", newline="")))
    rows[0][field] = str(replacement)
    with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(AuditError, match=f"canonical scenario metadata.*{field}"):
        audit_run(bundle.run_dir)


def test_run_manifest_contains_canonical_scenario_metadata_and_resolved_versions(
    tmp_path: Path,
):
    bundle = build_validation_bundle(tmp_path)
    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    scenario_id = bundle.results[0]["scenario_id"]
    scenario = next(
        item for item in manifest["matrix"]["scenarios"] if item["scenario_id"] == scenario_id
    )

    assert {
        "scenario_id",
        "stratum",
        "regime",
        "total_trucks",
        "hopper_count",
        "scale_count",
    } <= set(scenario)
    assert all(bundle.results[0][field] == scenario[field] for field in (
        "scenario_id",
        "stratum",
        "regime",
        "total_trucks",
        "hopper_count",
        "scale_count",
    ))

    from importlib.metadata import version

    expected_distributions = {
        "numpy",
        "pandas",
        "scipy",
        "pyarrow",
        "matplotlib",
        "pytest",
        "nbformat",
        "nbclient",
        "nbconvert",
        "ipykernel",
        "pequiflux-experiment",
    }
    dependencies = manifest["dependencies"]
    assert set(dependencies) >= expected_distributions
    assert all(isinstance(dependencies[name], str) and dependencies[name] == version(name)
               for name in expected_distributions)
