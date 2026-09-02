"""Event-applied digital projection of the physical yard."""

from __future__ import annotations

import copy
import math
from typing import Any, Iterable, Mapping

from .config import ScenarioConfig
from .domain import (
    Resource,
    Truck,
    YardSnapshot,
    TRUCK_STAGE_ARRIVED,
    TRUCK_STAGE_DOCUMENT_RELEASED,
    TRUCK_STAGE_SERVICE_COMPLETED,
    TRUCK_STAGE_SERVICE_STARTED,
    TRUCK_STAGE_WAITING,
    VALID_RESOURCE_STATUSES,
    VALID_TRUCK_STAGES,
)
from .events import EventRecord


class DigitalModel:
    """Apply an ordered event stream to an isolated ``YardSnapshot``."""

    def __init__(
        self,
        snapshot: YardSnapshot | None = None,
        *,
        scenario: ScenarioConfig | None = None,
    ) -> None:
        if snapshot is not None and not isinstance(snapshot, YardSnapshot):
            raise TypeError("snapshot must be a YardSnapshot or None")
        if scenario is not None and not isinstance(scenario, ScenarioConfig):
            raise TypeError("scenario must be a ScenarioConfig or None")
        self._state = copy.deepcopy(snapshot) if snapshot is not None else YardSnapshot()
        if scenario is not None:
            if self._state.scenario_id is not None and self._state.scenario_id != scenario.scenario_id:
                raise ValueError("snapshot scenario_id does not match scenario")
            self._state.scenario_id = scenario.scenario_id
        for resource in self._state.resources.values():
            if resource.status not in VALID_RESOURCE_STATUSES:
                raise ValueError(
                    "resource status outside closed set: "
                    f"{resource.resource_id}={resource.status!r}"
                )
        self._last_sequence = 0
        # Operation-aware service cycles are transient replay bookkeeping. They
        # are intentionally kept outside YardSnapshot so the public snapshot
        # schema remains unchanged for callers of the compact Task 2 model.
        self._active_operations: dict[str, str] = {}
        self._next_operations: dict[str, str] = {}
        # A recommendation remains pending until an accepted operator
        # decision is consumed by the corresponding SERVICE_STARTED event.
        # This replay bookkeeping is deliberately transient and is not part
        # of the public YardSnapshot schema.
        self._pending_decisions: dict[str, dict[str, Any]] = {}

    @classmethod
    def empty(cls, *, scenario: ScenarioConfig | None = None) -> "DigitalModel":
        """Create an empty projection with no applied events."""

        return cls(YardSnapshot.empty(), scenario=scenario)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: YardSnapshot,
        *,
        scenario: ScenarioConfig | None = None,
    ) -> "DigitalModel":
        return cls(snapshot, scenario=scenario)

    def snapshot(self) -> YardSnapshot:
        """Return a detached copy that cannot mutate the projection."""

        return copy.deepcopy(self._state)

    @property
    def last_sequence(self) -> int:
        return self._last_sequence

    def apply(self, event: EventRecord) -> None:
        """Apply one event atomically, rejecting ordering and state violations."""

        if not isinstance(event, EventRecord):
            raise TypeError("event must be an EventRecord")
        expected_sequence = self._last_sequence + 1
        if event.sequence != expected_sequence:
            raise ValueError(
                "event sequence gap: expected contiguous sequence "
                f"expected {expected_sequence}, received {event.sequence}"
            )
        if event.time < self._state.clock:
            raise ValueError("event time regresses the snapshot clock")

        candidate = copy.deepcopy(self._state)
        active_operations = dict(self._active_operations)
        next_operations = dict(self._next_operations)
        pending_decisions = copy.deepcopy(self._pending_decisions)
        self._apply_to(
            candidate,
            event,
            active_operations=active_operations,
            next_operations=next_operations,
            pending_decisions=pending_decisions,
        )
        candidate.clock = event.time
        self._state = candidate
        self._active_operations = active_operations
        self._next_operations = next_operations
        self._pending_decisions = pending_decisions
        self._last_sequence = event.sequence

    @staticmethod
    def _require_truck(state: YardSnapshot, truck_id: object) -> Truck:
        if not isinstance(truck_id, str) or truck_id not in state.trucks:
            raise ValueError(f"impossible transition: unknown truck {truck_id!r}")
        return state.trucks[truck_id]

    @staticmethod
    def _require_resource(state: YardSnapshot, resource_id: object) -> Resource:
        if not isinstance(resource_id, str) or resource_id not in state.resources:
            raise ValueError(f"impossible transition: unknown resource {resource_id!r}")
        resource = state.resources[resource_id]
        # Resource.status is mutable at the domain layer; validate it again at
        # every event boundary so an injected unknown value cannot be treated
        # as available by a transition.
        if resource.status not in VALID_RESOURCE_STATUSES:
            raise ValueError(
                "resource status outside closed set: "
                f"{resource.resource_id}={resource.status!r}"
            )
        return resource

    @staticmethod
    def _selection_from_recommendation(value: object) -> dict[str, Any] | None:
        """Extract the fields that identify a recommendation's selection.

        Decision records from the earlier Task 2 boundary may carry arbitrary
        evidence without a ``selected`` field.  Such records are retained as
        evidence but do not form a command chain.  Once ``selected`` is
        present, however, its truck identifier is mandatory so the chain can
        be validated fail-closed.
        """

        if not isinstance(value, Mapping):
            raise ValueError("recommendation must be a mapping")
        selected = value.get("selected")
        if selected is None:
            return None
        if not isinstance(selected, Mapping):
            raise ValueError("recommendation selected value must be a mapping")
        truck_id = selected.get("truck_id")
        if not isinstance(truck_id, str) or not truck_id:
            raise ValueError("recommendation selected truck_id must be a non-empty string")
        operation = selected.get("operation")
        if operation is not None and (
            not isinstance(operation, str)
            or operation not in {"gate", "scale_in", "unload", "scale_out"}
        ):
            raise ValueError("recommendation selected operation is invalid")
        resource_id = selected.get("resource_id")
        if resource_id is not None and (
            not isinstance(resource_id, str) or not resource_id
        ):
            raise ValueError("recommendation selected resource_id must be a non-empty string")
        return {
            "truck_id": truck_id,
            "operation": operation,
            "resource_id": resource_id,
        }

    @staticmethod
    def _validate_operation_resource_kind(operation: object, resource: Resource) -> None:
        if operation is None:
            return
        expected_kinds = {
            "gate": "gate",
            "scale_in": "scale",
            "unload": "hopper",
            "scale_out": "scale",
        }
        if operation not in expected_kinds:
            raise ValueError("operation must be one of the four service operations")
        expected_kind = expected_kinds[operation]
        if resource.kind != expected_kind:
            raise ValueError(
                "resource kind is incompatible with operation: "
                f"{operation!r} requires {expected_kind!r}, got {resource.kind!r}"
            )

    @classmethod
    def _apply_to(
        cls,
        state: YardSnapshot,
        event: EventRecord,
        *,
        active_operations: dict[str, str] | None = None,
        next_operations: dict[str, str] | None = None,
        pending_decisions: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        if active_operations is None:
            active_operations = {}
        if next_operations is None:
            next_operations = {}
        if pending_decisions is None:
            pending_decisions = {}
        kind = event.kind
        payload = event.payload

        if state.ended and kind != "END_OF_DAY":
            raise ValueError("impossible transition: day already ended")

        if kind == "RUN_STARTED":
            if state.running or state.ended:
                raise ValueError("impossible transition: run already started or ended")
            state.running = True
            scenario_id = payload.get("scenario_id")
            if scenario_id is not None:
                if not isinstance(scenario_id, str) or not scenario_id:
                    raise ValueError("scenario_id must be a non-empty string")
                if state.scenario_id is not None and state.scenario_id != scenario_id:
                    raise ValueError("impossible transition: scenario_id changed")
                state.scenario_id = scenario_id
            resource_payload = payload.get("resources")
            if resource_payload is not None:
                if not isinstance(resource_payload, Mapping):
                    raise ValueError("RUN_STARTED resources must be a mapping")
                projected_resources: dict[str, Resource] = {}
                for resource_id, raw_resource in resource_payload.items():
                    if not isinstance(resource_id, str) or not resource_id:
                        raise ValueError("RUN_STARTED resource identifiers must be non-empty strings")
                    resource = raw_resource if isinstance(raw_resource, Resource) else Resource.from_dict(raw_resource)
                    if resource.resource_id != resource_id:
                        raise ValueError("RUN_STARTED resource key must match resource_id")
                    projected_resources[resource_id] = copy.deepcopy(resource)
                state.resources = projected_resources
            return

        if kind == "TRUCK_ARRIVED":
            truck_id = payload["truck_id"]
            if not isinstance(truck_id, str) or not truck_id:
                raise ValueError("truck_id must be a non-empty string")
            arrival_time = payload["arrival_time"]
            if (
                isinstance(arrival_time, bool)
                or not isinstance(arrival_time, (int, float))
                or not math.isfinite(float(arrival_time))
                or float(arrival_time) < 0
            ):
                raise ValueError("arrival_time must be finite and non-negative")
            cargo_type = payload["cargo_type"]
            if not isinstance(cargo_type, str) or not cargo_type:
                raise ValueError("cargo_type must be a non-empty string")
            # Validate before looking up or mutating an existing truck.  This
            # keeps an invalid arrival from partially replacing its state.
            priority = payload["priority"]
            if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:
                raise ValueError("priority must be a non-negative integer")
            document_ok = payload["document_ok"]
            if not isinstance(document_ok, bool):
                raise ValueError("document_ok must be bool")
            stage = payload["stage"]
            if isinstance(stage, bool) or not isinstance(stage, int) or stage not in VALID_TRUCK_STAGES:
                raise ValueError("stage is outside the closed truck-state set")
            truck = state.trucks.get(truck_id)
            if truck is None:
                state.trucks[truck_id] = Truck(
                    truck_id=truck_id,
                    arrival_time=float(arrival_time),
                    cargo_type=cargo_type,
                    priority=priority,
                    document_ok=document_ok,
                    stage=stage,
                    arrived=True,
                    stage_entry_time=event.time,
                    next_operation="gate",
                )
            else:
                if truck.arrived or truck.stage != TRUCK_STAGE_WAITING:
                    raise ValueError("impossible transition: truck has already arrived")
                truck.arrival_time = float(arrival_time)
                truck.cargo_type = cargo_type
                truck.priority = priority
                truck.document_ok = document_ok
                truck.stage = stage
                truck.arrived = True
                truck.next_operation = "gate"
            state.trucks[truck_id].stage_entry_time = event.time
            return

        if kind == "DOCUMENT_RELEASED":
            truck = cls._require_truck(state, payload["truck_id"])
            if not truck.arrived:
                raise ValueError("impossible transition: truck has not arrived")
            if truck.document_ok or truck.stage in {
                TRUCK_STAGE_SERVICE_STARTED,
                TRUCK_STAGE_SERVICE_COMPLETED,
            }:
                raise ValueError("impossible transition: document already released or truck closed")
            truck.document_ok = True
            truck.stage = TRUCK_STAGE_DOCUMENT_RELEASED
            truck.stage_entry_time = event.time
            return

        if kind == "PRIORITY_CHANGED":
            truck = cls._require_truck(state, payload["truck_id"])
            priority = payload["priority"]
            if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:
                raise ValueError("priority must be a non-negative integer")
            if truck.stage == TRUCK_STAGE_SERVICE_COMPLETED:
                raise ValueError("impossible transition: departed truck cannot change priority")
            truck.priority = priority
            return

        if kind == "RESOURCE_FAILED":
            resource = cls._require_resource(state, payload["resource_id"])
            if resource.status == "failed":
                raise ValueError("impossible transition: resource already failed")
            resource.status = "failed"
            return

        if kind == "RESOURCE_RECOVERED":
            resource = cls._require_resource(state, payload["resource_id"])
            if resource.status != "failed":
                raise ValueError("impossible transition: resource is not failed")
            resource.status = "available"
            return

        if kind == "SERVICE_STARTED":
            truck = cls._require_truck(state, payload["truck_id"])
            resource = cls._require_resource(state, payload["resource_id"])
            if not truck.arrived:
                raise ValueError("impossible transition: truck has not arrived")
            if not truck.document_ok:
                raise ValueError("impossible transition: document is not released")
            if resource.status != "available":
                raise ValueError("impossible transition: resource is not available")
            cargo_type = payload.get("cargo_type", truck.cargo_type)
            if not isinstance(cargo_type, str) or not cargo_type:
                raise ValueError("cargo_type must be a non-empty string")
            if cargo_type != truck.cargo_type:
                raise ValueError("service start cargo_type does not match truck")
            if cargo_type not in resource.allowed_cargo_types:
                raise ValueError(
                    "resource compatibility violation: "
                    f"{resource.resource_id} does not accept cargo {cargo_type!r}"
                )
            allowed_cargo_types = payload.get("allowed_cargo_types")
            if allowed_cargo_types is not None:
                if tuple(allowed_cargo_types) != tuple(resource.allowed_cargo_types):
                    raise ValueError("service start allowed_cargo_types do not match resource")
            operation = payload["operation"]
            if not isinstance(operation, str) or operation not in {
                "gate",
                "scale_in",
                "unload",
                "scale_out",
            }:
                raise ValueError("operation must be one of the four service operations")
            cls._validate_operation_resource_kind(operation, resource)
            if truck.truck_id in active_operations:
                raise ValueError("impossible transition: service is already active")
            expected_operation = next_operations.get(
                truck.truck_id, truck.next_operation
            )
            if operation != expected_operation:
                raise ValueError(
                    "impossible transition: service operation is out of order"
                )
            if truck.stage == TRUCK_STAGE_SERVICE_COMPLETED and truck.truck_id not in next_operations:
                raise ValueError("impossible transition: truck is not serviceable")
            if truck.stage not in {
                TRUCK_STAGE_WAITING,
                TRUCK_STAGE_ARRIVED,
                TRUCK_STAGE_DOCUMENT_RELEASED,
            }:
                raise ValueError("impossible transition: truck is not serviceable")
            active_operations[truck.truck_id] = operation

            pending = pending_decisions.get(truck.truck_id)
            if pending is None or not pending.get("accepted", False):
                raise ValueError(
                    "service start requires an accepted operator decision"
                )
            selected = pending["selection"]
            selected_operation = selected.get("operation")
            if selected_operation != operation:
                raise ValueError(
                    "service start does not match the accepted decision operation"
                )
            selected_resource_id = selected.get("resource_id")
            if selected_resource_id != resource.resource_id:
                raise ValueError(
                    "service start does not match the accepted decision resource"
                )
            pending_decisions.pop(truck.truck_id, None)
            truck.stage = TRUCK_STAGE_SERVICE_STARTED
            truck.resource_id = resource.resource_id
            resource.status = "busy"
            truck.stage_entry_time = event.time
            return

        if kind == "SERVICE_COMPLETED":
            truck = cls._require_truck(state, payload["truck_id"])
            resource = cls._require_resource(state, payload["resource_id"])
            if truck.stage != TRUCK_STAGE_SERVICE_STARTED or truck.resource_id != resource.resource_id:
                raise ValueError("impossible transition: service was not started on this resource")
            if resource.status != "busy":
                raise ValueError("impossible transition: resource is not busy")
            operation = payload["operation"]
            if not isinstance(operation, str) or operation not in {
                "gate",
                "scale_in",
                "unload",
                "scale_out",
            }:
                raise ValueError("operation must be one of the four service operations")
            cls._validate_operation_resource_kind(operation, resource)
            active_operation = active_operations.get(truck.truck_id)
            if active_operation != operation:
                raise ValueError("impossible transition: completed operation was not active")
            active_operations.pop(truck.truck_id, None)
            operation_order = ("gate", "scale_in", "unload", "scale_out")
            operation_index = operation_order.index(operation)
            if operation_index < len(operation_order) - 1:
                next_operations[truck.truck_id] = operation_order[operation_index + 1]
                truck.next_operation = operation_order[operation_index + 1]
                # The truck remains document-cleared and is serviceable for
                # the next physical phase.
                truck.stage = TRUCK_STAGE_DOCUMENT_RELEASED
                truck.stage_entry_time = event.time
            else:
                next_operations.pop(truck.truck_id, None)
                truck.next_operation = "done"
                truck.stage = TRUCK_STAGE_SERVICE_COMPLETED
                truck.stage_entry_time = event.time
            resource.status = "available"
            # resource_id denotes the resource currently in service.  Once the
            # service completes, no resource remains attached to the truck.
            truck.resource_id = None
            return

        if kind == "DISPATCH_BLOCKED":
            # Blocking is an auditable observation, not a state transition.
            # Keep the event in the trace while leaving trucks/resources and
            # pending decision chains untouched.
            return

        if kind == "DECISION_RECORDED":
            # ``EventRecord.payload`` is recursively frozen; use its detached
            # representation for transient bookkeeping as well as public
            # evidence.
            decision = event.to_dict()["payload"]["decision"]
            selection = cls._selection_from_recommendation(decision)
            if selection is not None:
                truck_id = selection["truck_id"]
                if truck_id in pending_decisions:
                    raise ValueError(
                        "impossible transition: decision chain already pending "
                        f"for truck {truck_id}"
                    )
                pending_decisions[truck_id] = {
                    "selection": selection,
                    "recommendation": copy.deepcopy(decision),
                    "accepted": False,
                }
            state.decisions.append(
                {
                    "kind": kind,
                    "time": event.time,
                    "sequence": event.sequence,
                    "payload": event.to_dict()["payload"],
                }
            )
            return

        if kind == "OPERATOR_DECISION":
            decision_value = payload["decision"]
            if decision_value != "accept":
                raise ValueError(
                    "operator decision must be accept before service can start"
                )
            recommendation = payload.get("recommendation")
            selection = cls._selection_from_recommendation(recommendation)
            if selection is None:
                raise ValueError("operator decision requires a selected recommendation")
            truck_id = selection["truck_id"]
            pending = pending_decisions.get(truck_id)
            if pending is None:
                raise ValueError(
                    "operator decision has no matching recorded decision"
                )
            if pending["selection"] != selection:
                raise ValueError(
                    "operator decision does not match the recorded recommendation"
                )
            pending_decisions[truck_id] = {
                **pending,
                "accepted": True,
            }
            state.decisions.append(
                {
                    "kind": kind,
                    "time": event.time,
                    "sequence": event.sequence,
                    "payload": event.to_dict()["payload"],
                }
            )
            return

        if kind == "END_OF_DAY":
            if state.ended:
                raise ValueError("impossible transition: day already ended")
            if pending_decisions:
                pending_ids = ", ".join(sorted(pending_decisions))
                raise ValueError(
                    "unconsumed decision chain at end of day: "
                    f"{pending_ids}"
                )
            state.running = False
            state.ended = True
            return

        # EventRecord validates this branch away.  Keeping the explicit guard
        # makes this function fail closed if a future caller bypasses that type.
        raise ValueError(f"unknown event kind: {kind!r}")


def replay_events(
    events: Iterable[EventRecord],
    *,
    physical: YardSnapshot | None = None,
    scenario: ScenarioConfig | None = None,
) -> YardSnapshot:
    """Replay ``events`` from an optional detached physical snapshot."""

    model = DigitalModel.empty(scenario=scenario) if physical is None else DigitalModel.from_snapshot(
        physical, scenario=scenario
    )
    for event in events:
        model.apply(event)
    return model.snapshot()
