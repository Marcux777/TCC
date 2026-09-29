"""Hand-calculated metrics at the persisted-event boundary."""

import json
from dataclasses import replace
from decimal import Decimal

import pytest

from pequiflux_experiment.domain import ExecutionControls
from pequiflux_experiment.metrics import (
    METRIC_CATALOG, METRIC_SCALAR_FIELDS, MetricsError, canonical_metric_definitions,
    compute_policy_day_metrics,
)


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
         resources=resources, execution_controls=controls.to_dict(), admission_mode="mandatory_window",
         policy="fifo_flow_faithful")
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
    assert metrics["observed_makespan_minutes"] == 49
    assert metrics["throughput"] == 1
    assert metrics["throughput_per_hour"] == round(1 / 12, 12)
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
    assert metrics["gross_idle_fraction"] == round(2077 / 2160, 12)
    assert metrics["max_queue_length"] == (4 if reordered else 2)
    assert metrics["max_buffer_occupancy"] == metrics["max_buffer_reservation"] == 1
    assert metrics["queue_inversion_count"] == (3 if reordered else 0)
    assert metrics["max_queue_displacement"] == (2 if reordered else 0)
    assert metrics["queue_comparison_count"] == 3
    assert metrics["comparable_candidate_count"] == (4 if reordered else 2)
    assert metrics["mean_queue_displacement"] == (0.444444444444 if reordered else 0)
    assert metrics["replanning_count"] == (1 if reordered else 0)
    assert metrics["replanning_frequency_per_hour"] == (0.083333333333 if reordered else 0)
    if not reordered:
        assert metrics["total_wait_minutes"] == 712
        assert metrics["mean_wait_minutes"] == 356
        assert metrics["p95_wait_minutes"] == 710
        assert metrics["co2_estimated_kg"] == round(712 / 60 * .8 * 10.18, 12)
    assert metrics["co2_sensitivity_low_kg"] < metrics["co2_estimated_kg"] < metrics["co2_sensitivity_high_kg"]
    with pytest.raises(TypeError):
        result.scalars["resource_busy_minutes"] = 0
    json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize("corruption", ("missing_controls", "missing_admission_mode", "premature_recovery", "missing_completion", "forged_fifo_break"))
def test_metrics_fail_closed_for_missing_input_or_impossible_observation(tmp_path, corruption):
    path, events = _persisted_day(tmp_path)
    if corruption == "missing_controls":
        del events[0]["payload"]["execution_controls"]
    elif corruption == "missing_admission_mode":
        del events[0]["payload"]["admission_mode"]
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


