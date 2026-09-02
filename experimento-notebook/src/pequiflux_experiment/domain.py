"""Mutable physical-domain values used by the independent digital model.

The values in this module deliberately contain no event-processing logic.  A
``YardSnapshot`` can therefore represent the physical observation at a
boundary, while :class:`~pequiflux_experiment.digital_model.DigitalModel`
owns its own deep-copied projection of that observation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
import math
from typing import Any, Iterable, Mapping


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _finite_nonnegative(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


TRUCK_STAGE_WAITING = 0
TRUCK_STAGE_ARRIVED = 1
TRUCK_STAGE_DOCUMENT_RELEASED = 2
TRUCK_STAGE_SERVICE_STARTED = 3
TRUCK_STAGE_SERVICE_COMPLETED = 4
VALID_TRUCK_STAGES = frozenset(
    {
        TRUCK_STAGE_WAITING,
        TRUCK_STAGE_ARRIVED,
        TRUCK_STAGE_DOCUMENT_RELEASED,
        TRUCK_STAGE_SERVICE_STARTED,
        TRUCK_STAGE_SERVICE_COMPLETED,
    }
)
VALID_TRUCK_OPERATIONS = frozenset({"gate", "scale_in", "unload", "scale_out", "done"})

# Resource availability is intentionally a closed set.  Unknown values must
# never be interpreted as available by a replay or command boundary.
VALID_RESOURCE_STATUSES = frozenset({"available", "busy", "failed"})

CANONICAL_CARGO_TYPES = ("soy", "corn")


def canonical_allowed_cargo_types(resource_id: str, kind: str) -> tuple[str, ...]:
    """Return the immutable protocol matrix for a physical resource.

    Hopper 1 is deliberately universal so every canonical layout retains a
    feasible unload resource.  Hopper 2 and 3 are cargo-specialised; gates
    and scales accept both cargoes.  Additional hoppers use the universal
    matrix rather than silently becoming unusable.
    """

    if kind in {"gate", "scale"}:
        return CANONICAL_CARGO_TYPES
    if kind == "hopper":
        if resource_id == "hopper-2":
            return ("soy",)
        if resource_id == "hopper-3":
            return ("corn",)
        return CANONICAL_CARGO_TYPES
    return CANONICAL_CARGO_TYPES


def _cargo_tuple(value: Iterable[str] | None, *, resource_id: str, kind: str) -> tuple[str, ...]:
    if value is None:
        return canonical_allowed_cargo_types(resource_id, kind)
    if isinstance(value, (str, bytes, bytearray)):
        raise TypeError("allowed_cargo_types must be a sequence of strings")
    try:
        result = tuple(value)
    except TypeError as exc:
        raise TypeError("allowed_cargo_types must be a sequence of strings") from exc
    if not result or any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError("allowed_cargo_types must contain non-empty strings")
    if len(set(result)) != len(result):
        raise ValueError("allowed_cargo_types must not contain duplicates")
    return result

_STAGE_STATUS = {
    TRUCK_STAGE_WAITING: "waiting",
    TRUCK_STAGE_ARRIVED: "arrived",
    TRUCK_STAGE_DOCUMENT_RELEASED: "document_released",
    TRUCK_STAGE_SERVICE_STARTED: "service_started",
    TRUCK_STAGE_SERVICE_COMPLETED: "service_completed",
}
_STATUS_STAGE = {status: stage for stage, status in _STAGE_STATUS.items()}


@dataclass
class Truck:
    """The canonical state of one truck in the yard."""

    truck_id: str
    arrival_time: float
    cargo_type: str
    priority: int
    document_ok: bool
    stage: int
    resource_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    arrived: bool = False
    stage_entry_time: float | None = None
    next_operation: str = "gate"

    def __post_init__(self) -> None:
        self.truck_id = _identifier("truck_id", self.truck_id)
        self.arrival_time = _finite_nonnegative("arrival_time", self.arrival_time)
        self.cargo_type = _identifier("cargo_type", self.cargo_type)
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("priority must be an integer")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if not isinstance(self.document_ok, bool):
            raise TypeError("document_ok must be bool")
        if isinstance(self.stage, bool) or not isinstance(self.stage, int):
            raise TypeError("stage must be an integer")
        if self.stage not in VALID_TRUCK_STAGES:
            allowed = ", ".join(str(stage) for stage in sorted(VALID_TRUCK_STAGES))
            raise ValueError(f"stage must be one of: {allowed}")
        if self.resource_id is not None:
            self.resource_id = _identifier("resource_id", self.resource_id)
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        self.metadata = copy.deepcopy(dict(self.metadata))
        if not isinstance(self.arrived, bool):
            raise TypeError("arrived must be bool")
        if self.stage_entry_time is None:
            self.stage_entry_time = self.arrival_time
        else:
            self.stage_entry_time = _finite_nonnegative(
                "stage_entry_time", self.stage_entry_time
            )
        if not isinstance(self.next_operation, str) or self.next_operation not in VALID_TRUCK_OPERATIONS:
            allowed = ", ".join(sorted(VALID_TRUCK_OPERATIONS))
            raise ValueError(f"next_operation must be one of: {allowed}")

    @property
    def id(self) -> str:
        """Short alias useful at boundaries that use generic entity IDs."""

        return self.truck_id

    @property
    def state(self) -> str:
        return self.status

    @state.setter
    def state(self, value: str) -> None:
        self.status = value

    @property
    def status(self) -> str:
        return _STAGE_STATUS[self.stage]

    @status.setter
    def status(self, value: str) -> None:
        if value not in _STATUS_STAGE:
            raise ValueError(f"status must be one of: {', '.join(_STATUS_STAGE)}")
        self.stage = _STATUS_STAGE[value]

    @property
    def document_released(self) -> bool:
        """Compatibility alias for callers that used the earlier name."""

        return self.document_ok

    @document_released.setter
    def document_released(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("document_released must be bool")
        self.document_ok = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "arrival_time": self.arrival_time,
            "cargo_type": self.cargo_type,
            "priority": self.priority,
            "document_ok": self.document_ok,
            "stage": self.stage,
            "resource_id": self.resource_id,
            "metadata": copy.deepcopy(self.metadata),
            "arrived": self.arrived,
            "stage_entry_time": self.stage_entry_time,
            "next_operation": self.next_operation,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Truck":
        if not isinstance(value, Mapping):
            raise TypeError("truck must be a mapping")
        try:
            return cls(
                truck_id=value["truck_id"],
                arrival_time=value["arrival_time"],
                cargo_type=value["cargo_type"],
                priority=value["priority"],
                document_ok=value["document_ok"],
                stage=value["stage"],
                resource_id=value.get("resource_id"),
                metadata=value.get("metadata", {}),
                arrived=value.get("arrived", False),
                stage_entry_time=value.get("stage_entry_time"),
                next_operation=value.get("next_operation", "gate"),
            )
        except KeyError as exc:
            raise ValueError(f"truck missing required field: {exc.args[0]}") from exc


@dataclass
class Resource:
    """The canonical state of one service resource (scale, hopper, or similar)."""

    resource_id: str
    kind: str = "generic"
    status: str = "available"
    metadata: dict[str, Any] = field(default_factory=dict)
    allowed_cargo_types: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        self.resource_id = _identifier("resource_id", self.resource_id)
        self.kind = _identifier("kind", self.kind)
        self.status = _identifier("status", self.status)
        if self.status not in VALID_RESOURCE_STATUSES:
            allowed = ", ".join(sorted(VALID_RESOURCE_STATUSES))
            raise ValueError(f"status must be one of: {allowed}")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        self.metadata = copy.deepcopy(dict(self.metadata))
        self.allowed_cargo_types = _cargo_tuple(
            self.allowed_cargo_types,
            resource_id=self.resource_id,
            kind=self.kind,
        )

    @property
    def id(self) -> str:
        return self.resource_id

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @failed.setter
    def failed(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("failed must be bool")
        self.status = "failed" if value else "available"

    @property
    def available(self) -> bool:
        return self.status == "available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "status": self.status,
            "metadata": copy.deepcopy(self.metadata),
            "allowed_cargo_types": list(self.allowed_cargo_types),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Resource":
        if not isinstance(value, Mapping):
            raise TypeError("resource must be a mapping")
        try:
            return cls(
                resource_id=value["resource_id"],
                kind=value.get("kind", "generic"),
                status=value.get("status", "available"),
                metadata=value.get("metadata", {}),
                allowed_cargo_types=value.get("allowed_cargo_types"),
            )
        except KeyError as exc:
            raise ValueError(f"resource missing required field: {exc.args[0]}") from exc


@dataclass
class YardSnapshot:
    """A complete, JSON-friendly observation of the yard at one instant."""

    trucks: dict[str, Truck] = field(default_factory=dict)
    resources: dict[str, Resource] = field(default_factory=dict)
    clock: float = 0.0
    running: bool = False
    ended: bool = False
    decisions: list[dict[str, Any]] = field(default_factory=list)
    scenario_id: str | None = None

    @classmethod
    def empty(cls) -> "YardSnapshot":
        """Create the canonical empty yard state."""

        return cls()

    def __post_init__(self) -> None:
        if not isinstance(self.trucks, Mapping):
            raise TypeError("trucks must be a mapping")
        normalised_trucks: dict[str, Truck] = {}
        for key, value in self.trucks.items():
            truck = value if isinstance(value, Truck) else Truck.from_dict(value)
            truck_key = _identifier("truck key", key)
            if truck_key != truck.truck_id:
                raise ValueError("truck key must match truck_id")
            normalised_trucks[truck_key] = truck
        self.trucks = normalised_trucks

        if not isinstance(self.resources, Mapping):
            raise TypeError("resources must be a mapping")
        normalised_resources: dict[str, Resource] = {}
        for key, value in self.resources.items():
            resource = value if isinstance(value, Resource) else Resource.from_dict(value)
            resource_key = _identifier("resource key", key)
            if resource_key != resource.resource_id:
                raise ValueError("resource key must match resource_id")
            if resource.status not in VALID_RESOURCE_STATUSES:
                allowed = ", ".join(sorted(VALID_RESOURCE_STATUSES))
                raise ValueError(f"status must be one of: {allowed}")
            normalised_resources[resource_key] = resource
        self.resources = normalised_resources

        self.clock = _finite_nonnegative("clock", self.clock)
        if not isinstance(self.running, bool) or not isinstance(self.ended, bool):
            raise TypeError("running and ended must be bool")
        if self.ended and self.running:
            raise ValueError("ended snapshot cannot still be running")
        if not isinstance(self.decisions, list):
            raise TypeError("decisions must be a list")
        if any(not isinstance(item, Mapping) for item in self.decisions):
            raise TypeError("decisions must contain mappings")
        self.decisions = copy.deepcopy([dict(item) for item in self.decisions])
        if self.scenario_id is not None:
            self.scenario_id = _identifier("scenario_id", self.scenario_id)

    @property
    def time(self) -> float:
        """Alias for ``clock`` at event-oriented boundaries."""

        return self.clock

    @time.setter
    def time(self, value: float) -> None:
        self.clock = _finite_nonnegative("clock", value)

    def to_dict(self) -> dict[str, Any]:
        return self.canonical_dict()

    def canonical_dict(self) -> dict[str, Any]:
        """Return a detached, deterministically ordered state representation."""

        return {
            "trucks": {
                key: self.trucks[key].to_dict() for key in sorted(self.trucks)
            },
            "resources": {
                key: self.resources[key].to_dict() for key in sorted(self.resources)
            },
            "clock": self.clock,
            "running": self.running,
            "ended": self.ended,
            "decisions": copy.deepcopy(self.decisions),
            "scenario_id": self.scenario_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "YardSnapshot":
        if not isinstance(value, Mapping):
            raise TypeError("snapshot must be a mapping")
        return cls(
            trucks=value.get("trucks", {}),
            resources=value.get("resources", {}),
            clock=value.get("clock", value.get("time", 0.0)),
            running=value.get("running", False),
            ended=value.get("ended", False),
            decisions=value.get("decisions", []),
            scenario_id=value.get("scenario_id"),
        )
