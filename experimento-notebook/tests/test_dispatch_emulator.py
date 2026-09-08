"""Behavioral contracts for dispatch policies and the discrete-event emulator."""

from __future__ import annotations

import math
import hashlib
import random
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from pequiflux_experiment.config import POLICY_NAMES, load_config
from pequiflux_experiment.digital_model import DigitalModel
from pequiflux_experiment.dispatch import (
    Candidate,
    DispatchBlocked,
    DispatchContext,
    DispatchPolicy,
    NoFeasibleCandidate,
    recommend,
)
import pequiflux_experiment.emulator as emulator_module
import pequiflux_experiment.dataset as dataset_module
import pequiflux_experiment.experiment as experiment_module
import pequiflux_experiment.validation_fixtures as fixture_module
from pequiflux_experiment.emulator import run_day, tiny_scenario
from pequiflux_experiment.validation_fixtures import build_validation_fixture
from pequiflux_experiment.domain import EventLatentLedger, ExecutionControls
from pequiflux_experiment.dataset import _coalesced_rain_rows, _disruption_payload_hash
from pequiflux_experiment.config import EVENT_RANKS
from pequiflux_experiment.policies import make_policy


def _run_fixture(scenario, seed, policy):
    fixture = build_validation_fixture(scenario, seed)
    return run_day(fixture.instance, policy, fixture.controls, fixture.event_latents)


def _simulation_fixture(scenario, seed, policy):
    fixture = build_validation_fixture(scenario, seed)
    return emulator_module._DaySimulation(fixture.instance, policy, fixture.controls, fixture.event_latents)


def candidate(truck_id: str, *, document_ok: bool) -> Candidate:
    return Candidate(
        truck_id=truck_id,
        arrival_time=0.0,
        priority=1,
        document_ok=document_ok,
        waiting_time=1.0,
    )


def dispatch_context(*, resource_available: bool) -> DispatchContext:
    return DispatchContext(
        now=1.0,
        resource_id="scale-1",
        resource_available=resource_available,
    )


@pytest.mark.parametrize("policy", POLICY_NAMES)
def test_blocked_truck_and_failed_resource_never_generate_command(policy: str) -> None:
    candidates = [
        candidate("T-blocked", document_ok=False),
        candidate("T-ok", document_ok=True),
    ]
    context = dispatch_context(resource_available=False)

    with pytest.raises(NoFeasibleCandidate, match="resource unavailable"):
        recommend(candidates, context, make_policy(policy))

    context = dispatch_context(resource_available=True)
    if policy == "fifo_strict":
        with pytest.raises(DispatchBlocked, match="T-blocked|document"):
            recommend(candidates, context, make_policy(policy))
    else:
        recommendation = recommend(candidates, context, make_policy(policy))
        assert recommendation.selected.truck_id == "T-ok"


@pytest.mark.parametrize("policy", POLICY_NAMES)
def test_policy_select_also_fails_closed_on_unavailable_resource(policy: str) -> None:
    with pytest.raises(NoFeasibleCandidate, match="resource unavailable"):
        make_policy(policy).select(
            [candidate("T-ok", document_ok=True)],
            dispatch_context(resource_available=False),
        )


def test_same_seed_produces_identical_events_and_metrics() -> None:
    scenario = tiny_scenario(truck_count=8, hoppers=1, scales=1, regime="nominal")
    first = _run_fixture(scenario, 101, make_policy("lexicographic"))
    second = _run_fixture(scenario, 101, make_policy("lexicographic"))

    assert [event.to_dict() for event in first.events] == [
        event.to_dict() for event in second.events
    ]
    assert first.metrics == second.metrics
    assert first.hard_constraint_violations == 0


def test_scale_in_and_scale_out_share_one_physical_pool() -> None:
    scenario = tiny_scenario(truck_count=4, hoppers=1, scales=1, regime="nominal")
    result = _run_fixture(scenario, 101, make_policy("fifo_strict"))

    started = [
        event.payload["operation"]
        for event in result.events
        if event.kind == "SERVICE_STARTED"
    ]
    assert set(started) == {"gate", "scale_in", "unload", "scale_out"}
    assert result.max_scale_occupancy <= 1


def _force_arrival_time(monkeypatch, arrival_time: float, *, priority: int | None = None) -> None:
    load_trucks = emulator_module._DaySimulation._load_frozen_trucks

    def load_trucks_at_time(simulation):
        load_trucks(simulation)
        simulation.schedule.clear()
        for state in simulation.states.values():
            state.arrival_time = state.stage_entry_time = arrival_time
            if priority is not None:
                state.priority = priority
            simulation._push(time=arrival_time, kind="arrival", truck_id=state.truck_id)

    monkeypatch.setattr(emulator_module._DaySimulation, "_load_frozen_trucks", load_trucks_at_time)