def _four_truck_day(tmp_path, *, document_hold=False, admission_mode="mandatory_window"):
    """Literal non-overlapping cycles: waits 0,2,4,6 and services 4+5+20+5."""
    controls = ExecutionControls.build(ordinary_window=6, buffer_capacity=12,
        threshold_multiplier=Decimal("1.00"), intensity="base",
        source_dataset_root_hash="a" * 64, event_latents_sha256="b" * 64)
    trucks = {f"T{index+1}": {"arrival_time": index*100.0, "priority": 0, "cargo_type": "soy",
        "document_ok": not (document_hold and index == 1), "arrived": False, "next_operation": "gate"}
        for index in range(4)}
    resources = {name: {"kind": kind, "status": "available", "allowed_cargo_types": ["soy"]}
        for name, kind in (("gate-1", "gate"), ("scale-1", "scale"), ("hopper-1", "hopper"))}
    events = []
    def emit(time, kind, **payload):
        events.append({"time": time, "sequence": len(events)+1, "kind": kind, "payload": payload})
    emit(0, "RUN_STARTED", initial_snapshot={"trucks": trucks, "resources": resources},
         resources=resources, execution_controls=controls.to_dict(), admission_mode=admission_mode)
    for index, (truck_id, truck) in enumerate(trucks.items()):
        arrival = truck["arrival_time"]
        emit(arrival, "TRUCK_ARRIVED", truck_id=truck_id, arrival_time=arrival,
             priority=0, cargo_type="soy", document_ok=truck["document_ok"], stage=1 if truck["document_ok"] else 0)
        clock, entered = arrival+2*index, arrival
        if not truck["document_ok"]:
            emit(clock, "DOCUMENT_RELEASED", truck_id=truck_id)
            entered = clock
        for operation, resource_id, duration in (("gate", "gate-1", 4), ("scale_in", "scale-1", 5),
                                                   ("unload", "hopper-1", 20), ("scale_out", "scale-1", 5)):
            # No policy name is needed to reconstruct any metric.
            decision = {"resource_id": resource_id, "candidate_ids": [truck_id],
                "candidate_order": [{"truck_id": truck_id, "stage_entry_time": entered, "operation": operation}],
                "selected": {"truck_id": truck_id, "resource_id": resource_id, "operation": operation},
                "justification": {"fifo_break": False}}
            emit(clock, "DECISION_RECORDED", decision=decision)
            emit(clock, "OPERATOR_DECISION", decision="accept", recommendation=decision,
                 operator_mode="synthetic_auto_accept")
            emit(clock, "SERVICE_STARTED", truck_id=truck_id, resource_id=resource_id,
                 operation=operation, duration_minutes=duration)
            clock += duration
            emit(clock, "SERVICE_COMPLETED", truck_id=truck_id, resource_id=resource_id, operation=operation)
            entered = clock
    emit(720, "END_OF_DAY", horizon_minutes=720)
    path = tmp_path / "four-trucks.jsonl"
    path.write_text("".join(json.dumps(row)+"\n" for row in events), encoding="utf-8")
    return path, events


