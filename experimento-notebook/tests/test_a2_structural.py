"""Regression checks for the explicit five-field A2 decision contract."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from pequiflux_experiment.audit import AuditError, audit_run
from pequiflux_experiment.config import POLICY_NAMES, load_config
from pequiflux_experiment.dispatch import Candidate, DispatchContext, recommend
from pequiflux_experiment.digital_model import DigitalModel
from pequiflux_experiment.domain import YardSnapshot
from pequiflux_experiment.emulator import tiny_scenario
from pequiflux_experiment.experiment import run_experiment_matrix
from pequiflux_experiment.policies import make_policy
from pequiflux_experiment.replay import snapshot_hash
from pequiflux_experiment.events import EventRecord


PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


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
    return run_experiment_matrix(
        scenarios=[tiny_scenario(truck_count=2, hoppers=1, scales=1)],
        seeds=[101],
        policies=POLICY_NAMES,
        config=load_config(CONFIG_PATH),
        runs_root=tmp_path,
        phase="validation",
        now_utc="2026-09-01T12:00:00Z",
    )


def _rewrite_first_decision(bundle, mutate, *, target: str = "justification") -> None:
    log_path = next(bundle.logs_dir.glob("*.jsonl"))
    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    decision = next(line for line in lines if line["event_kind"] == "DECISION_RECORDED")
    recommendation = decision["payload"]["decision"]
    if target == "justification":
        mutate(recommendation["justification"])
    elif target == "recommendation":
        mutate(recommendation)
    else:
        raise ValueError(f"unsupported mutation target: {target}")
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


def test_pending_human_audit_is_not_an_approved_a2_result(tmp_path: Path) -> None:
    report = audit_run(_build_bundle(tmp_path).run_dir)

    assert report.a2_structural_pass is True
    assert report.a2_human_audit_pending is True
    serialized = report.to_dict()
    assert "a2_pass" not in serialized
    assert serialized["a2_structural_pass"] is True
    assert serialized["a2_human_audit_pending"] is True