def test_parallel_pool_resources_do_not_assign_one_truck_twice(monkeypatch) -> None:
    # Queue all four trucks together to exercise actual parallel service;
    # a late NHPP arrival may legitimately remain at the hard horizon.
    _force_arrival_time(monkeypatch, 0.0)
    result = _run_fixture(
        tiny_scenario(truck_count=4, hoppers=2, scales=2, regime="nominal"),
        101,
        make_policy("lexicographic"),
    )

    assert result.completed_trucks == 4
    assert result.max_scale_occupancy == 2
    assert result.hard_constraint_violations == 0
    active = {}
    for event in result.events:
        if event.kind == "SERVICE_STARTED":
            truck_id = event.payload["truck_id"]
            assert truck_id not in active
            active[truck_id] = event.payload["resource_id"]
        elif event.kind == "SERVICE_COMPLETED":
            assert active.pop(event.payload["truck_id"]) == event.payload["resource_id"]
    assert not active


def test_every_selection_is_explained_then_accepted_before_service() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=2, hoppers=1, scales=1, regime="nominal"),
        101,
        make_policy("fifo_strict"),
    )

    for index, event in enumerate(result.events):
        if event.kind != "SERVICE_STARTED":
            continue
        assert index >= 2
        recommendation = result.events[index - 2]
        operator = result.events[index - 1]
        assert recommendation.kind == "DECISION_RECORDED"
        assert operator.kind == "OPERATOR_DECISION"
        assert operator.payload["decision"] == "accept"


def test_unknown_regime_fails_before_running_a_scenario() -> None:
    with pytest.raises(ValueError, match="unknown regime"):
        tiny_scenario(truck_count=2, hoppers=1, scales=1, regime="unrecognised")


class _RecordingPolicy(DispatchPolicy):
    name = "recording"

    def __init__(self) -> None:
        self.observations: list[tuple[int, tuple[str, ...]]] = []

    def rank_key(self, candidate, context, candidates=()):
        del context, candidates
        return (candidate.arrival_time, candidate.truck_id)

    def select(self, candidates, context):
        values = tuple(candidates)
        self.observations.append(
            (context.queue_length, tuple(candidate.truck_id for candidate in values))
        )
        return super().select(values, context)


def test_policy_context_excludes_future_and_non_arrived_trucks() -> None:
    policy = _RecordingPolicy()
    _run_fixture(tiny_scenario(truck_count=4, hoppers=1, scales=1), 101, policy)

    assert policy.observations
    assert all(queue_length == len(candidate_ids) for queue_length, candidate_ids in policy.observations)


def test_run_day_exposes_equivalent_independent_physical_and_digital_snapshots() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=2, hoppers=1, scales=1),
        101,
        make_policy("fifo_strict"),
    )

    assert result.physical_snapshot is not result.digital_snapshot
    assert result.physical_snapshot.canonical_dict() == result.digital_snapshot.canonical_dict()
    assert result.final_snapshot.canonical_dict() == result.physical_snapshot.canonical_dict()


def test_run_day_fails_with_diagnostic_when_physical_snapshot_diverges(monkeypatch) -> None:
    original = emulator_module._DaySimulation._final_snapshot

    def divergent_snapshot(simulation):
        snapshot = original(simulation)
        snapshot.clock += 1.0
        return snapshot

    monkeypatch.setattr(emulator_module._DaySimulation, "_final_snapshot", divergent_snapshot)

    with pytest.raises(RuntimeError, match="snapshot divergence"):
        _run_fixture(
            tiny_scenario(truck_count=2, hoppers=1, scales=1),
            101,
            make_policy("fifo_strict"),
        )


