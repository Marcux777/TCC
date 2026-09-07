"""Hand-calculated metrics at the persisted-event boundary."""

import json
from decimal import Decimal

import pytest

from pequiflux_experiment.domain import ExecutionControls
from pequiflux_experiment.metrics import MetricsError, compute_policy_day_metrics


def _persisted_day(tmp_path, *, reordered=False):
    controls = ExecutionControls.build(ordinary_window=6, buffer_capacity=12,
        threshold_multiplier=Decimal("1.00"), intensity="base",
        source_dataset_root_hash="a" * 64, event_latents_sha256="b" * 64)
    trucks = {name: {"arrival_time": arrival, "priority": 0, "cargo_type": "soy",
                    "document_ok": True, "arrived": False, "next_operation": "gate"}
              for name, arrival in (("T1", 0.0), ("T2", 1.0), *(((("T3", 1.1), ("T4", 1.2))) if reordered else ()))}
    resources = {name: {"kind": kind, "status": "available", "allowed_cargo_types": ["soy"]}
                 for name, kind in (("gate-1", "gate"), ("scale-1", "scale"), ("hopper-1", "hopper"))}
    events = []
    def emit(time, kind, **payload):
        events.append({"time": time, "sequence": len(events) + 1, "kind": kind, "payload": payload})
    emit(0.0, "RUN_STARTED", initial_snapshot={"trucks": trucks, "resources": resources},
         resources=resources, execution_controls=controls.to_dict(), policy="fifo_flow_faithful")
    for name, truck in trucks.items():
        emit(truck["arrival_time"], "TRUCK_ARRIVED", truck_id=name, arrival_time=truck["arrival_time"],
             priority=0, cargo_type="soy", document_ok=True, stage=1)

    def service(time, end, truck, operation, resource, order):
        stage_times = {name: trucks[name]["arrival_time"] for name in trucks} if operation == "gate" else {truck: time}
        decision = {"policy": "fifo_flow_faithful", "resource_id": resource,
                    "candidate_ids": order, "candidate_order": [{"truck_id": name,
                    "stage_entry_time": stage_times[name], "operation": operation} for name in order],
                    "selected": {"truck_id": truck, "resource_id": resource, "operation": operation},
                    "justification": {"fifo_break": False}}
        emit(time, "DECISION_RECORDED", decision=decision)
        emit(time, "OPERATOR_DECISION", decision="accept", recommendation=decision, operator_mode="synthetic_auto_accept")
        emit(time, "SERVICE_STARTED", truck_id=truck, resource_id=resource, operation=operation, duration_minutes=end-time)
        emit(end, "SERVICE_COMPLETED", truck_id=truck, resource_id=resource, operation=operation)

    service(2, 6, "T1", "gate", "gate-1", list(trucks))
    service(6, 11, "T1", "scale_in", "scale-1", ["T1"])
    service(11, 31, "T1", "unload", "hopper-1", ["T1"])
    service(31, 36, "T1", "scale_out", "scale-1", ["T1"])
    service(40, 44, "T2", "gate", "gate-1", ["T4", "T3", "T2"] if reordered else ["T2"])
    service(44, 49, "T2", "scale_in", "scale-1", ["T2"])
    emit(50, "DISRUPTION_RECORDED", resource_id="hopper-1", cause="base_failure", latent_id="failure",
         scheduled_failure_start=50, effective_failure_start=50, scheduled_failure_duration=20,
         recovery_time=70, expired_before_effective_start=False)
    emit(50, "RESOURCE_FAILED", resource_id="hopper-1", cause="base_failure")
    emit(60, "DISRUPTION_RECORDED", resource_id="hopper-1", cause="rain", latent_id="rain",
         scheduled_failure_start=60, effective_failure_start=60, scheduled_failure_duration=30,
         recovery_time=90, expired_before_effective_start=False)
    emit(90, "RESOURCE_RECOVERED", resource_id="hopper-1", cause="rain")
    emit(720, "END_OF_DAY", horizon_minutes=720)
    path = tmp_path / "day.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in events), encoding="utf-8")
    return path, events


@pytest.mark.parametrize("reordered", (False, True))
def test_persisted_metrics_reconcile_overlap_censoring_weighted_resources_and_queue_order(tmp_path, reordered):
    path, _ = _persisted_day(tmp_path, reordered=reordered)
    result = compute_policy_day_metrics(path)
    metrics = result.scalars
    assert metrics["completed_trucks"] == 1
    assert metrics["makespan_minutes"] == 49
    assert metrics["median_system_time_minutes"] == 36
    assert result.trucks["T2"]["censored_wait_minutes"] == 671
    assert result.trucks["T2"]["observed_system_time_minutes"] == 719
    assert result.trucks["T2"]["system_time_censored"] is True
    assert result.resources["hopper-1"]["down_minutes"] == 40
    assert metrics["resource_busy_minutes"] == 43
    assert metrics["resource_available_minutes"] == 2120
    assert metrics["resource_idle_minutes"] == 2077
    assert metrics["gross_utilization"] == round(43 / 2160, 12)
    assert metrics["net_utilization"] == round(43 / 2120, 12)
    assert metrics["queue_inversion_count"] == (3 if reordered else 0)
    assert metrics["max_queue_displacement"] == (2 if reordered else 0)
    assert metrics["replanning_count"] == (1 if reordered else 0)
    if not reordered:
        assert metrics["total_wait_minutes"] == 712
        assert metrics["mean_wait_minutes"] == 356
        assert metrics["p95_wait_minutes"] == 710
        assert metrics["co2_estimated_kg"] == round(712 / 60 * .8 * 10.18, 12)
    assert metrics["co2_sensitivity_low_kg"] < metrics["co2_estimated_kg"] < metrics["co2_sensitivity_high_kg"]
    with pytest.raises(TypeError):
        result.scalars["resource_busy_minutes"] = 0
    json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize("corruption", ("missing_controls", "premature_recovery", "missing_completion", "forged_fifo_break"))
