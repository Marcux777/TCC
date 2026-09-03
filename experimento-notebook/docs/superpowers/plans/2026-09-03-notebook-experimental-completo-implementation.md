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
- Persist the sixth canonical payload `event_latents.jsonl` before realization. Its exact envelope is `instance_id, scenario_index, scenario_id, seed, generation_attempt, latent_id, latent_kind, event_origin, entity_id, payload`, ordered by `(instance_id, latent_kind_order, entity_id, latent_id)`, with closed payload variants for every truck document draw/release-duration candidate, eligible base-failure draw/resource/start/duration candidate, priority-shift draw/candidate list, every eligible immutable 30-minute rain slot (`block_index=0..23`, `start_minute=30*block_index`, `duration_min=30`, `end_minute=start_minute+30`) and the separate immutable critical forced-failure candidate. No old five-payload dataset, missing/corrupt ledger, extra key, or divergent hash is loadable.
- Sensitivity high is derived from the same frozen instance/ledger with no RNG, regeneration, filesystem lookup or config mutation. `base` at multiplier `1.00` must reproduce persisted status/disruptions byte-for-byte, including persisted coalesced rain rows; `high` uses only `u < min(1,2p)` for document/base-failure/rain candidates, appends document/base-failure candidates, and re-coalesces active rain blocks canonically (rain interval rows may change while latent blocks/timing remain fixed). It never changes forced events or realized durations. `intensity` is closed to `{base, high}`; `low`, unknown labels and any service-duration multiplier fail before namespace creation.
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
generate_synthetic_dataset ──> staging/payloads + event_latents ──> FREEZE.json + six hashes
        │                                      │
        └── validation selection               └── load_frozen_dataset
                                                   │
                                                   ▼
FrozenInstance + EventLatentLedger + ExecutionControls ──> run_day(instance, policy, controls, event_latents) ──> complete event JSONL + snapshots/hashes
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
| `domain.py`/`events.py` | `FrozenInstance`, `Truck`, `Resource`, `Event`, immutable `EventLatentLedger`, `FrozenValidationDataset`; `write_jsonl`, `read_jsonl` | Serializable immutable payloads/latent rows and deterministic event order. |
| `manifest.py` | `canonical_bytes`, `canonical_file_hash`, `create_run_directory`, `build_manifest`, `write_manifest` | Canonical JSON/checksum bytes, collision refusal and dirty-root/environment receipts; never mutates Git. |
| `dataset.py` | `generate_synthetic_dataset(config, face_report, dataset_root, ...)`, `resample_synthetic_dataset(config, face_report, source_staging_path, source_staging_root_hash, exact_rejected_ids, destination_root, ...)`, `load_aborted_staging`, `load_freeze_receipt`, `read_instance_header`, `load_event_latents`, `plan_synthetic_dataset`, `validate_generation_headers`, `canonical_payload_schemas`, `canonical_event_latent_schema`, `load_frozen_dataset`, `validate_frozen_dataset`, `freeze_dataset`, `select_pilot_configurations` | Complete 3,600-instance freeze with six payloads including `event_latents.jsonl`, lightweight persisted freeze/header receipts (no `FrozenInstance` construction), pure non-publishing header receipt, exact latent/disruption schemas, explicit one-attempt resample with latent-hash provenance and canonical hash chain; face report is always explicit. |
| `validation.py` | `build_validation_dataset(config, validation_config, run_root, face_report)`, `run_validation_checks`, `run_a1_adversarial_suite(fixtures_path)` | Persisted indices `[20,12,24]`, seed `101`, five policies, 15 policy-days and eight A1 contexts from disk. |
| `dispatch.py`/`policies.py` | `DispatchContext`, `Candidate`, `make_policy`, `filter_admissible`, `select_candidate` | Shared hard constraints and five policy-only ranking rules. |
| `emulator.py` | `ExecutionControls`, `derive_controlled_instance(instance, event_latents, controls)`, `run_day(instance: FrozenInstance, policy: DispatchPolicy | str, controls: ExecutionControls, event_latents: EventLatentLedger) -> DayResult` | Terminant DES with required immutable baseline/sensitivity controls, pure frozen-only derivation, no sampling/lazy defaults and complete event/hash output. |
| `metrics.py` | `compute_policy_day_metrics(persisted_day) -> MetricRow` | Sole producer of eight PDF metric families plus exploratory CO2 from persisted events; no fabricated values. |
| `capacity.py` | `inspect_capacity(workload, requirements, run_root) -> CapacityReceipt`; `require_capacity(receipt)` | Single TTL/hash/process/disk/RAM gate before confirmatory namespace; OS probes stay private and are monkeypatched only in tests. |
| `profiles.py` | `ConfirmatoryWorkload.from_dataset(frozen_dataset, config)`; `plan_policy_days` | Actual dataset/config/workload hashes and pure cardinality plans. |
| `experiment.py` | `run_policy_days(dataset, policies, phase, run_root, face_report, controls, event_latents, *, capacity_receipt=None, worker=run_day) -> RunBundle`; `load_run_bundle` | Pilot/confirmatory atomic rows/logs; production refuses partial grids and never infers/mutates controls or the ledger. Both optional arguments are keyword-only and `worker` defaults only to `run_day`. |
| `digital_model.py`/`replay.py` | `DigitalModel.apply`, `snapshot`, `replay_events`, `replay_run` | Independent projection and deterministic replay equality. |
| `audit.py`/`a2.py` | `audit_run`, `build_a2_sample`, `apply_rubric`, `compute_cohen_kappa`, `persist_a2_review` | A1 zero-violation report, A2 workflow/sample/rubric and `PENDING` semantics. |
| `statistics.py` | `paired_dataframe`, `evaluate_h1(confirmatory_bundle, config) -> H1Report` | Medium/high IUT, throughput margin, bootstrap/HL/rank-biserial and Holm. |
| `sensitivity.py` | `run_sensitivity(dataset, event_latents, face_report, grid, ...)`, `summarize_sensitivity` | Same-frozen-CRN base/high rates, 54-cell stress grid, ledger/control/source hashes and joint 75% `ROBUST` decision outside H1; face report is explicit and no RNG/regeneration is allowed. |
| `export.py` | `export_analysis`, `export_audit_table` | Audited raw/processed/tables/figures, transactional no-overwrite publication. |

## Exact Invariants and Check Mapping

| Invariant or material risk | Required minimum check | Plan task |
| --- | --- | --- |
| 72 configurations, exact order/IDs/rho, 50 seeds, policy set and stable hash | `test_config_manifest.py::test_config_contract_and_hash` | 1 |
| Face receipt/template version, real PDF/rubric hashes, approved gate or pending cause | `test_config_manifest.py::test_face_validation_receipt_gate` | 1 |
| Reduced validation is `[20,12,24] × [101] × 5`, persisted and non-confirmatory | `test_dispatch_emulator.py::test_validation_dataset_persisted_and_non_confirmatory` | 5 |
| Pure 72/3,600/18,000 generation plan/header receipt, exact six-payload schemas and strict loader rejection of test/legacy artifacts | `test_config_manifest.py::test_synthetic_plan_contract`, `::test_generation_headers_receipt_is_non_publishing`, `::test_canonical_payload_schemas_are_exact`, `::test_strict_loader_rejects_header_only_artifact` and Task 2.5 latent tests | 2 + 2.5 |
| Validation package persists three selected instances for approved and pending face reports | `test_dispatch_emulator.py::test_validation_dataset_persisted_and_non_confirmatory` | 5 |
| Validation action ignores confirmatory face/capacity gates while pilot/confirmatory enforce them before namespace | `test_experiment_audit.py::test_validation_runner_always_persists_with_pending_face` plus `::test_approved_face_capacity_block_makes_zero_worker_calls` | 6 |
| Explicit fail-fast resample preserves canonical accepted records, increments attempt once per explicit action and aborts on the next natural rejection | `test_config_manifest.py::test_fail_fast_persisted_resample_sequence` | 3 |
| `run_day` requires a complete frozen instance and has no hidden generation | `test_dispatch_emulator.py::test_run_day_requires_frozen_instance` | 4 |
| CRN inputs/latents are identical across five policies and sensitivity base/high uses no RNG | `test_dispatch_emulator.py::test_crn_is_policy_independent` plus `test_event_latent_roundtrip_and_high_projection` | 2.5 + 4 + 9 |
| Eight A1 contexts fail closed and are consumed from disk | `test_dispatch_emulator.py::test_a1_adversarial_suite_fail_closed` | 5 |
| Digital projection/replay is independent and hash-equal | `test_digital_model_replay.py::test_replay_matches_independent_projection` | 7 |
| Policy-day key uniqueness and pilot/confirmatory cardinality plans | `test_experiment_audit.py::test_policy_day_plan_cardinality_without_des` | 6 |
| Five A2 fields, per-scenario sample, rubric, single/two-reviewer kappa and pending state | `test_digital_model_replay.py::test_a2_sample_rubric_and_kappa_contract` | 7 |
| H1 IUT, throughput guard, paired hashes and Holm only for medium/high | `test_statistics_export.py::test_iut_holm_and_invalid_pairing` | 8 |
| Joint 54-cell sensitivity pairing/control/ledger hashes, explicit `median(d')>0` and incomplete-input invalidation | `test_experiment_audit.py::test_joint_sensitivity_robustness_and_invalid_input` | 9 |
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
- Create: `experimento-notebook/tests/conftest.py` with only the `approved_face` fixture; it imports only Task 1 modules and standard-library helpers.
- Modify: `experimento-notebook/pyproject.toml` and `experimento-notebook/requirements.lock` to declare direct `psutil` and retain the existing scientific dependencies.

