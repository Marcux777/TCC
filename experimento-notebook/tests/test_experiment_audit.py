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
    run_validation_matrix,
)
from pequiflux_experiment.audit import AuditError, AuditReport, audit_run
from pequiflux_experiment.policies import make_policy
from pequiflux_experiment.dispatch import DispatchPolicy
import pequiflux_experiment.audit as audit_module


PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


@pytest.mark.parametrize("phase", ["validation", "pilot", "execute-confirmatory"])
def test_scientific_executor_requires_frozen_inputs_before_namespace(tmp_path, monkeypatch, phase):
    from pequiflux_experiment.config import factorial_scenarios
    import pequiflux_experiment.experiment as execution

    config = load_config(CONFIG_PATH)
    def forbidden(*args, **kwargs):
        raise AssertionError("namespace or worker reached without frozen inputs")
    monkeypatch.setattr(execution, "create_run_directory", forbidden)
    monkeypatch.setattr(execution, "run_day", forbidden)
    with pytest.raises(ValueError, match="dataset_path.*expected_dataset_root_hash"):
        run_experiment_matrix(
            factorial_scenarios(config), config.seeds, config.policies,
            config, tmp_path / "runs", phase=phase,
        )
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("phase", ["pilot", "execute-confirmatory"])
@pytest.mark.parametrize("missing", ["face", "approved_face", "capacity"])
def test_scientific_prerequisites_cannot_be_bypassed_by_direct_api(tmp_path, monkeypatch, phase, missing):
    from types import SimpleNamespace
    from pequiflux_experiment.config import factorial_scenarios, config_hash
    from pequiflux_experiment.validation_fixtures import build_validation_fixture
    import pequiflux_experiment.dataset as datasets
    import pequiflux_experiment.face_validation as faces
    import pequiflux_experiment.experiment as execution

    config = load_config(CONFIG_PATH)
    fixture = build_validation_fixture()
    # The loader itself has separate full-payload tests. Here its validated
    # output is held fixed to isolate the executor's human/capacity boundary.
    dataset = SimpleNamespace(manifest={"config_hash": config_hash(config)},
                              instances=(), path=tmp_path,
                              event_latents=fixture.event_latents)
    monkeypatch.setattr(datasets, "load_frozen_dataset", lambda *args, **kwargs: dataset)
    def forbidden(*args, **kwargs):
        raise AssertionError("namespace or worker reached without prerequisites")
    monkeypatch.setattr(execution, "create_run_directory", forbidden)
    monkeypatch.setattr(execution, "run_day", forbidden)
    if missing == "capacity":
        monkeypatch.setattr(faces, "validate_face_validation_receipt",
                            lambda *args: SimpleNamespace(approved=True))
    scenarios = datasets.select_pilot_configurations(config) if phase == "pilot" else factorial_scenarios(config)
    message = {"face": "face_receipt_path", "approved_face": "FACE_VALIDATION=PENDING",
               "capacity": "capacity_receipt"}[missing]
    with pytest.raises(ValueError, match=message):
        run_experiment_matrix(
            scenarios, config.seeds, config.policies, config, tmp_path / "runs", phase,
            dataset_path=tmp_path, expected_dataset_root_hash=fixture.controls.source_dataset_root_hash,
            controls=fixture.controls,
            face_receipt_path=None if missing == "face" else PROJECT_ROOT / "inputs/face_validation_receipt.json",
        )
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("phase", ["validation", "execute-confirmatory"])
def test_matrix_preserves_custom_policy_or_rejects_it_before_confirmatory_execution(
    tmp_path: Path, phase: str
):
    class FailingPolicy(DispatchPolicy):
        name = "fixed_score"

        def rank_key(self, candidate, context, candidates=()):
            raise RuntimeError("custom policy execution failed")

    expected_error = ValueError if phase == "execute-confirmatory" else RuntimeError
    message = "canonical policy names" if phase == "execute-confirmatory" else "custom policy execution failed"
    with pytest.raises(expected_error, match=message):
        if phase == "validation":
            from pequiflux_experiment.validation_fixtures import build_validation_inputs
            instances, controls, latents = build_validation_inputs([tiny_scenario()], [101])
            run_validation_matrix(instances, [FailingPolicy()], load_config(CONFIG_PATH),
                                  tmp_path, controls=controls, event_latents=latents)
        else:
            run_experiment_matrix([tiny_scenario()], [101], [FailingPolicy()],
                                  load_config(CONFIG_PATH), tmp_path, phase=phase)
    if phase == "execute-confirmatory":
        assert not tuple(tmp_path.iterdir())


