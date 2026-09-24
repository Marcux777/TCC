"""Focused regression evidence; these fixtures never enter the central notebook."""

from pathlib import Path
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from pequiflux_experiment import load_config
from pequiflux_experiment.campaign import campaign_plan, paired_diagnostics, principal_storage_requirement
from pequiflux_experiment.dispatch import Candidate, DispatchContext
from pequiflux_experiment.policies import make_policy, EXPLORATORY_POLICIES
from pequiflux_experiment.emulator import tiny_scenario, run_day
from pequiflux_experiment.validation_fixtures import build_validation_fixture
from pequiflux_experiment.digital_model import replay_events
from pequiflux_experiment.audit import _validate_a2_manifest, AuditError, audit_run
from pequiflux_experiment.governance import study_scope
from pequiflux_experiment.experiment import LOG_REQUIRED_FIELDS, run_validation_matrix
from pequiflux_experiment.profiles import sensitivity_bootstrap
from pequiflux_experiment.validation_fixtures import build_validation_inputs

ROOT = Path(__file__).parents[1]


def test_complete_campaign_cardinalities_and_unchanged_storage_gate():
    config = load_config(ROOT / "config/confirmatory.json")
    plan = campaign_plan(config)
    assert plan.policy_days.tolist() == [3750, 18000, 777600, 10800]
    assert plan.policy_days.sum() == 810150
    required = principal_storage_requirement(config, ROOT)
    assert required["required_bytes_without_dataset"] == 93842309120


def test_prospective_v2_changes_only_version_and_preserves_legacy_face_gate():
    from pequiflux_experiment.dataset import _validate_generation_scope, FaceValidationError
    old = json.loads((ROOT / "config/archive/confirmatory.v1.json").read_text())
    new = json.loads((ROOT / "config/confirmatory.json").read_text())
    assert {key for key in old if old[key] != new[key]} == {"protocol_version"}
    _validate_generation_scope(None, load_config(ROOT / "config/confirmatory.json"))
    with pytest.raises(FaceValidationError):
        _validate_generation_scope(None, load_config(ROOT / "config/archive/confirmatory.v1.json"))


def test_exploratory_ranking_contracts():
    context = DispatchContext(now=100, affinity_target="corn")
    soy = Candidate("soy", priority=0, waiting_time=70, stage_entry_time=30, cargo_type="soy")
    corn = Candidate("corn", priority=1, waiting_time=50, stage_entry_time=50, cargo_type="corn")
    candidates = (soy, corn)
    assert min(candidates, key=lambda c: make_policy("myopic_predicted_delay").rank_key(c, context)) == corn
    assert min(candidates, key=lambda c: make_policy("batch_by_cargo").rank_key(c, context)) == corn
    assert min(candidates, key=lambda c: make_policy("batch_by_cargo").rank_key(c, DispatchContext())) == soy
    for c in candidates:
        key = make_policy("lexicographic").rank_key(c, context, candidates)
        assert make_policy("window_without_stability").rank_key(c, context, candidates) == key[:2] + key[3:]


@pytest.mark.parametrize("policy", EXPLORATORY_POLICIES)
def test_exploratory_policy_runs_real_des_and_replays(policy):
    scenario = tiny_scenario(truck_count=8, hoppers=1, scales=1, regime="nominal")
    fixture = build_validation_fixture(scenario, 101)
    day = run_day(fixture.instance, policy, fixture.controls, fixture.event_latents)
    replay = replay_events(day.events, physical=day.initial_snapshot, scenario=scenario)
    assert replay.canonical_dict() == day.final_snapshot.canonical_dict()
    assert day.hard_constraint_violations == 0
    if policy == "batch_by_cargo":
        last_cargo = {}
        for event in day.events:
            if event.kind == "SERVICE_COMPLETED":
                truck_id = event.payload["truck_id"]
                last_cargo[event.payload["resource_id"]] = day.initial_snapshot.trucks[truck_id].cargo_type
            if event.kind == "DECISION_RECORDED":
                decision = event.to_dict()["payload"]["decision"]
                assert decision["context"]["affinity_target"] == last_cargo.get(decision["resource_id"])


def paired_frame():
    rows = []
    for seed in range(101, 105):
        for policy in ("lexicographic", "fifo_flow_faithful", "priority_local", "fixed_score"):
            rows.append(dict(scenario_id="s1", seed=seed, policy=policy, stratum="medium",
                p95_wait_minutes=8 if policy == "lexicographic" else 10,
                throughput=98 if policy == "lexicographic" else 100, total_trucks=120,
                config_hash="c", dataset_root_hash="d", instance_hash=str(seed),
                execution_instance_hash=str(seed), control_hash="control"))
    return pd.DataFrame(rows)