**Interfaces:**
- Consumes: the frozen protocol values in the spec and the bytes of `main.pdf`/rubric.
- Produces: immutable `ExperimentConfig`/`ScenarioConfig`/`CapacityRequirements`; `factorial_scenarios()`; `load_config(path)`; `validate_confirmatory_config(config)`; `config_hash(config)`; `FaceValidationReport`; `validate_face_validation_receipt(path, config, pdf_path)`; `materialize_face_validation_template(path)`.

- [ ] **Step 1: Write the failing test (RED).**

```python
from datetime import datetime, timezone
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
  - Create `tests/conftest.py` with the single `approved_face(tmp_path)` fixture below. Its imports are limited to `hashlib`, `json`, `Path`, `pytest`, `config` and `face_validation`; do not import `dataset`, `domain`, `validation`, emulator, capacity, statistics, sensitivity or notebook modules in Task 1.

    ```python
    # experimento-notebook/tests/conftest.py (Task 1)
    import hashlib
    import json
    from pathlib import Path
    import pytest

    from pequiflux_experiment.config import config_hash, load_config
    from pequiflux_experiment.face_validation import validate_face_validation_receipt

    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    @pytest.fixture
    def approved_face(tmp_path):
        config = load_config(PROJECT_ROOT / "config" / "confirmatory.json")
        pdf = PROJECT_ROOT.parent / "main.pdf"
        rubric = PROJECT_ROOT / "inputs" / "face_validation_rubric.v1.json"
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        receipt = {
            "status": "APPROVED", "protocol_version": config.protocol_version,
            "config_hash": config_hash(config), "source_document": "main.pdf",
            "source_sha256": digest(pdf), "round_id": "task1-fixture",
            "completed_at": "2026-09-03T12:00:00+00:00", "blind": True,
            "reviewer_ids": [
                {"id": "reviewer-a", "independent": True},
                {"id": "reviewer-b", "independent": True},
            ],
            "rubric_path": "inputs/face_validation_rubric.v1.json",
            "rubric_version": "face_validation_rubric.v1", "rubric_sha256": digest(rubric),
            "discrepancies": [], "final_decision": "APPROVED",
        }
        path = tmp_path / "approved-face.json"
        path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n")
        report = validate_face_validation_receipt(path, config, pdf)
        assert report.status == "APPROVED"
        return report
    ```
  - Remove legacy `RUN_PROFILE`, `load-confirmatory`, environment/latest discovery, old aliases and old manifest schema assertions from `test_config_manifest.py`; replace them with canonical config, `CapacityRequirements` and explicit face-report tests.

- [ ] **Step 4: Run the focused GREEN and face checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py`

Expected: PASS for stable 72-scenario enumeration and `FACE_VALIDATION=PENDING` for the unapproved receipt.

- [ ] **Step 5: Commit the task files (executor command; do not run during plan authoring).**

```bash
rtk git add experimento-notebook/config/confirmatory.json experimento-notebook/config/validation.json experimento-notebook/inputs/face_validation_rubric.v1.json experimento-notebook/inputs/face_validation_receipt.template.v1.json experimento-notebook/inputs/face_validation_receipt.json experimento-notebook/src/pequiflux_experiment/config.py experimento-notebook/src/pequiflux_experiment/face_validation.py experimento-notebook/tests/test_config_manifest.py experimento-notebook/tests/conftest.py experimento-notebook/pyproject.toml experimento-notebook/requirements.lock
rtk git commit -m "feat(experimento): freeze config and face validation gate"
```

### Task 2: Frozen domain, deterministic generator and complete hash chain

**Files:**
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/domain.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/dataset.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/manifest.py`
- Modify/Replace: `experimento-notebook/tests/test_config_manifest.py` (replace legacy tiny/full-generation assumptions with pure planning/header-receipt checks and a tiny hand-built strict-loader rejection)
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/config.py` to expose canonical bytes and CRN helpers.

**Interfaces:**
- Consumes: `ExperimentConfig`, an explicit `FaceValidationReport`, and the pure `DatasetPlan`.
- Produces: immutable `Truck`, `Resource`, `FrozenInstance`, `FrozenDataset`; `plan_synthetic_dataset(config) -> DatasetPlan` with lightweight `ordered_instance_headers`; pure `validate_generation_headers(headers, expected_plan) -> GenerationPlanReceipt` (72 scenarios/3,600 instances/18,000 policy-days and canonical order, with no I/O, `FrozenInstance` construction or `FREEZE.json`); the five-payload `canonical_payload_schemas()` **transitional internal baseline**; and the internal serializer/checksum seams that Task 2.5 upgrades. This commit is `TRANSITIONAL INTERNAL ONLY`: it is not publishable, exposes no notebook action and is never eligible to create or validate a public `FREEZE.json`. The public `generate_synthetic_dataset`, `load_frozen_dataset` and `freeze_dataset` contract is opened only after Task 2.5's atomic six-payload migration, which adds `event_latents.jsonl` and the latent-loader contract before any resample or DES work. The public generator has no rejection injector or reduced/fallback flag, and the reduced validation integration is deliberately introduced in Task 5 after this planning contract.

- [ ] **Step 1: Write the failing test (RED).**

```python
import hashlib
import json
from pathlib import Path
import pytest

from pequiflux_experiment.config import load_config
from pequiflux_experiment.dataset import (
    DatasetContractError,
    GenerationPlanReceipt,
    canonical_payload_schemas,
    load_frozen_dataset,
    plan_synthetic_dataset,
    validate_generation_headers,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "config" / "confirmatory.json")

def test_synthetic_plan_contract():
    plan = plan_synthetic_dataset(CONFIG)
    assert plan.scenario_indices == tuple(range(72))
    assert plan.instance_count == 3_600
    assert plan.policy_day_count == 18_000
    assert plan.instance_ids[0] == "s00-seed101"
    assert plan.instance_ids[-1] == "s71-seed150"

def test_generation_headers_receipt_is_non_publishing():
    plan = plan_synthetic_dataset(CONFIG)
    receipt = validate_generation_headers(plan.ordered_instance_headers, expected_plan=plan)
    assert isinstance(receipt, GenerationPlanReceipt)
    assert (receipt.scenario_count, receipt.instance_count, receipt.policy_day_count) == (72, 3_600, 18_000)
    assert receipt.ordered_instance_ids == plan.instance_ids

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

def test_strict_loader_rejects_header_only_artifact(tmp_path, approved_face):
    artifact = tmp_path / "header-only"
    artifact.mkdir()
    for name in ("scenario_index.parquet", "trucks.parquet", "service_times.parquet"):
        (artifact / name).write_bytes(b"header-only test artifact")
    (artifact / "disruptions.jsonl").write_text("", encoding="utf-8")
    (artifact / "rejection_log.jsonl").write_text("", encoding="utf-8")
    (artifact / "manifest.json").write_text(json.dumps({"instance_count": 3_600}), encoding="utf-8")
    with pytest.raises(DatasetContractError, match="FREEZE|header-only|schema"):
        load_frozen_dataset(
            artifact, approved_face,
            expected_dataset_root_hash=hashlib.sha256(b"header-only-test-pin").hexdigest(),
        )
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py -k "synthetic_plan or generation_headers or canonical_payload_schemas or strict_loader"`

Expected: FAIL because the pure plan/header receipt, exact schema contract and strict loader are absent; this check must not call `generate_synthetic_dataset` or create/load 3,600 `FrozenInstance` objects.

