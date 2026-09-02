from pathlib import Path
import json
import tomllib

import pytest

from pequiflux_experiment.config import config_hash, factorial_scenarios, load_config
from pequiflux_experiment.manifest import build_manifest, create_run_directory
from pequiflux_experiment import manifest as manifest_module


PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "confirmatory.json"


def test_build_backend_requirement_is_exactly_locked():
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    build_requirements = pyproject["build-system"]["requires"]
    setuptools_requirements = [
        requirement
        for requirement in build_requirements
        if requirement.split("==", 1)[0].lower() == "setuptools"
    ]

    assert len(setuptools_requirements) == 1
    setuptools_requirement = setuptools_requirements[0]
    assert setuptools_requirement.startswith("setuptools==")
    assert setuptools_requirement.count("==") == 1

    lock_requirements = [
        line.strip()
        for line in (PROJECT_ROOT / "requirements.lock")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert [
        line for line in lock_requirements if line.lower().startswith("setuptools")
    ] == [setuptools_requirement]


def test_config_is_frozen_and_run_directory_never_overwrites(tmp_path):
    config = load_config(CONFIG_PATH)

    assert config.seeds == tuple(range(101, 151))
    assert len(factorial_scenarios(config)) == 72
    assert len(config_hash(config)) == 64

    run_dir = create_run_directory(
        tmp_path,
        "validation",
        "abc1234",
        config_hash(config),
        now_utc="2026-09-01T12:00:00Z",
    )

    with pytest.raises(FileExistsError, match="run directory already exists"):
        create_run_directory(
            tmp_path,
            "validation",
            "abc1234",
            config_hash(config),
            now_utc="2026-09-01T12:00:00Z",
        )

    assert run_dir.name.startswith("validation__20260901T120000Z__abc1234__")


@pytest.mark.parametrize("field", ["policies", "regimes"])
def test_json_objects_are_rejected_for_sequence_fields(tmp_path, field):
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    values = data[field]
    data[field] = {value: index for index, value in enumerate(values)}
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises((TypeError, ValueError), match="must be a sequence"):
        load_config(path)


@pytest.mark.parametrize(
    ("mutation", "error_pattern"),
    [
        (lambda data: data.update({"unexpected": True}), "unknown configuration keys"),
        (
            lambda data: data.update({"seeds": [101, 103, 102, *range(104, 151)]}),
            "seeds must be strictly increasing",
        ),
        (
            lambda data: data.update({"policies": ["fifo_strict"]}),
            "policy panel must be exactly",
        ),
        (
            lambda data: data.update({"regimes": ["nominal"]}),
            "factorial product must be 72",
        ),
    ],
)
def test_load_config_rejects_required_invalid_inputs(tmp_path, mutation, error_pattern):
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    mutation(data)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises((TypeError, ValueError), match=error_pattern):
        load_config(path)


def test_build_manifest_has_explicit_hardware_inventory(tmp_path, monkeypatch):
    config = load_config(CONFIG_PATH)
    monkeypatch.setattr(
        manifest_module,
        "_detect_gpu",
        lambda: {"status": "unavailable", "reason": "test: GPU not requested", "devices": []},
        raising=False,
    )
    monkeypatch.setattr(manifest_module, "_memory_total_bytes", lambda: None)

    manifest = build_manifest(
        config,
        "validation",
        "abc1234",
        config_hash(config),
        run_dir=tmp_path / "run",
        command="pytest",
        profile="validation",
        checkout_clean=True,
        now_utc="2026-09-01T12:00:00Z",
    )

    assert manifest["memory"]["status"] == "unavailable"
    assert manifest["memory"]["reason"]
    assert manifest["gpu"]["status"] == "unavailable"
    assert manifest["gpu"]["reason"] == "test: GPU not requested"
    assert manifest["gpu"]["devices"] == []
    assert manifest["phase"] == "validation"
    assert manifest["profile"] == "validation"
    assert manifest["command"] == "pytest"


def test_memory_inventory_failure_preserves_cause(monkeypatch):
    config = load_config(CONFIG_PATH)

    def fail_memory_inventory():
        raise OSError("synthetic memory read failure")

    monkeypatch.setattr(manifest_module, "_memory_total_bytes", fail_memory_inventory)

    with pytest.raises(RuntimeError, match="memory inventory failed") as exc_info:
        build_manifest(config, "validation", "abc1234", config_hash(config))

    assert isinstance(exc_info.value.__cause__, OSError)
    assert str(exc_info.value.__cause__) == "synthetic memory read failure"
