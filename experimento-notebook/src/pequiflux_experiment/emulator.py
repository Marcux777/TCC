"""Deterministic discrete-event emulator for the PequiFlux yard.

The implementation is deliberately small, but it follows the frozen protocol:
conditional NHPP arrivals, explicit document releases, triangular service
times, public disruption events, a hard 720-minute horizon, and one physical
dispatch pool for the two weighing operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import heapq
import math
import random
from types import MappingProxyType
from typing import Any, Mapping

from .config import ScenarioConfig
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
    Truck,
    YardSnapshot,
    canonical_allowed_cargo_types,
    TRUCK_STAGE_ARRIVED,
    TRUCK_STAGE_DOCUMENT_RELEASED,
    TRUCK_STAGE_SERVICE_COMPLETED,
    TRUCK_STAGE_SERVICE_STARTED,
    TRUCK_STAGE_WAITING,
)
from .events import EventRecord
from .policies import make_policy


_OPERATIONS: tuple[str, ...] = ("gate", "scale_in", "unload", "scale_out")
HORIZON_MINUTES = 720.0
BUFFER_CAPACITY = 12
ARRIVAL_BLOCKS: tuple[tuple[float, float], ...] = (
    (0.0, 180.0),
    (180.0, 300.0),
    (300.0, 480.0),
    (480.0, 720.0),
)
ARRIVAL_WEIGHTS: tuple[int, ...] = (6, 3, 7, 2)
PEAK_ARRIVAL_WEIGHTS: tuple[int, ...] = (9, 2, 10, 2)
DOCUMENT_BLOCK_RATE = 0.03
DOCUMENT_RELEASE_TRIANGULAR = (30.0, 60.0, 120.0)
SERVICE_TRIANGULAR: Mapping[str, tuple[float, float, float]] = {
    "gate": (2.0, 4.0, 7.0),
    "scale_in": (3.0, 5.0, 8.0),
    "unload": (12.0, 20.0, 35.0),
    "scale_out": (3.0, 5.0, 8.0),
}
CRITICAL_FAILURE_TIME_RANGE = (240.0, 480.0)
CRITICAL_FAILURE_DURATION = (20.0, 40.0, 70.0)
PRIORITY_SHIFT_TIME_RANGE = (240.0, 480.0)
PRIORITY_THRESHOLDS = (60.0, 30.0, 10.0)
RAIN_BLOCK_MINUTES = 30.0
RAIN_BLOCK_RATE = 0.10

# Lower rank means that an event at the same timestamp is applied first.
# Releases, failures/recoveries, priority changes, and arrivals therefore
# have a stable and explicit order; completions always free resources first.
_SCHEDULE_RANK = {
    "completion": 0,
    "document_release": 1,
    "resource_failure": 2,
    "resource_recovery": 2,
    "rain_start": 2,
    "rain_end": 2,
    "priority_change": 3,
    "arrival": 4,
}
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
    """Canonical output of one scenario/seed/policy execution."""

    scenario: ScenarioConfig
    seed: int
    policy_name: str
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
    def __init__(self, scenario: ScenarioConfig, seed: int, policy: DispatchPolicy) -> None:
        _validate_regime(scenario.regime)
        self.scenario = scenario
        self.seed = seed
        self.policy = policy
        self.schedule: list[tuple[float, int, int, _Scheduled]] = []
        self.next_schedule_sequence = 0
        self.next_event_sequence = 1
        self.events: list[EventRecord] = []
        self.clock = 0.0
        self.states: dict[str, _TruckState] = {}
        # ``resources`` is retained as a compact availability view for the
        # existing API; status is the authoritative physical state.
        self.resources: dict[str, bool] = {}
        self.resource_status: dict[str, str] = {}
        self.resource_failure_cause: dict[str, str | None] = {}
        self.resource_kind: dict[str, str] = {}
        self.resource_allowed_cargo: dict[str, tuple[str, ...]] = {}
        self.resource_pool: dict[str, tuple[str, ...]] = {}
        self.pending_failures: dict[str, tuple[str, float | None]] = {}
        self.scale_occupancy = 0
        self.max_scale_occupancy = 0
        self.waits: list[float] = []
        self.realized_durations: dict[tuple[str, str], float] = {}
        self.document_release_delays: dict[str, float] = {}
        self.first_arrival_time: float | None = None
        self.last_completion_time: float | None = None
        self.buffer_occupancy: dict[str, int] = {
            operation: 0 for operation in ("scale_in", "unload", "scale_out")
        }
        self.max_buffer_occupancy = 0
        self.max_buffer_reservation = 0
        self.digital_model: DigitalModel | None = None
        self._build_resources()
        self._build_trucks()
        self._build_disruptions()
        self.digital_model = DigitalModel.from_snapshot(
            self._initial_snapshot(),
            scenario=self.scenario,
        )

    def _stream(self, *parts: object) -> random.Random:
        """Return a reproducible substream independent of dispatch order.

        The policy is intentionally absent from the key.  Every stochastic
        realization is therefore common across policies for one
        scenario/seed pair, even when policies start different trucks first.
        """

        material = "|".join(
            ("pequiflux-des-crn-v1", self.scenario.scenario_id, str(self.seed), *(str(part) for part in parts))
        )
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        return random.Random(int.from_bytes(digest[:16], "big", signed=False))

    def _build_resources(self) -> None:
        self.resource_pool["gate"] = ("gate-1",)
        hoppers = tuple(f"hopper-{index}" for index in range(1, self.scenario.hopper_count + 1))
        scales = tuple(f"scale-{index}" for index in range(1, self.scenario.scale_count + 1))
        self.resource_pool["unload"] = hoppers
        self.resource_pool["scale_in"] = scales
        self.resource_pool["scale_out"] = scales
        for resource_id in ("gate-1", *hoppers, *scales):
            self.resources[resource_id] = True
            self.resource_status[resource_id] = "available"
            self.resource_failure_cause[resource_id] = None
            kind = "scale" if resource_id.startswith("scale") else resource_id.split("-")[0]
            self.resource_kind[resource_id] = kind
            self.resource_allowed_cargo[resource_id] = canonical_allowed_cargo_types(
                resource_id, kind
            )

    def _build_trucks(self) -> None:
        weights = PEAK_ARRIVAL_WEIGHTS if self.scenario.regime == "peak" else ARRIVAL_WEIGHTS
        # Conditioning on N arrivals gives the exact block probabilities of
        # the protocol while retaining deterministic local random draws.
        block_weights = [weight * (end - start) for weight, (start, end) in zip(weights, ARRIVAL_BLOCKS)]
        for index in range(self.scenario.truck_count):
            arrival_stream = self._stream("truck", index, "arrival")
            block_index = arrival_stream.choices(
                range(len(ARRIVAL_BLOCKS)), weights=block_weights, k=1
            )[0]
            arrival = arrival_stream.uniform(*ARRIVAL_BLOCKS[block_index])
            priority_draw = self._stream("truck", index, "priority").random()
            priority = 2 if priority_draw < 0.15 else 1 if priority_draw < 0.35 else 0
            document_ok = self._stream("truck", index, "document").random() >= DOCUMENT_BLOCK_RATE
            truck_id = f"T-{index + 1:03d}"
            self.states[truck_id] = _TruckState(
                truck_id=truck_id,
                arrival_time=float(arrival),
                priority=priority,
                cargo_type="soy" if index % 2 == 0 else "corn",
                document_ok=document_ok,
                stable_order=index,
                stage_entry_time=float(arrival),
            )
            self._push(time=float(arrival), kind="arrival", truck_id=truck_id)

    def _build_disruptions(self) -> None:
        # One independent shift-level base-failure Bernoulli is sampled for
        # every regime.  The stream key is policy-independent, so changing a
        # dispatch policy cannot change the disruption realization.
        base_failure = self._stream("event", "base_failure", "turn").random() < 0.05
        if base_failure:
            resource_ids = tuple(
                resource_id
                for resource_id in sorted(self.resource_status)
                if not (
                    self.scenario.regime == "critical_failure"
                    and resource_id == "hopper-1"
                )
            )
            if not resource_ids:
                raise RuntimeError("base failure has no resource distinct from the forced override")
            resource_index = self._stream("event", "base_failure", "resource").randrange(
                len(resource_ids)
            )
            self._push(
                time=self._stream("event", "base_failure", "start").uniform(
                    *CRITICAL_FAILURE_TIME_RANGE
                ),
                kind="resource_failure",
                resource_id=resource_ids[resource_index],
                cause="base_failure",
            )
        if self.scenario.regime == "critical_failure":
            self._push(
                time=self._stream("event", "critical_failure", "start").uniform(*CRITICAL_FAILURE_TIME_RANGE),
                kind="resource_failure",
                resource_id="hopper-1",
                cause="critical_failure",
            )
        if self.scenario.regime == "priority_shift":
            shift_time = self._stream("event", "priority_shift", "start").uniform(*PRIORITY_SHIFT_TIME_RANGE)
            eligible = [
                state for state in self.states.values()
                if state.priority < 2 and state.arrival_time >= shift_time
            ]
            if len(eligible) < max(1, math.ceil(0.10 * len(self.states))):
                eligible = [state for state in self.states.values() if state.priority < 2]
            target_count = max(1, math.ceil(0.10 * len(self.states)))
            for state in sorted(eligible, key=lambda item: (item.arrival_time, item.stable_order))[:target_count]:
                self._push(time=shift_time, kind="priority_change", truck_id=state.truck_id)
        # Rain exposes only the first hopper in two-or-more-hopper layouts.
        # Adjacent wet blocks are coalesced into one failure window.
        if self.scenario.hopper_count >= 2:
            wet_blocks = [
                self._stream("event", "rain", block_index).random() < RAIN_BLOCK_RATE
                for block_index in range(24)
            ]
            index = 0
            while index < len(wet_blocks):
                if not wet_blocks[index]:
                    index += 1
                    continue
                first = index
                while index + 1 < len(wet_blocks) and wet_blocks[index + 1]:
                    index += 1
                start = first * RAIN_BLOCK_MINUTES
                end = (index + 1) * RAIN_BLOCK_MINUTES
                self._push(
                    time=start,
                    kind="rain_start",
                    resource_id="hopper-1",
                    cause="rain",
                    recovery_at=end,
                )
                self._push(
                    time=end,
                    kind="rain_end",
                    resource_id="hopper-1",
                    cause="rain",
                    recovery_at=end,
                )
                index += 1

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
    ) -> None:
        if kind not in _SCHEDULE_RANK:
            raise ValueError(f"unknown scheduled event kind: {kind}")
        if not math.isfinite(time) or time < self.clock:
            raise ValueError("scheduled event time must be finite and monotonic")
        if recovery_at is not None and (not math.isfinite(recovery_at) or recovery_at < time):
            raise ValueError("recovery_at must be finite and no earlier than event time")
        self.next_schedule_sequence += 1
        item = _Scheduled(
            time=float(time),
            rank=_SCHEDULE_RANK[kind],
            sequence=self.next_schedule_sequence,
            kind=kind,
            truck_id=truck_id,
            operation=operation,
            resource_id=resource_id,
            cause=cause,
            recovery_at=recovery_at,
        )
        heapq.heappush(self.schedule, (item.time, item.rank, item.sequence, item))

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
        key = (truck_id, operation)
        if key in self.realized_durations:
            return self.realized_durations[key]
        low, mode, high = SERVICE_TRIANGULAR[operation]
        # This draw deliberately occurs after recommendation and acceptance.
        duration = _round_metric(self._stream("truck", truck_id, "duration", operation).triangular(low, high, mode))
        self.realized_durations[key] = duration
        return duration

    def _failure_duration(self, resource_id: str, cause: str, recovery_at: float | None) -> float:
        low, mode, high = CRITICAL_FAILURE_DURATION
        return _round_metric(
            self._stream("event", "failure_duration", resource_id, cause, recovery_at).triangular(
                low, high, mode
            )
        )

    def _document_release_delay(self, truck_id: str) -> float:
        if truck_id not in self.document_release_delays:
            low, mode, high = DOCUMENT_RELEASE_TRIANGULAR
            self.document_release_delays[truck_id] = _round_metric(
                self._stream("truck", truck_id, "document_release").triangular(low, high, mode)
            )
        return self.document_release_delays[truck_id]

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
                kind="scale" if resource_id.startswith("scale") else resource_id.split("-")[0],
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
        if self.max_buffer_occupancy > BUFFER_CAPACITY or self.max_buffer_reservation > BUFFER_CAPACITY:
            raise RuntimeError(
                "hard constraint violation: buffer capacity exceeded "
                f"(occupancy={self.max_buffer_occupancy}, reservation="
                f"{self.max_buffer_reservation}>{BUFFER_CAPACITY})"
            )

    def _buffer_allows(self, operation: str) -> bool:
        if operation == "gate":
            return self._unload_reservation() < BUFFER_CAPACITY
        if operation == "scale_in":
            # The candidate itself is already part of the reservation.
            return self._unload_reservation() <= BUFFER_CAPACITY
        downstream = {"gate": "scale_in", "scale_in": "unload", "unload": "scale_out"}.get(operation)
        if downstream is None:
            return True
        return self._queue_occupancy(downstream) < BUFFER_CAPACITY

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

    @classmethod
    def _snapshot_buffer_allows(cls, snapshot: YardSnapshot, operation: str) -> bool:
        reservation = cls._snapshot_unload_reservation(snapshot)
        if operation == "gate":
            return reservation < BUFFER_CAPACITY
        if operation == "scale_in":
            return reservation <= BUFFER_CAPACITY
        downstream = {"scale_in": "unload", "unload": "scale_out"}.get(operation)
        if downstream is None:
            return True
        return cls._snapshot_queue_occupancy(snapshot, downstream) < BUFFER_CAPACITY

    def _digital_snapshot(self) -> YardSnapshot:
        if self.digital_model is None:
            raise RuntimeError("digital model is not initialized")
        # ``snapshot`` is a deep detached projection; callers cannot mutate the
        # model or accidentally share Truck/Resource objects with the physical
        # simulation.
        return self.digital_model.snapshot()

    def _candidate_values(self, resource_id: str, operations: tuple[str, ...]) -> tuple[Candidate, ...]:
        snapshot = self._digital_snapshot()
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
        while progress and self.clock < HORIZON_MINUTES:
            progress = False
            self._update_buffer_occupancy()
            for _slot, operations, resource_id in self._dispatch_slots():
                snapshot = self._digital_snapshot()
                resource = snapshot.resources.get(resource_id)
                if resource is None or resource.status != "available":
                    continue
                candidates = self._candidate_values(resource_id, operations)
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
                self._accept_and_start(recommendation, selected_operation, resource_id)
                progress = True

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
        top_window = ordered[:6]
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

    @staticmethod
    def _pressure_value(priority: int, waiting_time: float) -> float:
        threshold = PRIORITY_THRESHOLDS[min(priority, len(PRIORITY_THRESHOLDS) - 1)]
        return max(0.0, waiting_time - threshold)

    @classmethod
    def _pressure(cls, candidate: Candidate) -> float:
        return cls._pressure_value(candidate.priority, candidate.waiting_time)

    def _accept_and_start(self, recommendation: Recommendation, operation: str, resource_id: str) -> None:
        selected_id = recommendation.selected.truck_id
        snapshot = self._digital_snapshot()
        digital_truck = snapshot.trucks.get(selected_id)
        digital_resource = snapshot.resources.get(resource_id)
        if digital_truck is None or digital_resource is None:
            raise RuntimeError("dispatch command references an unknown digital entity")
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
            {"decision": "accept", "recommendation": recommendation.to_dict()},
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
        wait = max(0.0, self.clock - recommendation.selected.stage_entry_time)
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
            kind="completion",
            truck_id=selected_id,
            operation=operation,
            resource_id=resource_id,
        )

    def _next_completion_time(self, resource_id: str) -> float | None:
        values = [item.time for _, _, _, item in self.schedule if item.kind == "completion" and item.resource_id == resource_id]
        return min(values) if values else None

    def _emit_resource_failure(self, resource_id: str, cause: str, recovery_at: float | None) -> None:
        if self.resource_status[resource_id] == "failed":
            return
        if self.resource_status[resource_id] != "available":
            raise RuntimeError("resource failure must be applied only when resource is available")
        if recovery_at is None:
            duration = self._failure_duration(resource_id, cause, recovery_at)
            recovery_at = self.clock + duration
        else:
            duration = max(0.0, recovery_at - self.clock)
        self._set_resource_status(resource_id, "failed", cause=cause)
        self._emit(
            "RESOURCE_FAILED",
            {
                "resource_id": resource_id,
                "cause": cause,
                "duration_minutes": _round_metric(duration),
            },
        )
        recovery_at = max(self.clock, recovery_at)
        self._push(
            time=recovery_at,
            kind="resource_recovery",
            resource_id=resource_id,
            cause=cause,
        )

    def _handle_resource_failure(self, item: _Scheduled) -> None:
        resource_id = item.resource_id
        if resource_id is None or resource_id not in self.resource_status:
            raise RuntimeError("resource failure event has an unknown resource")
        cause = item.cause or "unknown"
        if self.resource_status[resource_id] == "failed":
            return
        if self.resource_status[resource_id] == "busy":
            # Non-preemptive services finish first.  The public failure is
            # emitted exactly at that completion boundary.
            recovery_at = item.recovery_at
            self.pending_failures.setdefault(resource_id, (cause, recovery_at))
            return
        self._emit_resource_failure(resource_id, cause, item.recovery_at)

    def _process(self, item: _Scheduled) -> None:
        if item.kind in {"arrival", "document_release", "completion", "priority_change"}:
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
            if not state.document_ok:
                state.ready_time = self.clock + self._document_release_delay(state.truck_id)
                self._push(time=state.ready_time, kind="document_release", truck_id=state.truck_id)
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
        if item.kind == "rain_end":
            return
        if item.kind == "resource_recovery":
            resource_id = item.resource_id
            if resource_id is None or self.resource_status.get(resource_id) != "failed":
                raise RuntimeError("resource recovery does not match a failed resource")
            cause = item.cause or self.resource_failure_cause.get(resource_id) or "unknown"
            self._set_resource_status(resource_id, "available")
            self._emit("RESOURCE_RECOVERED", {"resource_id": resource_id, "cause": cause})
            return
        if item.kind == "completion":
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
            if pending is not None:
                cause, recovery_at = pending
                self._emit_resource_failure(item.resource_id, cause, recovery_at)
            self._update_buffer_occupancy()
            return
        raise RuntimeError(f"unknown scheduled event kind: {item.kind}")

    def _wait_metrics(self) -> tuple[float, float, float]:
        """Return mean/p95 accumulated wait per truck and censored residual."""

        waits: list[float] = []
        censored = 0.0
        for state in self.states.values():
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
                "resources": initial_snapshot.canonical_dict()["resources"],
            },
        )
        while self.schedule:
            next_time = self.schedule[0][0]
            if next_time > HORIZON_MINUTES:
                self.clock = HORIZON_MINUTES
                break
            self.clock = float(next_time)
            same_time: list[_Scheduled] = []
            while self.schedule and self.schedule[0][0] == next_time:
                same_time.append(heapq.heappop(self.schedule)[3])
            for item in same_time:
                self._process(item)
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
            "scale_utilization_peak": self.max_scale_occupancy,
            "max_buffer_occupancy": self.max_buffer_occupancy,
            "max_buffer_reservation": self.max_buffer_reservation,
            "buffer_capacity": BUFFER_CAPACITY,
            "hard_constraint_violations": 0,
        }
        return DayResult(
            scenario=self.scenario,
            seed=self.seed,
            policy_name=self.policy.name,
            events=tuple(self.events),
            metrics=metrics,
            hard_constraint_violations=0,
            max_scale_occupancy=self.max_scale_occupancy,
            initial_snapshot=initial_snapshot,
            final_snapshot=physical_snapshot,
            physical_snapshot=physical_snapshot,
            digital_snapshot=digital_snapshot,
        )


def run_day(scenario: ScenarioConfig, seed: int, policy: DispatchPolicy | str) -> DayResult:
    """Execute one deterministic scenario using a local RNG and policy."""

    if not isinstance(scenario, ScenarioConfig):
        raise TypeError("scenario must be a ScenarioConfig")
    _validate_regime(scenario.regime)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    selected_policy = make_policy(policy) if isinstance(policy, str) else policy
    if not isinstance(selected_policy, DispatchPolicy):
        raise TypeError("policy must be a DispatchPolicy or policy name")
    return _DaySimulation(scenario, seed, selected_policy).run()


__all__ = [
    "ARRIVAL_BLOCKS",
    "ARRIVAL_WEIGHTS",
    "BUFFER_CAPACITY",
    "DayResult",
    "HORIZON_MINUTES",
    "SERVICE_TRIANGULAR",
    "run_day",
    "tiny_scenario",
]
