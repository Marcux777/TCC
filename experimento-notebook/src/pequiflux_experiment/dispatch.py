"""Feasibility and recommendation boundaries for the yard dispatcher.

The dispatcher is intentionally independent from the discrete-event emulator.
It receives an immutable observation and returns a recommendation; it never
mutates a truck, resource, or event queue.  Policies therefore only rank the
same admissible candidate set and cannot bypass hard constraints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping, TYPE_CHECKING

from .domain import CANONICAL_CARGO_TYPES, VALID_RESOURCE_STATUSES

if TYPE_CHECKING:  # pragma: no cover - import-only cycle guard
    from .policies import DispatchPolicy


_OPERATIONS = frozenset({"gate", "scale_in", "unload", "scale_out"})

# A2 is deliberately represented by one closed, version-independent object.
# These names are part of the persisted decision contract; a free-form
# ``explanation`` is retained only as a supplementary human-readable summary.
JUSTIFICATION_FIELDS: tuple[str, ...] = (
    "truck_stage",
    "resource",
    "activated_rules",
    "reason",
    "fifo_break",
)

# Policy-specific evidence is kept closed as well.  A persisted decision may
# only claim a ranking/restriction that this dispatcher actually applies.
_POLICY_JUSTIFICATION_RULES: dict[str, tuple[str, ...]] = {
    "fifo_strict": (),
    "fifo_flow_faithful": ("waiting_window",),
    "priority_local": ("priority_order",),
    "fixed_score": ("waiting_window", "priority_score", "affinity_score"),
    "lexicographic": (
        "priority_order",
        "waiting_window",
        "stability_order",
        "affinity_order",
    ),
}


def _finite_nonnegative(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _identifier(name: str, value: object, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class Candidate:
    """One truck that may be considered for the current service operation.

    ``realized_duration`` is deliberately not a field.  Durations are sampled
    only after a selection has been accepted by the emulator, so no policy can
    use future realized service time when ranking candidates.
    """

    truck_id: str
    arrival_time: float = 0.0
    priority: int = 0
    document_ok: bool = True
    waiting_time: float = 0.0
    operation: str | None = None
    stability: float = 0.0
    affinity: float = 0.0
    stable_order: int = 0
    resource_id: str | None = None
    arrived: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    cargo_type: str = "soy"
    stage_entry_time: float | None = None
    pressure: float = 0.0
    reorder_penalty: float = 0.0
    eligible: bool = True
    eligibility_reason: str | None = None

    def __post_init__(self) -> None:
        identifier = _identifier("truck_id", self.truck_id)
        if identifier is None:  # pragma: no cover - _identifier already rejects this
            raise ValueError("truck_id must be a non-empty string")
        object.__setattr__(self, "truck_id", identifier)
        object.__setattr__(self, "arrival_time", _finite_nonnegative("arrival_time", self.arrival_time))
        if not isinstance(self.cargo_type, str) or not self.cargo_type.strip():
            raise ValueError("cargo_type must be a non-empty string")
        object.__setattr__(
            self,
            "stage_entry_time",
            self.arrival_time
            if self.stage_entry_time is None
            else _finite_nonnegative("stage_entry_time", self.stage_entry_time),
        )
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("priority must be an integer")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if not isinstance(self.document_ok, bool):
            raise TypeError("document_ok must be bool")
        object.__setattr__(self, "waiting_time", _finite_nonnegative("waiting_time", self.waiting_time))
        object.__setattr__(self, "pressure", _finite_nonnegative("pressure", self.pressure))
        object.__setattr__(
            self,
            "reorder_penalty",
            _finite_nonnegative("reorder_penalty", self.reorder_penalty),
        )
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be bool")
        if self.eligibility_reason is not None:
            if not isinstance(self.eligibility_reason, str) or not self.eligibility_reason.strip():
                raise ValueError("eligibility_reason must be a non-empty string or None")
        if self.operation is not None:
            if self.operation not in _OPERATIONS:
                raise ValueError(f"operation must be one of: {', '.join(sorted(_OPERATIONS))}")
        object.__setattr__(self, "stability", _finite_nonnegative("stability", self.stability))
        object.__setattr__(self, "affinity", _finite_nonnegative("affinity", self.affinity))
        if isinstance(self.stable_order, bool) or not isinstance(self.stable_order, int):
            raise TypeError("stable_order must be an integer")
        if self.stable_order < 0:
            raise ValueError("stable_order must be non-negative")
        resource_id = _identifier("resource_id", self.resource_id, allow_none=True)
        object.__setattr__(self, "resource_id", resource_id)
        if not isinstance(self.arrived, bool):
            raise TypeError("arrived must be bool")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def id(self) -> str:
        return self.truck_id

    @property
    def document_released(self) -> bool:
        """Alias matching the domain truck terminology."""

        return self.document_ok

    @property
    def document_blocked(self) -> bool:
        return not self.document_ok

    @property
    def wait(self) -> float:
        return self.waiting_time

    @property
    def ready_time(self) -> float:
        """Alias for the current-stage entry timestamp."""

        return self.stage_entry_time

    @classmethod
    def from_truck(
        cls,
        truck: Any,
        *,
        now: float = 0.0,
        operation: str | None = None,
        stable_order: int = 0,
    ) -> "Candidate":
        """Construct a candidate from a Task 2 ``Truck`` value."""

        if not hasattr(truck, "truck_id"):
            raise TypeError("truck must expose truck_id")
        arrival_time = float(truck.arrival_time)
        current_time = _finite_nonnegative("now", now)
        stage_entry_time = getattr(truck, "stage_entry_time", arrival_time)
        return cls(
            truck_id=truck.truck_id,
            arrival_time=arrival_time,
            priority=truck.priority,
            document_ok=truck.document_ok,
            waiting_time=max(0.0, current_time - float(stage_entry_time)),
            operation=operation,
            stable_order=stable_order,
            arrived=bool(getattr(truck, "arrived", True)),
            cargo_type=truck.cargo_type,
            stage_entry_time=stage_entry_time,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "arrival_time": self.arrival_time,
            "priority": self.priority,
            "document_ok": self.document_ok,
            "waiting_time": self.waiting_time,
            "operation": self.operation,
            "stability": self.stability,
            "affinity": self.affinity,
            "stable_order": self.stable_order,
            "resource_id": self.resource_id,
            "arrived": self.arrived,
            "metadata": dict(self.metadata),
            "cargo_type": self.cargo_type,
            "stage_entry_time": self.stage_entry_time,
            "pressure": self.pressure,
            "reorder_penalty": self.reorder_penalty,
            "eligible": self.eligible,
            "eligibility_reason": self.eligibility_reason,
        }


@dataclass(frozen=True, slots=True)
class DecisionJustification:
    """Canonical five-field explanation required by the A2 protocol.

    ``truck_stage`` and ``resource`` are mappings rather than interpolated
    strings so the auditor can compare identifiers and the selected stage
    directly with the recommendation.  The remaining fields stay explicit:
    activated rule names, a readable reason, and the boolean FIFO indication.
    No field has a default because an incomplete justification is not an A2
    decision record.
    """

    truck_stage: Mapping[str, str]
    resource: Mapping[str, str]
    activated_rules: tuple[str, ...]
    reason: str
    fifo_break: bool

    def __post_init__(self) -> None:
        if not isinstance(self.truck_stage, Mapping):
            raise TypeError("truck_stage must be a mapping")
        if set(self.truck_stage) != {"truck_id", "stage"}:
            raise ValueError("truck_stage must contain exactly truck_id and stage")
        truck_id = self.truck_stage.get("truck_id")
        stage = self.truck_stage.get("stage")
        _identifier("justification.truck_stage.truck_id", truck_id)
        if not isinstance(stage, str) or stage not in _OPERATIONS:
            allowed = ", ".join(sorted(_OPERATIONS))
            raise ValueError(f"justification.truck_stage.stage must be one of: {allowed}")
        object.__setattr__(
            self,
            "truck_stage",
            MappingProxyType({"truck_id": truck_id, "stage": stage}),
        )

        if not isinstance(self.resource, Mapping):
            raise TypeError("resource must be a mapping")
        if set(self.resource) != {"resource_id"}:
            raise ValueError("resource must contain exactly resource_id")
        resource_id = self.resource.get("resource_id")
        _identifier("justification.resource.resource_id", resource_id)
        object.__setattr__(
            self,
            "resource",
            MappingProxyType({"resource_id": resource_id}),
        )

        if isinstance(self.activated_rules, (str, bytes, bytearray)):
            raise TypeError("activated_rules must be an iterable of rule names")
        try:
            rules = tuple(self.activated_rules)
        except TypeError as exc:
            raise TypeError("activated_rules must be an iterable of rule names") from exc
        if not rules:
            raise ValueError("activated_rules must not be empty")
        if any(not isinstance(rule, str) or not rule.strip() for rule in rules):
            raise ValueError("activated_rules must contain non-empty strings")
        if len(set(rules)) != len(rules):
            raise ValueError("activated_rules must be unique")
        object.__setattr__(self, "activated_rules", rules)

        _identifier("justification.reason", self.reason)
        if not isinstance(self.fifo_break, bool):
            raise TypeError("fifo_break must be bool")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecisionJustification":
        """Parse exactly the canonical persisted five-field representation."""

        if not isinstance(value, Mapping):
            raise TypeError("justification must be a mapping")
        if set(value) != set(JUSTIFICATION_FIELDS):
            raise ValueError(
                "justification fields do not match canonical contract: "
                f"expected={JUSTIFICATION_FIELDS!r} observed={tuple(value)!r}"
            )
        return cls(
            truck_stage=value["truck_stage"],
            resource=value["resource"],
            activated_rules=value["activated_rules"],
            reason=value["reason"],
            fifo_break=value["fifo_break"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible contract object."""

        return {
            "truck_stage": dict(self.truck_stage),
            "resource": dict(self.resource),
            "activated_rules": list(self.activated_rules),
            "reason": self.reason,
            "fifo_break": self.fifo_break,
        }


