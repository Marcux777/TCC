"""Explicit synthetic responses for validation-only operator trials."""

from dataclasses import dataclass
from typing import Callable

from .dispatch import Candidate, Recommendation, feasible_candidates


SYNTHETIC_OPERATOR_PAYLOAD_VERSION = 1


@dataclass(frozen=True, slots=True)
class SyntheticOperatorResponse:
    action: str
    reason: str
    selected_truck_id: str | None = None

    def __post_init__(self) -> None:
        if self.action not in {"accept", "reject", "override"}:
            raise ValueError("synthetic operator action must be accept, reject or override")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("synthetic operator response requires a reason")
        if self.action == "override":
            if not isinstance(self.selected_truck_id, str) or not self.selected_truck_id.strip():
                raise ValueError("synthetic override requires selected_truck_id")
        elif self.selected_truck_id is not None:
            raise ValueError("only synthetic override may name another truck")

    def resolve(self, recommendation: Recommendation) -> Candidate | None:
        """Resolve within offered feasible candidates; executor enforces Cadm.

        Strict FIFO offers its full feasible queue to preserve head blocking,
        so the executor separately reapplies mandatory priority and the window.
        """
        if not isinstance(recommendation, Recommendation) or recommendation.context is None:
            raise TypeError("operator response requires a recommendation with dispatch context")
        if self.action == "reject":
            return None
        selected = recommendation.selected
        if self.action == "override":
            if self.selected_truck_id == selected.truck_id:
                raise ValueError("override must choose another admissible truck")
            selected = next((candidate for candidate in recommendation.candidates
                             if candidate.truck_id == self.selected_truck_id), None)
            if selected is None:
                raise ValueError("synthetic override target is outside the admissible candidate set")
        feasible_candidates((selected,), recommendation.context)
        return selected


SyntheticOperatorScript = Callable[[Recommendation], SyntheticOperatorResponse]
