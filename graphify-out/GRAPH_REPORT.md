# Graph Report - TCC  (2026-09-07)

## Corpus Check
- 51 files · ~107,039 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1291 nodes · 3826 edges · 55 communities (50 shown, 5 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 281 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `570342f4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_config
- audit.py
- ExperimentConfig
- Any
- dataset.py
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- Candidate
- EventRecord
- capacity.py
- test_config_manifest.py
- manifest.py
- _tiny_payload_manifest
- FrozenInstance
- events.py
- ExecutionControls
- resample_synthetic_dataset
- _comparison_stats
- Projeto experimental reproduzível em notebook
- replay.py
- statistics.py
- ScenarioConfig
- Exact Invariants and Check Mapping
- emulator.py
- DatasetContractError
- DigitalModel
- config.py
- EventLatentLedger
- canonical_bytes
- test_a2_structural.py
- ComparisonStats
- metrics.py
- power_analysis_rhfs.py
- File Map
- DatasetPlan
- Any
- ExportedArtifacts
- test_notebook.py
- test_export_audit_table_uses_persisted_json_and_rejects_collision
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- FrozenServiceTime
- FrozenDataset
- AbortedStaging
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment
- test_metrics.py
- FrozenTruck
- _rollback_promotion
- YardSnapshot
- _validate_disruption_semantics

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 88 edges
2. `DatasetContractError` - 79 edges
3. `load_config()` - 77 edges
4. `ScenarioConfig` - 63 edges
5. `Candidate` - 52 edges
6. `_DaySimulation` - 50 edges
7. `FrozenInstance` - 49 edges
8. `EventRecord` - 49 edges
9. `YardSnapshot` - 46 edges
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

## Communities (55 total, 5 thin omitted)

### Community 0 - "load_config"
Cohesion: 0.15
Nodes (40): load_config(), Path, Load and validate a JSON configuration from a local path., export_analysis(), Publish H1 artifacts from one real, re-audited confirmatory bundle., evaluate_h1(), Evaluate H1 from one real, persisted, audited confirmatory RunBundle., canonical_confirmatory_rows() (+32 more)

### Community 1 - "audit.py"
Cohesion: 0.07
Nodes (61): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _observed_exclusion() (+53 more)

### Community 2 - "ExperimentConfig"
Cohesion: 0.09
Nodes (25): canonical_json(), config_as_dict(), config_hash(), ExperimentConfig, factorial_scenarios(), The complete, immutable protocol configuration., Require exact equality with every frozen field in confirmatory.json., Enumerate the complete factorial in N, m, b, regime order. (+17 more)

### Community 3 - "Any"
Cohesion: 0.16
Nodes (7): _dataset_canonical_bytes(), _latent_sha256(), Any, Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation., Hash canonical event-latent rows without importing the dataset layer., _thaw_dataset_value()

### Community 4 - "dataset.py"
Cohesion: 0.10
Nodes (42): _assert_finite_json(), _coalesced_rain_rows(), _controlled_event_hash(), _derive_controlled_instance(), _digest_value(), _disruption_payload_hash(), _expected_instance_ids(), _expected_scenario_factors() (+34 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.13
Nodes (8): _DaySimulation, Any, Count queued and in-flight trucks that still need unload capacity. A scale-in…, Apply the protocol's mandatory-priority and short-window rules., Return mean/p95 accumulated wait per truck and censored residual., _round_metric(), _Scheduled, _validate_regime()

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.13
Nodes (44): Execute validated frozen inputs; never generate or replace missing draws., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), make_policy(), Construct one of the frozen policy-panel implementations., build_validation_fixture(), candidate() (+36 more)

### Community 7 - "export.py"
Cohesion: 0.13
Nodes (35): _destination(), _ensure_targets_absent(), _export_analysis_core(), export_audit_table(), export_metrics(), _figure_improvement(), _figure_p95(), _figure_tradeoff() (+27 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.06
Nodes (32): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+24 more)

### Community 9 - "Candidate"
Cohesion: 0.08
Nodes (37): ABC, _activated_rules(), _build_justification(), Candidate, DispatchContext, DispatchPolicy, _exclusion(), feasible_candidates() (+29 more)

### Community 10 - "EventRecord"
Cohesion: 0.12
Nodes (32): Replay ``events`` from an optional detached physical snapshot., Create an empty projection with no applied events., replay_events(), Create the canonical empty yard state., EventRecord, Write events as one canonical JSON object per line., One ordered, validated event in the experiment trace., write_jsonl() (+24 more)

### Community 11 - "capacity.py"
Cohesion: 0.20
Nodes (16): CapacityGateError, CapacityReceipt, _evaluate(), inspect_capacity(), _now(), _os_probe(), Path, RuntimeError (+8 more)

### Community 12 - "test_config_manifest.py"
Cohesion: 0.12
Nodes (34): crn_digest(), Return the SHA-256 digest for one canonical CRN substream key., canonical_payload_schemas(), derive_controlled_projection(), Derive a frozen projection and return its two identity attestations., Return the exact public Parquet column contract., _assert_latent_rows_rejected(), parametrize (+26 more)

### Community 13 - "manifest.py"
Cohesion: 0.11
Nodes (30): _as_utc(), build_manifest(), create_run_directory(), _declared_distribution_names(), _detect_gpu(), _memory_inventory(), _memory_total_bytes(), _normalise_artifacts() (+22 more)

### Community 14 - "_tiny_payload_manifest"
Cohesion: 0.17
Nodes (16): canonical_event_latent_schema(), Return the exact envelope and closed payload variants for latents., Path, Apply a manifest tamper while preserving its outer FREEZE hash chain., Rewrite both provenance copies and their hashes to test semantic validation., Create only tiny arbitrary payload bytes for hash-chain boundary tests., Write the tiny canonical hash-chain fixture and return its manifest., _rewrite_manifest_root() (+8 more)

### Community 15 - "FrozenInstance"
Cohesion: 0.09
Nodes (33): _build_event_latents(), _build_instance(), _draw_uniform(), _generate_one_candidate(), _generate_until_rejection(), _instance_id(), _materialize_production_header(), _PayloadWriter (+25 more)

### Community 16 - "events.py"
Cohesion: 0.20
Nodes (10): _canonicalize(), _freeze(), Any, Path, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Read and validate every non-empty JSONL event line., Normalize JSON values into detached dict/list/scalar containers. (+2 more)

### Community 17 - "ExecutionControls"
Cohesion: 0.19
Nodes (10): _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., _controlled_projection_overlay_hash(), _controlled_projection_view_hash(), _controlled_rain_covered_latent_ids(), ExecutionControls (+2 more)

### Community 18 - "resample_synthetic_dataset"
Cohesion: 0.13
Nodes (29): _as_utc(), _build_manifest(), _create_staging_directory(), generate_synthetic_dataset(), _install_tiny_generation_fixture(), load_aborted_staging(), _persist_staging_abort(), _prepare_destination() (+21 more)

### Community 19 - "_comparison_stats"
Cohesion: 0.31
Nodes (10): _bootstrap(), _comparison_stats(), _finite_array(), _hodges_lehmann(), _iqr(), ndarray, _rank_biserial(), Return the paired Hodges--Lehmann estimator from Walsh averages. (+2 more)

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.23
Nodes (16): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., Return the canonical SHA-256 digest used in log state boundaries. (+8 more)

### Community 22 - "statistics.py"
Cohesion: 0.09
Nodes (45): _as_frame(), _canonical_protocol_error(), canonical_scenario_metadata(), _decimal_relative_improvements(), _derived_stratum(), _evaluate_h1_core(), _extract_pair_frame(), _first_column() (+37 more)

### Community 23 - "ScenarioConfig"
Cohesion: 0.07
Nodes (44): One point in the confirmatory factorial design., ScenarioConfig, Select the preregistered 20% pilot by stable scenario hash order., select_pilot_configurations(), DayResult, Canonical output identifying its frozen input, controls and policy., _atomic_write_json(), _atomic_write_text() (+36 more)

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "emulator.py"
Cohesion: 0.14
Nodes (11): DispatchBlocked, NoFeasibleCandidate, RuntimeError, Raised when hard constraints leave no admissible dispatch choice., Raised when ``fifo_strict`` must idle behind an ineligible head truck., Deterministic discrete-event emulator for the PequiFlux yard. The…, _TruckState, _RecordingPolicy (+3 more)

### Community 26 - "DatasetContractError"
Cohesion: 0.09
Nodes (55): _canonical_confirmatory_config(), DatasetContractError, _digest_bytes(), _finalize_freeze(), freeze_dataset(), _git_inventory(), _instance_headers_from_manifest(), _load_aborted_staging_internal() (+47 more)

### Community 27 - "DigitalModel"
Cohesion: 0.08
Nodes (19): DigitalModel, Any, Event-applied digital projection of the physical yard., Extract the fields that identify a recommendation's selection. Decision records…, Apply an ordered event stream to an isolated ``YardSnapshot``., Apply one event atomically, rejecting ordering and state violations., _finite_nonnegative(), _identifier() (+11 more)

### Community 28 - "config.py"
Cohesion: 0.20
Nodes (20): _as_finite_number(), _as_positive_integer_tuple(), _as_probability(), _as_text_tuple(), _as_tuple(), _canonical_nested_fields(), CapacityRequirements, crn_key() (+12 more)

### Community 29 - "EventLatentLedger"
Cohesion: 0.25
Nodes (4): EventLatentLedger, Explicit alias for the immutable event-latent payload., Immutable, keyed collection of all pre-realisation event candidates. Rows are…, test_controlled_projection_rejects_rain_entity_index_mismatch()

### Community 30 - "canonical_bytes"
Cohesion: 0.12
Nodes (25): canonical_bytes(), Serialize any JSON-compatible value in the canonical byte representation., materialize_face_validation_template(), _pending(), _project_root(), Any, Path, Verifiable human face-validation receipt gate. The receipt is an input… (+17 more)

### Community 31 - "test_a2_structural.py"
Cohesion: 0.34
Nodes (13): _build_bundle(), parametrize, Path, Regression checks for the explicit five-field A2 decision contract., _rewrite_first_decision(), test_audit_authenticates_decision_facts_against_events(), test_audit_rejects_input_provenance_tampering(), test_audit_rejects_invented_rule_or_overlapping_exclusion() (+5 more)

### Community 32 - "ComparisonStats"
Cohesion: 0.10
Nodes (4): ComparisonStats, H1Report, Statistics and gates for one stratum/comparator pair., Structured confirmatory result for both congestion strata.

### Community 33 - "metrics.py"
Cohesion: 0.21
Nodes (17): _compute(), compute_policy_day_metrics(), _freeze(), _json_object(), MetricRow, MetricsError, _number(), _plain() (+9 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.36
Nodes (11): Namespace, BootstrapResult, estimate_mde80(), load_pairs(), main(), parse_args(), ndarray, Path (+3 more)

### Community 35 - "File Map"
Cohesion: 0.18
Nodes (10): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 1: Configuração congelada e manifesto, Task 2: Eventos e projeção independente do modelo digital, Task 3: Restrições, políticas e emulador DES, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação (+2 more)

### Community 36 - "DatasetPlan"
Cohesion: 0.07
Nodes (36): DatasetPlan, FaceValidationError, GenerationPlanReceipt, GenerationRejectedError, plan_synthetic_dataset(), probe_generation_attempt(), Pure cardinality receipt; it never publishes or loads a dataset., Validate only lightweight generation headers against the pure plan. (+28 more)

### Community 37 - "Any"
Cohesion: 0.22
Nodes (4): _finite_nonnegative(), _identifier(), Any, Construct a candidate from a Task 2 ``Truck`` value.

### Community 39 - "test_notebook.py"
Cohesion: 0.25
Nodes (9): _cell_source(), Path, Contract checks for the central experiment notebook. The structural check…, The load profile must re-audit, analyse, and export persisted evidence., Load the notebook without requiring the optional notebook stack., _read_notebook_with_stdlib(), test_notebook_has_ordered_sections_and_validation_default(), test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() (+1 more)

### Community 41 - "Notebook de experimentos PequiFlux"
Cohesion: 0.13
Nodes (12): Âncora exploratória RHFS, Governança e estado das entregas, O que falta para as alegações pendentes, Semântica do operador e cobertura existente, Ambiente deliberado, Estado deste checkout, Execução limpa canônica, Fronteiras científicas (+4 more)

### Community 42 - "domain.py"
Cohesion: 0.17
Nodes (12): canonical_allowed_cargo_types(), _cargo_tuple(), _freeze_dataset_value(), _latent_number(), _latent_resource(), Mutable physical-domain values used by the independent digital model. The…, Detach a JSON-compatible value into immutable containers., Validate variant ranges and CRN/entity semantics without a live config. (+4 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (7): Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "FrozenServiceTime"
Cohesion: 0.22
Nodes (4): FrozenServiceTime, One pre-generated service duration and its CRN provenance., test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order(), test_frozen_service_rejects_forged_crn_draw_key()

### Community 45 - "FrozenDataset"
Cohesion: 0.20
Nodes (4): Strictly validate a complete production freeze., validate_frozen_dataset(), FrozenDataset, Immutable view of a validated, persisted frozen dataset.

### Community 46 - "AbortedStaging"
Cohesion: 0.25
Nodes (5): plan_explicit_resample(), Build an explicit one-attempt resample plan from retained STAGING state., AbortedStaging, Retained, hash-linked staging state after a fail-fast rejection., Ordinal of the next candidate to be attempted after rejection.

### Community 50 - "test_metrics.py"
Cohesion: 0.46
Nodes (7): _persisted_day(), parametrize, Hand-calculated metrics at the persisted-event boundary., test_active_service_is_censored_as_busy_time_not_queue_wait(), test_metrics_fail_closed_for_missing_input_or_impossible_observation(), test_persisted_metrics_reconcile_overlap_censoring_weighted_resources_and_queue_order(), test_window_and_critical_diagnostics_are_rebuilt_from_controls_and_queue_events()

### Community 51 - "FrozenTruck"
Cohesion: 0.22
Nodes (4): _dataset_digest(), FrozenTruck, Immutable truck record persisted in ``trucks.parquet``., test_loader_rejects_missing_frozen_service_parameters()

### Community 52 - "_rollback_promotion"
Cohesion: 0.40
Nodes (5): BaseException, Remove only directories proven to be ours after a failed promotion., _rollback_promotion(), test_rollback_accumulates_conflicts_after_removing_own_targets(), test_rollback_preserves_reappeared_target_and_chains_cause()

### Community 53 - "YardSnapshot"
Cohesion: 0.31
Nodes (3): Return a detached copy that cannot mutate the projection., A complete, JSON-friendly observation of the yard at one instant., YardSnapshot

### Community 54 - "_validate_disruption_semantics"
Cohesion: 0.25
Nodes (8): Validate one instance's complete disruption realization against the protocol., _validate_disruption_semantics(), _priority_fixture_rows(), test_disruption_return_time_must_remain_within_horizon(), test_disruption_semantics_follow_canonical_scenario_rules(), test_failure_return_time_must_equal_time_plus_duration(), test_priority_changes_require_one_shift_time_and_canonical_truck_order(), test_rain_pairs_must_not_overlap_or_be_adjacent()

## Knowledge Gaps
- **84 isolated node(s):** `pequiflux-experiment`, `graphify`, `graphify`, `Fontes normativas do projeto`, `Classificação correta do artefato visual` (+79 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ScenarioConfig` connect `ScenarioConfig` to `ComparisonStats`, `audit.py`, `ExperimentConfig`, `dataset.py`, `DatasetPlan`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `FrozenInstance`, `YardSnapshot`, `statistics.py`, `emulator.py`, `DatasetContractError`, `DigitalModel`, `config.py`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `ExperimentConfig` connect `ExperimentConfig` to `load_config`, `audit.py`, `ComparisonStats`, `dataset.py`, `DatasetPlan`, `capacity.py`, `manifest.py`, `AbortedStaging`, `FrozenInstance`, `resample_synthetic_dataset`, `_comparison_stats`, `_validate_disruption_semantics`, `ScenarioConfig`, `statistics.py`, `DatasetContractError`, `config.py`, `canonical_bytes`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `_DaySimulation` connect `_DaySimulation` to `test_dispatch_emulator.py`, `Candidate`, `EventRecord`, `FrozenInstance`, `ExecutionControls`, `YardSnapshot`, `ScenarioConfig`, `emulator.py`, `DigitalModel`, `EventLatentLedger`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Candidate` (e.g. with `DayResult` and `_DaySimulation`) actually correct?**
  _`Candidate` has 11 INFERRED edges - model-reasoned connections that need verification._