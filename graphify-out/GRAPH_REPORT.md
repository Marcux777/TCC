# Graph Report - TCC  (2026-09-24)

## Corpus Check
- 61 files · ~115,357 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 10, .csv 3, .lock 2)

## Summary
- 1450 nodes · 4550 edges · 63 communities (52 shown, 11 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 723 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d0aec0b6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_config
- audit.py
- factorial_scenarios
- FrozenDataset
- DatasetContractError
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- Candidate
- campaign.py
- capacity.py
- test_config_manifest.py
- Architecture, Data Flow, and Public Interfaces
- FrozenInstance
- _persisted_day
- ExecutionControls
- dataset.py
- TCC PequiFlux
- Projeto experimental reproduzível em notebook
- replay.py
- statistics.py
- experiment.py
- Governança e estado das entregas
- emulator.py
- Path
- Resource
- config.py
- ExperimentConfig
- face_validation.py
- PequiFlux — experimento central do TCC
- ComparisonStats
- metrics.py
- power_analysis_rhfs.py
- File Map
- Emenda prospectiva — protocolo 2.0.0
- DecisionJustification
- Escopo fechado das entradas sintéticas
- pathlib
- export_audit_table
- digital_model.py
- Any
- EventRecord
- EventLatentLedger
- DatasetPlan
- canonical_bytes
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment
- .document_released
- .arrival_time
- .rho
- YardSnapshot
- _RecordingPolicy
- .ready_time
- domain.py
- ScenarioConfig
- 4.1 Contrato da geração
- Catálogo rastreável das entradas sintéticas
- power_analysis_provenance.md
- importlib_util
- unittest_mock

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 89 edges
2. `DatasetContractError` - 88 edges
3. `load_config()` - 84 edges
4. `Candidate` - 56 edges
5. `ScenarioConfig` - 53 edges
6. `_DaySimulation` - 53 edges
7. `ExecutionControls` - 49 edges
8. `FrozenInstance` - 49 edges
9. `EventRecord` - 47 edges
10. `YardSnapshot` - 46 edges

## Surprising Connections (you probably didn't know these)
- `Barreira verificável de validação de face` --references--> `config_hash()`  [INFERRED]
  experimento-notebook/docs/superpowers/specs/2026-09-02-notebook-experimental-completo-design.md → experimento-notebook/src/pequiflux_experiment/config.py
- `Task 4: Matriz, persistência, replay e auditoria` --references--> `run_day()`  [INFERRED]
  experimento-notebook/docs/superpowers/plans/2026-09-01-experimento-notebook-implementation.md → experimento-notebook/src/pequiflux_experiment/emulator.py
- `Identidades e execução` --references--> `study_scope()`  [INFERRED]
  experimento-notebook/docs/protocol-v2-amendment.md → experimento-notebook/src/pequiflux_experiment/governance.py
- `Architecture, Data Flow, and Public Interfaces` --references--> `audit_run()`  [INFERRED]
  experimento-notebook/docs/superpowers/plans/2026-09-03-notebook-experimental-completo-implementation.md → experimento-notebook/src/pequiflux_experiment/audit.py
- `Task 5: Eight metric families, validation action and persisted A1 contexts` --references--> `audit_run()`  [INFERRED]
  experimento-notebook/docs/superpowers/plans/2026-09-03-notebook-experimental-completo-implementation.md → experimento-notebook/src/pequiflux_experiment/audit.py

## Import Cycles
- None detected.

## Communities (63 total, 11 thin omitted)

### Community 0 - "load_config"
Cohesion: 0.12
Nodes (41): load_config(), Path, Load and validate a JSON configuration from a local path., export_analysis(), Publish H1 artifacts from one real, re-audited confirmatory bundle., evaluate_h1(), Evaluate H1 from one real, persisted, audited confirmatory RunBundle., canonical_confirmatory_rows() (+33 more)

### Community 1 - "audit.py"
Cohesion: 0.07
Nodes (68): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _observed_exclusion() (+60 more)

### Community 2 - "factorial_scenarios"
Cohesion: 0.15
Nodes (20): run_phase(), factorial_scenarios(), Enumerate the complete factorial in N, m, b, regime order., ConfirmatoryWorkload, _hash(), phase_policies(), plan_policy_days(), PolicyDayPlan (+12 more)

### Community 3 - "FrozenDataset"
Cohesion: 0.25
Nodes (3): FrozenDataset, Immutable view of a validated, persisted frozen dataset., Explicit alias for the immutable event-latent payload.

### Community 4 - "DatasetContractError"
Cohesion: 0.08
Nodes (55): _assert_finite_json(), _canonical_confirmatory_config(), DatasetContractError, _expected_instance_ids(), _instance_event_latent_hashes(), _instance_headers_from_manifest(), _load_aborted_staging_internal(), load_freeze_receipt() (+47 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.10
Nodes (12): _DaySimulation, Any, Return mean/p95 accumulated wait per truck and censored residual., Exercise explicit simulated responses on validation instances only. This is not…, Count queued and in-flight trucks that still need unload capacity. A scale-in…, Apply the protocol's mandatory-priority and short-window rules., _round_metric(), run_synthetic_operator_trial() (+4 more)

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.12
Nodes (46): Execute validated frozen inputs; never generate or replace missing draws., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), make_policy(), Construct one of the frozen policy-panel implementations., build_validation_fixture(), test_exploratory_policy_runs_real_des_and_replays() (+38 more)

### Community 7 - "export.py"
Cohesion: 0.09
Nodes (44): BaseException, collections_abc, _destination(), _ensure_targets_absent(), _export_analysis_core(), export_metrics(), ExportedArtifacts, _figure_improvement() (+36 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.13
Nodes (13): 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 1. Objetivo e fronteira científica, 3. Notebook único e ações explícitas, 5. Arquitetura e mapa de interfaces, 8.1 Unidade, efeito e comparadores (+5 more)

### Community 9 - "Candidate"
Cohesion: 0.09
Nodes (37): ABC, Task 3: Restrições, políticas e emulador DES, Task 4: Frozen-domain emulator, event ranks and five dispatch policies, _activated_rules(), _build_justification(), Candidate, DispatchContext, DispatchPolicy (+29 more)

### Community 10 - "campaign.py"
Cohesion: 0.11
Nodes (27): decimal, analyse_pilot(), _bootstrap_median(), campaign_plan(), exploratory_summary(), paired_diagnostics(), principal_storage_requirement(), Full notebook campaign: fixed phases, descriptive diagnostics and stress grid.… (+19 more)

### Community 11 - "capacity.py"
Cohesion: 0.13
Nodes (21): CapacityGateError, CapacityReceipt, _evaluate(), inspect_capacity(), _now(), _os_probe(), Path, RuntimeError (+13 more)

### Community 12 - "test_config_manifest.py"
Cohesion: 0.09
Nodes (47): collections, Task 2.5: Retrofit canonical event-latent ledger for same-CRN sensitivity, add_disruption(), canonical_event_latent_schema(), derive_controlled_instance(), derive_controlled_projection(), _disruption_payload_hash(), _jsonl_bytes() (+39 more)

### Community 13 - "Architecture, Data Flow, and Public Interfaces"
Cohesion: 0.09
Nodes (39): Task 1: Configuração congelada e manifesto, Architecture, Data Flow, and Public Interfaces, Interfaces públicas obrigatórias, canonical_json(), config_as_dict(), config_hash(), Return the validated configuration in its JSON-compatible shape., Serialize configuration with stable key ordering and compact separators. (+31 more)

### Community 15 - "FrozenInstance"
Cohesion: 0.08
Nodes (35): Fontes e natureza do suporte, crn_digest(), crn_seed(), Return the SHA-256 digest for one canonical CRN substream key., Map a CRN key to a stable non-negative integer seed., _build_event_latents(), _build_instance(), _coalesced_rain_rows() (+27 more)

### Community 16 - "_persisted_day"
Cohesion: 0.38
Nodes (7): _persisted_day(), emit(), service(), parametrize, test_active_service_is_censored_as_busy_time_not_queue_wait(), test_metrics_fail_closed_for_missing_input_or_impossible_observation(), test_persisted_metrics_reconcile_overlap_censoring_weighted_resources_and_queue_order()

### Community 17 - "ExecutionControls"
Cohesion: 0.15
Nodes (16): baseline_controls(), Complete controls in the prospective H0/buffer/threshold/intensity order., stress_grid(), _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., _controlled_projection_view_hash() (+8 more)

### Community 18 - "dataset.py"
Cohesion: 0.07
Nodes (59): _as_utc(), _build_manifest(), _create_staging_directory(), _generate_one_candidate(), generate_synthetic_dataset(), _generate_until_rejection(), GenerationRejectedError, _git_inventory() (+51 more)

### Community 19 - "TCC PequiFlux"
Cohesion: 0.29
Nodes (7): Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.23
Nodes (16): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., Return the canonical SHA-256 digest used in log state boundaries. (+8 more)

### Community 22 - "statistics.py"
Cohesion: 0.08
Nodes (48): Task 8: Confirmatory H1 statistics, pairing and invalid-input rules, _as_frame(), _bootstrap(), _comparison_stats(), _decimal_relative_improvements(), _evaluate_h1_core(), _extract_pair_frame(), _finite_array() (+40 more)

### Community 23 - "experiment.py"
Cohesion: 0.11
Nodes (40): _atomic_write_json(), _atomic_write_text(), _canonical_json(), _csv_text(), _decision_fields(), _derived_scenario_metadata(), _git_metadata(), _input_provenance() (+32 more)

### Community 24 - "Governança e estado das entregas"
Cohesion: 0.33
Nodes (6): Execução integral tentada em 24/09/2026, Governança e estado das entregas, O que falta para as alegações pendentes, Protocolo vigente: 2.0.0 (24 de setembro de 2026), Registro histórico do protocolo 1.0.0, Semântica do operador e cobertura existente

### Community 25 - "emulator.py"
Cohesion: 0.09
Nodes (26): dataclasses, DispatchBlocked, _exclusion(), feasible_candidates(), _fifo_reference(), NoFeasibleCandidate, RuntimeError, Feasibility and recommendation boundaries for the yard dispatcher. The… (+18 more)

### Community 26 - "Path"
Cohesion: 0.10
Nodes (39): _digest_bytes(), _finalize_freeze(), freeze_dataset(), load_frozen_dataset(), _load_frozen_dataset(), Path, Write canonical checksums/manifest and return their linked digests., Validate an ABORTED staging namespace without requiring FREEZE.json. (+31 more)

### Community 27 - "Resource"
Cohesion: 0.10
Nodes (12): _cargo_tuple(), _finite_nonnegative(), _identifier(), The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs., Compatibility alias for callers that used the earlier name., The canonical state of one service resource (scale, hopper, or similar)., Alias for ``clock`` at event-oriented boundaries. (+4 more)

### Community 28 - "config.py"
Cohesion: 0.21
Nodes (18): _as_finite_number(), _as_positive_integer_tuple(), _as_probability(), _as_text_tuple(), _as_tuple(), _canonical_nested_fields(), CapacityRequirements, crn_key() (+10 more)

### Community 29 - "ExperimentConfig"
Cohesion: 0.11
Nodes (13): ExperimentConfig, The complete, immutable protocol configuration., Require exact equality with every frozen field in confirmatory.json., validate_confirmatory_config(), human_audit_status(), Prospective study scope, bound to protocol identity rather than a skip flag., study_scope(), _canonical_protocol_error() (+5 more)

### Community 30 - "face_validation.py"
Cohesion: 0.09
Nodes (33): Exact Invariants and Check Mapping, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff, Task 5: Eight metric families, validation action and persisted A1 contexts, Task 6: Capacity gates, pilot/confirmatory execution and atomic run bundles, 13. Testes mínimos por risco material, FaceValidationError, Raised before any namespace is created without approved face evidence. (+25 more)

### Community 31 - "PequiFlux — experimento central do TCC"
Cohesion: 0.33
Nodes (6): Campanha integral, Entradas e armazenamento, Evidência e pendências, PequiFlux — experimento central do TCC, Protocolo vigente, Windows nativo com uv

### Community 32 - "ComparisonStats"
Cohesion: 0.10
Nodes (4): ComparisonStats, H1Report, Statistics and gates for one stratum/comparator pair., Structured confirmatory result for both congestion strata.

### Community 33 - "metrics.py"
Cohesion: 0.18
Nodes (20): _compute(), feasible_queue(), compute_policy_day_metrics(), require_resource(), require_truck(), _freeze(), _json_object(), MetricRow (+12 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.15
Nodes (21): argparse, csv, datetime, Namespace, numpy, platform, scipy, scipy_stats (+13 more)

### Community 35 - "File Map"
Cohesion: 0.25
Nodes (7): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação, Task 6: Notebook central e documentação, Task 7: Verificação integral e atualização do grafo

### Community 36 - "Emenda prospectiva — protocolo 2.0.0"
Cohesion: 0.50
Nodes (4): Elementos preservados, Emenda prospectiva — protocolo 2.0.0, Escopo e critérios substituídos, Identidades e execução

### Community 37 - "DecisionJustification"
Cohesion: 0.15
Nodes (8): DecisionJustification, _finite_nonnegative(), _identifier(), Any, Construct a candidate from a Task 2 ``Truck`` value., Canonical five-field explanation required by the A2 protocol. ``truck_stage``…, Parse exactly the canonical persisted five-field representation., Return a detached JSON-compatible contract object.

### Community 38 - "Escopo fechado das entradas sintéticas"
Cohesion: 0.25
Nodes (6): Escopo fechado das entradas sintéticas, Fronteiras do modelo e verificações, Persistência e CRN, Unidade e dimensão previstas, Predicted truck rows across instances, not observed generation output., Predicted potential-service rows, shared by all policies per instance.

### Community 39 - "pathlib"
Cohesion: 0.18
Nodes (7): Structural checks only: the notebook itself always requests the full campaign., main(), Execute the sole research notebook, retaining outputs even on failure., nbclient, nbformat, pathlib, tomllib

### Community 40 - "export_audit_table"
Cohesion: 0.40
Nodes (5): export_audit_table(), Publish one CSV row from a persisted ``audit.json``. The JSON file is the sole…, The audit table must come from the persisted audit boundary., test_export_audit_table_rejects_claimed_namespace_mismatch(), test_export_audit_table_uses_persisted_json_and_rejects_collision()

### Community 41 - "digital_model.py"
Cohesion: 0.16
Nodes (12): copy, Event-applied digital projection of the physical yard., _canonicalize(), _freeze(), Any, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Normalize JSON values into detached dict/list/scalar containers. (+4 more)

### Community 42 - "Any"
Cohesion: 0.09
Nodes (14): _dataset_canonical_bytes(), _dataset_digest(), _freeze_dataset_value(), FrozenServiceTime, _latent_sha256(), Any, One pre-generated service duration and its CRN provenance., Expose a lightweight scenario-like object for downstream consumers. (+6 more)

### Community 43 - "EventRecord"
Cohesion: 0.11
Nodes (36): Replay ``events`` from an optional detached physical snapshot., Create an empty projection with no applied events., replay_events(), EventRecord, Path, Write events as one canonical JSON object per line., Read and validate every non-empty JSONL event line., One ordered, validated event in the experiment trace. (+28 more)

### Community 44 - "EventLatentLedger"
Cohesion: 0.16
Nodes (9): Final Verification and Handoff, Task 9: Separate sensitivity grid and joint robustness decision, 10. Sensibilidade separada, 16. Auto-revisão contra `main.pdf`, 4.3 Common random numbers (CRN), 7. Métricas obrigatórias do PDF, Integridade e hash sem ciclo, EventLatentLedger (+1 more)

### Community 45 - "DatasetPlan"
Cohesion: 0.09
Nodes (18): Task 2: Frozen domain, deterministic generator and complete hash chain, canonical_payload_schemas(), DatasetPlan, _expected_scenario_factors(), GenerationPlanReceipt, Return detached, lightweight headers in canonical plan order., Return the zero-based ordinal immediately after ``instance_id``., Pure cardinality receipt; it never publishes or loads a dataset. (+10 more)

### Community 46 - "canonical_bytes"
Cohesion: 0.09
Nodes (26): Task 3: STAGING rejection and explicit one-attempt resample, Emenda de governança sem retry, canonical_bytes(), Serialize any JSON-compatible value in the canonical byte representation., _controlled_event_hash(), _digest_value(), _install_tiny_generation_fixture(), plan_synthetic_dataset() (+18 more)

### Community 52 - ".rho"
Cohesion: 0.33
Nodes (5): 2.1 Fatorial, sementes e estratos, 2.2 Horizonte, chegadas, serviços e perturbações, 2.3 Painel de políticas, 2. Protocolo congelado derivado do PDF, Pareamento CRN e pacote de entrada

### Community 53 - "YardSnapshot"
Cohesion: 0.16
Nodes (12): Task 2: Eventos e projeção independente do modelo digital, Task 7: Independent replay/audit, A1 adjudication and A2 workflow, DigitalModel, Any, Extract the fields that identify a recommendation's selection. Decision records…, Apply an ordered event stream to an isolated ``YardSnapshot``., Return a detached copy that cannot mutate the projection., Apply one event atomically, rejecting ordering and state violations. (+4 more)

### Community 56 - "domain.py"
Cohesion: 0.14
Nodes (15): _controlled_projection_overlay_hash(), _controlled_rain_covered_latent_ids(), ControlledProjection, FreezeReceipt, _latent_digest(), _latent_number(), _latent_resource(), Mutable physical-domain values used by the independent digital model. The… (+7 more)

### Community 57 - "ScenarioConfig"
Cohesion: 0.13
Nodes (10): Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 1: Canonical configuration and face-validation gate, 4.2 Esquema mínimo e arquivos, 6. Piloto e campanha confirmatória, One point in the confirmatory factorial design., ScenarioConfig (+2 more)

### Community 60 - "4.1 Contrato da geração"
Cohesion: 0.33
Nodes (5): 4.1 Contrato da geração, 4. Dataset sintético: geração visível, persistência e congelamento, 9.1 A1 adversarial, 9.2 A2: estrutura, amostra, rubrica e kappa, 9. A1 adversarial e A2 independente

### Community 64 - "Catálogo rastreável das entradas sintéticas"
Cohesion: 0.29
Nodes (7): Cardinalidades previstas, sem geração, Catálogo rastreável das entradas sintéticas, Chegadas, tempos e atributos, Controles, identificação e execução, Escala, relógio, recursos e fluxo, Lacunas de evidência que permanecem, Regimes e perturbações

## Knowledge Gaps
- **57 isolated node(s):** `pequiflux-experiment`, `graphify`, `graphify`, `Fontes normativas do projeto`, `Classificação correta do artefato visual` (+52 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 470 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExperimentConfig` connect `ExperimentConfig` to `load_config`, `audit.py`, `factorial_scenarios`, `DatasetContractError`, `PequiFlux — especificação vinculante do notebook experimental completo`, `Candidate`, `campaign.py`, `Architecture, Data Flow, and Public Interfaces`, `FrozenInstance`, `dataset.py`, `statistics.py`, `experiment.py`, `config.py`, `face_validation.py`, `ComparisonStats`, `EventLatentLedger`, `DatasetPlan`, `canonical_bytes`, `ScenarioConfig`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `Architecture, Data Flow, and Public Interfaces` connect `Architecture, Data Flow, and Public Interfaces` to `load_config`, `audit.py`, `factorial_scenarios`, `DatasetContractError`, `test_dispatch_emulator.py`, `Candidate`, `campaign.py`, `test_config_manifest.py`, `FrozenInstance`, `ExecutionControls`, `dataset.py`, `replay.py`, `statistics.py`, `experiment.py`, `Path`, `Resource`, `config.py`, `ExperimentConfig`, `export_audit_table`, `EventRecord`, `EventLatentLedger`, `DatasetPlan`, `canonical_bytes`, `YardSnapshot`, `ScenarioConfig`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `load_config()` connect `load_config` to `audit.py`, `factorial_scenarios`, `DatasetContractError`, `campaign.py`, `test_config_manifest.py`, `Architecture, Data Flow, and Public Interfaces`, `canonical_bytes`, `DatasetPlan`, `dataset.py`, `Path`, `config.py`, `ExperimentConfig`, `face_validation.py`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 56 inferred relationships involving `ExperimentConfig` (e.g. with `Task 1: Configuração congelada e manifesto` and `Architecture, Data Flow, and Public Interfaces`) actually correct?**
  _`ExperimentConfig` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `DatasetContractError` (e.g. with `Task 2.5: Retrofit canonical event-latent ledger for same-CRN sensitivity` and `_assert_latent_rows_rejected()`) actually correct?**
  _`DatasetContractError` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `load_config()` (e.g. with `Task 1: Configuração congelada e manifesto` and `Architecture, Data Flow, and Public Interfaces`) actually correct?**
  _`load_config()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `Candidate` (e.g. with `Task 3: Restrições, políticas e emulador DES` and `Architecture, Data Flow, and Public Interfaces`) actually correct?**
  _`Candidate` has 22 INFERRED edges - model-reasoned connections that need verification._