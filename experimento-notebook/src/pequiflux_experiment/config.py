"""Validation and canonical serialization of the frozen experiment design."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


POLICY_NAMES: tuple[str, ...] = (
    "fifo_strict",
    "fifo_flow_faithful",
    "priority_local",
    "fixed_score",
    "lexicographic",
)

_REGIMES: tuple[str, ...] = (
    "nominal",
    "peak",
    "critical_failure",
    "priority_shift",
)
_SEEDS: tuple[int, ...] = tuple(range(101, 151))
_TRUCK_COUNTS: tuple[int, ...] = (60, 120, 180)
_HOPPER_COUNTS: tuple[int, ...] = (1, 2, 3)
_SCALE_COUNTS: tuple[int, ...] = (1, 2)
_PRIORITY_THRESHOLDS: tuple[int, ...] = (60, 30, 10)
_SERVICE_DISTRIBUTIONS: dict[str, tuple[float, float, float]] = {
    "gate": (2.0, 4.0, 7.0),
    "scale_in": (3.0, 5.0, 8.0),
    "unload": (12.0, 20.0, 35.0),
    "scale_out": (3.0, 5.0, 8.0),
}
_ARRIVAL_BLOCKS: tuple[tuple[int, int, float], ...] = (
    (0, 180, 6.0),
    (180, 300, 3.0),
    (300, 480, 7.0),
    (480, 720, 2.0),
)
_PEAK_ARRIVAL_WEIGHTS: tuple[float, ...] = (9.0, 2.0, 10.0, 2.0)
_PRIORITY_PROBABILITIES: dict[str, float] = {
    "p2": 0.15,
    "p1": 0.20,
    "p0": 0.65,
}
_EVENT_RANKS: dict[str, int] = {
    "service_completion": 0,
    "resource_recovery": 10,
    "rain_end": 11,
    "resource_failure": 12,
    "rain_start": 13,
    "document_release": 20,
    "priority_change": 21,
    "arrival": 30,
}

CONFIG_KEYS: tuple[str, ...] = (
    "project_name",
    "protocol_version",
    "hypothesis",
    "seeds",
    "horizon_minutes",
    "ordinary_window",
    "priority_thresholds",
    "throughput_margin_rate",
    "minimum_throughput_margin",
    "truck_counts",
    "hopper_counts",
    "scale_counts",
    "regimes",
    "policies",
    "capacity",
    "crn_version",
    "buffer_capacity",
    "service_distributions",
    "arrival_blocks",
    "peak_arrival_weights",
    "priority_probabilities",
    "document_block_probability",
    "document_release_distribution",
    "base_failure_probability",
    "failure_start_window",
    "failure_duration_distribution",
    "priority_shift_fraction",
    "priority_shift_window",
    "rain_probability",
    "rain_block_minutes",
    "event_ranks",
)

_INTEGER_SEQUENCE_FIELDS = (
    "seeds",
    "priority_thresholds",
    "truck_counts",
    "hopper_counts",
    "scale_counts",
)


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_tuple(name: str, value: Iterable[Any]) -> tuple[Any, ...]:
    if isinstance(value, Mapping) or isinstance(value, (str, bytes, bytearray)) or value is None:
        raise TypeError(f"{name} must be a sequence")
    try:
        result = tuple(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be a sequence") from exc
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _as_positive_integer_tuple(name: str, value: Iterable[Any]) -> tuple[int, ...]:
    result = _as_tuple(name, value)
    if any(not _is_integer(item) or item <= 0 for item in result):
        raise ValueError(f"{name} must contain positive integers")
    return result


def _as_text_tuple(name: str, value: Iterable[Any]) -> tuple[str, ...]:
    result = _as_tuple(name, value)
    if any(not isinstance(item, str) or not item for item in result):
        raise ValueError(f"{name} must contain non-empty strings")
    return result


def _as_finite_number(name: str, value: object, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return number


def _as_probability(name: str, value: object) -> float:
    number = _as_finite_number(name, value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _freeze_mapping(name: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return MappingProxyType(dict(value))


def _normalise_triplet(name: str, value: Iterable[Any]) -> tuple[float, float, float]:
    values = _as_tuple(name, value)
    if len(values) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    result = tuple(_as_finite_number(f"{name}[{index}]", item, minimum=0.0) for index, item in enumerate(values))
    if not result[0] <= result[1] <= result[2]:
        raise ValueError(f"{name} must be non-decreasing")
    return result


def _normalise_window(name: str, value: Iterable[Any]) -> tuple[int, int]:
    values = _as_tuple(name, value)
    if len(values) != 2 or any(not _is_integer(item) for item in values):
        raise ValueError(f"{name} must contain two integer endpoints")
    start, end = values
    if start < 0 or end < start:
        raise ValueError(f"{name} must be an ordered non-negative window")
    return (start, end)


def _normalise_service_distributions(value: Mapping[str, Any]) -> Mapping[str, tuple[float, float, float]]:
    if not isinstance(value, Mapping):
        raise TypeError("service_distributions must be an object")
    if set(value) != set(_SERVICE_DISTRIBUTIONS):
        raise ValueError("service_distributions must define gate, scale_in, unload, and scale_out")
    return MappingProxyType(
        {name: _normalise_triplet(f"service_distributions.{name}", value[name]) for name in _SERVICE_DISTRIBUTIONS}
    )


def _normalise_arrival_blocks(value: Iterable[Any], horizon_minutes: int) -> tuple[tuple[int, int, float], ...]:
    blocks = _as_tuple("arrival_blocks", value)
    if len(blocks) != 4:
        raise ValueError("arrival_blocks must contain exactly four blocks")
    result: list[tuple[int, int, float]] = []
    expected_start = 0
    for index, block in enumerate(blocks):
        if not isinstance(block, Mapping):
            raise TypeError(f"arrival_blocks[{index}] must be an object")
        if set(block) != {"start_minute", "end_minute", "weight"}:
            raise ValueError("arrival block keys must be start_minute, end_minute, and weight")
        start, end = block["start_minute"], block["end_minute"]
        if not _is_integer(start) or not _is_integer(end) or start != expected_start or end <= start:
            raise ValueError("arrival blocks must be contiguous, ordered integer intervals")
        weight = _as_finite_number(f"arrival_blocks[{index}].weight", block["weight"], minimum=0.0)
        result.append((start, end, weight))
        expected_start = end
    if expected_start != horizon_minutes:
        raise ValueError("arrival blocks must cover the complete horizon")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class CapacityRequirements:
    """Fail-fast resource contract for local experiment execution."""

    min_free_ram_gib: int
    reserve_ram_gib: int
    max_workers: int
    receipt_ttl_seconds: int
    disk_margin: float = 1.25
    disk_reserve_gib: int = 5
    provider: str = "cpu"
    cpu_only: bool = True

    def __post_init__(self) -> None:
        for name in ("min_free_ram_gib", "reserve_ram_gib", "max_workers", "receipt_ttl_seconds", "disk_reserve_gib"):
            value = getattr(self, name)
            if not _is_integer(value) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.reserve_ram_gib >= self.min_free_ram_gib:
            raise ValueError("reserve_ram_gib must be lower than min_free_ram_gib")
        margin = _as_finite_number("disk_margin", self.disk_margin, minimum=1.0)
        object.__setattr__(self, "disk_margin", margin)
        if self.provider != "cpu":
            raise ValueError("provider must be cpu")
        if self.cpu_only is not True:
            raise ValueError("cpu_only must be true")

    @property
    def provider_requirement(self) -> str:
        return "cpu-only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_free_ram_gib": self.min_free_ram_gib,
            "reserve_ram_gib": self.reserve_ram_gib,
            "max_workers": self.max_workers,
            "receipt_ttl_seconds": self.receipt_ttl_seconds,
            "disk_margin": self.disk_margin,
            "disk_reserve_gib": self.disk_reserve_gib,
            "provider": self.provider,
            "cpu_only": self.cpu_only,
        }


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    """One point in the confirmatory factorial design."""

    truck_count: int
    hopper_count: int
    scale_count: int
    regime: str
    scenario_index: int = 0

    def __post_init__(self) -> None:
        for name in ("truck_count", "hopper_count", "scale_count"):
            value = getattr(self, name)
            if not _is_integer(value) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.regime, str) or not self.regime:
            raise ValueError("regime must be a non-empty string")
        if not _is_integer(self.scenario_index) or not 0 <= self.scenario_index < 72:
            raise ValueError("scenario_index must be in [0, 71]")

    @property
    def N(self) -> int:
        return self.truck_count

    @property
    def m(self) -> int:
        return self.hopper_count

    @property
    def b(self) -> int:
        return self.scale_count

    @property
    def scenario_id(self) -> str:
        return f"n{self.N}-m{self.m}-b{self.b}-{self.regime}"

    @property
    def rho(self) -> float:
        return self.N / min(36 * self.m, 72 * self.b)

    @property
    def stratum(self) -> str:
        if self.rho < 0.70:
            return "low"
        if self.rho < 0.85:
            return "medium"
        return "high"

    @property
    def hoppers(self) -> int:
        return self.hopper_count

    @property
    def scales(self) -> int:
        return self.scale_count


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """The complete, immutable protocol configuration."""

    project_name: str
    protocol_version: str
    hypothesis: str
    seeds: tuple[int, ...]
    horizon_minutes: int
    ordinary_window: int
    priority_thresholds: tuple[int, ...]
    throughput_margin_rate: float
    minimum_throughput_margin: int
    truck_counts: tuple[int, ...]
    hopper_counts: tuple[int, ...]
    scale_counts: tuple[int, ...]
    regimes: tuple[str, ...]
    policies: tuple[str, ...]
    capacity: CapacityRequirements | Mapping[str, Any] = CapacityRequirements(4, 2, 4, 60)
    crn_version: str = "crn.v1"
    buffer_capacity: int = 12
    service_distributions: Mapping[str, Any] = field(default_factory=lambda: dict(_SERVICE_DISTRIBUTIONS))
    arrival_blocks: Iterable[Any] = _ARRIVAL_BLOCKS
    peak_arrival_weights: tuple[float, ...] = _PEAK_ARRIVAL_WEIGHTS
    priority_probabilities: Mapping[str, Any] = field(default_factory=lambda: dict(_PRIORITY_PROBABILITIES))
    document_block_probability: float = 0.03
    document_release_distribution: tuple[float, ...] = (30.0, 60.0, 120.0)
    base_failure_probability: float = 0.05
    failure_start_window: tuple[int, int] = (240, 480)
    failure_duration_distribution: tuple[float, ...] = (20.0, 40.0, 70.0)
    priority_shift_fraction: float = 0.10
    priority_shift_window: tuple[int, int] = (240, 480)
    rain_probability: float = 0.10
    rain_block_minutes: int = 30
    event_ranks: Mapping[str, Any] = field(default_factory=lambda: dict(_EVENT_RANKS))

    def __post_init__(self) -> None:
        for name in ("project_name", "protocol_version", "hypothesis", "crn_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")

        for name in _INTEGER_SEQUENCE_FIELDS:
            object.__setattr__(self, name, _as_positive_integer_tuple(name, getattr(self, name)))
        if any(previous >= current for previous, current in zip(self.seeds, self.seeds[1:])):
            raise ValueError("seeds must be strictly increasing")

        for name in ("horizon_minutes", "ordinary_window", "minimum_throughput_margin", "buffer_capacity", "rain_block_minutes"):
            value = getattr(self, name)
            if not _is_integer(value) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        object.__setattr__(self, "throughput_margin_rate", _as_probability("throughput_margin_rate", self.throughput_margin_rate))

        thresholds = _as_positive_integer_tuple("priority_thresholds", self.priority_thresholds)
        if len(thresholds) != 3 or thresholds != (60, 30, 10):
            raise ValueError("priority_thresholds must be (60, 30, 10)")
        object.__setattr__(self, "priority_thresholds", thresholds)

        regimes = _as_text_tuple("regimes", self.regimes)
        if regimes != _REGIMES:
            raise ValueError("regimes must be nominal, peak, critical_failure, priority_shift in order")
        object.__setattr__(self, "regimes", regimes)

        policies = _as_text_tuple("policies", self.policies)
        if policies != POLICY_NAMES:
            expected = ", ".join(POLICY_NAMES)
            raise ValueError(f"policy panel must be exactly: {expected}")
        object.__setattr__(self, "policies", policies)
        if self.factorial_size != 72:
            raise ValueError(f"factorial product must be 72 (got {self.factorial_size})")

        if isinstance(self.capacity, CapacityRequirements):
            capacity = self.capacity
        elif isinstance(self.capacity, Mapping):
            capacity = CapacityRequirements(**dict(self.capacity))
        else:
            raise TypeError("capacity must be CapacityRequirements or an object")
        object.__setattr__(self, "capacity", capacity)

        service = _normalise_service_distributions(self.service_distributions)
        object.__setattr__(self, "service_distributions", service)
        arrival = _normalise_arrival_blocks(self.arrival_blocks, self.horizon_minutes)
        object.__setattr__(self, "arrival_blocks", arrival)
        peak = _as_tuple("peak_arrival_weights", self.peak_arrival_weights)
        if len(peak) != len(arrival):
            raise ValueError("peak_arrival_weights must match arrival_blocks")
        object.__setattr__(self, "peak_arrival_weights", tuple(_as_finite_number(f"peak_arrival_weights[{i}]", v, minimum=0.0) for i, v in enumerate(peak)))

        priorities = _freeze_mapping("priority_probabilities", self.priority_probabilities)
        if set(priorities) != {"p2", "p1", "p0"}:
            raise ValueError("priority_probabilities must define p2, p1, and p0")
        priorities = MappingProxyType({key: _as_probability(f"priority_probabilities.{key}", value) for key, value in priorities.items()})
        if not math.isclose(sum(priorities.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("priority_probabilities must sum to one")
        object.__setattr__(self, "priority_probabilities", priorities)

        for name in ("document_block_probability", "base_failure_probability", "priority_shift_fraction", "rain_probability"):
            object.__setattr__(self, name, _as_probability(name, getattr(self, name)))
        object.__setattr__(self, "document_release_distribution", _normalise_triplet("document_release_distribution", self.document_release_distribution))
        object.__setattr__(self, "failure_duration_distribution", _normalise_triplet("failure_duration_distribution", self.failure_duration_distribution))
        object.__setattr__(self, "failure_start_window", _normalise_window("failure_start_window", self.failure_start_window))
        object.__setattr__(self, "priority_shift_window", _normalise_window("priority_shift_window", self.priority_shift_window))

        ranks = _freeze_mapping("event_ranks", self.event_ranks)
        if set(ranks) != set(_EVENT_RANKS):
            raise ValueError("event_ranks must define all canonical event types")
        if any(not _is_integer(value) or value < 0 for value in ranks.values()):
            raise ValueError("event_ranks values must be non-negative integers")
        object.__setattr__(self, "event_ranks", MappingProxyType(dict(ranks)))

    @property
    def factorial_size(self) -> int:
        return len(self.truck_counts) * len(self.hopper_counts) * len(self.scale_counts) * len(self.regimes)

    @property
    def N_levels(self) -> tuple[int, ...]:
        return self.truck_counts

    @property
    def m_levels(self) -> tuple[int, ...]:
        return self.hopper_counts

    @property
    def b_levels(self) -> tuple[int, ...]:
        return self.scale_counts

    @property
    def H0(self) -> int:
        return self.ordinary_window

    @property
    def tau2(self) -> int:
        return self.priority_thresholds[2]

    @property
    def tau1(self) -> int:
        return self.priority_thresholds[1]

    @property
    def tau0(self) -> int:
        return self.priority_thresholds[0]

    @property
    def service_times(self) -> Mapping[str, tuple[float, float, float]]:
        return self.service_distributions

    @property
    def arrival_weight_profiles(self) -> Mapping[str, tuple[float, ...]]:
        return MappingProxyType({"nominal": tuple(block[2] for block in self.arrival_blocks), "peak": self.peak_arrival_weights})

    @property
    def throughput_margin(self) -> float:
        return self.throughput_margin_rate


def _canonical_nested_fields() -> dict[str, Any]:
    return {
        "capacity": CapacityRequirements(4, 2, 4, 60).as_dict(),
        "crn_version": "crn.v1",
        "buffer_capacity": 12,
        "service_distributions": {name: list(values) for name, values in _SERVICE_DISTRIBUTIONS.items()},
        "arrival_blocks": [
            {"start_minute": start, "end_minute": end, "weight": weight}
            for start, end, weight in _ARRIVAL_BLOCKS
        ],
        "peak_arrival_weights": list(_PEAK_ARRIVAL_WEIGHTS),
        "priority_probabilities": dict(_PRIORITY_PROBABILITIES),
        "document_block_probability": 0.03,
        "document_release_distribution": [30.0, 60.0, 120.0],
        "base_failure_probability": 0.05,
        "failure_start_window": [240, 480],
        "failure_duration_distribution": [20.0, 40.0, 70.0],
        "priority_shift_fraction": 0.10,
        "priority_shift_window": [240, 480],
        "rain_probability": 0.10,
        "rain_block_minutes": 30,
        "event_ranks": dict(_EVENT_RANKS),
    }


CANONICAL_CONFIRMATORY_FIELDS: Mapping[str, Any] = MappingProxyType(
    {
        "project_name": "PequiFlux - Experimento Reprodutivel",
        "protocol_version": "1.0.0",
        "hypothesis": "H1",
        "seeds": _SEEDS,
        "horizon_minutes": 720,
        "ordinary_window": 6,
        "priority_thresholds": _PRIORITY_THRESHOLDS,
        "throughput_margin_rate": 0.02,
        "minimum_throughput_margin": 2,
        "truck_counts": _TRUCK_COUNTS,
        "hopper_counts": _HOPPER_COUNTS,
        "scale_counts": _SCALE_COUNTS,
        "regimes": _REGIMES,
        "policies": POLICY_NAMES,
        **_canonical_nested_fields(),
    }
)


def validate_confirmatory_config(config: ExperimentConfig) -> ExperimentConfig:
    """Require exact equality with every frozen field in confirmatory.json."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    observed = config_as_dict(config)
    expected = {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in CANONICAL_CONFIRMATORY_FIELDS.items()
    }
    if observed != expected:
        for field_name in CONFIG_KEYS:
            if observed.get(field_name) != expected.get(field_name):
                raise ValueError(
                    "canonical confirmatory configuration mismatch for "
                    f"{field_name}: expected={expected.get(field_name)!r} observed={observed.get(field_name)!r}"
                )
        raise ValueError("canonical confirmatory configuration mismatch")
    scenarios = factorial_scenarios(config)
    if len(scenarios) != 72 or [scenario.scenario_index for scenario in scenarios] != list(range(72)):
        raise ValueError("factorial scenarios must contain canonical indices 0 through 71")
    return config


