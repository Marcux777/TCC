from pathlib import Path
from types import SimpleNamespace
import os
import sys

import pytest

from pequiflux_experiment.config import config_as_dict, config_hash, factorial_scenarios, load_config
from pequiflux_experiment import capacity
from pequiflux_experiment.profiles import ConfirmatoryWorkload, plan_policy_days

CONFIG = load_config(Path(__file__).parents[1] / 'config/confirmatory.json')
GIB = 1024 ** 3


def _dataset(tmp_path):
    root = tmp_path / 'frozen'
    root.mkdir()
    (root / 'FREEZE.json').write_text('{}')
    return SimpleNamespace(
        path=root, dataset_hash='a' * 64, dataset_id='frozen',
        manifest={'config_hash': config_hash(CONFIG), 'frozen_parameters': config_as_dict(CONFIG)},
        instances=tuple(SimpleNamespace(scenario_index=s.scenario_index, scenario_id=s.scenario_id,
                                       seed=seed, trucks=(None,) * s.truck_count)
                        for s in factorial_scenarios(CONFIG) for seed in CONFIG.seeds),
    )


def _probe(*_):
    return {'free_disk_bytes': 1000 * GIB, 'free_ram_bytes': 16 * GIB, 'logical_cpu': 16,
            'pid': os.getpid(), 'process_created': 100.0, 'process_owner': 'test-owner',
            'executable': str(Path(sys.executable).resolve()),
            'executable_sha256': 'b' * 64, 'owned_pids': [os.getpid()], 'processes': [],
            'gpu_inventory': [], 'causes': []}


def test_capacity_plan_and_receipt_fail_closed(tmp_path, monkeypatch):
    dataset = _dataset(tmp_path)
    monkeypatch.setattr('pequiflux_experiment.profiles.load_freeze_receipt', lambda *a, **k: SimpleNamespace(manifest=dataset.manifest))
    assert plan_policy_days(dataset, CONFIG.policies, 'pilot').count == 3750
    assert plan_policy_days(dataset, CONFIG.policies, 'execute-confirmatory').count == 18000
    with pytest.raises(ValueError, match='canonical'):
        plan_policy_days(dataset, CONFIG.policies[:-1], 'execute-confirmatory')
    workload = ConfirmatoryWorkload.from_dataset(dataset, CONFIG)
    monkeypatch.setattr(capacity, '_os_probe', _probe)
    monkeypatch.setattr(capacity, '_revalidate_dataset', lambda _: None)
    target = tmp_path / 'run'
    receipt = capacity.inspect_capacity(workload, CONFIG.capacity, target)
    assert receipt.decision == 'PASS'
    assert receipt.workers == 4
    assert receipt.required_disk_bytes == (5 * workload.estimate_output_bytes + 3) // 4 + 5 * GIB
    capacity.require_capacity(receipt, workload=workload, requirements=CONFIG.capacity, run_root=target)
    assert not target.exists()
    with pytest.raises(capacity.CapacityGateError, match='run_root'):
        capacity.require_capacity(receipt, workload=workload, requirements=CONFIG.capacity, run_root=tmp_path / 'other')
    receipt.path.write_text('{}')
    with pytest.raises(capacity.CapacityGateError, match='receipt'):
        capacity.require_capacity(receipt, workload=workload, requirements=CONFIG.capacity, run_root=target)


@pytest.mark.parametrize('change, cause', [
    ({'free_disk_bytes': 1}, 'required_disk_bytes'),
    ({'free_ram_bytes': 3 * GIB}, 'free_ram_bytes'),
    ({'causes': ['competing project process pid=123']}, 'competing project'),
])
def test_capacity_blocks_resources_before_namespace(tmp_path, monkeypatch, change, cause):
    dataset = _dataset(tmp_path)
    monkeypatch.setattr('pequiflux_experiment.profiles.load_freeze_receipt', lambda *a, **k: SimpleNamespace(manifest=dataset.manifest))
    workload = ConfirmatoryWorkload.from_dataset(dataset, CONFIG, phase='pilot')
    monkeypatch.setattr(capacity, '_os_probe', lambda *_: {**_probe(), **change})
    target = tmp_path / 'blocked'
    receipt = capacity.inspect_capacity(workload, CONFIG.capacity, target)
    assert receipt.decision == 'BLOCKED'
    with pytest.raises(capacity.CapacityGateError, match=cause):
        capacity.require_capacity(receipt, workload=workload, requirements=CONFIG.capacity, run_root=target)
    assert not target.exists()


@pytest.mark.parametrize('change, cause', [
    ({'pid': -1}, 'pid differs'),
    ({'process_created': 101.0}, 'process_created differs'),
    ({'executable': 'other-python.exe'}, 'executable differs'),
    ({'executable_sha256': 'c' * 64}, 'executable_sha256 differs'),
    ({'owned_pids': [os.getpid(), 42]}, 'unregistered descendant'),
    ({'causes': ['competing project process pid=123']}, 'competing project'),
])
def test_capacity_rechecks_current_process(tmp_path, monkeypatch, change, cause):
    dataset = _dataset(tmp_path)
    monkeypatch.setattr('pequiflux_experiment.profiles.load_freeze_receipt', lambda *a, **k: SimpleNamespace(manifest=dataset.manifest))
    monkeypatch.setattr(capacity, '_revalidate_dataset', lambda _: None)
    workload = ConfirmatoryWorkload.from_dataset(dataset, CONFIG)
    monkeypatch.setattr(capacity, '_os_probe', _probe)
    target = tmp_path / 'runs'
    target.mkdir()
    receipt = capacity.inspect_capacity(workload, CONFIG.capacity, target)
    monkeypatch.setattr(capacity, '_os_probe', lambda *_: {**_probe(), **change})
    with pytest.raises(capacity.CapacityGateError, match=cause):
        capacity.require_capacity(receipt, workload=workload, requirements=CONFIG.capacity, run_root=target)
    assert not list(target.iterdir())


def test_capacity_expires_and_binds_phase(tmp_path, monkeypatch):
    dataset = _dataset(tmp_path)
    monkeypatch.setattr('pequiflux_experiment.profiles.load_freeze_receipt', lambda *a, **k: SimpleNamespace(manifest=dataset.manifest))
    monkeypatch.setattr(capacity, '_revalidate_dataset', lambda _: None)
    monkeypatch.setattr(capacity, '_os_probe', _probe)
    workload = ConfirmatoryWorkload.from_dataset(dataset, CONFIG, phase='pilot')
    target = tmp_path / 'run'
    monkeypatch.setattr(capacity, '_now', lambda: 100.0)
    receipt = capacity.inspect_capacity(workload, CONFIG.capacity, target)
    confirmation = ConfirmatoryWorkload.from_dataset(dataset, CONFIG)
    with pytest.raises(capacity.CapacityGateError, match='phase hashes differ'):
        capacity.require_capacity(receipt, workload=confirmation, requirements=CONFIG.capacity, run_root=target)
    monkeypatch.setattr(capacity, '_now', lambda: 161.0)
    with pytest.raises(capacity.CapacityGateError, match='expired'):
        capacity.require_capacity(receipt, workload=workload, requirements=CONFIG.capacity, run_root=target)
    assert not target.exists()
