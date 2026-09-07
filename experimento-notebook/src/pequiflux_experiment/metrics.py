"""Canonical policy-day measurements derived only from persisted event bytes.

This reducer does not import the simulator, dispatcher, emitter or auditor.
It independently accounts for observed truck/resource intervals. Statistical
inference and cross-day aggregation belong to their respective consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from types import MappingProxyType
from typing import Any, Mapping

from .config import CANONICAL_CONFIRMATORY_FIELDS
from .domain import ExecutionControls
from .events import EventRecord


METRICS_SCHEMA_VERSION = 1
METRIC_SCALAR_FIELDS = (
    "event_count", "total_trucks", "completed_trucks", "remaining_trucks", "throughput",
    "mean_wait_minutes", "p50_wait_minutes", "p95_wait_minutes", "iqr_wait_minutes",
    "total_wait_minutes", "censored_wait_minutes", "makespan_minutes", "horizon_minutes",
    "throughput_rate", "scale_occupancy_peak", "hard_constraint_violations",
    "median_system_time_minutes", "iqr_system_time_minutes", "mean_system_time_minutes",
    "observed_system_time_minutes", "censored_system_time_minutes", "censored_system_trucks",
    "completed_system_trucks", "resource_busy_minutes", "resource_down_minutes",
    "resource_available_minutes", "resource_idle_minutes", "resource_gross_minutes",
    "gross_utilization", "net_utilization", "net_idle_fraction", "gross_idle_fraction",
    "decision_count", "fifo_break_count", "fifo_break_rate", "queue_comparison_count",
    "comparable_candidate_count", "queue_inversion_count", "max_queue_displacement",
    "mean_queue_displacement", "replanning_count", "replanning_frequency_per_hour",
    "ordinary_window_activation_count", "mandatory_candidate_count", "mandatory_decision_count",
    "critical_expansion_candidate_count", "critical_expansion_decision_count",
    "operator_accept_count", "operator_reject_count", "dispatch_block_count", "command_count",
    "co2_estimated_kg", "co2_sensitivity_low_kg", "co2_sensitivity_high_kg",
)
INTEGER_METRIC_FIELDS = frozenset({
    "event_count", "total_trucks", "completed_trucks", "remaining_trucks", "throughput",
    "horizon_minutes", "scale_occupancy_peak", "hard_constraint_violations",
    "censored_system_trucks", "completed_system_trucks", "decision_count", "fifo_break_count",
    "queue_comparison_count", "comparable_candidate_count", "queue_inversion_count",
    "max_queue_displacement", "replanning_count", "ordinary_window_activation_count",
    "mandatory_candidate_count", "mandatory_decision_count", "critical_expansion_candidate_count",
    "critical_expansion_decision_count", "operator_accept_count", "operator_reject_count",
    "dispatch_block_count", "command_count",
})

_DEFINITIONS = {
    "waiting": "Eligible queue intervals across four operations, including right-censored eligible waiting at the horizon; document holds and active service are excluded.",
    "quantiles": "p50 and medians use the arithmetic median; p95 waiting uses nearest rank ceil(.95*N); IQR uses linearly interpolated quartiles (R7).",
    "system_time": "Per-truck observed arrival-to-final-scale-completion or arrival-to-horizon interval, with an explicit censor flag. Mean/median/IQR use completed cycles only; no completed cycles is undefined and fails.",
    "resource_time": "Busy intervals include service still active at the horizon. Downtime is the union of effective disruption intervals, reconciled with physical failure/recovery transitions; nonpreemptive service cannot overlap downtime.",
    "utilization": "Gross=busy/horizon; net=busy/(horizon-down). Available idle=(horizon-down)-busy. Net idle fraction complements net utilization; gross nonbusy fraction includes downtime. Aggregates divide summed resource-minutes, never average resource ratios.",
    "fifo": "A FIFO break selects a different truck from the earliest (stage_entry_time,truck_id) in the recorded admissible candidate queue; the recorded justification must agree.",
    "stability": "Consecutive recorded candidate_order lists for the same physical resource are restricted to common IDs. Inversions count reversed pairs. Displacement is absolute rank change in these restricted lists; the empty/singleton permutation has distance zero. Mean displacement averages each comparison's mean absolute displacement; comparison and common-candidate counts remain explicit. This observes offered queues, not an unrecorded future policy ranking.",
    "replanning": "Count of consecutive observed queue comparisons with a changed relative order, divided by horizon hours for frequency. It is not a count of hypothetical solver runs or human replans.",
    "admission_diagnostics": "H0 activation counts non-mandatory non-strict decisions with more hard-feasible candidates than H0; mandatory and critical-expansion candidate counts are decision exposures, not distinct trucks. Critical expansion counts pressured candidates beyond the ordinary prefix. Strict FIFO does not apply the window.",
    "operator": "Accept/reject counts describe persisted operator decisions. Synthetic auto-accept events are not evidence of human validation or intervention.",
    "co2": "Exploratory eligible queue minutes/60 * .8 gal/hour * 10.18 kg CO2/gal; sensitivity uses .5 and 1.0 gal/hour. Includes censored observed queue waiting. Excludes travel, cold start, dust, electricity and fuel lifecycle; never enters H1/IUT.",
    "rounding": "Published floating metrics are rounded to 12 decimals; truck waiting accumulation and cross-truck sums use sorted truck IDs for reproducibility.",
}
_OPERATIONS = ("gate", "scale_in", "unload", "scale_out")
_OPERATION_KIND = {"gate": "gate", "scale_in": "scale", "unload": "hopper", "scale_out": "scale"}


class MetricsError(ValueError):
    """A persisted observation cannot define the complete metric contract."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class MetricRow:
    log_sha256: str
    scalars: Mapping[str, int | float]
    resources: Mapping[str, Mapping[str, Any]]
    trucks: Mapping[str, Mapping[str, Any]]
    definitions: Mapping[str, str]
    schema_version: int = METRICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if set(self.scalars) != set(METRIC_SCALAR_FIELDS):
            raise MetricsError("metric scalar fields do not match the complete schema")
        for name, value in self.scalars.items():
            _number(value, name)
            if name in INTEGER_METRIC_FIELDS and (isinstance(value, bool) or not isinstance(value, int)):
                raise MetricsError(f"{name} must be an integer")
        for name in ("scalars", "resources", "trucks", "definitions"):
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "log_sha256": self.log_sha256,
            "scalars": _plain(self.scalars),
            "resources": [{"resource_id": key, **_plain(value)} for key, value in sorted(self.resources.items())],
            "trucks": [{"truck_id": key, **_plain(value)} for key, value in sorted(self.trucks.items())],
            "definitions": _plain(self.definitions),
        }


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise MetricsError(f"{label} must be finite, numeric and non-negative")
    return float(value)