def load_config(path: str | Path) -> ExperimentConfig:
    """Load and validate a JSON configuration from a local path."""

    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"configuration file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON configuration: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a JSON object")
    expected_keys = set(CONFIG_KEYS)
    unknown_keys = sorted(set(raw) - expected_keys)
    if unknown_keys:
        raise ValueError(f"unknown configuration keys: {', '.join(unknown_keys)}")
    missing_keys = [key for key in CONFIG_KEYS if key not in raw]
    if missing_keys:
        raise ValueError(f"missing configuration keys: {', '.join(missing_keys)}")
    return validate_confirmatory_config(ExperimentConfig(**raw))


def factorial_scenarios(config: ExperimentConfig) -> tuple[ScenarioConfig, ...]:
    """Enumerate the complete factorial in N, m, b, regime order."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    scenarios: list[ScenarioConfig] = []
    for truck_count in config.truck_counts:
        for hopper_count in config.hopper_counts:
            for scale_count in config.scale_counts:
                for regime in config.regimes:
                    scenarios.append(
                        ScenarioConfig(
                            truck_count=truck_count,
                            hopper_count=hopper_count,
                            scale_count=scale_count,
                            regime=regime,
                            scenario_index=len(scenarios),
                        )
                    )
    return tuple(scenarios)


def config_as_dict(config: ExperimentConfig) -> dict[str, Any]:
    """Return the validated configuration in its JSON-compatible shape."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    return {
        "project_name": config.project_name,
        "protocol_version": config.protocol_version,
        "hypothesis": config.hypothesis,
        "seeds": list(config.seeds),
        "horizon_minutes": config.horizon_minutes,
        "ordinary_window": config.ordinary_window,
        "priority_thresholds": list(config.priority_thresholds),
        "throughput_margin_rate": config.throughput_margin_rate,
        "minimum_throughput_margin": config.minimum_throughput_margin,
        "truck_counts": list(config.truck_counts),
        "hopper_counts": list(config.hopper_counts),
        "scale_counts": list(config.scale_counts),
        "regimes": list(config.regimes),
        "policies": list(config.policies),
        "capacity": config.capacity.as_dict(),
        "crn_version": config.crn_version,
        "buffer_capacity": config.buffer_capacity,
        "service_distributions": {name: list(values) for name, values in config.service_distributions.items()},
        "arrival_blocks": [
            {"start_minute": start, "end_minute": end, "weight": weight}
            for start, end, weight in config.arrival_blocks
        ],
        "peak_arrival_weights": list(config.peak_arrival_weights),
        "priority_probabilities": dict(config.priority_probabilities),
        "document_block_probability": config.document_block_probability,
        "document_release_distribution": list(config.document_release_distribution),
        "base_failure_probability": config.base_failure_probability,
        "failure_start_window": list(config.failure_start_window),
        "failure_duration_distribution": list(config.failure_duration_distribution),
        "priority_shift_fraction": config.priority_shift_fraction,
        "priority_shift_window": list(config.priority_shift_window),
        "rain_probability": config.rain_probability,
        "rain_block_minutes": config.rain_block_minutes,
        "event_ranks": dict(config.event_ranks),
    }


