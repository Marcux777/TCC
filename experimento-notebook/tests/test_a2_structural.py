"""Regression checks for the explicit five-field A2 decision contract."""

from __future__ import annotations

import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from pequiflux_experiment.audit import AuditError, audit_run, _validate_decision_justification
from pequiflux_experiment.config import POLICY_NAMES, load_config
from pequiflux_experiment.dispatch import Candidate, DispatchContext, recommend
from pequiflux_experiment.digital_model import DigitalModel
from pequiflux_experiment.domain import YardSnapshot
from pequiflux_experiment.emulator import tiny_scenario
from pequiflux_experiment.experiment import run_validation_matrix
from pequiflux_experiment.validation_fixtures import build_validation_inputs
from pequiflux_experiment.policies import make_policy
from pequiflux_experiment.replay import snapshot_hash
from pequiflux_experiment.events import EventRecord


PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


@pytest.mark.parametrize("same_stage_time", [False, True])
def test_auditor_reconstructs_stage_fifo_and_rejects_tampering(same_stage_time) -> None:
    # Arrival and stable order favor Z; stage FIFO (including its ID tie break) favors A.
    payload = recommend(
        [Candidate("Z", arrival_time=0, stage_entry_time=8, stable_order=0,
                   operation="unload"),
         Candidate("A", arrival_time=1, stage_entry_time=8 if same_stage_time else 2,
                   stable_order=1, operation="unload")],
        DispatchContext(now=10, resource_id="hopper-1", operation="unload"),
        make_policy("fifo_strict"),
    ).to_dict()
    assert payload["selected"]["truck_id"] == "A"
    assert _validate_decision_justification(payload)
    for mutate in (
        lambda value: value.__setitem__("fifo_reference_truck_id", "Z"),
        lambda value: value["candidate_order"][0].__setitem__("stage_entry_time", 0),
        lambda value: value["candidate_order"][0].pop("stage_entry_time"),
        lambda value: value.__setitem__("schema_version", 1),
    ):
        tampered = deepcopy(payload)
        mutate(tampered)
        assert not _validate_decision_justification(tampered)


@pytest.mark.parametrize("assigned_resource", [None, "hopper-1"])
def test_auditor_checks_structured_cargo_exclusion_and_context(assigned_resource) -> None:
    payload = recommend(
        [Candidate("corn", cargo_type="corn", operation="unload", resource_id=assigned_resource),
         Candidate("soy", cargo_type="soy", operation="unload", resource_id=assigned_resource)],
        DispatchContext(now=10, resource_id="hopper-1", operation="unload",
                        allowed_cargo_types=("soy",)),
        make_policy("fifo_flow_faithful"),
    ).to_dict()
    assert payload["selected"]["truck_id"] == "soy"
    assert _validate_decision_justification(payload)
    assert payload["excluded"][0]["cause"] == "CARGO_INCOMPATIBLE"
    for mutate in (
        lambda value: value["excluded"][0].__setitem__("cause", "RESOURCE_MISMATCH"),
        lambda value: value["excluded"][0]["candidate"].__setitem__("cargo_type", "soy"),
        lambda value: value["context"].__setitem__("allowed_cargo_types", ["soy", "corn"]),
        lambda value: value["context"].__setitem__("resource_id", "hopper-2"),
        lambda value: value["candidate_order"][0].__setitem__("cargo_type", "corn"),
    ):
        tampered = deepcopy(payload)
        mutate(tampered)
        assert not _validate_decision_justification(tampered)


