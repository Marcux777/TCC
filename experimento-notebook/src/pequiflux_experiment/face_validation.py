"""Verifiable human face-validation receipt gate.

The receipt is an input artifact.  This module never fills reviewer fields or
silently promotes a template; any missing or divergent evidence is reported as
PENDING with its causal diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .config import ExperimentConfig, canonical_bytes, config_hash, validate_confirmatory_config


RUBRIC_RELATIVE_PATH = "inputs/face_validation_rubric.v1.json"
RUBRIC_VERSION = "face_validation_rubric.v1"
_RECEIPT_KEYS = {
    "status",
    "protocol_version",
    "config_hash",
    "source_document",
    "source_sha256",
    "round_id",
    "completed_at",
    "blind",
    "reviewer_ids",
    "rubric_path",
    "rubric_version",
    "rubric_sha256",
    "discrepancies",
    "final_decision",
}
_RUBRIC = {
    "rubric_version": RUBRIC_VERSION,
    "ratings": ["PASS", "REVISE", "FAIL"],
    "criteria": {
        "parameter_plausibility": {
            "question": "Os parâmetros estão dentro das faixas e unidades do protocolo?",
            "threshold": "todos os valores verificáveis no intervalo do PDF",
            "rationale_required": True,
        },
        "scenario_semantic_feasibility": {
            "question": "O cenário é semanticamente executável nas quatro etapas?",
            "threshold": "recursos, precedências e capacidades coerentes",
            "rationale_required": True,
        },
        "exemplar_trace_coherence": {
            "question": "Os exemplos e rastros correspondem às entradas e regras declaradas?",
            "threshold": "cada exemplar reconstrói sem contradição",
            "rationale_required": True,
        },
        "hard_constraint_consistency": {
            "question": "As restrições rígidas são aplicadas sem exceção silenciosa?",
            "threshold": "nenhuma violação aceita",
            "rationale_required": True,
        },
    },
    "decision_rule": "APPROVED somente com dois revisores independentes e todos os critérios PASS, ou divergências resolvidas e documentadas",
}
_TEMPLATE = {
    "status": "PENDING",
    "protocol_version": "",
    "config_hash": "",
    "source_document": "main.pdf",
    "source_sha256": "",
    "round_id": "",
    "completed_at": "",
    "blind": False,
    "reviewer_ids": [],
    "rubric_path": RUBRIC_RELATIVE_PATH,
    "rubric_version": RUBRIC_VERSION,
    "rubric_sha256": "",
    "discrepancies": [],
    "final_decision": "PENDING",
}


@dataclass(frozen=True, slots=True)
class FaceValidationReport:
    """Outcome of validating a face-validation receipt."""

    status: str
    cause: str
    receipt_path: Path | None = None
    protocol_version: str | None = None
    config_hash: str | None = None
    source_document: str | None = None
    source_sha256: str | None = None
    rubric_path: str | None = None
    rubric_version: str | None = None
    rubric_sha256: str | None = None

    @property
    def approved(self) -> bool:
        return self.status == "APPROVED"

    @property
    def face_validation(self) -> str:
        return self.status

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "cause": self.cause,
            "receipt_path": str(self.receipt_path) if self.receipt_path else None,
            "protocol_version": self.protocol_version,
            "config_hash": self.config_hash,
            "source_document": self.source_document,
            "source_sha256": self.source_sha256,
            "rubric_path": self.rubric_path,
            "rubric_version": self.rubric_version,
            "rubric_sha256": self.rubric_sha256,
        }


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pending(path: Path, cause: str, receipt: Mapping[str, Any] | None = None) -> FaceValidationReport:
    return FaceValidationReport(
        status="PENDING",
        cause=cause,
        receipt_path=path,
        protocol_version=receipt.get("protocol_version") if receipt else None,
        config_hash=receipt.get("config_hash") if receipt else None,
        source_document=receipt.get("source_document") if receipt else None,
        source_sha256=receipt.get("source_sha256") if receipt else None,
        rubric_path=receipt.get("rubric_path") if receipt else None,
        rubric_version=receipt.get("rubric_version") if receipt else None,
        rubric_sha256=receipt.get("rubric_sha256") if receipt else None,
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def materialize_face_validation_template(path: str | Path) -> Path:
    """Write the empty, versioned receipt template without human values."""

    target = Path(path)
    payload = canonical_bytes(_TEMPLATE)
    if target.exists():
        if not target.is_file():
            raise FileExistsError(f"face-validation template target is not a file: {target}")
        if target.read_bytes() != payload:
            raise FileExistsError(f"refusing to overwrite existing face-validation template: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def _resolve_rubric(project_root: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or relative_path != RUBRIC_RELATIVE_PATH:
        raise ValueError(f"rubric_path must be exactly {RUBRIC_RELATIVE_PATH}")
    candidate = Path(relative_path)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ValueError("rubric_path must be a relative path confined to the project root")
    resolved_root = project_root.resolve()
    resolved = (project_root / candidate).resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("rubric_path resolves outside the project root") from exc
    if not resolved.is_file():
        raise ValueError("rubric_path does not identify a regular file")
    return resolved


def _require_hex(name: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest") from exc
    return value.lower()


def _validate_reviewers(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("reviewer_ids must be a list")
    reviewers: list[str] = []
    for index, reviewer in enumerate(value):
        if not isinstance(reviewer, Mapping):
            raise ValueError(f"reviewer_ids[{index}] must be an object")
        if set(reviewer) != {"id", "independent"}:
            raise ValueError(f"reviewer_ids[{index}] must contain id and independent")
        identifier = reviewer["id"]
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"reviewer_ids[{index}].id must be non-empty")
        if reviewer["independent"] is not True:
            raise ValueError(f"reviewer_ids[{index}].independent must be true")
        reviewers.append(identifier.strip())
    if len(set(reviewers)) < 2:
        raise ValueError("at least two distinct independent reviewers are required")


def _validate_discrepancies(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("discrepancies must be a list")
    for index, discrepancy in enumerate(value):
        if not isinstance(discrepancy, Mapping):
            raise ValueError(f"discrepancies[{index}] must be an object")
        if set(discrepancy) != {"item", "decision", "rationale"}:
            raise ValueError(f"discrepancies[{index}] must contain item, decision, rationale")
        if not isinstance(discrepancy["item"], str) or not discrepancy["item"].strip():
            raise ValueError(f"discrepancies[{index}].item must be non-empty")
        if discrepancy["decision"] not in {"ADJUSTED", "MAINTAINED"}:
            raise ValueError(f"discrepancies[{index}].decision must be ADJUSTED or MAINTAINED")
        if not isinstance(discrepancy["rationale"], str) or not discrepancy["rationale"].strip():
            raise ValueError(f"discrepancies[{index}].rationale must be non-empty")


def validate_face_validation_receipt(
    path: str | Path,
    config: ExperimentConfig,
    pdf_path: str | Path,
) -> FaceValidationReport:
    """Validate a receipt against the frozen config, PDF and rubric bytes."""

    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    validate_confirmatory_config(config)
    receipt_path = Path(path)
    try:
        raw = _read_json(receipt_path)
    except FileNotFoundError as exc:
        return _pending(receipt_path, f"receipt is missing; APPROVED evidence is required: {exc}")
    except (json.JSONDecodeError, UnicodeError) as exc:
        return _pending(receipt_path, f"receipt JSON is invalid; APPROVED evidence is required: {exc}")
    if not isinstance(raw, dict):
        return _pending(receipt_path, "receipt root must be an object; APPROVED evidence is required")
    try:
        unknown = sorted(set(raw) - _RECEIPT_KEYS)
        missing = sorted(_RECEIPT_KEYS - set(raw))
        if unknown:
            raise ValueError(f"unknown receipt keys: {', '.join(unknown)}")
        if missing:
            raise ValueError(f"missing receipt keys: {', '.join(missing)}")
        if raw["status"] != "APPROVED" or raw["final_decision"] != "APPROVED":
            raise ValueError("status and final_decision must both be APPROVED")
        if raw["protocol_version"] != config.protocol_version:
            raise ValueError("protocol_version does not match the frozen config")
        if raw["config_hash"] != config_hash(config):
            raise ValueError("config_hash does not match the frozen config")
        if raw["source_document"] != "main.pdf":
            raise ValueError("source_document must be main.pdf")
        pdf = Path(pdf_path)
        if pdf.name != "main.pdf":
            raise ValueError("pdf_path must identify main.pdf")
        if not pdf.is_file():
            raise FileNotFoundError(f"source PDF is missing: {pdf}")
        source_hash = _sha256(pdf)
        if raw["source_sha256"] != source_hash:
            raise ValueError("source_sha256 does not match the real main.pdf bytes")
        if not isinstance(raw["round_id"], str) or not raw["round_id"].strip():
            raise ValueError("round_id must be non-empty")
        if not isinstance(raw["completed_at"], str) or not raw["completed_at"].strip():
            raise ValueError("completed_at must be an ISO-8601 timestamp")
        completed_at = datetime.fromisoformat(raw["completed_at"].replace("Z", "+00:00"))
        if completed_at.tzinfo is None or completed_at.utcoffset() is None:
            raise ValueError("completed_at must include an explicit timezone")
        if raw["blind"] is not True:
            raise ValueError("blind must be true")
        _validate_reviewers(raw["reviewer_ids"])
        rubric = _resolve_rubric(_project_root(), raw["rubric_path"])
        rubric_bytes = rubric.read_bytes()
        if raw["rubric_version"] != RUBRIC_VERSION:
            raise ValueError("rubric_version does not match the versioned rubric")
        rubric_hash = _sha256(rubric)
        if raw["rubric_sha256"] != rubric_hash:
            raise ValueError("rubric_sha256 does not match the real rubric bytes")
        rubric_payload = json.loads(rubric_bytes.decode("utf-8"))
        if rubric_payload != _RUBRIC:
            raise ValueError("rubric content does not match the frozen rubric")
        if rubric_bytes != canonical_bytes(rubric_payload):
            raise ValueError("rubric bytes must use canonical JSON serialization")
        _validate_discrepancies(raw["discrepancies"])
    except (OSError, ValueError, TypeError, json.JSONDecodeError, UnicodeError) as exc:
        return _pending(receipt_path, f"face-validation receipt rejected: {exc}", raw)
    return FaceValidationReport(
        status="APPROVED",
        cause="face-validation receipt APPROVED and hashes verified",
        receipt_path=receipt_path,
        protocol_version=raw["protocol_version"],
        config_hash=raw["config_hash"],
        source_document=raw["source_document"],
        source_sha256=raw["source_sha256"],
        rubric_path=raw["rubric_path"],
        rubric_version=raw["rubric_version"],
        rubric_sha256=raw["rubric_sha256"],
    )
