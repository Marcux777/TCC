from pathlib import Path
import hashlib
import json

import pytest

from pequiflux_experiment.config import (
    CapacityRequirements,
    canonical_bytes,
    config_hash,
    factorial_scenarios,
    load_config,
)
from pequiflux_experiment.dataset import (
    DatasetContractError,
    generate_synthetic_dataset,
    plan_synthetic_dataset,
    validate_frozen_dataset,
)
import pequiflux_experiment.face_validation as face_validation
from pequiflux_experiment.face_validation import validate_face_validation_receipt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


@pytest.fixture
def approved_face():
    return type("ApprovedFace", (), {"status": "APPROVED"})()


def test_synthetic_plan_contract():
    plan = plan_synthetic_dataset(load_config(CONFIG_PATH))

    assert plan.scenario_indices == tuple(range(72))
    assert plan.instance_count == 3_600
    assert plan.policy_day_count == 18_000
    assert plan.instance_ids[0] == "s00-seed101"
    assert plan.instance_ids[-1] == "s71-seed150"


def test_generate_freezes_complete_dataset(tmp_path, approved_face, monkeypatch):
    plan = plan_synthetic_dataset(load_config(CONFIG_PATH))

    class HeaderMaterializerSpy:
        count = 0

        def __call__(self, header, writer):
            self.count += 1
            writer.write_header(
                {"instance_id": header.instance_id, "generation_attempt": 0}
            )

    writer = HeaderMaterializerSpy()
    monkeypatch.setattr(
        "pequiflux_experiment.dataset._materialize_production_header", writer
    )
    generate_synthetic_dataset(
        load_config(CONFIG_PATH),
        approved_face,
        tmp_path,
        now_utc="2026-09-03T12:00:00+00:00",
        generator_version="generator.v1",
    )

    assert writer.count == 3_600
    validate_frozen_dataset(tmp_path, expected_plan=plan, strict_production=True)


def test_production_refuses_incomplete_freeze(tmp_path, approved_face):
    del approved_face
    with pytest.raises(DatasetContractError, match="3,600"):
        validate_frozen_dataset(
            tmp_path,
            expected_plan=plan_synthetic_dataset(load_config(CONFIG_PATH)),
            strict_production=True,
        )


def test_config_contract_and_hash():
    cfg = load_config(CONFIG_PATH)
    scenarios = factorial_scenarios(cfg)

    assert len(scenarios) == 72
    assert scenarios[0].scenario_id == "n60-m1-b1-nominal"
    assert scenarios[-1].scenario_index == 71
    assert cfg.seeds == tuple(range(101, 151))
    assert cfg.policies == (
        "fifo_strict",
        "fifo_flow_faithful",
        "priority_local",
        "fixed_score",
        "lexicographic",
    )
    assert cfg.capacity == CapacityRequirements(
        min_free_ram_gib=4,
        reserve_ram_gib=2,
        max_workers=4,
        receipt_ttl_seconds=60,
    )
    assert config_hash(cfg) == config_hash(load_config(CONFIG_PATH))


def test_face_validation_receipt_gate():
    report = validate_face_validation_receipt(
        PROJECT_ROOT / "inputs" / "face_validation_receipt.json",
        load_config(CONFIG_PATH),
        PROJECT_ROOT.parent / "main.pdf",
    )

    assert report.status == "PENDING"
    assert "APPROVED" in report.cause


def test_face_validation_rejects_noncanonical_rubric_bytes(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    rubric_path = project_root / "inputs" / "face_validation_rubric.v1.json"
    rubric_path.parent.mkdir(parents=True)
    rubric_payload = json.loads(
        (PROJECT_ROOT / "inputs" / "face_validation_rubric.v1.json").read_text(
            encoding="utf-8"
        )
    )
    rubric_path.write_text(
        json.dumps(rubric_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(face_validation, "_project_root", lambda: project_root)

    cfg = load_config(CONFIG_PATH)
    pdf_path = PROJECT_ROOT.parent / "main.pdf"
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = {
        "status": "APPROVED",
        "protocol_version": cfg.protocol_version,
        "config_hash": config_hash(cfg),
        "source_document": "main.pdf",
        "source_sha256": digest(pdf_path),
        "round_id": "noncanonical-rubric",
        "completed_at": "2026-09-03T12:00:00-03:00",
        "blind": True,
        "reviewer_ids": [
            {"id": "reviewer-a", "independent": True},
            {"id": "reviewer-b", "independent": True},
        ],
        "rubric_path": "inputs/face_validation_rubric.v1.json",
        "rubric_version": "face_validation_rubric.v1",
        "rubric_sha256": digest(rubric_path),
        "discrepancies": [
            {"item": "format", "decision": "MAINTAINED", "rationale": "unchanged"}
        ],
        "final_decision": "APPROVED",
    }
    receipt_path = project_root / "receipt.json"
    receipt_path.write_bytes(canonical_bytes(receipt))

    report = validate_face_validation_receipt(receipt_path, cfg, pdf_path)

    assert report.status == "PENDING"
    assert "canonical" in report.cause.lower()