def build_validation_bundle(tmp_path: Path):
    from pequiflux_experiment.validation_fixtures import build_validation_inputs
    instances, controls, latents = build_validation_inputs([tiny_scenario()], [101, 102])
    return run_validation_matrix(
        instances=instances,
        policies=POLICY_NAMES,
        config=load_config(CONFIG_PATH),
        runs_root=tmp_path,
        controls=controls,
        event_latents=latents,
        now_utc="2026-09-01T12:00:00Z",
    )


def test_validation_bundle_is_complete_replayable_and_auditable(tmp_path: Path):
    bundle = build_validation_bundle(tmp_path)

    assert len(bundle.results) == 10
    assert bundle.manifest_path.exists()
    assert bundle.results_path.exists()
    assert bundle.logs_dir.exists()
    assert len(tuple(bundle.logs_dir.glob("*.jsonl"))) == 10
    from pequiflux_experiment.experiment import INPUT_IDENTITY_FIELDS
    for seed in (101, 102):
        paired = [row for row in bundle.results if row["seed"] == seed]
        assert {row["policy"] for row in paired} == set(POLICY_NAMES)
        for field in INPUT_IDENTITY_FIELDS:
            assert len({row[field] for row in paired}) == 1, field

    report = audit_run(bundle.run_dir)

    assert report.a1_pass is True
    assert report.a2_structural_pass is True
    assert report.a2_human_audit_pending is True
    assert report.replay_pass is True
    assert bundle.manifest["schema_version"] == 4
    assert bundle.manifest["operator_mode"] == "synthetic_auto_accept"
    assert report.to_dict()["global_acceptance_status"] == "pending"
    assert report.to_dict()["acceptance_scope"] == "automated_structural_checks_only"
    from pequiflux_experiment.export import export_metrics
    paths = export_metrics(bundle, tmp_path / "descriptive")
    with paths["table_metrics.csv"].open(encoding="utf-8", newline="") as handle:
        exported = list(csv.DictReader(handle))
    assert len(exported) == 10
    assert float(exported[0]["co2_estimated_kg"]) == bundle.results[0]["co2_estimated_kg"]
    assert paths["table_metrics_resources.csv"].is_file()
    assert paths["table_metrics_trucks.csv"].is_file()
    with paths["table_metrics_resource_classes.csv"].open(encoding="utf-8", newline="") as handle:
        classes = list(csv.DictReader(handle))
    assert len(classes) == 30
    assert float(classes[0]["net_utilization"]) == round(float(classes[0]["busy_minutes"]) / float(classes[0]["available_minutes"]), 12)
    for row in classes:
        assert float(row["gross_idle_fraction"]) == round(float(row["idle_minutes"]) / float(row["gross_minutes"]), 12)
    for filename in ("table_metrics_by_scenario.csv", "table_metrics_by_stratum.csv"):
        with paths[filename].open(encoding="utf-8", newline="") as handle:
            pooled = list(csv.DictReader(handle))
        for row in pooled:
            assert float(row["gross_idle_fraction_pooled"]) == round(
                float(row["resource_idle_minutes_total"]) / float(row["resource_gross_minutes_total"]), 12,
            )
    metric_path = bundle.run_dir / bundle.results[0]["metrics_file"]
    metric_payload = json.loads(metric_path.read_text(encoding="utf-8"))
    with paths["table_metric_catalog.csv"].open(encoding="utf-8", newline="") as handle:
        catalog_rows = list(csv.DictReader(handle))
    catalog = {}
    for row in catalog_rows:
        assert int(row["metrics_schema_version"]) == metric_payload["schema_version"]
        catalog.setdefault(row["namespace"], {})[row["metric"]] = {
            name: row[name] for name in ("definition", "unit", "population", "window")
        }
    assert catalog == metric_payload["definitions"]["catalog"]
    with paths["table_metric_assumptions.csv"].open(encoding="utf-8", newline="") as handle:
        assumptions_rows = list(csv.DictReader(handle))
    assumptions = {}
    for row in assumptions_rows:
        assumptions.setdefault(row["section"], {})[row["key"]] = json.loads(row["value_json"])
    assert assumptions == {key: metric_payload["definitions"][key] for key in ("conventions", "co2_assumptions")}
    del metric_payload["definitions"]["co2_assumptions"]["engine_on_fraction"]
    metric_path.write_text(json.dumps(metric_payload), encoding="utf-8")
    from pequiflux_experiment.export import _metric_frames
    with pytest.raises(ValueError, match="definition contract"):
        _metric_frames(bundle)


