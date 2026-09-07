"""Synthetic operator responses exercise real DES commands without human claims."""

import pytest

from pequiflux_experiment import emulator
from pequiflux_experiment.digital_model import replay_events
from pequiflux_experiment.events import EventRecord, read_jsonl, write_jsonl
from pequiflux_experiment.policies import make_policy
from pequiflux_experiment.validation_fixtures import build_validation_fixture


def test_strict_fifo_override_cannot_bypass_mandatory_admission():
    from pequiflux_experiment.dispatch import Candidate, DispatchContext, recommend
    from pequiflux_experiment.operator import SyntheticOperatorResponse

    fixture = build_validation_fixture(emulator.tiny_scenario(truck_count=4))
    policy = make_policy("fifo_strict")
    recommendation = recommend(
        (Candidate("mandatory", priority=2, operation="gate"),
         Candidate("ordinary", priority=0, operation="gate", stage_entry_time=1)),
        DispatchContext(now=2, operation="gate", resource_id="gate-1"), policy,
    )
    assert {candidate.truck_id for candidate in recommendation.candidates} == {"mandatory", "ordinary"}
    simulation = emulator._DaySimulation(
        fixture.instance, policy, fixture.controls, fixture.event_latents,
        operator_script=lambda _: SyntheticOperatorResponse("override", "Synthetic forbidden demotion", "ordinary"),
    )
    with pytest.raises(ValueError, match="mandatory-priority/window admission"):
        simulation._apply_operator_response(recommendation, "gate-1")
    assert not simulation.events
    assert all(state.active_operation is None for state in simulation.states.values())


@pytest.mark.parametrize("action", ["accept", "reject", "override"])
def test_synthetic_responses_execute_only_the_resolved_admissible_command(action, tmp_path):
    from pequiflux_experiment.operator import SyntheticOperatorResponse

    fixture = build_validation_fixture(emulator.tiny_scenario(truck_count=4))
    exercised = False

    def script(recommendation):
        nonlocal exercised
        if action == "reject" and not exercised:
            exercised = True
            return SyntheticOperatorResponse("reject", "Synthetic refusal at first decision")
        if action == "override" and not exercised:
            alternatives = [candidate for candidate in recommendation.candidates
                            if candidate.truck_id != recommendation.selected_truck_id]
            if not alternatives:
                return SyntheticOperatorResponse("reject", "Synthetic hold until another admissible candidate")
            exercised = True
            return SyntheticOperatorResponse("override", "Synthetic admissible alternative",
                                             selected_truck_id=alternatives[-1].truck_id)
        return SyntheticOperatorResponse("accept", "Synthetic acceptance")

    result = emulator.run_synthetic_operator_trial(
        fixture.instance, "fifo_flow_faithful", fixture.controls, fixture.event_latents,
        operator_script=script,
    )
    assert result.events[0].payload["operator_mode"] == "synthetic_scripted"
    responses = [event for event in result.events if event.kind == "OPERATOR_DECISION"]
    assert action in {event.payload["decision"] for event in responses}
    for index, event in enumerate(result.events):
        if event.kind != "OPERATOR_DECISION":
            continue
        assert event.payload["origin"] == "simulated"
        assert event.payload["operator_mode"] == "synthetic_scripted"
        assert event.payload["reason"]
        resource_id = event.payload["recommendation"]["resource_id"]
        starts = [later for later in result.events[index + 1:]
                  if later.kind == "SERVICE_STARTED" and later.payload["resource_id"] == resource_id]
        if event.payload["decision"] == "reject":
            assert event.payload["selection"] is None
            assert not starts or starts[0].time > event.time
        else:
            assert result.events[index + 1].kind == "SERVICE_STARTED"
            assert starts[0].payload["truck_id"] == event.payload["selection"]["truck_id"]
            if event.payload["decision"] == "override":
                assert event.payload["selection"]["truck_id"] != event.payload["recommendation"]["selected"]["truck_id"]
    log_path = tmp_path / f"synthetic-{action}.jsonl"
    write_jsonl(log_path, result.events)
    persisted = read_jsonl(log_path)
    assert replay_events(persisted, physical=result.initial_snapshot).canonical_dict() == result.final_snapshot.canonical_dict()
    assert result.hard_constraint_violations == 0
    if action == "override":
        override_index = next(index for index, event in enumerate(persisted)
                              if event.kind == "OPERATOR_DECISION" and event.payload["decision"] == "override")
        for field, value in (("origin", "human"), ("selection", {"truck_id": "not-offered"})):
            events = list(persisted)
            raw = events[override_index].to_dict()
            raw["payload"][field] = value
            events[override_index] = EventRecord.from_dict(raw)
            with pytest.raises(ValueError, match="origin|admissible"):
                replay_events(events, physical=result.initial_snapshot)


@pytest.mark.parametrize("invalid_response", ["future_truck", "missing_response"])
def test_invalid_synthetic_response_fails_before_any_service_starts(invalid_response):
    from pequiflux_experiment.operator import SyntheticOperatorResponse

    fixture = build_validation_fixture(emulator.tiny_scenario(truck_count=4))

    def script(recommendation):
        if invalid_response == "missing_response":
            return None
        future_truck = next(truck for truck in fixture.instance.trucks
                            if truck.truck_id not in recommendation.to_dict()["candidate_ids"])
        assert future_truck.arrival_minute > recommendation.now
        return SyntheticOperatorResponse("override", "Synthetic inadmissible future arrival",
                                         selected_truck_id=future_truck.truck_id)

    simulation = emulator._DaySimulation(
        fixture.instance, make_policy("fifo_flow_faithful"), fixture.controls,
        fixture.event_latents, operator_script=script,
    )
    with pytest.raises((ValueError, TypeError), match="admissible|no implicit acceptance"):
        simulation.run()
    assert not any(event.kind == "SERVICE_STARTED" for event in simulation.events)
    assert all(state.active_operation is None for state in simulation.states.values())
