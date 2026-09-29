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


METRICS_SCHEMA_VERSION = 2
METRIC_SCALAR_FIELDS = (
    "event_count", "total_trucks", "completed_trucks", "remaining_trucks", "throughput",
    "mean_wait_minutes", "p50_wait_minutes", "p95_wait_minutes", "iqr_wait_minutes",
    "total_wait_minutes", "censored_wait_minutes", "document_hold_minutes",
    "observed_makespan_minutes", "horizon_minutes", "throughput_per_hour",
    "scale_occupancy_peak", "max_queue_length", "max_buffer_occupancy", "max_buffer_reservation",
    "hard_constraint_violations",
    "median_system_time_minutes", "iqr_system_time_minutes", "mean_system_time_minutes",
    "observed_system_time_minutes", "censored_system_time_minutes", "censored_system_trucks",
    "completed_system_trucks", "resource_busy_minutes", "resource_down_minutes",
    "resource_available_minutes", "resource_idle_minutes", "resource_gross_minutes",
    "gross_utilization", "net_utilization", "net_idle_fraction", "gross_idle_fraction",
    "decision_count", "fifo_break_count", "fifo_break_rate", "raw_fifo_break_count",
    "avoidable_fifo_break_count", "queue_comparison_count",
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
    "max_queue_length", "max_buffer_occupancy", "max_buffer_reservation",
    "censored_system_trucks", "completed_system_trucks", "decision_count", "fifo_break_count",
    "raw_fifo_break_count", "avoidable_fifo_break_count", "queue_comparison_count",
    "comparable_candidate_count", "queue_inversion_count",
    "max_queue_displacement", "replanning_count", "ordinary_window_activation_count",
    "mandatory_candidate_count", "mandatory_decision_count", "critical_expansion_candidate_count",
    "critical_expansion_decision_count", "operator_accept_count", "operator_reject_count",
    "dispatch_block_count", "command_count",
})

