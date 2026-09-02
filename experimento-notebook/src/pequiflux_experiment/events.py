"""Validated event records and their JSONL persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


EVENT_KINDS: tuple[str, ...] = (
    "RUN_STARTED",
    "TRUCK_ARRIVED",
    "DOCUMENT_RELEASED",
    "PRIORITY_CHANGED",
    "RESOURCE_FAILED",
    "RESOURCE_RECOVERED",
    "SERVICE_STARTED",
    "SERVICE_COMPLETED",
    "DECISION_RECORDED",
    "OPERATOR_DECISION",
    "DISPATCH_BLOCKED",
    "END_OF_DAY",
)

# The fields are intentionally defined at the event boundary.  Event payloads
# may carry additional evidence, but omitting an identifier that is required
# to apply a transition is rejected before persistence.
REQUIRED_PAYLOAD_FIELDS: dict[str, frozenset[str]] = {
    "RUN_STARTED": frozenset(),
    "TRUCK_ARRIVED": frozenset(
        {
            "truck_id",
            "arrival_time",
            "cargo_type",
            "priority",
            "document_ok",
            "stage",
        }
    ),
    "DOCUMENT_RELEASED": frozenset({"truck_id"}),
    "PRIORITY_CHANGED": frozenset({"truck_id", "priority"}),
    "RESOURCE_FAILED": frozenset({"resource_id"}),
    "RESOURCE_RECOVERED": frozenset({"resource_id"}),
    "SERVICE_STARTED": frozenset({"truck_id", "resource_id", "operation"}),
    "SERVICE_COMPLETED": frozenset({"truck_id", "resource_id", "operation"}),
    "DECISION_RECORDED": frozenset({"decision"}),
    "OPERATOR_DECISION": frozenset({"decision"}),
    "DISPATCH_BLOCKED": frozenset({"resource_id", "operation", "candidate_ids", "reasons"}),
    "END_OF_DAY": frozenset(),
}


def _canonicalize(value: Any) -> Any:
    """Normalize JSON values into detached dict/list/scalar containers."""

    if isinstance(value, Mapping):
        canonical: dict[str, Any] = {}
        keys = list(value)
        for key in keys:
            if not isinstance(key, str):
                raise TypeError("payload mapping keys must be strings")
        for key in sorted(keys):
            canonical[key] = _canonicalize(value[key])
        return canonical
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("payload must contain only finite numbers")
        return value
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"payload value is not JSON-compatible: {type(value).__name__}")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class EventRecord:
    """One ordered, validated event in the experiment trace."""

    time: float
    sequence: int
    kind: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if isinstance(self.time, bool) or not isinstance(self.time, (int, float)):
            raise TypeError("time must be numeric")
        timestamp = float(self.time)
        if not math.isfinite(timestamp):
            raise ValueError("time must be finite")
        object.__setattr__(self, "time", timestamp)

        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence must be an integer")
        if self.sequence <= 0:
            raise ValueError("sequence must be positive")

        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {self.kind!r}")

        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        payload = _canonicalize(self.payload)
        missing = sorted(REQUIRED_PAYLOAD_FIELDS[self.kind] - payload.keys())
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"payload missing required fields: {joined}")
        object.__setattr__(self, "payload", _freeze(payload))

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible representation."""

        return {
            "time": self.time,
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": _thaw(self.payload),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EventRecord":
        if not isinstance(value, Mapping):
            raise TypeError("event must be a mapping")
        required = {"time", "sequence", "kind", "payload"}
        missing = sorted(required - value.keys())
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"event missing required fields: {joined}")
        return cls(
            time=value["time"],
            sequence=value["sequence"],
            kind=value["kind"],
            payload=value["payload"],
        )


def write_jsonl(path: str | Path, events: Iterable[EventRecord]) -> None:
    """Write events as one canonical JSON object per line."""

    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    if isinstance(events, (str, bytes, bytearray)):
        raise TypeError("events must be an iterable of EventRecord")
    destination = Path(path)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            if not isinstance(event, EventRecord):
                raise TypeError("events must contain EventRecord values")
            line = json.dumps(
                event.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            handle.write(f"{line}\n")


def read_jsonl(path: str | Path) -> list[EventRecord]:
    """Read and validate every non-empty JSONL event line."""

    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    source = Path(path)
    events: list[EventRecord] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"JSONL line {line_number} is empty")
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}: {exc.msg}") from exc
            try:
                events.append(EventRecord.from_dict(raw))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid event at JSONL line {line_number}: {exc}") from exc
    return events
