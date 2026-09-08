"""Deterministic discrete-event emulator for the PequiFlux yard.

The implementation is deliberately small, but it follows the frozen protocol:
conditional NHPP arrivals, explicit document releases, triangular service
times, public disruption events, a hard 720-minute horizon, and one physical
dispatch pool for the two weighing operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import heapq
import math
from types import MappingProxyType
from typing import Any, Mapping

from .config import (
    ScenarioConfig, EVENT_RANKS, EVENT_SEMANTICS_VERSION, CANONICAL_CONFIRMATORY_FIELDS,
)
from .dataset import derive_controlled_projection
from .digital_model import DigitalModel, replay_events
from .dispatch import (
    Candidate,
    DispatchBlocked,
    DispatchContext,
    DispatchPolicy,
    NoFeasibleCandidate,
    Recommendation,
    recommend,
)
from .domain import (
    Resource,
    FrozenInstance,
    ExecutionControls,
    EventLatentLedger,
    Truck,
    YardSnapshot,
    TRUCK_STAGE_ARRIVED,
    TRUCK_STAGE_DOCUMENT_RELEASED,
    TRUCK_STAGE_SERVICE_COMPLETED,
    TRUCK_STAGE_SERVICE_STARTED,
    TRUCK_STAGE_WAITING,
)
from .events import EventRecord
from .operator import SyntheticOperatorResponse, SyntheticOperatorScript, SYNTHETIC_OPERATOR_PAYLOAD_VERSION
from .policies import make_policy


_OPERATIONS: tuple[str, ...] = ("gate", "scale_in", "unload", "scale_out")
HORIZON_MINUTES = float(CANONICAL_CONFIRMATORY_FIELDS["horizon_minutes"])
PRIORITY_THRESHOLDS = tuple(CANONICAL_CONFIRMATORY_FIELDS["priority_thresholds"])

VALID_REGIMES = frozenset({"nominal", "peak", "critical_failure", "priority_shift"})


def _validate_regime(regime: object) -> str:
    if not isinstance(regime, str) or regime not in VALID_REGIMES:
        raise ValueError(f"unknown regime: {regime!r}")
    return regime


def _round_metric(value: float) -> float:
    return round(float(value), 12)


@dataclass(frozen=True, slots=True)
class _Scheduled:
    time: float
    rank: int
    sequence: int
    kind: str
    truck_id: str | None = None
    operation: str | None = None
    resource_id: str | None = None
    cause: str | None = None
    recovery_at: float | None = None
    duration: float | None = None
    latent_id: str | None = None
    scheduled_start: float | None = None


@dataclass(slots=True)
class _TruckState:
    truck_id: str
    arrival_time: float
    priority: int
    cargo_type: str
    document_ok: bool
    stable_order: int
    arrived: bool = False
    operation: str = "gate"
    ready_time: float = 0.0
    active_resource: str | None = None
    active_operation: str | None = None
    service_started: list[tuple[str, float]] = field(default_factory=list)
    waiting_total: float = 0.0
    completed_at: float | None = None
    stage_entry_time: float = 0.0


@dataclass(frozen=True, slots=True)
class DayResult:
    """Canonical output identifying its frozen input, controls and policy."""

    scenario: ScenarioConfig
    seed: int
    policy_name: str
    instance_id: str
    instance_hash: str
    execution_instance_hash: str
    controls: ExecutionControls
    controlled_view_hash: str
    event_overlay_hash: str
    events: tuple[EventRecord, ...]
    metrics: Mapping[str, float | int]
    hard_constraint_violations: int
    max_scale_occupancy: int
    initial_snapshot: YardSnapshot
    final_snapshot: YardSnapshot
    physical_snapshot: YardSnapshot | None = None
    digital_snapshot: YardSnapshot | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, ScenarioConfig):
            raise TypeError("scenario must be a ScenarioConfig")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not isinstance(self.policy_name, str) or not self.policy_name:
            raise ValueError("policy_name must be a non-empty string")
        if not isinstance(self.instance_id, str) or not self.instance_id:
            raise ValueError("instance_id must be a non-empty string")
        if not isinstance(self.controls, ExecutionControls):
            raise TypeError("controls must be ExecutionControls")
        for name in ("instance_hash", "execution_instance_hash", "controlled_view_hash", "event_overlay_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        events = tuple(self.events)
        if any(not isinstance(event, EventRecord) for event in events):
            raise TypeError("events must contain EventRecord values")
        object.__setattr__(self, "events", events)
        if not isinstance(self.metrics, Mapping):
            raise TypeError("metrics must be a mapping")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
        if isinstance(self.hard_constraint_violations, bool) or not isinstance(
            self.hard_constraint_violations, int
        ):
            raise TypeError("hard_constraint_violations must be an integer")
        if self.hard_constraint_violations < 0:
            raise ValueError("hard_constraint_violations must be non-negative")
        if isinstance(self.max_scale_occupancy, bool) or not isinstance(
            self.max_scale_occupancy, int
        ):
            raise TypeError("max_scale_occupancy must be an integer")
        if self.max_scale_occupancy < 0:
            raise ValueError("max_scale_occupancy must be non-negative")
        if not isinstance(self.initial_snapshot, YardSnapshot):
            raise TypeError("initial_snapshot must be a YardSnapshot")
        if not isinstance(self.final_snapshot, YardSnapshot):
            raise TypeError("final_snapshot must be a YardSnapshot")
        physical_snapshot = self.final_snapshot if self.physical_snapshot is None else self.physical_snapshot
        digital_snapshot = self.final_snapshot if self.digital_snapshot is None else self.digital_snapshot
        if not isinstance(physical_snapshot, YardSnapshot):
            raise TypeError("physical_snapshot must be a YardSnapshot")
        if not isinstance(digital_snapshot, YardSnapshot):
            raise TypeError("digital_snapshot must be a YardSnapshot")
        object.__setattr__(self, "physical_snapshot", physical_snapshot)
        object.__setattr__(self, "digital_snapshot", digital_snapshot)

    @property
    def policy(self) -> str:
        return self.policy_name

    @property
    def dataset_root_hash(self) -> str:
        return self.controls.source_dataset_root_hash

    @property
    def control_hash(self) -> str:
        return self.controls.control_hash

    @property
    def scenario_id(self) -> str:
        return self.scenario.scenario_id

    @property
    def completed_trucks(self) -> int:
        return int(self.metrics.get("completed_trucks", 0))

    @property
    def commands(self) -> tuple[EventRecord, ...]:
        return tuple(event for event in self.events if event.kind == "SERVICE_STARTED")


def tiny_scenario(
    truck_count: int = 4,
    hoppers: int = 1,
    scales: int = 1,
    regime: str = "nominal",
    *,
    hopper_count: int | None = None,
    scale_count: int | None = None,
) -> ScenarioConfig:
    """Return a validated, compact ScenarioConfig for demonstrations."""

    _validate_regime(regime)
    if hopper_count is not None:
        if hoppers != 1 and hoppers != hopper_count:
            raise ValueError("hoppers and hopper_count disagree")
        hoppers = hopper_count
    if scale_count is not None:
        if scales != 1 and scales != scale_count:
            raise ValueError("scales and scale_count disagree")
        scales = scale_count
    return ScenarioConfig(
        truck_count=truck_count,
        hopper_count=hoppers,
        scale_count=scales,
        regime=regime,
    )


class _DaySimulation:
    def __init__(self, instance: FrozenInstance, policy: DispatchPolicy,
                 controls: ExecutionControls, event_latents: EventLatentLedger, *,
                 operator_script: SyntheticOperatorScript | None = None) -> None:
        if operator_script is not None:
            if not callable(operator_script):
                raise TypeError("operator_script must explicitly return SyntheticOperatorResponse")
            if not instance.instance_id.startswith("validation-"):
                raise ValueError("synthetic operator trials require a validation instance_id")
        self.operator_script = operator_script
        self.operator_mode = "synthetic_auto_accept" if operator_script is None else "synthetic_scripted"
        self.source_instance = instance
        self.projection = derive_controlled_projection(instance, event_latents, controls)
        self.instance = self.projection.instance
        self.controls = controls
        scenario = ScenarioConfig(
            len(instance.trucks), sum(r.kind == "hopper" for r in instance.resources),
            sum(r.kind == "scale" for r in instance.resources),
            instance.scenario_id.rsplit("-", 1)[-1], instance.scenario_index,
        )
        if scenario.scenario_id != instance.scenario_id:
            raise ValueError("frozen instance scenario_id disagrees with its records")
        _validate_regime(scenario.regime)
        seed = instance.seed
        self.scenario = scenario
        self.seed = seed
        self.policy = policy
        self.schedule: list[tuple[float, int, str, str, int, _Scheduled]] = []
        self.next_schedule_sequence = 0
        self.next_event_sequence = 1
        self.events: list[EventRecord] = []
        self.clock = 0.0
        self.states: dict[str, _TruckState] = {}
        # Status is the authoritative physical resource state.
        self.resources: dict[str, bool] = {}
        self.resource_status: dict[str, str] = {}
        self.resource_failure_cause: dict[str, str | None] = {}
        self.resource_kind: dict[str, str] = {}
        self.resource_allowed_cargo: dict[str, tuple[str, ...]] = {}
        self.resource_pool: dict[str, tuple[str, ...]] = {}
        self.pending_failures: dict[str, list[_Scheduled]] = {}
        self.active_disruptions: dict[str, dict[str, float]] = {}
        self.scale_occupancy = 0
        self.max_scale_occupancy = 0
        self.waits: list[float] = []
        self.realized_durations: dict[tuple[str, str], float] = {}
        self.first_arrival_time: float | None = None
        self.last_completion_time: float | None = None
        self.buffer_occupancy: dict[str, int] = {
            operation: 0 for operation in ("scale_in", "unload", "scale_out")
        }
        self.max_buffer_occupancy = 0
        self.max_buffer_reservation = 0
        self.digital_model: DigitalModel | None = None
        self._build_resources()
        self._load_frozen_trucks()
        self._schedule_frozen_disruptions()
        self.digital_model = DigitalModel.from_snapshot(
            self._initial_snapshot(),
            scenario=self.scenario,
        )

    def _build_resources(self) -> None:
        expected_resources = {"gate-1": "gate"}
        expected_resources.update({f"hopper-{index}": "hopper" for index in range(1, self.scenario.hopper_count + 1)})
        expected_resources.update({f"scale-{index}": "scale" for index in range(1, self.scenario.scale_count + 1)})
        if {resource.resource_id: resource.kind for resource in self.instance.resources} != expected_resources:
            raise ValueError("frozen resource identities and kinds disagree with the scenario")
        for resource in self.instance.resources:
            resource_id = resource.resource_id
            if resource_id in self.resources or resource.status != "available":
                raise ValueError("frozen resources must be unique and initially available")
            self.resources[resource_id] = True
            self.resource_status[resource_id] = resource.status
            self.resource_failure_cause[resource_id] = None
            self.resource_kind[resource_id] = resource.kind
            self.resource_allowed_cargo[resource_id] = resource.allowed_cargo_types
            self.active_disruptions[resource_id] = {}
        for operation, kind in (("gate", "gate"), ("scale_in", "scale"),
                                ("scale_out", "scale"), ("unload", "hopper")):
            self.resource_pool[operation] = tuple(sorted(
                r.resource_id for r in self.instance.resources if r.kind == kind
            ))
        if self.resource_pool["gate"] != ("gate-1",):
            raise ValueError("frozen instance requires its canonical gate-1 resource")

    def _load_frozen_trucks(self) -> None:
        """Load arrivals and potential service durations without generating values."""
        for index, truck in enumerate(self.instance.trucks):
            if (truck.stage != "gate" or truck.arrival_minute > HORIZON_MINUTES
                    or truck.scenario_id != self.scenario.scenario_id
                    or truck.eligible_resources != ("gate-1",)):
                raise ValueError("frozen truck must start at gate within the horizon")
            self.states[truck.truck_id] = _TruckState(
                truck_id=truck.truck_id, arrival_time=truck.arrival_minute,
                priority=truck.priority, cargo_type=truck.cargo_type,
                document_ok=truck.document_ok, stable_order=index,
                stage_entry_time=truck.arrival_minute,
            )
            self._push(time=truck.arrival_minute, kind="arrival", truck_id=truck.truck_id)
        self.realized_durations = {
            (row.truck_id, row.operation): row.duration_min for row in self.instance.service_times
        }
        expected = {(truck_id, operation) for truck_id in self.states for operation in _OPERATIONS}
        if set(self.realized_durations) != expected or any(
            duration <= 0 for duration in self.realized_durations.values()
        ):
            raise ValueError("frozen service_times must contain exactly four positive durations per truck")

    def _schedule_frozen_disruptions(self) -> None:
        """Enqueue only the events from the validated frozen projection."""
        for row in self.instance.disruptions:
            self._push(
                time=float(row["time"]), kind=row["event_type"],
                truck_id=row["truck_id"] or None, resource_id=row["resource_id"] or None,
                cause=row["cause"], duration=float(row["duration_min"]),
                recovery_at=float(row["return_time"]) if row["return_time"] else None,
                latent_id=row["latent_id"], scheduled_start=float(row["time"]),
            )

    def _push(
        self,
        *,
        time: float,
        kind: str,
        truck_id: str | None = None,
        operation: str | None = None,
        resource_id: str | None = None,
        cause: str | None = None,
        recovery_at: float | None = None,
        duration: float | None = None,
        latent_id: str | None = None,
        scheduled_start: float | None = None,
    ) -> None:
        if kind not in EVENT_RANKS:
            raise ValueError(f"unknown scheduled event kind: {kind}")
        if not math.isfinite(time) or time < self.clock:
            raise ValueError("scheduled event time must be finite and monotonic")
        if recovery_at is not None and (not math.isfinite(recovery_at) or (recovery_at < time and kind != "rain_start")):
            raise ValueError("recovery_at must be finite and no earlier than event time")
        self.next_schedule_sequence += 1
        item = _Scheduled(
            time=float(time),
            rank=EVENT_RANKS[kind],
            sequence=self.next_schedule_sequence,
            kind=kind,
            truck_id=truck_id,
            operation=operation,
            resource_id=resource_id,
            cause=cause,
            recovery_at=recovery_at, duration=duration, latent_id=latent_id,
            scheduled_start=scheduled_start,
        )
        heapq.heappush(self.schedule, (item.time, item.rank, item.resource_id or "",
                                     item.truck_id or "", item.sequence, item))

    def _emit(self, kind: str, payload: Mapping[str, Any]) -> EventRecord:
        event = EventRecord(
            time=self.clock,
            sequence=self.next_event_sequence,
            kind=kind,
            payload=dict(payload),
        )
        if self.digital_model is None:
            raise RuntimeError("digital model is not initialized before event emission")
        # The digital projection is advanced at the exact emission boundary.
        # If validation fails, the event is not appended and its original cause
        # propagates to the caller (fail-fast, no retry/fallback).
        self.digital_model.apply(event)
        self.events.append(event)
        self.next_event_sequence += 1
        return event

    def _duration(self, truck_id: str, operation: str) -> float:
        return self.realized_durations[(truck_id, operation)]

    def _initial_snapshot(self) -> YardSnapshot:
        trucks = {
            truck_id: Truck(
                truck_id=truck_id,
                arrival_time=state.arrival_time,
                cargo_type=state.cargo_type,
                priority=state.priority,
                document_ok=state.document_ok,
                stage=TRUCK_STAGE_WAITING,
                arrived=False,
                metadata={"stable_order": state.stable_order},
                stage_entry_time=state.stage_entry_time,
                next_operation="gate",
            )
            for truck_id, state in self.states.items()
        }
        resources = {
            resource_id: Resource(
                resource_id=resource_id,
                kind=self.resource_kind[resource_id],
                allowed_cargo_types=self.resource_allowed_cargo[resource_id],
            )
            for resource_id in self.resources
        }
        return YardSnapshot(
            trucks=trucks,
            resources=resources,
            clock=0.0,
            scenario_id=self.scenario.scenario_id,
        )

    def _final_snapshot(self) -> YardSnapshot:
        def truck_stage(state: _TruckState) -> int:
            if state.operation == "done":
                return TRUCK_STAGE_SERVICE_COMPLETED
            if state.active_operation is not None:
                return TRUCK_STAGE_SERVICE_STARTED
            if state.arrived and state.document_ok:
                if state.operation != "gate" or state.service_started or state.ready_time > state.arrival_time:
                    return TRUCK_STAGE_DOCUMENT_RELEASED
                return TRUCK_STAGE_ARRIVED
            return TRUCK_STAGE_WAITING

        trucks = {
            truck_id: Truck(
                truck_id=truck_id,
                arrival_time=state.arrival_time,
                cargo_type=state.cargo_type,
                priority=state.priority,
                document_ok=state.document_ok,
                stage=truck_stage(state),
                resource_id=state.active_resource,
                arrived=state.arrived,
                metadata={"stable_order": state.stable_order},
                stage_entry_time=state.stage_entry_time,
                next_operation=state.operation,
            )
            for truck_id, state in self.states.items()
        }
        resources = {
            resource_id: Resource(
                resource_id=resource_id,
                kind=self.resource_kind[resource_id],
                status=self.resource_status[resource_id],
                allowed_cargo_types=self.resource_allowed_cargo[resource_id],
            )
            for resource_id in self.resources
        }
        decisions = [
            event.to_dict()
            for event in self.events
            if event.kind in {"DECISION_RECORDED", "OPERATOR_DECISION"}
        ]
        return YardSnapshot(
            trucks=trucks,
            resources=resources,
            clock=self.clock,
            running=False,
            ended=True,
            decisions=decisions,
            scenario_id=self.scenario.scenario_id,
        )

    def _set_resource_status(self, resource_id: str, status: str, *, cause: str | None = None) -> None:
        if resource_id not in self.resource_status:
            raise RuntimeError(f"unknown resource: {resource_id}")
        if status not in {"available", "busy", "failed"}:
            raise RuntimeError(f"unknown resource status: {status}")
        self.resource_status[resource_id] = status
        self.resources[resource_id] = status == "available"
        if cause is not None:
            self.resource_failure_cause[resource_id] = cause
        elif status == "available":
            self.resource_failure_cause[resource_id] = None

    def _queue_occupancy(self, operation: str) -> int:
        return sum(
            1
            for state in self.states.values()
            if state.operation == operation and state.arrived and state.active_operation is None
        )

    def _unload_reservation(self) -> int:
        """Count queued and in-flight trucks that still need unload capacity.

        A scale-in service is upstream of the unload buffer.  Its active and
        queued trucks already reserve a slot, as do trucks waiting for or
        executing unload.  Gate trucks remain in the external arrival queue
        until gate completion and therefore do not consume this internal
        reservation yet.
        """

        return sum(
            1
            for state in self.states.values()
            if state.arrived and state.operation in {"scale_in", "unload"}
        )

    def _update_buffer_occupancy(self) -> None:
        self.buffer_occupancy["scale_in"] = self._queue_occupancy("scale_in")
        self.buffer_occupancy["unload"] = max(
            self._queue_occupancy("unload"), self._unload_reservation()
        )
        self.buffer_occupancy["scale_out"] = self._queue_occupancy("scale_out")
        self.max_buffer_reservation = max(
            self.max_buffer_reservation, self._unload_reservation()
        )
        self.max_buffer_occupancy = max(self.max_buffer_occupancy, *self.buffer_occupancy.values())
        if self.max_buffer_occupancy > self.controls.buffer_capacity or self.max_buffer_reservation > self.controls.buffer_capacity:
            raise RuntimeError(
                "hard constraint violation: buffer capacity exceeded "
                f"(occupancy={self.max_buffer_occupancy}, reservation="
                f"{self.max_buffer_reservation}>{self.controls.buffer_capacity})"
            )

    def _buffer_allows(self, operation: str) -> bool:
        if operation == "gate":
            return self._unload_reservation() < self.controls.buffer_capacity
        if operation == "scale_in":
            # The candidate itself is already part of the reservation.
            return self._unload_reservation() <= self.controls.buffer_capacity
        downstream = {"gate": "scale_in", "scale_in": "unload", "unload": "scale_out"}.get(operation)
        if downstream is None:
            return True
        return self._queue_occupancy(downstream) < self.controls.buffer_capacity

    @staticmethod
    def _snapshot_unload_reservation(snapshot: YardSnapshot) -> int:
        return sum(
            1
            for truck in snapshot.trucks.values()
            if truck.arrived and truck.next_operation in {"scale_in", "unload"}
        )

    @classmethod
    def _snapshot_queue_occupancy(cls, snapshot: YardSnapshot, operation: str) -> int:
        return sum(
            1
            for truck in snapshot.trucks.values()
            if truck.arrived
            and truck.next_operation == operation
            and truck.stage != TRUCK_STAGE_SERVICE_STARTED
        )

    def _snapshot_buffer_allows(self, snapshot: YardSnapshot, operation: str) -> bool:
        reservation = self._snapshot_unload_reservation(snapshot)
        if operation == "gate":
            return reservation < self.controls.buffer_capacity
        if operation == "scale_in":
            return reservation <= self.controls.buffer_capacity
        downstream = {"scale_in": "unload", "unload": "scale_out"}.get(operation)
        if downstream is None:
            return True
        return self._snapshot_queue_occupancy(snapshot, downstream) < self.controls.buffer_capacity

    def _digital_snapshot(self) -> YardSnapshot:
        if self.digital_model is None:
            raise RuntimeError("digital model is not initialized")
        # ``snapshot`` is a deep detached projection; callers cannot mutate the
        # model or accidentally share Truck/Resource objects with the physical
        # simulation.
        return self.digital_model.snapshot()

    def _candidate_values(
        self, resource_id: str, operations: tuple[str, ...], *, snapshot: YardSnapshot
    ) -> tuple[Candidate, ...]:
        candidates: list[Candidate] = []
        for truck in snapshot.trucks.values():
            operation = truck.next_operation
            if operation not in operations or truck.stage == TRUCK_STAGE_SERVICE_STARTED:
                continue
            if not truck.arrived or operation == "done":
                continue
            pool = self.resource_pool[operation]
            if resource_id not in pool:
                continue
            resource_index = pool.index(resource_id)
            stable_order = int(truck.metadata.get("stable_order", 0))
            eligible = self._snapshot_buffer_allows(snapshot, operation)
            candidates.append(
                Candidate(
                    truck_id=truck.truck_id,
                    arrival_time=truck.arrival_time,
                    priority=truck.priority,
                    cargo_type=truck.cargo_type,
                    document_ok=truck.document_ok,
                    waiting_time=max(0.0, snapshot.clock - truck.stage_entry_time),
                    operation=operation,
                    pressure=self._pressure_value(
                        truck.priority,
                        max(0.0, snapshot.clock - truck.stage_entry_time),
                    ),
                    affinity=1.0
                    if stable_order % max(1, len(pool)) == resource_index
                    else 0.0,
                    stability=1.0 / (1.0 + stable_order),
                    stable_order=stable_order,
                    stage_entry_time=truck.stage_entry_time,
                    resource_id=resource_id,
                    arrived=truck.arrived,
                    eligible=eligible,
                    eligibility_reason=None
                    if eligible
                    else f"buffer full for {operation}",
                )
            )
        # The reorder penalty is a property of this detached stage queue, not
        # of the physical TruckState construction order.
        return tuple(
            replace(
                candidate,
                reorder_penalty=float(
                    sum(
                        1
                        for other in candidates
                        if other.stage_entry_time < candidate.stage_entry_time
                    )
                ),
            )
            for candidate in candidates
        )

    def _dispatch_slots(self) -> tuple[tuple[str, tuple[str, ...], str], ...]:
        slots: list[tuple[str, tuple[str, ...], str]] = [("gate", ("gate",), "gate-1")]
        slots.extend(("scale", ("scale_in", "scale_out"), resource_id) for resource_id in self.resource_pool["scale_in"])
        slots.extend(("unload", ("unload",), resource_id) for resource_id in self.resource_pool["unload"])
        return tuple(slots)

    def _dispatch_available(self) -> None:
        progress = True
        # A rejection idles this resource for the rest of the current external
        # event batch, including additional passes caused by other resources.
        rejected_resources: set[str] = set()
        while progress and self.clock < HORIZON_MINUTES:
            progress = False
            self._update_buffer_occupancy()
            for _slot, operations, resource_id in self._dispatch_slots():
                if resource_id in rejected_resources:
                    continue
                snapshot = self._digital_snapshot()
                resource = snapshot.resources.get(resource_id)
                if resource is None or resource.status != "available":
                    continue
                candidates = self._candidate_values(resource_id, operations, snapshot=snapshot)
                if not candidates:
                    continue
                context = DispatchContext(
                    now=self.clock,
                    resource_id=resource_id,
                    resource_available=True,
                    resource_status=resource.status,
                    operation=None if len(operations) > 1 else operations[0],
                    queue_length=len(candidates),
                    allowed_cargo_types=resource.allowed_cargo_types,
                )
                # Strict FIFO inspects the actual stage queue head before any
                # eligibility filtering; the other policies receive the
                # protocol's admissible window after hard filtering.
                dispatch_candidates = (
                    candidates
                    if self.policy.name == "fifo_strict"
                    else self._admissible_candidates(
                        candidates,
                        allowed_cargo_types=resource.allowed_cargo_types,
                    )
                )
                if not dispatch_candidates:
                    reasons = [
                        {
                            "truck_id": candidate.truck_id,
                            "reason": self._hard_candidate_block_reason(
                                candidate,
                                allowed_cargo_types=resource.allowed_cargo_types,
                            ),
                        }
                        for candidate in candidates
                    ]
                    self._emit(
                        "DISPATCH_BLOCKED",
                        {
                            "resource_id": resource_id,
                            "operation": context.operation or ",".join(operations),
                            "candidate_ids": [candidate.truck_id for candidate in candidates],
                            "reasons": reasons,
                        },
                    )
                    continue
                try:
                    recommendation = recommend(dispatch_candidates, context, self.policy)
                except DispatchBlocked as blocked:
                    self._emit(
                        "DISPATCH_BLOCKED",
                        {
                            "resource_id": resource_id,
                            "operation": context.operation or ",".join(operations),
                            "candidate_ids": [candidate.truck_id for candidate in candidates],
                            "reasons": [
                                {"truck_id": truck_id, "reason": reason}
                                for truck_id, reason in blocked.excluded
                            ],
                        },
                    )
                    continue
                except NoFeasibleCandidate as exc:
                    raise RuntimeError(
                        "prevalidated dispatch candidates unexpectedly became infeasible"
                    ) from exc
                selected_operation = recommendation.selected.operation
                if selected_operation not in operations:
                    raise RuntimeError("policy selected a candidate outside the resource operation pool")
                started = self._apply_operator_response(recommendation, resource_id)
                if started:
                    progress = True
                else:
                    rejected_resources.add(resource_id)

    @staticmethod
    def _hard_candidate_block_reason(
        candidate: Candidate,
        *,
        allowed_cargo_types: tuple[str, ...],
    ) -> str:
        if not candidate.document_ok:
            return "document blocked"
        if not candidate.eligible:
            return candidate.eligibility_reason or "candidate is not eligible"
        if candidate.cargo_type not in allowed_cargo_types:
            return f"cargo type {candidate.cargo_type!r} is incompatible with resource"
        raise RuntimeError("candidate has no hard blocking reason")

    def _admissible_candidates(
        self,
        candidates: tuple[Candidate, ...],
        *,
        allowed_cargo_types: tuple[str, ...],
    ) -> tuple[Candidate, ...]:
        """Apply the protocol's mandatory-priority and short-window rules."""

        hard_feasible = tuple(
            candidate
            for candidate in candidates
            if candidate.document_ok
            and candidate.eligible
            and candidate.cargo_type in allowed_cargo_types
        )
        priority_two = tuple(candidate for candidate in hard_feasible if candidate.priority == 2)
        if priority_two:
            return priority_two
        ordered = tuple(
            sorted(hard_feasible, key=lambda item: (item.stage_entry_time, item.truck_id))
        )
        top_window = ordered[:self.controls.ordinary_window]
        pressured = tuple(
            candidate
            for candidate in ordered
            if self._pressure(candidate) > 0.0
        )
        # Dict insertion order is not relied on: stable sorting gives the
        # same candidate order to every policy and to the audit log.
        merged: dict[str, Candidate] = {candidate.truck_id: candidate for candidate in top_window}
        merged.update({candidate.truck_id: candidate for candidate in pressured})
        return tuple(
            sorted(merged.values(), key=lambda item: (item.stage_entry_time, item.truck_id))
        )

    def _pressure_value(self, priority: int, waiting_time: float) -> float:
        threshold = PRIORITY_THRESHOLDS[min(priority, len(PRIORITY_THRESHOLDS) - 1)] * float(self.controls.threshold_multiplier)
        return max(0.0, waiting_time - threshold)

    def _pressure(self, candidate: Candidate) -> float:
        return self._pressure_value(candidate.priority, candidate.waiting_time)

    def _apply_operator_response(self, recommendation: Recommendation, resource_id: str) -> bool:
        response = None
        selected = recommendation.selected
        if self.operator_script is not None:
            response = self.operator_script(recommendation)
            if not isinstance(response, SyntheticOperatorResponse):
                raise TypeError("operator_script must return SyntheticOperatorResponse; no implicit acceptance")
            selected = response.resolve(recommendation)
            if response.action == "override":
                # Strict FIFO deliberately retains the full feasible queue for
                # head-of-line blocking. That queue is not the operator's Cadm.
                admissible = self._admissible_candidates(
                    recommendation.candidates,
                    allowed_cargo_types=recommendation.context.allowed_cargo_types,
                )
                if selected not in admissible:
                    raise ValueError("synthetic override violates mandatory-priority/window admission")
            if selected is None:
                self._emit("DECISION_RECORDED", {"decision": recommendation.to_dict()})
                self._emit("OPERATOR_DECISION", self._scripted_operator_payload(recommendation, response, None))
                return False
        selected_id = selected.truck_id
        operation = selected.operation
        snapshot = self._digital_snapshot()
        digital_truck = snapshot.trucks.get(selected_id)
        digital_resource = snapshot.resources.get(resource_id)
        if digital_truck is None or digital_resource is None:
            raise RuntimeError("dispatch command references an unknown digital entity")
        if not digital_truck.arrived:
            raise RuntimeError(f"hard constraint violation: truck has not arrived {selected_id}")
        if digital_truck.next_operation != operation or digital_truck.stage == TRUCK_STAGE_SERVICE_STARTED:
            raise RuntimeError(f"hard constraint violation: invalid digital operation for {selected_id}")
        if not digital_truck.document_ok:
            raise RuntimeError(f"hard constraint violation: document blocked truck {selected_id}")
        if digital_resource.status != "available":
            raise RuntimeError(f"hard constraint violation: resource unavailable {resource_id}")
        if digital_truck.cargo_type not in digital_resource.allowed_cargo_types:
            raise RuntimeError(
                f"hard constraint violation: cargo {digital_truck.cargo_type!r} "
                f"is incompatible with {resource_id}"
            )
        if not self._snapshot_buffer_allows(snapshot, operation):
            raise RuntimeError(f"hard constraint violation: downstream buffer full for {operation}")
        state = self.states[selected_id]
        # Physical state is checked only at command execution.  It never feeds
        # candidate construction or policy ranking.
        if state.operation != operation or state.active_operation is not None:
            raise RuntimeError(f"hard constraint violation: invalid physical operation for {selected_id}")
        if self.resource_status[resource_id] != "available":
            raise RuntimeError(f"hard constraint violation: physical resource unavailable {resource_id}")
        self._emit("DECISION_RECORDED", {"decision": recommendation.to_dict()})
        self._emit(
            "OPERATOR_DECISION",
            self._scripted_operator_payload(recommendation, response, selected)
            if response is not None else
            {"decision": "accept", "operator_mode": "synthetic_auto_accept", "recommendation": recommendation.to_dict()},
        )
        duration = self._duration(selected_id, operation)
        # Execute the validated typed command against the physical model before
        # emitting SERVICE_STARTED.  The event then advances the detached
        # digital projection and verifies the same transition independently.
        self._set_resource_status(resource_id, "busy")
        state.active_resource = resource_id
        state.active_operation = operation
        state.stage_entry_time = self.clock
        state.service_started.append((operation, self.clock))
        wait = max(0.0, self.clock - selected.stage_entry_time)
        state.waiting_total += wait
        self.waits.append(wait)
        if operation in {"scale_in", "scale_out"}:
            self.scale_occupancy += 1
            self.max_scale_occupancy = max(self.max_scale_occupancy, self.scale_occupancy)
            if self.scale_occupancy > self.scenario.scale_count:
                raise RuntimeError("hard constraint violation: scale pool over capacity")
        self._emit(
            "SERVICE_STARTED",
            {
                "truck_id": selected_id,
                "resource_id": resource_id,
                "operation": operation,
                "cargo_type": digital_truck.cargo_type,
                "allowed_cargo_types": list(digital_resource.allowed_cargo_types),
                "command": "start",
                "duration_minutes": duration,
            },
        )
        self._push(
            time=self.clock + duration,
            kind="service_completion",
            truck_id=selected_id,
            operation=operation,
            resource_id=resource_id,
        )
        return True

    @staticmethod
    def _scripted_operator_payload(
        recommendation: Recommendation, response: SyntheticOperatorResponse,
        selected: Candidate | None,
    ) -> dict[str, Any]:
        return {
            "operator_payload_version": SYNTHETIC_OPERATOR_PAYLOAD_VERSION,
            "operator_mode": "synthetic_scripted", "origin": "simulated",
            "decision": response.action, "reason": response.reason,
            "recommendation": recommendation.to_dict(),
            "selection": None if selected is None else selected.to_dict(),
        }

    def _activate_disruption(self, item: _Scheduled) -> None:
        resource_id = item.resource_id
        if resource_id is None or item.latent_id is None or item.duration is None:
            raise RuntimeError("frozen disruption is missing its resource, latent or duration")
        recovery = (item.recovery_at if item.kind == "rain_start"
                    else self.clock + item.duration)
        if recovery is None:
            raise RuntimeError("rain requires its frozen end time")
        evidence = {
            "resource_id": resource_id, "cause": item.cause, "latent_id": item.latent_id,
            "scheduled_failure_start": item.scheduled_start,
            "effective_failure_start": self.clock,
            "scheduled_failure_duration": item.duration,
            "recovery_time": recovery,
            "expired_before_effective_start": recovery <= self.clock,
        }
        self._emit("DISRUPTION_RECORDED", evidence)
        if recovery <= self.clock:
            return
        active = self.active_disruptions[resource_id]
        if item.latent_id in active:
            raise RuntimeError("duplicate active frozen disruption")
        active[item.latent_id] = recovery
        if self.resource_status[resource_id] == "available":
            self._set_resource_status(resource_id, "failed", cause=item.cause)
            self._emit("RESOURCE_FAILED", {
                **evidence, "duration_minutes": recovery - self.clock,
            })
        elif self.resource_status[resource_id] != "failed":
            raise RuntimeError("disruption cannot preempt an active service")
        if item.kind != "rain_start":
            self._push(time=recovery, kind="resource_recovery", resource_id=resource_id,
                       cause=item.cause, latent_id=item.latent_id)

    def _handle_resource_failure(self, item: _Scheduled) -> None:
        if item.resource_id not in self.resource_status:
            raise RuntimeError("resource failure event has an unknown resource")
        if self.resource_status[item.resource_id] == "busy":
            self.pending_failures.setdefault(item.resource_id, []).append(item)
        else:
            self._activate_disruption(item)

    def _recover_disruption(self, item: _Scheduled) -> None:
        active = self.active_disruptions[item.resource_id]
        if item.latent_id not in active:
            if item.kind == "rain_end":
                return  # rain may finish before the nonpreemptive service
            raise RuntimeError("resource recovery has no matching active disruption")
        del active[item.latent_id]
        if not active:
            self._set_resource_status(item.resource_id, "available")
            self._emit("RESOURCE_RECOVERED", {
                "resource_id": item.resource_id, "cause": item.cause,
                "latent_id": item.latent_id,
            })

    def _process(self, item: _Scheduled) -> None:
        if item.kind in {"arrival", "document_release", "service_completion", "priority_change"}:
            if item.truck_id is None:
                raise RuntimeError(f"scheduled {item.kind} event has no truck")
            state = self.states[item.truck_id]
        else:
            state = None
        if item.kind == "arrival":
            if state.arrived:
                raise RuntimeError(f"duplicate arrival for {state.truck_id}")
            state.arrived = True
            if self.first_arrival_time is None:
                self.first_arrival_time = self.clock
            else:
                self.first_arrival_time = min(self.first_arrival_time, self.clock)
            self._emit(
                "TRUCK_ARRIVED",
                {
                    "truck_id": state.truck_id,
                    "arrival_time": state.arrival_time,
                    "cargo_type": state.cargo_type,
                    "priority": state.priority,
                    "document_ok": state.document_ok,
                    "stage": 1 if state.document_ok else 0,
                },
            )
            state.ready_time = state.arrival_time
            state.stage_entry_time = self.clock
            return
        if item.kind == "document_release":
            if state.document_ok:
                raise RuntimeError(f"duplicate document release for {state.truck_id}")
            state.document_ok = True
            state.ready_time = self.clock
            state.stage_entry_time = self.clock
            self._emit("DOCUMENT_RELEASED", {"truck_id": state.truck_id})
            return
        if item.kind == "priority_change":
            if state.operation == "done":
                return
            state.priority = 2
            self._emit("PRIORITY_CHANGED", {"truck_id": state.truck_id, "priority": 2})
            return
        if item.kind in {"resource_failure", "rain_start"}:
            self._handle_resource_failure(item)
            return
        if item.kind in {"rain_end", "resource_recovery"}:
            self._recover_disruption(item)
            return
        if item.kind == "service_completion":
            if state is None or item.operation is None or item.resource_id is None:
                raise RuntimeError("completion event missing operation/resource")
            if state.active_operation != item.operation or state.active_resource != item.resource_id:
                raise RuntimeError(f"completion does not match active service for {state.truck_id}")
            if self.resource_status[item.resource_id] != "busy":
                raise RuntimeError("completion resource is not busy")
            self._set_resource_status(item.resource_id, "available")
            self._emit(
                "SERVICE_COMPLETED",
                {"truck_id": state.truck_id, "resource_id": item.resource_id, "operation": item.operation},
            )
            if self.last_completion_time is None:
                self.last_completion_time = self.clock
            else:
                self.last_completion_time = max(self.last_completion_time, self.clock)
            if item.operation in {"scale_in", "scale_out"}:
                self.scale_occupancy -= 1
                if self.scale_occupancy < 0:
                    raise RuntimeError("hard constraint violation: negative scale occupancy")
            state.active_operation = None
            state.active_resource = None
            state.stage_entry_time = self.clock
            next_index = _OPERATIONS.index(item.operation) + 1
            if next_index >= len(_OPERATIONS):
                state.operation = "done"
                state.completed_at = self.clock
            else:
                state.operation = _OPERATIONS[next_index]
                state.ready_time = self.clock
                state.stage_entry_time = self.clock
            pending = self.pending_failures.pop(item.resource_id, None)
            for failure in pending or ():
                self._push(
                    time=self.clock, kind=failure.kind, resource_id=failure.resource_id,
                    cause=failure.cause, recovery_at=failure.recovery_at,
                    duration=failure.duration, latent_id=failure.latent_id,
                    scheduled_start=failure.scheduled_start,
                )
            self._update_buffer_occupancy()
            return
        raise RuntimeError(f"unknown scheduled event kind: {item.kind}")

    def _wait_metrics(self) -> tuple[float, float, float]:
        """Return mean/p95 accumulated wait per truck and censored residual."""

        waits: list[float] = []
        censored = 0.0
        for truck_id in sorted(self.states):
            state = self.states[truck_id]
            value = state.waiting_total
            if (
                state.arrived
                and state.document_ok
                and state.active_operation is None
                and state.operation != "done"
            ):
                residual = max(0.0, self.clock - state.ready_time)
                value += residual
                censored += residual
            waits.append(value)
        ordered = sorted(waits)
        index = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)) if ordered else 0
        mean = sum(waits) / len(waits) if waits else 0.0
        return mean, ordered[index] if ordered else 0.0, censored

    def run(self) -> DayResult:
        initial_snapshot = self._initial_snapshot()
        self.digital_model = DigitalModel.from_snapshot(
            initial_snapshot,
            scenario=self.scenario,
        )
        self._emit(
            "RUN_STARTED",
            {
                "scenario_id": self.scenario.scenario_id,
                "instance_id": self.source_instance.instance_id,
                "instance_hash": self.source_instance.instance_hash,
                "execution_instance_hash": self.instance.instance_hash,
                "dataset_root_hash": self.controls.source_dataset_root_hash,
                "control_hash": self.controls.control_hash,
                "controlled_view_hash": self.projection.controlled_view_hash,
                "event_overlay_hash": self.projection.event_overlay_hash,
                "event_latents_sha256": self.controls.event_latents_sha256,
                "execution_controls": self.controls.to_dict(),
                "operator_mode": self.operator_mode,
                "event_semantics_version": EVENT_SEMANTICS_VERSION,
                "event_ranks": dict(EVENT_RANKS),
                "resources": initial_snapshot.canonical_dict()["resources"],
            },
        )
        while self.schedule:
            next_time = self.schedule[0][0]
            if next_time > HORIZON_MINUTES:
                self.clock = HORIZON_MINUTES
                break
            self.clock = float(next_time)
            while self.schedule and self.schedule[0][0] == next_time:
                self._process(heapq.heappop(self.schedule)[-1])
            self._update_buffer_occupancy()
            self._dispatch_available()
        # The horizon is a fixed observation boundary even when the queue
        # drains early; future scheduled events are intentionally censored.
        self.clock = HORIZON_MINUTES
        self._update_buffer_occupancy()
        self._emit("END_OF_DAY", {"horizon_minutes": int(HORIZON_MINUTES)})

        physical_snapshot = self._final_snapshot()
        try:
            replayed_snapshot = replay_events(
                self.events,
                physical=initial_snapshot,
                scenario=self.scenario,
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError("emulator event stream failed digital replay") from exc
        if self.digital_model is None:  # pragma: no cover - initialized above
            raise RuntimeError("digital model missing at run completion")
        digital_snapshot = self.digital_model.snapshot()
        if digital_snapshot.canonical_dict() != replayed_snapshot.canonical_dict():
            raise RuntimeError(
                "incremental digital model diverged from independent event replay"
            )
        physical_dict = physical_snapshot.canonical_dict()
        digital_dict = digital_snapshot.canonical_dict()
        if physical_dict != digital_dict:
            differing = sorted(
                key for key in set(physical_dict) | set(digital_dict)
                if physical_dict.get(key) != digital_dict.get(key)
            )
            raise RuntimeError(
                "snapshot divergence between physical and digital replay: "
                f"fields={differing}; physical={physical_dict}; digital={digital_dict}"
            )

        completed = sum(state.operation == "done" for state in self.states.values())
        remaining = len(self.states) - completed
        mean_wait, p95_wait, censored_wait = self._wait_metrics()
        if self.first_arrival_time is None:
            raise RuntimeError(
                "cannot derive makespan: no TRUCK_ARRIVED event before the hard horizon"
            )
        if self.last_completion_time is None:
            raise RuntimeError(
                "cannot derive makespan: no SERVICE_COMPLETED event before the hard horizon"
            )
        makespan = self.last_completion_time - self.first_arrival_time
        if not math.isfinite(makespan) or makespan <= 0.0:
            raise RuntimeError(
                "cannot derive makespan: last SERVICE_COMPLETED is not after first TRUCK_ARRIVED"
            )
        metrics: dict[str, float | int] = {
            "total_trucks": len(self.states),
            "completed_trucks": completed,
            "remaining_trucks": remaining,
            "throughput": completed,
            "mean_wait_minutes": _round_metric(mean_wait),
            "p95_wait_minutes": _round_metric(p95_wait),
            "censored_wait_minutes": _round_metric(censored_wait),
            "makespan_minutes": _round_metric(makespan),
            "horizon_minutes": int(HORIZON_MINUTES),
            "throughput_rate": _round_metric(completed / makespan) if makespan > 0 else 0.0,
            "scale_occupancy_peak": self.max_scale_occupancy,
            "max_buffer_occupancy": self.max_buffer_occupancy,
            "max_buffer_reservation": self.max_buffer_reservation,
            "buffer_capacity": self.controls.buffer_capacity,
            "hard_constraint_violations": 0,
        }
        return DayResult(
            scenario=self.scenario,
            seed=self.seed,
            policy_name=self.policy.name,
            instance_id=self.source_instance.instance_id,
            instance_hash=str(self.source_instance.instance_hash),
            execution_instance_hash=str(self.instance.instance_hash),
            controls=self.controls,
            controlled_view_hash=self.projection.controlled_view_hash,
            event_overlay_hash=self.projection.event_overlay_hash,
            events=tuple(self.events),
            metrics=metrics,
            hard_constraint_violations=0,
            max_scale_occupancy=self.max_scale_occupancy,
            initial_snapshot=initial_snapshot,
            final_snapshot=physical_snapshot,
            physical_snapshot=physical_snapshot,
            digital_snapshot=digital_snapshot,
        )


def run_day(instance: FrozenInstance, policy: DispatchPolicy | str,
            controls: ExecutionControls, event_latents: EventLatentLedger) -> DayResult:
    """Execute validated frozen inputs; never generate or replace missing draws."""
    if not isinstance(instance, FrozenInstance):
        raise TypeError("instance must be a FrozenInstance")
    if not isinstance(controls, ExecutionControls):
        raise TypeError("controls must be ExecutionControls")
    if not isinstance(event_latents, EventLatentLedger):
        raise TypeError("event_latents must be an EventLatentLedger")
    selected_policy = make_policy(policy) if isinstance(policy, str) else policy
    if not isinstance(selected_policy, DispatchPolicy):
        raise TypeError("policy must be a DispatchPolicy or policy name")
    return _DaySimulation(instance, selected_policy, controls, event_latents).run()


def run_synthetic_operator_trial(
    instance: FrozenInstance, policy: DispatchPolicy | str,
    controls: ExecutionControls, event_latents: EventLatentLedger, *,
    operator_script: SyntheticOperatorScript,
) -> DayResult:
    """Exercise explicit simulated responses on validation instances only.

    This is not a scientific matrix entry point. The caller must supply every
    response, and the canonical run_day API retains automatic acceptance.
    """
    if not isinstance(instance, FrozenInstance) or not instance.instance_id.startswith("validation-"):
        raise ValueError("synthetic operator trials require a validation FrozenInstance")
    if not isinstance(controls, ExecutionControls) or not isinstance(event_latents, EventLatentLedger):
        raise TypeError("synthetic operator trials require typed controls and event latents")
    if not callable(operator_script):
        raise TypeError("operator_script must explicitly return SyntheticOperatorResponse")
    selected_policy = make_policy(policy) if isinstance(policy, str) else policy
    if not isinstance(selected_policy, DispatchPolicy):
        raise TypeError("policy must be a DispatchPolicy or policy name")
    return _DaySimulation(instance, selected_policy, controls, event_latents,
                          operator_script=operator_script).run()


__all__ = [
    "DayResult",
    "HORIZON_MINUTES",
    "run_day",
    "run_synthetic_operator_trial",
    "tiny_scenario",
]