@pytest.mark.parametrize("forgery", ["secondary_scalar", "secondary_details", "human_approval"])
def test_audit_rejects_secondary_metric_and_human_approval_forgery(tmp_path, forgery):
    bundle = build_validation_bundle(tmp_path)
    if forgery == "secondary_scalar":
        rows = [dict(row) for row in bundle.results]
        rows[0]["co2_estimated_kg"] += 1
        from pequiflux_experiment.experiment import _csv_text
        bundle.results_path.write_text(_csv_text(rows), encoding="utf-8")
        expected = "co2_estimated_kg.*reconcile"
    elif forgery == "secondary_details":
        metric_path = bundle.run_dir / bundle.results[0]["metrics_file"]
        payload = json.loads(metric_path.read_text(encoding="utf-8"))
        payload["resources"][0]["busy_minutes"] += 1
        metric_path.write_text(json.dumps(payload), encoding="utf-8")
        expected = "metrics artifact SHA-256"
    else:
        manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
        manifest["human_audit_status"] = "complete"
        manifest["a2"]["human_audit_status"] = "complete"
        bundle.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        expected = "complete requires a verified human review"
    with pytest.raises(AuditError, match=expected):
        audit_run(bundle.run_dir)


def test_audit_reconstructs_metrics_without_calling_the_producer(tmp_path, monkeypatch):
    bundle = build_validation_bundle(tmp_path)
    import pequiflux_experiment.metrics as producer

    def forbidden(*args, **kwargs):
        raise AssertionError("auditor called the metric producer")

    monkeypatch.setattr(producer, "compute_policy_day_metrics", forbidden)
    assert audit_run(bundle.run_dir).replay_pass


def test_audit_independently_reconstructs_complete_analytic_metrics(tmp_path):
    from types import SimpleNamespace
    from test_metrics import _persisted_day
    from pequiflux_experiment.events import EventRecord
    from pequiflux_experiment.metrics import METRIC_SCALAR_FIELDS

    path, rows = _persisted_day(tmp_path)
    details = SimpleNamespace(events=tuple(EventRecord.from_dict(row) for row in rows), log_path=path)
    derived = audit_module._derived_log_metrics(details)
    expected = {
        "event_count": 32, "total_trucks": 2, "completed_trucks": 1, "remaining_trucks": 1,
        "throughput": 1, "throughput_per_hour": round(1/12, 12), "horizon_minutes": 720,
        "mean_wait_minutes": 356, "p50_wait_minutes": 356, "p95_wait_minutes": 710,
        "iqr_wait_minutes": 354, "total_wait_minutes": 712, "censored_wait_minutes": 671,
        "document_hold_minutes": 0, "observed_makespan_minutes": 49,
        "scale_occupancy_peak": 1, "max_queue_length": 2, "max_buffer_occupancy": 1,
        "max_buffer_reservation": 1, "hard_constraint_violations": 0,
        "median_system_time_minutes": 36, "iqr_system_time_minutes": 0, "mean_system_time_minutes": 36,
        "observed_system_time_minutes": 755, "censored_system_time_minutes": 719,
        "censored_system_trucks": 1, "completed_system_trucks": 1,
        "resource_busy_minutes": 43, "resource_down_minutes": 40, "resource_available_minutes": 2120,
        "resource_idle_minutes": 2077, "resource_gross_minutes": 2160,
        "gross_utilization": round(43/2160, 12), "net_utilization": round(43/2120, 12),
        "net_idle_fraction": round(2077/2120, 12), "gross_idle_fraction": round(2077/2160, 12),
        "decision_count": 6, "fifo_break_count": 0, "fifo_break_rate": 0,
        "raw_fifo_break_count": 0, "avoidable_fifo_break_count": 0,
        "queue_comparison_count": 3, "comparable_candidate_count": 2, "queue_inversion_count": 0,
        "max_queue_displacement": 0, "mean_queue_displacement": 0,
        "replanning_count": 0, "replanning_frequency_per_hour": 0,
        "ordinary_window_activation_count": 0, "mandatory_candidate_count": 0,
        "mandatory_decision_count": 0, "critical_expansion_candidate_count": 0,
        "critical_expansion_decision_count": 0, "operator_accept_count": 6, "operator_reject_count": 0,
        "dispatch_block_count": 0, "command_count": 6,
        "co2_estimated_kg": round(712/60*.8*10.18, 12),
        "co2_sensitivity_low_kg": round(712/60*.5*10.18, 12),
        "co2_sensitivity_high_kg": round(712/60*10.18, 12),
    }
    assert set(expected) == set(METRIC_SCALAR_FIELDS)
    assert dict(derived.scalars) == expected
    for resource_id, kind, busy, down in (("gate-1", "gate", 8, 0), ("scale-1", "scale", 15, 0), ("hopper-1", "hopper", 20, 40)):
        available, idle = 720-down, 720-down-busy
        assert dict(derived.resources[resource_id]) == {
            "kind": kind, "gross_minutes": 720, "busy_minutes": busy, "down_minutes": down,
            "available_minutes": available, "idle_minutes": idle,
            "gross_utilization": round(busy/720, 12), "net_utilization": round(busy/available, 12),
            "net_idle_fraction": round(idle/available, 12), "gross_idle_fraction": round(idle/720, 12),
        }
    assert {key: dict(value) for key, value in derived.trucks.items()} == {
        "T1": {"wait_minutes": 2, "censored_wait_minutes": 0, "service_minutes": 34,
               "censored_service_minutes": 0, "document_hold_minutes": 0,
               "observed_system_time_minutes": 36, "system_time_censored": False},
        "T2": {"wait_minutes": 710, "censored_wait_minutes": 671, "service_minutes": 9,
               "censored_service_minutes": 0, "document_hold_minutes": 0,
               "observed_system_time_minutes": 719, "system_time_censored": True},
    }


