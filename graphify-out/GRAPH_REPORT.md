# Graph Report - TCC  (2026-09-15)

## Corpus Check
- 74 files · ~127,899 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1434 nodes · 4185 edges · 73 communities (68 shown, 5 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 304 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d2ead468`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_digital_model_replay.py
- recommend
- audit.py
- FrozenTruck
- Any
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- _exclusion
- EventRecord
- config.py
- load_config
- manifest.py
- Any
- config_hash
- .from_snapshot
- RunBundle
- dataset.py
- events.py
- Projeto experimental reproduzível em notebook
- replay.py
- statistics.py
- experiment.py
- Exact Invariants and Check Mapping
- emulator.py
- canonical_file_hash
- Truck
- _comparison_stats
- load_aborted_staging
- validate_face_validation_receipt
- export_audit_table
- ComparisonStats
- ExecutionControls
- power_analysis_rhfs.py
- File Map
- DatasetPlan
- _finite_nonnegative
- experimento-notebook/README.md
- test_notebook.py
- ScenarioConfig
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- FrozenServiceTime
- Template e Guia de Submissão: Revista Production (ABEPRO / SciELO)
- .overall_pass
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment
- FrozenDataset
- DatasetContractError
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
- FrozenInstance
- _validate_scenario_rows
- Candidate
- ExperimentConfig
- EventLatentLedger
- Contrato das métricas canônicas
- Academic Paper: Logistics 5.0 in Agro-Industrial Yard Dispatching
- _rollback_promotion

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 88 edges
2. `load_config()` - 79 edges
3. `DatasetContractError` - 79 edges
4. `ScenarioConfig` - 65 edges
5. `Candidate` - 58 edges
6. `_DaySimulation` - 54 edges
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
- `AuditError` --uses--> `ExecutionControls`  [INFERRED]
  experimento-notebook/src/pequiflux_experiment/audit.py → experimento-notebook/src/pequiflux_experiment/domain.py
- `AuditError` --uses--> `EventRecord`  [INFERRED]
  experimento-notebook/src/pequiflux_experiment/audit.py → experimento-notebook/src/pequiflux_experiment/events.py

## Import Cycles
- None detected.

## Communities (73 total, 5 thin omitted)

### Community 0 - "test_digital_model_replay.py"
Cohesion: 0.30
Nodes (18): _physics_contract(), _physics_disruption(), _physics_event(), _physics_model(), _physics_service(), parametrize, Behavioral contract for the independent digital-yard replay model., test_event_record_rejects_invalid_records() (+10 more)

### Community 1 - "recommend"
Cohesion: 0.28
Nodes (16): Return one policy recommendation after hard-constraint filtering., recommend(), _build_bundle(), parametrize, Path, Regression checks for the explicit five-field A2 decision contract., _rewrite_first_decision(), test_audit_authenticates_decision_facts_against_events() (+8 more)

### Community 2 - "audit.py"
Cohesion: 0.07
Nodes (63): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _metric_interval_union() (+55 more)

### Community 3 - "FrozenTruck"
Cohesion: 0.18
Nodes (5): _dataset_digest(), _freeze_dataset_value(), FrozenTruck, Immutable truck record persisted in ``trucks.parquet``., Detach a JSON-compatible value into immutable containers.

### Community 4 - "Any"
Cohesion: 0.11
Nodes (31): _assert_finite_json(), _coalesced_rain_rows(), _controlled_event_hash(), _derive_controlled_instance(), _digest_value(), _disruption_payload_hash(), _expected_instance_ids(), _manifest_seeds() (+23 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.12
Nodes (8): _DaySimulation, Any, Load arrivals and potential service durations without generating values., Enqueue only the events from the validated frozen projection., Count queued and in-flight trucks that still need unload capacity. A scale-in…, Reserve output space during unload; release it when scale-out starts., Apply the protocol's mandatory-priority and short-window rules., _Scheduled

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.09
Nodes (63): Execute validated frozen inputs; never generate or replace missing draws., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), Path, Write events as one canonical JSON object per line., Read and validate every non-empty JSONL event line., read_jsonl() (+55 more)

### Community 7 - "export.py"
Cohesion: 0.12
Nodes (34): _destination(), _ensure_targets_absent(), _export_analysis_core(), export_metrics(), ExportedArtifacts, _figure_improvement(), _figure_p95(), _figure_tradeoff() (+26 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.11
Nodes (18): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+10 more)

### Community 9 - "_exclusion"
Cohesion: 0.18
Nodes (6): _exclusion(), _fifo_reference(), Any, Return a stable cause and supplementary human explanation., Order admissible candidates solely by ``(stage_entry_time, truck_id)``. Yard…, Return a deterministic key; lower keys are selected.

### Community 10 - "EventRecord"
Cohesion: 0.16
Nodes (20): Create an empty projection with no applied events., Replay ``events`` from an optional detached physical snapshot., replay_events(), Create the canonical empty yard state., EventRecord, One ordered, validated event in the experiment trace., _decision_chain_prefix(), The DES emits four service phases for each truck. (+12 more)

### Community 11 - "config.py"
Cohesion: 0.11
Nodes (34): CapacityGateError, CapacityReceipt, _evaluate(), inspect_capacity(), _now(), _os_probe(), Path, RuntimeError (+26 more)

### Community 12 - "load_config"
Cohesion: 0.06
Nodes (87): crn_digest(), load_config(), Path, Load and validate a JSON configuration from a local path., Return the SHA-256 digest for one canonical CRN substream key., canonical_payload_schemas(), derive_controlled_projection(), _jsonl_bytes() (+79 more)

### Community 13 - "manifest.py"
Cohesion: 0.10
Nodes (33): canonical_json(), config_as_dict(), Return the validated configuration in its JSON-compatible shape., Serialize configuration with stable key ordering and compact separators., Frozen configuration and run-manifest primitives for PequiFlux experiments., _as_utc(), build_manifest(), create_run_directory() (+25 more)

### Community 14 - "Any"
Cohesion: 0.15
Nodes (7): _dataset_canonical_bytes(), _latent_sha256(), Any, Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation., Hash canonical event-latent rows without importing the dataset layer., _thaw_dataset_value()

### Community 15 - "config_hash"
Cohesion: 0.16
Nodes (20): config_hash(), factorial_scenarios(), Enumerate the complete factorial in N, m, b, regime order., Return the SHA-256 digest of the canonical UTF-8 configuration JSON., Select the preregistered 20% pilot by stable scenario hash order., select_pilot_configurations(), _hash(), plan_policy_days() (+12 more)

### Community 16 - ".from_snapshot"
Cohesion: 0.32
Nodes (7): _arrival_event(), _physical_snapshot(), Path, test_event_round_trip_and_replay_are_independent_from_physical_snapshot(), test_existing_truck_arrival_validates_priority_before_assignment(), test_jsonl_is_one_canonical_event_per_line(), test_truck_arrival_projects_complete_payload()

### Community 17 - "RunBundle"
Cohesion: 0.24
Nodes (6): load_run_bundle(), _mapping_copy(), Path, Load a persisted bundle without discovering or substituting another run., Immutable handles and parsed rows for one persisted matrix run., RunBundle

### Community 18 - "dataset.py"
Cohesion: 0.12
Nodes (35): _as_utc(), _build_manifest(), _create_staging_directory(), _finalize_freeze(), freeze_dataset(), generate_synthetic_dataset(), _git_inventory(), _load_frozen_dataset() (+27 more)

### Community 19 - "events.py"
Cohesion: 0.25
Nodes (7): _canonicalize(), _freeze(), Any, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Normalize JSON values into detached dict/list/scalar containers., _thaw()

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.23
Nodes (16): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., Return the canonical SHA-256 digest used in log state boundaries. (+8 more)

### Community 22 - "statistics.py"
Cohesion: 0.09
Nodes (45): _as_frame(), _canonical_protocol_error(), canonical_scenario_metadata(), _decimal_relative_improvements(), _derived_stratum(), _evaluate_h1_core(), _extract_pair_frame(), _first_column() (+37 more)

### Community 23 - "experiment.py"
Cohesion: 0.14
Nodes (34): Require exact equality with every frozen field in confirmatory.json., validate_confirmatory_config(), _atomic_write_json(), _atomic_write_text(), _canonical_json(), _csv_text(), _decision_fields(), _derived_scenario_metadata() (+26 more)

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "emulator.py"
Cohesion: 0.07
Nodes (26): ABC, DispatchBlocked, DispatchPolicy, feasible_candidates(), NoFeasibleCandidate, RuntimeError, Feasibility and recommendation boundaries for the yard dispatcher. The…, Raised when hard constraints leave no admissible dispatch choice. (+18 more)

### Community 26 - "canonical_file_hash"
Cohesion: 0.12
Nodes (29): canonical_event_latent_schema(), Require the exact immutable file set for an initial or resampled freeze., Return the exact envelope and closed payload variants for latents., _validate_checksum_chain(), _validate_namespace_inventory(), canonical_checksum_bytes(), canonical_file_hash(), Hash the exact bytes of a persisted artifact. Hashing is intentionally byte… (+21 more)

### Community 27 - "Truck"
Cohesion: 0.11
Nodes (11): _finite_nonnegative(), _identifier(), The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs., Compatibility alias for callers that used the earlier name., The canonical state of one service resource (scale, hopper, or similar)., Alias for ``clock`` at event-oriented boundaries., Resource (+3 more)

### Community 28 - "_comparison_stats"
Cohesion: 0.31
Nodes (10): _bootstrap(), _comparison_stats(), _finite_array(), _hodges_lehmann(), _iqr(), ndarray, _rank_biserial(), Return the paired Hodges--Lehmann estimator from Walsh averages. (+2 more)

### Community 29 - "load_aborted_staging"
Cohesion: 0.28
Nodes (9): _install_tiny_generation_fixture(), load_aborted_staging(), Install a private tiny materialization seam for persisted integration tests., Load and independently validate one retained ABORTED STAGING root., _build_tiny_final_freeze(), Materialize the real hash chain using only the private tiny fixture., Each explicit resample records the complete source/latent provenance contract., test_new_rejection_aborts_without_retry() (+1 more)

### Community 30 - "validate_face_validation_receipt"
Cohesion: 0.22
Nodes (15): materialize_face_validation_template(), _pending(), _project_root(), Any, Path, Verifiable human face-validation receipt gate. The receipt is an input…, Write the empty, versioned receipt template without human values., Validate a receipt against the frozen config, PDF and rubric bytes. (+7 more)

### Community 31 - "export_audit_table"
Cohesion: 0.40
Nodes (5): export_audit_table(), Publish one CSV row from a persisted ``audit.json``. The JSON file is the sole…, The audit table must come from the persisted audit boundary., test_export_audit_table_rejects_claimed_namespace_mismatch(), test_export_audit_table_uses_persisted_json_and_rejects_collision()

### Community 32 - "ComparisonStats"
Cohesion: 0.10
Nodes (4): ComparisonStats, H1Report, Statistics and gates for one stratum/comparator pair., Structured confirmatory result for both congestion strata.

### Community 33 - "ExecutionControls"
Cohesion: 0.10
Nodes (37): ExecutionControls, Decimal, Complete immutable baseline/high control value for a frozen instance., canonical_metric_definitions(), _compute(), compute_policy_day_metrics(), _freeze(), _json_object() (+29 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.36
Nodes (11): Namespace, BootstrapResult, estimate_mde80(), load_pairs(), main(), parse_args(), ndarray, Path (+3 more)

### Community 35 - "File Map"
Cohesion: 0.18
Nodes (10): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 1: Configuração congelada e manifesto, Task 2: Eventos e projeção independente do modelo digital, Task 3: Restrições, políticas e emulador DES, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação (+2 more)

### Community 36 - "DatasetPlan"
Cohesion: 0.09
Nodes (16): DatasetPlan, _instance_id(), plan_synthetic_dataset(), probe_generation_attempt(), Predicted truck rows across instances, not observed generation output., Predicted potential-service rows, shared by all policies per instance., Return detached, lightweight headers in canonical plan order., Validate only lightweight generation headers against the pure plan. (+8 more)

### Community 37 - "_finite_nonnegative"
Cohesion: 0.32
Nodes (3): _finite_nonnegative(), _identifier(), Construct a candidate from a Task 2 ``Truck`` value.

### Community 38 - "experimento-notebook/README.md"
Cohesion: 0.23
Nodes (4): Âncora exploratória RHFS, Governança e estado das entregas, O que falta para as alegações pendentes, Semântica do operador e cobertura existente

### Community 39 - "test_notebook.py"
Cohesion: 0.25
Nodes (9): _cell_source(), Path, Contract checks for the central experiment notebook. The structural check…, The load profile must re-audit, analyse, and export persisted evidence., Load the notebook without requiring the optional notebook stack., _read_notebook_with_stdlib(), test_notebook_has_ordered_sections_and_validation_default(), test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() (+1 more)

### Community 40 - "ScenarioConfig"
Cohesion: 0.10
Nodes (19): crn_seed(), One point in the confirmatory factorial design., Map a CRN key to a stable non-negative integer seed., ScenarioConfig, _build_event_latents(), _build_instance(), _draw_uniform(), _priority_shift_eligible_count() (+11 more)

### Community 41 - "Notebook de experimentos PequiFlux"
Cohesion: 0.22
Nodes (9): Ambiente deliberado, Escopo dos dados sintéticos, Estado deste checkout, Execução limpa canônica, Fronteiras científicas, Layout de artefatos, Notebook de experimentos PequiFlux, Perfis (+1 more)

### Community 42 - "domain.py"
Cohesion: 0.12
Nodes (17): _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., canonical_allowed_cargo_types(), _cargo_tuple(), _controlled_projection_overlay_hash(), _controlled_projection_view_hash() (+9 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (8): Ambiente experimental, Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação do texto, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "FrozenServiceTime"
Cohesion: 0.33
Nodes (3): FrozenServiceTime, One pre-generated service duration and its CRN provenance., test_frozen_service_rejects_forged_crn_draw_key()

### Community 45 - "Template e Guia de Submissão: Revista Production (ABEPRO / SciELO)"
Cohesion: 0.33
Nodes (5): 1. Regras Editoriais Oficiais da Revista *Production*, 2. Inventário de Arquivos do Pacote de Submissão, 3. Instruções de Compilação dos Documentos, 4. Passo a Passo para Submissão no ScholarOne, Template e Guia de Submissão: Revista Production (ABEPRO / SciELO)

### Community 50 - "FrozenDataset"
Cohesion: 0.20
Nodes (4): Strictly validate a complete production freeze., validate_frozen_dataset(), FrozenDataset, Immutable view of a validated, persisted frozen dataset.

### Community 51 - "DatasetContractError"
Cohesion: 0.10
Nodes (41): canonical_bytes(), Serialize any JSON-compatible value in the canonical byte representation., _canonical_confirmatory_config(), DatasetContractError, _digest_bytes(), _instance_event_latent_hashes(), _instance_headers_from_manifest(), _load_aborted_staging_internal() (+33 more)

### Community 52 - "Catálogo rastreável das entradas sintéticas"
Cohesion: 0.22
Nodes (9): Cardinalidades previstas, sem geração, Catálogo rastreável das entradas sintéticas, Chegadas, tempos e atributos, Controles, identificação e execução, Escala, relógio, recursos e fluxo, Fontes e natureza do suporte, Lacunas de evidência que permanecem, Pareamento CRN e pacote de entrada (+1 more)

### Community 53 - "YardSnapshot"
Cohesion: 0.14
Nodes (13): DigitalModel, _physical_number(), _PhysicalReplay, Any, Event-applied digital projection of the physical yard., Apply an ordered event stream to an isolated ``YardSnapshot``., Return a detached copy that cannot mutate the projection., Apply one event atomically, rejecting ordering and state violations. (+5 more)

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

### Community 65 - "FrozenInstance"
Cohesion: 0.06
Nodes (46): FaceValidationError, _generate_one_candidate(), _generate_until_rejection(), GenerationPlanReceipt, GenerationRejectedError, _materialize_production_header(), _PayloadWriter, plan_explicit_resample() (+38 more)

### Community 66 - "_validate_scenario_rows"
Cohesion: 0.40
Nodes (5): _expected_scenario_factors(), Return the fixed confirmatory factorial in its protocol order., _validate_scenario_rows(), _expected_scenario_factors(), Return the canonical confirmatory factorial in protocol order.

### Community 67 - "Candidate"
Cohesion: 0.11
Nodes (23): _activated_rules(), _build_justification(), Candidate, DispatchContext, Alias matching the domain truck terminology., Alias for the current-stage entry timestamp., Immutable observable state supplied to a policy at one decision point., Build the ordered rule list persisted in every recommendation. (+15 more)

### Community 70 - "EventLatentLedger"
Cohesion: 0.22
Nodes (3): EventLatentLedger, Explicit alias for the immutable event-latent payload., Immutable, keyed collection of all pre-realisation event candidates. Rows are…

### Community 72 - "Contrato das métricas canônicas"
Cohesion: 0.25
Nodes (7): CO₂ como hipótese exploratória, Contrato das métricas canônicas, Espera, documentos e corte, Estabilidade, FIFO e admissão, Produção e intervalo observado, Recursos e máximos, Verificação e ausência de dados

### Community 73 - "Academic Paper: Logistics 5.0 in Agro-Industrial Yard Dispatching"
Cohesion: 0.33
Nodes (5): Academic Paper: Logistics 5.0 in Agro-Industrial Yard Dispatching, Compilação, Estrutura de Arquivos, Informações Editoriais, Relação com o TCC e Repositório

### Community 74 - "_rollback_promotion"
Cohesion: 0.40
Nodes (5): BaseException, Remove only directories proven to be ours after a failed promotion., _rollback_promotion(), test_rollback_accumulates_conflicts_after_removing_own_targets(), test_rollback_preserves_reappeared_target_and_chains_cause()

## Knowledge Gaps
- **144 isolated node(s):** `schema_version`, `name`, `cwd`, `steps`, `schema_version` (+139 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExperimentConfig` connect `ExperimentConfig` to `ComparisonStats`, `FrozenInstance`, `audit.py`, `DatasetPlan`, `Any`, `ScenarioConfig`, `config.py`, `load_config`, `manifest.py`, `config_hash`, `RunBundle`, `dataset.py`, `DatasetContractError`, `statistics.py`, `experiment.py`, `_comparison_stats`, `validate_face_validation_receipt`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `ScenarioConfig` connect `ScenarioConfig` to `test_digital_model_replay.py`, `audit.py`, `Any`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `config.py`, `manifest.py`, `config_hash`, `.from_snapshot`, `RunBundle`, `dataset.py`, `statistics.py`, `experiment.py`, `emulator.py`, `ComparisonStats`, `DatasetPlan`, `DatasetContractError`, `YardSnapshot`, `FrozenInstance`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `Truck` connect `Truck` to `test_digital_model_replay.py`, `_DaySimulation`, `domain.py`, `EventRecord`, `Any`, `.from_snapshot`, `YardSnapshot`, `emulator.py`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Candidate` (e.g. with `DayResult` and `_DaySimulation`) actually correct?**
  _`Candidate` has 13 INFERRED edges - model-reasoned connections that need verification._