@pytest.mark.parametrize("seed", [101, 103])
def test_des_consumes_frozen_arrivals_documents_and_services_without_rng(monkeypatch, seed) -> None:
    # Materialize the ledger before the guard; the observed input is hand-set.
    fixture = build_validation_fixture(tiny_scenario(truck_count=2), seed)
    arrivals = {"T-001": 0.0, "T-002": 3.0}
    durations = {
        ("T-001", "gate"): 2.0, ("T-001", "scale_in"): 3.0,
        ("T-001", "unload"): 12.0, ("T-001", "scale_out"): 3.0,
        ("T-002", "gate"): 4.0, ("T-002", "scale_in"): 5.0,
        ("T-002", "unload"): 20.0, ("T-002", "scale_out"): 5.0,
    }
    instance = replace(
        fixture.instance,
        trucks=tuple(replace(truck, arrival_minute=arrivals[truck.truck_id],
                             truck_record_hash=None) for truck in fixture.instance.trucks),
        service_times=tuple(replace(row, duration_min=durations[row.truck_id, row.operation],
                                    service_record_hash=None) for row in fixture.instance.service_times),
        canonical_record_hash=None, instance_hash=None,
    )
    controls = ExecutionControls.build(
        ordinary_window=2, buffer_capacity=3, threshold_multiplier=Decimal("0.75"),
        intensity="base", event_latents_sha256=fixture.event_latents.event_latents_sha256,
        source_dataset_root_hash=hashlib.sha256(
            f"known-engineering-input:{instance.instance_hash}:{fixture.event_latents.event_latents_sha256}".encode()
        ).hexdigest(),
    )
    fixture = replace(fixture, instance=instance, controls=controls)
    original_instance = instance.to_dict()
    original_ledger = fixture.event_latents.to_rows()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("DES attempted to generate inputs or draw random values")

    for module, names in (
        (dataset_module, ("_rng", "_build_instance", "_build_event_latents", "generate_synthetic_dataset")),
        (fixture_module, ("_build_instance", "_build_event_latents", "build_validation_fixture", "build_validation_inputs")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    # Include the standard RNG APIs as well as the project's generator boundary.
    for module in (random, np.random):
        for name in dir(module):
            if not name.startswith("_") and callable(getattr(module, name)):
                monkeypatch.setattr(module, name, forbidden)

    events_by_policy = {}
    for policy_order in (POLICY_NAMES, tuple(reversed(POLICY_NAMES))):
        for policy in policy_order:
            result = run_day(instance, policy, controls, fixture.event_latents)
            observed_arrivals = {
                event.payload["truck_id"]: (event.time, event.payload["arrival_time"], event.payload["document_ok"])
                for event in result.events if event.kind == "TRUCK_ARRIVED"
            }
            assert observed_arrivals == {"T-001": (0.0, 0.0, True), "T-002": (3.0, 3.0, True)}
            assert {(event.payload["truck_id"], event.payload["operation"]): event.payload["duration_minutes"]
                    for event in result.commands} == durations
            starts = {(event.payload["truck_id"], event.payload["operation"]): event.time
                      for event in result.commands}
            completions = {(event.payload["truck_id"], event.payload["operation"]): event.time
                           for event in result.events if event.kind == "SERVICE_COMPLETED"}
            assert {key: completed_at - starts[key] for key, completed_at in completions.items()} == durations
            assert result.completed_trucks == 2
            assert result.instance_id == instance.instance_id
            assert result.instance_hash == result.execution_instance_hash == instance.instance_hash
            assert result.dataset_root_hash == controls.source_dataset_root_hash
            assert result.control_hash == controls.control_hash
            assert result.controls == controls
            assert result.metrics["buffer_capacity"] == 3
            assert result.events[0].payload["event_latents_sha256"] == fixture.event_latents.event_latents_sha256
            serialized = [event.to_dict() for event in result.events]
            if policy in events_by_policy:
                assert serialized == events_by_policy[policy]
            events_by_policy[policy] = serialized
    assert instance.to_dict() == original_instance
    assert fixture.event_latents.to_rows() == original_ledger

    first = fixture.instance.service_times[0]
    changed_service = replace(first, duration_min=first.source_b, service_record_hash=None)
    changed = replace(fixture.instance, service_times=(changed_service, *fixture.instance.service_times[1:]),
                      canonical_record_hash=None, instance_hash=None)
    changed_result = run_day(changed, "lexicographic", fixture.controls, fixture.event_latents)
    observed = next(event for event in changed_result.events if event.kind == "SERVICE_STARTED"
                    and event.payload["truck_id"] == first.truck_id and event.payload["operation"] == first.operation)
    assert observed.payload["duration_minutes"] == first.source_b
    completed = next(event for event in changed_result.events if event.kind == "SERVICE_COMPLETED"
                     and event.payload["truck_id"] == first.truck_id and event.payload["operation"] == first.operation)
    assert completed.time - observed.time == first.source_b
    assert changed_result.instance_hash == changed.instance_hash != result.instance_hash
    missing = replace(fixture.instance, service_times=fixture.instance.service_times[1:],
                      canonical_record_hash=None, instance_hash=None)
    with pytest.raises(ValueError, match="four positive durations"):
        run_day(missing, "lexicographic", fixture.controls, fixture.event_latents)
    with pytest.raises(TypeError, match="FrozenInstance"):
        run_day(tiny_scenario(), "lexicographic", fixture.controls, fixture.event_latents)
    forged_rows = tuple({
        **row, "instance_id": f"s00-seed{seed}",
        "latent_id": row["latent_id"].replace(fixture.instance.instance_id, f"s00-seed{seed}"),
    } for row in fixture.event_latents.to_rows())
    with pytest.raises(ValueError, match="scenario_id diverges"):
        EventLatentLedger(forged_rows)


@pytest.mark.parametrize("field", ["execution_instance_hash", "policy_name"])
def test_matrix_rejects_worker_result_from_wrong_projection_or_policy(tmp_path, monkeypatch, field):
    fixture = build_validation_fixture(tiny_scenario(truck_count=2))
    result = run_day(fixture.instance, "fifo_strict", fixture.controls, fixture.event_latents)
    forged = replace(result, **{field: "0" * 64 if field == "execution_instance_hash" else "lexicographic"})
    if field == "execution_instance_hash":
        # Keep the returned envelope and RUN_STARTED mutually consistent: only
        # comparison with the supplied frozen projection can expose this forgery.
        started = replace(result.events[0], payload={**result.events[0].payload, field: "0" * 64})
        forged = replace(forged, events=(started, *result.events[1:]))
    monkeypatch.setattr(experiment_module, "run_day", lambda *_args: forged)
    with pytest.raises(RuntimeError, match="worker result does not identify its consumed frozen input"):
        experiment_module.run_validation_matrix(
            [fixture.instance], ["fifo_strict"],
            load_config(Path(__file__).parents[1] / "config" / "confirmatory.json"),
            tmp_path / "runs", controls=fixture.controls, event_latents=fixture.event_latents,
        )
    assert not list((tmp_path / "runs").rglob("*.jsonl"))


def test_matrix_proves_ledger_contains_instance_before_namespace(tmp_path, monkeypatch):
    fixture = build_validation_fixture(tiny_scenario(truck_count=2), 101)
    other = build_validation_fixture(tiny_scenario(truck_count=2), 103)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("namespace or worker reached before proving the frozen input")

    monkeypatch.setattr(experiment_module, "create_run_directory", forbidden)
    monkeypatch.setattr(experiment_module, "run_day", forbidden)
    with pytest.raises(dataset_module.DatasetContractError, match="does not contain the supplied instance"):
        experiment_module.run_validation_matrix(
            [fixture.instance], ["fifo_strict"],
            load_config(Path(__file__).parents[1] / "config" / "confirmatory.json"),
            tmp_path / "runs", controls=other.controls, event_latents=other.event_latents,
        )
    assert not (tmp_path / "runs").exists()


def _overlap_fixture(*, unload_duration=20.0, failure_start=245.0):
    fixture = build_validation_fixture(tiny_scenario(truck_count=1, hoppers=2, regime="critical_failure"))
    truck = replace(fixture.instance.trucks[0], arrival_minute=230.0, cargo_type="soy",
                    document_status="CLEAR", truck_record_hash=None)
    services = tuple(replace(row, duration_min={"gate": 4.0, "scale_in": 5.0,
                         "unload": unload_duration, "scale_out": 5.0}[row.operation],
                         service_record_hash=None) for row in fixture.instance.service_times)
    rows = list(fixture.event_latents.to_rows())
    for row in rows:
        payload = row["payload"]
        if row["latent_kind"] == "document":
            payload["u"] = 0.99
        elif row["latent_kind"] == "rain_block":
            payload["u"] = 0.0 if payload["block_index"] == 8 else 0.99
        elif row["latent_kind"] == "forced_failure":
            payload.update(start_minute=failure_start, duration_min=40.0, end_minute=failure_start + 40.0)
    ledger = EventLatentLedger(tuple(rows))
    failure = dict(next(row for row in fixture.instance.disruptions if row["cause"] == "critical_failure"))
    failure.update(time=failure_start, duration_min=40.0, return_time=failure_start + 40.0)
    disruptions = [failure, *_coalesced_rain_rows(fixture.instance,
        [row for row in rows if row["latent_kind"] == "rain_block" and row["payload"]["u"] == 0.0])]
    disruptions.sort(key=lambda row: (row["time"], row["event_rank"], row["resource_id"], row["truck_id"]))
    for index, row in enumerate(disruptions, 1):
        row["sequence"] = index
        row["payload_hash"] = _disruption_payload_hash(row)
    instance = replace(fixture.instance, trucks=(truck,), service_times=services,
                       disruptions=tuple(disruptions), canonical_record_hash=None, instance_hash=None)
    controls = ExecutionControls.build(**{key: value for key, value in fixture.controls.to_dict().items()
        if key not in {"control_hash", "event_latents_sha256"}}, event_latents_sha256=ledger.event_latents_sha256)
    return instance, controls, ledger


@pytest.mark.parametrize("unload_duration,failure_start", ((20.0, 245.0), (35.0, 245.0), (31.0, 270.0)))
def test_nonpreemptive_failure_rain_overlap_and_same_timestamp_order(unload_duration, failure_start):
    instance, controls, ledger = _overlap_fixture(unload_duration=unload_duration, failure_start=failure_start)
    result = run_day(instance, "lexicographic", controls, ledger)
    completion = next(event.time for event in result.events if event.kind == "SERVICE_COMPLETED"
                      and event.payload["operation"] == "unload")
    assert completion == 239.0 + unload_duration
    evidence = [event for event in result.events if event.kind == "DISRUPTION_RECORDED"]
    critical = next(event.payload for event in evidence if event.payload["cause"] == "critical_failure")
    assert critical["effective_failure_start"] == max(failure_start, completion)
    assert critical["recovery_time"] == max(failure_start, completion) + 40.0
    recovered = [event.time for event in result.events if event.kind == "RESOURCE_RECOVERED"]
    assert recovered == [critical["recovery_time"]]
    assert all(not (completion <= event.time < critical["recovery_time"])
               for event in result.events if event.kind == "SERVICE_STARTED"
               and event.payload["resource_id"] == "hopper-1")
    # Completion precedes the public failure; at a rain-end/failure collision,
    # all same-time changes settle before dispatch and the new failure wins.
    same_time = [event.kind for event in result.events if event.time == completion]
    assert same_time.index("SERVICE_COMPLETED") < same_time.index("RESOURCE_FAILED")
    assert EVENT_RANKS["rain_end"] < EVENT_RANKS["resource_failure"]


def test_service_durations_use_canonical_triangular_ranges() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=4, hoppers=1, scales=1, regime="nominal"),
        101,
        make_policy("fifo_strict"),
    )
    starts = {
        (event.payload["truck_id"], event.payload["operation"]): event.time
        for event in result.events
        if event.kind == "SERVICE_STARTED"
    }
    completions = {
        (event.payload["truck_id"], event.payload["operation"]): event.time
        for event in result.events
        if event.kind == "SERVICE_COMPLETED"
    }
    bounds = {
        "gate": (2.0, 7.0),
        "scale_in": (3.0, 8.0),
        "unload": (12.0, 35.0),
        "scale_out": (3.0, 8.0),
    }
    assert starts.keys() == completions.keys()
    for key, started_at in starts.items():
        operation = key[1]
        duration = completions[key] - started_at
        lower, upper = bounds[operation]
        assert lower <= duration <= upper
        assert math.isfinite(duration)