@dataclass(frozen=True, slots=True)
class DispatchContext:
    """Immutable observable state supplied to a policy at one decision point."""

    now: float = 0.0
    resource_id: str | None = None
    resource_available: bool = True
    resource_status: str = "available"
    operation: str | None = None
    queue_length: int = 0
    affinity_target: str | None = None
    allowed_cargo_types: tuple[str, ...] = CANONICAL_CARGO_TYPES

    def __post_init__(self) -> None:
        object.__setattr__(self, "now", _finite_nonnegative("now", self.now))
        object.__setattr__(
            self,
            "resource_id",
            _identifier("resource_id", self.resource_id, allow_none=True),
        )
        if not isinstance(self.resource_available, bool):
            raise TypeError("resource_available must be bool")
        if not isinstance(self.resource_status, str) or not self.resource_status:
            raise ValueError("resource_status must be a non-empty string")
        if self.resource_status not in VALID_RESOURCE_STATUSES:
            allowed = ", ".join(sorted(VALID_RESOURCE_STATUSES))
            raise ValueError(f"resource_status must be one of: {allowed}")
        if self.operation is not None and self.operation not in _OPERATIONS:
            raise ValueError(f"operation must be one of: {', '.join(sorted(_OPERATIONS))}")
        if isinstance(self.queue_length, bool) or not isinstance(self.queue_length, int):
            raise TypeError("queue_length must be an integer")
        if self.queue_length < 0:
            raise ValueError("queue_length must be non-negative")
        object.__setattr__(
            self,
            "affinity_target",
            _identifier("affinity_target", self.affinity_target, allow_none=True),
        )
        if isinstance(self.allowed_cargo_types, (str, bytes, bytearray)):
            raise TypeError("allowed_cargo_types must be a sequence of strings")
        try:
            cargo_types = tuple(self.allowed_cargo_types)
        except TypeError as exc:
            raise TypeError("allowed_cargo_types must be a sequence of strings") from exc
        if not cargo_types or any(not isinstance(item, str) or not item.strip() for item in cargo_types):
            raise ValueError("allowed_cargo_types must contain non-empty strings")
        if len(set(cargo_types)) != len(cargo_types):
            raise ValueError("allowed_cargo_types must not contain duplicates")
        object.__setattr__(self, "allowed_cargo_types", cargo_types)

    @property
    def is_resource_available(self) -> bool:
        return self.resource_available and self.resource_status == "available"

    @property
    def resource_failed(self) -> bool:
        return self.resource_status == "failed" or not self.resource_available