def test_recommendation_emits_canonical_five_field_justification() -> None:
    candidates = (
        Candidate(
            "T-older",
            arrival_time=0.0,
            priority=0,
            waiting_time=2.0,
            operation="unload",
            stable_order=0,
        ),
        Candidate(
            "T-urgent",
            arrival_time=1.0,
            priority=2,
            waiting_time=1.0,
            operation="unload",
            stable_order=1,
        ),
    )
    recommendation = recommend(
        candidates,
        DispatchContext(
            now=2.0,
            resource_id="hopper-1",
            resource_available=True,
            resource_status="available",
            operation="unload",
            queue_length=2,
        ),
        make_policy("priority_local"),
    )

    payload = recommendation.to_dict()
    justification = payload["justification"]

    assert set(justification) == {
        "truck_stage",
        "resource",
        "activated_rules",
        "reason",
        "fifo_break",
    }
    assert justification["truck_stage"] == {
        "truck_id": "T-urgent",
        "stage": "unload",
    }
    assert justification["resource"] == {"resource_id": "hopper-1"}
    assert isinstance(justification["activated_rules"], list)
    assert "resource_available" in justification["activated_rules"]
    assert "document_released" in justification["activated_rules"]
    assert "policy:priority_local" in justification["activated_rules"]
    assert "fifo_override" in justification["activated_rules"]
    assert justification["fifo_break"] is True
    assert "T-urgent" in justification["reason"]
    assert "unload" in justification["reason"]
    assert "hopper-1" in justification["reason"]
    assert "FIFO" in justification["reason"]
    assert payload["fifo_reference_truck_id"] == "T-older"


@pytest.mark.parametrize(
    "candidate_operation",
    [None, "gate"],
)
def test_recommend_rejects_missing_or_divergent_operation(
    candidate_operation: str | None,
) -> None:
    candidate = Candidate(
        "T-1",
        arrival_time=0.0,
        priority=0,
        operation=candidate_operation,
        stable_order=0,
    )
    with pytest.raises(ValueError, match="operation"):
        recommend(
            [candidate],
            DispatchContext(
                now=1.0,
                resource_id="hopper-1",
                operation="unload",
            ),
            make_policy("fifo_strict"),
        )


def _build_bundle(tmp_path: Path):
    instances, controls, ledger = build_validation_inputs(
        [tiny_scenario(truck_count=2, hoppers=1, scales=1)], [101],
    )
    return run_validation_matrix(
        instances=instances,
        controls=controls,
        event_latents=ledger,
        policies=POLICY_NAMES,
        config=load_config(CONFIG_PATH),
        runs_root=tmp_path,
        now_utc="2026-09-01T12:00:00Z",
    )