@pytest.mark.parametrize("regime", ("critical_failure", "priority_shift"))
def test_canonical_disruption_regimes_emit_public_events(regime: str) -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=60, hoppers=2, scales=1, regime=regime),
        101,
        make_policy("lexicographic"),
    )
    kinds = {event.kind for event in result.events}
    if regime == "critical_failure":
        assert {"RESOURCE_FAILED", "RESOURCE_RECOVERED"} <= kinds
        assert any(
            event.payload.get("cause") == "critical_failure"
            for event in result.events
            if event.kind == "DISRUPTION_RECORDED"
        )
    else:
        changed = [event for event in result.events if event.kind == "PRIORITY_CHANGED"]
        assert changed
        assert all(event.payload["priority"] == 2 for event in changed)


def test_rain_blocks_exposed_hopper_with_failure_recovery_events() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=60, hoppers=2, scales=1, regime="nominal"),
        101,
        make_policy("lexicographic"),
    )
    rain_failures = [
        event
        for event in result.events
        if event.kind == "RESOURCE_FAILED" and event.payload.get("cause") == "rain"
    ]
    rain_recoveries = [
        event
        for event in result.events
        if event.kind == "RESOURCE_RECOVERED" and event.payload.get("cause") == "rain"
    ]
    assert rain_failures
    assert rain_recoveries
    assert all(event.payload["resource_id"] == "hopper-1" for event in rain_failures)
    assert all(event.payload["resource_id"] == "hopper-1" for event in rain_recoveries)