_DEFINITIONS = {
    "waiting": "Eligible queue intervals across four operations, including right-censored eligible waiting at the horizon; document holds and active service are excluded.",
    "documents": "Document holds are arrival-to-release or arrival-to-horizon intervals, reported separately from eligible queue waiting; they do not change the primary H1 waiting estimand.",
    "quantiles": "p50 and medians use the arithmetic median; p95 waiting uses nearest rank ceil(.95*N); IQR uses linearly interpolated quartiles (R7).",
    "system_time": "Per-truck observed arrival-to-final-scale-completion or arrival-to-horizon interval, with an explicit censor flag. Mean/median/IQR use completed cycles only; no completed cycles is undefined and fails.",
    "resource_time": "Busy intervals include service still active at the horizon. Downtime is the union of effective disruption intervals, reconciled with physical failure/recovery transitions; nonpreemptive service cannot overlap downtime.",
    "utilization": "Gross=busy/horizon; net=busy/(horizon-down). Available idle=(horizon-down)-busy. Gross idle=available idle/horizon, excluding downtime; gross busy+gross idle+down/horizon=1. Net idle complements net utilization. Aggregates divide summed resource-minutes, never average resource ratios.",
    "fifo": "A FIFO break selects a different truck from the earliest (stage_entry_time,truck_id) in the recorded admissible candidate queue; the recorded justification must agree.",
    "raw_fifo": "Raw FIFO orders all arrived, non-active, unfinished trucks whose next operation uses the physical resource kind, before document, cargo, buffer and mandatory-priority filters. A raw break is avoidable only when this first truck is hard-eligible and satisfies the registered admission mode's mandatory-priority restriction. No metric branches on a policy name.",
    "stability": "Consecutive recorded candidate_order lists for the same physical resource are restricted to common IDs. Inversions count reversed pairs. Displacement is absolute rank change in these restricted lists; the empty/singleton permutation has distance zero. Mean displacement averages each comparison's mean absolute displacement; comparison and common-candidate counts remain explicit. This observes offered queues, not an unrecorded future policy ranking.",
    "replanning": "Count of consecutive observed queue comparisons with a changed relative order, divided by horizon hours for frequency. It is not a count of hypothetical solver runs or human replans.",
    "admission_diagnostics": "RUN_STARTED must register admission_mode as full_queue or mandatory_window. H0 activation counts mandatory_window decisions without a mandatory truck and with more hard-feasible candidates than H0; mandatory and critical-expansion candidate counts are decision exposures, not distinct trucks. Critical expansion counts pressured candidates beyond the ordinary prefix. full_queue does not apply a window or mandatory-priority filter.",
    "operator": "Accept/reject counts describe persisted operator decisions. Synthetic auto-accept events are not evidence of human validation or intervention.",
    "co2": "Exploratory eligible queue minutes/60 * idle fuel rate in US gal/hour * 10.18 kg CO2/US gal * engine_on_fraction. Base fuel rate=.8 and assumed engine_on_fraction=1.0. Sensitivity rates .5 and 1.0 are assumed scenarios, not measured bounds. Includes censored observed queue waiting; excludes document holds, travel, cold start, dust, electricity and fuel lifecycle; never enters H1/IUT.",
    "maxima": "Queue and occupancy peaks are counts observed after each public state transition, not time integrals. Buffer occupancy is the maximum of the three intermediate queues and inbound reservation; buffer reservation is the maximum of inbound (scale_in plus unload, active or queued) and outbound (active unload plus queued scale_out) reservations.",
    "undefined_values": "Zero available resource time, no completed truck for completed-cycle summaries, no decisions for decision rates, or no consecutive resource queues for stability means an undefined denominator/population and raises MetricsError. Observed zero counts and zero distances in defined populations remain numeric zero.",
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


_DAY = "Observed canonical day [0,720] minutes; services may finish at 720 but cannot start at 720."
_TRUCKS = "All trucks in the frozen initial inventory, including unfinished trucks."
_COMPLETED = "Only trucks whose final scale_out service completes by minute 720."
_RESOURCES = "All initial physical resources, weighted by their resource-minutes."
_DECISIONS = "Persisted DECISION_RECORDED recommendations, including subsequent rejection."
_COMPARISONS = "Consecutive recorded candidate queues for the same physical resource; common IDs only."
_RESOURCE_KEYS = ("kind", "gross_minutes", "busy_minutes", "down_minutes", "available_minutes",
                  "idle_minutes", "gross_utilization", "net_utilization", "net_idle_fraction", "gross_idle_fraction")
_TRUCK_KEYS = ("wait_minutes", "censored_wait_minutes", "service_minutes", "censored_service_minutes",
               "document_hold_minutes", "observed_system_time_minutes", "system_time_censored")


def _description(definition: str, unit: str, population: str, window: str = _DAY) -> dict[str, str]:
    return {"definition": definition, "unit": unit, "population": population, "window": window}


# Declarative metadata only: the independent auditor shares these definitions,
# never the reducer's interval, percentile, admission or counting algorithms.
_SCALAR_CATALOG = {
    "event_count": _description("Number of persisted events, including RUN_STARTED and END_OF_DAY.", "events", "All persisted log rows."),
    "total_trucks": _description("Number of trucks in the initial inventory.", "trucks", _TRUCKS),
    "completed_trucks": _description("Number of complete four-operation cycles observed.", "trucks", _COMPLETED),
    "remaining_trucks": _description("Initial inventory minus completed cycles.", "trucks", _TRUCKS),
    "throughput": _description("Number of trucks completing their final scale_out by the horizon; a count, not a rate.", "trucks/day", _COMPLETED),
    "throughput_per_hour": _description("Completed cycles divided by 720/60 observed hours.", "trucks/hour", _COMPLETED),
    "mean_wait_minutes": _description("Arithmetic mean of per-truck accumulated eligible queue waiting, including censored eligible waits.", "minutes/truck", _TRUCKS),
    "p50_wait_minutes": _description("Arithmetic median of per-truck accumulated eligible queue waiting.", "minutes", _TRUCKS),
    "p95_wait_minutes": _description("Nearest-rank percentile: sorted per-truck waiting at one-based rank ceil(0.95*N).", "minutes", _TRUCKS),
    "iqr_wait_minutes": _description("R7 linearly interpolated 75th percentile minus 25th percentile of per-truck eligible waiting.", "minutes", _TRUCKS),
    "total_wait_minutes": _description("Sum of eligible waits before all four operations; excludes service and document holds.", "truck-minutes", _TRUCKS),
    "censored_wait_minutes": _description("Sum of unfinished eligible queue intervals from eligibility to minute 720.", "truck-minutes", "Unfinished trucks waiting and document-clear at minute 720."),
    "document_hold_minutes": _description("Sum of arrival-to-document-release holds, censored at 720 when unreleased.", "truck-minutes", _TRUCKS),
    "observed_makespan_minutes": _description("Last completion of any operation observed by 720 minus the first arrival; does not estimate clearance of unfinished trucks.", "minutes", "All observed operation completions and the first inventory arrival."),
    "horizon_minutes": _description("Fixed duration of the observation day.", "minutes", "One policy-day."),
    "scale_occupancy_peak": _description("Maximum number of simultaneous scale_in and scale_out services in the shared scale pool.", "trucks", "Active services on all scales."),
    "max_queue_length": _description("Maximum waiting count in any one of gate, scale_in, unload or scale_out queues; gate includes documentary holds; active services excluded.", "trucks", "All arrived unfinished trucks, grouped by next operation."),
    "max_buffer_occupancy": _description("Maximum of queued scale_in, queued unload, queued scale_out and inbound reservations (queued or active scale_in/unload).", "trucks", "Intermediate queues and inbound reserved buffer slots."),
    "max_buffer_reservation": _description("Maximum reserved slots in either inbound (scale_in/unload, queued or active) or outbound (active unload plus queued scale_out) buffer.", "trucks", "Reservations in each of the two intermediate buffers."),
    "hard_constraint_violations": _description("Zero only after every observed physical/eligibility/accounting invariant checked by the reducer passes; invalid observations raise.", "violations", "Observed resource, truck, service and buffer transitions."),
    "median_system_time_minutes": _description("Arithmetic median of arrival-to-final-scale-completion intervals; undefined without a completed truck.", "minutes", _COMPLETED),
    "iqr_system_time_minutes": _description("R7 IQR of arrival-to-final-scale-completion intervals; undefined without a completed truck.", "minutes", _COMPLETED),
    "mean_system_time_minutes": _description("Arithmetic mean of arrival-to-final-scale-completion intervals; undefined without a completed truck.", "minutes/truck", _COMPLETED),
    "observed_system_time_minutes": _description("Sum of arrival-to-final-completion intervals, or arrival-to-720 for unfinished trucks.", "truck-minutes", _TRUCKS),
    "censored_system_time_minutes": _description("Sum of arrival-to-720 observed system intervals for unfinished trucks.", "truck-minutes", "Trucks whose final scale_out is not completed by 720."),
    "censored_system_trucks": _description("Count of unfinished, right-censored system intervals.", "trucks", _TRUCKS),
    "completed_system_trucks": _description("Count of uncensored completed system intervals used by system-time summaries.", "trucks", _COMPLETED),
    "resource_busy_minutes": _description("Sum of service interval lengths, including active services clipped at 720.", "resource-minutes", _RESOURCES),
    "resource_down_minutes": _description("Sum across resources of each resource's union of effective disruption intervals, clipped to the horizon.", "resource-minutes", _RESOURCES),
    "resource_available_minutes": _description("Total resource horizon minus union downtime.", "resource-minutes", _RESOURCES),
    "resource_idle_minutes": _description("Available resource time minus busy time; excludes downtime.", "resource-minutes", _RESOURCES),
    "resource_gross_minutes": _description("Number of initial resources multiplied by 720 minutes.", "resource-minutes", _RESOURCES),
    "gross_utilization": _description("Summed busy resource-minutes divided by summed gross resource-minutes.", "fraction", _RESOURCES),
    "net_utilization": _description("Summed busy resource-minutes divided by summed available resource-minutes; zero available time is undefined.", "fraction", _RESOURCES),
    "net_idle_fraction": _description("Summed available idle time divided by summed available time; zero available time is undefined.", "fraction", _RESOURCES),
    "gross_idle_fraction": _description("Summed available idle time divided by summed gross time; downtime is excluded from the numerator.", "fraction", _RESOURCES),
    "decision_count": _description("Number of persisted recommendations.", "decisions", _DECISIONS),
    "fifo_break_count": _description("Recommendations selecting other than the earliest (stage_entry_time,truck_id) within the recorded admitted queue.", "decisions", _DECISIONS),
    "fifo_break_rate": _description("Admitted-queue FIFO break count divided by decision count; no decisions is undefined.", "fraction", _DECISIONS),
    "raw_fifo_break_count": _description("Recommendations bypassing the earliest raw resource-kind-compatible queue truck before hard and mandatory filters.", "decisions", _DECISIONS),
    "avoidable_fifo_break_count": _description("Raw FIFO breaks whose bypassed first truck is hard-eligible and obeys the registered admission mode's mandatory-priority restriction.", "decisions", _DECISIONS),
    "queue_comparison_count": _description("Number of consecutive resource-specific candidate-order comparisons.", "comparisons", _COMPARISONS),
    "comparable_candidate_count": _description("Sum of common candidate counts over consecutive queue comparisons; repeated appearances count repeatedly.", "candidate-exposures", _COMPARISONS),
    "queue_inversion_count": _description("Sum of pair reversals between consecutive lists restricted to their common IDs.", "pair-inversions", _COMPARISONS),
    "max_queue_displacement": _description("Maximum absolute rank change after restricting each compared list to common IDs; empty/singleton lists have distance zero.", "positions", _COMPARISONS),
    "mean_queue_displacement": _description("Mean across comparisons of each comparison's mean absolute common-ID rank change; empty lists contribute zero; no comparisons is undefined.", "positions/comparison", _COMPARISONS),
    "replanning_count": _description("Number of consecutive queue comparisons with at least one inversion; no hypothetical solver or human actions inferred.", "comparisons", _COMPARISONS),
    "replanning_frequency_per_hour": _description("Observed inversion-bearing queue comparisons divided by 12 observation hours.", "comparisons/hour", _COMPARISONS),
    "ordinary_window_activation_count": _description("mandatory_window recommendations with no mandatory truck and more hard-feasible trucks than H0.", "decisions", _DECISIONS),
    "mandatory_candidate_count": _description("Sum of priority-2 candidate exposures in mandatory_window decisions with mandatory trucks.", "candidate-exposures", _DECISIONS),
    "mandatory_decision_count": _description("mandatory_window recommendations restricted to priority-2 trucks.", "decisions", _DECISIONS),
    "critical_expansion_candidate_count": _description("Sum of pressured hard-feasible candidate exposures admitted beyond H0 when no mandatory truck exists.", "candidate-exposures", _DECISIONS),
    "critical_expansion_decision_count": _description("mandatory_window recommendations admitting at least one pressured candidate beyond H0.", "decisions", _DECISIONS),
    "operator_accept_count": _description("Persisted operator decisions accepting a matching recommendation; synthetic acceptance is not human validation.", "decisions", "Persisted OPERATOR_DECISION events."),
    "operator_reject_count": _description("Persisted operator decisions rejecting a matching recommendation.", "decisions", "Persisted OPERATOR_DECISION events."),
    "dispatch_block_count": _description("Number of persisted DISPATCH_BLOCKED events; not a count of hypothetical opportunities.", "events", "Persisted DISPATCH_BLOCKED events."),
    "command_count": _description("Number of services actually started after an accepted recommendation.", "commands", "Persisted SERVICE_STARTED events."),
    "co2_estimated_kg": _description("Eligible queue hours * 0.8 US gal/hour * 10.18 kg CO2/US gal * assumed engine-on fraction 1.0; exploratory combustion-only estimate.", "kg CO2", _TRUCKS),
    "co2_sensitivity_low_kg": _description("Same exploratory calculation using assumed fuel rate 0.5 US gal/hour; not an empirical lower bound.", "kg CO2", _TRUCKS),
    "co2_sensitivity_high_kg": _description("Same exploratory calculation using assumed fuel rate 1.0 US gal/hour; not an empirical upper bound.", "kg CO2", _TRUCKS),
}
_RESOURCE_CATALOG = {
    "kind": _description("Physical resource class: gate, scale or hopper.", "category", "One initial physical resource."),
    "gross_minutes": _description("Full resource observation horizon of 720 minutes.", "minutes", "One initial physical resource."),
    "busy_minutes": _description("Union length of its service intervals clipped at 720.", "minutes", "One initial physical resource."),
    "down_minutes": _description("Union length of its effective disruption intervals clipped at 720.", "minutes", "One initial physical resource."),
    "available_minutes": _description("Gross horizon minus union downtime.", "minutes", "One initial physical resource."),
    "idle_minutes": _description("Available time minus busy time, excluding downtime.", "minutes", "One initial physical resource."),
    "gross_utilization": _description("Busy minutes divided by the 720-minute gross horizon.", "fraction", "One initial physical resource."),
    "net_utilization": _description("Busy minutes divided by available minutes; zero available time raises.", "fraction", "One initial physical resource."),
    "net_idle_fraction": _description("Available idle minutes divided by available minutes; zero available time raises.", "fraction", "One initial physical resource."),
    "gross_idle_fraction": _description("Available idle minutes divided by gross minutes; downtime is not idle.", "fraction", "One initial physical resource."),
}
_TRUCK_CATALOG = {
    "wait_minutes": _description("Sum of eligible queue intervals before four operations, including an unfinished eligible interval clipped at 720.", "minutes", "One truck; document holds and active services excluded."),
    "censored_wait_minutes": _description("Final unfinished eligible queue interval up to 720; zero if not waiting while document-clear at 720.", "minutes", "One truck."),
    "service_minutes": _description("Sum of completed services plus elapsed part of service active at 720.", "minutes", "One truck."),
    "censored_service_minutes": _description("Elapsed portion of service still active at 720; zero without active service.", "minutes", "One truck."),
    "document_hold_minutes": _description("Arrival-to-document-release interval, or arrival-to-720 when blocked throughout observation.", "minutes", "One truck."),
    "observed_system_time_minutes": _description("Arrival-to-final-scale completion for completed trucks, otherwise arrival-to-720; equals queue+service+document time.", "minutes", "One truck."),
    "system_time_censored": _description("True exactly when final scale_out is not completed by 720.", "boolean", "One truck."),
}
if (set(_SCALAR_CATALOG) != set(METRIC_SCALAR_FIELDS)
        or set(_RESOURCE_CATALOG) != set(_RESOURCE_KEYS) or set(_TRUCK_CATALOG) != set(_TRUCK_KEYS)):
    raise RuntimeError("metric catalog must describe every published measurement field exactly")
METRIC_CATALOG = _freeze({"scalars": _SCALAR_CATALOG, "resources": _RESOURCE_CATALOG, "trucks": _TRUCK_CATALOG})
CO2_ASSUMPTIONS = _freeze({
    "idle_fuel_rate_us_gal_per_hour": 0.8,
    "carbon_factor_kg_per_us_gal": 10.18,
    "engine_on_fraction": 1.0,
    "sensitivity_us_gal_per_hour": [0.5, 1.0],
    "fuel_rate_source": "US DOE, Long-Haul Truck Idling Burns Up Profits (2015): approximately 0.8 US gal/hour.",
    "fuel_rate_source_url": "https://afdc.energy.gov/uploads/publication/hdv_idling_2015.pdf",
    "carbon_factor_source": "US EPA, SmartWay 2024 Table 1: diesel 10,180 g CO2/US gal, converted to 10.18 kg; 100% combustion.",
    "carbon_factor_source_url": "https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P101961J.txt",
    "engine_on_source": "Explicit project assumption, not an empirical observation: engine on throughout eligible waiting.",
    "sensitivity_source": "Assumed fuel-rate scenarios, not measured confidence bounds.",
    "scope": "Combustion-only exploratory estimate over observed eligible queue time, including censored waits; not H1/IUT.",
})
METRIC_DEFINITIONS = _freeze({"catalog": METRIC_CATALOG, "conventions": _DEFINITIONS, "co2_assumptions": CO2_ASSUMPTIONS})


def canonical_metric_definitions() -> dict[str, Any]:
    """Return detached JSON-compatible declarative metadata, without computing metrics."""

    return _plain(METRIC_DEFINITIONS)


@dataclass(frozen=True, slots=True)
class MetricRow:
    log_sha256: str
    scalars: Mapping[str, int | float]
    resources: Mapping[str, Mapping[str, Any]]
    trucks: Mapping[str, Mapping[str, Any]]
    definitions: Mapping[str, Any]
    schema_version: int = METRICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != METRICS_SCHEMA_VERSION:
            raise MetricsError("metric schema_version must be 2")
        if (not isinstance(self.log_sha256, str) or len(self.log_sha256) != 64
                or any(character not in "0123456789abcdef" for character in self.log_sha256)):
            raise MetricsError("metric log_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.scalars, Mapping) or set(self.scalars) != set(METRIC_SCALAR_FIELDS):
            raise MetricsError("metric scalar fields do not match the complete schema")
        for name, value in self.scalars.items():
            _number(value, name)
            if name in INTEGER_METRIC_FIELDS and (isinstance(value, bool) or not isinstance(value, int)):
                raise MetricsError(f"{name} must be an integer")
        for namespace, expected in (("resources", _RESOURCE_KEYS), ("trucks", _TRUCK_KEYS)):
            records = getattr(self, namespace)
            if not isinstance(records, Mapping) or not records:
                raise MetricsError(f"metric {namespace} must be a nonempty mapping")
            for identifier, record in records.items():
                if not isinstance(identifier, str) or not identifier.strip():
                    raise MetricsError(f"metric {namespace} identifiers must be nonempty strings")
                if not isinstance(record, Mapping) or set(record) != set(expected):
                    raise MetricsError(f"metric {namespace} record {identifier} fields do not match the complete schema")
                for name, value in record.items():
                    if namespace == "resources" and name == "kind":
                        if not isinstance(value, str) or value not in {"gate", "scale", "hopper"}:
                            raise MetricsError(f"metric resource {identifier} kind is invalid")
                    elif namespace == "trucks" and name == "system_time_censored":
                        if type(value) is not bool:
                            raise MetricsError(f"metric truck {identifier} system_time_censored must be a boolean")
                    else:
                        _number(value, f"{namespace}.{identifier}.{name}")
        if not isinstance(self.definitions, Mapping):
            raise MetricsError("metric definitions must match the canonical metadata")
        try:
            observed_definitions = json.dumps(_plain(self.definitions), sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise MetricsError("metric definitions must match the canonical metadata") from exc
        if observed_definitions != json.dumps(canonical_metric_definitions(), sort_keys=True, allow_nan=False):
            raise MetricsError("metric definitions must match the canonical metadata")
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
    admission_mode = events[0].payload["admission_mode"]
    if admission_mode not in {"full_queue", "mandatory_window"}:
        raise MetricsError("RUN_STARTED admission_mode must be full_queue or mandatory_window")
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
        scale_out_reservation = scale_out_queue + sum(service[0] == "unload" for service in active.values())
        values = []
        for truck_id, state in states.items():
            stage = state["stage"]
            if not state["arrived"] or stage == 4 or truck_id in active or not state["document"]:
                continue
            if _OPERATION_KIND[_OPERATIONS[stage]] != resource["kind"] or state["cargo"] not in resource["allowed_cargo_types"]:
                continue
            allowed = (reservation < controls.buffer_capacity if stage == 0 else
                       reservation <= controls.buffer_capacity if stage == 1 else
                       scale_out_reservation < controls.buffer_capacity if stage == 2 else True)
            if allowed:
                values.append(truck_id)
        return sorted(values, key=lambda truck_id: (states[truck_id]["stage_time"], truck_id))

    def observe_peaks():
        queues = [0, 0, 0, 0]
        inbound = outbound = 0
        for truck_id, state in states.items():
            if not state["arrived"] or state["stage"] == 4:
                continue
            stage, busy = state["stage"], truck_id in active
            if not busy:
                queues[stage] += 1
            inbound += stage in (1, 2)
            outbound += (stage == 2 and busy) or (stage == 3 and not busy)
        counts["max_queue_length"] = max(counts["max_queue_length"], *queues)
        counts["max_buffer_occupancy"] = max(counts["max_buffer_occupancy"], *queues[1:], inbound)
        counts["max_buffer_reservation"] = max(counts["max_buffer_reservation"], inbound, outbound)
        if max(*queues[1:], inbound, outbound) > controls.buffer_capacity:
            raise MetricsError("observed buffer queue or reservation exceeds execution capacity")

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
            if admission_mode == "mandatory_window":
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
            raw_queue = sorted(
                (truck_id for truck_id, state in states.items()
                 if state["arrived"] and state["stage"] != 4 and truck_id not in active
                 and _OPERATION_KIND[_OPERATIONS[state["stage"]]] == initial_resources[resource_id]["kind"]),
                key=lambda truck_id: (states[truck_id]["stage_time"], truck_id),
            )
            raw_fifo_id = raw_queue[0]
            raw_break = selected_id != raw_fifo_id
            mandatory_eligible = (admission_mode == "full_queue" or not mandatory
                                  or raw_fifo_id in mandatory)
            counts["raw_fifo_break_count"] += raw_break
            counts["avoidable_fifo_break_count"] += raw_break and raw_fifo_id in feasible and mandatory_eligible
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
            if (now >= horizon or truck_id in active or resource_status[resource_id] != "available" or state["ready"] is None
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
        observe_peaks()

    if decisions or accepted:
        raise MetricsError("terminal log contains an unfinished recommendation/command chain")
    truck_rows = {}
    waits, system_times = [], []
    censored_waits: list[float] = []
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
            censored_waits.append(state["censored_wait"])
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
            "net_idle_fraction": _rounded(idle/available), "gross_idle_fraction": _rounded(idle/horizon)}
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
        "total_wait_minutes": total_wait, "censored_wait_minutes": sum(censored_waits),
        "document_hold_minutes": sum(states[key]["document_hold"] for key in sorted(states)),
        "observed_makespan_minutes": makespan, "horizon_minutes": int(horizon),
        "throughput_per_hour": len(system_times)/(horizon/60),
        "median_system_time_minutes": median(system_times), "mean_system_time_minutes": sum(system_times)/len(system_times),
        "iqr_system_time_minutes": _quantile(system_times, .75)-_quantile(system_times, .25),
        "observed_system_time_minutes": sum((horizon if states[key]["completed"] is None else states[key]["completed"])-states[key]["arrival"] for key in sorted(states)),
        "censored_system_time_minutes": sum(horizon-states[key]["arrival"] for key in sorted(states) if states[key]["completed"] is None),
        "censored_system_trucks": len(states)-len(system_times), "completed_system_trucks": len(system_times),
        "resource_busy_minutes": busy, "resource_down_minutes": down, "resource_available_minutes": available,
        "resource_idle_minutes": available-busy, "resource_gross_minutes": gross,
        "gross_utilization": busy/gross, "net_utilization": busy/available,
        "net_idle_fraction": (available-busy)/available, "gross_idle_fraction": (available-busy)/gross,
        "fifo_break_rate": counts["fifo_break_count"]/counts["decision_count"],
        "mean_queue_displacement": displacement_sum/counts["queue_comparison_count"],
        "replanning_frequency_per_hour": counts["replanning_count"]/(horizon/60),
        "co2_estimated_kg": total_wait/60 * CO2_ASSUMPTIONS["idle_fuel_rate_us_gal_per_hour"]
            * CO2_ASSUMPTIONS["carbon_factor_kg_per_us_gal"] * CO2_ASSUMPTIONS["engine_on_fraction"],
        "co2_sensitivity_low_kg": total_wait/60 * CO2_ASSUMPTIONS["sensitivity_us_gal_per_hour"][0]
            * CO2_ASSUMPTIONS["carbon_factor_kg_per_us_gal"] * CO2_ASSUMPTIONS["engine_on_fraction"],
        "co2_sensitivity_high_kg": total_wait/60 * CO2_ASSUMPTIONS["sensitivity_us_gal_per_hour"][1]
            * CO2_ASSUMPTIONS["carbon_factor_kg_per_us_gal"] * CO2_ASSUMPTIONS["engine_on_fraction"],
    })
    scalar = {key: scalar[key] if key in INTEGER_METRIC_FIELDS else _rounded(scalar[key]) for key in METRIC_SCALAR_FIELDS}
    return MetricRow(log_hash, scalar, resource_rows, truck_rows, METRIC_DEFINITIONS)


__all__ = ["MetricRow", "MetricsError", "METRIC_SCALAR_FIELDS", "INTEGER_METRIC_FIELDS",
           "METRIC_CATALOG", "METRIC_DEFINITIONS", "CO2_ASSUMPTIONS", "canonical_metric_definitions",
           "compute_policy_day_metrics"]
