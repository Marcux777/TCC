from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace
from decimal import Decimal
import hashlib
import inspect
import json
import os
import shutil

import pytest

from pequiflux_experiment.config import (
    CapacityRequirements,
    canonical_bytes,
    config_hash,
    crn_digest,
    factorial_scenarios,
    load_config,
)
from pequiflux_experiment.dataset import (
    DatasetPlan,
    DatasetContractError,
    FaceValidationError,
    GenerationPlanReceipt,
    GenerationRejectedError,
    _install_tiny_generation_fixture,
    canonical_payload_schemas,
    canonical_event_latent_schema,
    derive_controlled_instance,
    generate_synthetic_dataset,
    load_event_latents,
    load_aborted_staging,
    load_freeze_receipt,
    load_frozen_dataset,
    plan_synthetic_dataset,
    probe_generation_attempt,
    read_instance_header,
    resample_synthetic_dataset,
    validate_generation_headers,
    _prepare_destination,
    _read_jsonl,
    _validate_disruption_event_type,
    _validate_approved_face,
)
import pequiflux_experiment.dataset as dataset_module
from pequiflux_experiment.domain import (
    ControlledProjection,
    EventLatentLedger,
    ExecutionControls,
    FrozenInstance,
    FrozenResource,
    FrozenServiceTime,
    FrozenTruck,
)
import pequiflux_experiment.face_validation as face_validation
from pequiflux_experiment.face_validation import FaceValidationReport, validate_face_validation_receipt
from pequiflux_experiment.manifest import canonical_file_hash, dataset_root_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


def _tiny_payload_manifest(root: Path, dataset_id: str) -> tuple[dict, list[tuple[str, str]]]:
    """Create only tiny arbitrary payload bytes for hash-chain boundary tests."""

    from pequiflux_experiment.dataset import _PAYLOAD_NAMES, _build_manifest
    from pequiflux_experiment.manifest import canonical_file_hash

    root.mkdir(parents=True, exist_ok=True)
    for name in _PAYLOAD_NAMES:
        (root / name).write_bytes(name.encode("utf-8"))
    entries = [(name, canonical_file_hash(root / name)) for name in _PAYLOAD_NAMES]
    config = load_config(CONFIG_PATH)
    manifest = _build_manifest(
        config,
        plan_synthetic_dataset(config),
        Path(root.parent / dataset_id),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        "test-generator",
        tuple(entries),
        0,
        instance_hashes=[],
        cardinalities={
            "scenario_index": 72,
            "instances": 3_600,
            "trucks": 1,
            "service_times": 1,
            "disruptions": 0,
            "rejection_log": 0,
        },
    )
    manifest["dataset_id"] = dataset_id
    return manifest, entries


@pytest.fixture
def approved_face(tmp_path):
    """Build and validate a real APPROVED Task-1 receipt for current bytes."""

    cfg = load_config(CONFIG_PATH)
    pdf_path = PROJECT_ROOT.parent / "main.pdf"
    rubric_path = PROJECT_ROOT / "inputs" / "face_validation_rubric.v1.json"
    receipt = {
        "status": "APPROVED",
        "protocol_version": cfg.protocol_version,
        "config_hash": config_hash(cfg),
        "source_document": "main.pdf",
        "source_sha256": canonical_file_hash(pdf_path),
        "round_id": "task3-approved-fixture",
        "completed_at": "2026-09-03T12:00:00+00:00",
        "blind": True,
        "reviewer_ids": [
            {"id": "reviewer-a", "independent": True},
            {"id": "reviewer-b", "independent": True},
        ],
        "rubric_path": "inputs/face_validation_rubric.v1.json",
        "rubric_version": "face_validation_rubric.v1",
        "rubric_sha256": canonical_file_hash(rubric_path),
        "discrepancies": [
            {"item": "format", "decision": "MAINTAINED", "rationale": "unchanged"}
        ],
        "final_decision": "APPROVED",
    }
    receipt_path = tmp_path / "face-validation-approved.json"
    receipt_path.write_bytes(canonical_bytes(receipt))
    report = validate_face_validation_receipt(receipt_path, cfg, pdf_path)
    assert report.status == "APPROVED"
    return report


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


def test_checksum_chain_accepts_exact_six_payload_mapping(tmp_path):
    from pequiflux_experiment.dataset import _PAYLOAD_NAMES, _validate_checksum_chain
    from pequiflux_experiment.manifest import canonical_checksum_bytes, canonical_file_hash, dataset_root_hash, write_manifest

    root = tmp_path / "published"
    manifest, entries = _tiny_payload_manifest(root, root.name)
    write_manifest(root / "manifest.json", manifest)
    checksums = canonical_checksum_bytes(entries)
    (root / "checksums.sha256").write_bytes(checksums)
    manifest_hash = canonical_file_hash(root / "manifest.json")
    checksums_hash = hashlib.sha256(checksums).hexdigest()
    (root / "FREEZE.json").write_bytes(
        canonical_bytes(
            {
                "manifest_hash": manifest_hash,
                "checksums_hash": checksums_hash,
                "dataset_root_hash": dataset_root_hash(manifest_hash, checksums_hash),
            }
        )
    )

    _loaded_manifest, observed = _validate_checksum_chain(root)

    assert tuple(observed) == tuple(_PAYLOAD_NAMES)
    assert observed == dict(entries)


def test_checksum_chain_rejects_manifest_extra_field(tmp_path):
    from pequiflux_experiment.dataset import _validate_checksum_chain
    from pequiflux_experiment.manifest import canonical_checksum_bytes, canonical_file_hash, dataset_root_hash, write_manifest

    root = tmp_path / "published"
    manifest, entries = _tiny_payload_manifest(root, root.name)
    manifest["unexpected"] = True
    write_manifest(root / "manifest.json", manifest)
    checksums = canonical_checksum_bytes(entries)
    (root / "checksums.sha256").write_bytes(checksums)
    manifest_hash = canonical_file_hash(root / "manifest.json")
    checksums_hash = hashlib.sha256(checksums).hexdigest()
    (root / "FREEZE.json").write_bytes(
        canonical_bytes(
            {
                "manifest_hash": manifest_hash,
                "checksums_hash": checksums_hash,
                "dataset_root_hash": dataset_root_hash(manifest_hash, checksums_hash),
            }
        )
    )

    with pytest.raises(DatasetContractError, match="unexpected fields"):
        _validate_checksum_chain(root)


def test_staging_validates_with_published_dataset_id_before_atomic_rename(tmp_path, monkeypatch):
    staging = tmp_path / ".published.staging-test"
    destination = tmp_path / "published"
    manifest, _entries = _tiny_payload_manifest(staging, destination.name)
    calls = []
    monkeypatch.setattr(
        dataset_module,
        "_load_frozen_dataset",
        lambda path, expected_plan=None, published_dataset_id=None: calls.append(
            (Path(path).name, published_dataset_id)
        ) or "validated",
    )

    assert dataset_module._finalize_freeze(staging, manifest) == "validated"
    assert calls == [(staging.name, destination.name)]
    os.replace(staging, destination)
    assert destination.is_dir()
    assert not staging.exists()


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
        draw_key=crn_digest("crn.v1", 0, 101, 0, "T-001", "unload"),
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
        draw_key=crn_digest("crn.v1", 0, 101, 0, "T-001", "gate"),
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


def test_frozen_service_rejects_forged_crn_draw_key():
    with pytest.raises(ValueError, match="draw_key"):
        FrozenServiceTime(
            instance_id="s00-seed101",
            scenario_index=0,
            scenario_id="n60-m1-b1-nominal",
            seed=101,
            truck_id="T-001",
            operation="gate",
            duration_min=4.0,
            source_a=2.0,
            source_mode=4.0,
            source_b=7.0,
            draw_key="a" * 64,
            crn_version="crn.v1",
        )