def _fifo_reference(candidates: tuple[Candidate, ...]) -> Candidate:
    """Return the deterministic FIFO reference among admissible candidates."""

    if not candidates:
        raise ValueError("FIFO reference requires at least one candidate")
    return min(
        candidates,
        key=lambda candidate: (
            candidate.stage_entry_time,
            candidate.truck_id,
        ),
    )


def _activated_rules(
    *,
    candidates: tuple[Candidate, ...],
    excluded: tuple[tuple[str, str], ...],
    context: DispatchContext,
    policy_name: str,
    fifo_break: bool,
) -> tuple[str, ...]:
    """Build the ordered rule list persisted in every recommendation."""

    rules: list[str] = [
        "resource_available",
        "truck_arrived",
        "document_released",
    ]
    if context.operation is not None or any(candidate.operation is not None for candidate in candidates):
        rules.append("stage_compatibility")
    has_resource_compatibility = context.resource_id is not None and bool(
        context.allowed_cargo_types
    )
    exclusion_reasons = tuple(reason.casefold() for _, reason in excluded)
    has_resource_block = any(
        "resource mismatch" in reason or "cargo" in reason for reason in exclusion_reasons
    )
    if has_resource_compatibility or has_resource_block:
        rules.append("resource_compatibility")
    if excluded:
        rules.append("excluded_candidates")
        if has_resource_block:
            rules.append("resource_blocked")
        if any("future" in reason for reason in exclusion_reasons):
            rules.append("arrival_window")
    rules.extend(_POLICY_JUSTIFICATION_RULES.get(policy_name, ()))
    rules.append(f"policy:{policy_name}")
    rules.append("fifo_override" if fifo_break else "fifo_order")
    return tuple(rules)


