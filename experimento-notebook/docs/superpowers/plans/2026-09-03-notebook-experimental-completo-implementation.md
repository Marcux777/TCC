# Notebook Experimental Completo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy notebook pipeline with the frozen, auditable and fail-fast experimental notebook specified in `experimento-notebook/docs/superpowers/specs/2026-09-02-notebook-experimental-completo-design.md`.

**Architecture:** A persisted dataset generator is the only source of stochastic inputs. Frozen instances feed a deterministic four-stage DES through one dispatch interface; event logs feed an independent digital projection/replay and audit layer, and only a complete audited confirmatory bundle feeds H1 IUT/Holm and transactional exports. The notebook is a thin literate router with six literal actions and no duplicated simulation logic.

**Tech Stack:** Python 3 with frozen dataclasses, NumPy/pandas/SciPy, Parquet via `pyarrow`, `psutil` for the capacity gate, JSONL/JSON canonical hashing, Jupyter `nbclient`, pytest, and matplotlib for figures.

**Spec:** `experimento-notebook/docs/superpowers/specs/2026-09-02-notebook-experimental-completo-design.md`

## Global Constraints

- Work only under `experimento-notebook/`; never alter `main.tex`, `main.pdf`, `refs.bib`, the dirty repository root, or `agro-yard-des-experiment`.
- The confirmatory factorial is exactly `N ∈ {60, 120, 180}`, `m ∈ {1, 2, 3}`, `b ∈ {1, 2}`, regimes `nominal`, `peak`, `critical_failure`, `priority_shift`, seeds `101..150`, and policies `fifo_strict`, `fifo_flow_faithful`, `priority_local`, `fixed_score`, `lexicographic`.
- Enumerate loops in the exact order `N`, then `m`, then `b`, then regime; produce `scenario_index=0..71`, `scenario_id=f"n{N}-m{m}-b{b}-{regime}"`, 72 configurations, 3,600 instances and 18,000 policy-days.
- Use `rho(N,m,b) = N / min(36*m, 72*b)` with strata `low` (`rho < 0,70`), `medium` (`0,70 ≤ rho < 0,85`) and `high` (`rho ≥ 0,85`); H1 uses only medium and high.
- A terminating day starts at 06:00, has empty buffers, and ends at 18:00 (`720` minutes); all arrivals, service times and disruptions are generated before policy execution.
- Preserve the four triangular service distributions `(2,4,7)`, `(3,5,8)`, `(12,20,35)`, `(3,5,8)`, pressure controls `H0=6`, `tau2=10`, `tau1=30`, `tau0=60`, buffer `12`, and `delta(N)=max(2,0,02*N)`.
- Derive every random substream from `(crn_version, scenario_index, seed, generation_attempt, entity_id, operation/event)`; policy name never participates in the key.
- `face_validation.py` must verify real SHA-256 bytes for `main.pdf` and `inputs/face_validation_rubric.v1.json`; absent, incomplete, divergent or unapproved human receipt is `FACE_VALIDATION=PENDING` and blocks every principal action before namespace creation.
- `validation` alone may create a reduced, persisted, deterministic dataset with either an approved or `PENDING` face report and must label it `non_confirmatory=true`; `config/validation.json` is exactly `scenario_indices=[20,12,24]`, `seeds=[101]`, and the five canonical policies. Only `generate-synthetic`, `pilot`, `execute-confirmatory` and `sensitivity` block before namespace creation when face is not `APPROVED`; `audit-analyze` remains diagnostic.
- `generate-synthetic` requires an explicit `FaceValidationReport.status=APPROVED` and materializes/publishes the complete dataset from the canonical plan; it does not require a pre-existing frozen dataset. `pilot` requires an approved face report and an existing complete frozen dataset but no confirmatory capacity gate. `execute-confirmatory` additionally requires the single capacity gate. `sensitivity` requires an approved face report and an existing complete frozen dataset in its own namespace but no capacity gate. `audit-analyze` is diagnostic over an explicit existing `RUN_ID` and may inspect a package without a face receipt, leaving publication pending when the receipt is absent.
- None of those actions generates a fallback dataset, retries, or uses a latest/implicit run. `DayResult` is immutable and carries the consumed instance/hash, complete logs/events, physical/digital snapshots, remnant queue and replay hashes but no `MetricRow`, `None`, `NaN` or sentinel zero. `compute_policy_day_metrics(persisted_day)` is the sole public metric producer, called after the persisted day/log is available and before its row is committed; no bundle closes without that complete canonical `MetricRow` and hashes, and audit recomputes/reconciles it.
- All validation, capacity, cardinality, hash, collision, replay, hard-constraint and statistical failures are fatal, preserve `__cause__`, include operation and identifiers, and leave staging evidence intact.
- Capacity is inspected once for all 18,000 policy-days: `estimate_output_bytes=sum(32768*N)+dataset_size_bytes`, `required_disk_bytes=ceil(1.25*estimate_output_bytes)+5 GiB`, `workers=min(4, logical_cpu-1, floor((free_ram_bytes-2 GiB)/1 GiB))`, at least one worker and at least 4 GiB free; receipt TTL is 60 seconds and CPU is canonical (GPU inventory only).
- `CapacityRequirements` is part of `confirmatory.json` and is passed explicitly to every gate; no global capacity/profile state is read.
- Permanent pytest checks never materialize the 3,600 production instances or execute 3,750/18,000 DES runs. They use `plan_synthetic_dataset`, `plan_policy_days`, the three-instance persisted validation package, and injected worker/provider seams; full materialization/campaign execution is a gated notebook action only.
- Confirmatory H1 is paired by `(scenario_index, seed)`, uses the three primary comparators, p95 waiting plus throughput IUT, `alpha=0,05`, 5,000 paired bootstrap resamples, Wilcoxon, Hodges–Lehmann, rank-biserial effect and one Holm correction across medium/high only.
- A1 is an eight-fixture persisted adversarial suite; A2 is structural plus optional human review, with `max(50, ceil(0,10*D_s))` per scenario, versioned rubric and Cohen kappa only for two reviewers; missing human review is `A2_human=PENDING`.
- Sensitivity has its own namespace and never enters H1; `ROBUST` requires the same complete cells to pass p95 gain and throughput guard against all three primary comparators in at least 75% of cells; incomplete input is `INVALID_INPUT`.
- Writes are staged and atomically renamed into new, collision-free namespaces. `results/` accepts only audited bundles, refuses overwrite, and fails explicitly when Parquet/`pyarrow` is unavailable.
- Baseline before implementation: 162 passed, 1 warning, 1085.09 s. Final verification is one canonical `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q` (no retry), `compileall`, inspection of the notebook validation receipt from that run, and a live capacity preflight only when a real frozen dataset exists; record its actual `PASS`/`BLOCKED`, or `NOT_RUN_NO_FROZEN_DATASET`, without launching a campaign.

## Architecture, Data Flow, and Public Interfaces

```text
config + approved face receipt
        │
        ▼
generate_synthetic_dataset ──> staging/payloads ──> FREEZE.json + hashes
        │                                      │
        └── validation selection               └── load_frozen_dataset
                                                   │
                                                   ▼
FrozenInstance ──> run_day(instance, policy) ──> complete event JSONL + snapshots/hashes
                                                   │
                                                   └──> compute_policy_day_metrics ──> MetricRow
                                                   │
                                                   ├──> DigitalModel/replay ──> independent audit/A1/A2
                                                   └──> audited confirmatory rows ──> H1 IUT/Holm ──> exports
```

