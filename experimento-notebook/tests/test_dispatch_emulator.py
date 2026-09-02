"""Behavioral contracts for dispatch policies and the discrete-event emulator."""

from __future__ import annotations

import math

import pytest

from pequiflux_experiment.config import POLICY_NAMES
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
from pequiflux_experiment.emulator import run_day, tiny_scenario
from pequiflux_experiment.policies import make_policy


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
    first = run_day(scenario, 101, make_policy("lexicographic"))
    second = run_day(scenario, 101, make_policy("lexicographic"))

    assert [event.to_dict() for event in first.events] == [
        event.to_dict() for event in second.events
    ]
    assert first.metrics == second.metrics
    assert first.hard_constraint_violations == 0


def test_scale_in_and_scale_out_share_one_physical_pool() -> None:
    scenario = tiny_scenario(truck_count=4, hoppers=1, scales=1, regime="nominal")
    result = run_day(scenario, 101, make_policy("fifo_strict"))

    started = [
        event.payload["operation"]
        for event in result.events
        if event.kind == "SERVICE_STARTED"
    ]
    assert set(started) == {"gate", "scale_in", "unload", "scale_out"}
    assert result.max_scale_occupancy <= 1


def test_parallel_pool_resources_do_not_assign_one_truck_twice() -> None:
    result = run_day(
        tiny_scenario(truck_count=4, hoppers=2, scales=2, regime="nominal"),
        101,
        make_policy("lexicographic"),
    )

    assert result.completed_trucks == 4
    assert result.hard_constraint_violations == 0


def test_every_selection_is_explained_then_accepted_before_service() -> None:
    result = run_day(
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
    run_day(tiny_scenario(truck_count=4, hoppers=1, scales=1), 101, policy)

    assert policy.observations
    assert all(queue_length == len(candidate_ids) for queue_length, candidate_ids in policy.observations)


def test_run_day_exposes_equivalent_independent_physical_and_digital_snapshots() -> None:
    result = run_day(
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
        run_day(
            tiny_scenario(truck_count=2, hoppers=1, scales=1),
            101,
            make_policy("fifo_strict"),
        )


def test_canonical_nhpp_blocks_and_document_block_rate() -> None:
    """Arrivals and document blocks follow the frozen protocol inputs."""

    scenario = tiny_scenario(truck_count=2000, hoppers=1, scales=1, regime="nominal")
    simulation = emulator_module._DaySimulation(scenario, 101, make_policy("fifo_strict"))
    arrival_times = [state.arrival_time for state in simulation.states.values()]

    assert len(arrival_times) == 2000
    assert all(0.0 <= value <= 720.0 for value in arrival_times)
    block_edges = (0.0, 180.0, 300.0, 480.0, 720.0)
    block_counts = [
        sum(start <= value < end for value in arrival_times)
        for start, end in zip(block_edges, block_edges[1:])
    ]
    assert all(count > 0 for count in block_counts)
    # Conditional NHPP weights are (6, 3, 7, 2) over the four block lengths;
    # these broad bounds reject the previous all-early uniform stream while
    # allowing ordinary seed-to-seed multinomial variation.
    assert block_counts[0] < 900
    assert 140 < block_counts[1] < 330
    assert 650 < block_counts[2] < 950
    assert 180 < block_counts[3] < 430

    blocked = sum(not state.document_ok for state in simulation.states.values())
    assert 0.01 <= blocked / len(simulation.states) <= 0.06


def test_service_durations_use_canonical_triangular_ranges() -> None:
    result = run_day(
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
    result = run_day(
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
            if event.kind == "RESOURCE_FAILED"
        )
    else:
        changed = [event for event in result.events if event.kind == "PRIORITY_CHANGED"]
        assert changed
        assert all(event.payload["priority"] == 2 for event in changed)


def test_rain_blocks_exposed_hopper_with_failure_recovery_events() -> None:
    result = run_day(
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
    result = run_day(
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
    result = run_day(
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


def test_zero_completion_fails_closed_without_fabricated_makespan() -> None:
    with pytest.raises(RuntimeError, match="no SERVICE_COMPLETED|makespan"):
        run_day(
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


def test_reentrant_scale_pool_competes_scale_in_and_scale_out_in_one_dispatch() -> None:
    policy = _ScaleOutFirstPolicy()
    result = run_day(
        tiny_scenario(truck_count=60, hoppers=1, scales=1, regime="nominal"),
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

    result = run_day(
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
    result = run_day(
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
    fifo = run_day(scenario, 101, make_policy("fifo_strict"))
    lexicographic = run_day(scenario, 101, make_policy("lexicographic"))

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
        disruptions = tuple(
            (
                event.kind,
                event.time,
                event.payload.get("resource_id"),
                event.payload.get("cause"),
                event.payload.get("priority"),
            )
            for event in result.events
            if event.kind in {"RESOURCE_FAILED", "RESOURCE_RECOVERED", "PRIORITY_CHANGED"}
        )
        return arrivals, durations, disruptions

    fifo_arrivals, fifo_durations, fifo_disruptions = realizations(fifo)
    lex_arrivals, lex_durations, lex_disruptions = realizations(lexicographic)
    assert fifo_arrivals == lex_arrivals
    assert fifo_disruptions == lex_disruptions
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
    simulation = emulator_module._DaySimulation(
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


def test_critical_failure_has_base_substream_and_forced_hopper_override() -> None:
    scenario = tiny_scenario(truck_count=4, hoppers=2, scales=1, regime="critical_failure")
    # Seed 23 is frozen because its independent shift-level Bernoulli is below
    # 5%, so this run must contain both the base draw and the regime override.
    result = run_day(scenario, 23, make_policy("fifo_flow_faithful"))
    failures = [event for event in result.events if event.kind == "RESOURCE_FAILED"]

    base = [event for event in failures if event.payload.get("cause") == "base_failure"]
    forced = [
        event
        for event in failures
        if event.payload.get("cause") == "critical_failure"
    ]
    assert len(base) == 1
    assert len(forced) == 1
    assert base[0].payload["resource_id"] != forced[0].payload["resource_id"]
    assert forced[0].payload["resource_id"] == "hopper-1"
    assert 240.0 <= forced[0].time <= 480.0
    assert all(
        20.0 <= float(event.payload.get("duration_minutes", 20.0)) <= 70.0
        for event in failures
        if event.payload.get("cause") == "critical_failure"
    )


def test_priority_shift_promotion_survives_future_arrival() -> None:
    result = run_day(
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
    simulation = emulator_module._DaySimulation(
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
    candidates = simulation._candidate_values("gate-1", ("gate",))

    assert candidates and candidates[0].truck_id == state.truck_id
    assert candidates[0].priority == original_priority
    assert simulation.digital_model is not None
    assert simulation.digital_model.snapshot().trucks[state.truck_id] is not state