def _build_justification(
    *,
    selected: Candidate,
    candidates: tuple[Candidate, ...],
    excluded: tuple[tuple[str, str], ...],
    context: DispatchContext,
    policy_name: str,
) -> DecisionJustification | None:
    """Construct A2 evidence when the decision has explicit stage/resource.

    Direct callers may use the low-level dispatcher without naming an
    operation or resource.  Such a recommendation remains inspectable, but
    its serialization fails closed in :meth:`Recommendation.to_dict`; no
    placeholder stage or resource is invented.
    """

    stage = context.operation if context.operation is not None else selected.operation
    if stage is None or context.resource_id is None:
        return None
    fifo_reference = _fifo_reference(candidates)
    fifo_break = selected.truck_id != fifo_reference.truck_id
    fifo_sentence = (
        f"FIFO order broken: {selected.truck_id} precedes {fifo_reference.truck_id}"
        if fifo_break
        else "FIFO order preserved"
    )
    reason = (
        f"Selected truck {selected.truck_id} for stage {stage} on resource "
        f"{context.resource_id} under policy {policy_name}; {fifo_sentence}."
    )
    policy_rules = _POLICY_JUSTIFICATION_RULES.get(policy_name, ())
    if policy_rules:
        readable_rules = ", ".join(policy_rules)
        reason = f"{reason[:-1]}; applied rules: {readable_rules}."
    if any(
        "resource mismatch" in exclusion_reason.casefold()
        or "cargo" in exclusion_reason.casefold()
        for _, exclusion_reason in excluded
    ):
        reason = (
            f"{reason[:-1]}; a resource assignment was blocked by compatibility "
            "constraints."
        )
    return DecisionJustification(
        truck_stage={"truck_id": selected.truck_id, "stage": stage},
        resource={"resource_id": context.resource_id},
        activated_rules=_activated_rules(
            candidates=candidates,
            excluded=excluded,
            context=context,
            policy_name=policy_name,
            fifo_break=fifo_break,
        ),
        reason=reason,
        fifo_break=fifo_break,
    )


