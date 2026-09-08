"""Event-applied digital projection of the physical yard."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Mapping

from .config import EVENT_RANKS, EVENT_SEMANTICS_VERSION, ScenarioConfig
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


def _physical_number(value: object, name: str, *, positive: bool = False) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (positive and value == 0)):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'non-negative'}")
    return float(value)


@dataclass
class _PhysicalReplay:
    """Independent physical obligations, copied with each atomic event application."""

    strict: bool = False
    buffer_capacity: int | None = None
    pool_counts: dict[str, int] | None = None
    service_starts: dict[str, float] = field(default_factory=dict)
    service_deadlines: dict[str, float] = field(default_factory=dict)
    completed_services: dict[str, tuple[float, float]] = field(default_factory=dict)
    disruptions: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    seen_disruptions: set[tuple[str, str]] = field(default_factory=set)
    required_failure: dict[str, Any] | None = None
    order_time: float | None = None
    order_key: tuple[int, str, str] | None = None
    dispatch_started: bool = False

    @staticmethod
    def _occupancy(state: YardSnapshot) -> tuple[dict[str, int], int, int]:
        queues = {operation: 0 for operation in ("scale_in", "unload", "scale_out")}
        inbound = outbound = 0
        for truck in state.trucks.values():
            if not truck.arrived:
                continue
            operation = truck.next_operation
            active = truck.stage == TRUCK_STAGE_SERVICE_STARTED
            if operation in queues and not active:
                queues[operation] += 1
            if operation in {"scale_in", "unload"}:
                inbound += 1
            if (operation == "unload" and active) or (operation == "scale_out" and not active):
                outbound += 1
        return queues, inbound, outbound

    def _order(self, event: EventRecord) -> None:
        if not self.strict:
            return
        if event.time != self.order_time:
            self.order_time, self.order_key, self.dispatch_started = event.time, None, False
        kind, payload = event.kind, event.payload
        external = {
            "SERVICE_COMPLETED": "service_completion", "DOCUMENT_RELEASED": "document_release",
            "PRIORITY_CHANGED": "priority_change", "TRUCK_ARRIVED": "arrival",
        }.get(kind)
        if kind == "DISRUPTION_RECORDED":
            external = "rain_start" if payload["cause"] == "rain" else "resource_failure"
        elif kind == "RESOURCE_RECOVERED":
            external = "rain_end" if payload["cause"] == "rain" else "resource_recovery"
        if external is not None:
            key = (EVENT_RANKS[external], payload.get("resource_id", ""), payload.get("truck_id", ""))
            if self.dispatch_started or (self.order_key is not None and key < self.order_key):
                raise ValueError(f"public event rank/order violation: {kind} at {event.time}")
            self.order_key = key
        elif kind in {"DECISION_RECORDED", "OPERATOR_DECISION", "SERVICE_STARTED", "DISPATCH_BLOCKED"}:
            self.dispatch_started = True
        # RESOURCE_FAILED is the immediate consequence of DISRUPTION_RECORDED,
        # not another external event. Decision/operator/service chains likewise
        # stay together after the complete external batch.

    def before(self, state: YardSnapshot, event: EventRecord) -> None:
        kind, payload = event.kind, event.to_dict()["payload"]
        if kind == "RUN_STARTED":
            contract = {"event_semantics_version", "event_ranks", "execution_controls"}
            if contract.intersection(payload):
                if not contract.issubset(payload):
                    raise ValueError("incomplete physical event semantics contract")
                if payload["event_semantics_version"] != EVENT_SEMANTICS_VERSION:
                    raise ValueError("unsupported physical event semantics version")
                ranks = payload["event_ranks"]
                if (not isinstance(ranks, Mapping) or dict(ranks) != dict(EVENT_RANKS)
                        or any(type(value) is not int for value in ranks.values())):
                    raise ValueError("event ranks disagree with physical semantics version")
                controls = payload["execution_controls"]
                if not isinstance(controls, Mapping):
                    raise ValueError("execution controls must be a mapping")
                capacity = controls.get("buffer_capacity")
                if type(capacity) is not int or capacity <= 0:
                    raise ValueError("buffer capacity must be a positive integer")
                self.buffer_capacity, self.strict = capacity, True
                resources = payload.get("resources")
                if resources is not None and resources != state.canonical_dict()["resources"]:
                    raise ValueError("RUN_STARTED resource pool differs from initial snapshot")
        resource_id = payload.get("resource_id")
        resource = state.resources.get(resource_id)
        if kind == "RESOURCE_FAILED" and resource is not None and resource.status == "busy":
            raise ValueError("resource failure cannot preempt an active service")
        if self.required_failure is not None:
            if (kind != "RESOURCE_FAILED" or event.time != self.required_failure["effective_failure_start"]
                    or any(payload.get(key) != value for key, value in self.required_failure.items())):
                raise ValueError("recorded disruption requires its matching resource failure")
        for truck_id, deadline in self.service_deadlines.items():
            if event.time > deadline:
                raise ValueError(f"missing service completion at deadline {deadline}: {truck_id}")
        for identifier, intervals in self.disruptions.items():
            deadline = max(item["recovery_time"] for item in intervals.values())
            if state.resources[identifier].status == "failed" and event.time > deadline:
                raise ValueError(f"missing resource recovery at {deadline}: {identifier}")

        if kind == "DISRUPTION_RECORDED":
            if resource is None:
                raise ValueError("disruption references an unknown resource")
            if resource.status == "busy":
                raise ValueError("effective disruption cannot preempt an active service")
            for key in ("latent_id", "cause"):
                if not isinstance(payload.get(key), str) or not payload[key].strip():
                    raise ValueError(f"disruption {key} must be a non-empty string")
            latent_id = payload["latent_id"]
            identity = (resource_id, latent_id)
            if identity in self.seen_disruptions:
                raise ValueError("duplicate recorded disruption")
            scheduled = _physical_number(payload.get("scheduled_failure_start"), "scheduled failure start")
            effective = _physical_number(payload.get("effective_failure_start"), "effective failure start")
            duration = _physical_number(payload.get("scheduled_failure_duration"), "disruption duration", positive=True)
            recovery = _physical_number(payload.get("recovery_time"), "recovery time")
            expired = payload.get("expired_before_effective_start")
            rain = payload["cause"] == "rain"
            expected_recovery = (scheduled if rain else effective) + duration
            if (scheduled > effective or effective != event.time
                    or not math.isclose(recovery, expected_recovery, rel_tol=0, abs_tol=1e-9)
                    or type(expired) is not bool or expired != (recovery <= effective)):
                raise ValueError("disruption interval or expiration evidence is incoherent")
            if effective > scheduled:
                interval = self.completed_services.get(resource_id)
                if interval is None or interval[1] != effective or not interval[0] < scheduled < interval[1]:
                    raise ValueError("deferred disruption must originate inside the completed service interval")
            self.seen_disruptions.add(identity)
            if not expired:
                self.disruptions.setdefault(resource_id, {})[latent_id] = payload
                if resource.status == "available":
                    self.required_failure = payload
        elif kind == "RESOURCE_FAILED":
            if self.required_failure is None:
                raise ValueError("resource failure has no active recorded disruption (or it expired)")
            duration = _physical_number(payload.get("duration_minutes"), "failure duration", positive=True)
            if duration != self.required_failure["recovery_time"] - event.time:
                raise ValueError("resource failure duration disagrees with recorded disruption")
            self.required_failure = None
        elif kind == "RESOURCE_RECOVERED":
            intervals = self.disruptions.get(resource_id, {})
            interval = intervals.get(payload.get("latent_id"))
            if (interval is None or interval["cause"] != payload.get("cause")
                    or interval["recovery_time"] != event.time
                    or any(item["recovery_time"] > event.time for item in intervals.values())):
                raise ValueError("resource recovery has unmatched or still active disruptions")
            if any(truck.resource_id == resource_id and truck.stage == TRUCK_STAGE_SERVICE_STARTED
                   for truck in state.trucks.values()):
                raise ValueError("resource recovery cannot release an active service")
            self.disruptions.pop(resource_id)
        elif kind == "SERVICE_STARTED":
            truck_id = payload["truck_id"]
            self.service_starts[truck_id] = event.time
            if self.strict or "duration_minutes" in payload:
                duration = _physical_number(payload.get("duration_minutes"), "service duration", positive=True)
                self.service_deadlines[truck_id] = _physical_number(event.time + duration, "service completion deadline")
            if any(truck.resource_id == resource_id and truck.stage == TRUCK_STAGE_SERVICE_STARTED
                   for truck in state.trucks.values()):
                raise ValueError("resource pool capacity exceeded: another service is active")
            if self.buffer_capacity is not None:
                _, inbound, outbound = self._occupancy(state)
                operation = payload["operation"]
                if ((operation == "gate" and inbound >= self.buffer_capacity)
                        or (operation == "scale_in" and inbound > self.buffer_capacity)
                        or (operation == "unload" and outbound >= self.buffer_capacity)):
                    raise ValueError(f"buffer reservation capacity blocks {operation}")
        elif kind == "SERVICE_COMPLETED":
            truck_id = payload["truck_id"]
            if truck_id in self.service_deadlines:
                if event.time != self.service_deadlines[truck_id]:
                    raise ValueError("service completion disagrees with effective duration")
                self.service_deadlines.pop(truck_id)
            elif self.strict:
                raise ValueError("service completion is missing its effective duration")
            started = self.service_starts.pop(truck_id, None)
            if started is None:
                raise ValueError("impossible transition: service completion has no observed start")
            self.completed_services[resource_id] = (started, event.time)
        elif kind == "END_OF_DAY":
            if any(deadline <= event.time for deadline in self.service_deadlines.values()):
                raise ValueError("service completion due before end of day is missing")
            if any(max(item["recovery_time"] for item in intervals.values()) <= event.time
                   for intervals in self.disruptions.values()):
                raise ValueError("resource recovery due before end of day is missing")
        self._order(event)

    def after(self, state: YardSnapshot, event: EventRecord) -> None:
        if event.kind == "RUN_STARTED" and self.strict and self.pool_counts is not None:
            for kind, expected in self.pool_counts.items():
                if sum(resource.kind == kind for resource in state.resources.values()) != expected:
                    raise ValueError(f"{kind} resource pool capacity disagrees with scenario")
        if self.buffer_capacity is not None:
            queues, inbound, outbound = self._occupancy(state)
            if max(*queues.values(), inbound, outbound) > self.buffer_capacity:
                raise ValueError("physical buffer occupancy or reservation exceeds capacity")


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
        self._operator_mode: str | None = None
        self._physics = _PhysicalReplay(pool_counts=None if scenario is None else {
            "gate": 1, "scale": scenario.scale_count, "hopper": scenario.hopper_count,
        })

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
        physics = copy.deepcopy(self._physics)
        physics.before(candidate, event)
        self._apply_to(
            candidate,
            event,
            active_operations=active_operations,
            next_operations=next_operations,
            pending_decisions=pending_decisions,
            operator_mode=self._operator_mode,
        )
        candidate.clock = event.time
        physics.after(candidate, event)
        self._state = candidate
        self._active_operations = active_operations
        self._next_operations = next_operations
        self._pending_decisions = pending_decisions
        self._physics = physics
        self._last_sequence = event.sequence
        if event.kind == "RUN_STARTED":
            self._operator_mode = event.payload.get("operator_mode")

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
        operator_mode: str | None = None,
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
            mode = payload.get("operator_mode")
            if mode is not None and mode not in {"synthetic_auto_accept", "synthetic_scripted"}:
                raise ValueError("RUN_STARTED operator_mode is not supported")
            if mode == "synthetic_scripted":
                instance_id = payload.get("instance_id")
                if not isinstance(instance_id, str) or not instance_id.startswith("validation-"):
                    raise ValueError("synthetic scripted replay requires a validation instance_id")
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

        if kind == "DISRUPTION_RECORDED":
            cls._require_resource(state, payload["resource_id"])
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
            # Compare detached JSON values: event freezing changes list fields
            # to tuples, while the recorded recommendation uses JSON lists.
            payload = event.to_dict()["payload"]
            decision_value = payload["decision"]
            scripted = operator_mode == "synthetic_scripted"
            if not scripted and (decision_value != "accept" or payload.get("operator_mode") == "synthetic_scripted"):
                raise ValueError(
                    "operator decision must be accept before service can start"
                )
            if scripted:
                if (payload.get("operator_mode") != "synthetic_scripted"
                        or payload.get("origin") != "simulated"
                        or type(payload.get("operator_payload_version")) is not int
                        or payload["operator_payload_version"] != 1):
                    raise ValueError("synthetic operator response requires its explicit mode, origin and payload version")
                if decision_value not in {"accept", "reject", "override"}:
                    raise ValueError("unknown synthetic operator response")
                if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
                    raise ValueError("synthetic operator response requires a reason")
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
            if scripted and recommendation != pending["recommendation"]:
                raise ValueError("synthetic response changed the recorded recommendation")
            if scripted and decision_value == "reject":
                if "selection" not in payload or payload["selection"] is not None:
                    raise ValueError("rejected recommendation must not contain a service selection")
                pending_decisions.pop(truck_id)
            else:
                effective_selection = selection
                if scripted:
                    actual = payload.get("selection")
                    effective_selection = cls._selection_from_recommendation({"selected": actual})
                    if effective_selection is None:
                        raise ValueError("accepted synthetic response requires a selection")
                    if decision_value == "accept" and actual != recommendation["selected"]:
                        raise ValueError("synthetic accept must preserve the recommended selection")
                    if decision_value == "override":
                        target = effective_selection["truck_id"]
                        if target == truck_id:
                            raise ValueError("synthetic override must select another admissible truck")
                        candidates = recommendation.get("candidate_order")
                        if not isinstance(candidates, (list, tuple)):
                            raise ValueError("synthetic override requires recorded admissible candidates")
                        offered = next((item for item in candidates
                                        if isinstance(item, Mapping) and item.get("truck_id") == target), None)
                        if offered is None or any(actual.get(key) != value for key, value in offered.items()):
                            raise ValueError("synthetic override is outside the recorded admissible candidates")
                        if any(offered.get(key) is not True for key in ("arrived", "document_ok", "eligible")):
                            raise ValueError("synthetic override target violates an admissibility constraint")
                        truck = cls._require_truck(state, target)
                        mandatory_ids = {
                            item["truck_id"] for item in candidates
                            if isinstance(item, Mapping) and item.get("truck_id") in state.trucks
                            and state.trucks[item["truck_id"]].priority == 2
                        }
                        if mandatory_ids and target not in mandatory_ids:
                            raise ValueError("synthetic override violates mandatory-priority admission")
                        resource = cls._require_resource(state, recommendation.get("resource_id"))
                        operation = effective_selection["operation"]
                        cls._validate_operation_resource_kind(operation, resource)
                        if (not truck.arrived or not truck.document_ok or target in active_operations
                                or truck.next_operation != operation or resource.status != "available"
                                or truck.cargo_type not in resource.allowed_cargo_types
                                or effective_selection["resource_id"] != resource.resource_id):
                            raise ValueError("synthetic override violates a hard constraint in the observed state")
                        if target in pending_decisions:
                            raise ValueError("synthetic override target already has a pending command")
                        pending_decisions.pop(truck_id)
                        truck_id = target
                pending_decisions[truck_id] = {
                    **pending, "selection": effective_selection, "accepted": True,
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
