"""Run-manifest boundary checks independent of dataset materialization."""

import pytest

from pequiflux_experiment.manifest import (
    _memory_inventory,
    canonical_checksum_bytes,
    dataset_root_hash,
)


@pytest.mark.parametrize("digest", ["g" * 64, "+" + "a" * 63, " " + "a" * 63])
def test_manifest_hash_boundaries_reject_non_hex_digests(digest):
    payloads = (
        "scenario_index.parquet", "trucks.parquet", "service_times.parquet",
        "disruptions.jsonl", "event_latents.jsonl", "rejection_log.jsonl",
    )
    with pytest.raises(ValueError):
        canonical_checksum_bytes({name: digest for name in payloads})
    with pytest.raises(ValueError):
        dataset_root_hash(digest, "a" * 64)
    with pytest.raises(ValueError):
        dataset_root_hash("a" * 64, digest)


def test_manifest_reports_physical_memory_on_supported_host():
    memory = _memory_inventory()
    assert memory["status"] == "detected"
    assert memory["total_bytes"] > 0
    assert memory["reason"] is None