class NoFeasibleCandidate(RuntimeError):
    """Raised when hard constraints leave no admissible dispatch choice."""


class DispatchBlocked(NoFeasibleCandidate):
    """Raised when ``fifo_strict`` must idle behind an ineligible head truck."""

    def __init__(
        self,
        *,
        blocked_truck_id: str,
        resource_id: str | None,
        operation: str | None,
        excluded: tuple[tuple[str, str], ...],
    ) -> None:
        self.blocked_truck_id = blocked_truck_id
        self.resource_id = resource_id
        self.operation = operation
        self.excluded = tuple(excluded)
        reason = next(
            (text for truck_id, text in self.excluded if truck_id == blocked_truck_id),
            "head-of-line candidate is not eligible",
        )
        super().__init__(
            f"fifo_strict blocked at {blocked_truck_id}: {reason}"
        )


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A policy's selected candidate and its auditable ranking context."""

    selected: Candidate
    policy: str
    candidates: tuple[Candidate, ...]
    excluded: tuple[tuple[str, str], ...] = ()
    now: float = 0.0
    resource_id: str | None = None
    explanation: str = ""
    justification: DecisionJustification | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selected, Candidate):
            raise TypeError("selected must be a Candidate")
        if not isinstance(self.policy, str) or not self.policy:
            raise ValueError("policy must be a non-empty string")
        candidates = tuple(self.candidates)
        if not candidates:
            raise ValueError("candidates must not be empty")
        if any(not isinstance(candidate, Candidate) for candidate in candidates):
            raise TypeError("candidates must contain Candidate values")
        if self.selected not in candidates:
            raise ValueError("selected candidate must be in candidates")
        object.__setattr__(self, "candidates", candidates)
        excluded = tuple((str(identifier), str(reason)) for identifier, reason in self.excluded)
        object.__setattr__(self, "excluded", excluded)
        object.__setattr__(self, "now", _finite_nonnegative("now", self.now))
        object.__setattr__(
            self,
            "resource_id",
            _identifier("resource_id", self.resource_id, allow_none=True),
        )
        if self.justification is not None and not isinstance(
            self.justification, DecisionJustification
        ):
            raise TypeError("justification must be a DecisionJustification")
        if self.justification is not None:
            expected_stage = self.selected.operation
            if expected_stage is None:
                raise ValueError(
                    "recommendation justification requires an explicit selected operation"
                )
            if self.justification.truck_stage != {
                "truck_id": self.selected.truck_id,
                "stage": expected_stage,
            }:
                raise ValueError(
                    "recommendation justification stage must match the selected candidate"
                )
            if self.resource_id is None:
                raise ValueError(
                    "recommendation justification requires an explicit resource_id"
                )
            if self.justification.resource.get("resource_id") != self.resource_id:
                raise ValueError(
                    "recommendation justification resource must match resource_id"
                )

    @property
    def candidate(self) -> Candidate:
        return self.selected

    @property
    def selected_truck_id(self) -> str:
        return self.selected.truck_id

    @property
    def ranked_candidates(self) -> tuple[Candidate, ...]:
        return self.candidates

    def to_dict(self) -> dict[str, Any]:
        if self.justification is None:
            raise ValueError(
                "recommendation cannot be serialized without an explicit "
                "canonical decision justification"
            )
        fifo_reference = _fifo_reference(self.candidates)
        return {
            "type": "Recommendation",
            "policy": self.policy,
            "selected": self.selected.to_dict(),
            "candidate_ids": [candidate.truck_id for candidate in self.candidates],
            "excluded": [
                {"truck_id": truck_id, "reason": reason}
                for truck_id, reason in self.excluded
            ],
            "now": self.now,
            "resource_id": self.resource_id,
            "explanation": self.explanation,
            "justification": self.justification.to_dict(),
            "candidate_order": [
                {
                    "truck_id": candidate.truck_id,
                    "arrival_time": candidate.arrival_time,
                    "stable_order": candidate.stable_order,
                    "operation": candidate.operation,
                    "resource_id": candidate.resource_id,
                    "document_ok": candidate.document_ok,
                    "arrived": candidate.arrived,
                }
                for candidate in self.candidates
            ],
            "fifo_reference_truck_id": fifo_reference.truck_id,
        }


