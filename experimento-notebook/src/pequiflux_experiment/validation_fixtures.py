"""Explicit engineering fixtures; these values are never a published dataset."""

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from typing import Iterable

from .config import ScenarioConfig
from .dataset import _build_instance, _build_event_latents, _canonical_confirmatory_config
from .domain import EventLatentLedger, ExecutionControls, FrozenInstance, EVENT_LATENT_KINDS


@dataclass(frozen=True, slots=True)
class ValidationFixture:
    instance: FrozenInstance
    controls: ExecutionControls
    event_latents: EventLatentLedger


def build_validation_inputs(
    scenarios: Iterable[ScenarioConfig], seeds: Iterable[int]
) -> tuple[tuple[FrozenInstance, ...], ExecutionControls, EventLatentLedger]:
    """Materialize small engineering inputs explicitly, outside the DES."""
    config = _canonical_confirmatory_config()
    scenarios, seeds = tuple(scenarios), tuple(seeds)
    instances = tuple(_build_instance(config, scenario, seed, validation_fixture=True) for scenario in scenarios for seed in seeds)
    if not instances or len({instance.instance_id for instance in instances}) != len(instances):
        raise ValueError("validation fixtures require nonempty unique scenario-index/seed pairs")
    rows = tuple(
        row
        for scenario in scenarios
        for seed in seeds
        for row in _build_event_latents(
            config, scenario, seed, 0,
            next(item.trucks for item in instances if item.scenario_index == scenario.scenario_index and item.scenario_id == scenario.scenario_id and item.seed == seed),
            validation_fixture=True,
        ).to_rows()
    )
    ledger = EventLatentLedger(tuple(sorted(rows, key=lambda row: (
        row["instance_id"], EVENT_LATENT_KINDS.index(row["latent_kind"]), row["entity_id"], row["latent_id"],
    ))))
    root_hash = hashlib.sha256(
        ("engineering-validation-only\n" + "\n".join(str(item.instance_hash) for item in instances)
         + "\n" + ledger.event_latents_sha256).encode("utf-8")
    ).hexdigest()
    controls = ExecutionControls.build(
        ordinary_window=6, buffer_capacity=12, threshold_multiplier=Decimal("1.00"),
        intensity="base", source_dataset_root_hash=root_hash,
        event_latents_sha256=ledger.event_latents_sha256,
    )
    return instances, controls, ledger


def build_validation_fixture(
    scenario: ScenarioConfig | None = None, seed: int = 101
) -> ValidationFixture:
    scenario = ScenarioConfig(4, 1, 1, "nominal") if scenario is None else scenario
    instances, controls, ledger = build_validation_inputs((scenario,), (seed,))
    return ValidationFixture(instances[0], controls, ledger)
