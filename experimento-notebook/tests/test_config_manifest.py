from pathlib import Path
import hashlib
import inspect
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
    DatasetPlan,
    DatasetContractError,
    GenerationPlanReceipt,
    canonical_payload_schemas,
    load_frozen_dataset,
    plan_synthetic_dataset,
    validate_generation_headers,
    _prepare_destination,
    _read_jsonl,
)
from pequiflux_experiment.domain import (
    FrozenInstance,
    FrozenResource,
    FrozenServiceTime,
    FrozenTruck,
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


def test_generation_headers_receipt_is_non_publishing():
    plan = plan_synthetic_dataset(load_config(CONFIG_PATH))

    receipt = validate_generation_headers(
        plan.ordered_instance_headers,
        expected_plan=plan,
    )

    assert isinstance(receipt, GenerationPlanReceipt)
    assert (receipt.scenario_count, receipt.instance_count, receipt.policy_day_count) == (
        72,
        3_600,
        18_000,
    )
    assert receipt.ordered_instance_ids == plan.instance_ids
    assert not hasattr(receipt, "path")


def test_strict_loader_rejects_header_only_artifact(tmp_path):
    artifact = tmp_path / "header-only"
    artifact.mkdir()
    with pytest.raises(DatasetContractError, match="FREEZE|header-only|schema"):
        load_frozen_dataset(
            artifact,
            expected_plan=plan_synthetic_dataset(load_config(CONFIG_PATH)),
        )


def test_canonical_payload_schemas_are_exact():
    assert canonical_payload_schemas() == {
        "scenario_index.parquet": (
            "scenario_index", "scenario_id", "N", "hopper_count", "scale_count",
            "regime", "rho", "stratum", "protocol_version", "config_hash", "generator_version",
        ),
        "trucks.parquet": (
            "instance_id", "scenario_index", "scenario_id", "seed", "truck_id", "arrival_minute",
            "cargo_type", "priority", "document_status", "stage", "eligible_resources", "truck_record_hash",
        ),
        "service_times.parquet": (
            "instance_id", "scenario_index", "scenario_id", "seed", "truck_id", "operation",
            "duration_min", "source_a", "source_mode", "source_b", "draw_key", "crn_version",
            "service_record_hash",
        ),
    }


def test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order():
    truck = FrozenTruck(
        instance_id="s00-seed101",
        scenario_index=0,
        scenario_id="n60-m1-b1-nominal",
        seed=101,
        truck_id="T-001",
        arrival_minute=4.0,
        cargo_type="soy",
        priority=1,
        document_status="CLEAR",
        eligible_resources=("gate-1", "hopper-2"),
    )
    resource = FrozenResource("hopper-2", "hopper", ("soy",))
    service_late = FrozenServiceTime(
        instance_id=truck.instance_id,
        scenario_index=0,
        scenario_id=truck.scenario_id,
        seed=101,
        truck_id=truck.truck_id,
        operation="unload",
        duration_min=20.0,
        source_a=12.0,
        source_mode=20.0,
        source_b=35.0,
        draw_key="a" * 64,
        crn_version="crn.v1",
    )
    service_early = FrozenServiceTime(
        instance_id=truck.instance_id,
        scenario_index=0,
        scenario_id=truck.scenario_id,
        seed=101,
        truck_id=truck.truck_id,
        operation="gate",
        duration_min=4.0,
        source_a=2.0,
        source_mode=4.0,
        source_b=7.0,
        draw_key="b" * 64,
        crn_version="crn.v1",
    )
    instance = FrozenInstance(
        instance_id=truck.instance_id,
        scenario_index=0,
        scenario_id=truck.scenario_id,
        seed=101,
        generation_attempt=0,
        trucks=(truck,),
        resources=(resource,),
        service_times=(service_late, service_early),
    )
    round_trip = FrozenInstance.from_dict(instance.to_dict())

    assert round_trip.instance_hash == instance.instance_hash
    assert round_trip.trucks[0].cargo_type == "soy"
    assert round_trip.resources[0].allowed_cargo_types == ("soy",)
    assert tuple(item.operation for item in round_trip.service_times) == (
        "gate",
        "unload",
    )


def test_jsonl_loader_rejects_noncanonical_line_endings(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"a":1}\r\n')
    with pytest.raises(DatasetContractError, match="canonical|LF"):
        _read_jsonl(path, "events.jsonl")


def test_public_generator_has_no_test_injector():
    from pequiflux_experiment.dataset import generate_synthetic_dataset

    assert "rejection_injector" not in inspect.signature(generate_synthetic_dataset).parameters


def test_existing_destination_is_a_collision(tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        _prepare_destination(destination)


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
