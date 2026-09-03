"""Mutable physical-domain values used by the independent digital model.

The values in this module deliberately contain no event-processing logic.  A
``YardSnapshot`` can therefore represent the physical observation at a
boundary, while :class:`~pequiflux_experiment.digital_model.DigitalModel`
owns its own deep-copied projection of that observation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .config import crn_digest


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


# ---------------------------------------------------------------------------
# Frozen dataset-domain values
# ---------------------------------------------------------------------------


def _freeze_dataset_value(value: Any) -> Any:
    """Detach a JSON-compatible value into immutable containers."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_dataset_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_dataset_value(item) for item in value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("dataset values must be finite")
        return value
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"dataset value is not JSON-compatible: {type(value).__name__}")


def _thaw_dataset_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_dataset_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_dataset_value(item) for item in value]
    return value


def _dataset_canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _thaw_dataset_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _dataset_digest(value: Any) -> str:
    return hashlib.sha256(_dataset_canonical_bytes(value)).hexdigest()


_FROZEN_DOCUMENT_STATUSES = frozenset({"CLEAR", "BLOCKED"})
_FROZEN_STAGES = frozenset({"gate", "scale_in", "unload", "scale_out", "done"})


@dataclass(frozen=True, slots=True)
class FrozenTruck:
    """Immutable truck record persisted in ``trucks.parquet``."""

    instance_id: str
    scenario_index: int
    scenario_id: str
    seed: int
    truck_id: str
    arrival_minute: float
    cargo_type: str
    priority: int
    document_status: str
    stage: str = "gate"
    eligible_resources: tuple[str, ...] = ()
    generation_attempt: int = 0
    truck_record_hash: str | None = None

    def __post_init__(self) -> None:
        for name in ("instance_id", "scenario_id", "truck_id", "cargo_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        for name in ("scenario_index", "seed", "priority"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(self.arrival_minute, (int, float)) or isinstance(self.arrival_minute, bool):
            raise TypeError("arrival_minute must be numeric")
        arrival = float(self.arrival_minute)
        if not math.isfinite(arrival) or arrival < 0:
            raise ValueError("arrival_minute must be finite and non-negative")
        object.__setattr__(self, "arrival_minute", arrival)
        if self.document_status not in _FROZEN_DOCUMENT_STATUSES:
            raise ValueError("document_status must be CLEAR or BLOCKED")
        if self.stage not in _FROZEN_STAGES:
            raise ValueError(f"stage must be one of {sorted(_FROZEN_STAGES)!r}")
        if isinstance(self.generation_attempt, bool) or not isinstance(self.generation_attempt, int) or self.generation_attempt < 0:
            raise ValueError("generation_attempt must be a non-negative integer")
        resources = tuple(self.eligible_resources)
        if any(not isinstance(item, str) or not item.strip() for item in resources):
            raise ValueError("eligible_resources must contain non-empty strings")
        if len(set(resources)) != len(resources):
            raise ValueError("eligible_resources must not contain duplicates")
        object.__setattr__(self, "eligible_resources", resources)
        expected = _dataset_digest(self._record_without_hash())
        if self.truck_record_hash is None:
            object.__setattr__(self, "truck_record_hash", expected)
        elif self.truck_record_hash != expected:
            raise ValueError("truck_record_hash does not match canonical truck record")

    @property
    def arrival_time(self) -> float:
        return self.arrival_minute

    @property
    def document_ok(self) -> bool:
        return self.document_status == "CLEAR"

    def _record_without_hash(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "scenario_index": self.scenario_index,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "truck_id": self.truck_id,
            "arrival_minute": self.arrival_minute,
            "cargo_type": self.cargo_type,
            "priority": self.priority,
            "document_status": self.document_status,
            "stage": self.stage,
            "eligible_resources": list(self.eligible_resources),
            "generation_attempt": self.generation_attempt,
        }

    @property
    def canonical_record_hash(self) -> str:
        return self.truck_record_hash or _dataset_digest(self._record_without_hash())

    def to_dict(self) -> dict[str, Any]:
        record = self._record_without_hash()
        record.pop("generation_attempt", None)
        record["truck_record_hash"] = self.canonical_record_hash
        return record

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenTruck":
        if not isinstance(value, Mapping):
            raise TypeError("frozen truck must be a mapping")
        required = {
            "instance_id", "scenario_index", "scenario_id", "seed", "truck_id",
            "arrival_minute", "cargo_type", "priority", "document_status", "stage",
            "eligible_resources", "truck_record_hash",
        }
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"frozen truck missing required fields: {', '.join(missing)}")
        unexpected = sorted(set(value) - required - {"generation_attempt"})
        if unexpected:
            raise ValueError(f"frozen truck has unexpected fields: {', '.join(unexpected)}")
        return cls(
            instance_id=value["instance_id"],
            scenario_index=value["scenario_index"],
            scenario_id=value["scenario_id"],
            seed=value["seed"],
            truck_id=value["truck_id"],
            arrival_minute=value["arrival_minute"],
            cargo_type=value["cargo_type"],
            priority=value["priority"],
            document_status=value["document_status"],
            stage=value["stage"],
            eligible_resources=value["eligible_resources"],
            generation_attempt=value.get("generation_attempt", 0),
            truck_record_hash=value["truck_record_hash"],
        )