class DispatchPolicy(ABC):
    """Base interface: subclasses may rank, but never change feasibility."""

    name: str

    def select(
        self,
        candidates: Iterable[Candidate],
        context: DispatchContext,
    ) -> Candidate:
        values = tuple(candidates)
        if not values:
            raise NoFeasibleCandidate("no feasible candidates")
        if any(not isinstance(candidate, Candidate) for candidate in values):
            raise TypeError("candidates must contain Candidate values")
        if not isinstance(context, DispatchContext):
            raise TypeError("context must be a DispatchContext")
        if not context.is_resource_available:
            raise NoFeasibleCandidate(
                f"resource unavailable: {context.resource_id or 'unnamed resource'}"
            )
        selected = min(values, key=lambda candidate: self.rank_key(candidate, context, values))
        if not isinstance(selected, Candidate):  # defensive fail-closed boundary
            raise TypeError("policy returned an invalid candidate")
        return selected

    @abstractmethod
    def rank_key(
        self,
        candidate: Candidate,
        context: DispatchContext,
        candidates: tuple[Candidate, ...] = (),
    ) -> tuple[Any, ...]:
        """Return a deterministic key; lower keys are selected."""


def feasible_candidates(
    candidates: Iterable[Candidate],
    context: DispatchContext,
) -> tuple[tuple[Candidate, ...], tuple[tuple[str, str], ...]]:
    """Apply all hard constraints and return admissible values plus exclusions."""

    if not isinstance(context, DispatchContext):
        raise TypeError("context must be a DispatchContext")
    if not context.is_resource_available:
        raise NoFeasibleCandidate(
            f"resource unavailable: {context.resource_id or 'unnamed resource'}"
        )
    if isinstance(candidates, (str, bytes, bytearray)):
        raise TypeError("candidates must be an iterable of Candidate values")
    try:
        values = tuple(candidates)
    except TypeError as exc:
        raise TypeError("candidates must be an iterable of Candidate values") from exc
    if any(not isinstance(candidate, Candidate) for candidate in values):
        raise TypeError("candidates must contain Candidate values")

    seen: set[str] = set()
    feasible: list[Candidate] = []
    excluded: list[tuple[str, str]] = []
    for candidate in values:
        if candidate.truck_id in seen:
            raise ValueError(f"duplicate candidate truck_id: {candidate.truck_id}")
        seen.add(candidate.truck_id)
        if not candidate.arrived:
            excluded.append((candidate.truck_id, "truck not arrived"))
            continue
        if candidate.arrival_time > context.now:
            excluded.append((candidate.truck_id, "truck arrival is in the future"))
            continue
        if not candidate.eligible:
            excluded.append(
                (
                    candidate.truck_id,
                    candidate.eligibility_reason or "candidate is not eligible",
                )
            )
            continue
        if not candidate.document_ok:
            excluded.append((candidate.truck_id, "document blocked"))
            continue
        if context.operation is not None and candidate.operation is not None:
            if candidate.operation != context.operation:
                excluded.append((candidate.truck_id, "operation mismatch"))
                continue
        if context.resource_id is not None and candidate.resource_id is not None:
            if candidate.resource_id != context.resource_id:
                excluded.append((candidate.truck_id, "resource mismatch"))
                continue
        if candidate.cargo_type not in context.allowed_cargo_types:
            excluded.append(
                (
                    candidate.truck_id,
                    f"cargo type {candidate.cargo_type!r} is incompatible with resource",
                )
            )
            continue
        feasible.append(candidate)

    if not feasible:
        reason = "no feasible candidates"
        if excluded and all(reason_text == "document blocked" for _, reason_text in excluded):
            reason = "no feasible candidates: document blocked"
        raise NoFeasibleCandidate(reason)
    return tuple(feasible), tuple(excluded)