- [ ] **Step 3: Implement generation and freeze.**

  - Make `plan_synthetic_dataset(config)` pure and cheap: return 72 ordered scenario headers, exact 3,600 ordered instance IDs and 18,000 policy-day keys/cardinalities without writing, sampling or constructing `FrozenInstance`. `validate_generation_headers(headers, expected_plan)` compares only lightweight header fields and returns `GenerationPlanReceipt`; it never writes a payload, exposes a destination, publishes `FREEZE.json` or is accepted by the strict production loader. Task 5 owns the only reduced three-instance materializer.
  - Define the five-payload `canonical_payload_schemas()` baseline with no optional/default columns and reject any missing, extra, nullable or type-divergent field. The exact Parquet columns are: `scenario_index.parquet = (scenario_index, scenario_id, N, hopper_count, scale_count, regime, rho, stratum, protocol_version, config_hash, generator_version)`; `trucks.parquet = (instance_id, scenario_index, scenario_id, seed, truck_id, arrival_minute, cargo_type, priority, document_status, stage, eligible_resources, truck_record_hash)`; `service_times.parquet = (instance_id, scenario_index, scenario_id, seed, truck_id, operation, duration_min, source_a, source_mode, source_b, draw_key, crn_version, service_record_hash)`. JSONL schemas at this stage are exact too: `disruptions.jsonl` rows carry `instance_id, scenario_index, scenario_id, seed, time, event_rank, resource_id, truck_id, sequence, event_type, cause, operation, duration_min, return_time, payload_hash`; `rejection_log.jsonl` rows carry `dataset_id, candidate_ordinal, scenario_index, instance_id, seed, generation_attempt, reason_code, validator, observed, expected, candidate_hash, automatic_resample_status, next_action, timestamp`. This schema is an **internal, non-publishable transition check only**; no Task 2 test or implementation may claim a public freeze or notebook action. Task 2.5 adds `latent_id`, `event_origin` and the sixth `event_latents.jsonl` payload atomically before Task 3, and only that six-payload contract is public.
  - Materialize exactly 72 scenario rows in canonical fatorial order (`N` outer, then `hopper_count`, `scale_count`, `regime`), with consecutive `scenario_index=0..71` and exact `scenario_id`; emit exactly `N` truck rows per instance, unique/injective truck IDs, and exactly four service-operation rows per truck with no missing/duplicate operation. Validate disruptions against the canonical event ordering/schema and rejection-log cardinality against accepted/rejected/next-ordinal partitions; an empty rejection log is still a valid zero-row file with the declared schema.
  - On load, reconstruct `instance_id -> (scenario_index, seed)` and verify every scenario/truck/service/disruption/rejection row carries the matching instance/scenario/seed. Recompute each service `draw_key` from the exact CRN tuple `(crn_version, scenario_index, seed, generation_attempt, entity_id, operation_or_event)` and canonical hash bytes; reject any late/default draw, mismatch, duplicate, missing row, non-finite value or changed order before returning `FrozenInstance`.
  - Write all five baseline payloads plus an internal manifest/checksum receipt under a sibling temporary staging directory, never the requested destination. Strictly validate schemas, cardinalities, hashes and the complete 3,600-instance plan in staging, then retain it only as a `TRANSITIONAL_INTERNAL` artifact; do **not** atomically publish a destination or write an eligible `FREEZE.json` in Task 2. Delete scratch staging only after a successful internal check; retain causal rejection/validation staging, `STAGING.json` and `rejection_log` with the original exception chain when validation fails. Task 2.5 owns the later six-payload migration and the first public freeze.
  - Hash only the five baseline payload files for this internal receipt; `checksums.sha256` is ordered `relative_name<TAB>sha256_hex`, `manifest_hash=sha256(canonical manifest bytes)`, `checksums_hash=sha256(canonical checksum bytes)`, and `dataset_root_hash=sha256(manifest_hash+":"+checksums_hash)`. Exclude `manifest.json`, `FREEZE.json`, and `checksums.sha256` from their own checksum list. The receipt is labelled `TRANSITIONAL_INTERNAL`, `publishable=false`, `notebook_action=null`, and cannot be passed to a public loader; only Task 2.5 may upgrade it to the six-payload manifest/checksum/FREEZE contract. Require canonical bytes/order in the internal receipt as a schema check, but never claim a public freeze or a final dataset hash from it.
  - Keep the public `load_frozen_dataset`/`freeze_dataset` entry points closed until Task 2.5: Task 2 may expose only the internal schema/plan checks and must reject `GenerationPlanReceipt`, header-only/test artifacts and any attempt to publish a five-payload root. After the six-payload migration, the strict production loader rejects missing/extra/default fields, absent/corrupt/altered `FREEZE.json`, collisions and changed hashes before returning `FrozenDataset`; the public generator has no rejection injector, reduced selector or fallback. Keep the private deterministic rejection seam introduced in Task 3 separate from this complete-generation contract; a `PENDING` face report fails before creating a namespace.
  - Remove obsolete `tiny_scenario`, old IDs/aliases, old results schema and legacy `test_config_manifest.py` expectations; retain only pure plan/header receipt and tiny strict-loader checks here. Do not move the real three-instance materializer into Task 2; it is implemented and tested in Task 5.

- [ ] **Step 4: Run the plan/schema/loader checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py -k "synthetic_plan or generation_headers or canonical_payload_schemas or strict_loader"`

Expected: PASS for the pure 72/3,600/18,000 plan and ordered `GenerationPlanReceipt`, exact Parquet/JSONL schema declarations and tiny strict-loader rejection; no production payload generation, `FREEZE.json` publication or 3,600-instance load occurs in pytest.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/domain.py experimento-notebook/src/pequiflux_experiment/dataset.py experimento-notebook/src/pequiflux_experiment/manifest.py experimento-notebook/src/pequiflux_experiment/config.py experimento-notebook/tests/test_config_manifest.py
rtk git commit -m "chore(experimento): stage transitional payload schema (internal)"
```

This commit is deliberately `TRANSITIONAL_INTERNAL`: it is not publishable, is not wired to any notebook action, and cannot create or validate a public `FREEZE.json`. The first public freeze and all final hashes exist only after Task 2.5's six-payload migration.

### Task 2.5: Retrofit canonical event-latent ledger for same-CRN sensitivity

**Files:**
- Modify `experimento-notebook/src/pequiflux_experiment/dataset.py`, `domain.py` and `manifest.py` to upgrade the transitional Task 2 five-payload receipt to six payloads and expose the immutable ledger.
- Modify `experimento-notebook/tests/test_config_manifest.py` with bounded roundtrip/legacy/no-RNG checks; Task 3 extends its resample assertions with latent and source-chain hashes.
- Modify `experimento-notebook/tests/conftest.py` only for Task 2.5's bounded ledger fixtures/helpers; it must retain Task 1's sole `approved_face` fixture and import no future-task modules.

**Interfaces:**
- Produces `canonical_event_latent_schema()`, `load_event_latents(path) -> EventLatentLedger`, and an immutable `EventLatentLedger` keyed by `(instance_id, latent_id)`. The exact envelope is `(instance_id, scenario_index, scenario_id, seed, generation_attempt, latent_id, latent_kind, event_origin, entity_id, payload)` and the only payload variants are `document`, `base_failure`, `priority_shift`, `rain_block` and `forced_failure` with the fields defined in the design spec.
- Exact latent identity/order is fixed: `document/<truck_id>` has one row for every truck (`entity_id=truck_id`); `base_failure/<regime>` has one row for every eligible non-critical instance (`entity_id=regime`); `priority_shift/<regime>` has one row for `priority_shift`; `rain_block/<block_index>` has exactly 24 immutable 30-minute slots for each `m>=2` instance (`entity_id=f"rain-{block_index:02d}"`, `start_minute=30*block_index`, `duration_min=30`, `end_minute=start_minute+30`); and `forced_failure/<resource_id>` has one row for `critical_failure` (`event_origin='forced'`). Forced rows have no incidence `u`, but carry `start_draw_key` and `duration_draw_key` for their frozen start/duration candidates. Rows sort by `(instance_id, latent_kind_order, entity_id, latent_id)`, where kind order is `document, base_failure, priority_shift, rain_block, forced_failure`; `latent_id` is the canonical concatenation `f"{instance_id}:{latent_kind}:{entity_id}"` and is unique.
- Extends `disruptions.jsonl` with exact `latent_id`/`event_origin` back-references and upgrades every freeze/staging namespace to the ordered six-payload inventory. The exact resample provenance content/reference includes `source_staging_relpath` and `source_staging_receipt_sha256`; source-aware loaders recursively validate the retained sibling chain, as specified below. Old five-payload roots, absent/corrupt/noncanonical ledgers, hash mismatches and stale maps fail before an instance or namespace is usable.
- The retrofit does not alter the 72×50 factorial, generation order or rejection semantics. It materializes all candidate draws before realization, keeps the forced critical-failure row separate/immutable, and exposes `event_latents_sha256` to `ExecutionControls`.

Task 1 creates `tests/conftest.py` with only `approved_face`. Before this task's RED check, extend it only with the bounded ledger fixtures/helpers needed here (`bounded_frozen_fixture`, `legacy_five_payload_root`, immutable `BASE_CONTROLS`/`HIGH_CONTROLS`, `forced_disruptions`, `non_rain_disruptions`, `rain_latent_ids`, `tamper_event_latents` and canonical serializers). Imports may use only standard-library modules, `pytest`, and Task 1/Task 2/Task 2.5 modules (`config`, `face_validation`, `manifest`, `domain`, `dataset`); do not import `validation`, emulator, capacity, experiment, replay, statistics, sensitivity, metrics, A2 or notebook modules. Later tasks define their own fixtures in their own test modules; no shared fixture is promised beyond `approved_face` and this Task 2.5 extension.

The Task 2.5 test module receives the bounded fixtures by pytest injection and has no relative `.conftest` imports. Its RED contracts are:

- `test_event_latent_schema_and_legacy_loader_fail_fast` compares `canonical_event_latent_schema()` with the exact envelope and five closed payload variants in the design. The `legacy_five_payload_root` fixture is a coherent historical v1 root: it contains valid five-payload bytes, a matching five-entry manifest/checksum inventory, recomputed `manifest_hash`, `checksums_hash`, and `dataset_root_hash` in `FREEZE.json`. The test reads that actual detached root hash from `FREEZE.json` and passes it to `load_frozen_dataset`; the v2 loader must fail specifically with `MISSING_EVENT_LATENTS` before serving an instance (never with a zero/fabricated pin or stale-chain mismatch).

