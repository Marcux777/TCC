"""Persist and revalidate short-lived, process-bound CPU capacity decisions."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid

import psutil

from .config import CapacityRequirements, canonical_bytes
from .dataset import load_freeze_receipt
from .profiles import ConfirmatoryWorkload

GIB = 1024 ** 3
INSPECTION_VERSION = 'capacity.v1'
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class CapacityGateError(RuntimeError):
    """A capacity prerequisite is unavailable, changed, or unproven."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _now():
    return datetime.now(timezone.utc).timestamp()


def _os_probe(run_root: Path):
    """Read actual resources and prove ownership, without starting work."""
    current = psutil.Process()
    owned = {current.pid, *(process.pid for process in current.children(recursive=True))}
    causes, processes = [], []
    for process in psutil.process_iter(['pid', 'name']):
        name = (process.info['name'] or '').lower()
        if not any(token in name for token in ('python', 'jupyter', 'pytest')) or process.pid in owned:
            continue
        try:
            argv, cwd, executable_path = process.cmdline(), process.cwd(), process.exe()
            record = {'pid': process.pid, 'name': name, 'cwd': cwd, 'argv': argv,
                      'executable': executable_path,
                      'owner': process.username(), 'created': process.create_time()}
            processes.append(record)
            project = os.path.normcase(str(PROJECT_ROOT))
            references = [os.path.normcase(cwd), os.path.normcase(executable_path),
                          *(os.path.normcase(arg) for arg in argv)]
            if any(reference == project or project + os.sep in reference for reference in references):
                causes.append(f'competing project process pid={process.pid} owner={record["owner"]}')
        except psutil.NoSuchProcess:
            continue
        except (psutil.AccessDenied, OSError) as exc:
            causes.append(f'process ownership unproven pid={process.pid}: {type(exc).__name__}: {exc}')
    executable = Path(sys.executable).resolve(strict=True)
    for line in (PROJECT_ROOT / 'experimento-notebook/requirements.lock').read_text().splitlines():
        if '==' not in line:
            continue
        name, version = line.split('==')
        try:
            actual = importlib.metadata.version(name)
            if actual != version:
                causes.append(f'dependency {name} requires {version}; observed {actual}')
        except importlib.metadata.PackageNotFoundError as exc:
            causes.append(f'dependency {name} unavailable: {exc}')
    gpu = []
    if platform.system() == 'Windows':
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion | ConvertTo-Json -Compress'],
            text=True, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            causes.append(f'GPU inventory inspection failed: {result.stderr.strip()}')
        elif result.stdout.strip():
            gpu = json.loads(result.stdout)
    else:
        gpu = {'status': 'not_required', 'provider': 'cpu', 'platform': platform.system()}
    return {'free_disk_bytes': shutil.disk_usage(run_root.parent).free,
            'free_ram_bytes': psutil.virtual_memory().available,
            'logical_cpu': psutil.cpu_count(logical=True), 'pid': current.pid,
            'process_owner': current.username(),
            'process_created': current.create_time(), 'executable': str(executable),
            'executable_sha256': _sha(executable), 'owned_pids': sorted(owned),
            'processes': processes, 'gpu_inventory': gpu, 'causes': causes}