@dataclass(frozen=True, slots=True)
class FrozenResource:
    """Immutable resource record used by a frozen instance."""

    resource_id: str
    kind: str
    allowed_cargo_types: tuple[str, ...]
    status: str = "available"

    def __post_init__(self) -> None:
        for name in ("resource_id", "kind", "status"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.status not in VALID_RESOURCE_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_RESOURCE_STATUSES)!r}")
        cargo = tuple(self.allowed_cargo_types)
        if not cargo or any(not isinstance(item, str) or not item.strip() for item in cargo):
            raise ValueError("allowed_cargo_types must contain non-empty strings")
        if len(set(cargo)) != len(cargo):
            raise ValueError("allowed_cargo_types must not contain duplicates")
        object.__setattr__(self, "allowed_cargo_types", cargo)

    @property
    def id(self) -> str:
        return self.resource_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "allowed_cargo_types": list(self.allowed_cargo_types),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class FrozenServiceTime:
    """One pre-generated service duration and its CRN provenance."""

    instance_id: str
    scenario_index: int
    scenario_id: str
    seed: int
    truck_id: str
    operation: str
    duration_min: float
    source_a: float
    source_mode: float
    source_b: float
    draw_key: str
    crn_version: str
    generation_attempt: int = 0
    service_record_hash: str | None = None

    def __post_init__(self) -> None:
        for name in ("instance_id", "scenario_id", "truck_id", "operation", "draw_key", "crn_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.scenario_index, bool) or not isinstance(self.scenario_index, int) or self.scenario_index < 0:
            raise ValueError("scenario_index must be a non-negative integer")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if isinstance(self.generation_attempt, bool) or not isinstance(self.generation_attempt, int) or self.generation_attempt < 0:
            raise ValueError("generation_attempt must be a non-negative integer")
        if not isinstance(self.duration_min, (int, float)) or isinstance(self.duration_min, bool):
            raise TypeError("duration_min must be numeric")
        duration = float(self.duration_min)
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("duration_min must be finite and non-negative")
        object.__setattr__(self, "duration_min", duration)
        sources = tuple(float(getattr(self, name)) for name in ("source_a", "source_mode", "source_b"))
        if any(not math.isfinite(item) or item < 0 for item in sources):
            raise ValueError("service sources must be finite and non-negative")
        if not sources[0] <= sources[1] <= sources[2]:
            raise ValueError("service sources must be ordered")
        for name, item in zip(("source_a", "source_mode", "source_b"), sources):
            object.__setattr__(self, name, item)
        if len(self.draw_key) != 64 or any(char not in "0123456789abcdefABCDEF" for char in self.draw_key):
            raise ValueError("draw_key must be a SHA-256 digest")
        expected = _dataset_digest(self._record_without_hash())
        if self.service_record_hash is None:
            object.__setattr__(self, "service_record_hash", expected)
        elif self.service_record_hash != expected:
            raise ValueError("service_record_hash does not match canonical service record")

    def _record_without_hash(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "scenario_index": self.scenario_index,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "truck_id": self.truck_id,
            "operation": self.operation,
            "duration_min": self.duration_min,
            "source_a": self.source_a,
            "source_mode": self.source_mode,
            "source_b": self.source_b,
            "draw_key": self.draw_key,
            "crn_version": self.crn_version,
            "generation_attempt": self.generation_attempt,
        }

    @property
    def distribution(self) -> tuple[float, float, float]:
        return (self.source_a, self.source_mode, self.source_b)

    def to_dict(self) -> dict[str, Any]:
        result = self._record_without_hash()
        result.pop("generation_attempt", None)
        result["service_record_hash"] = self.service_record_hash
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenServiceTime":
        if not isinstance(value, Mapping):
            raise TypeError("frozen service time must be a mapping")
        required = {
            "instance_id", "scenario_index", "scenario_id", "seed", "truck_id", "operation",
            "duration_min", "source_a", "source_mode", "source_b", "draw_key", "crn_version",
            "service_record_hash",
        }
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"frozen service time missing required fields: {', '.join(missing)}")
        unexpected = sorted(set(value) - required - {"generation_attempt"})
        if unexpected:
            raise ValueError(f"frozen service time has unexpected fields: {', '.join(unexpected)}")
        return cls(
            instance_id=value["instance_id"],
            scenario_index=value["scenario_index"],
            scenario_id=value["scenario_id"],
            seed=value["seed"],
            truck_id=value["truck_id"],
            operation=value["operation"],
            duration_min=value["duration_min"],
            source_a=value["source_a"],
            source_mode=value["source_mode"],
            source_b=value["source_b"],
            draw_key=value["draw_key"],
            crn_version=value["crn_version"],
            generation_attempt=value.get("generation_attempt", 0),
            service_record_hash=value["service_record_hash"],
        )