- `test_event_latent_roundtrip_and_high_projection` loads the ledger, verifies its persisted SHA, and defines `rain_latent_coverage(instance)` locally in the test module (or imports that explicitly named Task 2.5 helper). It requires base status/disruptions to be byte/hash-equal to the persisted projection; `non_rain_base_ids ⊆ non_rain_high_ids` (high may append approved document/base-failure candidates), and events present in both projections (including forced and priority rows) to be semantically equal in `event_type`, `latent_id`, `event_origin`, `resource_id`, `truck_id`, `cause`, `operation`, `time`, `duration_min` and `return_time`. High uses a fresh canonical contiguous stream with projection-local `sequence` and recomputed row `payload_hash`, so those two fields are not compared byte-for-byte; high rain rows must cover exactly the active immutable block latent IDs under the canonical coalescing algorithm, while distinct `controlled_view_hash`/`event_overlay_hash` attest projection identity.

- `test_event_latent_loader_rejects_tamper` covers missing, corrupt, extra-key and noncanonical ledgers and expects `DatasetContractError` before DES. `test_controlled_derivation_is_frozen_no_rng_regeneration_or_mutation` monkeypatches RNG, regeneration and filesystem seams, derives high once, and proves the source instance bytes are unchanged.
- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py -k "event_latent or legacy_five_payload or controlled_derivation"`

Expected: FAIL because Task 2 still emits only five payloads and no canonical latent/control projection exists.

- [ ] **Step 3: Implement the six-payload ledger retrofit.**

  - Materialize every candidate before status/disruption realization with CRN keys containing `generation_attempt` and never policy. Validate exact envelope/variant keys, identity/order/cardinality, finite `u` in `[0,1)`, candidate ranges and disruption back-references. Document rows carry U plus release-duration candidate for every truck; base-failure rows carry U plus resource/start/duration candidates only in eligible nominal/peak/priority-shift regimes; rain rows carry U plus resource/start/duration for all 24 eligible blocks; forced rows carry no incidence U but do carry `start_draw_key`/`duration_draw_key` with their resource/start/duration/end candidates and remain immutable. For both base and forced failures, reconcile `scheduled_failure_start`, deterministic busy-resource `effective_failure_start` and `recovery_time=effective_failure_start+duration` against the corresponding disruption rows; never resample at DES time.
  - Add `event_latents.jsonl` to initial/staging/resample inventories, manifest/hash/checksum/FREEZE/STAGING chains and roundtrip receipts. `event_latents_sha256` is mandatory. Reject the valid five-payload fixture with `MISSING_EVENT_LATENTS`, and reject missing/corrupt/extra/noncanonical rows or divergent hashes before loading an instance.
  - Persist accepted latent rows byte-identically through resample and complete `accepted_event_latent_hashes`/`prior_accepted_event_latent_hashes` maps. The exact provenance schema/reference has the safe sibling `source_staging_relpath` and canonical source `source_staging_receipt_sha256`; recursive source validation and external final-root pin follow the Task 3 contract.
  - Implement `derive_controlled_instance(instance, event_latents, controls)` as pure frozen-only logic: no RNG, regeneration, filesystem, clock or mutation. Base is byte/hash-equal to persisted status/disruptions, including coalesced rain intervals. High uses `u < min(1,2p)` only for document/base-failure/rain candidate overlays and emits a fresh canonical contiguous event stream: `sequence` is renumbered and each row `payload_hash` is recomputed for that projection. Events present in both projections must remain semantically equal in `event_type`, `latent_id`, `event_origin`, `resource_id`, `truck_id`, `cause`, `operation`, `time`, `duration_min` and `return_time`; `sequence`/`payload_hash` are projection-local, not byte-identical. Document/base-failure additions are appended, while active rain blocks are re-coalesced by the canonical interval algorithm and may produce different rain rows/interval IDs. Forced events and all realized durations remain unchanged; non-rain base disruptions, priority changes and forced disruptions preserve those stable fields, while controlled rain rows may merge/change IDs but must cover their active immutable block latent IDs. Distinct `controlled_view_hash`/`event_overlay_hash` attest projection identity. `scheduled_failure_start` is policy-independent and `effective_failure_start` is only a deterministic runtime deferment logged alongside recovery for both base and forced failures.

- [ ] **Step 4: Run the ledger/roundtrip checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py -k "event_latent or legacy_five_payload or controlled_derivation"`

Expected: PASS for exact schema/order, six-payload hashes, base/high projection and no-RNG/no-regeneration/no-mutation; old five-payload, missing/corrupt ledger and provenance/source tamper fail closed without a DES campaign.

- [ ] **Step 5: Commit only the retrofit.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/dataset.py experimento-notebook/src/pequiflux_experiment/domain.py experimento-notebook/src/pequiflux_experiment/manifest.py experimento-notebook/tests/test_config_manifest.py experimento-notebook/tests/conftest.py
rtk git commit -m "feat(experimento): persist event latent ledger for sensitivity"
```

Task 3 and all later DES/sensitivity work are blocked until this commit is present.

### Task 3: STAGING rejection and explicit one-attempt resample

**Files:**
- Modify/Replace: `experimento-notebook/tests/test_config_manifest.py` (replace any implicit retry/source-dataset assumptions)
- Modify: `experimento-notebook/src/pequiflux_experiment/dataset.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/manifest.py`
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/domain.py` for `AbortedStaging` and provenance types.

**Interfaces:**
- Consumes: an `AbortedStaging` path, explicit approved `FaceValidationReport`, the declared `source_staging_root_hash`, and the exact rejected `instance_id` list.
- Produces: `validate_candidate_semantics(config, candidate) -> CandidateValidation` (the canonical production validator used before materialization); pure `probe_generation_attempt(config, face_report, candidate_headers, *, generation_attempt=0) -> GenerationProbeReceipt` for a lightweight, nonpublishing diagnostic that can report both known shortages but is never an `AbortedStaging`, authorization or `FREEZE` (its `status`, `publishing`, `aborted_staging`, `authorization` and rejection-row fields make that boundary explicit); pure `plan_explicit_resample(aborted_staging, exact_rejected_ids, config) -> ResamplePlan`; `generate_synthetic_dataset(config, face_report, dataset_root, *, now_utc, generator_version)`; `load_aborted_staging(path) -> AbortedStaging` exposing `staging_json`, `manifest`, `rejection_rows`, `accepted_instance_ids`, `rejected_instance_ids`, `remaining_instance_ids`, `chain_valid` and `recomputed_staging_root_hash`; `load_freeze_receipt(root, *, expected_dataset_root_hash) -> FreezeReceipt` reading only canonical `FREEZE.json`/manifest/header-index receipts and enforcing the external action pin; `read_instance_header(root, instance_id, *, expected_dataset_root_hash) -> InstanceHeader` reading only `scenario_index` and the persisted instance/hash index from either STAGING or frozen roots, enforcing the same pin and never constructing `FrozenInstance`, trucks or service rows; `resample_synthetic_dataset(config, face_report, source_staging_path, source_staging_root_hash, exact_rejected_ids, destination_root, *, now_utc, generator_version)`; `resample_provenance.json`; `generation_attempt` in every derived CRN key. `GenerationRejectedError` carries the retained `staging_path`; `DatasetPlan.next_ordinal_after(instance_id)` gives the exact post-rejection ordinal; the private `_validate_candidate(candidate) -> bool` seam delegates to `validate_candidate_semantics` and is monkeypatched only for the new-rejection regression. `_install_tiny_generation_fixture(monkeypatch, fixture_path)` is a private file/materialization seam used only by the persisted integration test: it may stub heavy candidate payload materialization only, while the public generator/resampler execute the real artifact writes, canonical bytes/hashes, manifest/checksum chain, atomic rename and STAGING/FREEZE state transitions; neither public API accepts an injector or fallback.

The exact `resample_provenance.json` schema is `{path,sha256,source_staging_relpath,source_staging_receipt_sha256,source_dataset_id,source_staging_root_hash,resampled_instance_ids,generation_attempts,accepted_record_hashes,accepted_instance_hashes,prior_accepted_instance_hashes,accepted_event_latent_hashes,prior_accepted_event_latent_hashes,authorizing_action}`. `source_staging_relpath` is only a safe basename of the retained source staging; source and destination must be sibling directories under the same action/dataset root. Reject empty/`.`/absolute paths, separators or `..`, symlink/junction/reparse points, missing/colliding destinations and cycles. `source_staging_receipt_sha256` is the canonical SHA-256 of the source `STAGING.json`; loaders resolve `current_root.parent / source_staging_relpath`, recursively validate that chain and compare source dataset/root/receipt hashes, accepted/rejected partition, attempts and record/latent maps. `resampled_instance_ids`, `generation_attempts` and `accepted_*` maps in the final provenance contain only IDs produced by the current action; `prior_*` maps contain the complete inherited partition. `resample_provenance=null` and no file are valid only when every header has `generation_attempt=0`; a positive attempt requires the provenance file. Internal chaining proves consistency with retained sources; authenticity against a coordinated rewrite of the entire chain requires the external action-manifest `pinned_dataset_root_hash` checked by every public receipt/header loader.

- [ ] **Step 1: Write the failing tests (RED).**