def test_all_metric_fields_have_literal_analytical_values_and_complete_catalog(tmp_path):
    path, _ = _four_truck_day(tmp_path)
    result = compute_policy_day_metrics(path)
    expected = {
        "event_count": 70, "total_trucks": 4, "completed_trucks": 4, "remaining_trucks": 0, "throughput": 4,
        "mean_wait_minutes": 3.0, "p50_wait_minutes": 3.0, "p95_wait_minutes": 6.0, "iqr_wait_minutes": 3.0,
        "total_wait_minutes": 12.0, "censored_wait_minutes": 0.0, "document_hold_minutes": 0.0,
        "observed_makespan_minutes": 340.0, "horizon_minutes": 720, "throughput_per_hour": 0.333333333333,
        "scale_occupancy_peak": 1, "max_queue_length": 1, "max_buffer_occupancy": 1, "max_buffer_reservation": 1,
        "hard_constraint_violations": 0, "median_system_time_minutes": 37.0, "iqr_system_time_minutes": 3.0,
        "mean_system_time_minutes": 37.0, "observed_system_time_minutes": 148.0,
        "censored_system_time_minutes": 0.0, "censored_system_trucks": 0, "completed_system_trucks": 4,
        "resource_busy_minutes": 136.0, "resource_down_minutes": 0.0, "resource_available_minutes": 2160.0,
        "resource_idle_minutes": 2024.0, "resource_gross_minutes": 2160.0,
        "gross_utilization": 0.062962962963, "net_utilization": 0.062962962963,
        "net_idle_fraction": 0.937037037037, "gross_idle_fraction": 0.937037037037,
        "decision_count": 16, "fifo_break_count": 0, "fifo_break_rate": 0.0, "raw_fifo_break_count": 0,
        "avoidable_fifo_break_count": 0, "queue_comparison_count": 13, "comparable_candidate_count": 4,
        "queue_inversion_count": 0, "max_queue_displacement": 0, "mean_queue_displacement": 0.0,
        "replanning_count": 0, "replanning_frequency_per_hour": 0.0,
        "ordinary_window_activation_count": 0, "mandatory_candidate_count": 0, "mandatory_decision_count": 0,
        "critical_expansion_candidate_count": 0, "critical_expansion_decision_count": 0,
        "operator_accept_count": 16, "operator_reject_count": 0, "dispatch_block_count": 0, "command_count": 16,
        "co2_estimated_kg": 1.6288, "co2_sensitivity_low_kg": 1.018, "co2_sensitivity_high_kg": 2.036,
    }
    assert set(expected) == set(METRIC_SCALAR_FIELDS)
    assert dict(result.scalars) == expected
    expected_resources = {
        "gate-1": {"kind": "gate", "gross_minutes": 720.0, "busy_minutes": 16.0, "down_minutes": 0.0,
            "available_minutes": 720.0, "idle_minutes": 704.0, "gross_utilization": 0.022222222222,
            "net_utilization": 0.022222222222, "net_idle_fraction": 0.977777777778, "gross_idle_fraction": 0.977777777778},
        "scale-1": {"kind": "scale", "gross_minutes": 720.0, "busy_minutes": 40.0, "down_minutes": 0.0,
            "available_minutes": 720.0, "idle_minutes": 680.0, "gross_utilization": 0.055555555556,
            "net_utilization": 0.055555555556, "net_idle_fraction": 0.944444444444, "gross_idle_fraction": 0.944444444444},
        "hopper-1": {"kind": "hopper", "gross_minutes": 720.0, "busy_minutes": 80.0, "down_minutes": 0.0,
            "available_minutes": 720.0, "idle_minutes": 640.0, "gross_utilization": 0.111111111111,
            "net_utilization": 0.111111111111, "net_idle_fraction": 0.888888888889, "gross_idle_fraction": 0.888888888889},
    }
    assert {key: dict(value) for key, value in result.resources.items()} == expected_resources
    expected_trucks = {
        f"T{index+1}": {"wait_minutes": wait, "censored_wait_minutes": 0.0, "service_minutes": 34.0,
            "censored_service_minutes": 0.0, "document_hold_minutes": 0.0,
            "observed_system_time_minutes": system, "system_time_censored": False}
        for index, (wait, system) in enumerate(((0.0, 34.0), (2.0, 36.0), (4.0, 38.0), (6.0, 40.0)))
    }
    assert {key: dict(value) for key, value in result.trucks.items()} == expected_trucks
    for namespace, fields in (("scalars", expected), ("resources", expected_resources["gate-1"]),
                              ("trucks", expected_trucks["T1"])):
        assert set(METRIC_CATALOG[namespace]) == set(fields)
        for entry in METRIC_CATALOG[namespace].values():
            assert set(entry) == {"definition", "unit", "population", "window"}
            assert all(isinstance(value, str) and value for value in entry.values())
    metadata = canonical_metric_definitions()
    assert result.to_dict()["definitions"] == metadata
    assert result.schema_version == 2
    assumptions = metadata["co2_assumptions"]
    assert (assumptions["idle_fuel_rate_us_gal_per_hour"], assumptions["carbon_factor_kg_per_us_gal"],
            assumptions["engine_on_fraction"], assumptions["sensitivity_us_gal_per_hour"]) == (0.8, 10.18, 1.0, [0.5, 1.0])
    assert assumptions["fuel_rate_source_url"] == "https://afdc.energy.gov/uploads/publication/hdv_idling_2015.pdf"
    assert assumptions["carbon_factor_source_url"] == "https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P101961J.txt"
    metadata["catalog"]["scalars"]["throughput"]["unit"] = "tampered"
    assert canonical_metric_definitions()["catalog"]["scalars"]["throughput"]["unit"] == "trucks/day"


