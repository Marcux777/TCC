# Graph Report - TCC  (2026-09-07)

## Corpus Check
- 55 files · ~112,830 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1327 nodes · 3913 edges · 61 communities (58 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 291 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ac14e738`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_config
- audit.py
- validate_confirmatory_config
- Any
- DatasetContractError
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- Candidate
- EventRecord
- capacity.py
- test_config_manifest.py
- manifest.py
- FrozenInstance
- ScenarioConfig
- digital_model.py
- ExecutionControls
- Path
- _validate_resample_provenance
- Projeto experimental reproduzível em notebook
- replay.py
- statistics.py
- experiment.py
- Exact Invariants and Check Mapping
- emulator.py
- dataset.py
- Truck
- config.py
- ExperimentConfig
- validate_face_validation_receipt
- canonical_bytes
- ComparisonStats
- metrics.py
- power_analysis_rhfs.py
- File Map
- DatasetPlan
- _finite_nonnegative
- synthetic-data-scope.md
- test_notebook.py
- export_audit_table
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- RunBundle
- FrozenDataset
- AbortedStaging
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment
- test_metrics.py
- FrozenTruck
- Catálogo rastreável das entradas sintéticas
- YardSnapshot
- _RecordingPolicy
- 4. Dataset sintético: geração visível, persistência e congelamento
- 2. Protocolo congelado derivado do PDF
- 8. Inferência confirmatória de H1
- Escopo fechado das entradas sintéticas
- _expected_scenario_factors
- 9. A1 adversarial e A2 independente

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 88 edges
2. `DatasetContractError` - 79 edges
3. `load_config()` - 77 edges
4. `ScenarioConfig` - 63 edges
5. `Candidate` - 57 edges
6. `_DaySimulation` - 53 edges
7. `FrozenInstance` - 50 edges
8. `EventRecord` - 49 edges
9. `YardSnapshot` - 46 edges
10. `EventLatentLedger` - 44 edges

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

## Communities (61 total, 3 thin omitted)

### Community 0 - "load_config"
Cohesion: 0.15
Nodes (40): load_config(), Path, Load and validate a JSON configuration from a local path., export_analysis(), Publish H1 artifacts from one real, re-audited confirmatory bundle., evaluate_h1(), Evaluate H1 from one real, persisted, audited confirmatory RunBundle., canonical_confirmatory_rows() (+32 more)

### Community 1 - "audit.py"
Cohesion: 0.06
Nodes (73): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _observed_exclusion() (+65 more)

### Community 2 - "validate_confirmatory_config"
Cohesion: 0.30
Nodes (13): factorial_scenarios(), Require exact equality with every frozen field in confirmatory.json., Enumerate the complete factorial in N, m, b, regime order., validate_confirmatory_config(), plan_policy_days(), Plan exact ordered cells; never execute DES or infer a reduced campaign., _dataset(), _probe() (+5 more)

### Community 3 - "Any"
Cohesion: 0.10
Nodes (10): FrozenResource, FrozenServiceTime, Any, Immutable resource record used by a frozen instance., One pre-generated service duration and its CRN provenance., Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation., test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order() (+2 more)

### Community 4 - "DatasetContractError"
Cohesion: 0.10
Nodes (43): _assert_finite_json(), _canonical_confirmatory_config(), _coalesced_rain_rows(), DatasetContractError, _derive_controlled_instance(), _disruption_payload_hash(), _expected_instance_ids(), freeze_dataset() (+35 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.13
Nodes (5): _DaySimulation, Any, Return mean/p95 accumulated wait per truck and censored residual., Count queued and in-flight trucks that still need unload capacity. A scale-in…, Apply the protocol's mandatory-priority and short-window rules.

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.13
Nodes (46): Execute validated frozen inputs; never generate or replace missing draws., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), make_policy(), Construct one of the frozen policy-panel implementations., build_validation_fixture(), candidate() (+38 more)

### Community 7 - "export.py"
Cohesion: 0.10
Nodes (39): BaseException, _destination(), _ensure_targets_absent(), _export_analysis_core(), export_metrics(), ExportedArtifacts, _figure_improvement(), _figure_p95() (+31 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.13
Nodes (15): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+7 more)

### Community 9 - "Candidate"
Cohesion: 0.08
Nodes (38): _activated_rules(), _build_justification(), Candidate, DispatchContext, _exclusion(), feasible_candidates(), _fifo_reference(), Any (+30 more)

### Community 10 - "EventRecord"
Cohesion: 0.16
Nodes (23): Replay ``events`` from an optional detached physical snapshot., Create an empty projection with no applied events., Apply one event atomically, rejecting ordering and state violations., replay_events(), Create the canonical empty yard state., EventRecord, One ordered, validated event in the experiment trace., _arrival_event() (+15 more)

### Community 11 - "capacity.py"
Cohesion: 0.16
Nodes (19): CapacityGateError, CapacityReceipt, _evaluate(), inspect_capacity(), _now(), _os_probe(), Path, RuntimeError (+11 more)

### Community 12 - "test_config_manifest.py"
Cohesion: 0.07
Nodes (52): canonical_payload_schemas(), derive_controlled_projection(), _jsonl_bytes(), load_event_latents(), Load and validate the canonical ``event_latents.jsonl`` payload., Derive a frozen projection and return its two identity attestations., Return the exact public Parquet column contract., EventLatentLedger (+44 more)

### Community 13 - "manifest.py"
Cohesion: 0.11
Nodes (29): Frozen configuration and run-manifest primitives for PequiFlux experiments., _as_utc(), build_manifest(), create_run_directory(), _declared_distribution_names(), _detect_gpu(), _memory_inventory(), _memory_total_bytes() (+21 more)

### Community 14 - "FrozenInstance"
Cohesion: 0.15
Nodes (18): _generate_one_candidate(), _generate_until_rejection(), _materialize_production_header(), _PayloadWriter, Collect deterministic rows for one complete production freeze., Materialize one complete immutable instance into the payload writer., Validate one fully generated candidate before any payload write. The priority-…, Private seam delegating to the canonical validator. Tests may monkeypatch this… (+10 more)

### Community 15 - "ScenarioConfig"
Cohesion: 0.09
Nodes (25): crn_digest(), crn_seed(), One point in the confirmatory factorial design., Return the SHA-256 digest for one canonical CRN substream key., Map a CRN key to a stable non-negative integer seed., ScenarioConfig, _build_event_latents(), _build_instance() (+17 more)

### Community 16 - "digital_model.py"
Cohesion: 0.13
Nodes (18): Event-applied digital projection of the physical yard., _canonicalize(), _freeze(), Any, Path, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Write events as one canonical JSON object per line. (+10 more)

### Community 17 - "ExecutionControls"
Cohesion: 0.19
Nodes (10): _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., _controlled_projection_overlay_hash(), _controlled_projection_view_hash(), _controlled_rain_covered_latent_ids(), ExecutionControls (+2 more)

### Community 18 - "Path"
Cohesion: 0.14
Nodes (32): _as_utc(), _build_manifest(), _create_staging_directory(), generate_synthetic_dataset(), _git_inventory(), _install_tiny_generation_fixture(), load_aborted_staging(), _persist_staging_abort() (+24 more)

### Community 19 - "_validate_resample_provenance"
Cohesion: 0.16
Nodes (21): _instance_headers_from_manifest(), _load_aborted_staging_internal(), load_freeze_receipt(), _load_json(), plan_synthetic_dataset(), Validate provenance reference, content bytes, and header reconciliation. This…, Load one retained STAGING root while recursively tracking its source chain., Read a canonical FREEZE/manifest/header receipt with an explicit pin. (+13 more)

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.27
Nodes (14): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., _read_raw_lines() (+6 more)

### Community 22 - "statistics.py"
Cohesion: 0.08
Nodes (51): _as_frame(), _bootstrap(), _comparison_stats(), _decimal_relative_improvements(), _derived_stratum(), _evaluate_h1_core(), _extract_pair_frame(), _finite_array() (+43 more)

### Community 23 - "experiment.py"
Cohesion: 0.15
Nodes (32): _atomic_write_json(), _atomic_write_text(), _canonical_json(), _csv_text(), _decision_fields(), _derived_scenario_metadata(), _git_metadata(), _input_provenance() (+24 more)

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "emulator.py"
Cohesion: 0.09
Nodes (23): ABC, DispatchBlocked, DispatchPolicy, NoFeasibleCandidate, RuntimeError, Feasibility and recommendation boundaries for the yard dispatcher. The…, Raised when hard constraints leave no admissible dispatch choice., Raised when ``fifo_strict`` must idle behind an ineligible head truck. (+15 more)

### Community 26 - "dataset.py"
Cohesion: 0.09
Nodes (43): canonical_event_latent_schema(), _controlled_event_hash(), _digest_bytes(), _digest_value(), FaceValidationError, _finalize_freeze(), _instance_event_latent_hashes(), probe_generation_attempt() (+35 more)

### Community 27 - "Truck"
Cohesion: 0.09
Nodes (18): _cargo_tuple(), _finite_nonnegative(), _identifier(), The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs., Compatibility alias for callers that used the earlier name., The canonical state of one service resource (scale, hopper, or similar)., Alias for ``clock`` at event-oriented boundaries. (+10 more)

### Community 28 - "config.py"
Cohesion: 0.21
Nodes (20): _as_finite_number(), _as_positive_integer_tuple(), _as_probability(), _as_text_tuple(), _as_tuple(), canonical_json(), _canonical_nested_fields(), config_as_dict() (+12 more)

### Community 29 - "ExperimentConfig"
Cohesion: 0.12
Nodes (8): ExperimentConfig, The complete, immutable protocol configuration., Enforce the exact 72 x 50 x 5 matrix at the execution boundary., _validate_confirmatory_matrix(), _canonical_protocol_error(), canonical_scenario_metadata(), Return a diagnostic when ``config`` is not the frozen H1 protocol., Return the immutable, protocol-derived metadata for all 72 scenarios. The…

### Community 30 - "validate_face_validation_receipt"
Cohesion: 0.16
Nodes (19): _validate_approved_face(), FaceValidationReport, materialize_face_validation_template(), _pending(), _project_root(), Any, Path, Verifiable human face-validation receipt gate. The receipt is an input… (+11 more)

### Community 31 - "canonical_bytes"
Cohesion: 0.20
Nodes (11): canonical_bytes(), config_hash(), Serialize any JSON-compatible value in the canonical byte representation., Return the SHA-256 digest of the canonical UTF-8 configuration JSON., _hash(), PolicyDayPlan, Pure phase plans and workload identity for frozen scientific inputs., approved_face() (+3 more)

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
Cohesion: 0.06
Nodes (25): DatasetPlan, GenerationPlanReceipt, GenerationRejectedError, _instance_id(), plan_explicit_resample(), Predicted truck rows across instances, not observed generation output., Predicted potential-service rows, shared by all policies per instance., Return detached, lightweight headers in canonical plan order. (+17 more)

### Community 37 - "_finite_nonnegative"
Cohesion: 0.32
Nodes (3): _finite_nonnegative(), _identifier(), Construct a candidate from a Task 2 ``Truck`` value.

### Community 38 - "synthetic-data-scope.md"
Cohesion: 0.27
Nodes (4): Âncora exploratória RHFS, Governança e estado das entregas, O que falta para as alegações pendentes, Semântica do operador e cobertura existente

### Community 39 - "test_notebook.py"
Cohesion: 0.25
Nodes (9): _cell_source(), Path, Contract checks for the central experiment notebook. The structural check…, The load profile must re-audit, analyse, and export persisted evidence., Load the notebook without requiring the optional notebook stack., _read_notebook_with_stdlib(), test_notebook_has_ordered_sections_and_validation_default(), test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() (+1 more)

### Community 40 - "export_audit_table"
Cohesion: 0.40
Nodes (5): export_audit_table(), Publish one CSV row from a persisted ``audit.json``. The JSON file is the sole…, The audit table must come from the persisted audit boundary., test_export_audit_table_rejects_claimed_namespace_mismatch(), test_export_audit_table_uses_persisted_json_and_rejects_collision()

### Community 41 - "Notebook de experimentos PequiFlux"
Cohesion: 0.22
Nodes (9): Ambiente deliberado, Escopo dos dados sintéticos, Estado deste checkout, Execução limpa canônica, Fronteiras científicas, Layout de artefatos, Notebook de experimentos PequiFlux, Perfis (+1 more)

### Community 42 - "domain.py"
Cohesion: 0.20
Nodes (11): _dataset_canonical_bytes(), _latent_number(), _latent_resource(), _latent_sha256(), Mutable physical-domain values used by the independent digital model. The…, Hash canonical event-latent rows without importing the dataset layer., Validate variant ranges and CRN/entity semantics without a live config., Validate scenario identity, cardinality and resource eligibility. (+3 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (7): Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "RunBundle"
Cohesion: 0.29
Nodes (4): _mapping_copy(), Path, Immutable handles and parsed rows for one persisted matrix run., RunBundle

### Community 45 - "FrozenDataset"
Cohesion: 0.17
Nodes (6): _load_frozen_dataset(), Strictly validate a complete production freeze., Load a complete, canonical production freeze with an explicit pin., validate_frozen_dataset(), FrozenDataset, Immutable view of a validated, persisted frozen dataset.

### Community 46 - "AbortedStaging"
Cohesion: 0.22
Nodes (6): _provenance_payload(), Copy accepted source rows into a fresh writer without loading instances., _writer_from_aborted_staging(), AbortedStaging, Retained, hash-linked staging state after a fail-fast rejection., Ordinal of the next candidate to be attempted after rejection.

### Community 50 - "test_metrics.py"
Cohesion: 0.46
Nodes (7): _persisted_day(), parametrize, Hand-calculated metrics at the persisted-event boundary., test_active_service_is_censored_as_busy_time_not_queue_wait(), test_metrics_fail_closed_for_missing_input_or_impossible_observation(), test_persisted_metrics_reconcile_overlap_censoring_weighted_resources_and_queue_order(), test_window_and_critical_diagnostics_are_rebuilt_from_controls_and_queue_events()

### Community 51 - "FrozenTruck"
Cohesion: 0.17
Nodes (5): _dataset_digest(), _freeze_dataset_value(), FrozenTruck, Immutable truck record persisted in ``trucks.parquet``., Detach a JSON-compatible value into immutable containers.

### Community 52 - "Catálogo rastreável das entradas sintéticas"
Cohesion: 0.22
Nodes (9): Cardinalidades previstas, sem geração, Catálogo rastreável das entradas sintéticas, Chegadas, tempos e atributos, Controles, identificação e execução, Escala, relógio, recursos e fluxo, Fontes e natureza do suporte, Lacunas de evidência que permanecem, Pareamento CRN e pacote de entrada (+1 more)

### Community 53 - "YardSnapshot"
Cohesion: 0.21
Nodes (8): DigitalModel, Any, Extract the fields that identify a recommendation's selection. Decision records…, Apply an ordered event stream to an isolated ``YardSnapshot``., Return a detached copy that cannot mutate the projection., A complete, JSON-friendly observation of the yard at one instant., YardSnapshot, test_existing_truck_arrival_validates_priority_before_assignment()

### Community 54 - "_RecordingPolicy"
Cohesion: 0.22
Nodes (3): _RecordingPolicy, _ScaleOutFirstPolicy, test_lexicographic_h_uses_pressure_wait_reorder_affinity_then_stage_entry()

### Community 55 - "4. Dataset sintético: geração visível, persistência e congelamento"
Cohesion: 0.33
Nodes (6): 4.1 Contrato da geração, 4.2 Esquema mínimo e arquivos, 4.3 Common random numbers (CRN), 4. Dataset sintético: geração visível, persistência e congelamento, Emenda de governança sem retry, Integridade e hash sem ciclo

### Community 56 - "2. Protocolo congelado derivado do PDF"
Cohesion: 0.50
Nodes (4): 2.1 Fatorial, sementes e estratos, 2.2 Horizonte, chegadas, serviços e perturbações, 2.3 Painel de políticas, 2. Protocolo congelado derivado do PDF

### Community 57 - "8. Inferência confirmatória de H1"
Cohesion: 0.50
Nodes (4): 8.1 Unidade, efeito e comparadores, 8.2 IUT com guarda de throughput, 8.3 Holm e linguagem permitida, 8. Inferência confirmatória de H1

### Community 58 - "Escopo fechado das entradas sintéticas"
Cohesion: 0.50
Nodes (4): Escopo fechado das entradas sintéticas, Fronteiras do modelo e verificações, Persistência e CRN, Unidade e dimensão previstas

### Community 59 - "_expected_scenario_factors"
Cohesion: 0.50
Nodes (4): _expected_scenario_factors(), Return the fixed confirmatory factorial in its protocol order., _expected_scenario_factors(), Return the canonical confirmatory factorial in protocol order.

### Community 60 - "9. A1 adversarial e A2 independente"
Cohesion: 0.67
Nodes (3): 9.1 A1 adversarial, 9.2 A2: estrutura, amostra, rubrica e kappa, 9. A1 adversarial e A2 independente

## Knowledge Gaps
- **96 isolated node(s):** `pequiflux-experiment`, `graphify`, `graphify`, `Fontes normativas do projeto`, `Classificação correta do artefato visual` (+91 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ScenarioConfig` connect `ScenarioConfig` to `audit.py`, `validate_confirmatory_config`, `DatasetContractError`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `manifest.py`, `FrozenInstance`, `digital_model.py`, `statistics.py`, `experiment.py`, `emulator.py`, `dataset.py`, `config.py`, `ExperimentConfig`, `ComparisonStats`, `DatasetPlan`, `RunBundle`, `YardSnapshot`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `ExperimentConfig` connect `ExperimentConfig` to `load_config`, `audit.py`, `validate_confirmatory_config`, `DatasetContractError`, `capacity.py`, `manifest.py`, `FrozenInstance`, `ScenarioConfig`, `Path`, `_validate_resample_provenance`, `statistics.py`, `experiment.py`, `dataset.py`, `config.py`, `validate_face_validation_receipt`, `canonical_bytes`, `ComparisonStats`, `DatasetPlan`, `RunBundle`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `_DaySimulation` connect `_DaySimulation` to `test_dispatch_emulator.py`, `Candidate`, `EventRecord`, `test_config_manifest.py`, `FrozenInstance`, `ScenarioConfig`, `ExecutionControls`, `YardSnapshot`, `emulator.py`, `Truck`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Candidate` (e.g. with `DayResult` and `_DaySimulation`) actually correct?**
  _`Candidate` has 13 INFERRED edges - model-reasoned connections that need verification._