@pytest.mark.parametrize("event_type", ["unknown", "arrival", ""])
def test_disruption_event_type_is_closed(event_type):
    with pytest.raises(DatasetContractError, match="event_type"):
        _validate_disruption_event_type(event_type)


@pytest.mark.parametrize(
    ("frozen_parameters", "message"),
    [(None, "frozen_parameters"), ({}, "service_distributions"), ({"service_distributions": {"gate": [1, 2, 3]}}, "service_distributions")],
)
def test_loader_rejects_missing_frozen_service_parameters(tmp_path, monkeypatch, frozen_parameters, message):
    root = tmp_path / "dataset"
    root.mkdir()
    truck = FrozenTruck(
        instance_id="s00-seed101",
        scenario_index=0,
        scenario_id="n60-m1-b1-nominal",
        seed=101,
        truck_id="T-001",
        arrival_minute=1.0,
        cargo_type="soy",
        priority=0,
        document_status="CLEAR",
        eligible_resources=("gate-1",),
    )
    manifest = {
        "dataset_id": root.name,
        "phase": "synthetic",
        "freeze_status": "FROZEN",
        "policy_days_executed": False,
        "parameters": {"seeds": list(range(101, 151))},
        "frozen_parameters": frozen_parameters,
    }
    monkeypatch.setattr(
        dataset_module,
        "_read_payloads",
        lambda _root: ([], [truck.to_dict()], [], [], []),
    )
    monkeypatch.setattr(
        dataset_module,
        "_validate_scenario_rows",
        lambda _rows, _manifest, _plan: {
            0: {
                "scenario_id": "n60-m1-b1-nominal",
                "N": 1,
                "hopper_count": 1,
                "scale_count": 1,
                "regime": "nominal",
            }
        },
    )
    monkeypatch.setattr(dataset_module, "_expected_instance_ids", lambda _manifest, _plan: ("s00-seed101",))

    with pytest.raises(DatasetContractError, match=message):
        dataset_module._validate_full_payloads(root, manifest, None)


def test_frozen_instance_service_order_keeps_truck_identity():
    def make_truck(truck_id: str, arrival: float) -> FrozenTruck:
        return FrozenTruck(
            instance_id="s00-seed101",
            scenario_index=0,
            scenario_id="n60-m1-b1-nominal",
            seed=101,
            truck_id=truck_id,
            arrival_minute=arrival,
            cargo_type="soy",
            priority=1,
            document_status="CLEAR",
            eligible_resources=("gate-1",),
        )

    def make_service(truck_id: str, operation: str) -> FrozenServiceTime:
        distribution = {
            "gate": (2.0, 4.0, 7.0),
            "unload": (12.0, 20.0, 35.0),
        }[operation]
        return FrozenServiceTime(
            instance_id="s00-seed101",
            scenario_index=0,
            scenario_id="n60-m1-b1-nominal",
            seed=101,
            truck_id=truck_id,
            operation=operation,
            duration_min=distribution[1],
            source_a=distribution[0],
            source_mode=distribution[1],
            source_b=distribution[2],
            draw_key=crn_digest("crn.v1", 0, 101, 0, truck_id, operation),
            crn_version="crn.v1",
        )

    instance = FrozenInstance(
        instance_id="s00-seed101",
        scenario_index=0,
        scenario_id="n60-m1-b1-nominal",
        seed=101,
        generation_attempt=0,
        trucks=(make_truck("T-002", 2.0), make_truck("T-001", 8.0)),
        resources=(FrozenResource("gate-1", "gate", ("soy", "corn")),),
        service_times=(
            make_service("T-001", "unload"),
            make_service("T-002", "unload"),
            make_service("T-001", "gate"),
            make_service("T-002", "gate"),
        ),
    )

    assert [(item.truck_id, item.operation) for item in instance.service_times] == [
        ("T-002", "gate"),
        ("T-002", "unload"),
        ("T-001", "gate"),
        ("T-001", "unload"),
    ]


def test_jsonl_loader_rejects_noncanonical_line_endings(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"a":1}\r\n')
    with pytest.raises(DatasetContractError, match="canonical|LF"):
        _read_jsonl(path, "events.jsonl")


def test_public_generator_has_no_test_injector():
    from pequiflux_experiment.dataset import generate_synthetic_dataset

    assert "rejection_injector" not in inspect.signature(generate_synthetic_dataset).parameters


def test_fabricated_face_report_is_rejected_at_generation_boundary():
    config = load_config(CONFIG_PATH)
    fabricated = FaceValidationReport(
        status="APPROVED",
        cause="fabricated",
        receipt_path=PROJECT_ROOT / "inputs" / "face_validation_receipt.json",
    )

    with pytest.raises(FaceValidationError, match="exactly|receipt|revalidated"):
        _validate_approved_face(fabricated, config)


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


KNOWN_SHORTAGES = (
    ("n60-m2-b1-priority_shift", 119, "s11-seed119", "PRIORITY_SHIFT_ELIGIBLE_SHORTAGE"),
    ("n60-m3-b2-priority_shift", 141, "s23-seed141", "PRIORITY_SHIFT_ELIGIBLE_SHORTAGE"),
)
FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
STAGING_KEYS = {
    "status", "manifest_hash", "checksums_hash", "staging_root_hash",
    "accepted_instance_ids", "rejected_instance_ids", "next_candidate_ordinal",
}


def _build_tiny_final_freeze(tmp_path, approved_face, monkeypatch):
    """Materialize the real hash chain using only the private tiny fixture."""

    _install_tiny_generation_fixture(monkeypatch, tmp_path / "tiny-provenance-fixture.jsonl")
    with pytest.raises(GenerationRejectedError) as first_error:
        generate_synthetic_dataset(
            load_config(CONFIG_PATH), approved_face, tmp_path / "provenance-published-1",
            now_utc=FIXED_NOW, generator_version="generator.v1",
        )
    staging1 = load_aborted_staging(first_error.value.staging_path)
    with pytest.raises(GenerationRejectedError) as second_error:
        resample_synthetic_dataset(
            load_config(CONFIG_PATH), approved_face, staging1.path, staging1.staging_root_hash,
            ["s11-seed119"], tmp_path / "provenance-published-2",
            now_utc=FIXED_NOW, generator_version="generator.v1",
        )
    staging2 = load_aborted_staging(second_error.value.staging_path)
    resample_synthetic_dataset(
        load_config(CONFIG_PATH), approved_face, staging2.path, staging2.staging_root_hash,
        ["s23-seed141"], tmp_path / "provenance-published-3",
        now_utc=FIXED_NOW, generator_version="generator.v1",
    )
    return tmp_path / "provenance-published-3"


def _rewrite_manifest_root(root: Path, mutator) -> None:
    """Apply a manifest tamper while preserving its outer FREEZE hash chain."""

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    mutator(manifest)
    manifest_path.write_bytes(canonical_bytes(manifest))
    freeze_path = root / "FREEZE.json"
    freeze = json.loads(freeze_path.read_bytes())
    manifest_hash = canonical_file_hash(manifest_path)
    freeze["manifest_hash"] = manifest_hash
    freeze["dataset_root_hash"] = dataset_root_hash(manifest_hash, freeze["checksums_hash"])
    freeze_path.write_bytes(canonical_bytes(freeze))