def test_document_hold_is_separate_from_primary_queue_wait_and_co2(tmp_path):
    path, _ = _four_truck_day(tmp_path, document_hold=True)
    result = compute_policy_day_metrics(path)
    assert result.trucks["T2"]["document_hold_minutes"] == 2
    assert result.trucks["T2"]["wait_minutes"] == 0
    assert result.scalars["document_hold_minutes"] == 2
    assert result.scalars["total_wait_minutes"] == 10
    assert result.scalars["co2_estimated_kg"] == round(10 / 60 * 0.8 * 10.18, 12)
    assert result.scalars["observed_system_time_minutes"] == 148


@pytest.mark.parametrize("namespace", ("scalars", "resources", "trucks", "definitions"))
def test_metric_row_rejects_incomplete_published_namespace(tmp_path, namespace):
    path, _ = _four_truck_day(tmp_path)
    complete = compute_policy_day_metrics(path)
    fields = complete.to_dict()
    if namespace == "resources":
        records = {row["resource_id"]: {key: value for key, value in row.items() if key != "resource_id"}
                   for row in fields[namespace]}
        del records["gate-1"]["busy_minutes"]
    elif namespace == "trucks":
        records = {row["truck_id"]: {key: value for key, value in row.items() if key != "truck_id"}
                   for row in fields[namespace]}
        del records["T1"]["wait_minutes"]
    else:
        records = fields[namespace]
        del records["throughput" if namespace == "scalars" else "catalog"]
    with pytest.raises(MetricsError, match=namespace[:-1] if namespace != "definitions" else "definitions"):
        replace(complete, **{namespace: records})


@pytest.mark.parametrize("undefined", ("completed_population", "available_denominator", "queue_comparisons"))
def test_undefined_populations_and_zero_denominators_raise_explicitly(tmp_path, undefined):
    path, events = _persisted_day(tmp_path)
    if undefined == "completed_population":
        events = [row for row in events if row["time"] < 36 or row["kind"] == "END_OF_DAY"]
        next(row for row in events if row["kind"] == "SERVICE_STARTED"
             and row["payload"]["operation"] == "scale_out")["payload"]["duration_minutes"] = 700
        message = "no completed truck"
    elif undefined == "available_denominator":
        # A spare resource with zero available time isolates the 0/0 ratio from
        # completed-cycle and consecutive-queue populations, which are nonempty.
        resource = {"kind": "hopper", "status": "available", "allowed_cargo_types": ["soy"]}
        events[0]["payload"]["initial_snapshot"]["resources"]["hopper-2"] = resource
        events[1:1] = [
            {"time": 0, "kind": "DISRUPTION_RECORDED", "payload": {
                "resource_id": "hopper-2", "cause": "rain", "latent_id": "whole-day-rain",
                "scheduled_failure_start": 0, "effective_failure_start": 0,
                "scheduled_failure_duration": 720, "recovery_time": 720,
                "expired_before_effective_start": False}},
            {"time": 0, "kind": "RESOURCE_FAILED", "payload": {"resource_id": "hopper-2", "cause": "rain"}},
        ]
        events.insert(-1, {"time": 720, "kind": "RESOURCE_RECOVERED",
                           "payload": {"resource_id": "hopper-2", "cause": "rain"}})
        message = "net utilization undefined for hopper-2: no available horizon"
    else:
        # One completed cycle uses a distinct scale for each weighing, leaving
        # no physical resource with a consecutive queue observation.
        events = [row for row in events if row["time"] <= 36 or row["kind"] == "END_OF_DAY"]
        del events[0]["payload"]["initial_snapshot"]["trucks"]["T2"]
        events = [row for row in events if not (row["kind"] == "TRUCK_ARRIVED"
                                                and row["payload"]["truck_id"] == "T2")]
        first = next(row["payload"]["decision"] for row in events if row["kind"] == "DECISION_RECORDED")
        first["candidate_ids"] = ["T1"]
        first["candidate_order"] = first["candidate_order"][:1]
        events[0]["payload"]["initial_snapshot"]["resources"]["scale-2"] = {
            "kind": "scale", "status": "available", "allowed_cargo_types": ["soy"]}
        for row in events:
            payload = row["payload"]
            if payload.get("operation") == "scale_out":
                payload["resource_id"] = "scale-2"
            decision = payload.get("decision") if row["kind"] == "DECISION_RECORDED" else payload.get("recommendation")
            if isinstance(decision, dict) and decision["selected"]["operation"] == "scale_out":
                decision["resource_id"] = decision["selected"]["resource_id"] = "scale-2"
        message = "queue stability require observed decisions and consecutive queues"
    for sequence, row in enumerate(events, 1):
        row["sequence"] = sequence
    path.write_text("".join(json.dumps(row)+"\n" for row in events), encoding="utf-8")
    with pytest.raises(MetricsError, match=message):
        compute_policy_day_metrics(path)