def _evaluate(workload, requirements, probe):
    required_disk = math.ceil(requirements.disk_margin * workload.estimate_output_bytes) + requirements.disk_reserve_gib * GIB
    workers = min(requirements.max_workers, probe['logical_cpu'] - 1,
                  (probe['free_ram_bytes'] - requirements.reserve_ram_gib * GIB) // GIB)
    causes = list(probe['causes'])
    if probe['free_disk_bytes'] < required_disk:
        causes.append(f'required_disk_bytes={required_disk}; free_disk_bytes={probe["free_disk_bytes"]}')
    if probe['free_ram_bytes'] < requirements.min_free_ram_gib * GIB:
        causes.append(f'free_ram_bytes={probe["free_ram_bytes"]}; minimum={requirements.min_free_ram_gib * GIB}')
    if workers < 1:
        causes.append(f'authorized workers={workers}; require >=1')
    return required_disk, max(0, workers), causes


@dataclass(frozen=True, slots=True)
class CapacityReceipt:
    path: Path
    sha256: str
    decision: str
    workers: int
    required_disk_bytes: int

    def to_dict(self):
        return {'path': str(self.path), 'sha256': self.sha256, 'decision': self.decision,
                'workers': self.workers, 'required_disk_bytes': self.required_disk_bytes}


def inspect_capacity(workload: ConfirmatoryWorkload, requirements: CapacityRequirements, run_root) -> CapacityReceipt:
    if not isinstance(workload, ConfirmatoryWorkload) or not isinstance(requirements, CapacityRequirements):
        raise TypeError('explicit frozen workload and CapacityRequirements are required')
    target = Path(run_root).resolve()
    if not target.parent.is_dir():
        raise CapacityGateError(f'inspect_capacity run_root={target}: parent does not exist')
    if target.exists() and not target.is_dir():
        raise CapacityGateError(f'inspect_capacity run_root={target}: output root is not a directory')
    try:
        probe = _os_probe(target)
        disk, workers, causes = _evaluate(workload, requirements, probe)
    except Exception as exc:
        raise CapacityGateError(f'inspect_capacity workload={workload.workload_hash} run_root={target}: {exc}') from exc
    payload = {'inspection_version': INSPECTION_VERSION, 'timestamp': _now(),
               'requirements': requirements.as_dict(), 'run_root': str(target),
               'workload': workload.to_dict(), 'workload_hash': workload.workload_hash,
               'probe': probe, 'required_disk_bytes': disk, 'workers': workers,
               'estimated_peak_ram_bytes': (requirements.reserve_ram_gib + workers) * GIB,
               'estimated_rows': workload.policy_day_count, 'estimated_logs': workload.policy_day_count,
               'decision': 'BLOCKED' if causes else 'PASS', 'causes': causes}
    receipt_path = target.parent / f'{target.name}.capacity-{uuid.uuid4().hex}.json'
    raw = canonical_bytes(payload)
    with receipt_path.open('xb') as stream:
        stream.write(raw)
    return CapacityReceipt(receipt_path, hashlib.sha256(raw).hexdigest(), payload['decision'], workers, disk)


def _revalidate_dataset(workload):
    receipt = load_freeze_receipt(workload.dataset_path, expected_dataset_root_hash=workload.dataset_hash)
    if receipt.manifest['config_hash'] != workload.config_hash:
        raise ValueError('dataset config_hash changed')
    size = sum(path.stat().st_size for path in workload.dataset_path.rglob('*') if path.is_file())
    if size != workload.dataset_size_bytes:
        raise ValueError('dataset size changed')


def require_capacity(receipt, *, workload: ConfirmatoryWorkload, requirements: CapacityRequirements, run_root):
    """Recheck saved evidence and current ownership immediately before run creation."""
    target = Path(run_root).resolve()
    try:
        if not isinstance(receipt, CapacityReceipt):
            raise ValueError('explicit persisted CapacityReceipt required')
        if receipt.path.resolve().parent != target.parent:
            raise ValueError('receipt path is outside run_root parent')
        raw = receipt.path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt.sha256:
            raise ValueError('receipt hash changed')
        saved = json.loads(raw)
        if saved['inspection_version'] != INSPECTION_VERSION:
            raise ValueError('receipt inspection_version differs')
        if saved['run_root'] != str(target) or (target.exists() and not target.is_dir()):
            raise ValueError('run_root differs or is not a directory')
        if saved['workload_hash'] != workload.workload_hash or saved['workload'] != workload.to_dict():
            raise ValueError('receipt workload/config/dataset/phase hashes differ')
        if saved['requirements'] != requirements.as_dict():
            raise ValueError('receipt requirements differ')
        age = _now() - saved['timestamp']
        if not 0 <= age <= requirements.receipt_ttl_seconds:
            raise ValueError(f'receipt expired or future timestamp: age={age}')
        if saved['decision'] != 'PASS':
            raise ValueError('; '.join(saved['causes']))
        if (receipt.decision, receipt.workers, receipt.required_disk_bytes) != (saved['decision'], saved['workers'], saved['required_disk_bytes']):
            raise ValueError('receipt object differs from persisted fields')
        _revalidate_dataset(workload)
        current = _os_probe(target)
        for field in ('pid', 'process_created', 'process_owner', 'executable', 'executable_sha256'):
            if current[field] != saved['probe'][field]:
                raise ValueError(f'current process {field} differs from receipt')
        if not set(current['owned_pids']).issubset(saved['probe']['owned_pids']):
            raise ValueError('unregistered descendant process ownership')
        _, workers, causes = _evaluate(workload, requirements, current)
        if workers < saved['workers']:
            causes.append('current capacity cannot support all authorized workers')
        if causes:
            raise ValueError('; '.join(causes))
        if _now() - saved['timestamp'] > requirements.receipt_ttl_seconds:
            raise ValueError('receipt expired during revalidation')
    except Exception as exc:
        raise CapacityGateError(f'require_capacity workload={workload.workload_hash} run_root={target}: {exc}') from exc
    return receipt