def test_horizon_censors_wait_and_reports_buffer_remnants() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=60, hoppers=1, scales=1, regime="nominal"),
        101,
        make_policy("fifo_strict"),
    )
    assert result.events[-1].kind == "END_OF_DAY"
    assert result.events[-1].time == 720.0
    assert result.metrics["horizon_minutes"] == 720
    assert result.metrics["makespan_minutes"] <= 720.0
    assert result.completed_trucks < 60
    assert result.metrics["remaining_trucks"] == 60 - result.completed_trucks
    assert result.metrics["max_buffer_occupancy"] <= 12
    assert result.metrics["censored_wait_minutes"] >= 0.0


def test_makespan_is_relative_to_first_arrival() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=4, hoppers=1, scales=1, regime="nominal"),
        101,
        make_policy("fifo_strict"),
    )
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
    expected = round(last_completion - first_arrival, 12)
    assert result.metrics["makespan_minutes"] == expected
    assert result.metrics["throughput_rate"] == round(
        result.completed_trucks / expected, 12
    )


def test_zero_completion_fails_closed_without_fabricated_makespan(monkeypatch) -> None:
    # Even the shortest gate service cannot complete before the hard horizon.
    _force_arrival_time(monkeypatch, 719.0)
    with pytest.raises(RuntimeError, match="no SERVICE_COMPLETED|makespan"):
        _run_fixture(
            tiny_scenario(truck_count=1, hoppers=1, scales=1, regime="nominal"),
            327,
            make_policy("fifo_strict"),
        )


class _ScaleOutFirstPolicy(DispatchPolicy):
    name = "scale_out_first"

    def __init__(self) -> None:
        self.observations: list[tuple[tuple[str, ...], str]] = []

    def rank_key(self, candidate, context, candidates=()):
        del context, candidates
        return (
            0 if candidate.operation == "scale_out" else 1,
            candidate.arrival_time,
            candidate.truck_id,
        )

    def select(self, candidates, context):
        values = tuple(candidates)
        selected = super().select(values, context)
        self.observations.append(
            (tuple(sorted({candidate.operation for candidate in values})), selected.operation)
        )
        return selected