@pytest.mark.parametrize("namespace", ["scalars", "resources", "trucks"])
def test_audit_rejects_semantic_metric_forgery_with_updated_receipts(tmp_path, monkeypatch, namespace):
    bundle = build_validation_bundle(tmp_path)
    rows = [dict(row) for row in bundle.results]
    path = bundle.run_dir / rows[0]["metrics_file"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if namespace == "scalars":
        payload[namespace]["co2_estimated_kg"] += 1
        rows[0]["co2_estimated_kg"] = payload[namespace]["co2_estimated_kg"]
    elif namespace == "resources":
        payload[namespace][0]["busy_minutes"] += 1
    else:
        payload[namespace][0]["document_hold_minutes"] += 1
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")
    rows[0]["metrics_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    from pequiflux_experiment.experiment import _csv_text
    bundle.results_path.write_text(_csv_text(rows), encoding="utf-8", newline="\n")
    import pequiflux_experiment.metrics as producer

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic audit delegated reconstruction to the producer")

    monkeypatch.setattr(producer, "compute_policy_day_metrics", forbidden)
    with pytest.raises(AuditError, match="metrics artifact.*independently reconstructed"):
        audit_run(bundle.run_dir)


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
    from pequiflux_experiment.validation_fixtures import build_validation_fixture
    fixture = build_validation_fixture(scenario, 101)
    result = run_day(fixture.instance, make_policy("fifo_strict"), fixture.controls, fixture.event_latents)
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
    from pequiflux_experiment.metrics import compute_policy_day_metrics
    persisted_metrics = compute_policy_day_metrics(log_path)
    assert derived.to_dict() == persisted_metrics.to_dict()
    assert persisted_metrics.scalars["censored_system_trucks"] > 0
    assert any(row["censored_service_minutes"] > 0 for row in persisted_metrics.trucks.values())
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
    completed = sum(event.kind == "SERVICE_COMPLETED" and event.payload["operation"] == "scale_out" for event in result.events)
    expected_rate = round(completed / 12, 12)
    assert derived.scalars["observed_makespan_minutes"] == expected_makespan
    assert derived.scalars["throughput_per_hour"] == expected_rate


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
    if field == "total_trucks":
        # Keep the row internally consistent so the audit fails on the
        # disagreement with the canonical scenario metadata.
        rows[0]["remaining_trucks"] = str(int(replacement) - int(rows[0]["completed_trucks"]))
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
