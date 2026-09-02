"""Behavioral contract for the independent digital-yard replay model."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pequiflux_experiment.digital_model import DigitalModel, replay_events
from pequiflux_experiment.domain import Resource, Truck, YardSnapshot
from pequiflux_experiment.events import (
    EventRecord,
    read_jsonl,
    write_jsonl,
)


def _physical_snapshot() -> YardSnapshot:
    return YardSnapshot(
        trucks={
            "T-001": Truck("T-001", 0.0, "soy", 1, False, 0)
        },
        resources={"scale-1": Resource(resource_id="scale-1", kind="scale")},
        clock=0.0,
    )


def _arrival_event() -> EventRecord:
    return EventRecord(
        time=1.5,
        sequence=1,
        kind="TRUCK_ARRIVED",
        payload={
            "truck_id": "T-001",
            "arrival_time": 1.5,
            "cargo_type": "soy",
            "priority": 1,
            "document_ok": True,
            "stage": 0,
        },
    )


def test_event_round_trip_and_replay_are_independent_from_physical_snapshot(
    tmp_path: Path,
) -> None:
    physical = _physical_snapshot()
    event = _arrival_event()
    restored_event = EventRecord.from_dict(event.to_dict())

    independently_mutated = copy.deepcopy(physical)
    independently_mutated.trucks["T-001"].arrival_time = event.payload["arrival_time"]
    independently_mutated.trucks["T-001"].cargo_type = event.payload["cargo_type"]
    independently_mutated.trucks["T-001"].priority = event.payload["priority"]
    independently_mutated.trucks["T-001"].document_ok = event.payload["document_ok"]
    independently_mutated.trucks["T-001"].stage = event.payload["stage"]
    independently_mutated.trucks["T-001"].arrived = True
    independently_mutated.trucks["T-001"].stage_entry_time = event.time
    independently_mutated.clock = event.time

    digital = DigitalModel.from_snapshot(physical)
    digital.apply(restored_event)
    expected = copy.deepcopy(independently_mutated)
    assert digital.snapshot() == expected

    independently_mutated.trucks["T-001"].cargo_type = "wheat"
    independently_mutated.trucks["T-001"].priority = 99
    assert digital.snapshot() == expected

    returned = digital.snapshot()
    returned.trucks["T-001"].cargo_type = "mutated-after-snapshot"
    assert digital.snapshot() == expected

    path = tmp_path / "events.jsonl"
    write_jsonl(path, [restored_event])
    replayed = replay_events(physical=_physical_snapshot(), events=read_jsonl(path))
    assert replayed == expected


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"time": float("nan"), "sequence": 1, "kind": "RUN_STARTED", "payload": {}},
            "finite",
        ),
        (
            {"time": 0.0, "sequence": 0, "kind": "RUN_STARTED", "payload": {}},
            "positive",
        ),
        (
            {"time": 0.0, "sequence": 1, "kind": "UNKNOWN", "payload": {}},
            "kind",
        ),
        (
            {"time": 1.0, "sequence": 1, "kind": "TRUCK_ARRIVED", "payload": {}},
            "payload",
        ),
    ],
)
def test_event_record_rejects_invalid_records(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        EventRecord(**kwargs)


def test_model_rejects_sequence_regression_and_impossible_transition() -> None:
    model = DigitalModel.empty()
    model.apply(EventRecord(time=0.0, sequence=1, kind="RUN_STARTED", payload={}))
    with pytest.raises(ValueError, match="sequence"):
        model.apply(EventRecord(time=0.1, sequence=1, kind="END_OF_DAY", payload={}))
    with pytest.raises(ValueError, match="transition"):
        model.apply(
            EventRecord(
                time=0.2,
                sequence=2,
                kind="DOCUMENT_RELEASED",
                payload={"truck_id": "missing"},
            )
        )
    model.apply(EventRecord(time=0.2, sequence=2, kind="END_OF_DAY", payload={}))
    with pytest.raises(ValueError, match="transition"):
        model.apply(
            EventRecord(
                time=0.3,
                sequence=3,
                kind="TRUCK_ARRIVED",
                payload={
                    "truck_id": "T-002",
                    "arrival_time": 0.3,
                    "cargo_type": "soy",
                    "priority": 0,
                    "document_ok": False,
                    "stage": 0,
                },
            )
        )


def test_public_empty_and_canonical_snapshot_contract() -> None:
    snapshot = YardSnapshot.empty()
    assert snapshot.canonical_dict() == {
        "clock": 0.0,
        "decisions": [],
        "ended": False,
        "resources": {},
        "running": False,
        "scenario_id": None,
        "trucks": {},
    }
    assert DigitalModel.empty().snapshot() == snapshot


def test_truck_arrival_projects_complete_payload() -> None:
    event = _arrival_event()
    result = replay_events([event])
    truck = result.trucks["T-001"]
    assert (
        truck.truck_id,
        truck.arrival_time,
        truck.cargo_type,
        truck.priority,
        truck.document_ok,
        truck.stage,
    ) == ("T-001", 1.5, "soy", 1, True, 0)


def test_existing_truck_arrival_validates_priority_before_assignment() -> None:
    physical = YardSnapshot(
        trucks={"T-001": Truck("T-001", 0.0, "soy", 7, False, 0)},
    )
    model = DigitalModel.from_snapshot(physical)
    payload = _arrival_event().to_dict()["payload"]
    payload["priority"] = -1
    with pytest.raises(ValueError, match="priority"):
        model.apply(
            EventRecord(time=1.5, sequence=1, kind="TRUCK_ARRIVED", payload=payload)
        )
    assert model.snapshot().trucks["T-001"].priority == 7


def test_sequences_must_start_at_one_and_be_contiguous() -> None:
    model = DigitalModel.empty()
    with pytest.raises(ValueError, match="sequence"):
        model.apply(EventRecord(time=0.0, sequence=2, kind="RUN_STARTED", payload={}))
    model.apply(EventRecord(time=0.0, sequence=1, kind="RUN_STARTED", payload={}))
    with pytest.raises(ValueError, match="gap|contiguous"):
        model.apply(EventRecord(time=0.1, sequence=3, kind="END_OF_DAY", payload={}))
    assert model.last_sequence == 1


def test_service_started_before_arrival_and_document_release_is_impossible() -> None:
    model = DigitalModel(
        YardSnapshot(
            trucks={"T-001": Truck("T-001", 0.0, "soy", 0, False, 0)},
            resources={"scale-1": Resource("scale-1", "scale")},
        )
    )
    with pytest.raises(ValueError, match="arriv|document"):
        model.apply(
            EventRecord(
                time=1.0,
                sequence=1,
                kind="SERVICE_STARTED",
                payload={
                    "truck_id": "T-001",
                    "resource_id": "scale-1",
                    "operation": "scale_in",
                },
            )
        )


@pytest.mark.parametrize("kind", ("SERVICE_STARTED", "SERVICE_COMPLETED"))
def test_service_events_require_operation_at_event_boundary(kind: str) -> None:
    with pytest.raises(ValueError, match="missing required fields: operation"):
        EventRecord(
            time=1.0,
            sequence=1,
            kind=kind,
            payload={"truck_id": "T-001", "resource_id": "scale-1"},
        )


def test_event_payload_is_recursively_immutable_and_to_dict_is_detached() -> None:
    payload = {"decision": {"operator": {"name": "Ana"}}}
    event = EventRecord(time=1.0, sequence=1, kind="DECISION_RECORDED", payload=payload)
    expected = event.to_dict()
    payload["decision"]["operator"]["name"] = "Bia"
    assert event.to_dict() == expected

    with pytest.raises(TypeError):
        event.payload["decision"]["operator"]["name"] = "Caio"

    detached = event.to_dict()
    detached["payload"]["decision"]["operator"]["name"] = "Duda"
    assert event.to_dict() == expected
    model = DigitalModel.empty()
    model.apply(event)
    assert model.snapshot().decisions[0]["payload"]["decision"]["operator"]["name"] == "Ana"


def test_jsonl_is_one_canonical_event_per_line(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    event = _arrival_event()
    write_jsonl(path, [event])
    assert path.read_text(encoding="utf-8").splitlines() == [
        json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ]


def test_model_replays_ordered_four_operation_service_cycles() -> None:
    """The DES emits four service phases for each truck."""

    snapshot = YardSnapshot(
        trucks={"T-001": Truck("T-001", 0.0, "soy", 0, False, 0)},
        resources={
            "gate-1": Resource("gate-1", "gate"),
            "scale-1": Resource("scale-1", "scale"),
            "hopper-1": Resource("hopper-1", "hopper"),
        },
    )
    events = [
        EventRecord(time=0.0, sequence=1, kind="RUN_STARTED", payload={}),
        EventRecord(
            time=0.1,
            sequence=2,
            kind="TRUCK_ARRIVED",
            payload={
                "truck_id": "T-001",
                "arrival_time": 0.1,
                "cargo_type": "soy",
                "priority": 0,
                "document_ok": True,
                "stage": 1,
            },
        ),
    ]
    sequence = 3
    time = 0.2
    for operation, resource_id in (
        ("gate", "gate-1"),
        ("scale_in", "scale-1"),
        ("unload", "hopper-1"),
        ("scale_out", "scale-1"),
    ):
        recommendation = {
            "selected": {
                "truck_id": "T-001",
                "operation": operation,
                "resource_id": resource_id,
            }
        }
        events.append(
            EventRecord(
                time=time,
                sequence=sequence,
                kind="DECISION_RECORDED",
                payload={"decision": recommendation},
            )
        )
        sequence += 1
        events.append(
            EventRecord(
                time=time,
                sequence=sequence,
                kind="OPERATOR_DECISION",
                payload={
                    "decision": "accept",
                    "recommendation": recommendation,
                },
            )
        )
        sequence += 1
        events.append(
            EventRecord(
                time=time,
                sequence=sequence,
                kind="SERVICE_STARTED",
                payload={
                    "truck_id": "T-001",
                    "resource_id": resource_id,
                    "operation": operation,
                },
            )
        )
        sequence += 1
        time += 0.1
        events.append(
            EventRecord(
                time=time,
                sequence=sequence,
                kind="SERVICE_COMPLETED",
                payload={
                    "truck_id": "T-001",
                    "resource_id": resource_id,
                    "operation": operation,
                },
            )
        )
        sequence += 1
        time += 0.1
    events.append(EventRecord(time=time, sequence=sequence, kind="END_OF_DAY", payload={}))

    result = replay_events(events, physical=snapshot)

    assert result.trucks["T-001"].stage == 4
    assert result.resources["scale-1"].status == "available"


def _decision_chain_prefix(operation: str = "gate", resource_id: str = "gate-1") -> list[EventRecord]:
    return [
        EventRecord(time=0.0, sequence=1, kind="RUN_STARTED", payload={}),
        EventRecord(
            time=0.1,
            sequence=2,
            kind="TRUCK_ARRIVED",
            payload={
                "truck_id": "T-001",
                "arrival_time": 0.1,
                "cargo_type": "soy",
                "priority": 0,
                "document_ok": True,
                "stage": 1,
            },
        ),
        EventRecord(
            time=0.2,
            sequence=3,
            kind="DECISION_RECORDED",
            payload={
                "decision": {
                    "type": "Recommendation",
                    "selected": {
                        "truck_id": "T-001",
                        "operation": operation,
                        "resource_id": resource_id,
                    },
                }
            },
        ),
        EventRecord(
            time=0.2,
            sequence=4,
            kind="OPERATOR_DECISION",
            payload={
                "decision": "accept",
                "recommendation": {
                    "selected": {
                        "truck_id": "T-001",
                        "operation": operation,
                        "resource_id": resource_id,
                    }
                },
            },
        ),
    ]


def test_replay_requires_matching_accepted_decision_before_service() -> None:
    snapshot = YardSnapshot(
        trucks={"T-001": Truck("T-001", 0.0, "soy", 0, False, 0)},
        resources={"gate-1": Resource("gate-1", "gate")},
    )
    events = _decision_chain_prefix()
    events[3] = EventRecord(
        time=0.2,
        sequence=4,
        kind="OPERATOR_DECISION",
        payload={"decision": "reject", "recommendation": {}},
    )
    events.append(
        EventRecord(
            time=0.3,
            sequence=5,
            kind="SERVICE_STARTED",
            payload={
                "truck_id": "T-001",
                "resource_id": "gate-1",
                "operation": "gate",
            },
        )
    )

    with pytest.raises(ValueError, match="accept|operator decision"):
        replay_events(events, physical=snapshot)


def test_replay_rejects_unconsumed_decision_at_end_of_day() -> None:
    snapshot = YardSnapshot(
        trucks={"T-001": Truck("T-001", 0.0, "soy", 0, False, 0)},
        resources={"gate-1": Resource("gate-1", "gate")},
    )
    events = _decision_chain_prefix()
    events[-1] = EventRecord(
        time=0.2,
        sequence=4,
        kind="DECISION_RECORDED",
        payload={"decision": {"selected": {"truck_id": "T-001"}}},
    )
    events.append(EventRecord(time=0.3, sequence=5, kind="END_OF_DAY", payload={}))

    with pytest.raises(ValueError, match="unconsumed|decision chain"):
        replay_events(events, physical=snapshot)


def test_replay_requires_operation_compatible_resource_kind() -> None:
    snapshot = YardSnapshot(
        trucks={"T-001": Truck("T-001", 0.0, "soy", 0, False, 0)},
        resources={"gate-1": Resource("gate-1", "gate"), "scale-1": Resource("scale-1", "scale")},
    )
    events = _decision_chain_prefix(operation="unload", resource_id="scale-1")
    events.append(
        EventRecord(
            time=0.3,
            sequence=5,
            kind="SERVICE_STARTED",
            payload={
                "truck_id": "T-001",
                "resource_id": "scale-1",
                "operation": "unload",
            },
        )
    )

    with pytest.raises(ValueError, match="resource kind|operation"):
        replay_events(events, physical=snapshot)


def test_replay_allows_active_service_at_hard_cutoff_and_preserves_it() -> None:
    snapshot = YardSnapshot(
        trucks={"T-001": Truck("T-001", 0.0, "soy", 0, False, 0)},
        resources={"gate-1": Resource("gate-1", "gate")},
    )
    events = _decision_chain_prefix()
    events.append(
        EventRecord(
            time=0.3,
            sequence=5,
            kind="SERVICE_STARTED",
            payload={
                "truck_id": "T-001",
                "resource_id": "gate-1",
                "operation": "gate",
            },
        )
    )
    events.append(EventRecord(time=0.4, sequence=6, kind="END_OF_DAY", payload={}))

    result = replay_events(events, physical=snapshot)

    assert result.trucks["T-001"].stage == 3
    assert result.trucks["T-001"].resource_id == "gate-1"
    assert result.resources["gate-1"].status == "busy"


def test_resource_status_outside_closed_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="status"):
        Resource("scale-1", "scale", status="mystery")


def test_digital_model_rejects_incompatible_cargo_on_service_start() -> None:
    """The replay boundary enforces cargo/resource compatibility itself."""

    snapshot = YardSnapshot(
        trucks={"T-001": Truck("T-001", 0.0, "corn", 0, False, 0)},
        resources={
            "hopper-2": Resource(
                "hopper-2",
                "hopper",
                allowed_cargo_types=("soy",),
            )
        },
    )
    events = [
        EventRecord(time=0.0, sequence=1, kind="RUN_STARTED", payload={}),
        EventRecord(
            time=0.1,
            sequence=2,
            kind="TRUCK_ARRIVED",
            payload={
                "truck_id": "T-001",
                "arrival_time": 0.1,
                "cargo_type": "corn",
                "priority": 0,
                "document_ok": True,
                "stage": 1,
            },
        ),
        EventRecord(
            time=0.2,
            sequence=3,
            kind="DECISION_RECORDED",
            payload={"decision": {"selected": {"truck_id": "T-001", "operation": "unload", "resource_id": "hopper-2"}}},
        ),
        EventRecord(
            time=0.2,
            sequence=4,
            kind="OPERATOR_DECISION",
            payload={"decision": "accept", "recommendation": {"selected": {"truck_id": "T-001", "operation": "unload", "resource_id": "hopper-2"}}},
        ),
        EventRecord(
            time=0.3,
            sequence=5,
            kind="SERVICE_STARTED",
            payload={
                "truck_id": "T-001",
                "resource_id": "hopper-2",
                "operation": "unload",
                "cargo_type": "corn",
            },
        ),
    ]

    with pytest.raises(ValueError, match="cargo|compatib"):
        replay_events(events, physical=snapshot)


def test_dispatch_blocked_is_evidence_without_mutating_digital_state() -> None:
    model = DigitalModel.empty()
    model.apply(EventRecord(time=0.0, sequence=1, kind="RUN_STARTED", payload={}))
    before = model.snapshot().canonical_dict()
    model.apply(
        EventRecord(
            time=1.0,
            sequence=2,
            kind="DISPATCH_BLOCKED",
            payload={
                "resource_id": "gate-1",
                "operation": "gate",
                "candidate_ids": ["T-001"],
                "reasons": [{"truck_id": "T-001", "reason": "document blocked"}],
            },
        )
    )
    after = model.snapshot().canonical_dict()
    assert after["clock"] == 1.0
    after["clock"] = before["clock"]
    assert after == before