@dataclass(frozen=True, slots=True)
class FrozenInstance:
    """Immutable, fully materialized stochastic input for one day."""

    instance_id: str
    scenario_index: int
    scenario_id: str
    seed: int
    generation_attempt: int
    trucks: tuple[FrozenTruck, ...]
    resources: tuple[FrozenResource, ...]
    service_times: tuple[FrozenServiceTime, ...]
    disruptions: tuple[Mapping[str, Any], ...] = ()
    canonical_record_hash: str | None = None
    instance_hash: str | None = None

    def __post_init__(self) -> None:
        for name in ("instance_id", "scenario_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        for name in ("scenario_index", "seed", "generation_attempt"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        trucks = tuple(self.trucks)
        resources = tuple(self.resources)
        service_times = tuple(self.service_times)
        if any(not isinstance(item, FrozenTruck) for item in trucks):
            raise TypeError("trucks must contain FrozenTruck values")
        if any(not isinstance(item, FrozenResource) for item in resources):
            raise TypeError("resources must contain FrozenResource values")
        if any(not isinstance(item, FrozenServiceTime) for item in service_times):
            raise TypeError("service_times must contain FrozenServiceTime values")
        if any(item.instance_id != self.instance_id for item in trucks + service_times):
            raise ValueError("instance records must use the same instance_id")
        if any(item.scenario_index != self.scenario_index or item.seed != self.seed for item in trucks):
            raise ValueError("truck records must match instance scenario and seed")
        if any(
            item.scenario_index != self.scenario_index
            or item.seed != self.seed
            or item.scenario_id != self.scenario_id
            for item in service_times
        ):
            raise ValueError("service records must match instance scenario, ID and seed")
        if any(item.generation_attempt != self.generation_attempt for item in trucks + service_times):
            raise ValueError("instance generation_attempt must match child records")
        truck_ids = [item.truck_id for item in trucks]
        if len(set(truck_ids)) != len(truck_ids):
            raise ValueError("instance truck IDs must be unique")
        trucks = tuple(sorted(trucks, key=lambda item: (item.arrival_minute, item.truck_id)))
        truck_order = {item.truck_id: index for index, item in enumerate(trucks)}
        operation_order = {name: index for index, name in enumerate(("gate", "scale_in", "unload", "scale_out"))}
        service_keys = [(item.truck_id, item.operation) for item in service_times]
        if len(set(service_keys)) != len(service_keys):
            raise ValueError("instance service operations must be unique per truck")
        service_times = tuple(
            sorted(
                service_times,
                key=lambda item: (truck_order.get(item.truck_id, len(trucks)), operation_order.get(item.operation, len(operation_order)), item.truck_id),
            )
        )
        object.__setattr__(self, "trucks", trucks)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "service_times", service_times)
        disruptions = tuple(_freeze_dataset_value(item) for item in self.disruptions)
        if any(not isinstance(item, Mapping) for item in disruptions):
            raise TypeError("disruptions must contain mappings")
        object.__setattr__(self, "disruptions", disruptions)
        expected = _dataset_digest(self._record_without_hash())
        if self.canonical_record_hash is None:
            object.__setattr__(self, "canonical_record_hash", expected)
        elif self.canonical_record_hash != expected:
            raise ValueError("canonical_record_hash does not match instance records")
        if self.instance_hash is None:
            object.__setattr__(self, "instance_hash", expected)
        elif self.instance_hash != expected:
            raise ValueError("instance_hash does not match canonical instance records")

    @property
    def scenario(self) -> Any:
        """Expose a lightweight scenario-like object for downstream consumers."""

        return self.scenario_id

    @property
    def truck_count(self) -> int:
        return len(self.trucks)

    def _record_without_hash(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "scenario_index": self.scenario_index,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "generation_attempt": self.generation_attempt,
            "trucks": [item._record_without_hash() for item in self.trucks],
            "resources": [item.to_dict() for item in self.resources],
            "service_times": [item._record_without_hash() for item in self.service_times],
            "disruptions": [_thaw_dataset_value(item) for item in self.disruptions],
        }

    def canonical_dict(self) -> dict[str, Any]:
        # Keep the instance-level canonical record independent from the
        # persisted child-record hashes, while still making ``to_dict`` a
        # lossless round-trip representation.  The generation attempt is an
        # internal provenance field (not a payload column), so include it here
        # explicitly alongside each child's persisted hash.
        result = self._record_without_hash()
        result["trucks"] = [
            {**item.to_dict(), "generation_attempt": item.generation_attempt}
            for item in self.trucks
        ]
        result["service_times"] = [
            {**item.to_dict(), "generation_attempt": item.generation_attempt}
            for item in self.service_times
        ]
        result["canonical_record_hash"] = self.canonical_record_hash
        result["instance_hash"] = self.instance_hash
        return result

    def to_dict(self) -> dict[str, Any]:
        return self.canonical_dict()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenInstance":
        if not isinstance(value, Mapping):
            raise TypeError("frozen instance must be a mapping")
        required = {
            "instance_id", "scenario_index", "scenario_id", "seed", "generation_attempt",
            "trucks", "resources", "service_times", "disruptions",
        }
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"frozen instance missing required fields: {', '.join(missing)}")
        return cls(
            instance_id=value["instance_id"],
            scenario_index=value["scenario_index"],
            scenario_id=value["scenario_id"],
            seed=value["seed"],
            generation_attempt=value["generation_attempt"],
            trucks=tuple(FrozenTruck.from_dict(item) for item in value["trucks"]),
            resources=tuple(
                FrozenResource(
                    resource_id=item["resource_id"],
                    kind=item["kind"],
                    allowed_cargo_types=item["allowed_cargo_types"],
                    status=item.get("status", "available"),
                )
                for item in value["resources"]
            ),
            service_times=tuple(
                FrozenServiceTime.from_dict(item)
                for item in value["service_times"]
            ),
            disruptions=tuple(value["disruptions"]),
            canonical_record_hash=value.get("canonical_record_hash"),
            instance_hash=value.get("instance_hash"),
        )


