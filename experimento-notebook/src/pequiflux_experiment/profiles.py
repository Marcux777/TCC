"""Pure phase plans and workload identity for frozen scientific inputs."""

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .config import (ExperimentConfig, canonical_bytes, config_hash,
                     factorial_scenarios, validate_confirmatory_config)
from .dataset import load_freeze_receipt, select_pilot_configurations
from .policies import EXPLORATORY_POLICIES, STRESS_POLICIES

SCIENTIFIC_PHASES = ('pilot', 'execute-confirmatory', 'sensitivity', 'exploratory')


def sensitivity_bootstrap(controls):
    material = {'version': 'sensitivity-bootstrap.v1',
                'control_hash': controls.control_hash,
                'event_latents_sha256': controls.event_latents_sha256}
    digest = hashlib.sha256(canonical_bytes(material)).digest()
    return {**material, 'seed': int.from_bytes(digest[:8], 'big') % (2**32 - 1),
            'iterations': 5000, 'pair_order': 'scenario_id,seed',
            'paired_indices_across_policies': True}


def phase_policies(config, phase):
    if phase == 'sensitivity':
        return STRESS_POLICIES
    if phase == 'exploratory':
        return EXPLORATORY_POLICIES
    return config.policies


def _hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class PolicyDayPlan:
    phase: str
    keys: tuple[tuple[int, int, str], ...]
    scenario_indices: tuple[int, ...]
    seeds: tuple[int, ...]
    policies: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.keys)

    @property
    def plan_hash(self) -> str:
        return _hash({'phase': self.phase, 'keys': self.keys})


def plan_policy_days(dataset, policies, phase: str) -> PolicyDayPlan:
    """Plan exact ordered cells; never execute DES or infer a reduced campaign."""
    if phase not in {'validation', *SCIENTIFIC_PHASES}:
        raise ValueError('unknown execution phase')
    config = ExperimentConfig(**dataset.manifest['frozen_parameters'])
    validate_confirmatory_config(config)
    if config_hash(config) != dataset.manifest['config_hash']:
        raise ValueError('dataset configuration hash mismatch')
    policies = tuple(policies)
    if policies != phase_policies(config, phase):
        raise ValueError('phase requires all canonical policies in order')
    observed = tuple((item.scenario_index, item.seed) for item in dataset.instances)
    if len(set(observed)) != len(observed):
        raise ValueError('duplicate dataset instance key')
    if phase == 'validation':
        if dataset.manifest.get('non_confirmatory') is not True:
            raise ValueError('validation requires explicitly non-confirmatory dataset')
        selected = observed
        scenarios = tuple(dict.fromkeys(key[0] for key in selected))
        seeds = tuple(dict.fromkeys(key[1] for key in selected))
    else:
        canonical = factorial_scenarios(config)
        expected = tuple((s.scenario_index, seed) for s in canonical for seed in config.seeds)
        if observed != expected:
            raise ValueError('scientific plan requires complete canonical ordered frozen dataset')
        scenarios = tuple(s.scenario_index for s in (
            select_pilot_configurations(config) if phase == 'pilot' else canonical))
        seeds = config.seeds
        selected = tuple((index, seed) for index in scenarios for seed in seeds)
    return PolicyDayPlan(phase, tuple((index, seed, policy) for index, seed in selected for policy in policies),
                         scenarios, seeds, policies)


@dataclass(frozen=True, slots=True)
class ConfirmatoryWorkload:
    phase: str
    dataset_path: Path
    dataset_hash: str
    config_hash: str
    dataset_size_bytes: int
    estimate_output_bytes: int
    plan: PolicyDayPlan
    control_hash: str | None = None

    @classmethod
    def from_dataset(cls, dataset, config: ExperimentConfig, *, phase='execute-confirmatory', controls=None):
        if phase not in SCIENTIFIC_PHASES:
            raise ValueError('unknown scientific capacity workload phase')
        if phase in {'sensitivity', 'exploratory'} and controls is None:
            raise ValueError('exploratory workloads require explicit controls')
        validate_confirmatory_config(config)
        root = dataset.path.resolve(strict=True)
        pin = dataset.dataset_hash
        freeze = load_freeze_receipt(root, expected_dataset_root_hash=pin)
        if config_hash(config) != dataset.manifest['config_hash'] or config_hash(config) != freeze.manifest['config_hash']:
            raise ValueError('workload dataset/config hash mismatch')
        plan = plan_policy_days(dataset, phase_policies(config, phase), phase)
        if controls is not None and (controls.source_dataset_root_hash != pin
                or controls.event_latents_sha256 != dataset.event_latents.event_latents_sha256):
            raise ValueError('workload controls do not identify the frozen inputs')
        sizes = [path.stat().st_size for path in root.rglob('*') if path.is_file()]
        dataset_size = sum(sizes)
        counts = {(item.scenario_index, item.seed): len(item.trucks) for item in dataset.instances}
        expected_counts = {s.scenario_index: s.truck_count for s in factorial_scenarios(config)}
        if any(count != expected_counts[index] for (index, _), count in counts.items()):
            raise ValueError('workload truck count diverges from canonical scenario')
        output_bytes = dataset_size + sum(32768 * counts[(index, seed)] for index, seed, _ in plan.keys)
        return cls(phase, root, pin, config_hash(config), dataset_size, output_bytes, plan,
                   controls.control_hash if controls is not None else None)

    @property
    def policy_day_count(self):
        return self.plan.count

    def to_dict(self):
        return {'phase': self.phase, 'dataset_path': str(self.dataset_path),
                'dataset_hash': self.dataset_hash, 'config_hash': self.config_hash,
                'dataset_size_bytes': self.dataset_size_bytes,
                'estimate_output_bytes': self.estimate_output_bytes,
                'policy_day_count': self.plan.count, 'plan_hash': self.plan.plan_hash,
                'scenario_indices': list(self.plan.scenario_indices),
                'seeds': list(self.plan.seeds), 'policies': list(self.plan.policies),
                'control_hash': self.control_hash}

    @property
    def workload_hash(self):
        return _hash(self.to_dict())
