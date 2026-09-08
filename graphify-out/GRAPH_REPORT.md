# Graph Report - TCC  (2026-09-07)

## Corpus Check
- 71 files · ~120,444 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1402 nodes · 4103 edges · 66 communities (60 shown, 6 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 296 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `129084ee`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_digital_model_replay.py
- audit.py
- test_capacity.py
- FrozenTruck
- dataset.py
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- Candidate
- EventRecord
- config.py
- load_config
- manifest.py
- Any
- ExperimentConfig
- events.py
- ExecutionControls
- Path
- compute_policy_day_metrics
- Projeto experimental reproduzível em notebook
- replay.py
- statistics.py
- ScenarioConfig
- Exact Invariants and Check Mapping
- EventLatentLedger
- canonical_bytes
- Truck
- _comparison_stats
- .empty
- validate_face_validation_receipt
- export_audit_table
- ComparisonStats
- metrics.py
- power_analysis_rhfs.py
- File Map
- FrozenInstance
- _finite_nonnegative
- experimento-notebook/README.md
- test_notebook.py
- crn_digest
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- FrozenServiceTime
- test_operator_interventions.py
- .overall_pass
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment
- FrozenDataset
- Catálogo rastreável das entradas sintéticas
- YardSnapshot
- Baseline de fechamento — Tarefa 1
- 4. Dataset sintético: geração visível, persistência e congelamento
- 2. Protocolo congelado derivado do PDF
- 8. Inferência confirmatória de H1
- Escopo fechado das entradas sintéticas
- install/manifest.json
- kernel/manifest.json
- suite/manifest.json
- before-branch/manifest.json
- compileall/manifest.json
- create-environment/manifest.json
- ExportedArtifacts
- .ready_time

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 88 edges
2. `load_config()` - 79 edges
3. `DatasetContractError` - 79 edges
4. `ScenarioConfig` - 65 edges
5. `Candidate` - 58 edges
6. `_DaySimulation` - 55 edges
7. `EventRecord` - 54 edges
8. `YardSnapshot` - 52 edges
9. `FrozenInstance` - 50 edges
10. `EventLatentLedger` - 46 edges

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

## Communities (66 total, 6 thin omitted)

### Community 0 - "test_digital_model_replay.py"
Cohesion: 0.30
Nodes (18): _physics_contract(), _physics_disruption(), _physics_event(), _physics_model(), _physics_service(), parametrize, Behavioral contract for the independent digital-yard replay model., test_event_record_rejects_invalid_records() (+10 more)

### Community 1 - "audit.py"
Cohesion: 0.06
Nodes (71): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _observed_exclusion() (+63 more)

### Community 2 - "test_capacity.py"
Cohesion: 0.57
Nodes (7): _dataset(), _probe(), parametrize, test_capacity_blocks_resources_before_namespace(), test_capacity_expires_and_binds_phase(), test_capacity_plan_and_receipt_fail_closed(), test_capacity_rechecks_current_process()

### Community 3 - "FrozenTruck"
Cohesion: 0.18
Nodes (5): _dataset_digest(), _freeze_dataset_value(), FrozenTruck, Immutable truck record persisted in ``trucks.parquet``., Detach a JSON-compatible value into immutable containers.

### Community 4 - "dataset.py"
Cohesion: 0.07
Nodes (75): _canonical_confirmatory_config(), _coalesced_rain_rows(), _controlled_event_hash(), DatasetContractError, _derive_controlled_instance(), _digest_value(), _disruption_payload_hash(), _expected_instance_ids() (+67 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.13
Nodes (8): _DaySimulation, Any, Return mean/p95 accumulated wait per truck and censored residual., Enqueue only the events from the validated frozen projection., Count queued and in-flight trucks that still need unload capacity. A scale-in…, Reserve output space during unload; release it when scale-out starts., Apply the protocol's mandatory-priority and short-window rules., _Scheduled

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.12
Nodes (51): Execute validated frozen inputs; never generate or replace missing draws., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), make_policy(), Construct one of the frozen policy-panel implementations., build_validation_fixture(), candidate() (+43 more)

### Community 7 - "export.py"
Cohesion: 0.12
Nodes (37): BaseException, _destination(), _ensure_targets_absent(), _export_analysis_core(), export_metrics(), _figure_improvement(), _figure_p95(), _figure_tradeoff() (+29 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.11
Nodes (18): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+10 more)

### Community 9 - "Candidate"
Cohesion: 0.07
Nodes (46): ABC, _activated_rules(), _build_justification(), Candidate, DispatchContext, DispatchPolicy, _exclusion(), feasible_candidates() (+38 more)

### Community 10 - "EventRecord"
Cohesion: 0.17
Nodes (17): Replay ``events`` from an optional detached physical snapshot., replay_events(), The canonical state of one service resource (scale, hopper, or similar)., Resource, EventRecord, One ordered, validated event in the experiment trace., _decision_chain_prefix(), The DES emits four service phases for each truck. (+9 more)

### Community 11 - "config.py"
Cohesion: 0.11
Nodes (34): CapacityGateError, CapacityReceipt, _evaluate(), inspect_capacity(), _now(), _os_probe(), Path, RuntimeError (+26 more)

### Community 12 - "load_config"
Cohesion: 0.06
Nodes (86): load_config(), Path, Load and validate a JSON configuration from a local path., canonical_payload_schemas(), derive_controlled_projection(), _jsonl_bytes(), Derive a frozen projection and return its two identity attestations., Return the exact public Parquet column contract. (+78 more)

### Community 13 - "manifest.py"
Cohesion: 0.11
Nodes (30): _as_utc(), build_manifest(), create_run_directory(), _declared_distribution_names(), _detect_gpu(), _memory_inventory(), _memory_total_bytes(), _normalise_artifacts() (+22 more)

### Community 14 - "Any"
Cohesion: 0.17
Nodes (7): _dataset_canonical_bytes(), _latent_sha256(), Any, Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation., Hash canonical event-latent rows without importing the dataset layer., _thaw_dataset_value()

### Community 15 - "ExperimentConfig"
Cohesion: 0.08
Nodes (28): canonical_json(), config_as_dict(), config_hash(), ExperimentConfig, factorial_scenarios(), The complete, immutable protocol configuration., Require exact equality with every frozen field in confirmatory.json., Enumerate the complete factorial in N, m, b, regime order. (+20 more)

### Community 16 - "events.py"
Cohesion: 0.13
Nodes (20): _canonicalize(), _freeze(), Any, Path, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Write events as one canonical JSON object per line., Read and validate every non-empty JSONL event line. (+12 more)

### Community 17 - "ExecutionControls"
Cohesion: 0.19
Nodes (10): _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., _controlled_projection_overlay_hash(), _controlled_projection_view_hash(), _controlled_rain_covered_latent_ids(), ExecutionControls (+2 more)

### Community 18 - "Path"
Cohesion: 0.14
Nodes (32): _as_utc(), _build_manifest(), _create_staging_directory(), generate_synthetic_dataset(), _git_inventory(), _install_tiny_generation_fixture(), load_aborted_staging(), _persist_staging_abort() (+24 more)

### Community 19 - "compute_policy_day_metrics"
Cohesion: 0.35
Nodes (10): compute_policy_day_metrics(), Path, Read one closed JSONL log and derive its complete numeric measurements. Input…, _persisted_day(), parametrize, Hand-calculated metrics at the persisted-event boundary., test_active_service_is_censored_as_busy_time_not_queue_wait(), test_metrics_fail_closed_for_missing_input_or_impossible_observation() (+2 more)

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.24
Nodes (14): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., _read_raw_lines() (+6 more)

### Community 22 - "statistics.py"
Cohesion: 0.09
Nodes (45): _as_frame(), _canonical_protocol_error(), canonical_scenario_metadata(), _decimal_relative_improvements(), _derived_stratum(), _evaluate_h1_core(), _extract_pair_frame(), _first_column() (+37 more)

### Community 23 - "ScenarioConfig"
Cohesion: 0.06
Nodes (57): One point in the confirmatory factorial design., ScenarioConfig, _build_event_latents(), _build_instance(), _draw_uniform(), _instance_id(), _priority_shift_eligible_count(), Return detached, lightweight headers in canonical plan order. (+49 more)

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "EventLatentLedger"
Cohesion: 0.06
Nodes (22): DispatchBlocked, NoFeasibleCandidate, RuntimeError, Raised when hard constraints leave no admissible dispatch choice., Raised when ``fifo_strict`` must idle behind an ineligible head truck., EventLatentLedger, Explicit alias for the immutable event-latent payload., Immutable, keyed collection of all pre-realisation event candidates. Rows are… (+14 more)

### Community 26 - "canonical_bytes"
Cohesion: 0.11
Nodes (38): canonical_bytes(), Serialize any JSON-compatible value in the canonical byte representation., _assert_finite_json(), canonical_event_latent_schema(), _digest_bytes(), _finalize_freeze(), Write canonical checksums/manifest and return their linked digests., Reject JSON numbers that are non-finite at the load boundary. (+30 more)

### Community 27 - "Truck"
Cohesion: 0.14
Nodes (8): _finite_nonnegative(), _identifier(), The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs., Compatibility alias for callers that used the earlier name., Alias for ``clock`` at event-oriented boundaries., Truck, setter

### Community 28 - "_comparison_stats"
Cohesion: 0.31
Nodes (10): _bootstrap(), _comparison_stats(), _finite_array(), _hodges_lehmann(), _iqr(), ndarray, _rank_biserial(), Return the paired Hodges--Lehmann estimator from Walsh averages. (+2 more)

### Community 29 - ".empty"
Cohesion: 0.25
Nodes (7): Create an empty projection with no applied events., Create the canonical empty yard state., test_dispatch_blocked_is_evidence_without_mutating_digital_state(), test_event_payload_is_recursively_immutable_and_to_dict_is_detached(), test_model_rejects_sequence_regression_and_impossible_transition(), test_public_empty_and_canonical_snapshot_contract(), test_sequences_must_start_at_one_and_be_contiguous()

### Community 30 - "validate_face_validation_receipt"
Cohesion: 0.22
Nodes (15): materialize_face_validation_template(), _pending(), _project_root(), Any, Path, Verifiable human face-validation receipt gate. The receipt is an input…, Write the empty, versioned receipt template without human values., Validate a receipt against the frozen config, PDF and rubric bytes. (+7 more)

### Community 31 - "export_audit_table"
Cohesion: 0.40
Nodes (5): export_audit_table(), Publish one CSV row from a persisted ``audit.json``. The JSON file is the sole…, The audit table must come from the persisted audit boundary., test_export_audit_table_rejects_claimed_namespace_mismatch(), test_export_audit_table_uses_persisted_json_and_rejects_collision()

### Community 32 - "ComparisonStats"
Cohesion: 0.10
Nodes (4): ComparisonStats, H1Report, Statistics and gates for one stratum/comparator pair., Structured confirmatory result for both congestion strata.

### Community 33 - "metrics.py"
Cohesion: 0.24
Nodes (14): _compute(), _freeze(), _json_object(), MetricRow, MetricsError, _number(), _plain(), Any (+6 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.36
Nodes (11): Namespace, BootstrapResult, estimate_mde80(), load_pairs(), main(), parse_args(), ndarray, Path (+3 more)

### Community 35 - "File Map"
Cohesion: 0.18
Nodes (10): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 1: Configuração congelada e manifesto, Task 2: Eventos e projeção independente do modelo digital, Task 3: Restrições, políticas e emulador DES, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação (+2 more)

### Community 36 - "FrozenInstance"
Cohesion: 0.05
Nodes (49): DatasetPlan, FaceValidationError, _generate_one_candidate(), _generate_until_rejection(), GenerationPlanReceipt, GenerationRejectedError, _materialize_production_header(), _PayloadWriter (+41 more)

### Community 37 - "_finite_nonnegative"
Cohesion: 0.32
Nodes (3): _finite_nonnegative(), _identifier(), Construct a candidate from a Task 2 ``Truck`` value.

### Community 38 - "experimento-notebook/README.md"
Cohesion: 0.23
Nodes (4): Âncora exploratória RHFS, Governança e estado das entregas, O que falta para as alegações pendentes, Semântica do operador e cobertura existente

### Community 39 - "test_notebook.py"
Cohesion: 0.25
Nodes (9): _cell_source(), Path, Contract checks for the central experiment notebook. The structural check…, The load profile must re-audit, analyse, and export persisted evidence., Load the notebook without requiring the optional notebook stack., _read_notebook_with_stdlib(), test_notebook_has_ordered_sections_and_validation_default(), test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() (+1 more)

### Community 40 - "crn_digest"
Cohesion: 0.50
Nodes (4): crn_digest(), crn_seed(), Return the SHA-256 digest for one canonical CRN substream key., Map a CRN key to a stable non-negative integer seed.

### Community 41 - "Notebook de experimentos PequiFlux"
Cohesion: 0.22
Nodes (9): Ambiente deliberado, Escopo dos dados sintéticos, Estado deste checkout, Execução limpa canônica, Fronteiras científicas, Layout de artefatos, Notebook de experimentos PequiFlux, Perfis (+1 more)

### Community 42 - "domain.py"
Cohesion: 0.21
Nodes (10): canonical_allowed_cargo_types(), _cargo_tuple(), _latent_number(), _latent_resource(), Mutable physical-domain values used by the independent digital model. The…, Validate variant ranges and CRN/entity semantics without a live config., Return the immutable protocol matrix for a physical resource. Hopper 1 is…, Validate scenario identity, cardinality and resource eligibility. (+2 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (8): Ambiente experimental, Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação do texto, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "FrozenServiceTime"
Cohesion: 0.14
Nodes (7): FrozenResource, FrozenServiceTime, Immutable resource record used by a frozen instance., One pre-generated service duration and its CRN provenance., test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order(), test_frozen_instance_service_order_keeps_truck_identity(), test_frozen_service_rejects_forged_crn_draw_key()

### Community 45 - "test_operator_interventions.py"
Cohesion: 0.50
Nodes (3): parametrize, Synthetic operator responses exercise real DES commands without human claims., test_invalid_synthetic_response_fails_before_any_service_starts()

### Community 50 - "FrozenDataset"
Cohesion: 0.17
Nodes (6): freeze_dataset(), Strictly validate a complete production freeze., Finalize a directory containing the six payloads and return its freeze., validate_frozen_dataset(), FrozenDataset, Immutable view of a validated, persisted frozen dataset.

### Community 52 - "Catálogo rastreável das entradas sintéticas"
Cohesion: 0.22
Nodes (9): Cardinalidades previstas, sem geração, Catálogo rastreável das entradas sintéticas, Chegadas, tempos e atributos, Controles, identificação e execução, Escala, relógio, recursos e fluxo, Fontes e natureza do suporte, Lacunas de evidência que permanecem, Pareamento CRN e pacote de entrada (+1 more)

### Community 53 - "YardSnapshot"
Cohesion: 0.15
Nodes (12): DigitalModel, _physical_number(), _PhysicalReplay, Any, Event-applied digital projection of the physical yard., Apply an ordered event stream to an isolated ``YardSnapshot``., Return a detached copy that cannot mutate the projection., Apply one event atomically, rejecting ordering and state violations. (+4 more)

### Community 54 - "Baseline de fechamento — Tarefa 1"
Cohesion: 0.29
Nodes (7): Baseline de fechamento — Tarefa 1, Comandos e isolamento, Estado anterior à branch, Evidência preservada, Execução atual, Interpretador e instalação limpa, Kernel

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

### Community 59 - "install/manifest.json"
Cohesion: 0.33
Nodes (5): cwd, inputs, name, schema_version, steps

### Community 60 - "kernel/manifest.json"
Cohesion: 0.33
Nodes (5): cwd, inputs, name, schema_version, steps

### Community 61 - "suite/manifest.json"
Cohesion: 0.33
Nodes (5): cwd, inputs, name, schema_version, steps

### Community 62 - "before-branch/manifest.json"
Cohesion: 0.40
Nodes (4): cwd, name, schema_version, steps

### Community 63 - "compileall/manifest.json"
Cohesion: 0.40
Nodes (4): cwd, name, schema_version, steps

### Community 64 - "create-environment/manifest.json"
Cohesion: 0.40
Nodes (4): cwd, name, schema_version, steps

## Knowledge Gaps
- **130 isolated node(s):** `schema_version`, `name`, `cwd`, `steps`, `schema_version` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ScenarioConfig` connect `ScenarioConfig` to `ComparisonStats`, `audit.py`, `test_digital_model_replay.py`, `dataset.py`, `FrozenInstance`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `config.py`, `ExperimentConfig`, `events.py`, `YardSnapshot`, `statistics.py`, `EventLatentLedger`, `.empty`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `ExperimentConfig` connect `ExperimentConfig` to `ComparisonStats`, `audit.py`, `dataset.py`, `FrozenInstance`, `config.py`, `load_config`, `manifest.py`, `Path`, `statistics.py`, `ScenarioConfig`, `_comparison_stats`, `validate_face_validation_receipt`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `Truck` connect `Truck` to `test_digital_model_replay.py`, `_DaySimulation`, `domain.py`, `EventRecord`, `Any`, `events.py`, `YardSnapshot`, `EventLatentLedger`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Candidate` (e.g. with `DayResult` and `_DaySimulation`) actually correct?**
  _`Candidate` has 13 INFERRED edges - model-reasoned connections that need verification._