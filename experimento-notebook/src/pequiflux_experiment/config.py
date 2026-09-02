"""Validation and canonical serialization of the frozen experiment design."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    """One point in the confirmatory factorial design."""

    truck_count: int
    hopper_count: int
    scale_count: int
    regime: str

    def __post_init__(self) -> None:
        if not _is_integer(self.truck_count) or self.truck_count <= 0:
            raise ValueError("truck_count must be a positive integer")
        if not _is_integer(self.hopper_count) or self.hopper_count <= 0:
            raise ValueError("hopper_count must be a positive integer")
        if not _is_integer(self.scale_count) or self.scale_count <= 0:
            raise ValueError("scale_count must be a positive integer")
        if not isinstance(self.regime, str) or not self.regime:
            raise ValueError("regime must be a non-empty string")

    @property
    def scenario_id(self) -> str:
        """Stable human-readable identifier for persistence boundaries."""

        return (
            f"trucks_{self.truck_count}__hoppers_{self.hopper_count}"
            f"__scales_{self.scale_count}__regime_{self.regime}"
        )

    @property
    def hoppers(self) -> int:
        """Alias used by the small-scenario helpers in later tasks."""

        return self.hopper_count

    @property
    def scales(self) -> int:
        """Alias used by the small-scenario helpers in later tasks."""

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

    def __post_init__(self) -> None:
        for name in ("project_name", "protocol_version", "hypothesis"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")

        for name in _INTEGER_SEQUENCE_FIELDS:
            values = _as_positive_integer_tuple(name, getattr(self, name))
            object.__setattr__(self, name, values)

        seeds = self.seeds
        if any(previous >= current for previous, current in zip(seeds, seeds[1:])):
            raise ValueError("seeds must be strictly increasing")

        for name in ("horizon_minutes", "ordinary_window", "minimum_throughput_margin"):
            value = getattr(self, name)
            if not _is_integer(value) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

        if isinstance(self.throughput_margin_rate, bool) or not isinstance(
            self.throughput_margin_rate, (int, float)
        ):
            raise TypeError("throughput_margin_rate must be numeric")
        margin_rate = float(self.throughput_margin_rate)
        if not math.isfinite(margin_rate) or margin_rate < 0:
            raise ValueError("throughput_margin_rate must be finite and non-negative")
        object.__setattr__(self, "throughput_margin_rate", margin_rate)

        regimes = _as_text_tuple("regimes", self.regimes)
        if len(set(regimes)) != len(regimes):
            raise ValueError("regimes must be unique")
        object.__setattr__(self, "regimes", regimes)

        policies = _as_text_tuple("policies", self.policies)
        if policies != POLICY_NAMES:
            expected = ", ".join(POLICY_NAMES)
            raise ValueError(f"policy panel must be exactly: {expected}")
        object.__setattr__(self, "policies", policies)

        factorial_product = (
            len(self.truck_counts)
            * len(self.hopper_counts)
            * len(self.scale_counts)
            * len(self.regimes)
        )
        if factorial_product != 72:
            raise ValueError(f"factorial product must be 72 (got {factorial_product})")

    @property
    def factorial_size(self) -> int:
        return (
            len(self.truck_counts)
            * len(self.hopper_counts)
            * len(self.scale_counts)
            * len(self.regimes)
        )


# One immutable source of truth for the confirmatory protocol.  Validation and
# execution boundaries consume this representation instead of inferring a
# protocol from a checksum or from the current working directory.
CANONICAL_CONFIRMATORY_FIELDS: Mapping[str, Any] = MappingProxyType(
    {
        "project_name": "PequiFlux - Experimento Reprodutivel",
        "protocol_version": "1.0.0",
        "hypothesis": "H1",
        "seeds": tuple(range(101, 151)),
        "horizon_minutes": 720,
        "ordinary_window": 6,
        "priority_thresholds": (60, 30, 10),
        "throughput_margin_rate": 0.02,
        "minimum_throughput_margin": 2,
        "truck_counts": (60, 120, 180),
        "hopper_counts": (1, 2, 3),
        "scale_counts": (1, 2),
        "regimes": ("nominal", "peak", "critical_failure", "priority_shift"),
        "policies": POLICY_NAMES,
    }
)


def validate_confirmatory_config(config: ExperimentConfig) -> ExperimentConfig:
    """Require exact equality with every frozen field in ``confirmatory.json``."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    for field_name, expected in CANONICAL_CONFIRMATORY_FIELDS.items():
        observed = getattr(config, field_name)
        if isinstance(expected, tuple):
            observed = tuple(observed)
        if observed != expected:
            raise ValueError(
                "canonical confirmatory configuration mismatch for "
                f"{field_name}: expected={expected!r} observed={observed!r}"
            )
    return config


def load_config(path: str | Path) -> ExperimentConfig:
    """Load and validate a JSON configuration from a local path."""

    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON configuration: {exc.msg}") from exc

    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a JSON object")

    expected_keys = set(CONFIG_KEYS)
    actual_keys = set(raw)
    unknown_keys = sorted(actual_keys - expected_keys)
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ValueError(f"unknown configuration keys: {joined}")

    missing_keys = [key for key in CONFIG_KEYS if key not in raw]
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise ValueError(f"missing configuration keys: {joined}")

    return ExperimentConfig(**raw)


def factorial_scenarios(config: ExperimentConfig) -> tuple[ScenarioConfig, ...]:
    """Enumerate the complete factorial in configuration order."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    return tuple(
        ScenarioConfig(
            truck_count=truck_count,
            hopper_count=hopper_count,
            scale_count=scale_count,
            regime=regime,
        )
        for truck_count in config.truck_counts
        for hopper_count in config.hopper_counts
        for scale_count in config.scale_counts
        for regime in config.regimes
    )


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
    }


def canonical_json(config: ExperimentConfig) -> str:
    """Serialize configuration with stable key ordering and compact separators."""

    return json.dumps(
        config_as_dict(config),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def config_hash(config: ExperimentConfig) -> str:
    """Return the SHA-256 digest of the canonical UTF-8 configuration JSON."""

    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()