def test_resample_provenance_persists_source_receipt_and_event_latent_maps(
    tmp_path, approved_face, monkeypatch
):
    """Each explicit resample records the complete source/latent provenance contract."""

    final_root = _build_tiny_final_freeze(tmp_path, approved_face, monkeypatch)
    manifest = json.loads((final_root / "manifest.json").read_bytes())
    provenance = manifest["resample_provenance"]
    expected_content_keys = {
        "source_staging_relpath",
        "source_staging_receipt_sha256",
        "source_dataset_id",
        "source_staging_root_hash",
        "resampled_instance_ids",
        "generation_attempts",
        "accepted_record_hashes",
        "accepted_instance_hashes",
        "prior_accepted_instance_hashes",
        "accepted_event_latent_hashes",
        "prior_accepted_event_latent_hashes",
        "authorizing_action",
    }
    assert expected_content_keys <= set(provenance)
    assert set(provenance["accepted_event_latent_hashes"]) == {"s23-seed141"}
    assert set(provenance["prior_accepted_event_latent_hashes"]) == {
        item["instance_id"] for item in json.loads((final_root / "manifest.json").read_bytes())["instance_headers"]
        if item["instance_id"] != "s23-seed141"
    }


def test_final_freeze_rejects_tampered_resample_provenance(tmp_path, approved_face, monkeypatch):
    final_root = _build_tiny_final_freeze(tmp_path, approved_face, monkeypatch)
    mutations = {
        "bytes": lambda root: (root / "resample_provenance.json").write_bytes(
            (root / "resample_provenance.json").read_bytes() + b" "
        ),
        "path": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"path": "wrong.json"}),
        ),
        "source_dataset_id": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"source_dataset_id": "tampered"}),
        ),
        "source_staging_root_hash": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"source_staging_root_hash": "0" * 64}),
        ),
        "resampled_instance_ids": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"resampled_instance_ids": ["s99-seed999"]}),
        ),
        "generation_attempts": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"generation_attempts": {"s23-seed141": 2}}),
        ),
        "accepted_record_hashes": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"accepted_record_hashes": {"s23-seed141": "0" * 64}}),
        ),
        "accepted_instance_hashes": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"accepted_instance_hashes": {"s23-seed141": "0" * 64}}),
        ),
        "prior_accepted_instance_hashes": lambda root: _rewrite_manifest_root(
            root,
            lambda manifest: manifest["resample_provenance"].update({"prior_accepted_instance_hashes": {"s00-seed101": "0" * 64}}),
        ),
    }
    for label, mutate in mutations.items():
        tampered_root = tmp_path / f"tampered-{label}"
        shutil.copytree(final_root, tampered_root)
        mutate(tampered_root)
        with pytest.raises(DatasetContractError, match="provenance"):
            load_freeze_receipt(tampered_root)


def test_probe_diagnoses_both_without_publishing(approved_face):
    config = load_config(CONFIG_PATH)
    plan = plan_synthetic_dataset(config)
    probe = probe_generation_attempt(
        config,
        approved_face,
        plan.ordered_instance_headers,
        generation_attempt=0,
    )
    assert probe.status == "DIAGNOSTIC"
    assert probe.publishing is False
    assert probe.aborted_staging is None
    assert probe.authorization is None
    assert probe.rejected_instance_ids == tuple(item[2] for item in KNOWN_SHORTAGES)
    assert [
        (row.instance_id, row.generation_attempt, row.reason_code, row.validator)
        for row in probe.rejection_rows
    ] == [
        (item[2], 0, item[3], "canonical_semantic_validator")
        for item in KNOWN_SHORTAGES
    ]


def test_fail_fast_persisted_resample_sequence(tmp_path, approved_face, monkeypatch):
    config = load_config(CONFIG_PATH)
    plan = plan_synthetic_dataset(config)
    fixture_path = tmp_path / "tiny-generation-fixture.jsonl"
    _install_tiny_generation_fixture(monkeypatch, fixture_path)

    with pytest.raises(GenerationRejectedError, match="s11-seed119") as first_error:
        generate_synthetic_dataset(
            config, approved_face, tmp_path / "published-1",
            now_utc=FIXED_NOW, generator_version="generator.v1",
        )
    staging1 = load_aborted_staging(first_error.value.staging_path)
    assert not (tmp_path / "published-1").exists()
    assert set(staging1.staging_json) == STAGING_KEYS
    assert staging1.staging_json["status"] == "ABORTED"
    assert not (staging1.path / "FREEZE.json").exists()
    assert staging1.chain_valid is True
    assert staging1.recomputed_staging_root_hash == staging1.staging_root_hash
    assert staging1.rejected_instance_ids == ("s11-seed119",)
    assert staging1.next_candidate_ordinal == plan.next_ordinal_after("s11-seed119")
    assert set(staging1.accepted_instance_ids).isdisjoint(staging1.rejected_instance_ids)
    assert set(staging1.accepted_instance_ids) | set(staging1.rejected_instance_ids) | set(staging1.remaining_instance_ids) == set(plan.instance_ids)
    assert [
        (row.instance_id, row.generation_attempt, row.reason_code, row.automatic_resample_status, row.next_action)
        for row in staging1.rejection_rows
    ] == [
        ("s11-seed119", 0, "PRIORITY_SHIFT_ELIGIBLE_SHORTAGE", "PROHIBITED", "EXPLICIT_RESAMPLE_REQUIRED")
    ]
    accepted_hash = read_instance_header(staging1.path, "s00-seed101").canonical_record_hash

    with pytest.raises(GenerationRejectedError, match="s23-seed141") as second_error:
        resample_synthetic_dataset(
            config, approved_face, staging1.path, staging1.staging_root_hash,
            ["s11-seed119"], tmp_path / "published-2",
            now_utc=FIXED_NOW, generator_version="generator.v1",
        )
    staging2 = load_aborted_staging(second_error.value.staging_path)
    assert not (tmp_path / "published-2").exists()
    assert set(staging2.staging_json) == STAGING_KEYS
    assert staging2.staging_json["status"] == "ABORTED"
    assert not (staging2.path / "FREEZE.json").exists()
    assert staging2.rejected_instance_ids == ("s23-seed141",)
    assert staging2.next_candidate_ordinal == plan.next_ordinal_after("s23-seed141")
    assert staging2.chain_valid is True
    assert staging2.recomputed_staging_root_hash == staging2.staging_root_hash
    assert set(staging2.accepted_instance_ids).isdisjoint(staging2.rejected_instance_ids)
    assert set(staging2.accepted_instance_ids) | set(staging2.rejected_instance_ids) | set(staging2.remaining_instance_ids) == set(plan.instance_ids)
    assert read_instance_header(staging2.path, "s00-seed101").canonical_record_hash == accepted_hash
    assert read_instance_header(staging2.path, "s11-seed119").generation_attempt == 1
    assert staging2.rejection_rows[0].generation_attempt == 0
    assert staging2.rejection_rows[0].next_action == "EXPLICIT_RESAMPLE_REQUIRED"
    provenance1_path = staging2.path / "resample_provenance.json"
    provenance1_raw = provenance1_path.read_bytes()
    provenance1 = json.loads(provenance1_raw)
    assert provenance1_raw == canonical_bytes(provenance1)
    assert provenance1["source_dataset_id"] == staging1.dataset_id
    assert provenance1["source_staging_root_hash"] == staging1.staging_root_hash
    assert provenance1["resampled_instance_ids"] == ["s11-seed119"]
    assert provenance1["generation_attempts"] == {"s11-seed119": 1}
    assert read_instance_header(staging2.path, "s11-seed119").canonical_record_hash == provenance1["accepted_instance_hashes"]["s11-seed119"]
    assert staging2.manifest["resample_provenance"]["sha256"] == dataset_module.canonical_file_hash(provenance1_path)

    resample_synthetic_dataset(
        config, approved_face, staging2.path, staging2.staging_root_hash,
        ["s23-seed141"], tmp_path / "published-3",
        now_utc=FIXED_NOW, generator_version="generator.v1",
    )
    freeze_receipt = load_freeze_receipt(tmp_path / "published-3")
    assert freeze_receipt.manifest["freeze_status"] == "FROZEN"
    assert freeze_receipt.manifest["instance_count"] == 3_600
    assert freeze_receipt.manifest["policy_day_count"] == 18_000
    assert freeze_receipt.manifest["generation_plan_receipt"]["instance_count"] == 3_600
    assert freeze_receipt.manifest["generation_plan_receipt"]["policy_day_count"] == 18_000
    s00_header = read_instance_header(tmp_path / "published-3", "s00-seed101")
    s11_header = read_instance_header(tmp_path / "published-3", "s11-seed119")
    s23_header = read_instance_header(tmp_path / "published-3", "s23-seed141")
    assert s11_header.generation_attempt == 1
    assert s23_header.generation_attempt == 1
    assert s00_header.canonical_record_hash == accepted_hash
    provenance2_path = tmp_path / "published-3" / "resample_provenance.json"
    provenance2_raw = provenance2_path.read_bytes()
    provenance2 = json.loads(provenance2_raw)
    assert provenance2_raw == canonical_bytes(provenance2)
    assert provenance2["source_dataset_id"] == staging2.dataset_id
    assert provenance2["source_staging_root_hash"] == staging2.staging_root_hash
    assert provenance2["resampled_instance_ids"] == ["s23-seed141"]
    assert provenance2["generation_attempts"] == {"s23-seed141": 1}
    assert s23_header.canonical_record_hash == provenance2["accepted_instance_hashes"]["s23-seed141"]
    assert s00_header.canonical_record_hash == provenance2["prior_accepted_instance_hashes"]["s00-seed101"]
    assert freeze_receipt.manifest["resample_provenance"]["sha256"] == dataset_module.canonical_file_hash(provenance2_path)
    assert (tmp_path / "published-3" / "FREEZE.json").exists()
    assert not (tmp_path / "published-3" / "STAGING.json").exists()