def _rewrite_first_decision(bundle, mutate, *, target: str = "justification", decision_index: int = 0) -> None:
    log_path = next(bundle.logs_dir.glob("*.jsonl"))
    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    decision = [line for line in lines if line["event_kind"] == "DECISION_RECORDED"][decision_index]
    recommendation = decision["payload"]["decision"]
    if target == "justification":
        mutate(recommendation["justification"])
    elif target == "recommendation":
        mutate(recommendation)
    else:
        raise ValueError(f"unsupported mutation target: {target}")
    decision["selection"] = recommendation["selected"]
    decision["excluded"] = recommendation["excluded"]
    # The decision payload is part of the replayed digital-model state.  Keep
    # the tampered fixture replayable so the assertion reaches the A2 semantic
    # gate instead of stopping at an unrelated state-hash mismatch.
    initial_raw = next(line for line in lines if line["event_kind"] == "RUN_STARTED")
    model = DigitalModel.from_snapshot(
        YardSnapshot.from_dict(initial_raw["payload"]["initial_snapshot"])
    )
    for line in lines:
        event = EventRecord.from_dict(
            {
                "time": line["time"],
                "sequence": line["sequence"],
                "kind": line["event_kind"],
                "payload": line["payload"],
            }
        )
        line["state_before_hash"] = snapshot_hash(model.snapshot())
        model.apply(event)
        line["state_after_hash"] = snapshot_hash(model.snapshot())
    final_hash = snapshot_hash(model.snapshot())

    content = "\n".join(
        json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for line in lines
    ) + "\n"
    log_path.write_text(content, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    manifest["decision_logs"][log_path.name]["sha256"] = digest
    manifest["logs"][log_path.name]["sha256"] = digest
    bundle.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with bundle.results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["log_file"] == log_path.name:
            row["log_sha256"] = digest
            row["final_state_hash"] = final_hash
            row["replay_state_hash"] = final_hash
    with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize(
    ("field", "mutate"),
    [
        (
            "truck_stage",
            lambda value: value.update({"truck_id": "T-999"}),
        ),
        (
            "resource",
            lambda value: value.update({"resource_id": "wrong-resource"}),
        ),
        (
            "activated_rules",
            lambda value: value.__setitem__("activated_rules", []),
        ),
        (
            "reason",
            lambda value: value.__setitem__("reason", "changed"),
        ),
        (
            "fifo_break",
            lambda value: value.__setitem__("fifo_break", not value["fifo_break"]),
        ),
    ],
)
def test_audit_rejects_semantically_incoherent_a2_justification(
    tmp_path: Path, field: str, mutate
) -> None:
    bundle = _build_bundle(tmp_path)
    _rewrite_first_decision(bundle, mutate)

    with pytest.raises(AuditError, match="A2|justification"):
        audit_run(bundle.run_dir)


def test_audit_rejects_invented_rule_or_overlapping_exclusion(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)

    def add_invented_rule(value):
        value["activated_rules"].append("invented_rule")

    _rewrite_first_decision(bundle, add_invented_rule)
    with pytest.raises(AuditError, match="A2|justification"):
        audit_run(bundle.run_dir)

    bundle = _build_bundle(tmp_path / "overlap")
    def overlap_exclusion(value):
        selected_id = value["selected"]["truck_id"]
        value["excluded"].append({"truck_id": selected_id, "reason": "fabricated"})

    _rewrite_first_decision(bundle, overlap_exclusion, target="recommendation")
    with pytest.raises(AuditError, match="A2|justification|excluded"):
        audit_run(bundle.run_dir)


def test_computational_a2_does_not_claim_human_evaluation(tmp_path: Path) -> None:
    report = audit_run(_build_bundle(tmp_path).run_dir)

    assert report.a2_structural_pass is True
    assert report.a2_human_audit_pending is False
    serialized = report.to_dict()
    assert "a2_pass" not in serialized
    assert serialized["a2_structural_pass"] is True
    assert serialized["a2_human_audit_pending"] is False
    assert serialized["human_evaluation_status"] == "not_evaluated"


@pytest.mark.parametrize("field", ["instance_hash", "execution_instance_hash", "control_hash", "controls"])
def test_audit_rejects_input_provenance_tampering(tmp_path: Path, field: str) -> None:
    bundle = _build_bundle(tmp_path)
    if field == "controls":
        manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
        manifest["input_provenance"]["controls"]["ordinary_window"] += 1
        bundle.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        with bundle.results_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0][field] = "0" * 64
        with bundle.results_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    with pytest.raises(AuditError, match="provenance|control_hash|execution instances"):
        audit_run(bundle.run_dir)


@pytest.mark.parametrize("field", ["stage_entry_time", "allowed_cargo_types"])
def test_audit_authenticates_decision_facts_against_events(tmp_path: Path, field: str) -> None:
    bundle = _build_bundle(tmp_path)

    def alter_consistently(value):
        if field == "stage_entry_time":
            assert value["selected"]["stage_entry_time"] > 0
            value["selected"]["stage_entry_time"] = 0
            for item in value["candidate_order"]:
                if item["truck_id"] == value["selected"]["truck_id"]:
                    item["stage_entry_time"] = 0
        else:
            value["context"]["allowed_cargo_types"].append("invented-cargo")
        # The payload remains internally consistent; replay facts must expose the forgery.
        assert _validate_decision_justification(value)

    _rewrite_first_decision(bundle, alter_consistently, target="recommendation", decision_index=1)
    with pytest.raises(AuditError, match="observation"):
        audit_run(bundle.run_dir)