Keep all heavy Task 3 helpers local to `test_config_manifest.py`; do not put them in `tests/conftest.py` and do not use a relative `.conftest` import. Before RED, define/import the local `write_action_manifest_pin`, `ValidResampledChain`, `valid_resampled_chain`, and tamper helpers using only Task 1/2/2.5 modules plus standard library and pytest. The valid chain must exercise the real public generator/resampler through the private tiny-file seam, while avoiding full payload/DES execution.

Test contracts:

- `test_probe_diagnoses_both_without_publishing`: `probe_generation_attempt` is diagnostic only (`status=DIAGNOSTIC`, `publishing=False`, no staging/authorization) and reports both known shortages in canonical order without writing a freeze.
- `test_fail_fast_persisted_resample_sequence`: action 1 stops at `s11-seed119` with one `ABORTED` staging and no `FREEZE.json`; resample 1 accepts exactly that ID once, preserves all inherited records/latents, then stops at `s23-seed141`; resample 2 accepts exactly that ID once and publishes a strict 3,600-instance/18,000-policy-day freeze. Use `load_freeze_receipt` and `read_instance_header` for counts/attempts, not a full dataset materialization.
- For each resample provenance, assert canonical bytes and compare the entire ordered dictionaries `accepted_record_hashes`, `accepted_instance_hashes`, `prior_accepted_instance_hashes`, `accepted_event_latent_hashes` and `prior_accepted_event_latent_hashes` against complete maps reconstructed from every relevant persisted header; do not assert only one key/value or only map keys. Verify the real provenance SHA is referenced by the manifest.
- `test_new_rejection_aborts_without_retry`: monkeypatch only the private validator to reject the attempt-1 candidate; require a retained second `ABORTED` staging, no destination/`FREEZE.json`, one `PROHIBITED`/`EXPLICIT_RESAMPLE_REQUIRED` row and no automatic retry.
- `test_source_chain_validation_fail_closed`: run unsafe basename, absolute/separator/parent path, missing source, cycle, link/reparse, source-receipt/root and noncanonical-byte tamper cases against the source-aware loader; the focused GREEN command must include this test and the detached-pin test.
- `test_detached_pin_rejects_coherent_rewrite`: the local `rewrite_payload_and_hash_chain` helper mutates one existing event-latent field with a schema-valid value, serializes JSONL with actual `b"\n"` line endings and checksums with actual `b"\t"` separators plus LF, recomputes manifest/checksum/FREEZE hashes, and then passes the original detached action pin to prove the loader rejects the coherent rewrite.

All local helpers preserve the retained sibling chain and never use a zero hash, stale receipt or fake payload row.
- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py::test_probe_diagnoses_both_without_publishing`

Expected: FAIL because the canonical semantic validator and nonpublishing natural-rejection probe are not implemented.

- [ ] **Step 3: Implement the fail-fast STAGING flow.**

  - Use the canonical semantic validator for every production candidate before materialization, one candidate at a time and never as a batch. A nonpublishing `probe_generation_attempt` may diagnose both known attempt-0 shortages, but it is never an `AbortedStaging`, authorization or `FREEZE` and cannot authorize resample. The persisted action is fail-fast: action 1 stops at the first canonical rejection `n60-m2-b1-priority_shift`/seed `119` (`s11-seed119`), writes exactly one rejection row and `STAGING.json` with `rejected_instance_ids=["s11-seed119"]` and the exact next ordinal; it must not continue to `s23` in that action.
  - Keep both public dataset signatures free of test controls: accept the explicit face report and use only the private `_validate_candidate(candidate)` seam under `monkeypatch` for the new-attempt-1 regression. On rejection, atomically finish all six payloads (including `event_latents.jsonl`), manifest and checksums, then write `STAGING.json` with exactly the seven keys `status`, `manifest_hash`, `checksums_hash`, `staging_root_hash`, `accepted_instance_ids`, `rejected_instance_ids`, and `next_candidate_ordinal`; rejection rows carry `automatic_resample_status='PROHIBITED'` and `next_action='EXPLICIT_RESAMPLE_REQUIRED'`; never write `FREEZE.json` or retry.
  - Require `resample_synthetic_dataset(config, approved_face, source_staging_path, source_staging_root_hash, exact_rejected_ids, destination_root, ...)` to validate the full STAGING/manifest/checksum chain, partition and source root before creating a destination namespace. The implementation is generic over the exact IDs declared by the source STAGING (known IDs are not hardcoded conditionals). Resample 1 accepts only the exact source ID `["s11-seed119"]` at attempt 1, preserves all canonical records/hashes already accepted, continues canonical generation, then stops at the next natural rejection `n60-m3-b2-priority_shift`/seed `141` (`s23-seed141`) and writes a new STAGING with only `["s23-seed141"]` at attempt 0.
  - Resample 2 accepts only `["s23-seed141"]` at attempt 1, preserves prior accepted canonical records/hashes, continues without any automatic retry and publishes `FREEZE.json` only after strict validation reaches exactly 3,600 valid instances and 18,000 policy-day keys. Persist those counts in the canonical `generation_plan_receipt` carried by the final manifest/header, and use `load_freeze_receipt` plus `read_instance_header` (not `load_frozen_dataset` or a `FrozenDataset.instances` materialization) as the integration evidence. The persisted integration test uses only a private deterministic tiny/file fixture seam that stubs heavy payload I/O without overriding the canonical validator, and never materializes full payloads or executes policy-day DES; artifact writes, hashes and state transitions remain real.
  - Persist canonical `resample_provenance.json` with exactly `path`, `sha256`, `source_staging_relpath`, `source_staging_receipt_sha256`, `source_dataset_id`, `source_staging_root_hash`, `resampled_instance_ids`, `generation_attempts`, `accepted_record_hashes`, `accepted_instance_hashes` (the newly accepted IDs), `prior_accepted_instance_hashes` (the inherited IDs), `accepted_event_latent_hashes`, `prior_accepted_event_latent_hashes` and `authorizing_action`. The maps are complete, sorted and keyed by instance ID so `read_instance_header` can reconcile `s11`, `s23` and inherited `s00` without loading payload rows. Reference its real canonical SHA in the new manifest. Reject IDs missing/extra/duplicated, root/hash/ledger/receipt mismatches, destination collisions, or a `PENDING` face report before any namespace.
  - Keep the action manifest outside each dataset subdirectory and write `pinned_dataset_root_hash` after every generated freeze. Every existing-load path (validation nested package, pilot, execute-confirmatory and sensitivity) reads that external pin first and passes it explicitly to `load_freeze_receipt`, `load_frozen_dataset` and `read_instance_header`; a detached/coherently rewritten dataset is rejected even when its internal chain is self-consistent.
  - Remove any legacy source-data hash alias, automatic retry helper, fallback alias or hidden resample path from tests and APIs; preserve aborted staging and rejection logs for diagnosis.

- [ ] **Step 4: Run the resample and abort checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_config_manifest.py -k "probe_diagnoses_both_without_publishing or fail_fast_persisted_resample_sequence or new_rejection_aborts_without_retry or source_chain_validation_fail_closed or detached_pin_rejects_coherent_rewrite"`

Expected: PASS with the nonpublishing probe diagnosing both IDs, persisted action1/action2 fail-fast STAGING sequence (`s11` then `s23`), canonical accepted hashes preserved, one attempt per explicit resample, final manifest/header receipt of 3,600/18,000 read through the lightweight receipt/header APIs, and a retained second ABORTED STAGING (no `FREEZE.json`) plus visible `PROHIBITED`/`EXPLICIT_RESAMPLE_REQUIRED` no-retry row when the public resample is monkeypatched to reject attempt 1; no `load_frozen_dataset`, full payload or 18,000 DES execution.

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
- Consumes: `FrozenInstance`, `EventLatentLedger`, `DispatchPolicy`, events/disruptions and immutable `ExperimentConfig`.
- Produces: immutable `ExecutionControls(ordinary_window, buffer_capacity, threshold_multiplier, intensity, source_dataset_root_hash, event_latents_sha256, control_hash)`; pure `derive_controlled_instance(instance, event_latents, controls) -> FrozenInstance`; `run_day(instance: FrozenInstance, policy: DispatchPolicy | str, controls: ExecutionControls, event_latents: EventLatentLedger) -> DayResult`; `DispatchContext`; `make_policy`; `filter_admissible`; `process_event_batch(events, state) -> BatchResult`; stable event ranks and serialized event logs. `controls` and `event_latents` are mandatory arguments with no defaults, and the function never mutates `ExperimentConfig` or `FrozenInstance`. `DayResult` contains only complete simulation primitives/events/snapshots/hashes; `MetricRow` is intentionally absent until Task 5.

**RED fixture/import precondition:** Before RED, define `BASE_CONTROLS`, `LEDGER`, `frozen_instance`, `CANONICAL_POLICIES` and `canonical_exogenous` locally in `test_dispatch_emulator.py`; import only the Task 4 modules shown in the snippet plus `pytest`. Do not rely on future-task fixtures or relative `conftest` imports.