def test_new_rejection_aborts_without_retry(tmp_path, approved_face, monkeypatch):
    fixture_path = tmp_path / "tiny-generation-fixture-new-rejection.jsonl"
    _install_tiny_generation_fixture(monkeypatch, fixture_path)

    with pytest.raises(GenerationRejectedError, match="s11-seed119") as first_error:
        generate_synthetic_dataset(
            load_config(CONFIG_PATH), approved_face, tmp_path / "source-published",
            now_utc=FIXED_NOW, generator_version="generator.v1",
        )
    source = load_aborted_staging(first_error.value.staging_path)
    assert source.rejected_instance_ids == ("s11-seed119",)

    monkeypatch.setattr(
        "pequiflux_experiment.dataset._validate_candidate",
        lambda candidate: candidate.instance_id != "s11-seed119",
    )
    with pytest.raises(GenerationRejectedError, match="s11-seed119") as second_error:
        resample_synthetic_dataset(
            load_config(CONFIG_PATH), approved_face, source.path, source.staging_root_hash,
            ["s11-seed119"], tmp_path / "retry-published",
            now_utc=FIXED_NOW, generator_version="generator.v1",
        )
    retained = load_aborted_staging(second_error.value.staging_path)
    assert retained.path != source.path
    assert set(retained.staging_json) == STAGING_KEYS
    assert retained.staging_json["status"] == "ABORTED"
    assert not (retained.path / "FREEZE.json").exists()
    assert not (tmp_path / "retry-published").exists()
    assert retained.rejected_instance_ids == ("s11-seed119",)
    assert retained.chain_valid is True
    assert retained.recomputed_staging_root_hash == retained.staging_root_hash
    assert retained.rejection_rows[0].generation_attempt == 1
    assert retained.rejection_rows[0].automatic_resample_status == "PROHIBITED"
    assert retained.rejection_rows[0].next_action == "EXPLICIT_RESAMPLE_REQUIRED"


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


def _write_tiny_chain(root: Path, manifest: dict | None = None) -> dict:
    """Write the tiny canonical hash-chain fixture and return its manifest."""

    from pequiflux_experiment.manifest import canonical_checksum_bytes, canonical_file_hash, dataset_root_hash, write_manifest

    if manifest is None:
        manifest, entries = _tiny_payload_manifest(root, root.name)
    else:
        entries = [(name, dataset_module.canonical_file_hash(root / name)) for name in dataset_module._PAYLOAD_NAMES]
    write_manifest(root / "manifest.json", manifest)
    checksums = canonical_checksum_bytes(entries)
    (root / "checksums.sha256").write_bytes(checksums)
    manifest_hash = canonical_file_hash(root / "manifest.json")
    checksums_hash = hashlib.sha256(checksums).hexdigest()
    (root / "FREEZE.json").write_bytes(
        canonical_bytes(
            {
                "manifest_hash": manifest_hash,
                "checksums_hash": checksums_hash,
                "dataset_root_hash": dataset_root_hash(manifest_hash, checksums_hash),
            }
        )
    )
    return manifest


@pytest.mark.parametrize("extra_name", ["STAGING.json", "resample_provenance.json", "unexpected.bin"])
def test_initial_freeze_rejects_namespace_extras(tmp_path, extra_name):
    root = tmp_path / "published"
    root.mkdir()
    _write_tiny_chain(root)
    (root / extra_name).write_bytes(b"{}")

    with pytest.raises(DatasetContractError, match="namespace|unexpected|inventory"):
        dataset_module._validate_checksum_chain(root)


@pytest.mark.parametrize("mutator", [
    lambda manifest: manifest.__setitem__("protocol_version", "9.9.9"),
    lambda manifest: manifest["parameters"]["event_ranks"].__setitem__("arrival", 31),
    lambda manifest: manifest["frozen_parameters"].__setitem__("horizon_minutes", 721),
    lambda manifest: manifest["frozen_parameters"]["service_distributions"].__setitem__("gate", [99.0, 100.0, 101.0]),
])
def test_manifest_configuration_is_anchored_to_current_config(tmp_path, mutator):
    root = tmp_path / "published"
    root.mkdir()
    manifest, _entries = _tiny_payload_manifest(root, root.name)
    mutator(manifest)
    _write_tiny_chain(root, manifest)

    with pytest.raises(DatasetContractError, match="canonical|configuration|config"):
        dataset_module._validate_checksum_chain(root)


