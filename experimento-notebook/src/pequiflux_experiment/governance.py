"""Prospective study scope, bound to protocol identity rather than a skip flag."""

from .config import ExperimentConfig, validate_confirmatory_config


COMPUTATIONAL_PROTOCOL = "2.0.0"


def study_scope(config: ExperimentConfig) -> dict[str, str]:
    validate_confirmatory_config(config)
    if config.protocol_version == COMPUTATIONAL_PROTOCOL:
        return {
            "design": "computational_synthetic_comparison",
            "parameters": "engineering_assumptions_not_externally_validated",
            "face_validation": "not_evaluated_out_of_scope",
            "human_evaluation": "not_evaluated",
            "a1": "modelled_hard_constraints",
            "a2": "automated_traceability_and_reconstructibility",
            "claim_scope": "specified_synthetic_model_only",
        }
    return {
        "design": "synthetic_comparison_with_human_validation",
        "face_validation": "required",
        "human_evaluation": "required",
        "a1": "modelled_hard_constraints",
        "a2": "structural_and_human_review",
        "claim_scope": "specified_synthetic_model_only",
    }


def human_audit_status(config: ExperimentConfig) -> str:
    study_scope(config)
    return "not_evaluated" if config.protocol_version == COMPUTATIONAL_PROTOCOL else "pending"