`ExecutionControls` is a frozen, slots-based value with no defaults. `ordinary_window` is the exact serialized `H0` value; all seven fields above are required, `threshold_multiplier` is canonically quantized `Decimal`, and `control_hash` must match the canonical hash of the other six fields. `BASE_CONTROLS` is constructed explicitly as `(ordinary_window=6, buffer_capacity=12, threshold_multiplier=Decimal("1.00"), intensity="base", source_dataset_root_hash=..., event_latents_sha256=..., control_hash=...)`; sensitivity constructs a complete value per grid cell. Tests pass a separate `LEDGER` fixture to every call; `FrozenInstance` does not carry an implicit or mutable ledger.

- [ ] **Step 1: Write the failing tests (RED).**

```python
import pytest

from pequiflux_experiment.config import ScenarioConfig
from pequiflux_experiment.domain import Event, InstanceContractError
from pequiflux_experiment.emulator import DispatchState, EVENT_RANKS, process_event_batch, run_day

def test_run_day_requires_frozen_instance():
    with pytest.raises(InstanceContractError, match="FrozenInstance"):
        run_day(
            ScenarioConfig(truck_count=60, hopper_count=1, scale_count=1, regime="nominal", scenario_index=0),
            "lexicographic", BASE_CONTROLS, LEDGER,
        )

def test_crn_is_policy_independent(frozen_instance):
    results = [run_day(frozen_instance, name, BASE_CONTROLS, LEDGER) for name in CANONICAL_POLICIES]
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

The module imports `pytest` and the named public symbols above; its fixtures provide `BASE_CONTROLS`, `LEDGER`, `frozen_instance`, and `CANONICAL_POLICIES`, while `canonical_exogenous` serializes only policy-independent event payloads. `ScenarioConfig(...)` is intentionally a real canonical object with `truck_count=60`, `hopper_count=1`, `scale_count=1`, `regime="nominal"` and `scenario_index=0`, so the rejection reaches `run_day` and is not a constructor `TypeError`.

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_dispatch_emulator.py::test_run_day_requires_frozen_instance`

Expected: FAIL because the emulator still accepts legacy scenario/seed inputs or does not exist.

- [ ] **Step 3: Implement the minimum deterministic DES.**

  - Remove random calls, generation, lazy durations/default fields and tiny legacy shortcuts from the execution path. Validate exact truck/service/disruption/latent cardinalities, hashes and required fields before scheduling event rank zero. Require an immutable `ExecutionControls` and `EventLatentLedger`; derive the controlled instance with the pure frozen-only helper before/inside DES, without mutating the source instance/config or reading the filesystem.
  - Define exact numeric event ranks `0,10,11,12,13,20,21,30` for service completion, resource recovery, rain end, resource failure, rain start, document release, priority change and arrival. `scheduled_failure_start` and its candidate duration are frozen and policy-independent; if the resource is busy, the DES deterministically records `effective_failure_start` at current service completion and computes recovery from that effective time, without resampling. Sort by `(time,event_rank,resource_id_or_empty,truck_id_or_empty,sequence)` and apply the complete same-timestamp batch before any dispatch; recovery/end precede new failure/start and a new unavailability wins collisions.
  - Implement one common admissibility filter for cargo/resource compatibility, document, failure/availability, rain closure, precedence and buffer; `fifo_strict` sees only the raw queue head and idles when it is inadmissible, while the other four rank the same `C_adm`. Controls are explicit per run: baseline is `H0=6`, buffer `12`, threshold multiplier `Decimal('1.00')`, intensity `base`; sensitivity supplies every alternative value and its source/ledger hashes. No implicit baseline/fallback path is allowed.
  - Implement exact `fifo_flow_faithful`, `priority_local`, frozen `fixed_score`, and pressure/mandatory-priority/reorder-penalty/affinity `lexicographic` rules. Commands never mutate policy inputs; human overrides require authorized profile, reason and rechecked constraints.
  - Emit immutable `DayResult` with consumed instance/hash, complete events/logs, physical/digital snapshots, A1 counts, A2 fields, remnant queue and replay hashes, but no metric field or fabricated metric value. Task 5's public `compute_policy_day_metrics(persisted_day)` is called by `run_policy_days` after the day/log has been persisted and before the policy-day row is committed; a run cannot close without its complete hashed `MetricRow`, and audit later recomputes/reconciles it.
  - Remove `tiny_scenario`, the old `run_day(scenario, seed, policy)` overload, random/generation/lazy-duration paths, old IDs/aliases and old event/result-schema assertions from `test_dispatch_emulator.py`; all callers use `run_day(FrozenInstance, policy, controls, event_latents)` and compute metrics only after persisting the returned `DayResult`.

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

**RED fixture/import precondition:** Before RED, define `CONFIG`, `VALIDATION_CONFIG`, `APPROVED_FACE`, `PENDING_FACE`, `persisted_day` and the three-instance persisted validation fixture locally in the Task 5 test modules; import `json`, `math`, `pytest` and only the Task 5 APIs under test. Define the A1 fixture path from the persisted package; do not import or promise future runner/capacity/statistics/notebook fixtures.

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
  - Set `non_confirmatory=true`, `validation_scope_hash=sha256(canonical_bytes(config/validation.json)+":"+canonical_bytes(a1_adversarial_fixtures.jsonl))`, and persist the face status/cause. The reduced package carries the same six-payload schema, including a bounded `event_latents.jsonl` and its hash, so checks can prove the frozen-only control seam without using a generator. All checks read only these files.
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
- Consumes: frozen dataset plus its `EventLatentLedger`, explicit `FaceValidationReport`, canonical policy list, phase (`validation`, `pilot` or `execute-confirmatory`), immutable baseline `ExecutionControls`, workload and requirements.
- Produces: `ConfirmatoryWorkload.from_dataset(frozen_dataset, config) -> ConfirmatoryWorkload`; `plan_policy_days(dataset, policies, phase) -> PolicyDayPlan`; `inspect_capacity(workload, requirements, run_root) -> CapacityReceipt`; `require_capacity(receipt)`; `run_policy_days(dataset, policies, phase, run_root, face_report, controls, event_latents, *, capacity_receipt=None, worker=run_day) -> RunBundle`; `load_run_bundle(run_id)`. Baseline controls are explicit even for validation/pilot/confirmatory; no runner infers or mutates them. OS samplers remain private; tests monkeypatch that private seam rather than widening either public API.

**RED fixture/import precondition:** Before RED, define `CONFIG`, `CANONICAL_POLICIES`, `frozen_dataset`, `validation_dataset`, `pending_face`, `approved_face`, `base_controls`, `ledger`, `low_disk_probe`, `blocked_capacity` and `spy_worker` locally in `test_experiment_audit.py`; import the Task 6 APIs/errors and `pytest`. Keep the pending-face validation case separate from the approved-face capacity-block case; do not rely on future-task fixtures or relative `conftest` imports.

- [ ] **Step 1: Write the failing tests (RED).**

```python
def test_capacity_gate_blocks_with_cause(tmp_path, low_disk_probe, frozen_dataset, monkeypatch):
    monkeypatch.setattr("pequiflux_experiment.capacity._os_probe", low_disk_probe)
    workload = ConfirmatoryWorkload.from_dataset(frozen_dataset, CONFIG)
    receipt = inspect_capacity(workload, CONFIG.capacity, tmp_path)
    with pytest.raises(CapacityGateError, match="required_disk_bytes"):
        require_capacity(receipt)
    assert receipt.decision == "BLOCKED"
    assert not (tmp_path / "runs").exists()

def test_policy_day_plan_cardinality_without_des(frozen_dataset):
    assert plan_policy_days(frozen_dataset, CANONICAL_POLICIES, "pilot").count == 3_750
    assert plan_policy_days(frozen_dataset, CANONICAL_POLICIES, "execute-confirmatory").count == 18_000

def test_validation_runner_always_persists_with_pending_face(tmp_path, validation_dataset, pending_face, base_controls, ledger, spy_worker):
    bundle = run_policy_days(
        validation_dataset, CANONICAL_POLICIES, "validation", tmp_path, pending_face,
        base_controls, ledger, worker=spy_worker
    )
    assert bundle.policy_day_count == 15
    assert bundle.namespace_closed is True
    assert spy_worker.calls == 15

def test_approved_face_capacity_block_makes_zero_worker_calls(tmp_path, frozen_dataset, approved_face, blocked_capacity, base_controls, ledger, spy_worker):
    with pytest.raises(CapacityGateError):
        run_policy_days(
            frozen_dataset, CANONICAL_POLICIES, "execute-confirmatory", tmp_path / "blocked",
            approved_face, base_controls, ledger, capacity_receipt=blocked_capacity, worker=spy_worker
        )
    assert spy_worker.calls == 0
    assert not (tmp_path / "blocked").exists()
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py::test_capacity_gate_blocks_with_cause`

Expected: FAIL because `profiles.py`, explicit face/capacity gates and the private OS-probe/worker seams are not present.