| Module | Public interface | Contract consumed/produced |
| --- | --- | --- |
| `config.py` | `ExperimentConfig`, `ScenarioConfig`, `CapacityRequirements`, `load_config`, `factorial_scenarios`, `validate_confirmatory_config`, `config_hash` | Immutable canonical factorial, order, rho/strata, capacity fields and hash. |
| `face_validation.py` | `validate_face_validation_receipt(path, config, pdf_path) -> FaceValidationReport`; `materialize_face_validation_template(path)` | Real PDF/rubric hashes, approved gate or `PENDING` with cause. |
| `domain.py`/`events.py` | `FrozenInstance`, `Truck`, `Resource`, `Event`, `FrozenValidationDataset`; `write_jsonl`, `read_jsonl` | Serializable immutable payloads and deterministic event order. |
| `manifest.py` | `canonical_bytes`, `canonical_file_hash`, `create_run_directory`, `build_manifest`, `write_manifest` | Canonical JSON/checksum bytes, collision refusal and dirty-root/environment receipts; never mutates Git. |
| `dataset.py` | `generate_synthetic_dataset(config, face_report, dataset_root, ...)`, `resample_synthetic_dataset(config, face_report, source_staging_path, source_staging_root_hash, exact_rejected_ids, destination, ...)`, `load_aborted_staging`, `plan_synthetic_dataset`, `load_frozen_dataset`, `validate_frozen_dataset`, `freeze_dataset`, `select_pilot_configurations` | Complete 3,600-instance freeze, explicit one-attempt resample, canonical hash chain; face report is always explicit. |
| `validation.py` | `build_validation_dataset(config, validation_config, run_root, face_report)`, `run_validation_checks`, `run_a1_adversarial_suite(fixtures_path)` | Persisted indices `[20,12,24]`, seed `101`, five policies, 15 policy-days and eight A1 contexts from disk. |
| `dispatch.py`/`policies.py` | `DispatchContext`, `Candidate`, `make_policy`, `filter_admissible`, `select_candidate` | Shared hard constraints and five policy-only ranking rules. |
| `emulator.py` | `run_day(instance: FrozenInstance, policy: DispatchPolicy | str) -> DayResult` | Terminant DES with no sampling, no lazy defaults and complete event/hash output. |
| `metrics.py` | `compute_policy_day_metrics(persisted_day) -> MetricRow` | Sole producer of eight PDF metric families plus exploratory CO2 from persisted events; no fabricated values. |
| `capacity.py` | `inspect_capacity(workload, requirements, run_root, providers=...) -> CapacityReceipt`; `require_capacity(receipt)` | Single TTL/hash/process/disk/RAM gate before confirmatory namespace. |
| `profiles.py` | `ConfirmatoryWorkload.from_dataset(frozen_dataset, config)`; `plan_policy_days` | Actual dataset/config/workload hashes and pure cardinality plans. |
| `experiment.py` | `run_policy_days(dataset, policies, phase, run_root, face_report, capacity_receipt=None, worker=...) -> RunBundle`; `load_run_bundle` | Pilot/confirmatory atomic rows/logs; production refuses partial grids. |
| `digital_model.py`/`replay.py` | `DigitalModel.apply`, `snapshot`, `replay_events`, `replay_run` | Independent projection and deterministic replay equality. |
| `audit.py`/`a2.py` | `audit_run`, `build_a2_sample`, `apply_rubric`, `compute_cohen_kappa`, `persist_a2_review` | A1 zero-violation report, A2 workflow/sample/rubric and `PENDING` semantics. |
| `statistics.py` | `paired_dataframe`, `evaluate_h1(confirmatory_bundle, config) -> H1Report` | Medium/high IUT, throughput margin, bootstrap/HL/rank-biserial and Holm. |
| `sensitivity.py` | `run_sensitivity(dataset, face_report, grid, ...)`, `summarize_sensitivity` | Base/high rates, stress grid and joint 75% `ROBUST` decision outside H1; face report is explicit. |
| `export.py` | `export_analysis`, `export_audit_table` | Audited raw/processed/tables/figures, transactional no-overwrite publication. |

## Exact Invariants and Check Mapping

| Invariant or material risk | Required minimum check | Plan task |
| --- | --- | --- |
| 72 configurations, exact order/IDs/rho, 50 seeds, policy set and stable hash | `test_config_manifest.py::test_config_contract_and_hash` | 1 |
| Face receipt/template version, real PDF/rubric hashes, approved gate or pending cause | `test_config_manifest.py::test_face_validation_receipt_gate` | 1 |
| Reduced validation is `[20,12,24] × [101] × 5`, persisted and non-confirmatory | `test_dispatch_emulator.py::test_validation_dataset_persisted_and_non_confirmatory` | 5 |
| Complete production plan, 3,600-header orchestration, payloads, manifest, rejection log and checksums | `test_config_manifest.py::test_synthetic_plan_contract` plus `::test_generate_freezes_complete_dataset` | 2 |
| Validation package persists three selected instances for approved and pending face reports | `test_dispatch_emulator.py::test_validation_dataset_persisted_and_non_confirmatory` | 5 |
| Validation action ignores confirmatory face/capacity gates while pilot/confirmatory enforce them before namespace | `test_experiment_audit.py::test_validation_runner_always_persists_with_pending_face` plus `::test_face_or_capacity_block_makes_zero_worker_calls` | 6 |
| Explicit resample preserves canonical accepted records, increments attempt once and aborts on new rejection | `test_config_manifest.py::test_explicit_resample_provenance_and_abort` | 3 |
| `run_day` requires a complete frozen instance and has no hidden generation | `test_dispatch_emulator.py::test_run_day_requires_frozen_instance` | 4 |
| CRN inputs are identical across five policies | `test_dispatch_emulator.py::test_crn_is_policy_independent` | 4 |
| Eight A1 contexts fail closed and are consumed from disk | `test_dispatch_emulator.py::test_a1_adversarial_suite_fail_closed` | 5 |
| Digital projection/replay is independent and hash-equal | `test_digital_model_replay.py::test_replay_matches_independent_projection` | 7 |
| Policy-day key uniqueness and pilot/confirmatory cardinality plans | `test_experiment_audit.py::test_policy_day_plan_cardinality_without_des` | 6 |
| Five A2 fields, per-scenario sample, rubric, single/two-reviewer kappa and pending state | `test_digital_model_replay.py::test_a2_sample_rubric_and_kappa_contract` | 7 |
| H1 IUT, throughput guard, paired hashes and Holm only for medium/high | `test_statistics_export.py::test_iut_holm_and_invalid_pairing` | 8 |
| Joint sensitivity robustness and incomplete-input invalidation | `test_experiment_audit.py::test_joint_sensitivity_robustness_and_invalid_input` | 9 |
| Capacity/process ownership/TTL/hash gate blocks without starting campaign | `test_experiment_audit.py::test_capacity_gate_blocks_with_cause` | 6 |
| Six literal notebook actions and top-to-bottom validation journey | `test_notebook.py::test_notebook_actions_and_validation_run` | 11 |

### Task 1: Canonical configuration and face-validation gate

**Files:**
- Modify/Replace: `experimento-notebook/config/confirmatory.json`
- Create: `experimento-notebook/config/validation.json`
- Create: `experimento-notebook/inputs/face_validation_rubric.v1.json`
- Create: `experimento-notebook/inputs/face_validation_receipt.template.v1.json`
- Create: `experimento-notebook/inputs/face_validation_receipt.json`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/config.py`
- Create: `experimento-notebook/src/pequiflux_experiment/face_validation.py`
- Modify/Replace: `experimento-notebook/tests/test_config_manifest.py` (remove legacy config/manifest expectations and add the face-gate checks below)
- Modify: `experimento-notebook/pyproject.toml` and `experimento-notebook/requirements.lock` to declare direct `psutil` and retain the existing scientific dependencies.

**Interfaces:**
- Consumes: the frozen protocol values in the spec and the bytes of `main.pdf`/rubric.
- Produces: immutable `ExperimentConfig`/`ScenarioConfig`/`CapacityRequirements`; `factorial_scenarios()`; `load_config(path)`; `validate_confirmatory_config(config)`; `config_hash(config)`; `FaceValidationReport`; `validate_face_validation_receipt(path, config, pdf_path)`; `materialize_face_validation_template(path)`.

- [ ] **Step 1: Write the failing test (RED).**

```python
from pathlib import Path
import pytest

from pequiflux_experiment.config import CapacityRequirements, factorial_scenarios, config_hash, load_config
from pequiflux_experiment.face_validation import validate_face_validation_receipt

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "confirmatory.json"

def test_config_contract_and_hash():
    cfg = load_config(ROOT / "config" / "confirmatory.json")
    scenarios = factorial_scenarios(cfg)
    assert len(scenarios) == 72
    assert scenarios[0].scenario_id == "n60-m1-b1-nominal"
    assert scenarios[-1].scenario_index == 71
    assert cfg.seeds == tuple(range(101, 151))
    assert cfg.policies == ("fifo_strict", "fifo_flow_faithful", "priority_local", "fixed_score", "lexicographic")
    assert cfg.capacity == CapacityRequirements(
        min_free_ram_gib=4, reserve_ram_gib=2, max_workers=4, receipt_ttl_seconds=60
    )
    assert config_hash(cfg) == config_hash(load_config(ROOT / "config" / "confirmatory.json"))

def test_face_validation_receipt_gate(tmp_path):
    report = validate_face_validation_receipt(
        ROOT / "inputs" / "face_validation_receipt.json", load_config(CONFIG), ROOT.parent / "main.pdf"
    )
    assert report.status == "PENDING"
    assert "APPROVED" in report.cause
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py::test_config_contract_and_hash`

Expected: FAIL because the canonical loader, scenario enumeration and face report do not yet exist.

- [ ] **Step 3: Implement the minimum GREEN contract.**

  - Serialize config and rubric with ordered keys, `(',', ':')`, UTF-8 and one LF; reject unknown keys, wrong levels, wrong loop order, non-72 product, invalid policies, bad rho/stratum boundaries or seed range.
  - Encode `confirmatory.json` with all exact fatorial, horizon, controls, distributions, event and policy values plus a `capacity` object containing `min_free_ram_gib=4`, `reserve_ram_gib=2`, `max_workers=4`, `receipt_ttl_seconds=60`, `disk_margin=1.25`, `disk_reserve_gib=5`, and the canonical CPU-only provider requirement; encode `validation.json` exactly as the three scenario indices, seed and five policies required by the spec.
  - Materialize the full rubric JSON from the spec and a receipt file whose status/final decision is `PENDING`, with no invented reviewer IDs, decisions, hashes or rationale; the template leaves those human fields empty.
  - Implement path-confined rubric resolution, real SHA-256 of `main.pdf` and rubric, distinct independent reviewers, `blind=true`, protocol/config equality, discrepancy decisions and causal `PENDING` reports; never silently promote a template. Every later generator/runner/sensitivity API receives this report as an argument and cannot consult global face state.
  - Remove legacy `RUN_PROFILE`, `load-confirmatory`, environment/latest discovery, old aliases and old manifest schema assertions from `test_config_manifest.py`; replace them with canonical config, `CapacityRequirements` and explicit face-report tests.

- [ ] **Step 4: Run the focused GREEN and face checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py`