def test_reentrant_scale_pool_competes_scale_in_and_scale_out_in_one_dispatch(monkeypatch) -> None:
    # Homogeneous priorities keep both scale operations in the admissible pool.
    _force_arrival_time(monkeypatch, 0.0, priority=0)
    policy = _ScaleOutFirstPolicy()
    result = _run_fixture(
        tiny_scenario(truck_count=12, hoppers=1, scales=1, regime="nominal"),
        101,
        policy,
    )

    mixed = [selected for operations, selected in policy.observations if operations == ("scale_in", "scale_out")]
    assert mixed
    assert set(mixed) == {"scale_out"}
    assert result.max_scale_occupancy <= 1


@pytest.mark.parametrize("truck_count", (120, 180))
def test_buffer_reserves_upstream_trucks_destined_to_unload(truck_count: int) -> None:
    """The unload buffer includes upstream/in-flight reservations, not only its queue."""

    result = _run_fixture(
        tiny_scenario(truck_count=truck_count, hoppers=1, scales=1, regime="nominal"),
        101,
        make_policy("fifo_strict"),
    )

    assert result.hard_constraint_violations == 0
    assert result.metrics["buffer_capacity"] == 12
    assert result.metrics["max_buffer_occupancy"] <= 12
    assert result.metrics["max_buffer_reservation"] <= 12


def _per_truck_waits_from_events(result):
    ready: dict[str, float] = {}
    totals: dict[str, float] = {}
    active: set[str] = set()
    completed: set[str] = set()
    released: set[str] = set()
    for event in result.events:
        payload = event.to_dict()["payload"]
        if event.kind == "TRUCK_ARRIVED":
            truck_id = payload["truck_id"]
            if payload["document_ok"]:
                ready[truck_id] = float(payload["arrival_time"])
                released.add(truck_id)
        elif event.kind == "DOCUMENT_RELEASED":
            truck_id = payload["truck_id"]
            ready[truck_id] = event.time
            released.add(truck_id)
        elif event.kind == "SERVICE_STARTED":
            truck_id = payload["truck_id"]
            totals.setdefault(truck_id, 0.0)
            totals[truck_id] += max(0.0, event.time - ready[truck_id])
            active.add(truck_id)
        elif event.kind == "SERVICE_COMPLETED":
            truck_id = payload["truck_id"]
            active.discard(truck_id)
            if payload.get("operation") != "scale_out":
                ready[truck_id] = event.time
            else:
                completed.add(truck_id)
    censored = 0.0
    for truck_id in sorted(released - completed - active):
        residual = max(0.0, 720.0 - ready[truck_id])
        totals.setdefault(truck_id, 0.0)
        totals[truck_id] += residual
        censored += residual
    waits = [totals.get(f"T-{index:03d}", 0.0) for index in range(1, result.scenario.truck_count + 1)]
    return waits, censored


def test_wait_metrics_are_per_truck_and_include_censored_horizon_wait() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=60, hoppers=1, scales=1, regime="nominal"),
        101,
        make_policy("fifo_strict"),
    )

    waits, censored = _per_truck_waits_from_events(result)
    ordered = sorted(waits)
    p95_index = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    assert result.metrics["mean_wait_minutes"] == round(sum(waits) / len(waits), 12)
    assert result.metrics["p95_wait_minutes"] == round(ordered[p95_index], 12)
    assert result.metrics["censored_wait_minutes"] == round(censored, 12)


def test_common_random_numbers_are_policy_independent() -> None:
    scenario = tiny_scenario(truck_count=12, hoppers=2, scales=1, regime="critical_failure")
    fifo_simulation = _simulation_fixture(scenario, 101, make_policy("fifo_strict"))
    lex_simulation = _simulation_fixture(scenario, 101, make_policy("lexicographic"))
    # Exogenous draws must agree. Public failure times may be deferred until
    # a busy resource completes its current, policy-dependent service.
    assert fifo_simulation.schedule == lex_simulation.schedule
    fifo = fifo_simulation.run()
    lexicographic = lex_simulation.run()

    def realizations(result):
        arrivals = {
            event.payload["truck_id"]: (
                event.payload["arrival_time"],
                event.payload["document_ok"],
            )
            for event in result.events
            if event.kind == "TRUCK_ARRIVED"
        }
        durations = {
            (event.payload["truck_id"], event.payload["operation"]): event.payload["duration_minutes"]
            for event in result.events
            if event.kind == "SERVICE_STARTED"
        }
        return arrivals, durations

    fifo_arrivals, fifo_durations = realizations(fifo)
    lex_arrivals, lex_durations = realizations(lexicographic)
    assert fifo_arrivals == lex_arrivals
    common = fifo_durations.keys() & lex_durations.keys()
    assert common
    assert all(fifo_durations[key] == lex_durations[key] for key in common)