def test_paired_descriptive_effect_and_throughput_guard():
    report = paired_diagnostics(paired_frame())
    assert len(report) == 3
    assert report.gain_median.tolist() == [.2] * 3
    assert report.gain_iqr.tolist() == [0] * 3
    assert report.gain_ci95_low.tolist() == [.2] * 3
    assert report.throughput_guard_median.tolist() == pytest.approx([.4] * 3)
    assert not any("pvalue" in c for c in report.columns)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "identity", "zero"])
def test_descriptive_input_rejections(fault):
    frame = paired_frame()
    if fault == "missing":
        frame = frame.iloc[:-1]
    elif fault == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    elif fault == "identity":
        frame.loc[1, "instance_hash"] = "tampered"
    else:
        frame.loc[1, "p95_wait_minutes"] = 0
    with pytest.raises(ValueError, match="INVALID_INPUT"):
        paired_diagnostics(frame)


def test_v2_manifest_rejects_contradictory_human_provenance():
    config = load_config(ROOT / "config/confirmatory.json")
    configuration = json.loads((ROOT / "config/confirmatory.json").read_text())
    manifest = dict(configuration=configuration, protocol_version="2.0.0", phase="pilot",
        study_scope=study_scope(config), human_audit_status="not_evaluated",
        a2=dict(human_audit_status="not_evaluated", structural_status="automated", required_fields=list(LOG_REQUIRED_FIELDS)),
        operator_mode="synthetic_auto_accept", global_acceptance_status="pending", human_review_evidence=None,
        input_provenance=dict(face_validation=dict(status="NOT_EVALUATED", required=False, scope=study_scope(config))))
    assert _validate_a2_manifest(manifest) is False
    manifest["protocol_version"] = "1.0.0"
    with pytest.raises(AuditError, match="protocol_version"):
        _validate_a2_manifest(manifest)
    manifest["protocol_version"] = "2.0.0"
    manifest["input_provenance"]["face_validation"]["status"] = "APPROVED"
    with pytest.raises(AuditError, match="NOT_EVALUATED"):
        _validate_a2_manifest(manifest)


def test_sensitivity_bootstrap_is_bound_to_controls_and_ledger():
    fixture = build_validation_fixture(tiny_scenario(truck_count=4), 101)
    receipt = sensitivity_bootstrap(fixture.controls)
    assert receipt["version"] == "sensitivity-bootstrap.v1"
    assert receipt["iterations"] == 5000
    assert receipt == sensitivity_bootstrap(fixture.controls)
    changed = SimpleNamespace(control_hash="f" * 64,
        event_latents_sha256=fixture.controls.event_latents_sha256)
    assert receipt["seed"] != sensitivity_bootstrap(changed)["seed"]
    report = paired_diagnostics(paired_frame(), bootstrap=receipt)
    assert set(report.bootstrap_seed) == {receipt["seed"]}


@pytest.mark.parametrize("field", ["controlled_view_hash", "event_overlay_hash", "execution_instance_hash"])
def test_auditor_rederives_projection_from_source_instead_of_trusting_log(tmp_path, monkeypatch, field):
    # Only the storage loader is doubled: DES, persistence, projection and audit
    # are real. These tiny fixtures cannot be accepted as scientific datasets.
    import pequiflux_experiment.dataset as dataset_api
    from pequiflux_experiment.config import config_hash
    config = load_config(ROOT / "config/confirmatory.json")
    values, controls, ledger = build_validation_inputs([tiny_scenario(truck_count=4)], (101,))
    bundle = run_validation_matrix(values, ("lexicographic",), config, tmp_path / "runs",
                                   controls=controls, event_latents=ledger)
    manifest = json.loads(bundle.manifest_path.read_text())
    manifest["input_provenance"].update(kind="frozen_dataset", dataset_path=str(tmp_path / "source"))
    bundle.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source = SimpleNamespace(manifest={"config_hash": config_hash(config)},
                             instances=values, event_latents=ledger)
    monkeypatch.setattr(dataset_api, "load_frozen_dataset", lambda *a, **k: source)
    assert audit_run(bundle.run_dir).overall_pass
    original = dataset_api.derive_controlled_projection

    def wrong_projection(*args):
        projection = original(*args)
        return SimpleNamespace(
            controlled_view_hash="0" * 64 if field == "controlled_view_hash" else projection.controlled_view_hash,
            event_overlay_hash="0" * 64 if field == "event_overlay_hash" else projection.event_overlay_hash,
            instance=SimpleNamespace(instance_hash="0" * 64) if field == "execution_instance_hash" else projection.instance)

    monkeypatch.setattr(dataset_api, "derive_controlled_projection", wrong_projection)
    with pytest.raises(AuditError, match="projection differs"):
        audit_run(bundle.run_dir)