Expected: PASS for stable 72-scenario enumeration and `FACE_VALIDATION=PENDING` for the unapproved receipt.

- [ ] **Step 5: Commit the task files (executor command; do not run during plan authoring).**

```bash
rtk git add experimento-notebook/config/confirmatory.json experimento-notebook/config/validation.json experimento-notebook/inputs/face_validation_rubric.v1.json experimento-notebook/inputs/face_validation_receipt.template.v1.json experimento-notebook/inputs/face_validation_receipt.json experimento-notebook/src/pequiflux_experiment/config.py experimento-notebook/src/pequiflux_experiment/face_validation.py experimento-notebook/tests/test_config_manifest.py experimento-notebook/pyproject.toml experimento-notebook/requirements.lock
rtk git commit -m "feat(experimento): freeze config and face validation gate"
```

### Task 2: Frozen domain, deterministic generator and complete hash chain

**Files:**
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/domain.py`
- Create: `experimento-notebook/src/pequiflux_experiment/dataset.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/manifest.py`
- Modify/Replace: `experimento-notebook/tests/test_config_manifest.py` (replace legacy tiny/full-generation assumptions with pure planning and header-spy orchestration checks)
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/config.py` to expose canonical bytes and CRN helpers.

**Interfaces:**
- Consumes: `ExperimentConfig`, an explicit `FaceValidationReport`, and the pure `DatasetPlan`.
- Produces: immutable `Truck`, `Resource`, `FrozenInstance`, `FrozenDataset`; `plan_synthetic_dataset(config) -> DatasetPlan`; `generate_synthetic_dataset(config, face_report, dataset_root, *, now_utc, generator_version)`; `validate_frozen_dataset(path, expected_plan=None, strict_production=False)`; `freeze_dataset`; `load_frozen_dataset`; canonical manifest/checksum functions. The reduced validation integration is deliberately introduced in Task 5 after this production planning/freeze contract.

- [ ] **Step 1: Write the failing test (RED).**

```python
from pathlib import Path
from datetime import datetime, timezone
import pytest

from pequiflux_experiment.config import load_config
from pequiflux_experiment.dataset import DatasetContractError, plan_synthetic_dataset, generate_synthetic_dataset, validate_frozen_dataset

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "config" / "confirmatory.json")
FIXED_NOW = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)

def test_synthetic_plan_contract():
    plan = plan_synthetic_dataset(CONFIG)
    assert plan.scenario_indices == tuple(range(72))
    assert plan.instance_count == 3_600
    assert plan.policy_day_count == 18_000
    assert plan.instance_ids[0] == "s00-seed101"
    assert plan.instance_ids[-1] == "s71-seed150"

def test_generate_freezes_complete_dataset(tmp_path, approved_face, monkeypatch):
    plan = plan_synthetic_dataset(CONFIG)
    class HeaderMaterializerSpy:
        count = 0
        def __call__(self, header, writer):
            self.count += 1
            writer.write_header({"instance_id": header.instance_id, "generation_attempt": 0})
    writer = HeaderMaterializerSpy()
    monkeypatch.setattr("pequiflux_experiment.dataset._materialize_production_header", writer)
    generate_synthetic_dataset(CONFIG, approved_face, tmp_path, now_utc=FIXED_NOW, generator_version="generator.v1")
    assert writer.count == 3_600
    validate_frozen_dataset(tmp_path, expected_plan=plan, strict_production=True)

def test_production_refuses_incomplete_freeze(tmp_path, approved_face):
    with pytest.raises(DatasetContractError, match="3,600"):
        validate_frozen_dataset(tmp_path, expected_plan=plan_synthetic_dataset(CONFIG), strict_production=True)
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py::test_synthetic_plan_contract`

Expected: FAIL because the pure plan, explicit face-report signature and freeze validator are absent.

- [ ] **Step 3: Implement generation and freeze.**

  - Make `plan_synthetic_dataset(config)` pure and cheap: return all 72 ordered headers, exact 3,600 instance IDs, 18,000 policy-day keys and cardinalities without writing or sampling. The production API has no reduced/fallback flag; it accepts only an explicit face report and the complete plan.
  - Build canonical immutable payloads for `scenario_index`, trucks, four service times per truck, priority/document state, disruptions and rejection records; use CRN substreams keyed by the exact tuple and stable `(arrival_time, truck_id)` ordering. Do not add a reduced/fallback selector to this production API; Task 5 owns the separate three-instance validation integration.
  - Write Parquet/JSONL payloads, `manifest.json`, `rejection_log.jsonl`, and checksums via a staging directory. Hash only the five payload files; `checksums.sha256` is ordered `relative_name<TAB>sha256_hex`, `manifest_hash=sha256(canonical manifest bytes)`, `checksums_hash=sha256(canonical checksum bytes)`, and `dataset_root_hash=sha256(manifest_hash+":"+checksums_hash)`. Exclude `manifest.json`, `FREEZE.json`, and `checksums.sha256` from their own checksum list.
  - Define `FREEZE.json` with exactly `manifest_hash`, `checksums_hash`, and `dataset_root_hash`; manifest fields include `dataset_id`, `phase=synthetic`, protocol/config/scenario hashes, `instance_count=3600`, `scenario_count=72`, `seed_count=50`, CRN/generator versions, frozen parameters, `freeze_status`, UTC time, commit/dirty state, runtime inventory, ordered five-payload hashes, rejection count, `policy_days_executed=false`, and `resample_provenance=null` for initial generation.
  - For `test_generate_freezes_complete_dataset`, exercise all 3,600 headers with an internal deterministic lightweight materializer/writer spy and strict validator; do not generate full truck/service payloads in pytest. Full materialization is a campaign action gated by the approved face receipt, not permanent test evidence.
  - Have loaders reject absent/corrupt/altered freeze, missing fields, extra fields, non-finite values, collisions and changed hashes before returning `FrozenInstance`; a `PENDING` face report must fail before creating any namespace.
  - Remove obsolete `tiny_scenario`, old IDs/aliases, old results schema and legacy `test_config_manifest.py` expectations; retain only the canonical plan/freeze/validation assertions.

- [ ] **Step 4: Run the generator and refusal checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py -k "synthetic_plan or generate_freezes_complete_dataset or incomplete_freeze"`

Expected: PASS for the pure 3,600-instance plan, header orchestration and explicit incomplete-freeze error; no full payload campaign runs in pytest.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/domain.py experimento-notebook/src/pequiflux_experiment/dataset.py experimento-notebook/src/pequiflux_experiment/manifest.py experimento-notebook/src/pequiflux_experiment/config.py experimento-notebook/tests/test_config_manifest.py
rtk git commit -m "feat(experimento): generate and freeze canonical dataset"
```

### Task 3: STAGING rejection and explicit one-attempt resample

**Files:**
- Modify/Replace: `experimento-notebook/tests/test_config_manifest.py` (replace any implicit retry/source-dataset assumptions)
- Modify: `experimento-notebook/src/pequiflux_experiment/dataset.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/manifest.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/domain.py` for `AbortedStaging` and provenance types.

**Interfaces:**
- Consumes: an `AbortedStaging` path, explicit approved `FaceValidationReport`, the declared `source_staging_root_hash`, and the exact rejected `instance_id` list.
- Produces: `generate_synthetic_dataset(config, face_report, dataset_root, *, now_utc, generator_version)`; `load_aborted_staging(path) -> AbortedStaging`; `resample_synthetic_dataset(config, face_report, source_staging_path, source_staging_root_hash, exact_rejected_ids, destination_root, *, now_utc, generator_version)`; `resample_provenance.json`; `generation_attempt` in every derived CRN key. The private `_validate_candidate(candidate) -> bool` seam is monkeypatched only by deterministic tests; neither public API accepts an injector or fallback.

- [ ] **Step 1: Write the failing test (RED).**

