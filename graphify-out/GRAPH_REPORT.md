# Graph Report - TCC  (2026-09-07)

## Corpus Check
- 45 files · ~101,030 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1251 nodes · 3716 edges · 48 communities (43 shown, 5 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 273 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e2e50b03`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_config
- audit.py
- YardSnapshot
- Any
- dataset.py
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- Candidate
- EventRecord
- config.py
- .__post_init__
- canonical_bytes
- _validate_resample_provenance
- DatasetContractError
- digital_model.py
- ExecutionControls
- Path
- statistics.py
- Projeto experimental reproduzível em notebook
- replay.py
- PairingError
- ExperimentConfig
- Exact Invariants and Check Mapping
- emulator.py
- canonical_file_hash
- DigitalModel
- _build_event_latents
- EventLatentLedger
- DispatchPolicy
- test_a2_structural.py
- ComparisonStats
- DataFrame
- power_analysis_rhfs.py
- File Map
- DatasetPlan
- Recommendation
- ExportedArtifacts
- test_notebook.py
- test_export_audit_table_uses_persisted_json_and_rejects_collision
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- FrozenServiceTime
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 88 edges
2. `DatasetContractError` - 79 edges
3. `load_config()` - 77 edges
4. `ScenarioConfig` - 63 edges
5. `Candidate` - 52 edges
6. `_DaySimulation` - 50 edges
7. `FrozenInstance` - 49 edges
8. `YardSnapshot` - 46 edges
9. `EventRecord` - 46 edges
10. `EventLatentLedger` - 43 edges

## Surprising Connections (you probably didn't know these)
- `test_public_generator_has_no_test_injector()` --indirect_call--> `generate_synthetic_dataset()`  [INFERRED]
  experimento-notebook/tests/test_config_manifest.py → experimento-notebook/src/pequiflux_experiment/dataset.py
- `AuditError` --uses--> `ExperimentConfig`  [INFERRED]
  experimento-notebook/src/pequiflux_experiment/audit.py → experimento-notebook/src/pequiflux_experiment/config.py
- `AuditError` --uses--> `ScenarioConfig`  [INFERRED]
  experimento-notebook/src/pequiflux_experiment/audit.py → experimento-notebook/src/pequiflux_experiment/config.py
- `AuditError` --uses--> `EventRecord`  [INFERRED]
  experimento-notebook/src/pequiflux_experiment/audit.py → experimento-notebook/src/pequiflux_experiment/events.py
- `AuditError` --uses--> `RunBundle`  [INFERRED]
  experimento-notebook/src/pequiflux_experiment/audit.py → experimento-notebook/src/pequiflux_experiment/experiment.py

## Import Cycles
- None detected.

## Communities (48 total, 5 thin omitted)

### Community 0 - "load_config"
Cohesion: 0.05
Nodes (97): load_config(), Path, Load and validate a JSON configuration from a local path., canonical_payload_schemas(), derive_controlled_projection(), _jsonl_bytes(), Derive a frozen projection and return its two identity attestations., Validate one instance's complete disruption realization against the protocol. (+89 more)

### Community 1 - "audit.py"
Cohesion: 0.07
Nodes (59): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _observed_exclusion() (+51 more)

### Community 2 - "YardSnapshot"
Cohesion: 0.15
Nodes (18): Replay ``events`` from an optional detached physical snapshot., Return a detached copy that cannot mutate the projection., replay_events(), The canonical state of one service resource (scale, hopper, or similar)., A complete, JSON-friendly observation of the yard at one instant., Resource, YardSnapshot, _decision_chain_prefix() (+10 more)

### Community 3 - "Any"
Cohesion: 0.15
Nodes (8): _dataset_canonical_bytes(), _dataset_digest(), _latent_sha256(), Any, Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation., Hash canonical event-latent rows without importing the dataset layer., _thaw_dataset_value()

### Community 4 - "dataset.py"
Cohesion: 0.09
Nodes (48): _assert_finite_json(), canonical_event_latent_schema(), _coalesced_rain_rows(), _controlled_event_hash(), _derive_controlled_instance(), _digest_value(), _disruption_payload_hash(), _expected_instance_ids() (+40 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.13
Nodes (7): _DaySimulation, Any, Count queued and in-flight trucks that still need unload capacity. A scale-in…, Apply the protocol's mandatory-priority and short-window rules., Return mean/p95 accumulated wait per truck and censored residual., _Scheduled, _validate_regime()

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.12
Nodes (46): Execute validated frozen inputs; never generate or replace missing draws., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), make_policy(), Construct one of the frozen policy-panel implementations., build_validation_fixture(), candidate() (+38 more)

### Community 7 - "export.py"
Cohesion: 0.12
Nodes (36): BaseException, _destination(), _ensure_targets_absent(), _export_analysis_core(), export_audit_table(), _figure_improvement(), _figure_p95(), _figure_tradeoff() (+28 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.06
Nodes (32): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+24 more)

### Community 9 - "Candidate"
Cohesion: 0.11
Nodes (19): Candidate, DispatchContext, Any, Alias matching the domain truck terminology., Alias for the current-stage entry timestamp., Construct a candidate from a Task 2 ``Truck`` value., Immutable observable state supplied to a policy at one decision point., Return a deterministic key; lower keys are selected. (+11 more)

### Community 10 - "EventRecord"
Cohesion: 0.13
Nodes (24): Create an empty projection with no applied events., Create the canonical empty yard state., EventRecord, Path, Write events as one canonical JSON object per line., Read and validate every non-empty JSONL event line., One ordered, validated event in the experiment trace., read_jsonl() (+16 more)

### Community 11 - "config.py"
Cohesion: 0.11
Nodes (35): CapacityGateError, CapacityReceipt, _evaluate(), inspect_capacity(), _now(), _os_probe(), Path, RuntimeError (+27 more)

### Community 12 - ".__post_init__"
Cohesion: 0.25
Nodes (3): _finite_nonnegative(), _identifier(), Alias for ``clock`` at event-oriented boundaries.

### Community 13 - "canonical_bytes"
Cohesion: 0.06
Nodes (63): canonical_bytes(), canonical_json(), config_as_dict(), config_hash(), Return the validated configuration in its JSON-compatible shape., Serialize configuration with stable key ordering and compact separators., Serialize any JSON-compatible value in the canonical byte representation., Return the SHA-256 digest of the canonical UTF-8 configuration JSON. (+55 more)

### Community 14 - "_validate_resample_provenance"
Cohesion: 0.12
Nodes (29): _canonical_confirmatory_config(), _install_tiny_generation_fixture(), _instance_headers_from_manifest(), load_aborted_staging(), _load_aborted_staging_internal(), load_freeze_receipt(), Install a private tiny materialization seam for persisted integration tests., Validate provenance reference, content bytes, and header reconciliation. This… (+21 more)

### Community 15 - "DatasetContractError"
Cohesion: 0.14
Nodes (23): DatasetContractError, _generate_one_candidate(), _generate_until_rejection(), _materialize_production_header(), _PayloadWriter, Collect deterministic rows for one complete production freeze., Materialize one complete immutable instance into the payload writer., Validate one fully generated candidate before any payload write. The priority-… (+15 more)

### Community 16 - "digital_model.py"
Cohesion: 0.23
Nodes (8): Event-applied digital projection of the physical yard., _canonicalize(), _freeze(), Any, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Normalize JSON values into detached dict/list/scalar containers., _thaw()

### Community 17 - "ExecutionControls"
Cohesion: 0.15
Nodes (14): _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., _controlled_projection_overlay_hash(), _controlled_projection_view_hash(), _controlled_rain_covered_latent_ids(), ExecutionControls (+6 more)

### Community 18 - "Path"
Cohesion: 0.11
Nodes (29): _as_utc(), _build_manifest(), _create_staging_directory(), freeze_dataset(), generate_synthetic_dataset(), _git_inventory(), _load_frozen_dataset(), _persist_staging_abort() (+21 more)

### Community 19 - "statistics.py"
Cohesion: 0.22
Nodes (16): _bootstrap(), _comparison_stats(), _decimal_relative_improvements(), _finite_array(), _hodges_lehmann(), _iqr(), Decimal, ndarray (+8 more)

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.23
Nodes (16): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., Return the canonical SHA-256 digest used in log state boundaries. (+8 more)

### Community 22 - "PairingError"
Cohesion: 0.10
Nodes (27): _as_frame(), _canonical_protocol_error(), canonical_scenario_metadata(), _derived_stratum(), _extract_pair_frame(), _hashes(), _normalise_stratum(), _pair_identifier() (+19 more)

### Community 23 - "ExperimentConfig"
Cohesion: 0.05
Nodes (60): ExperimentConfig, factorial_scenarios(), One point in the confirmatory factorial design., The complete, immutable protocol configuration., Require exact equality with every frozen field in confirmatory.json., Enumerate the complete factorial in N, m, b, regime order., ScenarioConfig, validate_confirmatory_config() (+52 more)

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "emulator.py"
Cohesion: 0.10
Nodes (12): DispatchBlocked, NoFeasibleCandidate, RuntimeError, Raised when hard constraints leave no admissible dispatch choice., Raised when ``fifo_strict`` must idle behind an ineligible head truck., DayResult, Deterministic discrete-event emulator for the PequiFlux yard. The…, Canonical output identifying its frozen input, controls and policy. (+4 more)

### Community 26 - "canonical_file_hash"
Cohesion: 0.14
Nodes (25): _digest_bytes(), _finalize_freeze(), _load_json(), Write canonical checksums/manifest and return their linked digests., Validate an ABORTED staging namespace without requiring FREEZE.json., Require the exact immutable file set for an initial or resampled freeze., Anchor every persisted protocol value to the canonical config on disk., _validate_checksum_chain() (+17 more)

### Community 27 - "DigitalModel"
Cohesion: 0.13
Nodes (11): DigitalModel, Any, Extract the fields that identify a recommendation's selection. Decision records…, Apply an ordered event stream to an isolated ``YardSnapshot``., Apply one event atomically, rejecting ordering and state violations., The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs., Compatibility alias for callers that used the earlier name. (+3 more)

### Community 28 - "_build_event_latents"
Cohesion: 0.21
Nodes (16): crn_digest(), crn_seed(), Return the SHA-256 digest for one canonical CRN substream key., Map a CRN key to a stable non-negative integer seed., _build_event_latents(), _build_instance(), _draw_uniform(), _instance_id() (+8 more)

### Community 29 - "EventLatentLedger"
Cohesion: 0.22
Nodes (3): EventLatentLedger, Explicit alias for the immutable event-latent payload., Immutable, keyed collection of all pre-realisation event candidates. Rows are…

### Community 30 - "DispatchPolicy"
Cohesion: 0.17
Nodes (14): ABC, _activated_rules(), _build_justification(), DispatchPolicy, _exclusion(), feasible_candidates(), _fifo_reference(), Feasibility and recommendation boundaries for the yard dispatcher. The… (+6 more)

### Community 31 - "test_a2_structural.py"
Cohesion: 0.25
Nodes (17): Return one policy recommendation after hard-constraint filtering., recommend(), _build_bundle(), parametrize, Path, Regression checks for the explicit five-field A2 decision contract., _rewrite_first_decision(), test_audit_authenticates_decision_facts_against_events() (+9 more)

### Community 32 - "ComparisonStats"
Cohesion: 0.10
Nodes (4): ComparisonStats, H1Report, Statistics and gates for one stratum/comparator pair., Structured confirmatory result for both congestion strata.

### Community 33 - "DataFrame"
Cohesion: 0.31
Nodes (10): _first_column(), _holm_adjust(), _long_metric_column(), _metric_column(), paired_dataframe(), DataFrame, ValueError, Materialise the report summary as a fresh DataFrame for export. (+2 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.35
Nodes (11): Namespace, BootstrapResult, estimate_mde80(), load_pairs(), main(), parse_args(), ndarray, Path (+3 more)

### Community 35 - "File Map"
Cohesion: 0.18
Nodes (10): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 1: Configuração congelada e manifesto, Task 2: Eventos e projeção independente do modelo digital, Task 3: Restrições, políticas e emulador DES, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação (+2 more)

### Community 36 - "DatasetPlan"
Cohesion: 0.06
Nodes (34): DatasetPlan, FaceValidationError, GenerationPlanReceipt, GenerationRejectedError, plan_explicit_resample(), plan_synthetic_dataset(), probe_generation_attempt(), Return detached, lightweight headers in canonical plan order. (+26 more)

### Community 37 - "Recommendation"
Cohesion: 0.22
Nodes (4): _finite_nonnegative(), _identifier(), A policy's selected candidate and its auditable ranking context., Recommendation

### Community 39 - "test_notebook.py"
Cohesion: 0.25
Nodes (9): _cell_source(), Path, Contract checks for the central experiment notebook. The structural check…, The load profile must re-audit, analyse, and export persisted evidence., Load the notebook without requiring the optional notebook stack., _read_notebook_with_stdlib(), test_notebook_has_ordered_sections_and_validation_default(), test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() (+1 more)

### Community 41 - "Notebook de experimentos PequiFlux"
Cohesion: 0.22
Nodes (8): Ambiente deliberado, Estado deste checkout, Execução limpa canônica, Fronteiras científicas, Layout de artefatos, Notebook de experimentos PequiFlux, Perfis, Testes

### Community 42 - "domain.py"
Cohesion: 0.15
Nodes (12): canonical_allowed_cargo_types(), _cargo_tuple(), _freeze_dataset_value(), _latent_number(), _latent_resource(), Mutable physical-domain values used by the independent digital model. The…, Detach a JSON-compatible value into immutable containers., Validate variant ranges and CRN/entity semantics without a live config. (+4 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (7): Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "FrozenServiceTime"
Cohesion: 0.15
Nodes (7): FrozenResource, FrozenServiceTime, Immutable resource record used by a frozen instance., One pre-generated service duration and its CRN provenance., test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order(), test_frozen_instance_service_order_keeps_truck_identity(), test_frozen_service_rejects_forged_crn_draw_key()

## Knowledge Gaps
- **81 isolated node(s):** `pequiflux-experiment`, `graphify`, `graphify`, `Fontes normativas do projeto`, `Classificação correta do artefato visual` (+76 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExperimentConfig` connect `ExperimentConfig` to `load_config`, `audit.py`, `ComparisonStats`, `dataset.py`, `DatasetPlan`, `config.py`, `canonical_bytes`, `_validate_resample_provenance`, `DatasetContractError`, `Path`, `statistics.py`, `PairingError`, `canonical_file_hash`, `_build_event_latents`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `ScenarioConfig` connect `ExperimentConfig` to `ComparisonStats`, `audit.py`, `YardSnapshot`, `dataset.py`, `DatasetPlan`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `config.py`, `canonical_bytes`, `DatasetContractError`, `digital_model.py`, `ExecutionControls`, `statistics.py`, `PairingError`, `emulator.py`, `DigitalModel`, `_build_event_latents`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `DayResult` connect `emulator.py` to `YardSnapshot`, `Recommendation`, `_DaySimulation`, `test_dispatch_emulator.py`, `Candidate`, `EventRecord`, `DatasetContractError`, `ExecutionControls`, `ExperimentConfig`, `DigitalModel`, `EventLatentLedger`, `DispatchPolicy`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Candidate` (e.g. with `DayResult` and `_DaySimulation`) actually correct?**
  _`Candidate` has 11 INFERRED edges - model-reasoned connections that need verification._