- [ ] **Step 3: Implement one-shot capacity and phase execution.**

  - Define `ConfirmatoryWorkload.from_dataset(frozen_dataset, config)` from the actual frozen dataset size and canonical dataset/config/workload hashes; it must not accept a config-only constructor or infer a dataset. Define `profiles.py` with explicit phase/profile fields and pure `plan_policy_days` key construction.
  - Inspect the complete confirmatory workload, dataset size, free disk/RAM, logical CPU, GPU/driver inventory and competing Python/Jupyter/pytest processes via the public `inspect_capacity(workload, requirements, run_root)` only for `execute-confirmatory`; keep OS samplers private and monkeypatchable solely by tests. Register only the current kernel/descendants; block another project process or unproven ownership with an operation/workload/cause error.
  - Persist TTL-60-second receipt with exact disk/RAM formulas, authorized workers, estimated rows/logs, config/dataset/workload hashes, timestamp, inspection version and decision. Revalidate immediately before creating the `execute-confirmatory` namespace; do not gate `pilot` or `sensitivity` on this receipt, and do not wait, retry, kill, change precision, or shrink scope.
  - Select the pilot by canonical hash to exactly `ceil(0,20*72)=15` scenarios and define its 3,750-key plan; require the full frozen dataset for confirmation and define its 18,000-key plan. Production `run_policy_days` refuses partial pilot/confirmatory selections, missing/extra/duplicate keys and mixed hashes.
  - Keep permanent tests cheap: plan cardinality is pure; the only runner integration uses the 15-row persisted validation dataset with an injected worker to prove atomicity/hash. A low-disk/process or pending-face receipt is tested with a spied worker and must create zero calls and zero namespaces. No pytest path executes a full DES campaign.
  - Branch `phase="validation"` before any confirmatory gate: it always writes the reduced persisted package even with `PENDING` face and no/blocked capacity receipt. For `pilot`, require only the explicit approved face report and existing complete frozen dataset; for `execute-confirmatory`, check face and frozen dataset first, then revalidate the explicit capacity receipt immediately before namespace creation. Sensitivity follows its own approved-face/frozen-dataset namespace without this capacity gate. Write each row/log progressively into staging and atomically rename only after complete cardinality/hash checks. Every API receives `face_report` and never consults hidden global state.
  - Remove `run_experiment_matrix`, old `RUN_PROFILE`/`load-confirmatory` routing, tiny fixtures and old results schemas from `test_experiment_audit.py`; replace them with plans, injected validation runner and gate assertions.

- [ ] **Step 4: Run capacity and execution checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py -k "capacity_gate or policy_day_plan or validation_runner or approved_face_capacity_block"`

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

**RED fixture/import precondition:** Before RED, define a persisted `run_bundle` fixture with independent event/snapshot hashes and its on-disk A1 contexts locally in `test_digital_model_replay.py`; import `pytest`, `math` and only the Task 7 APIs under test. No fixture is inherited from `conftest.py` beyond Task 1's face fixture, and replay tests must not call the emulator.

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

**RED fixture/import precondition:** Before RED, define `CONFIG`, a local `audited_confirmatory_bundle` fixture containing complete medium/high pairs, three comparator rows, immutable instance hashes and audit receipts, a `bundle_with_duplicate_pair` fixture derived from it with one duplicated `(scenario_index, seed)`, and the local `make_complete_audited_bundle_from_pairs` helper used by the concrete false-positive regression; import `Decimal`, `pytest` and the Task 8 APIs under test. Do not rely on future sensitivity/export/notebook fixtures or relative `conftest` imports.

- [ ] **Step 1: Write the failing tests (RED).**

```python
from decimal import Decimal

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
    medium = [(Decimal("100.00"), Decimal("80.00"))] * 300 + [(Decimal("100.00"), Decimal("90.00"))] * 300
    high = [(Decimal("100.00"), Decimal("83.00"))] * 2_800
    bundle = make_complete_audited_bundle_from_pairs(
        {"medium": medium, "high": high}, throughput_guard="positive_median_d_prime"
    )
    report = evaluate_h1(bundle, CONFIG)
    assert report.aggregate_relative_median == Decimal("0.17")
    assert report.components_for("medium")[0].waiting_p_value == pytest.approx(.5)
    assert report.components_for("high")[0].waiting_p_value == pytest.approx(0.0)
    assert all(component.median_d_prime > Decimal("0") for component in report.all_components)
    assert report.h1 == "NOT_SUPPORTED"
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_statistics_export.py::test_aggregate_relative_median_false_positive_is_rejected`

Expected: FAIL because H1 pairing, stratum-level p-value aggregation and the concrete aggregate-relative-median regression are absent.

- [ ] **Step 3: Implement exact H1 inference.**

  - Pair only `(scenario_index, seed)` and compare lexicographic with each primary comparator in medium/high. Compute `g_i=(p95_comp-p95_lexicographic)/p95_comp`, reject zero denominators, missing/duplicate pairs and mixed hashes as `H1=INVALID_INPUT` with causal error.
  - For each `(stratum, comparator)`, compute `g_i` with `Decimal` and canonical quantization, test `median(g_i-.15)>0` with one-sided Wilcoxon signed-rank and require median `g≥.15`; test throughput `d'_i=(T_lex-T_comp)+delta(N_i)` with one-sided Wilcoxon and require the explicit `median(d')>0` guard. Set each comparator IUT p-value to the larger component p-value, then set each stratum global p-value to `max(all component and IUT p-values in that stratum)` before Holm.
  - Report medians/IQR, paired differences, percent gain, Hodges–Lehmann, deterministic 5,000-resample paired bootstrap 95% CI, rank-biserial effect, zero count and exact one-sided sign test only when zeros exceed 50%; sign test never replaces Wilcoxon/IUT/Holm.
  - Apply a single sequential Holm correction only to the two stratum global p-values (`p_IUT_medium`, `p_IUT_high`) at 0,05; never adjust the three comparators separately. Set `SUPPORTED` only if both strata pass all three IUTs and both adjusted p-values reject; low, A1/A2, CO2 and secondary metrics stay descriptive. The fixed 600/2,800-pair fixture above must report canonical `p_medium≈.5`, `p_high=0`, aggregate median `.17`, positive throughput guards and still remain `NOT_SUPPORTED`; an exact median `g=.15` (zero shifted effect) is never support even when a library emits `p≤.05`.
  - Remove legacy `test_statistics_export.py` assertions that aggregate strata, use old result IDs/schema, fill absent components or treat an aggregate relative median as evidence; retain the concrete 600-pair regression, duplicate/missing/hash invalidation and exact 5,000 bootstrap contract.

- [ ] **Step 4: Run statistics and invalid-input checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_statistics_export.py -k "aggregate_relative_median_false_positive or iut_holm_and_invalid_pairing or invalid_pairing_is_not_inconclusive"`

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
- Consumes: the same frozen dataset/CRN, its validated `EventLatentLedger`/SHA-256, explicit `FaceValidationReport`, immutable baseline/high `ExecutionControls` and exploratory stress/policy grid.
- Produces: `run_sensitivity(dataset, event_latents, face_report, grid, ...)`; `summarize_sensitivity`; `ROBUST`/`INVALID_INPUT` result with joint-cell counts and descriptive medians/IQR/bootstrap. The canonical grid has exactly 54 cells in `H0 → buffer → threshold_multiplier → intensity` order and each cell has exactly 3,600 paired instances × four policies; no RNG, regeneration, H1 input or confirmatory writes.

**RED fixture/import precondition:** Before RED, define a local `sensitivity_bundle` fixture with the complete 54-cell synthetic rows, immutable base/high controls, ledger/source hashes and four policy rows per cell; each cell exposes its four persisted `rows` plus `controlled_view_hash`/`event_overlay_hash`. Import `pytest` and the Task 9 APIs under test. The fixture must expose `drop_one_cell` and `full_grid_executed`; do not rely on future export/notebook fixtures or relative `conftest` imports.

`grid` is a closed list of 54 cells, and every cell carries a complete immutable `ExecutionControls` (including source, ledger and control hashes); it is not a tuple from which the runner may infer baseline/high controls. `run_sensitivity` rejects a missing/default/mutated control before namespace creation and passes that explicit control plus the separate `EventLatentLedger` to every DES call. The function never constructs a control from mutable `ExperimentConfig` or regenerates a ledger.

- [ ] **Step 1: Write the failing test (RED).**

```python
def test_joint_sensitivity_robustness_and_invalid_input(sensitivity_bundle):
    result = summarize_sensitivity(sensitivity_bundle)
    assert result.cell_rule == "same_cell_all_three_comparators"
    assert result.threshold == pytest.approx(.75)
    assert result.h1_input_used is False
    assert result.decision in {"ROBUST", "NON_ROBUST"}
    assert result.cell_count == 54
    assert result.base_control_hash and result.high_control_hash
    assert result.event_latents_sha256 and result.source_dataset_root_hash
    assert result.pairing_key == ("scenario_index", "seed")
    assert all(cell.median_d_prime > 0 for cell in result.cells)
    assert all(cell.controlled_view_hash and cell.event_overlay_hash for cell in result.cells)
    assert all(len({row.controlled_view_hash for row in cell.rows}) == 1 for cell in result.cells)
    assert all(len({row.event_overlay_hash for row in cell.rows}) == 1 for cell in result.cells)
    assert all(cell.source_dataset_root_hash == result.source_dataset_root_hash for cell in result.cells)
    assert all(cell.event_latents_sha256 == result.event_latents_sha256 for cell in result.cells)
    incomplete = sensitivity_bundle.drop_one_cell()
    assert summarize_sensitivity(incomplete).decision == "INVALID_INPUT"
    assert sensitivity_bundle.full_grid_executed is False
```