```python
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from pequiflux_experiment.config import load_config
from pequiflux_experiment.dataset import (
    GenerationRejectedError,
    generate_synthetic_dataset,
    load_aborted_staging,
    resample_synthetic_dataset,
)
from pequiflux_experiment.manifest import canonical_file_hash

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "config" / "confirmatory.json")
FIXED_NOW = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)

def test_explicit_resample_provenance_and_abort(tmp_path, approved_face, monkeypatch):
    rejected = ["s20-seed101"]
    # Test-only deterministic seam: reject this ID only on its first attempt;
    # the explicit resample at generation_attempt=1 must be accepted.
    monkeypatch.setattr(
        "pequiflux_experiment.dataset._validate_candidate",
        lambda candidate: not (
            candidate.instance_id in rejected and candidate.generation_attempt == 0
        ),
    )
    with pytest.raises(GenerationRejectedError, match="EXPLICIT_RESAMPLE_REQUIRED"):
        generate_synthetic_dataset(
            CONFIG, approved_face, tmp_path / "staging", now_utc=FIXED_NOW,
            generator_version="generator.v1",
        )
    staging = load_aborted_staging(tmp_path / "staging")
    aborted = json.loads((tmp_path / "staging" / "STAGING.json").read_text())
    assert aborted["status"] == "ABORTED"
    assert not (tmp_path / "staging" / "FREEZE.json").exists()
    source_root = aborted["staging_root_hash"]
    out = resample_synthetic_dataset(
        CONFIG, approved_face, tmp_path / "staging", source_root, rejected,
        tmp_path / "resampled", now_utc=FIXED_NOW, generator_version="generator.v1"
    )
    prov = json.loads((tmp_path / "resampled" / "resample_provenance.json").read_text())
    assert prov["source_staging_root_hash"] == source_root
    assert prov["generation_attempts"] == {"s20-seed101": 1}
    assert out.instance("s12-seed101").canonical_record_hash == staging.instance("s12-seed101").canonical_record_hash
    assert out.instance("s20-seed101").generation_attempt == 1
    assert out.manifest["resample_provenance"]["sha256"] == canonical_file_hash(tmp_path / "resampled" / "resample_provenance.json")

def test_new_rejection_aborts_without_retry(tmp_path, approved_face, monkeypatch):
    rejected = ["s20-seed101"]
    # Always reject this ID, including attempt 1, to prove fail-closed abort.
    monkeypatch.setattr(
        "pequiflux_experiment.dataset._validate_candidate",
        lambda candidate: candidate.instance_id not in rejected,
    )
    with pytest.raises(GenerationRejectedError):
        generate_synthetic_dataset(
            CONFIG, approved_face, tmp_path / "source", now_utc=FIXED_NOW,
            generator_version="generator.v1",
        )
    source = load_aborted_staging(tmp_path / "source")
    with pytest.raises(GenerationRejectedError, match="EXPLICIT_RESAMPLE_REQUIRED"):
        resample_synthetic_dataset(
            CONFIG, approved_face, source.path, source.staging_root_hash, ["s20-seed101"],
            tmp_path / "again", now_utc=FIXED_NOW, generator_version="generator.v1",
        )
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py::test_explicit_resample_provenance_and_abort`

Expected: FAIL because `AbortedStaging`, explicit face/report/source-root validation and one-attempt provenance are not implemented.

- [ ] **Step 3: Implement the fail-fast STAGING flow.**

  - Keep both public dataset signatures free of test controls: accept the explicit face report and use only the private `_validate_candidate(candidate)` seam under `monkeypatch` in tests. On rejection, atomically finish payloads, manifest and checksums, then write `STAGING.json` exactly with `status='ABORTED'`, `manifest_hash`, `checksums_hash`, `staging_root_hash=sha256(manifest_hash+':'+checksums_hash)`, `accepted_instance_ids`, `rejected_instance_ids`, and `next_candidate_ordinal`; never write `FREEZE.json` or retry.
  - Require `resample_synthetic_dataset(config, approved_face, source_staging_path, source_staging_root_hash, exact_rejected_ids, destination, ...)`. Validate the full STAGING/manifest/checksum chain, partition and source root before creating a destination namespace.
  - Preserve accepted canonical records and `instance_hash` values (not physical Parquet bytes); resample each rejected ID exactly once at `generation_attempt=previous+1`, leave not-yet-generated candidates at attempt 0, and stop on a new rejection.
  - Persist canonical `resample_provenance.json` with `source_dataset_id`, source root hash, ordered IDs, generation attempts, accepted record/instance hashes and authorizing action. Reference its real canonical SHA in the new manifest. Reject IDs missing/extra/duplicated, root/hash mismatches, destination collisions, or a `PENDING` face report before any namespace.
  - Remove any legacy source-data hash alias, automatic retry helper, fallback alias or hidden resample path from tests and APIs; preserve aborted staging and rejection logs for diagnosis.

- [ ] **Step 4: Run the resample and abort checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py -k "resample or staging"`

Expected: PASS with exactly one attempt per rejected ID and a visible no-retry failure on a second rejection.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/dataset.py experimento-notebook/src/pequiflux_experiment/manifest.py experimento-notebook/src/pequiflux_experiment/domain.py experimento-notebook/tests/test_config_manifest.py
rtk git commit -m "feat(experimento): make rejection resampling explicit and auditable"
```

### Task 4: Frozen-domain emulator, event ranks and five dispatch policies

**Files:**
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/events.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/dispatch.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/policies.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/emulator.py`
- Modify/Replace: `experimento-notebook/tests/test_dispatch_emulator.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/domain.py` for immutable snapshots/results.

**Interfaces:**
- Consumes: `FrozenInstance`, `DispatchPolicy`, events/disruptions and immutable `ExperimentConfig`.
- Produces: `run_day(instance: FrozenInstance, policy: DispatchPolicy | str) -> DayResult`; `DispatchContext`; `make_policy`; `filter_admissible`; `process_event_batch(events, state) -> BatchResult`; stable event ranks and serialized event logs. `DayResult` contains only complete simulation primitives/events/snapshots/hashes; `MetricRow` is intentionally absent until Task 5.

- [ ] **Step 1: Write the failing tests (RED).**

```python
def test_run_day_requires_frozen_instance():
    with pytest.raises(InstanceContractError, match="FrozenInstance"):
        run_day(ScenarioConfig(N=60, m=1, b=1, regime="nominal"), "lexicographic")

def test_crn_is_policy_independent(frozen_instance):
    results = [run_day(frozen_instance, name) for name in CANONICAL_POLICIES]
    assert {r.instance_hash for r in results} == {frozen_instance.instance_hash}
    assert {canonical_exogenous(r.events) for r in results} == {canonical_exogenous(results[0].events)}

def test_event_rank_contract():
    assert EVENT_RANKS == {
        "service_completion": 0, "resource_recovery": 10, "rain_end": 11,
        "resource_failure": 12, "rain_start": 13, "document_release": 20,
        "priority_change": 21, "arrival": 30,
    }
    batch = process_event_batch(
        [Event(time=240, event_type="arrival", event_rank=30, resource_id="", truck_id="T-001", sequence=1),
         Event(time=240, event_type="resource_failure", event_rank=12, resource_id="hopper-1", truck_id="", sequence=2)],
        DispatchState.empty(),
    )
    assert batch.dispatch_sequence == ("resource_failure", "arrival", "dispatch")
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_dispatch_emulator.py::test_run_day_requires_frozen_instance`

Expected: FAIL because the emulator still accepts legacy scenario/seed inputs or does not exist.

- [ ] **Step 3: Implement the minimum deterministic DES.**

  - Remove random calls, generation, lazy durations/default fields and tiny legacy shortcuts from the execution path. Validate exact truck/service/disruption cardinalities, hashes and required fields before scheduling event rank zero.
  - Define exact numeric event ranks `0,10,11,12,13,20,21,30` for service completion, resource recovery, rain end, resource failure, rain start, document release, priority change and arrival. Sort by `(time,event_rank,resource_id_or_empty,truck_id_or_empty,sequence)` and apply the complete same-timestamp batch before any dispatch; recovery/end precede new failure/start and a new unavailability wins collisions.
  - Implement one common admissibility filter for cargo/resource compatibility, document, failure/availability, rain closure, precedence and buffer; `fifo_strict` sees only the raw queue head and idles when it is inadmissible, while the other four rank the same `C_adm`.
  - Implement exact `fifo_flow_faithful`, `priority_local`, frozen `fixed_score`, and pressure/mandatory-priority/reorder-penalty/affinity `lexicographic` rules. Commands never mutate policy inputs; human overrides require authorized profile, reason and rechecked constraints.
  - Emit immutable `DayResult` with consumed instance/hash, complete events/logs, physical/digital snapshots, A1 counts, A2 fields, remnant queue and replay hashes, but no metric field or fabricated metric value. Task 5's public `compute_policy_day_metrics(persisted_day)` is called by `run_policy_days` after the day/log has been persisted and before the policy-day row is committed; a run cannot close without its complete hashed `MetricRow`, and audit later recomputes/reconciles it.
  - Remove `tiny_scenario`, the old `run_day(scenario, seed, policy)` overload, random/generation/lazy-duration paths, old IDs/aliases and old event/result-schema assertions from `test_dispatch_emulator.py`; all callers use `run_day(FrozenInstance, policy)`.

- [ ] **Step 4: Run emulator and CRN checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_dispatch_emulator.py`

Expected: PASS for early rejection of non-frozen input and equal exogenous event payloads across all five policies.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/events.py experimento-notebook/src/pequiflux_experiment/dispatch.py experimento-notebook/src/pequiflux_experiment/policies.py experimento-notebook/src/pequiflux_experiment/emulator.py experimento-notebook/src/pequiflux_experiment/domain.py experimento-notebook/tests/test_dispatch_emulator.py
rtk git commit -m "feat(experimento): run deterministic frozen-instance dispatch"
```

### Task 5: Eight metric families, validation action and persisted A1 contexts

**Files:**
- Create: `experimento-notebook/src/pequiflux_experiment/metrics.py`
- Create: `experimento-notebook/src/pequiflux_experiment/validation.py`
- Modify/Replace: `experimento-notebook/tests/test_dispatch_emulator.py` for persisted A1 fixture consumption and fail-closed assertions.
- Modify/Replace: `experimento-notebook/tests/test_a2_structural.py` to remove old metric/override expectations and use the new persisted contexts.
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/domain.py` for `MetricRow` and `ValidationReport`.

