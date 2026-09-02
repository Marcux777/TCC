"""Deterministic ranking policies for the dispatch boundary."""

from __future__ import annotations

from typing import Any

from .dispatch import Candidate, DispatchContext, DispatchPolicy


def _stable_tail(candidate: Candidate) -> tuple[Any, ...]:
    # Stage entry is the only temporal order visible to a policy.  The global
    # construction order is physical bookkeeping, not queue age.
    return (candidate.stage_entry_time, candidate.truck_id)


class FifoStrictPolicy(DispatchPolicy):
    name = "fifo_strict"

    def rank_key(
        self,
        candidate: Candidate,
        context: DispatchContext,
        candidates: tuple[Candidate, ...] = (),
    ) -> tuple[Any, ...]:
        del context, candidates
        return _stable_tail(candidate)


class FifoFlowFaithfulPolicy(DispatchPolicy):
    name = "fifo_flow_faithful"

    def rank_key(
        self,
        candidate: Candidate,
        context: DispatchContext,
        candidates: tuple[Candidate, ...] = (),
    ) -> tuple[Any, ...]:
        del context, candidates
        return _stable_tail(candidate)


class PriorityLocalPolicy(DispatchPolicy):
    name = "priority_local"

    def rank_key(
        self,
        candidate: Candidate,
        context: DispatchContext,
        candidates: tuple[Candidate, ...] = (),
    ) -> tuple[Any, ...]:
        del context, candidates
        return (-candidate.priority, candidate.stage_entry_time, candidate.truck_id)


class FixedScorePolicy(DispatchPolicy):
    name = "fixed_score"
    WEIGHTS = (0.45, 0.35, 0.20)
    weights = WEIGHTS

    def rank_key(
        self,
        candidate: Candidate,
        context: DispatchContext,
        candidates: tuple[Candidate, ...] = (),
    ) -> tuple[Any, ...]:
        del context
        values = candidates or (candidate,)
        max_priority = max((item.priority for item in values), default=1)
        max_wait = max((item.waiting_time for item in values), default=1.0)
        priority_component = candidate.priority / max(1, max_priority)
        wait_component = candidate.waiting_time / max(1.0, max_wait)
        affinity_component = max(0.0, min(1.0, candidate.affinity))
        score = (
            self.WEIGHTS[0] * wait_component
            + self.WEIGHTS[1] * priority_component
            + self.WEIGHTS[2] * affinity_component
        )
        return (-score, candidate.stage_entry_time, candidate.truck_id)


class LexicographicPolicy(DispatchPolicy):
    name = "lexicographic"

    def rank_key(
        self,
        candidate: Candidate,
        context: DispatchContext,
        candidates: tuple[Candidate, ...] = (),
    ) -> tuple[Any, ...]:
        del context
        values = candidates or (candidate,)

        # Reordering is the canonical count of candidates that entered the
        # current stage earlier.  It is derived exclusively from the detached
        # candidate set, never accepted as caller-provided physical state.
        reorder_values = {
            item.truck_id: float(
                sum(
                    1
                    for other in values
                    if other.stage_entry_time < item.stage_entry_time
                )
            )
            for item in values
        }

        def normalized(value: float, maximum: float) -> float:
            return value / maximum if maximum > 0.0 else 0.0

        max_pressure = max((float(item.pressure) for item in values), default=0.0)
        max_wait = max((float(item.waiting_time) for item in values), default=0.0)
        max_reorder = max(reorder_values.values(), default=0.0)
        max_affinity = max((float(item.affinity) for item in values), default=0.0)
        reorder = reorder_values[candidate.truck_id]
        return (
            -normalized(candidate.pressure, max_pressure),
            -normalized(candidate.waiting_time, max_wait),
            normalized(reorder, max_reorder),
            -normalized(candidate.affinity, max_affinity),
            -candidate.priority,
            candidate.stage_entry_time,
            candidate.truck_id,
        )


_POLICY_TYPES = {
    "fifo_strict": FifoStrictPolicy,
    "fifo_flow_faithful": FifoFlowFaithfulPolicy,
    "priority_local": PriorityLocalPolicy,
    "fixed_score": FixedScorePolicy,
    "lexicographic": LexicographicPolicy,
}


def make_policy(name: str) -> DispatchPolicy:
    """Construct one of the frozen policy-panel implementations."""

    if not isinstance(name, str) or not name:
        raise ValueError("policy name must be a non-empty string")
    try:
        policy_type = _POLICY_TYPES[name]
    except KeyError as exc:
        expected = ", ".join(_POLICY_TYPES)
        raise ValueError(f"unknown policy {name!r}; expected one of: {expected}") from exc
    return policy_type()


POLICY_TYPES = dict(_POLICY_TYPES)

__all__ = [
    "DispatchPolicy",
    "FifoStrictPolicy",
    "FifoFlowFaithfulPolicy",
    "PriorityLocalPolicy",
    "FixedScorePolicy",
    "LexicographicPolicy",
    "POLICY_TYPES",
    "make_policy",
]