def canonical_json(config: ExperimentConfig) -> str:
    """Serialize configuration with stable key ordering and compact separators."""

    return json.dumps(
        config_as_dict(config),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + chr(10)


def canonical_bytes(value: Any) -> bytes:
    """Serialize any JSON-compatible value in the canonical byte representation."""

    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        + bytes((10,))
    )


def crn_key(
    crn_version: str,
    scenario_index: int,
    seed: int,
    generation_attempt: int,
    entity_id: str,
    operation_or_event: str,
) -> tuple[str, int, int, int, str, str]:
    """Validate and return the complete policy-independent CRN key.

    The key deliberately has no policy component.  Every stochastic draw is
    therefore derived from the same tuple for all policies consuming one
    frozen instance.  ``generation_attempt`` is part of the identity so an
    explicit resample can change only the rejected instance's substreams.
    """

    if not isinstance(crn_version, str) or not crn_version.strip():
        raise ValueError("crn_version must be a non-empty string")
    for name, value in (
        ("scenario_index", scenario_index),
        ("seed", seed),
        ("generation_attempt", generation_attempt),
    ):
        if not _is_integer(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    for name, value in (("entity_id", entity_id), ("operation_or_event", operation_or_event)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    return (
        crn_version,
        int(scenario_index),
        int(seed),
        int(generation_attempt),
        entity_id,
        operation_or_event,
    )


def crn_digest(
    crn_version: str,
    scenario_index: int,
    seed: int,
    generation_attempt: int,
    entity_id: str,
    operation_or_event: str,
) -> str:
    """Return the SHA-256 digest for one canonical CRN substream key."""

    key = crn_key(
        crn_version,
        scenario_index,
        seed,
        generation_attempt,
        entity_id,
        operation_or_event,
    )
    return hashlib.sha256(canonical_bytes(list(key))).hexdigest()


def crn_seed(
    crn_version: str,
    scenario_index: int,
    seed: int,
    generation_attempt: int,
    entity_id: str,
    operation_or_event: str,
) -> int:
    """Map a CRN key to a stable non-negative integer seed."""

    return int(
        crn_digest(
            crn_version,
            scenario_index,
            seed,
            generation_attempt,
            entity_id,
            operation_or_event,
        )[:16],
        16,
    )


def config_hash(config: ExperimentConfig) -> str:
    """Return the SHA-256 digest of the canonical UTF-8 configuration JSON."""

    return hashlib.sha256(canonical_bytes(config_as_dict(config))).hexdigest()