@pytest.mark.parametrize(
    ("scenario", "row", "message"),
    [
        (
            {"scenario_id": "n60-m1-b1-nominal", "N": 60, "hopper_count": 1, "scale_count": 1, "regime": "nominal"},
            {"event_type": "rain_start", "resource_id": "hopper-1", "cause": "rain", "truck_id": "", "operation": "", "time": 10.0, "duration_min": 30.0, "return_time": 40.0, "event_rank": 13},
            "rain",
        ),
        (
            {"scenario_id": "n60-m1-b1-nominal", "N": 60, "hopper_count": 1, "scale_count": 1, "regime": "nominal"},
            {"event_type": "priority_change", "resource_id": "", "cause": "priority_shift", "truck_id": "T-001", "operation": "", "time": 10.0, "duration_min": 0.0, "return_time": 0.0, "event_rank": 21},
            "priority",
        ),
        (
            {"scenario_id": "n60-m1-b1-priority_shift", "N": 60, "hopper_count": 1, "scale_count": 1, "regime": "priority_shift"},
            {"event_type": "document_release", "resource_id": "", "cause": "document", "truck_id": "T-001", "operation": "gate", "time": 10.0, "duration_min": 0.0, "return_time": 0.0, "event_rank": 20},
            "document",
        ),
        (
            {"scenario_id": "n60-m1-b1-nominal", "N": 60, "hopper_count": 1, "scale_count": 1, "regime": "nominal"},
            {"event_type": "resource_failure", "resource_id": "hopper-1", "cause": "critical_failure", "truck_id": "", "operation": "", "time": 10.0, "duration_min": 30.0, "return_time": 40.0, "event_rank": 12},
            "failure",
        ),
    ],
)
def test_disruption_semantics_follow_canonical_scenario_rules(scenario, row, message):
    from pequiflux_experiment.dataset import _validate_disruption_semantics

    config = load_config(CONFIG_PATH)
    truck = FrozenTruck(
        instance_id="s00-seed101",
        scenario_index=0,
        scenario_id=scenario["scenario_id"],
        seed=101,
        truck_id="T-001",
        arrival_minute=1.0,
        cargo_type="soy",
        priority=1,
        document_status="CLEAR",
        eligible_resources=("gate-1", "hopper-1"),
    )
    row = {
        "instance_id": "s00-seed101",
        "scenario_index": 0,
        "scenario_id": scenario["scenario_id"],
        "seed": 101,
        "sequence": 1,
        "payload_hash": "0" * 64,
        **row,
    }
    with pytest.raises(DatasetContractError, match=message):
        _validate_disruption_semantics(
            (row,),
            scenario=scenario,
            trucks=(truck,),
            event_ranks=config.event_ranks,
            horizon_minutes=config.horizon_minutes,
        )


def test_disruption_return_time_must_remain_within_horizon():
    from pequiflux_experiment.dataset import _validate_disruption_semantics

    config = load_config(CONFIG_PATH)
    row = {
        "instance_id": "s00-seed101",
        "scenario_index": 0,
        "scenario_id": "n60-m1-b1-critical_failure",
        "seed": 101,
        "sequence": 1,
        "event_type": "resource_failure",
        "event_rank": 12,
        "resource_id": "hopper-1",
        "truck_id": "",
        "cause": "critical_failure",
        "operation": "",
        "time": 240.0,
        "duration_min": 20.0,
        "return_time": float(config.horizon_minutes) + 1.0,
        "payload_hash": "0" * 64,
    }
    with pytest.raises(DatasetContractError, match="horizon"):
        _validate_disruption_semantics(
            (row,),
            scenario={
                "scenario_id": "n60-m1-b1-critical_failure",
                "N": 60,
                "hopper_count": 1,
                "scale_count": 1,
                "regime": "critical_failure",
            },
            trucks=(),
            event_ranks=config.event_ranks,
            horizon_minutes=config.horizon_minutes,
            config=config,
        )


def _priority_fixture_rows(*, wrong_selection: bool = False, split_time: bool = False):
    config = load_config(CONFIG_PATH)
    scenario = {
        "scenario_id": "n60-m1-b1-priority_shift",
        "N": 60,
        "hopper_count": 1,
        "scale_count": 1,
        "regime": "priority_shift",
    }
    trucks = tuple(
        FrozenTruck(
            instance_id="s00-seed101",
            scenario_index=0,
            scenario_id=scenario["scenario_id"],
            seed=101,
            truck_id=f"T-{index:03d}",
            arrival_minute=250.0 + index,
            cargo_type="soy",
            priority=1,
            document_status="CLEAR",
            eligible_resources=("gate-1", "hopper-1"),
        )
        for index in range(1, 8)
    )
    selected = list(trucks)
    if wrong_selection:
        selected[5] = trucks[6]
    rows = []
    for sequence, truck in enumerate(selected, start=1):
        rows.append(
            {
                "instance_id": "s00-seed101",
                "scenario_index": 0,
                "scenario_id": scenario["scenario_id"],
                "seed": 101,
                "time": 240.0 + (1.0 if split_time and sequence == 1 else 0.0),
                "event_rank": 21,
                "resource_id": "",
                "truck_id": truck.truck_id,
                "sequence": sequence,
                "event_type": "priority_change",
                "cause": "priority_shift",
                "operation": "",
                "duration_min": 0.0,
                "return_time": 0.0,
                "payload_hash": "0" * 64,
            }
        )
    return config, scenario, trucks, tuple(rows)


@pytest.mark.parametrize("kwargs", [{"split_time": True}, {"wrong_selection": True}])
def test_priority_changes_require_one_shift_time_and_canonical_truck_order(kwargs):
    from pequiflux_experiment.dataset import _validate_disruption_semantics

    config, scenario, trucks, rows = _priority_fixture_rows(**kwargs)
    with pytest.raises(DatasetContractError, match="priority"):
        _validate_disruption_semantics(
            rows,
            scenario=scenario,
            trucks=trucks,
            event_ranks=config.event_ranks,
            horizon_minutes=config.horizon_minutes,
            config=config,
        )


def test_failure_return_time_must_equal_time_plus_duration():
    from pequiflux_experiment.dataset import _validate_disruption_semantics

    config = load_config(CONFIG_PATH)
    row = {
        "instance_id": "s00-seed101",
        "scenario_index": 0,
        "scenario_id": "n60-m1-b1-critical_failure",
        "seed": 101,
        "sequence": 1,
        "event_type": "resource_failure",
        "event_rank": 12,
        "resource_id": "hopper-1",
        "truck_id": "",
        "cause": "critical_failure",
        "operation": "",
        "time": 240.0,
        "duration_min": 20.0,
        "return_time": 261.0,
        "payload_hash": "0" * 64,
    }
    with pytest.raises(DatasetContractError, match="failure"):
        _validate_disruption_semantics(
            (row,),
            scenario={
                "scenario_id": "n60-m1-b1-critical_failure",
                "N": 60,
                "hopper_count": 1,
                "scale_count": 1,
                "regime": "critical_failure",
            },
            trucks=(),
            event_ranks=config.event_ranks,
            horizon_minutes=config.horizon_minutes,
            config=config,
        )


def test_rain_pairs_must_not_overlap_or_be_adjacent():
    from pequiflux_experiment.dataset import _validate_disruption_semantics

    config = load_config(CONFIG_PATH)
    scenario = {
        "scenario_id": "n60-m2-b1-nominal",
        "N": 60,
        "hopper_count": 2,
        "scale_count": 1,
        "regime": "nominal",
    }
    rows = []
    for sequence, (event_type, time, duration, return_time, rank) in enumerate(
        (
            ("rain_start", 0.0, 30.0, 30.0, 13),
            ("rain_end", 30.0, 0.0, 0.0, 11),
            ("rain_start", 30.0, 30.0, 60.0, 13),
            ("rain_end", 60.0, 0.0, 0.0, 11),
        ),
        start=1,
    ):
        rows.append(
            {
                "instance_id": "s00-seed101",
                "scenario_index": 0,
                "scenario_id": scenario["scenario_id"],
                "seed": 101,
                "time": time,
                "event_rank": rank,
                "resource_id": "hopper-1",
                "truck_id": "",
                "sequence": sequence,
                "event_type": event_type,
                "cause": "rain",
                "operation": "",
                "duration_min": duration,
                "return_time": return_time,
                "payload_hash": "0" * 64,
            }
        )
    with pytest.raises(DatasetContractError, match="rain"):
        _validate_disruption_semantics(
            tuple(rows),
            scenario=scenario,
            trucks=(),
            event_ranks=config.event_ranks,
            horizon_minutes=config.horizon_minutes,
            config=config,
        )


