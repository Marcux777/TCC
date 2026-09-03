from pathlib import Path

from pequiflux_experiment.config import (
    CapacityRequirements,
    config_hash,
    factorial_scenarios,
    load_config,
)
from pequiflux_experiment.face_validation import validate_face_validation_receipt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


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