def test_metrics_fail_closed_for_missing_input_or_impossible_observation(tmp_path, corruption):
    path, events = _persisted_day(tmp_path)
    if corruption == "missing_controls":
        del events[0]["payload"]["execution_controls"]
    elif corruption == "premature_recovery":
        next(row for row in events if row["kind"] == "RESOURCE_RECOVERED")["time"] = 70
    elif corruption == "missing_completion":
        events = [row for row in events if not (row["kind"] == "SERVICE_COMPLETED" and row["payload"]["operation"] == "scale_out")]
        for sequence, row in enumerate(events, 1):
            row["sequence"] = sequence
    else:
        next(row for row in events if row["kind"] == "DECISION_RECORDED")["payload"]["decision"]["justification"]["fifo_break"] = True
    path.write_text("".join(json.dumps(row) + "\n" for row in events), encoding="utf-8")
    with pytest.raises(MetricsError):
        compute_policy_day_metrics(path)


def test_active_service_is_censored_as_busy_time_not_queue_wait(tmp_path):
    path, events = _persisted_day(tmp_path)
    terminal = events.pop()
    decision = {"policy": "fifo_flow_faithful", "resource_id": "hopper-1", "candidate_ids": ["T2"],
        "candidate_order": [{"truck_id": "T2", "stage_entry_time": 49, "operation": "unload"}],
        "selected": {"truck_id": "T2", "resource_id": "hopper-1", "operation": "unload"},
        "justification": {"fifo_break": False}}
    for kind, payload in (
        ("DECISION_RECORDED", {"decision": decision}),
        ("OPERATOR_DECISION", {"decision": "accept", "recommendation": decision, "operator_mode": "synthetic_auto_accept"}),
        ("SERVICE_STARTED", {"truck_id": "T2", "resource_id": "hopper-1", "operation": "unload", "duration_minutes": 20}),
    ):
        events.append({"time": 710, "kind": kind, "payload": payload})
    events.append(terminal)
    for sequence, row in enumerate(events, 1):
        row["sequence"] = sequence
    path.write_text("".join(json.dumps(row) + "\n" for row in events), encoding="utf-8")
    result = compute_policy_day_metrics(path)
    assert result.scalars["resource_busy_minutes"] == 53
    assert result.trucks["T2"]["censored_service_minutes"] == 10
    assert result.trucks["T2"]["censored_wait_minutes"] == 0
    assert result.scalars["total_wait_minutes"] == 702


@pytest.mark.parametrize("mandatory", (False, True))
def test_window_and_critical_diagnostics_are_rebuilt_from_controls_and_queue_events(tmp_path, mandatory):
    path, events = _persisted_day(tmp_path, reordered=True)
    old = events[0]["payload"]["execution_controls"]
    controls = ExecutionControls.build(ordinary_window=1, buffer_capacity=12,
        threshold_multiplier=Decimal("0.50"), intensity="base",
        source_dataset_root_hash=old["source_dataset_root_hash"], event_latents_sha256=old["event_latents_sha256"])
    events[0]["payload"]["execution_controls"] = controls.to_dict()
    first = next(row["payload"]["decision"] for row in events if row["kind"] == "DECISION_RECORDED")
    first["candidate_ids"] = ["T1"]
    first["candidate_order"] = first["candidate_order"][:1]
    if mandatory:
        events[0]["payload"]["initial_snapshot"]["trucks"]["T1"]["priority"] = 2
        next(row for row in events if row["kind"] == "TRUCK_ARRIVED" and row["payload"]["truck_id"] == "T1")["payload"]["priority"] = 2
    path.write_text("".join(json.dumps(row) + "\n" for row in events), encoding="utf-8")
    metrics = compute_policy_day_metrics(path).scalars
    assert metrics["ordinary_window_activation_count"] == (1 if mandatory else 2)
    assert metrics["mandatory_candidate_count"] == (4 if mandatory else 0)
    assert metrics["mandatory_decision_count"] == (4 if mandatory else 0)
    assert metrics["critical_expansion_candidate_count"] == 2
    assert metrics["critical_expansion_decision_count"] == 1