def _rounded(value: float) -> float:
    return round(float(value), 12)


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise MetricsError("quantile is undefined without observed values")
    values = sorted(values)
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    fraction = position - lower
    return values[lower] + fraction * (values[min(lower + 1, len(values) - 1)] - values[lower])


def _union(intervals: list[tuple[float, float]], horizon: float) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted((max(0.0, start), min(horizon, end)) for start, end in intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise MetricsError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def compute_policy_day_metrics(persisted_day: str | Path) -> MetricRow:
    """Read one closed JSONL log and derive its complete numeric measurements.

    Input must contain the initial truck/resource inventory and complete
    execution controls in RUN_STARTED. Missing observations and undefined
    denominators fail instead of being substituted with zero or NaN.
    """
    source = Path(persisted_day)
    try:
        raw_bytes = source.read_bytes()
        rows = []
        for line_number, line in enumerate(raw_bytes.decode("utf-8").splitlines(), 1):
            if not line.strip():
                raise MetricsError(f"empty JSONL row {line_number}")
            row = json.loads(line, object_pairs_hook=_json_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(MetricsError(f"nonfinite JSON value {value}")))
            if not isinstance(row, dict):
                raise MetricsError(f"JSONL row {line_number} must be an object")
            rows.append(row)
        return _compute(rows, hashlib.sha256(raw_bytes).hexdigest())
    except MetricsError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, IndexError) as exc:
        raise MetricsError(f"cannot derive complete metrics from {source}: {exc}") from exc