def recommend(
    candidates: Iterable[Candidate],
    context: DispatchContext,
    policy: DispatchPolicy,
) -> Recommendation:
    """Return one policy recommendation after hard-constraint filtering."""

    if not isinstance(policy, DispatchPolicy):
        raise TypeError("policy must be a DispatchPolicy")
    if not isinstance(context, DispatchContext):
        raise TypeError("context must be a DispatchContext")

    # An explicitly named operation is a public contract, not an optional
    # hint.  Validate it before filtering/ranking so an absent or divergent
    # candidate can never be selected and later acquire the context stage.
    if isinstance(candidates, (str, bytes, bytearray)):
        raise TypeError("candidates must be an iterable of Candidate values")
    try:
        candidate_values = tuple(candidates)
    except TypeError as exc:
        raise TypeError("candidates must be an iterable of Candidate values") from exc
    if any(not isinstance(candidate, Candidate) for candidate in candidate_values):
        raise TypeError("candidates must contain Candidate values")
    if context.operation is not None:
        for candidate in candidate_values:
            if candidate.operation is None:
                raise ValueError(
                    f"candidate {candidate.truck_id} has no operation for "
                    f"context operation {context.operation}"
                )
            if candidate.operation != context.operation:
                raise ValueError(
                    f"candidate {candidate.truck_id} operation {candidate.operation!r} "
                    f"diverges from context operation {context.operation!r}"
                )

    try:
        admissible, excluded = feasible_candidates(candidate_values, context)
    except NoFeasibleCandidate:
        if (
            policy.name == "fifo_strict"
            and context.is_resource_available
            and candidate_values
        ):
            head = _fifo_reference(tuple(candidate_values))
            raise DispatchBlocked(
                blocked_truck_id=head.truck_id,
                resource_id=context.resource_id,
                operation=context.operation,
                excluded=((head.truck_id, "no feasible candidate at queue head"),),
            ) from None
        raise
    if policy.name == "fifo_strict" and candidate_values:
        head = _fifo_reference(tuple(candidate_values))
        if head not in admissible:
            reason = next(
                (item for item in excluded if item[0] == head.truck_id),
                (head.truck_id, "head-of-line candidate is not eligible"),
            )
            raise DispatchBlocked(
                blocked_truck_id=head.truck_id,
                resource_id=context.resource_id,
                operation=context.operation,
                excluded=(reason,),
            )
    selected = policy.select(admissible, context)
    if selected not in admissible:
        raise ValueError("policy selected a candidate outside the feasible domain")
    justification = _build_justification(
        selected=selected,
        candidates=admissible,
        excluded=excluded,
        context=context,
        policy_name=policy.name,
    )
    explanation = (
        justification.reason
        if justification is not None
        else (
            f"{policy.name} selected {selected.truck_id} from "
            f"{len(admissible)} feasible candidate(s)"
        )
    )
    return Recommendation(
        selected=selected,
        policy=policy.name,
        candidates=admissible,
        excluded=excluded,
        now=context.now,
        resource_id=context.resource_id,
        explanation=explanation,
        justification=justification,
    )


__all__ = [
    "Candidate",
    "DecisionJustification",
    "DispatchContext",
    "DispatchPolicy",
    "NoFeasibleCandidate",
    "DispatchBlocked",
    "Recommendation",
    "JUSTIFICATION_FIELDS",
    "feasible_candidates",
    "recommend",
]