**Interfaces:**
- Consumes: an explicit approved/PENDING `FaceValidationReport`, frozen validation dataset, persisted event logs and `config/validation.json`; never calls a generator during checks.
- Produces: `compute_policy_day_metrics(persisted_day) -> MetricRow`; `build_validation_dataset(config, validation_config, run_root, face_report) -> FrozenValidationDataset`; `run_validation_checks(dataset) -> ValidationReport`; `run_a1_adversarial_suite(fixtures_path) -> A1Report`; eight canonical A1 `dispatch_context` fixtures and `validation_scope_hash`. The runner invokes this sole producer after each event log is persisted and before its row is committed, and `audit_run` recomputes/reconciles the same hashes, so no persisted result lacks canonical metrics.

- [ ] **Step 1: Write the failing tests (RED).**

```python
def test_validation_dataset_persisted_and_non_confirmatory(tmp_path, APPROVED_FACE):
    dataset = build_validation_dataset(CONFIG, VALIDATION_CONFIG, tmp_path, APPROVED_FACE)
    report = run_validation_checks(dataset)
    assert dataset.scenario_indices == (20, 12, 24)
    assert dataset.seeds == (101,)
    assert len(dataset.policy_days) == 15
    assert len(dataset.a1_fixtures) == 8
    assert dataset.manifest["non_confirmatory"] is True
    assert dataset.manifest["FACE_VALIDATION"] == "APPROVED"
    assert report.validation_scope_hash

def test_validation_dataset_persisted_with_pending_face(tmp_path, PENDING_FACE):
    dataset = build_validation_dataset(CONFIG, VALIDATION_CONFIG, tmp_path, PENDING_FACE)
    report = run_validation_checks(dataset)
    assert (tmp_path / "validation_dataset" / "FREEZE.json").exists()
    assert len(dataset.instances) == 3
    assert len(dataset.policy_days) == 15
    assert dataset.manifest["non_confirmatory"] is True
    assert dataset.manifest["FACE_VALIDATION"] == "PENDING"
    assert dataset.manifest["face_validation_cause"]
    assert report.validation_scope_hash

def test_metrics_have_eight_families_and_exploratory_co2(persisted_day):
    row = compute_policy_day_metrics(persisted_day)
    assert set(row.families) == {"queue_wait", "throughput", "system_time", "makespan", "utilization", "stability", "feasibility", "co2"}
    assert row.co2_exploratory is True
    assert all(math.isfinite(value) for value in row.numeric_values())

def test_a1_adversarial_suite_fail_closed(tmp_path, monkeypatch):
    dataset = build_validation_dataset(CONFIG, VALIDATION_CONFIG, tmp_path, APPROVED_FACE)
    fixtures_path = tmp_path / "validation_dataset" / "a1_adversarial_fixtures.jsonl"
    fixtures = [json.loads(line) for line in fixtures_path.read_text().splitlines()]
    assert len(fixtures) == 8
    assert sum(f["expected_outcome"] == "BLOCK_NO_COMMAND" for f in fixtures) == 7
    assert next(f for f in fixtures if f["fixture_id"] == "f08")["expected_outcome"] == "SELECT_T-002_P2"
    monkeypatch.setattr("pequiflux_experiment.validation.build_validation_dataset", lambda *a, **k: (_ for _ in ()).throw(AssertionError("builder called")))
    monkeypatch.setattr("pequiflux_experiment.validation.generate_synthetic_dataset", lambda *a, **k: (_ for _ in ()).throw(AssertionError("generator called")), raising=False)
    report = run_a1_adversarial_suite(fixtures_path)
    assert report.checked_fixture_ids == tuple(f["fixture_id"] for f in fixtures)
    assert report.violations == []
    assert report.status == "PASS"
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_dispatch_emulator.py::test_a1_adversarial_suite_fail_closed`

Expected: FAIL because persisted validation contexts, disk-only A1 evaluation and metric families are absent.

- [ ] **Step 3: Implement validation and metrics.**

  - Read and verify the exact validation JSON order: index 20 = `n60-m3-b2-nominal`/low, 12 = `n60-m2-b2-nominal`/medium, 24 = `n120-m1-b1-nominal`/high; accept the explicit face report and always persist exactly three instances and fifteen policy-days in a separate `validation__<run_id>` namespace. With `APPROVED_FACE` record `FACE_VALIDATION=APPROVED`; with `PENDING_FACE` still create the complete reduced package and record `FACE_VALIDATION=PENDING` plus its cause. This action never blocks on the face status.
  - Derive and persist exactly eight complete A1 contexts (`f01`–`f08`) from `s20-seed101`, `s12-seed101`, and `s24-seed101`, with the seven `BLOCK_NO_COMMAND` outcomes and mandatory-priority `SELECT_T-002_P2`; hash every line excluding its hash field. `run_a1_adversarial_suite` reads this file from disk only, and the regression monkeypatch proves it never calls a builder/generator.
  - Set `non_confirmatory=true`, `validation_scope_hash=sha256(canonical_bytes(config/validation.json)+":"+canonical_bytes(a1_adversarial_fixtures.jsonl))`, and persist the face status/cause. All checks read only these files.
  - Compute queue wait p50/p95/mean/IQR/censored remnants; throughput count/rate/paired median; system time; makespan; resource utilization/idle; stability/reordering; feasibility/A2 fields; and `E_CO2=sum(wait_queue_i/60)*0,8*10,18` as exploratory. Missing values raise instead of writing `0`, `NaN` or success text. `DayResult` has no metric field; `MetricRow` is created only here.
  - Replace the old `test_dispatch_emulator.py` and `test_a2_structural.py` fixtures that construct tiny scenarios or expect legacy metric fields; they must consume the eight persisted contexts and assert all seven blocks plus f08 priority selection.

- [ ] **Step 4: Run validation and metric checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_a2_structural.py::test_metrics_have_eight_families_and_exploratory_co2 experimento-notebook\\tests\\test_dispatch_emulator.py::test_validation_dataset_persisted_and_non_confirmatory experimento-notebook\\tests\\test_dispatch_emulator.py::test_validation_dataset_persisted_with_pending_face experimento-notebook\\tests\\test_dispatch_emulator.py::test_a1_adversarial_suite_fail_closed`

Expected: PASS for metrics, fifteen persisted validation policy-days with both APPROVED and PENDING face reports, eight disk-backed A1 fixtures, stable scope hash and all eight finite metric families.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/metrics.py experimento-notebook/src/pequiflux_experiment/validation.py experimento-notebook/src/pequiflux_experiment/domain.py experimento-notebook/tests/test_dispatch_emulator.py experimento-notebook/tests/test_a2_structural.py
rtk git commit -m "feat(experimento): add validation package and metric families"
```

### Task 6: Capacity gates, pilot/confirmatory execution and atomic run bundles

**Files:**
- Create: `experimento-notebook/src/pequiflux_experiment/capacity.py`
- Create: `experimento-notebook/src/pequiflux_experiment/profiles.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/experiment.py`
- Modify/Replace: `experimento-notebook/tests/test_experiment_audit.py` (remove legacy matrix/cardinality execution)
- Modify: `experimento-notebook/src/pequiflux_experiment/manifest.py` and `metrics.py` for run receipts and policy-day rows.

**Interfaces:**
- Consumes: frozen dataset, explicit `FaceValidationReport`, canonical policy list, phase (`validation`, `pilot` or `execute-confirmatory`), workload and requirements.
- Produces: `ConfirmatoryWorkload.from_dataset(frozen_dataset, config) -> ConfirmatoryWorkload`; `plan_policy_days(dataset, policies, phase) -> PolicyDayPlan`; `inspect_capacity(workload, requirements, run_root, providers=...) -> CapacityReceipt`; `require_capacity(receipt)`; `run_policy_days(dataset, policies, phase, run_root, face_report, capacity_receipt=None, worker=...) -> RunBundle`; `load_run_bundle(run_id)`.

- [ ] **Step 1: Write the failing tests (RED).**

```python
def test_capacity_gate_blocks_with_cause(tmp_path, low_disk_provider, frozen_dataset):
    workload = ConfirmatoryWorkload.from_dataset(frozen_dataset, CONFIG)
    receipt = inspect_capacity(workload, CONFIG.capacity, tmp_path, providers=low_disk_provider)
    with pytest.raises(CapacityGateError, match="required_disk_bytes"):
        require_capacity(receipt)
    assert receipt.decision == "BLOCKED"
    assert not (tmp_path / "runs").exists()

def test_policy_day_plan_cardinality_without_des(frozen_dataset):
    assert plan_policy_days(frozen_dataset, CANONICAL_POLICIES, "pilot").count == 3_750
    assert plan_policy_days(frozen_dataset, CANONICAL_POLICIES, "execute-confirmatory").count == 18_000

def test_validation_runner_always_persists_with_pending_face(tmp_path, validation_dataset, pending_face, blocked_capacity, spy_worker):
    bundle = run_policy_days(validation_dataset, CANONICAL_POLICIES, "validation", tmp_path, pending_face, blocked_capacity, worker=spy_worker)
    assert bundle.policy_day_count == 15
    assert bundle.namespace_closed is True
    assert spy_worker.calls == 15

def test_face_or_capacity_block_makes_zero_worker_calls(tmp_path, validation_dataset, pending_face, blocked_capacity, spy_worker):
    with pytest.raises((FaceValidationError, CapacityGateError)):
        run_policy_days(validation_dataset, CANONICAL_POLICIES, "execute-confirmatory", tmp_path / "blocked", pending_face, blocked_capacity, worker=spy_worker)
    assert spy_worker.calls == 0
    assert not (tmp_path / "blocked").exists()
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py::test_capacity_gate_blocks_with_cause`