@pytest.mark.parametrize("reason", ("avoidable", "mandatory_priority", "document_block", "full_queue_priority"))
def test_raw_and_avoidable_fifo_are_rebuilt_without_policy_names(tmp_path, reason):
    path, events = _persisted_day(tmp_path, reordered=True)
    events = [row for row in events if row["time"] <= 36 or row["kind"] == "END_OF_DAY"]
    selected_id = "T2" if reason == "document_block" else "T4"
    admitted = ["T2", "T3", "T4"] if reason == "document_block" else ["T4"] if reason == "mandatory_priority" else ["T1", "T2", "T3", "T4"]
    if reason in {"mandatory_priority", "full_queue_priority"}:
        events[0]["payload"]["initial_snapshot"]["trucks"]["T4"]["priority"] = 2
        if reason == "full_queue_priority":
            events[0]["payload"]["admission_mode"] = "full_queue"
    elif reason == "document_block":
        events[0]["payload"]["initial_snapshot"]["trucks"]["T1"]["document_ok"] = False
    for row in events:
        payload = row["payload"]
        if row["kind"] == "TRUCK_ARRIVED":
            if reason in {"mandatory_priority", "full_queue_priority"} and payload["truck_id"] == "T4":
                payload["priority"] = 2
            elif reason == "document_block" and payload["truck_id"] == "T1":
                payload.update(document_ok=False, stage=0)
            continue
        if payload.get("truck_id") == "T1":
            payload["truck_id"] = selected_id
        if row["kind"] != "DECISION_RECORDED":
            continue
        decision = payload["decision"]
        decision.pop("policy", None)
        decision["selected"]["truck_id"] = selected_id
        if decision["selected"]["operation"] == "gate":
            decision["candidate_ids"] = admitted
            decision["candidate_order"] = [record for record in decision["candidate_order"] if record["truck_id"] in admitted]
            decision["justification"]["fifo_break"] = reason in {"avoidable", "full_queue_priority"}
        else:
            decision["candidate_ids"] = [selected_id]
            decision["candidate_order"][0]["truck_id"] = selected_id
    if reason == "document_block":
        events.append({"time": 30, "kind": "DOCUMENT_RELEASED", "payload": {"truck_id": "T1"}})
        events.sort(key=lambda row: row["time"])
    for sequence, row in enumerate(events, 1):
        row["sequence"] = sequence
    path.write_text("".join(json.dumps(row)+"\n" for row in events), encoding="utf-8")
    result = compute_policy_day_metrics(path)
    assert result.scalars["decision_count"] == 4
    assert result.scalars["raw_fifo_break_count"] == 1
    assert result.scalars["avoidable_fifo_break_count"] == (1 if reason in {"avoidable", "full_queue_priority"} else 0)
    assert result.scalars["fifo_break_count"] == (1 if reason in {"avoidable", "full_queue_priority"} else 0)
    assert result.scalars["fifo_break_rate"] == (0.25 if reason in {"avoidable", "full_queue_priority"} else 0)
    assert result.scalars["mandatory_decision_count"] == (4 if reason == "mandatory_priority" else 0)