def test_fixed_score_weights_waiting_before_priority_with_deterministic_ties() -> None:
    policy = make_policy("fixed_score")
    context = DispatchContext(
        now=10.0,
        resource_id="hopper-1",
        operation="unload",
    )
    candidates = (
        Candidate(
            "T-wait",
            priority=0,
            waiting_time=10.0,
            affinity=0.0,
            operation="unload",
            resource_id="hopper-1",
            stable_order=1,
        ),
        Candidate(
            "T-priority",
            priority=10,
            waiting_time=0.0,
            affinity=0.0,
            operation="unload",
            resource_id="hopper-1",
            stable_order=0,
        ),
    )

    # With both components normalized to one, the specified 0.45 waiting
    # weight selects T-wait; the inverted priority/waiting weights select
    # T-priority instead.
    assert policy.select(candidates, context).truck_id == "T-wait"

    rules = recommend(candidates, context, policy).to_dict()["justification"][
        "activated_rules"
    ]
    policy_index = rules.index("policy:fixed_score")
    assert tuple(rules[policy_index - 3 : policy_index]) == (
        "waiting_window",
        "priority_score",
        "affinity_score",
    )

    tied = (
        Candidate("T-late", arrival_time=1.0, priority=1, waiting_time=1.0),
        Candidate("T-early", arrival_time=0.0, priority=1, waiting_time=1.0),
    )
    assert policy.select(tied, context).truck_id == "T-early"


def test_dispatch_hard_filters_cargo_before_affinity_ranking() -> None:
    """A corn truck must not be sent to the soy-only hopper."""

    candidates = (
        Candidate(
            "T-corn",
            cargo_type="corn",
            operation="unload",
            resource_id="hopper-2",
            stage_entry_time=0.0,
            waiting_time=10.0,
            affinity=1.0,
        ),
        Candidate(
            "T-soy",
            cargo_type="soy",
            operation="unload",
            resource_id="hopper-2",
            stage_entry_time=1.0,
            waiting_time=0.0,
            affinity=0.0,
        ),
    )
    context = DispatchContext(
        now=10.0,
        resource_id="hopper-2",
        operation="unload",
        allowed_cargo_types=("soy",),
    )

    recommendation = recommend(candidates, context, make_policy("lexicographic"))

    assert recommendation.selected.truck_id == "T-soy"
    assert "resource_compatibility" in recommendation.to_dict()["justification"]["activated_rules"]


@pytest.mark.parametrize(
    "candidates",
    (
        (
            Candidate("T-priority-corn", cargo_type="corn", priority=2, stage_entry_time=0.0),
            Candidate("T-soy", cargo_type="soy", priority=0, stage_entry_time=1.0),
        ),
        tuple(
            [
                Candidate(
                    f"T-corn-{index}",
                    cargo_type="corn",
                    stage_entry_time=float(index),
                )
                for index in range(6)
            ]
            + [Candidate("T-soy", cargo_type="soy", stage_entry_time=6.0)]
        ),
    ),
)
def test_admissible_window_filters_cargo_before_priority_and_top_h0(
    candidates: tuple[Candidate, ...],
) -> None:
    simulation = _simulation_fixture(
        tiny_scenario(truck_count=1, hoppers=2, scales=1, regime="nominal"),
        101,
        make_policy("lexicographic"),
    )

    admissible = simulation._admissible_candidates(
        candidates,
        allowed_cargo_types=("soy",),
    )

    assert tuple(candidate.truck_id for candidate in admissible) == ("T-soy",)


def test_fifo_strict_blocks_first_stage_entry_instead_of_skipping() -> None:
    candidates = (
        Candidate(
            "T-first",
            document_ok=False,
            stage_entry_time=1.0,
            operation="gate",
            resource_id="gate-1",
        ),
        Candidate(
            "T-second",
            document_ok=True,
            stage_entry_time=2.0,
            operation="gate",
            resource_id="gate-1",
        ),
    )
    context = DispatchContext(
        now=3.0,
        resource_id="gate-1",
        operation="gate",
        allowed_cargo_types=("soy", "corn"),
    )

    with pytest.raises(DispatchBlocked, match="T-first|document"):
        recommend(candidates, context, make_policy("fifo_strict"))

    assert recommend(candidates, context, make_policy("fifo_flow_faithful")).selected.truck_id == "T-second"

    global_arrival_conflicts_with_stage_entry = (
        Candidate(
            "T-global-old",
            arrival_time=0.0,
            stage_entry_time=2.0,
            operation="gate",
            resource_id="gate-1",
        ),
        Candidate(
            "T-stage-old",
            arrival_time=1.0,
            stage_entry_time=1.0,
            operation="gate",
            resource_id="gate-1",
        ),
    )
    assert (
        recommend(
            global_arrival_conflicts_with_stage_entry,
            context,
            make_policy("fifo_flow_faithful"),
        ).selected.truck_id
        == "T-stage-old"
    )