Expected: FAIL because `profiles.py`, explicit face/capacity gates and injected provider/worker seams are not present.

- [ ] **Step 3: Implement one-shot capacity and phase execution.**

  - Define `ConfirmatoryWorkload.from_dataset(frozen_dataset, config)` from the actual frozen dataset size and canonical dataset/config/workload hashes; it must not accept a config-only constructor or infer a dataset. Define `profiles.py` with explicit phase/profile fields and pure `plan_policy_days` key construction.
  - Inspect the complete confirmatory workload, dataset size, free disk/RAM, logical CPU, GPU/driver inventory and competing Python/Jupyter/pytest processes via `inspect_capacity(workload, requirements, run_root, providers=...)` only for `execute-confirmatory`. Register only the current kernel/descendants; block another project process or unproven ownership with an operation/workload/cause error.
  - Persist TTL-60-second receipt with exact disk/RAM formulas, authorized workers, estimated rows/logs, config/dataset/workload hashes, timestamp, inspection version and decision. Revalidate immediately before creating the `execute-confirmatory` namespace; do not gate `pilot` or `sensitivity` on this receipt, and do not wait, retry, kill, change precision, or shrink scope.
  - Select the pilot by canonical hash to exactly `ceil(0,20*72)=15` scenarios and define its 3,750-key plan; require the full frozen dataset for confirmation and define its 18,000-key plan. Production `run_policy_days` refuses partial pilot/confirmatory selections, missing/extra/duplicate keys and mixed hashes.
  - Keep permanent tests cheap: plan cardinality is pure; the only runner integration uses the 15-row persisted validation dataset with an injected worker to prove atomicity/hash. A low-disk/process or pending-face receipt is tested with a spied worker and must create zero calls and zero namespaces. No pytest path executes a full DES campaign.
  - Branch `phase="validation"` before any confirmatory gate: it always writes the reduced persisted package even with `PENDING` face and no/blocked capacity receipt. For `pilot`, require only the explicit approved face report and existing complete frozen dataset; for `execute-confirmatory`, check face and frozen dataset first, then revalidate the explicit capacity receipt immediately before namespace creation. Sensitivity follows its own approved-face/frozen-dataset namespace without this capacity gate. Write each row/log progressively into staging and atomically rename only after complete cardinality/hash checks. Every API receives `face_report` and never consults hidden global state.
  - Remove `run_experiment_matrix`, old `RUN_PROFILE`/`load-confirmatory` routing, tiny fixtures and old results schemas from `test_experiment_audit.py`; replace them with plans, injected validation runner and gate assertions.

- [ ] **Step 4: Run capacity and execution checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py -k "capacity_gate or policy_day_plan or validation_runner or face_or_capacity_block"`

Expected: PASS for causal low-resource blocking, pure exact plans, tiny validation atomicity and zero worker/namespace calls when a gate fails.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/capacity.py experimento-notebook/src/pequiflux_experiment/profiles.py experimento-notebook/src/pequiflux_experiment/experiment.py experimento-notebook/src/pequiflux_experiment/manifest.py experimento-notebook/src/pequiflux_experiment/metrics.py experimento-notebook/tests/test_experiment_audit.py
rtk git commit -m "feat(experimento): gate and persist pilot and confirmatory runs"
```

### Task 7: Independent replay/audit, A1 adjudication and A2 workflow

**Files:**
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/digital_model.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/replay.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/audit.py`
- Create: `experimento-notebook/src/pequiflux_experiment/a2.py`
- Modify/Replace: `experimento-notebook/tests/test_experiment_audit.py` for audit/replay integration and old API removal.
- Modify/Replace: `experimento-notebook/tests/test_digital_model_replay.py`
- Modify: `experimento-notebook/src/pequiflux_experiment/validation.py` to call the persisted-fixture A1 suite.

**Interfaces:**
- Consumes: persisted event JSONL, snapshots, A1 contexts, confirmatory run bundle and A2 rubric.
- Produces: `DigitalModel.apply`, `snapshot`, `replay_events`, `replay_run`; `audit_run`; `run_a1_adversarial_suite`; `build_a2_sample`; `apply_rubric(sample, labels_by_reviewer)`; `compute_cohen_kappa(labels_by_reviewer)`; `persist_a2_review`.

- [ ] **Step 1: Write the failing tests (RED).**

```python
def test_replay_matches_independent_projection(run_bundle):
    replay = replay_run(run_bundle)
    assert replay.final_snapshot_hash == run_bundle.digital_snapshot_hash
    assert replay.event_count == run_bundle.event_count

def test_a2_sample_rubric_and_kappa_contract(run_bundle, tmp_path):
    sample = build_a2_sample(run_bundle, tmp_path)
    assert all(item.sample_size == min(item.decision_count, max(50, math.ceil(.10 * item.decision_count))) for item in sample.by_scenario)
    assert {"truck_stage", "resource", "rules", "reason", "fifo_break"} <= set(sample.fields)
    assert apply_rubric(sample, labels_by_reviewer={}).human_status == "PENDING"
    one = apply_rubric(sample, labels_by_reviewer={"reviewer-1": ["PASS"] * sample.total_items})
    assert one.human_status == "COMPLETE"
    assert one.kappa_status == "not_applicable"
    two_labels = {"reviewer-1": ["PASS"] * sample.total_items, "reviewer-2": ["PASS"] * sample.total_items}
    assert compute_cohen_kappa(two_labels).global_kappa == pytest.approx(1.0)
    disagree = {"reviewer-1": ["PASS"] * sample.total_items, "reviewer-2": ["FAIL"] * sample.total_items}
    assert apply_rubric(sample, labels_by_reviewer=disagree).human_status == "PENDING"
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_digital_model_replay.py::test_replay_matches_independent_projection`

Expected: FAIL because no independent projection, replay or audit layer exists.

- [ ] **Step 3: Implement independent audit and review contracts.**

  - Implement a separate mutable `DigitalModel` that consumes only serialized events; reject duplicate/regressive sequence, impossible transitions and hash divergence. `replay_run` must not call `run_day` or regenerate an instance.
  - Audit checksums, cardinality, unique keys, monotonic event times/ranks, hard constraints, no command in blocked state, no illegal override, complete A1 fixture outcomes, A2 structural five-field coverage, mixed hashes and replay equality; producer reports are not trusted.
  - Deserialize the eight persisted contexts only, run all seven blocked outcomes and mandatory priority, persist `a1_adversarial.jsonl`/`a1_report.json`, and fail A1 on any violation or swallowed exception.
  - Build per-scenario A2 sample by hash order using `n_s=min(D_s,max(50,ceil(.10*D_s)))`; persist workflow, selected decision/log hash and `a2_rubric_v1`. No labels means `A2_human=PENDING`; one explicit reviewer label set with complete PASS labels may become `COMPLETE` without kappa; two explicit independent blind label sets persist labels/reasons and Cohen kappa per scenario/global; κ<0,60 or any missing/unclear/fail leaves `A2_human=PENDING`. `compute_cohen_kappa` accepts label sets, never a reviewer count alone.
  - Remove old `test_experiment_audit.py`/`test_digital_model_replay.py` assumptions about `run_experiment_matrix`, legacy IDs/results schema, shared mutable state or reviewer-count-only kappa; replace with persisted logs and explicit label sets.

- [ ] **Step 4: Run replay, A1 and A2 checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_digital_model_replay.py experimento-notebook\\tests\\test_experiment_audit.py -k "replay or a2"`

Expected: PASS for hash-equal independent replay, zero persisted A1 violations and correct single/two-reviewer A2 pending/kappa semantics.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/digital_model.py experimento-notebook/src/pequiflux_experiment/replay.py experimento-notebook/src/pequiflux_experiment/audit.py experimento-notebook/src/pequiflux_experiment/a2.py experimento-notebook/src/pequiflux_experiment/validation.py experimento-notebook/tests/test_digital_model_replay.py experimento-notebook/tests/test_experiment_audit.py
rtk git commit -m "feat(experimento): add independent replay and audit workflows"
```

### Task 8: Confirmatory H1 statistics, pairing and invalid-input rules

**Files:**
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/statistics.py`
- Modify/Replace: `experimento-notebook/tests/test_statistics_export.py` (remove legacy aggregate/false-positive expectations)
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/experiment.py` and `audit.py` to expose only closed, audited confirmatory bundles.

**Interfaces:**
- Consumes: audited `execute-confirmatory` rows with one immutable hash per `(scenario_index, seed)`, config strata and metric rows.
- Produces: `paired_dataframe`; `evaluate_h1(confirmatory_bundle, config) -> H1Report`; robust estimators, IUT components and Holm-adjusted decisions.

- [ ] **Step 1: Write the failing tests (RED).**

```python
def test_iut_holm_and_invalid_pairing(audited_confirmatory_bundle):
    report = evaluate_h1(audited_confirmatory_bundle, CONFIG)
    assert report.strata == ("medium", "high")
    assert report.comparators == ("fifo_flow_faithful", "priority_local", "fixed_score")
    assert report.bootstrap_resamples == 5_000
    assert report.holm_alpha == pytest.approx(.05)
    assert report.h1 in {"SUPPORTED", "NOT_SUPPORTED"}