- [ ] **Step 2: Run the focused RED check once.**

Run (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py::test_joint_sensitivity_robustness_and_invalid_input`

Expected: FAIL because the separated namespace, synthetic-row summarizer and joint rule are absent.

- [ ] **Step 3: Implement exploratory sensitivity.**

  - Run only from the approved frozen dataset and explicit face report with a separate manifest/schema and no writes to confirmatory rows. Load and hash `event_latents.jsonl` before creating the sensitivity namespace. In `high` intensity multiply only document-block, base-failure and rain Bernoulli rates by 2,0 capped at 1,0, apply `u < min(1,2p)` to the ledger candidates, preserve non-rain base disruptions, forced rows and priority rows semantically in `event_type`, `latent_id`, `event_origin`, `resource_id`, `truck_id`, `cause`, `operation`, `time`, `duration_min` and `return_time`, and keep forced events/durations unchanged. The high overlay emits a fresh canonical contiguous event stream: `sequence` is renumbered and each row `payload_hash` is recomputed for that projection. Rain rows are a canonical coalesced projection that must cover the active immutable block latent IDs; controlled rain may merge rows/change IDs. Distinct `controlled_view_hash`/`event_overlay_hash` attest projection identity; `base` remains a byte/hash-equal projection of persisted statuses/disruptions.
  - Cross `H0 ∈ {4,6,8}`, buffer `∈ {8,12,16}`, threshold multiplier `∈ {0,75;1,00;1,25}`, intensity `{base,high}` in that order for lexicographic and the three primary comparators, yielding exactly 54 cells and 14,400 policy-days per cell (777,600 total). Pair only `(scenario_index, seed)` within each cell; require every row to carry matching `source_dataset_root_hash`, `event_latents_sha256`, `control_hash` and `instance_hash`. Add deterministic `myopic_predicted_delay`, `window_without_stability`, and `batch_by_cargo` only to descriptive exploration.
  - For every complete cell, require median p95 gain `>0` and `median(d')>0`, where `d'=(T_lex-T_comp)+delta(N)`, against all three comparators; count the cell once. Publish `ROBUST` iff joint fraction ≥75%; expose per-comparator fractions only as diagnostics. Any missing package/cell, zero p95 denominator, mismatched pairing/hash/control/ledger or old five-payload source is `INVALID_INPUT`, never `NON_ROBUST`, and no p-values/Holm feed H1. Permanent tests summarize synthetic complete rows only; they do not run the stress grid or DES.

- [ ] **Step 4: Run sensitivity checks.**

Verify (CWD `C:\\p\\PequiFlux\\TCC`): `rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q experimento-notebook\\tests\\test_experiment_audit.py::test_joint_sensitivity_robustness_and_invalid_input`

Expected: PASS for joint-cell counting, no H1 input, and incomplete-cell invalidation.

- [ ] **Step 5: Commit the task files.**

```bash
rtk git add experimento-notebook/src/pequiflux_experiment/sensitivity.py experimento-notebook/src/pequiflux_experiment/experiment.py experimento-notebook/tests/test_experiment_audit.py
rtk git commit -m "feat(experimento): isolate sensitivity and joint robustness"
```

For descriptive sensitivity intervals only, use exactly 5,000 paired bootstrap resamples with indices derived deterministically from `sensitivity-bootstrap.v1` plus the cell/ledger hashes (record seed/version in the sensitivity manifest); do not invoke the DES RNG and never use these intervals to decide `ROBUST`.

### Task 10: Audited transactional exports

**Files:**
- Modify/Replace: `experimento-notebook/src/pequiflux_experiment/export.py`
- Modify/Replace: `experimento-notebook/tests/test_statistics_export.py` (remove legacy export paths/schema assertions)
- Modify: `experimento-notebook/src/pequiflux_experiment/manifest.py`, `statistics.py`, `audit.py` and `sensitivity.py` to expose pinned source hashes and audit status.

**Interfaces:**
- Consumes: only closed, independently audited run bundles and persisted metric/statistical frames.
- Produces: `export_analysis(bundle, results_root)` and `export_audit_table(bundle, results_root)` writing the exact audited artifact set transactionally. A sensitivity bundle writes sensitivity PDFs only in its own namespace; a confirmatory bundle never receives them.

**RED fixture/import precondition:** Before RED, define a local audited `audited_bundle` fixture and import `pytest`, `ExportContractError` and the Task 10 exporters in `test_statistics_export.py`. The fixture must expose the exact audited output set and an `with_audit(False)` variant; do not rely on future notebook fixtures or relative `conftest` imports.

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
    actual = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert actual == expected
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

**RED fixture/import precondition:** Before RED, define `ROOT`, `execute_notebook` and the temporary output fixture locally in `test_notebook.py`; import `json`, `re`, `nbformat`, `pytest` and only the notebook test helpers. Do not rely on future fixtures or relative `conftest` imports.

- [ ] **Step 1: Write the failing test (RED).**

```python
def test_notebook_actions_and_validation_run(tmp_path):
    nb = nbformat.read(ROOT / "TCC_experimentos.ipynb", as_version=4)
    source = "\n".join(cell.source for cell in nb.cells if cell.cell_type == "code")
    assert 'ACTION = "validation"' in source
    assert "ALLOWED_ACTIONS = (\"validation\", \"generate-synthetic\", \"pilot\", \"execute-confirmatory\", \"audit-analyze\", \"sensitivity\")" in source
    assert set(re.findall(r'ALLOWED_ACTIONS\s*=\s*\(([^)]*)\)', source))
    assert set(re.findall(r'"([^"]+)"', source.split("ALLOWED_ACTIONS", 1)[1].split(")", 1)[0])) == {
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

- Latent/control coverage: Task 2.5 is a mandatory gate before Task 4; the six-payload `event_latents.jsonl` envelope/variants, disruption back-references, resample hash maps, immutable `ExecutionControls`, pure base/high derivation and zero-RNG sensitivity pairing are covered by explicit RED/GREEN checks.
- Statistics/sensitivity coverage: Task 8's Decimal 600/2,800 fixture proves `p_medium=.5`, `p_high=0`, Holm and positive `median(d')` without aggregate false support; Task 9 requires 54 complete cells, exact pair/control/ledger/source hashes and `INVALID_INPUT` for zero denominators or stale artifacts.

- Coverage check: Tasks 1–3 cover config/face, canonical planning/freeze and `AbortedStaging` resample; Tasks 4–7 cover event semantics, validation/A1, capacity, runner, replay and A2; Tasks 8–10 cover H1, sensitivity and audited exports; Task 11 covers the sole notebook interface.
- Contract/API scan: `DayResult` has no metric field or fabricated value; reduced validation is only `build_validation_dataset`; production generation has no reduced flag; capacity uses `from_dataset`, not a config-only workload; `compute_cohen_kappa` receives explicit label sets.
- Test-cost scan: no pytest test materializes production trucks/services or executes the pilot/confirmatory DES counts; pure plans, the three-instance validation package, synthetic sensitivity rows and injected worker/provider gates are the only permanent execution checks.
- Gate scan: validation persists with either `APPROVED` or `PENDING` face status; only principal generation/pilot/confirmatory/sensitivity routes block before namespace, and `audit-analyze` remains diagnostic. Every mutating API receives `face_report` explicitly.
- Legacy scan: old `tiny_scenario`, `run_day(scenario, seed, policy)`, `run_experiment_matrix`, `RUN_PROFILE`, `load-confirmatory`, environment/latest discovery, old IDs/aliases and old result schemas are removed from implementation, notebook, README and the named test files.
- Artifact/statistics scan: FREEZE/hash formulas, eight metrics/A1 contexts, exact event ranks, H1 stratum max-p and two-value Holm, joint 75% sensitivity and exact export filenames are specified without alternate paths.

## Final Verification and Handoff

Run the following exactly once with CWD `C:\\p\\PequiFlux\\TCC` after all task stages (Tasks 1, 2, 2.5, 3, 4–11); do not retry a failing command. The canonical pytest run includes the `nbclient` top-to-bottom validation test exactly once; do not execute a separate notebook command or any campaign.

```powershell
rtk experimento-notebook\\.venv\\Scripts\\python.exe -m pytest -q
rtk experimento-notebook\\.venv\\Scripts\\python.exe -m compileall -q experimento-notebook\\src experimento-notebook\\tests
```

After those two commands, inspect the notebook test's receipt/output path from that run and record `FACE_VALIDATION`/`non_confirmatory` values plus the six-payload/`event_latents_sha256` roundtrip receipt. Run a live capacity preflight only if a real frozen dataset exists, using `ConfirmatoryWorkload.from_dataset(frozen_dataset, config)` and the public `inspect_capacity(workload, config.capacity, run_root)`; record the actual `PASS` or `BLOCKED` decision without requiring either outcome. If no real frozen dataset exists, record `NOT_RUN_NO_FROZEN_DATASET` and rely on the deterministic injected low-disk/process block plus the existing read-only capacity audit. Never fabricate a pass/block and never launch full generation or a campaign during final verification. Preserve any failed staging/run namespace and its causal log; never clean the dirty root or claim confirmatory evidence from validation, pilot or sensitivity. `graphify` is N/A when `graphify-out/` is absent.