def test_lexicographic_h_uses_pressure_wait_reorder_affinity_then_stage_entry() -> None:
    policy = make_policy("lexicographic")
    context = DispatchContext(
        now=10.0,
        resource_id="scale-1",
        operation="scale_in",
        allowed_cargo_types=("soy", "corn"),
    )
    candidates = (
        Candidate(
            "T-pressure",
            cargo_type="soy",
            priority=0,
            pressure=4.0,
            waiting_time=1.0,
            reorder_penalty=0.0,
            affinity=0.0,
            stage_entry_time=9.0,
            operation="scale_in",
        ),
        Candidate(
            "T-priority",
            cargo_type="corn",
            priority=2,
            pressure=0.0,
            waiting_time=10.0,
            reorder_penalty=10.0,
            affinity=1.0,
            stage_entry_time=8.0,
            operation="scale_in",
        ),
    )

    assert policy.select(candidates, context).truck_id == "T-pressure"

    tied = (
        Candidate("T-late", stage_entry_time=2.0, reorder_penalty=1.0, stable_order=0),
        Candidate("T-early", stage_entry_time=1.0, reorder_penalty=1.0, stable_order=99),
    )
    assert policy.select(tied, context).truck_id == "T-early"

    reorder_precedes_affinity = (
        Candidate(
            "T-no-reorder",
            pressure=1.0,
            waiting_time=1.0,
            affinity=0.0,
            stage_entry_time=1.0,
        ),
        Candidate(
            "T-reordered",
            pressure=1.0,
            waiting_time=1.0,
            affinity=1.0,
            stage_entry_time=2.0,
        ),
    )
    assert policy.select(reorder_precedes_affinity, context).truck_id == "T-no-reorder"


@pytest.mark.parametrize("hoppers,scales,expected_resource", ((1, 1, "hopper-1"), (2, 1, "hopper-1"), (3, 1, "scale-1"), (3, 2, "hopper-1")))
def test_critical_failure_uses_only_frozen_nominal_bottleneck(hoppers, scales, expected_resource) -> None:
    fixture = build_validation_fixture(tiny_scenario(truck_count=12, hoppers=hoppers, scales=scales, regime="critical_failure"))
    result = run_day(fixture.instance, "fifo_flow_faithful", fixture.controls, fixture.event_latents)
    failures = [event for event in result.events if event.kind == "DISRUPTION_RECORDED" and event.payload["cause"] != "rain"]
    assert len(failures) == 1
    failure = failures[0].payload
    frozen = next(row for row in fixture.instance.disruptions if row["cause"] == "critical_failure")
    assert failure["resource_id"] == expected_resource
    assert failure["scheduled_failure_start"] == frozen["time"]
    assert failure["scheduled_failure_duration"] == frozen["duration_min"]
    assert failure["recovery_time"] == failure["effective_failure_start"] + frozen["duration_min"]


def test_priority_shift_promotion_survives_future_arrival() -> None:
    result = _run_fixture(
        tiny_scenario(truck_count=12, hoppers=2, scales=1, regime="priority_shift"),
        101,
        make_policy("fifo_flow_faithful"),
    )
    changes = {
        event.payload["truck_id"]: event
        for event in result.events
        if event.kind == "PRIORITY_CHANGED"
    }
    arrivals = {
        event.payload["truck_id"]: event
        for event in result.events
        if event.kind == "TRUCK_ARRIVED"
    }

    assert changes
    assert all(changes[truck_id].time < arrivals[truck_id].time for truck_id in changes)
    assert all(arrivals[truck_id].payload["priority"] == 2 for truck_id in changes)
    assert all(result.final_snapshot.trucks[truck_id].priority == 2 for truck_id in changes)


def test_candidates_are_built_from_detached_digital_snapshot_not_physical_state() -> None:
    simulation = _simulation_fixture(
        tiny_scenario(truck_count=1, hoppers=1, scales=1, regime="nominal"),
        101,
        make_policy("fifo_flow_faithful"),
    )
    state = next(iter(simulation.states.values()))
    simulation.digital_model = DigitalModel.from_snapshot(
        simulation._initial_snapshot(), scenario=simulation.scenario
    )
    simulation._emit("RUN_STARTED", {"scenario_id": simulation.scenario.scenario_id})
    simulation.clock = state.arrival_time
    simulation._emit(
        "TRUCK_ARRIVED",
        {
            "truck_id": state.truck_id,
            "arrival_time": state.arrival_time,
            "cargo_type": state.cargo_type,
            "priority": state.priority,
            "document_ok": True,
            "stage": 1,
        },
    )

    original_priority = state.priority
    state.arrived = False
    state.priority = 99
    candidates = simulation._candidate_values(
        "gate-1", ("gate",), snapshot=simulation._digital_snapshot()
    )

    assert candidates and candidates[0].truck_id == state.truck_id
    assert candidates[0].priority == original_priority
    assert simulation.digital_model is not None
    assert simulation.digital_model.snapshot().trucks[state.truck_id] is not state