@dataclass(frozen=True, slots=True)
class FrozenDataset:
    """Immutable view of a validated, persisted frozen dataset."""

    path: Path
    manifest: Mapping[str, Any]
    instances: tuple[FrozenInstance, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "manifest", _freeze_dataset_value(self.manifest))
        instances = tuple(self.instances)
        if any(not isinstance(item, FrozenInstance) for item in instances):
            raise TypeError("instances must contain FrozenInstance values")
        ids = [item.instance_id for item in instances]
        if len(set(ids)) != len(ids):
            raise ValueError("dataset instance IDs must be unique")
        object.__setattr__(self, "instances", instances)

    @property
    def dataset_id(self) -> str:
        return str(self.manifest.get("dataset_id", self.path.name))

    @property
    def dataset_hash(self) -> str:
        # The root hash lives in FREEZE.json rather than manifest.json: adding
        # it to the manifest would make the manifest hash self-referential.
        freeze_path = self.path / "FREEZE.json"
        try:
            freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeError) as exc:
            raise ValueError(f"frozen dataset FREEZE.json is unavailable: {freeze_path}") from exc
        value = freeze.get("dataset_root_hash") if isinstance(freeze, Mapping) else None
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError("frozen dataset FREEZE.json lacks dataset_root_hash")
        return value

    @property
    def frozen(self) -> bool:
        return self.manifest.get("freeze_status") == "FROZEN"

    @property
    def instance_ids(self) -> tuple[str, ...]:
        return tuple(item.instance_id for item in self.instances)

    def instance(self, instance_id: str) -> FrozenInstance:
        for item in self.instances:
            if item.instance_id == instance_id:
                return item
        raise KeyError(f"unknown frozen instance: {instance_id}")

    def __len__(self) -> int:
        return len(self.instances)
