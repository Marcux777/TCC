"""Strict reconstruction of one persisted decision log."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from .digital_model import DigitalModel
from .domain import YardSnapshot
from .events import EventRecord


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReplayError(ValueError):
    """Raised when a persisted log cannot be reconstructed fail-closed."""


@dataclass(frozen=True, slots=True)
class ReplayDetails:
    """Internal replay evidence retained for the independent auditor."""

    log_path: Path
    run_id: str
    scenario_id: str
    seed: int
    policy: str
    config_hash: str
    events: tuple[EventRecord, ...]
    lines: tuple[Mapping[str, Any], ...]
    initial_snapshot: YardSnapshot
    final_snapshot: YardSnapshot


def snapshot_hash(snapshot: YardSnapshot) -> str:
    """Return the canonical SHA-256 digest used in log state boundaries."""

    if not isinstance(snapshot, YardSnapshot):
        raise TypeError("snapshot must be a YardSnapshot")
    canonical = json.dumps(
        snapshot.canonical_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _required_text(raw: Mapping[str, Any], key: str, *, line_number: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ReplayError(
            f"log line {line_number} field {key!r} must be a non-empty string"
        )
    return value


def _required_sha(raw: Mapping[str, Any], key: str, *, line_number: int) -> str:
    value = _required_text(raw, key, line_number=line_number)
    if not _SHA256_RE.fullmatch(value):
        raise ReplayError(f"log line {line_number} field {key!r} is not SHA-256")
    return value


def _read_raw_lines(path: Path) -> tuple[Mapping[str, Any], ...]:
    if not path.is_file():
        raise FileNotFoundError(f"decision log does not exist: {path}")
    rows: list[Mapping[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    raise ReplayError(f"log line {line_number} is empty")
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ReplayError(
                        f"invalid JSON in decision log line {line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(value, Mapping):
                    raise ReplayError(
                        f"decision log line {line_number} must be a JSON object"
                    )
                rows.append(dict(value))
    except UnicodeDecodeError as exc:
        raise ReplayError(f"decision log is not valid UTF-8: {path}") from exc
    if not rows:
        raise ReplayError(f"decision log is empty: {path}")
    return tuple(rows)


def _replay_log(path: str | Path) -> ReplayDetails:
    if not isinstance(path, (str, Path)):
        raise TypeError("log_path must be a string or Path")
    log_path = Path(path)
    raw_lines = _read_raw_lines(log_path)

    first = raw_lines[0]
    required = {
        "run_id",
        "scenario_id",
        "seed",
        "policy",
        "config_hash",
        "event_id",
        "event_kind",
        "kind",
        "sequence",
        "time",
        "resource_id",
        "candidates",
        "excluded",
        "selection",
        "explanation",
        "human_decision",
        "state_before_hash",
        "state_after_hash",
        "payload",
    }
    missing = sorted(required - first.keys())
    if missing:
        raise ReplayError(
            f"decision log line 1 missing required fields: {', '.join(missing)}"
        )
    run_id = _required_text(first, "run_id", line_number=1)
    scenario_id = _required_text(first, "scenario_id", line_number=1)
    policy = _required_text(first, "policy", line_number=1)
    config_checksum = _required_sha(first, "config_hash", line_number=1)
    seed = first.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ReplayError("log line 1 field 'seed' must be a non-negative integer")

    events: list[EventRecord] = []
    metadata_fields = ("run_id", "scenario_id", "seed", "policy", "config_hash")
    for line_number, raw in enumerate(raw_lines, start=1):
        missing = sorted(required - raw.keys())
        if missing:
            raise ReplayError(
                f"decision log line {line_number} missing required fields: {', '.join(missing)}"
            )
        for key in metadata_fields:
            if raw.get(key) != first.get(key):
                raise ReplayError(
                    f"decision log line {line_number} field {key!r} changes within one log"
                )
        if isinstance(raw.get("seed"), bool) or not isinstance(raw.get("seed"), int):
            raise ReplayError(f"decision log line {line_number} field 'seed' is invalid")
        if not _SHA256_RE.fullmatch(str(raw.get("config_hash"))):
            raise ReplayError(f"decision log line {line_number} field 'config_hash' is invalid")
        event_kind = raw.get("event_kind")
        if raw.get("kind") != event_kind:
            raise ReplayError(f"decision log line {line_number} kind fields disagree")
        sequence = raw.get("sequence")
        event_id = raw.get("event_id")
        if not isinstance(event_kind, str) or not event_kind:
            raise ReplayError(f"decision log line {line_number} event_kind is invalid")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
            raise ReplayError(f"decision log line {line_number} sequence is invalid")
        if event_id != f"{sequence}:{event_kind}":
            raise ReplayError(f"decision log line {line_number} event_id does not match event")
        time = raw.get("time")
        if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(float(time)):
            raise ReplayError(f"decision log line {line_number} time is invalid")
        _required_sha(raw, "state_before_hash", line_number=line_number)
        _required_sha(raw, "state_after_hash", line_number=line_number)
        try:
            # The enriched log keeps ``event_kind`` as its audit-facing field;
            # adapt that explicit field to the canonical EventRecord schema.
            event = EventRecord.from_dict(
                {
                    "time": raw["time"],
                    "sequence": raw["sequence"],
                    "kind": raw["event_kind"],
                    "payload": raw["payload"],
                }
            )
        except (TypeError, ValueError) as exc:
            raise ReplayError(
                f"invalid event in decision log line {line_number}: {exc}"
            ) from exc
        if event.kind != event_kind or event.sequence != sequence:
            raise ReplayError(f"decision log line {line_number} event fields disagree")
        events.append(event)

    if events[0].kind != "RUN_STARTED":
        raise ReplayError("decision log must start with RUN_STARTED")
    first_payload = events[0].to_dict()["payload"]
    initial_raw = first_payload.get("initial_snapshot")
    if not isinstance(initial_raw, Mapping):
        raise ReplayError(
            "RUN_STARTED payload must include initial_snapshot for strict replay"
        )
    try:
        initial_snapshot = YardSnapshot.from_dict(initial_raw)
    except (TypeError, ValueError) as exc:
        raise ReplayError("RUN_STARTED initial_snapshot is invalid") from exc
    if initial_snapshot.scenario_id != scenario_id:
        raise ReplayError(
            "initial_snapshot scenario_id does not match decision log metadata"
        )
    payload_scenario = first_payload.get("scenario_id")
    if payload_scenario != scenario_id:
        raise ReplayError("RUN_STARTED scenario_id does not match decision log metadata")

    model = DigitalModel.from_snapshot(initial_snapshot)
    for line_number, (raw, event) in enumerate(zip(raw_lines, events), start=1):
        before = snapshot_hash(model.snapshot())
        if raw.get("state_before_hash") != before:
            raise ReplayError(
                f"decision log line {line_number} state_before_hash mismatch: "
                f"expected {before} observed {raw.get('state_before_hash')}"
            )
        try:
            model.apply(event)
        except (TypeError, ValueError) as exc:
            raise ReplayError(
                f"event replay failed at line {line_number} "
                f"({event.sequence}:{event.kind})"
            ) from exc
        after = snapshot_hash(model.snapshot())
        if raw.get("state_after_hash") != after:
            raise ReplayError(
                f"decision log line {line_number} state_after_hash mismatch: "
                f"expected {after} observed {raw.get('state_after_hash')}"
            )

    if events[-1].kind != "END_OF_DAY":
        raise ReplayError("decision log must terminate with END_OF_DAY")
    return ReplayDetails(
        log_path=log_path,
        run_id=run_id,
        scenario_id=scenario_id,
        seed=seed,
        policy=policy,
        config_hash=config_checksum,
        events=tuple(events),
        lines=tuple(raw_lines),
        initial_snapshot=initial_snapshot,
        final_snapshot=model.snapshot(),
    )


def replay_run(log_path: str | Path) -> YardSnapshot:
    """Reconstruct and return the final digital snapshot from one JSONL log."""

    return _replay_log(log_path).final_snapshot


__all__ = ["ReplayDetails", "ReplayError", "replay_run", "snapshot_hash"]