def _task25_instance_and_ledger(config, *, regime: str, hopper_count: int | None = None):
    scenarios = factorial_scenarios(config)
    scenario = next(
        item
        for item in scenarios
        if item.regime == regime
        and (hopper_count is None or item.hopper_count == hopper_count)
    )
    instance = dataset_module._build_instance(config, scenario, config.seeds[0], 0)
    ledger = dataset_module._build_event_latents(
        config, scenario, instance.seed, instance.generation_attempt, instance.trucks
    )
    return instance, ledger


def _task25_controls(ledger: EventLatentLedger, *, intensity: str) -> ExecutionControls:
    return ExecutionControls.build(
        ordinary_window=6,
        buffer_capacity=12,
        threshold_multiplier=Decimal("1.00"),
        intensity=intensity,
        source_dataset_root_hash="a" * 64,
        event_latents_sha256=ledger.event_latents_sha256,
    )


def test_event_latent_schema_and_legacy_loader_fail_fast(tmp_path):
    expected = {
        "envelope": (
            "instance_id", "scenario_index", "scenario_id", "seed",
            "generation_attempt", "latent_id", "latent_kind", "event_origin",
            "entity_id", "payload",
        ),
        "payload_variants": {
            "document": ("u", "u_draw_key", "release_duration_min", "release_duration_draw_key"),
            "base_failure": (
                "u", "u_draw_key", "resource_id", "resource_draw_key",
                "start_minute", "start_draw_key", "duration_min", "duration_draw_key",
            ),
            "priority_shift": (
                "u", "u_draw_key", "shift_time_minute", "candidate_truck_ids", "selected_truck_ids",
            ),
            "rain_block": (
                "u", "u_draw_key", "block_index", "resource_id", "start_minute", "duration_min", "end_minute",
            ),
            "forced_failure": (
                "forced_event_type", "resource_id", "start_minute", "start_draw_key",
                "duration_min", "duration_draw_key", "end_minute",
            ),
        },
        "latent_kind_order": ("document", "base_failure", "priority_shift", "rain_block", "forced_failure"),
    }
    assert canonical_event_latent_schema() == expected

    legacy = tmp_path / "legacy-v1"
    _write_tiny_chain(legacy)
    (legacy / "event_latents.jsonl").unlink()
    with pytest.raises(DatasetContractError, match="MISSING_EVENT_LATENTS"):
        load_frozen_dataset(legacy, expected_plan=plan_synthetic_dataset(load_config(CONFIG_PATH)))


def test_event_latent_roundtrip_and_high_projection(tmp_path):
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    payload = dataset_module._jsonl_bytes(ledger.to_rows(), "event_latents")
    path = tmp_path / "event_latents.jsonl"
    path.write_bytes(payload)
    loaded = load_event_latents(path)
    assert loaded.event_latents_sha256 == hashlib.sha256(payload).hexdigest()
    assert loaded.to_rows() == ledger.to_rows()

    base = derive_controlled_instance(instance, loaded, _task25_controls(loaded, intensity="base"))
    high = derive_controlled_instance(instance, loaded, _task25_controls(loaded, intensity="high"))
    assert base.instance_hash == instance.instance_hash
    assert base.disruptions == instance.disruptions
    assert [row["sequence"] for row in high.disruptions] == list(range(1, len(high.disruptions) + 1))
    base_non_rain = {
        row["latent_id"] for row in base.disruptions
        if row["event_type"] not in {"rain_start", "rain_end"}
    }
    high_non_rain = {
        row["latent_id"] for row in high.disruptions
        if row["event_type"] not in {"rain_start", "rain_end"}
    }
    assert base_non_rain <= high_non_rain
    active_blocks = {
        int(row["payload"]["block_index"])
        for row in loaded
        if row["latent_kind"] == "rain_block" and float(row["payload"]["u"]) < 0.20
    }
    covered_blocks: set[int] = set()
    for row in high.disruptions:
        if row["event_type"] == "rain_start":
            covered_blocks.update(range(int(float(row["time"]) / 30), int(float(row["return_time"]) / 30)))
        if row["event_type"] in {"rain_start", "rain_end"}:
            assert row["payload_hash"] == dataset_module._disruption_payload_hash(row)
    assert covered_blocks == active_blocks

    for regime in ("priority_shift", "critical_failure"):
        other, other_ledger = _task25_instance_and_ledger(config, regime=regime)
        other_base = derive_controlled_instance(other, other_ledger, _task25_controls(other_ledger, intensity="base"))
        other_high = derive_controlled_instance(other, other_ledger, _task25_controls(other_ledger, intensity="high"))
        for event_type in ("priority_change", "resource_failure"):
            if event_type == "resource_failure" and regime != "critical_failure":
                continue
            base_rows = tuple(row for row in other_base.disruptions if row["event_type"] == event_type)
            high_rows = tuple(row for row in other_high.disruptions if row["event_type"] == event_type)
            # High canonicalization may renumber the complete event stream (and
            # consequently each row hash) after appending overlays.  The
            # frozen forced/priority realization itself must remain unchanged.
            projection = lambda row: (
                row["event_type"], row["latent_id"], row["event_origin"],
                row["resource_id"], row["truck_id"], row["cause"],
                row["operation"], row["time"], row["duration_min"], row["return_time"],
            )
            assert tuple(map(projection, base_rows)) == tuple(map(projection, high_rows))


def test_controlled_projection_sidecar_hashes_are_deterministic_and_distinct():
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    base_controls = _task25_controls(ledger, intensity="base")
    high_controls = _task25_controls(ledger, intensity="high")

    base_projection = dataset_module.derive_controlled_projection(instance, ledger, base_controls)
    repeat_projection = dataset_module.derive_controlled_projection(instance, ledger, base_controls)
    high_projection = dataset_module.derive_controlled_projection(instance, ledger, high_controls)

    assert type(base_projection).__name__ == "ControlledProjection"
    assert base_projection.instance == derive_controlled_instance(instance, ledger, base_controls)
    assert base_projection.controlled_view_hash == repeat_projection.controlled_view_hash
    assert base_projection.event_overlay_hash == repeat_projection.event_overlay_hash
    assert base_projection.controlled_view_hash != high_projection.controlled_view_hash
    assert base_projection.event_overlay_hash != high_projection.event_overlay_hash
    for value in (
        base_projection.controlled_view_hash,
        base_projection.event_overlay_hash,
        high_projection.controlled_view_hash,
        high_projection.event_overlay_hash,
    ):
        assert isinstance(value, str) and len(value) == 64 and value == value.lower()


def test_controlled_projection_hashes_change_with_control_fields():
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    base_controls = _task25_controls(ledger, intensity="base")
    changed_controls = ExecutionControls.build(
        ordinary_window=base_controls.ordinary_window + 1,
        buffer_capacity=base_controls.buffer_capacity,
        threshold_multiplier=base_controls.threshold_multiplier,
        intensity=base_controls.intensity,
        source_dataset_root_hash=base_controls.source_dataset_root_hash,
        event_latents_sha256=base_controls.event_latents_sha256,
    )
    original = dataset_module.derive_controlled_projection(instance, ledger, base_controls)
    changed = dataset_module.derive_controlled_projection(instance, ledger, changed_controls)
    assert original.controlled_view_hash != changed.controlled_view_hash
    assert original.event_overlay_hash == changed.event_overlay_hash