def _compute(rows: list[dict[str, Any]], log_hash: str) -> MetricRow:
    events = tuple(EventRecord.from_dict(row) for row in rows)
    if not events or events[0].kind != "RUN_STARTED" or events[-1].kind != "END_OF_DAY":
        raise MetricsError("log must begin with RUN_STARTED and finish with END_OF_DAY")
    horizon = _number(events[-1].payload["horizon_minutes"], "horizon_minutes")
    if horizon != 720.0 or events[-1].time != horizon or events[0].time != 0.0:
        raise MetricsError("log must cover the complete canonical 720-minute horizon")
    previous_time = 0.0
    for index, event in enumerate(events, 1):
        if event.sequence != index or not previous_time <= event.time <= horizon:
            raise MetricsError("event sequence/time must be contiguous, ordered and within the horizon")
        if event.kind == "RUN_STARTED" and index != 1 or event.kind == "END_OF_DAY" and index != len(events):
            raise MetricsError("RUN_STARTED and END_OF_DAY must be unique")
        previous_time = event.time
    initial = events[0].payload["initial_snapshot"]
    controls = ExecutionControls(**dict(events[0].payload["execution_controls"]))
    initial_resources, initial_trucks = initial["resources"], initial["trucks"]
    if not isinstance(initial_resources, Mapping) or not initial_resources or not isinstance(initial_trucks, Mapping) or not initial_trucks:
        raise MetricsError("initial resource/truck inventories are required and cannot be empty")
    states = {}
    for truck_id, record in initial_trucks.items():
        if (not isinstance(truck_id, str) or not truck_id or type(record["priority"]) is not int
                or record["priority"] not in (0, 1, 2) or type(record["document_ok"]) is not bool
                or not isinstance(record["cargo_type"], str) or not record["cargo_type"]):
            raise MetricsError("initial truck identity, priority, document and cargo must be explicit valid values")
        arrival = _number(record["arrival_time"], f"{truck_id}.arrival_time")
        if arrival > horizon or record["arrived"] is not False or record["next_operation"] != "gate":
            raise MetricsError("initial truck must be unarrived, at gate, and due within the horizon")
        states[truck_id] = {"arrival": arrival, "priority": record["priority"], "cargo": record["cargo_type"],
                            "document": record["document_ok"], "arrived": False, "stage": 0,
                            "stage_time": arrival, "ready": None, "wait": 0.0, "service": 0.0,
                            "document_hold": 0.0, "completed": None, "censored_wait": 0.0}
    resource_status = {}
    for resource_id, record in initial_resources.items():
        cargo_types = record["allowed_cargo_types"]
        if (not isinstance(resource_id, str) or not resource_id or record["status"] != "available"
                or record["kind"] not in {"gate", "scale", "hopper"}
                or not isinstance(cargo_types, (list, tuple)) or not cargo_types
                or any(not isinstance(value, str) or not value for value in cargo_types)
                or len(set(cargo_types)) != len(cargo_types)):
            raise MetricsError("initial resources require an available physical kind and explicit cargo eligibility")
        resource_status[resource_id] = "available"
    busy_intervals = {key: [] for key in initial_resources}
    down_intervals = {key: [] for key in initial_resources}
    evidence_intervals = {key: [] for key in initial_resources}
    failed_since = {}
    active = {}
    resource_truck = {}
    accepted = {}
    decisions = {}
    previous_queues = {}
    disruption_ids = set()
    completed_operations = []
    counts = {name: 0 for name in INTEGER_METRIC_FIELDS}
    displacement_sum = 0.0
    thresholds = tuple(CANONICAL_CONFIRMATORY_FIELDS["priority_thresholds"])

    def require_truck(truck_id):
        if truck_id not in states:
            raise MetricsError(f"unknown truck {truck_id!r}")
        return states[truck_id]

    def require_resource(resource_id):
        if resource_id not in initial_resources:
            raise MetricsError(f"unknown resource {resource_id!r}")
        return initial_resources[resource_id]

    def feasible_queue(resource_id):
        resource = require_resource(resource_id)
        reservation = sum(state["arrived"] and state["stage"] in (1, 2) for state in states.values())
        scale_out_queue = sum(state["arrived"] and state["stage"] == 3 and truck_id not in active for truck_id, state in states.items())
        values = []
        for truck_id, state in states.items():
            stage = state["stage"]
            if not state["arrived"] or stage == 4 or truck_id in active or not state["document"]:
                continue
            if _OPERATION_KIND[_OPERATIONS[stage]] != resource["kind"] or state["cargo"] not in resource["allowed_cargo_types"]:
                continue
            allowed = (reservation < controls.buffer_capacity if stage == 0 else
                       reservation <= controls.buffer_capacity if stage == 1 else
                       scale_out_queue < controls.buffer_capacity if stage == 2 else True)
            if allowed:
                values.append(truck_id)
        return sorted(values, key=lambda truck_id: (states[truck_id]["stage_time"], truck_id))

    for event in events[1:-1]:
        payload, now, kind = event.payload, event.time, event.kind
        if kind == "TRUCK_ARRIVED":
            state = require_truck(payload["truck_id"])
            if state["arrived"] or now != state["arrival"] or payload["arrival_time"] != now:
                raise MetricsError("arrival is duplicated or disagrees with the frozen inventory")
            if (type(payload["priority"]) is not int or type(payload["document_ok"]) is not bool
                    or payload["priority"] != state["priority"] or payload["cargo_type"] != state["cargo"]
                    or payload["document_ok"] != state["document"]):
                raise MetricsError("arrival attributes diverge from the observed initial/priority state")
            state["arrived"] = True
            if state["document"]:
                state["ready"] = now
        elif kind == "DOCUMENT_RELEASED":
            state = require_truck(payload["truck_id"])
            if not state["arrived"] or state["document"] or state["stage"] != 0:
                raise MetricsError("document release requires one arrived blocked truck at gate")
            state.update(document=True, ready=now, stage_time=now, document_hold=now-state["arrival"])
        elif kind == "PRIORITY_CHANGED":
            state = require_truck(payload["truck_id"])
            priority = payload["priority"]
            if isinstance(priority, bool) or priority not in (0, 1, 2) or state["stage"] == 4:
                raise MetricsError("invalid priority transition")
            state["priority"] = priority
        elif kind == "DECISION_RECORDED":
            decision = payload["decision"]
            resource_id = decision["resource_id"]
            require_resource(resource_id)
            if resource_status[resource_id] != "available":
                raise MetricsError("decision references an unavailable resource")
            order = tuple(record["truck_id"] for record in decision["candidate_order"])
            if not order or len(set(order)) != len(order) or tuple(decision["candidate_ids"]) != order:
                raise MetricsError("decision requires a complete unique observed candidate order")
            feasible = feasible_queue(resource_id)
            mandatory = [truck_id for truck_id in feasible if states[truck_id]["priority"] == 2]
            expected = feasible
            if decision["policy"] != "fifo_strict":
                if mandatory:
                    expected = mandatory
                    counts["mandatory_decision_count"] += 1
                    counts["mandatory_candidate_count"] += len(mandatory)
                else:
                    extras = [truck_id for truck_id in feasible[controls.ordinary_window:]
                              if now - states[truck_id]["stage_time"] > thresholds[states[truck_id]["priority"]] * float(controls.threshold_multiplier)]
                    expected = feasible[:controls.ordinary_window] + extras
                    counts["ordinary_window_activation_count"] += len(feasible) > controls.ordinary_window
                    counts["critical_expansion_candidate_count"] += len(extras)
                    counts["critical_expansion_decision_count"] += bool(extras)
            if set(order) != set(expected):
                raise MetricsError("recorded candidate queue diverges from event-derived admission")
            for record in decision["candidate_order"]:
                state = require_truck(record["truck_id"])
                if record["stage_entry_time"] != state["stage_time"] or record["operation"] != _OPERATIONS[state["stage"]]:
                    raise MetricsError("candidate position/operation diverges from observed stage entry")
            selected = decision["selected"]
            selected_id = selected["truck_id"]
            if selected_id not in order or selected["resource_id"] != resource_id:
                raise MetricsError("selected command is outside the observed admissible queue")
            if selected_id in decisions or selected_id in accepted:
                raise MetricsError("new recommendation would overwrite an unfinished decision/command")
            fifo_id = min(order, key=lambda truck_id: (states[truck_id]["stage_time"], truck_id))
            fifo_break = selected_id != fifo_id
            if type(decision["justification"]["fifo_break"]) is not bool or decision["justification"]["fifo_break"] != fifo_break:
                raise MetricsError("recorded FIFO break disagrees with candidate timestamps")
            counts["decision_count"] += 1
            counts["fifo_break_count"] += fifo_break
            if resource_id in previous_queues:
                previous = previous_queues[resource_id]
                common = set(previous).intersection(order)
                before = [truck_id for truck_id in previous if truck_id in common]
                after = [truck_id for truck_id in order if truck_id in common]
                ranks = {truck_id: index for index, truck_id in enumerate(after)}
                inversions = sum(ranks[left] > ranks[right] for index, left in enumerate(before) for right in before[index+1:])
                displacement = [abs(index-ranks[truck_id]) for index, truck_id in enumerate(before)]
                counts["queue_comparison_count"] += 1
                counts["comparable_candidate_count"] += len(common)
                counts["queue_inversion_count"] += inversions
                counts["replanning_count"] += bool(inversions)
                counts["max_queue_displacement"] = max(counts["max_queue_displacement"], max(displacement, default=0))
                displacement_sum += sum(displacement) / len(displacement) if displacement else 0.0
            previous_queues[resource_id] = order
            decisions[selected_id] = decision
        elif kind == "OPERATOR_DECISION":
            decision = payload["recommendation"]
            truck_id = decision["selected"]["truck_id"]
            if decisions.get(truck_id) != decision:
                raise MetricsError("operator decision has no identical persisted recommendation")
            if payload["decision"] == "accept":
                counts["operator_accept_count"] += 1
                accepted[truck_id] = decision["selected"]
            elif payload["decision"] == "reject":
                counts["operator_reject_count"] += 1
            else:
                raise MetricsError("unknown operator decision")
            del decisions[truck_id]
        elif kind == "SERVICE_STARTED":
            truck_id, resource_id, operation = payload["truck_id"], payload["resource_id"], payload["operation"]
            state, resource = require_truck(truck_id), require_resource(resource_id)
            duration = _number(payload["duration_minutes"], "duration_minutes")
            if (truck_id in active or resource_status[resource_id] != "available" or state["ready"] is None
                    or state["stage"] == 4 or operation != _OPERATIONS[state["stage"]]
                    or _OPERATION_KIND[operation] != resource["kind"] or duration <= 0
                    or truck_id not in feasible_queue(resource_id)):
                raise MetricsError("service start violates occupancy, eligibility or operation precedence")
            command = accepted.pop(truck_id, None)
            if command is None or command["operation"] != operation or command["resource_id"] != resource_id:
                raise MetricsError("service start has no matching accepted command")
            state["wait"] += now - state["ready"]
            state["stage_time"] = now
            active[truck_id] = (operation, resource_id, now, duration)
            resource_truck[resource_id] = truck_id
            resource_status[resource_id] = "busy"
            counts["command_count"] += 1
            occupancy = sum(initial_resources[key]["kind"] == "scale" for key in resource_truck)
            counts["scale_occupancy_peak"] = max(counts["scale_occupancy_peak"], occupancy)
        elif kind == "SERVICE_COMPLETED":
            truck_id, resource_id, operation = payload["truck_id"], payload["resource_id"], payload["operation"]
            state = require_truck(truck_id)
            service = active.pop(truck_id, None)
            if service is None or service[:2] != (operation, resource_id) or resource_truck.get(resource_id) != truck_id:
                raise MetricsError("completion does not match an active service")
            _, _, start, duration = service
            if now != start + duration:
                raise MetricsError("completion time does not match the recorded service duration")
            busy_intervals[resource_id].append((start, now))
            state["service"] += now-start
            state["stage"] += 1
            state["stage_time"] = state["ready"] = now
            if state["stage"] == 4:
                state["completed"] = now
            resource_status[resource_id] = "available"
            del resource_truck[resource_id]
            completed_operations.append(now)
        elif kind == "DISRUPTION_RECORDED":
            resource_id, latent_id = payload["resource_id"], payload["latent_id"]
            require_resource(resource_id)
            key = (resource_id, latent_id)
            if key in disruption_ids or resource_status[resource_id] == "busy":
                raise MetricsError("duplicate disruption or preemption of an active service")
            disruption_ids.add(key)
            start = _number(payload["effective_failure_start"], "effective_failure_start")
            scheduled = _number(payload["scheduled_failure_start"], "scheduled_failure_start")
            duration = _number(payload["scheduled_failure_duration"], "scheduled_failure_duration")
            end = _number(payload["recovery_time"], "recovery_time")
            if start != now or scheduled > start or duration <= 0 or payload["cause"] not in {"rain", "base_failure", "critical_failure"}:
                raise MetricsError("disruption effective time/cause is inconsistent")
            expected_end = scheduled + duration if payload["cause"] == "rain" else start + duration
            if not math.isclose(end, expected_end, rel_tol=0.0, abs_tol=1e-9) or payload["expired_before_effective_start"] is not (end <= start):
                raise MetricsError("disruption duration/recovery evidence is inconsistent")
            if end > start:
                evidence_intervals[resource_id].append((start, end))
        elif kind == "RESOURCE_FAILED":
            resource_id = payload["resource_id"]
            require_resource(resource_id)
            if resource_status[resource_id] != "available":
                raise MetricsError("physical failure must begin on an available resource")
            failed_since[resource_id] = now
            resource_status[resource_id] = "failed"
        elif kind == "RESOURCE_RECOVERED":
            resource_id = payload["resource_id"]
            require_resource(resource_id)
            if resource_status[resource_id] != "failed":
                raise MetricsError("physical recovery has no matching failure")
            down_intervals[resource_id].append((failed_since.pop(resource_id), now))
            resource_status[resource_id] = "available"
        elif kind == "DISPATCH_BLOCKED":
            require_resource(payload["resource_id"])
            counts["dispatch_block_count"] += 1
        else:
            raise MetricsError(f"unhandled persisted event kind {kind}")

    if decisions or accepted:
        raise MetricsError("terminal log contains an unfinished recommendation/command chain")
    truck_rows = {}
    waits, system_times = [], []
    censored_wait = 0.0
    for truck_id in sorted(states):
        state = states[truck_id]
        if not state["arrived"]:
            raise MetricsError(f"missing arrival for frozen truck {truck_id}")
        censored_service = 0.0
        if truck_id in active:
            _, resource_id, start, duration = active[truck_id]
            if start + duration <= horizon:
                raise MetricsError("missing service completion within the observation horizon")
            busy_intervals[resource_id].append((start, horizon))
            censored_service = horizon-start
            state["service"] += censored_service
        elif state["document"] and state["completed"] is None:
            state["censored_wait"] = horizon-state["ready"]
            state["wait"] += state["censored_wait"]
            censored_wait += state["censored_wait"]
        if not state["document"]:
            state["document_hold"] = horizon-state["arrival"]
        censored = state["completed"] is None
        observed = (horizon if censored else state["completed"]) - state["arrival"]
        if not math.isclose(observed, state["wait"] + state["service"] + state["document_hold"], rel_tol=0.0, abs_tol=1e-8):
            raise MetricsError(f"truck {truck_id} observed time does not reconcile with queue, service and document intervals")
        waits.append(state["wait"])
        if not censored:
            system_times.append(observed)
        truck_rows[truck_id] = {"wait_minutes": _rounded(state["wait"]),
            "censored_wait_minutes": _rounded(state["censored_wait"]),
            "service_minutes": _rounded(state["service"]), "censored_service_minutes": _rounded(censored_service),
            "document_hold_minutes": _rounded(state["document_hold"]),
            "observed_system_time_minutes": _rounded(observed), "system_time_censored": censored}
    if not system_times:
        raise MetricsError("completed-cycle system-time summaries are undefined: no completed truck")
    if counts["decision_count"] == 0 or counts["queue_comparison_count"] == 0:
        raise MetricsError("decision rates/queue stability require observed decisions and consecutive queues")
    resource_rows = {}
    raw_resource_times = {}
    for resource_id in sorted(initial_resources):
        if resource_id in failed_since:
            if not evidence_intervals[resource_id] or max(end for _, end in evidence_intervals[resource_id]) <= horizon:
                raise MetricsError("missing physical recovery within the observation horizon")
            down_intervals[resource_id].append((failed_since[resource_id], horizon))
        down = _union(down_intervals[resource_id], horizon)
        evidence = _union(evidence_intervals[resource_id], horizon)
        if down != evidence:
            raise MetricsError(f"{resource_id} physical downtime does not equal the union of effective disruption evidence")
        busy = _union(busy_intervals[resource_id], horizon)
        if any(max(start, down_start) < min(end, down_end) for start, end in busy for down_start, down_end in down):
            raise MetricsError("resource busy time overlaps physical downtime")
        busy_time = sum(end-start for start, end in busy)
        down_time = sum(end-start for start, end in down)
        available = horizon-down_time
        if available <= 0:
            raise MetricsError(f"net utilization undefined for {resource_id}: no available horizon")
        idle = available-busy_time
        if idle < 0:
            raise MetricsError("resource accounting exceeds available time")
        raw_resource_times[resource_id] = (busy_time, down_time)
        resource_rows[resource_id] = {"kind": initial_resources[resource_id]["kind"],
            "gross_minutes": horizon, "busy_minutes": _rounded(busy_time), "down_minutes": _rounded(down_time),
            "available_minutes": _rounded(available), "idle_minutes": _rounded(idle),
            "gross_utilization": _rounded(busy_time/horizon), "net_utilization": _rounded(busy_time/available),
            "net_idle_fraction": _rounded(idle/available), "gross_idle_fraction": _rounded((horizon-busy_time)/horizon)}
    gross = horizon * len(resource_rows)
    busy = sum(values[0] for values in raw_resource_times.values())
    down = sum(values[1] for values in raw_resource_times.values())
    available = gross-down
    total_wait = sum(waits)
    makespan = max(completed_operations)-min(state["arrival"] for state in states.values())
    if makespan <= 0:
        raise MetricsError("makespan is undefined without a positive first-arrival-to-completion interval")
    scalar = dict(counts)
    scalar.update({
        "event_count": len(events), "total_trucks": len(states), "completed_trucks": len(system_times),
        "remaining_trucks": len(states)-len(system_times), "throughput": len(system_times),
        "mean_wait_minutes": sum(waits)/len(waits), "p50_wait_minutes": median(waits),
        "p95_wait_minutes": sorted(waits)[math.ceil(.95*len(waits))-1],
        "iqr_wait_minutes": _quantile(waits, .75)-_quantile(waits, .25),
        "total_wait_minutes": total_wait, "censored_wait_minutes": censored_wait,
        "makespan_minutes": makespan, "horizon_minutes": int(horizon), "throughput_rate": len(system_times)/makespan,
        "median_system_time_minutes": median(system_times), "mean_system_time_minutes": sum(system_times)/len(system_times),
        "iqr_system_time_minutes": _quantile(system_times, .75)-_quantile(system_times, .25),
        "observed_system_time_minutes": sum((horizon if states[key]["completed"] is None else states[key]["completed"])-states[key]["arrival"] for key in sorted(states)),
        "censored_system_time_minutes": sum(horizon-states[key]["arrival"] for key in sorted(states) if states[key]["completed"] is None),
        "censored_system_trucks": len(states)-len(system_times), "completed_system_trucks": len(system_times),
        "resource_busy_minutes": busy, "resource_down_minutes": down, "resource_available_minutes": available,
        "resource_idle_minutes": available-busy, "resource_gross_minutes": gross,
        "gross_utilization": busy/gross, "net_utilization": busy/available,
        "net_idle_fraction": (available-busy)/available, "gross_idle_fraction": (gross-busy)/gross,
        "fifo_break_rate": counts["fifo_break_count"]/counts["decision_count"],
        "mean_queue_displacement": displacement_sum/counts["queue_comparison_count"],
        "replanning_frequency_per_hour": counts["replanning_count"]/(horizon/60),
        "co2_estimated_kg": total_wait/60*.8*10.18,
        "co2_sensitivity_low_kg": total_wait/60*.5*10.18,
        "co2_sensitivity_high_kg": total_wait/60*1.0*10.18,
    })
    scalar = {key: scalar[key] if key in INTEGER_METRIC_FIELDS else _rounded(scalar[key]) for key in METRIC_SCALAR_FIELDS}
    return MetricRow(log_hash, scalar, resource_rows, truck_rows, _DEFINITIONS)


__all__ = ["MetricRow", "MetricsError", "METRIC_SCALAR_FIELDS", "INTEGER_METRIC_FIELDS", "compute_policy_day_metrics"]