def test_invalid_pairing_is_not_inconclusive(bundle_with_duplicate_pair):
    with pytest.raises(InvalidInputError, match="duplicate.*scenario_index.*seed"):
        evaluate_h1(bundle_with_duplicate_pair, CONFIG)

def test_aggregate_relative_median_false_positive_is_rejected():
    p95_comp = [100.0] * 300 + [1000.0] * 300
    p95_lex = [80.0] * 300 + [860.0] * 300
    bundle = make_complete_audited_bundle_from_pairs(p95_comp, p95_lex, strata=("medium", "high"))
    report = evaluate_h1(bundle, CONFIG)
    assert report.aggregate_relative_median == pytest.approx(.17, abs=.01)
    assert report.h1 == "NOT_SUPPORTED"
    assert all(component.p_value > .05 for component in report.components_for("medium"))
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_statistics_export.py::test_aggregate_relative_median_false_positive_is_rejected`

Expected: FAIL because H1 pairing, stratum-level p-value aggregation and the concrete aggregate-relative-median regression are absent.

- [ ] **Step 3: Implement exact H1 inference.**

  - Pair only `(scenario_index, seed)` and compare lexicographic with each primary comparator in medium/high. Compute `g_i=(p95_comp-p95_lexicographic)/p95_comp`, reject zero denominators, missing/duplicate pairs and mixed hashes as `H1=INVALID_INPUT` with causal error.
  - For each `(stratum, comparator)`, test `median(g_i-.15)>0` with one-sided Wilcoxon signed-rank and require median `g≥.15`; test throughput `d'_i=(T_lex-T_comp)+delta(N_i)` with one-sided Wilcoxon and require the delta guard. Set each comparator IUT p-value to the larger component p-value, then set each stratum global p-value to `max(all component and IUT p-values in that stratum)` before Holm.
  - Report medians/IQR, paired differences, percent gain, Hodges–Lehmann, deterministic 5,000-resample paired bootstrap 95% CI, rank-biserial effect, zero count and exact one-sided sign test only when zeros exceed 50%; sign test never replaces Wilcoxon/IUT/Holm.
  - Apply a single sequential Holm correction only to the two stratum global p-values (`p_IUT_medium`, `p_IUT_high`) at 0,05; never adjust the three comparators separately. Set `SUPPORTED` only if both strata pass all three IUTs and both adjusted p-values reject; low, A1/A2, CO2 and secondary metrics stay descriptive. The 300-pair 100→80 plus 300-pair 1000→860 fixture must remain `NOT_SUPPORTED` despite an aggregate relative median near .17 because Wilcoxon on `g-.15` is about .5.
  - Remove legacy `test_statistics_export.py` assertions that aggregate strata, use old result IDs/schema, fill absent components or treat an aggregate relative median as evidence; retain the concrete 600-pair regression, duplicate/missing/hash invalidation and exact 5,000 bootstrap contract.

- [ ] **Step 4: Run statistics and invalid-input checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_statistics_export.py -k "aggregate_relative_median_false_positive or iut_holm_and_invalid_pairing"`

Expected: PASS for valid paired output and explicit invalid status/error for duplicate, missing or mixed-hash input.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/statistics.py experimento-notebook/src/pequiflux_experiment/experiment.py experimento-notebook/src/pequiflux_experiment/audit.py experimento-notebook/tests/test_statistics_export.py
rtk git commit -m "feat(experimento): implement paired H1 IUT and Holm analysis"
```

### Task 9: Separate sensitivity grid and joint robustness decision

**Files:**
- Create: `experimento-notebook/src/pequiflux_experiment/sensitivity.py`
- Modify/Replace: `experimento-notebook/tests/test_experiment_audit.py` with synthetic complete sensitivity rows; remove any full-grid execution.
- Modify: `experimento-notebook/src/pequiflux_experiment/experiment.py` to namespace sensitivity runs separately.

**Interfaces:**
- Consumes: the same frozen dataset/CRN, explicit `FaceValidationReport`, base config and exploratory stress/policy grid.
- Produces: `run_sensitivity(dataset, face_report, grid, ...)`; `summarize_sensitivity`; `ROBUST`/`INVALID_INPUT` result with joint-cell counts and descriptive medians/IQR/bootstrap.

- [ ] **Step 1: Write the failing test (RED).**

```python
def test_joint_sensitivity_robustness_and_invalid_input():
    sensitivity_bundle = synthetic_complete_sensitivity_rows()
    result = summarize_sensitivity(sensitivity_bundle)
    assert result.cell_rule == "same_cell_all_three_comparators"
    assert result.threshold == pytest.approx(.75)
    assert result.h1_input_used is False
    assert result.decision in {"ROBUST", "NON_ROBUST"}
    incomplete = sensitivity_bundle.drop_one_cell()
    assert summarize_sensitivity(incomplete).decision == "INVALID_INPUT"
    assert sensitivity_bundle.full_grid_executed is False
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py::test_joint_sensitivity_robustness_and_invalid_input`

Expected: FAIL because the separated namespace, synthetic-row summarizer and joint rule are absent.

- [ ] **Step 3: Implement exploratory sensitivity.**

  - Run only from the approved frozen dataset and explicit face report with a separate manifest/schema and no writes to confirmatory rows. In high intensity multiply only document-block, base-failure and rain Bernoulli rates by 2,0 capped at 1,0; keep forced events/durations unchanged.
  - Cross `H0 ∈ {4,6,8}`, buffer `∈ {8,12,16}`, threshold multiplier `∈ {0,75;1,00;1,25}`, intensity `{base,high}` for lexicographic and the three primary comparators. Add deterministic `myopic_predicted_delay`, `window_without_stability`, and `batch_by_cargo` only to descriptive exploration.
  - For every complete cell, require median p95 gain `>0` and throughput within delta against all three comparators; count the cell once. Publish `ROBUST` iff joint fraction ≥75%; expose per-comparator fractions only as diagnostics. Any missing package/cell is `INVALID_INPUT`, never `NON_ROBUST`, and no p-values/Holm feed H1. Permanent tests summarize synthetic complete rows only; they do not run the stress grid or DES.

- [ ] **Step 4: Run sensitivity checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py::test_joint_sensitivity_robustness_and_invalid_input`

Expected: PASS for joint-cell counting, no H1 input, and incomplete-cell invalidation.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/sensitivity.py experimento-notebook/src/pequiflux_experiment/experiment.py experimento-notebook/tests/test_experiment_audit.py
rtk git commit -m "feat(experimento): isolate sensitivity and joint robustness"
```

### Task 10: Audited transactional exports

**Files:**
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/export.py`
- Modify/Replace: `experimento-notebook/tests/test_statistics_export.py` (remove legacy export paths/schema assertions)
- Modify: `experimento-notebook/src/pequiflux_experiment/manifest.py`, `statistics.py`, `audit.py` and `sensitivity.py` to expose signed source hashes and audit status.

**Interfaces:**
- Consumes: only closed, independently audited run bundles and persisted metric/statistical frames.
- Produces: `export_analysis(bundle, results_root)` and `export_audit_table(bundle, results_root)` writing the exact audited artifact set transactionally. A sensitivity bundle writes sensitivity PDFs only in its own namespace; a confirmatory bundle never receives them.

- [ ] **Step 1: Write the failing test (RED).**

```python
def test_exports_require_audit_and_refuse_overwrite(tmp_path, audited_bundle):
    export_analysis(audited_bundle, tmp_path)
    assert (tmp_path / "raw" / "experiment_runs.parquet").exists()
    assert (tmp_path / "tables" / "table_h1.csv").exists()
    expected = {
        "raw/experiment_runs.parquet", "raw/decision_logs.jsonl", "processed/summary.parquet",
        "tables/table_h1.csv", "tables/table_throughput.csv", "tables/table_metrics.csv",
        "tables/table_audit.csv", "tables/table_a2.csv", "figures/p95_by_policy.pdf",
        "figures/paired_improvement.pdf", "figures/throughput_waiting_tradeoff.pdf",
    }
    assert expected <= {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ExportContractError, match="already exists"):
        export_analysis(audited_bundle, tmp_path)
    with pytest.raises(ExportContractError, match="audited"):
        export_analysis(audited_bundle.with_audit(False), tmp_path / "unaudited")
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_statistics_export.py::test_exports_require_audit_and_refuse_overwrite`

Expected: FAIL because no transactional exporter or audit gate exists.

- [ ] **Step 3: Implement export boundaries.**

  - Require complete confirmatory cardinality, audit pass, unique source/config/dataset hashes, finite metrics and `pyarrow`; refuse validation/pilot/sensitivity-only bundles for H1 tables.
  - Stage exactly `raw/experiment_runs.parquet`, `raw/decision_logs.jsonl`, `processed/summary.parquet`, `tables/table_h1.csv`, `tables/table_throughput.csv`, `tables/table_metrics.csv`, `tables/table_audit.csv`, `tables/table_a2.csv`, `figures/p95_by_policy.pdf`, `figures/paired_improvement.pdf`, and `figures/throughput_waiting_tradeoff.pdf` for an audited confirmatory bundle. A sensitivity bundle may additionally write only `figures/sensitivity_h0.pdf`, `figures/sensitivity_buffer.pdf`, `figures/sensitivity_threshold.pdf`, `figures/sensitivity_intensity.pdf`, and `figures/sensitivity_co2.pdf` inside its sensitivity namespace; no vague or cross-namespace figure family is allowed. Validate schemas/cardinality/hash before atomic directory rename.
  - Refuse any existing destination, missing source metric or pending/invalid required audit, and preserve original exceptions. `table_h1.csv` includes p95/throughput components, IUT, raw/Holm p-values, estimates and decision; `table_metrics.csv` includes all eight families; `table_audit.csv` exposes A1/A2/replay/checksum/pending state. Remove old `results` aliases, legacy CSV names and tests that permit unaudited or overwriting publication.

- [ ] **Step 4: Run export checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_statistics_export.py -k "exports_require_audit_and_refuse_overwrite"`

