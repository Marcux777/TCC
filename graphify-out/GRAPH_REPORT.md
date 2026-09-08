# Graph Report - TCC  (2026-09-07)

## Corpus Check
- 71 files · ~117,139 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1370 nodes · 3958 edges · 66 communities (63 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 291 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f9a44ae9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_config
- audit.py
- config_hash
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
- FrozenInstance
- ExperimentConfig
- digital_model.py
- ExecutionControls
- Path
- DatasetContractError
- Projeto experimental reproduzível em notebook
- replay.py
- statistics.py
- ScenarioConfig
- Exact Invariants and Check Mapping
- emulator.py
- canonical_file_hash
- Resource
- config.py
- recommend
- canonical_bytes
- Recommendation
- ComparisonStats
- metrics.py
- power_analysis_rhfs.py
- File Map
- DatasetPlan
- dispatch.py
- experimento-notebook/README.md
- test_notebook.py
- export_audit_table
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- FrozenServiceTime
- test_event_round_trip_and_replay_are_independent_from_physical_snapshot
- AbortedStaging
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment
- EventLatentLedger
- FrozenTruck
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
- _dataset_canonical_bytes

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 88 edges
2. `DatasetContractError` - 79 edges
3. `load_config()` - 77 edges
4. `ScenarioConfig` - 63 edges
5. `Candidate` - 58 edges
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

## Communities (66 total, 3 thin omitted)

### Community 0 - "load_config"
Cohesion: 0.14
Nodes (42): load_config(), Path, Require exact equality with every frozen field in confirmatory.json., Load and validate a JSON configuration from a local path., validate_confirmatory_config(), export_analysis(), Publish H1 artifacts from one real, re-audited confirmatory bundle., evaluate_h1() (+34 more)

### Community 1 - "audit.py"
Cohesion: 0.07
Nodes (62): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _observed_exclusion() (+54 more)

### Community 2 - "config_hash"
Cohesion: 0.17
Nodes (19): config_hash(), factorial_scenarios(), Enumerate the complete factorial in N, m, b, regime order., Return the SHA-256 digest of the canonical UTF-8 configuration JSON., Frozen configuration and run-manifest primitives for PequiFlux experiments., _hash(), plan_policy_days(), PolicyDayPlan (+11 more)

### Community 3 - "Any"
Cohesion: 0.20
Nodes (3): Any, Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation.

### Community 4 - "dataset.py"
Cohesion: 0.09
Nodes (47): _assert_finite_json(), _coalesced_rain_rows(), _controlled_event_hash(), _derive_controlled_instance(), _digest_bytes(), _digest_value(), _disruption_payload_hash(), _expected_instance_ids() (+39 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.14
Nodes (5): _DaySimulation, Return mean/p95 accumulated wait per truck and censored residual., Count queued and in-flight trucks that still need unload capacity. A scale-in…, Apply the protocol's mandatory-priority and short-window rules., _Scheduled

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.11
Nodes (48): Execute validated frozen inputs; never generate or replace missing draws., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), make_policy(), Construct one of the frozen policy-panel implementations., build_validation_fixture(), candidate() (+40 more)

### Community 7 - "export.py"
Cohesion: 0.10
Nodes (39): BaseException, _destination(), _ensure_targets_absent(), _export_analysis_core(), export_metrics(), ExportedArtifacts, _figure_improvement(), _figure_p95() (+31 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.11
Nodes (18): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+10 more)

### Community 9 - "Candidate"
Cohesion: 0.13
Nodes (19): Candidate, DispatchContext, DispatchPolicy, Alias matching the domain truck terminology., Alias for the current-stage entry timestamp., Immutable observable state supplied to a policy at one decision point., Base interface: subclasses may rank, but never change feasibility., Return a deterministic key; lower keys are selected. (+11 more)

### Community 10 - "EventRecord"
Cohesion: 0.15
Nodes (26): Replay ``events`` from an optional detached physical snapshot., Create an empty projection with no applied events., replay_events(), Create the canonical empty yard state., EventRecord, One ordered, validated event in the experiment trace., _arrival_event(), _decision_chain_prefix() (+18 more)

### Community 11 - "capacity.py"
Cohesion: 0.20
Nodes (16): CapacityGateError, CapacityReceipt, _evaluate(), inspect_capacity(), _now(), _os_probe(), Path, RuntimeError (+8 more)

### Community 12 - "test_config_manifest.py"
Cohesion: 0.07
Nodes (55): canonical_event_latent_schema(), canonical_payload_schemas(), derive_controlled_projection(), _jsonl_bytes(), load_event_latents(), Load and validate the canonical ``event_latents.jsonl`` payload., Derive a frozen projection and return its two identity attestations., Return the exact public Parquet column contract. (+47 more)

### Community 13 - "manifest.py"
Cohesion: 0.11
Nodes (32): _as_utc(), build_manifest(), create_run_directory(), _declared_distribution_names(), _detect_gpu(), _memory_inventory(), _memory_total_bytes(), _normalise_artifacts() (+24 more)

### Community 14 - "FrozenInstance"
Cohesion: 0.14
Nodes (20): _generate_one_candidate(), _generate_until_rejection(), _materialize_production_header(), _PayloadWriter, Collect deterministic rows for one complete production freeze., Materialize one complete immutable instance into the payload writer., Validate one fully generated candidate before any payload write. The priority-…, Private seam delegating to the canonical validator. Tests may monkeypatch this… (+12 more)

### Community 15 - "ExperimentConfig"
Cohesion: 0.08
Nodes (27): crn_digest(), crn_seed(), ExperimentConfig, The complete, immutable protocol configuration., Return the SHA-256 digest for one canonical CRN substream key., Map a CRN key to a stable non-negative integer seed., _build_event_latents(), _build_instance() (+19 more)

### Community 16 - "digital_model.py"
Cohesion: 0.20
Nodes (9): Event-applied digital projection of the physical yard., _canonicalize(), _freeze(), Any, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Normalize JSON values into detached dict/list/scalar containers., _thaw() (+1 more)

### Community 17 - "ExecutionControls"
Cohesion: 0.17
Nodes (11): _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., ExecutionControls, Decimal, Complete immutable baseline/high control value for a frozen instance., build_validation_inputs() (+3 more)

### Community 18 - "Path"
Cohesion: 0.09
Nodes (39): _as_utc(), _build_manifest(), _create_staging_directory(), _finalize_freeze(), freeze_dataset(), generate_synthetic_dataset(), _git_inventory(), _install_tiny_generation_fixture() (+31 more)

### Community 19 - "DatasetContractError"
Cohesion: 0.12
Nodes (33): _canonical_confirmatory_config(), DatasetContractError, _instance_headers_from_manifest(), _load_aborted_staging_internal(), load_freeze_receipt(), _load_json(), Return the zero-based ordinal immediately after ``instance_id``., Build JSON objects while rejecting duplicate keys at parse time. (+25 more)

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.27
Nodes (14): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., _read_raw_lines() (+6 more)

### Community 22 - "statistics.py"
Cohesion: 0.08
Nodes (55): _as_frame(), _bootstrap(), _canonical_protocol_error(), canonical_scenario_metadata(), _comparison_stats(), _decimal_relative_improvements(), _derived_stratum(), _evaluate_h1_core() (+47 more)

### Community 23 - "ScenarioConfig"
Cohesion: 0.08
Nodes (40): One point in the confirmatory factorial design., ScenarioConfig, _atomic_write_json(), _atomic_write_text(), _canonical_json(), _csv_text(), _decision_fields(), _derived_scenario_metadata() (+32 more)

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "emulator.py"
Cohesion: 0.10
Nodes (15): DispatchBlocked, NoFeasibleCandidate, RuntimeError, Raised when hard constraints leave no admissible dispatch choice., Raised when ``fifo_strict`` must idle behind an ineligible head truck., DayResult, Deterministic discrete-event emulator for the PequiFlux yard. The…, Canonical output identifying its frozen input, controls and policy. (+7 more)

### Community 26 - "canonical_file_hash"
Cohesion: 0.26
Nodes (12): _validate_checksum_chain(), canonical_checksum_bytes(), canonical_file_hash(), Hash the exact bytes of a persisted artifact. Hashing is intentionally byte…, Serialize an ordered payload checksum list exactly once. ``entries`` must…, Create only tiny arbitrary payload bytes for hash-chain boundary tests., test_checksum_chain_accepts_exact_six_payload_mapping(), test_checksum_chain_rejects_manifest_extra_field() (+4 more)

### Community 27 - "Resource"
Cohesion: 0.10
Nodes (9): _cargo_tuple(), _finite_nonnegative(), _identifier(), Compatibility alias for callers that used the earlier name., The canonical state of one service resource (scale, hopper, or similar)., Alias for ``clock`` at event-oriented boundaries., Resource, test_resource_status_outside_closed_set_is_rejected() (+1 more)

### Community 28 - "config.py"
Cohesion: 0.19
Nodes (22): _as_finite_number(), _as_positive_integer_tuple(), _as_probability(), _as_text_tuple(), _as_tuple(), canonical_json(), _canonical_nested_fields(), CapacityRequirements (+14 more)

### Community 29 - "recommend"
Cohesion: 0.24
Nodes (18): Return one policy recommendation after hard-constraint filtering., recommend(), _build_bundle(), parametrize, Path, Regression checks for the explicit five-field A2 decision contract., _rewrite_first_decision(), test_audit_authenticates_decision_facts_against_events() (+10 more)

### Community 30 - "canonical_bytes"
Cohesion: 0.15
Nodes (21): canonical_bytes(), Serialize any JSON-compatible value in the canonical byte representation., materialize_face_validation_template(), _pending(), _project_root(), Any, Path, Verifiable human face-validation receipt gate. The receipt is an input… (+13 more)

### Community 31 - "Recommendation"
Cohesion: 0.16
Nodes (9): feasible_candidates(), A policy's selected candidate and its auditable ranking context., Apply all hard constraints and return admissible values plus exclusions., Recommendation, Any, Explicit synthetic responses for validation-only operator trials., Resolve within offered feasible candidates; executor enforces Cadm. Strict FIFO…, SyntheticOperatorResponse (+1 more)

### Community 32 - "ComparisonStats"
Cohesion: 0.10
Nodes (4): ComparisonStats, H1Report, Statistics and gates for one stratum/comparator pair., Structured confirmatory result for both congestion strata.

### Community 33 - "metrics.py"
Cohesion: 0.15
Nodes (24): _compute(), compute_policy_day_metrics(), _freeze(), _json_object(), MetricRow, MetricsError, _number(), _plain() (+16 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.36
Nodes (11): Namespace, BootstrapResult, estimate_mde80(), load_pairs(), main(), parse_args(), ndarray, Path (+3 more)

### Community 35 - "File Map"
Cohesion: 0.18
Nodes (10): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 1: Configuração congelada e manifesto, Task 2: Eventos e projeção independente do modelo digital, Task 3: Restrições, políticas e emulador DES, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação (+2 more)

### Community 36 - "DatasetPlan"
Cohesion: 0.07
Nodes (28): DatasetPlan, FaceValidationError, GenerationPlanReceipt, GenerationRejectedError, Predicted truck rows across instances, not observed generation output., Predicted potential-service rows, shared by all policies per instance., Return detached, lightweight headers in canonical plan order., Pure cardinality receipt; it never publishes or loads a dataset. (+20 more)

### Community 37 - "dispatch.py"
Cohesion: 0.11
Nodes (14): ABC, _activated_rules(), _build_justification(), _exclusion(), _fifo_reference(), _finite_nonnegative(), _identifier(), Any (+6 more)

### Community 38 - "experimento-notebook/README.md"
Cohesion: 0.23
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
Cohesion: 0.16
Nodes (12): _controlled_projection_overlay_hash(), _controlled_projection_view_hash(), _controlled_rain_covered_latent_ids(), _freeze_dataset_value(), _latent_number(), _latent_resource(), Mutable physical-domain values used by the independent digital model. The…, Detach a JSON-compatible value into immutable containers. (+4 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (8): Ambiente experimental, Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação do texto, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "FrozenServiceTime"
Cohesion: 0.15
Nodes (7): FrozenResource, FrozenServiceTime, Immutable resource record used by a frozen instance., One pre-generated service duration and its CRN provenance., test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order(), test_frozen_instance_service_order_keeps_truck_identity(), test_frozen_service_rejects_forged_crn_draw_key()

### Community 45 - "test_event_round_trip_and_replay_are_independent_from_physical_snapshot"
Cohesion: 0.24
Nodes (11): Path, Write events as one canonical JSON object per line., Read and validate every non-empty JSONL event line., read_jsonl(), write_jsonl(), _physical_snapshot(), Path, test_event_round_trip_and_replay_are_independent_from_physical_snapshot() (+3 more)

### Community 46 - "AbortedStaging"
Cohesion: 0.20
Nodes (7): plan_explicit_resample(), Copy accepted source rows into a fresh writer without loading instances., Build an explicit one-attempt resample plan from retained STAGING state., _writer_from_aborted_staging(), AbortedStaging, Retained, hash-linked staging state after a fail-fast rejection., Ordinal of the next candidate to be attempted after rejection.

### Community 50 - "EventLatentLedger"
Cohesion: 0.22
Nodes (3): EventLatentLedger, Explicit alias for the immutable event-latent payload., Immutable, keyed collection of all pre-realisation event candidates. Rows are…

### Community 51 - "FrozenTruck"
Cohesion: 0.24
Nodes (3): _dataset_digest(), FrozenTruck, Immutable truck record persisted in ``trucks.parquet``.

### Community 52 - "Catálogo rastreável das entradas sintéticas"
Cohesion: 0.22
Nodes (9): Cardinalidades previstas, sem geração, Catálogo rastreável das entradas sintéticas, Chegadas, tempos e atributos, Controles, identificação e execução, Escala, relógio, recursos e fluxo, Fontes e natureza do suporte, Lacunas de evidência que permanecem, Pareamento CRN e pacote de entrada (+1 more)

### Community 53 - "YardSnapshot"
Cohesion: 0.15
Nodes (13): DigitalModel, Any, Extract the fields that identify a recommendation's selection. Decision records…, Apply an ordered event stream to an isolated ``YardSnapshot``., Return a detached copy that cannot mutate the projection., Apply one event atomically, rejecting ordering and state violations., The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs. (+5 more)

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

### Community 65 - "_dataset_canonical_bytes"
Cohesion: 0.50
Nodes (4): _dataset_canonical_bytes(), _latent_sha256(), Hash canonical event-latent rows without importing the dataset layer., _thaw_dataset_value()

## Knowledge Gaps
- **130 isolated node(s):** `schema_version`, `name`, `cwd`, `steps`, `schema_version` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExperimentConfig` connect `ExperimentConfig` to `load_config`, `audit.py`, `config_hash`, `ComparisonStats`, `dataset.py`, `DatasetPlan`, `capacity.py`, `manifest.py`, `FrozenInstance`, `AbortedStaging`, `Path`, `DatasetContractError`, `statistics.py`, `ScenarioConfig`, `config.py`, `canonical_bytes`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `ScenarioConfig` connect `ScenarioConfig` to `ComparisonStats`, `audit.py`, `config_hash`, `dataset.py`, `DatasetPlan`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `FrozenInstance`, `ExperimentConfig`, `digital_model.py`, `ExecutionControls`, `DatasetContractError`, `YardSnapshot`, `statistics.py`, `emulator.py`, `config.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `load_config()` connect `load_config` to `audit.py`, `config_hash`, `dataset.py`, `DatasetPlan`, `test_config_manifest.py`, `ExperimentConfig`, `Path`, `DatasetContractError`, `canonical_file_hash`, `config.py`, `recommend`, `canonical_bytes`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Candidate` (e.g. with `DayResult` and `_DaySimulation`) actually correct?**
  _`Candidate` has 13 INFERRED edges - model-reasoned connections that need verification._