def test_controlled_projection_rejects_forged_forced_origin_and_noncanonical_rain_id():
    config = load_config(CONFIG_PATH)
    critical_instance, critical_ledger = _task25_instance_and_ledger(config, regime="critical_failure")
    forced_rows = [dict(row) for row in critical_instance.disruptions]
    forced = next(row for row in forced_rows if row["event_type"] == "resource_failure")
    forced["event_origin"] = "sampled"
    forged_forced = replace(critical_instance, disruptions=tuple(forced_rows), canonical_record_hash=None, instance_hash=None)
    with pytest.raises(DatasetContractError, match="forced|origin"):
        dataset_module.derive_controlled_projection(
            forged_forced,
            critical_ledger,
            _task25_controls(critical_ledger, intensity="base"),
        )

    rain_instance, rain_ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    rain_rows = [dict(row) for row in rain_instance.disruptions]
    rain = next(row for row in rain_rows if row["event_type"] == "rain_start")
    rain["latent_id"] = rain["latent_id"].replace(":01-", ":1-")
    forged_rain = replace(rain_instance, disruptions=tuple(rain_rows), canonical_record_hash=None, instance_hash=None)
    with pytest.raises(DatasetContractError, match="rain|latent"):
        dataset_module.derive_controlled_projection(
            forged_rain,
            rain_ledger,
            _task25_controls(rain_ledger, intensity="base"),
        )


def test_controlled_projection_rejects_rain_entity_index_mismatch():
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    rows = [dict(row) for row in ledger.to_rows()]
    rain_rows = [row for row in rows if row["latent_kind"] == "rain_block"]
    first, second = rain_rows[:2]
    first_entity, second_entity = first["entity_id"], second["entity_id"]
    first["entity_id"], second["entity_id"] = second_entity, first_entity
    first["latent_id"] = f"{first['instance_id']}:rain_block:{first['entity_id']}"
    second["latent_id"] = f"{second['instance_id']}:rain_block:{second['entity_id']}"
    kind_order = {kind: index for index, kind in enumerate(("document", "base_failure", "priority_shift", "rain_block", "forced_failure"))}
    rows.sort(key=lambda row: (row["instance_id"], kind_order[row["latent_kind"]], row["entity_id"], row["latent_id"]))
    with pytest.raises((DatasetContractError, ValueError), match="rain|block|entity"):
        EventLatentLedger(tuple(rows))


def _assert_latent_rows_rejected(tmp_path, rows):
    with pytest.raises((ValueError, DatasetContractError)):
        EventLatentLedger(tuple(rows))
    path = tmp_path / "event_latents.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dataset_module._jsonl_bytes(rows, "event_latents"))
    with pytest.raises(DatasetContractError):
        load_event_latents(path)


@pytest.mark.parametrize("resource_id", ["hopper-3", "scale-2"])
def test_event_latent_ledger_rejects_resources_outside_scenario(tmp_path, resource_id):
    config = load_config(CONFIG_PATH)
    _instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=1)
    rows = [dict(row) for row in ledger.to_rows()]
    target = next(row for row in rows if row["latent_kind"] == "base_failure")
    target["payload"] = dict(target["payload"])
    target["payload"]["resource_id"] = resource_id
    _assert_latent_rows_rejected(tmp_path, rows)


def test_event_latent_ledger_rejects_scenario_id_rewrite(tmp_path):
    config = load_config(CONFIG_PATH)
    _instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=1)
    rows = [dict(row) for row in ledger.to_rows()]
    rows[0]["scenario_id"] = "n60-m1-b1-peak"
    _assert_latent_rows_rejected(tmp_path, rows)


def test_event_latent_ledger_rejects_rain_cardinality_for_m1_and_m2(tmp_path):
    config = load_config(CONFIG_PATH)
    m1_instance, m1_ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=1)
    m2_instance, m2_ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    m1_rows = [dict(row) for row in m1_ledger.to_rows()]
    rain = next(row for row in m2_ledger.to_rows() if row["latent_kind"] == "rain_block")
    rain = dict(rain)
    rain["instance_id"] = m1_instance.instance_id
    rain["scenario_index"] = m1_instance.scenario_index
    rain["scenario_id"] = m1_instance.scenario_id
    rain["seed"] = m1_instance.seed
    rain["generation_attempt"] = m1_instance.generation_attempt
    rain["latent_id"] = f"{m1_instance.instance_id}:rain_block:{rain['entity_id']}"
    rain["payload"] = dict(rain["payload"])
    rain["payload"]["u_draw_key"] = crn_digest(
        config.crn_version,
        m1_instance.scenario_index,
        m1_instance.seed,
        m1_instance.generation_attempt,
        "hopper-1",
        "rain_block_0",
    )
    m1_rows.append(rain)
    kind_order = {kind: index for index, kind in enumerate(("document", "base_failure", "priority_shift", "rain_block", "forced_failure"))}
    m1_rows.sort(key=lambda row: (row["instance_id"], kind_order[row["latent_kind"]], row["entity_id"], row["latent_id"]))
    _assert_latent_rows_rejected(tmp_path / "m1", m1_rows)

    m2_rows = [row for row in m2_ledger.to_rows() if row["entity_id"] != "rain-00"]
    _assert_latent_rows_rejected(tmp_path / "m2", m2_rows)


def test_event_latent_ledger_rejects_forced_and_priority_regime_mismatch(tmp_path):
    config = load_config(CONFIG_PATH)
    nominal_instance, nominal_ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=1)
    critical_instance, critical_ledger = _task25_instance_and_ledger(config, regime="critical_failure", hopper_count=1)
    forced = next(row for row in critical_ledger.to_rows() if row["latent_kind"] == "forced_failure")
    forced = dict(forced)
    forced["instance_id"] = nominal_instance.instance_id
    forced["scenario_index"] = nominal_instance.scenario_index
    forced["scenario_id"] = nominal_instance.scenario_id
    forced["seed"] = nominal_instance.seed
    forced["generation_attempt"] = nominal_instance.generation_attempt
    forced["latent_id"] = f"{nominal_instance.instance_id}:forced_failure:{forced['entity_id']}"
    forced["payload"] = dict(forced["payload"])
    forced["payload"]["start_draw_key"] = crn_digest(config.crn_version, nominal_instance.scenario_index, nominal_instance.seed, nominal_instance.generation_attempt, "yard", "critical_failure_start")
    forced["payload"]["duration_draw_key"] = crn_digest(config.crn_version, nominal_instance.scenario_index, nominal_instance.seed, nominal_instance.generation_attempt, "yard", "critical_failure_duration")
    _assert_latent_rows_rejected(tmp_path / "forced", [*nominal_ledger.to_rows(), forced])

    priority_instance, priority_ledger = _task25_instance_and_ledger(config, regime="priority_shift", hopper_count=1)
    priority = next(row for row in priority_ledger.to_rows() if row["latent_kind"] == "priority_shift")
    priority = dict(priority)
    priority["instance_id"] = nominal_instance.instance_id
    priority["scenario_index"] = nominal_instance.scenario_index
    priority["scenario_id"] = nominal_instance.scenario_id
    priority["seed"] = nominal_instance.seed
    priority["generation_attempt"] = nominal_instance.generation_attempt
    priority["latent_id"] = f"{nominal_instance.instance_id}:priority_shift:{priority['entity_id']}"
    priority["payload"] = dict(priority["payload"])
    priority["payload"]["u_draw_key"] = crn_digest(config.crn_version, nominal_instance.scenario_index, nominal_instance.seed, nominal_instance.generation_attempt, "yard", "priority_shift_time")
    _assert_latent_rows_rejected(tmp_path / "priority", [*nominal_ledger.to_rows(), priority])


def test_derive_controlled_projection_rejects_forged_rain_semantics():
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    rows = [dict(row) for row in instance.disruptions]
    rain_start = next(row for row in rows if row["event_type"] == "rain_start")
    rain_start["cause"] = "forged"
    rain_start["payload_hash"] = dataset_module._disruption_payload_hash(rain_start)
    forged = replace(instance, disruptions=tuple(rows), canonical_record_hash=None, instance_hash=None)
    with pytest.raises(DatasetContractError, match="rain"):
        dataset_module.derive_controlled_projection(
            forged,
            ledger,
            _task25_controls(ledger, intensity="base"),
        )