Expected: PASS for audited publication, exact output set and no-overwrite/unaudited rejection.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/export.py experimento-notebook/src/pequiflux_experiment/manifest.py experimento-notebook/src/pequiflux_experiment/statistics.py experimento-notebook/src/pequiflux_experiment/audit.py experimento-notebook/src/pequiflux_experiment/sensitivity.py experimento-notebook/tests/test_statistics_export.py
rtk git commit -m "feat(experimento): publish audited analysis transactionally"
```

### Task 11: Single literate notebook, explicit actions and subproject handoff

**Files:**
- Modify/Replace: `experimento-notebook/TCC_experimentos.ipynb`
- Modify/Replace: `experimento-notebook/README.md`
- Modify/Replace: `experimento-notebook/tests/test_notebook.py` (remove legacy `RUN_PROFILE`/latest/env routing)
- Modify: `experimento-notebook/src/pequiflux_experiment/__init__.py` only to expose notebook entry points without side effects.

**Interfaces:**
- Consumes: all task modules, explicit paths/IDs and persisted validation/run bundles.
- Produces: six literal actions (`validation`, `generate-synthetic`, `pilot`, `execute-confirmatory`, `audit-analyze`, `sensitivity`), default validation execution, visible/persisted outputs, and reproducible README commands.

- [ ] **Step 1: Write the failing test (RED).**

```python
def test_notebook_actions_and_validation_run(tmp_path):
    nb = nbformat.read(ROOT / "TCC_experimentos.ipynb", as_version=4)
    source = "\\n".join(cell.source for cell in nb.cells if cell.cell_type == "code")
    assert 'ACTION = "validation"' in source
    assert "ALLOWED_ACTIONS = (\"validation\", \"generate-synthetic\", \"pilot\", \"execute-confirmatory\", \"audit-analyze\", \"sensitivity\")" in source
    assert set(re.findall(r'ALLOWED_ACTIONS\\s*=\\s*\\(([^\\)]*)\\)', source))
    assert set(re.findall(r'\"([^\"]+)\"', source.split("ALLOWED_ACTIONS", 1)[1].split(")", 1)[0])) == {
        "validation", "generate-synthetic", "pilot", "execute-confirmatory", "audit-analyze", "sensitivity"
    }
    assert "os.environ" not in source and "latest" not in source.lower()
    assert "RUN_PROFILE" not in source and "load-confirmatory" not in source
    execute_notebook(nb, cwd=ROOT, tmp_path=tmp_path)
    manifest = next(tmp_path.glob("runs/validation__*/manifest.json"))
    assert json.loads(manifest.read_text())["non_confirmatory"] is True
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_notebook.py::test_notebook_actions_and_validation_run`

Expected: FAIL because the notebook still contains implicit/legacy routing or does not persist validation output.

- [ ] **Step 3: Build the six-action literate notebook and README.**

  - Put the literal, visible first executable cell `ACTION = "validation"` and `ALLOWED_ACTIONS = ("validation", "generate-synthetic", "pilot", "execute-confirmatory", "audit-analyze", "sensitivity")`; validate only that tuple and raise `InvalidAction` for empty/unknown/discovered values. Require explicit `DATASET_RUN_ID`/`RUN_ID` cells where an existing artifact is needed; never read environment variables, prior cell state, latest pointers or hidden defaults.
  - Keep cells in the mandated order: identification/ACTION; manifest/inventory; config; protocol; dataset state; action execution; persisted artifact readback; audit/analysis; export; limits. The default route writes/displays/reads the reduced persisted validation dataset, eight A1 contexts and metrics, with `non_confirmatory=true` and face status/cause.
  - Route `generate-synthetic` through the approved face gate and full materialization; route `pilot` through approved face + existing frozen dataset without a capacity gate; route `execute-confirmatory` through approved face + existing frozen dataset + the single capacity gate; route `sensitivity` through approved face + existing frozen dataset in its own namespace without a capacity gate. Let `validation` persist its reduced package with APPROVED or PENDING face and let `audit-analyze` inspect an explicit run diagnostically. Use existing module APIs only; do not import `random`/`numpy.random` in notebook cells, install dependencies, call `Run All` into a full campaign, or duplicate simulator code.
  - Document exact setup, six actions, namespace rules, no-fallback/no-retry behavior, approved receipt procedure, capacity block, baseline and one-shot test/notebook commands in `README.md`; state that H1 requires audited complete confirmation and A2 human pending blocks global acceptance only. Remove legacy `RUN_PROFILE`, `load-confirmatory`, environment/latest discovery, aliases and old result-schema examples from both notebook and README.

- [ ] **Step 4: Run notebook validation and static checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_notebook.py::test_notebook_actions_and_validation_run`

Expected: PASS with `ACTION="validation"` executing top-to-bottom via `nbclient`, displaying and persisting only the reduced non-confirmatory package.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/TCC_experimentos.ipynb experimento-notebook/README.md experimento-notebook/tests/test_notebook.py experimento-notebook/src/pequiflux_experiment/__init__.py
rtk git commit -m "feat(experimento): replace legacy pipeline with literate notebook"
```

## Self-review against the spec

- Coverage check: Tasks 1–3 cover config/face, canonical planning/freeze and `AbortedStaging` resample; Tasks 4–7 cover event semantics, validation/A1, capacity, runner, replay and A2; Tasks 8–10 cover H1, sensitivity and audited exports; Task 11 covers the sole notebook interface.
- Contract/API scan: `DayResult` has no metric field or fabricated value; reduced validation is only `build_validation_dataset`; production generation has no reduced flag; capacity uses `from_dataset`, not a config-only workload; `compute_cohen_kappa` receives explicit label sets.
- Test-cost scan: no pytest test materializes production trucks/services or executes the pilot/confirmatory DES counts; pure plans, the three-instance validation package, synthetic sensitivity rows and injected worker/provider gates are the only permanent execution checks.
- Gate scan: validation persists with either `APPROVED` or `PENDING` face status; only principal generation/pilot/confirmatory/sensitivity routes block before namespace, and `audit-analyze` remains diagnostic. Every mutating API receives `face_report` explicitly.
- Legacy scan: old `tiny_scenario`, `run_day(scenario, seed, policy)`, `run_experiment_matrix`, `RUN_PROFILE`, `load-confirmatory`, environment/latest discovery, old IDs/aliases and old result schemas are removed from implementation, notebook, README and the named test files.
- Artifact/statistics scan: FREEZE/hash formulas, eight metrics/A1 contexts, exact event ranks, H1 stratum max-p and two-value Holm, joint 75% sensitivity and exact export filenames are specified without alternate paths.

## Final Verification and Handoff

Run the following exactly once with CWD `C:\\p\\PequiFlux\\TCC` after all eleven tasks; do not retry a failing command. The canonical pytest run includes the `nbclient` top-to-bottom validation test exactly once; do not execute a separate notebook command or any campaign.

```powershell
rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q
rtk experimento-notebook\\.venv\\Scripts\\python.exe -m compileall -q experimento-notebook\\src experimento-notebook\\tests
```

After those two commands, inspect the notebook test's receipt/output path from that run and record `FACE_VALIDATION`/`non_confirmatory` values. Run a live capacity preflight only if a real frozen dataset exists, using `ConfirmatoryWorkload.from_dataset(frozen_dataset, config)` and `inspect_capacity(workload, config.capacity, run_root, providers=...)`; record the actual `PASS` or `BLOCKED` decision without requiring either outcome. If no real frozen dataset exists, record `NOT_RUN_NO_FROZEN_DATASET` and rely on the deterministic injected low-disk/process block plus the existing read-only capacity audit. Never fabricate a pass/block and never launch full generation or a campaign during final verification. Preserve any failed staging/run namespace and its causal log; never clean the dirty root or claim confirmatory evidence from validation, pilot or sensitivity. `graphify` is N/A when `graphify-out/` is absent.