def test_controlled_projection_requires_controls_and_computes_hashes():
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    controls = _task25_controls(ledger, intensity="base")
    projection = ControlledProjection(instance=instance, controls=controls)
    assert projection.controls == controls
    assert projection.controlled_view_hash == dataset_module._controlled_view_hash(controls)
    with pytest.raises((TypeError, ValueError)):
        ControlledProjection(
            instance=instance,
            controlled_view_hash="0" * 64,
            event_overlay_hash="0" * 64,
        )


@pytest.mark.parametrize(
    "tamper",
    ["payload_hash", "instance_id", "scenario_index", "scenario_id", "seed", "sequence", "duplicate_sequence", "swap_order"],
)
def test_derive_controlled_projection_rejects_nonrain_stream_tamper(tamper):
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="priority_shift", hopper_count=1)
    rows = [dict(row) for row in instance.disruptions]
    target_index = next(index for index, row in enumerate(rows) if row["event_type"] == "priority_change")
    target = rows[target_index]
    if tamper == "payload_hash":
        target["payload_hash"] = "0" * 64
    elif tamper == "instance_id":
        target["instance_id"] = "forged-instance"
        target["payload_hash"] = dataset_module._disruption_payload_hash(target)
    elif tamper == "scenario_index":
        target["scenario_index"] = 999
        target["payload_hash"] = dataset_module._disruption_payload_hash(target)
    elif tamper == "scenario_id":
        target["scenario_id"] = "n60-m1-b1-nominal"
        target["payload_hash"] = dataset_module._disruption_payload_hash(target)
    elif tamper == "seed":
        target["seed"] = 999
        target["payload_hash"] = dataset_module._disruption_payload_hash(target)
    elif tamper == "sequence":
        target["sequence"] = 999
        target["payload_hash"] = dataset_module._disruption_payload_hash(target)
    elif tamper == "duplicate_sequence":
        target["sequence"] = rows[target_index - 1]["sequence"]
        target["payload_hash"] = dataset_module._disruption_payload_hash(target)
    else:
        rows[target_index], rows[target_index + 1] = rows[target_index + 1], rows[target_index]
    forged = replace(instance, disruptions=tuple(rows), canonical_record_hash=None, instance_hash=None)
    with pytest.raises(DatasetContractError, match="disruption|sequence|canonical|payload|instance|scenario"):
        dataset_module.derive_controlled_projection(
            forged,
            ledger,
            _task25_controls(ledger, intensity="base"),
        )


def test_derive_controlled_projection_wraps_unknown_priority_truck():
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="priority_shift", hopper_count=1)
    rows = [dict(row) for row in instance.disruptions]
    target = next(row for row in rows if row["event_type"] == "priority_change")
    target["truck_id"] = "T-999"
    target["payload_hash"] = dataset_module._disruption_payload_hash(target)
    forged = replace(instance, disruptions=tuple(rows), canonical_record_hash=None, instance_hash=None)
    with pytest.raises(DatasetContractError) as caught:
        dataset_module.derive_controlled_projection(
            forged,
            ledger,
            _task25_controls(ledger, intensity="base"),
        )
    assert isinstance(caught.value.__cause__, KeyError)


@pytest.mark.parametrize(
    "regime, latent_kind, field, value",
    [
        ("nominal", "base_failure", "start_minute", 0.0),
        ("nominal", "base_failure", "duration_min", 0.0),
        ("nominal", "base_failure", "resource_id", "hopper-999"),
        ("critical_failure", "forced_failure", "duration_min", 0.0),
        ("priority_shift", "priority_shift", "shift_time_minute", 0.0),
        ("priority_shift", "priority_shift", "candidate_truck_ids", []),
    ],
)
def test_load_event_latents_rejects_variant_semantic_tamper(tmp_path, regime, latent_kind, field, value):
    config = load_config(CONFIG_PATH)
    _instance, ledger = _task25_instance_and_ledger(config, regime=regime)
    rows = [dict(row) for row in ledger.to_rows()]
    target = next(row for row in rows if row["latent_kind"] == latent_kind)
    payload = dict(target["payload"])
    payload[field] = value
    target["payload"] = payload
    path = tmp_path / "event_latents.jsonl"
    path.write_bytes(dataset_module._jsonl_bytes(rows, "event_latents"))
    with pytest.raises(DatasetContractError, match="latent|candidate|resource|range|priority|duration|window"):
        load_event_latents(path)


def test_controlled_derivation_reconciles_persisted_projection_and_hashes():
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="critical_failure")
    forced = next(row for row in instance.disruptions if row["event_type"] == "resource_failure")
    tampered_rows = [dict(row) for row in instance.disruptions]
    tampered = next(row for row in tampered_rows if row["sequence"] == forced["sequence"])
    tampered["duration_min"] = float(tampered["duration_min"]) + 1.0
    tampered["return_time"] = float(tampered["return_time"]) + 1.0
    forged = replace(
        instance,
        disruptions=tuple(tampered_rows),
        canonical_record_hash=None,
        instance_hash=None,
    )
    with pytest.raises(DatasetContractError, match="forced failure latent projection"):
        derive_controlled_instance(forged, ledger, _task25_controls(ledger, intensity="base"))

    wrong_hash_controls = ExecutionControls.build(
        ordinary_window=6,
        buffer_capacity=12,
        threshold_multiplier=Decimal("1.00"),
        intensity="base",
        source_dataset_root_hash="a" * 64,
        event_latents_sha256="b" * 64,
    )
    with pytest.raises(ValueError, match="event_latents_sha256"):
        derive_controlled_instance(instance, ledger, wrong_hash_controls)


@pytest.mark.parametrize("tamper", ["missing", "extra", "noncanonical", "crn", "document_range"])
def test_event_latent_loader_rejects_tamper(tmp_path, tamper):
    config = load_config(CONFIG_PATH)
    _instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    rows = [dict(row) for row in ledger.to_rows()]
    path = tmp_path / "event_latents.jsonl"
    if tamper == "missing":
        with pytest.raises(DatasetContractError, match="MISSING_EVENT_LATENTS"):
            load_event_latents(path)
        return
    if tamper == "extra":
        rows[0]["unexpected"] = True
    elif tamper == "crn":
        rows[0]["payload"]["u_draw_key"] = "0" * 64
    elif tamper == "document_range":
        rows[0]["payload"]["release_duration_min"] = 0.0
    if tamper == "extra":
        payload = b"".join(canonical_bytes(row) for row in rows)
    else:
        payload = dataset_module._jsonl_bytes(rows, "event_latents")
        if tamper == "noncanonical":
            payload = payload.replace(b"\n", b" \n", 1)
    path.write_bytes(payload)
    with pytest.raises(DatasetContractError, match="canonical|CRN|schema|unexpected"):
        load_event_latents(path)


def test_controlled_derivation_is_frozen_no_rng_regeneration_or_mutation(monkeypatch):
    config = load_config(CONFIG_PATH)
    instance, ledger = _task25_instance_and_ledger(config, regime="nominal", hopper_count=2)
    before = instance.to_dict()
    controls = _task25_controls(ledger, intensity="high")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("controlled derivation must not sample or regenerate")

    monkeypatch.setattr(dataset_module, "_rng", forbidden)
    monkeypatch.setattr(dataset_module, "_build_instance", forbidden)
    derived = derive_controlled_instance(instance, ledger, controls)
    assert instance.to_dict() == before
    assert derived.instance_hash
