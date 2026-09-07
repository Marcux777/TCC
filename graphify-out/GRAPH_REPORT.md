# Graph Report - TCC  (2026-09-07)

## Corpus Check
- 40 files · ~95,634 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1177 nodes · 3383 edges · 49 communities (45 shown, 4 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 236 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4b2dc898`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_config
- audit.py
- ScenarioConfig
- Any
- dataset.py
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- Candidate
- EventRecord
- validate_face_validation_receipt
- emulator.py
- config.py
- FrozenDataset
- FrozenInstance
- events.py
- AbortedStaging
- Path
- NoFeasibleCandidate
- Projeto experimental reproduzível em notebook
- replay.py
- PairingError
- ExperimentConfig
- Exact Invariants and Check Mapping
- statistics.py
- canonical_bytes
- YardSnapshot
- test_admissible_window_filters_cargo_before_priority_and_top_h0
- EventLatentLedger
- DatasetContractError
- test_a2_structural.py
- ComparisonStats
- H1Report
- power_analysis_rhfs.py
- File Map
- DatasetPlan
- dispatch.py
- _extract_pair_frame
- test_notebook.py
- ExecutionControls
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- FrozenTruck
- FrozenServiceTime
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 82 edges
2. `DatasetContractError` - 79 edges
3. `load_config()` - 76 edges
4. `ScenarioConfig` - 58 edges
5. `_DaySimulation` - 52 edges
6. `Candidate` - 49 edges
7. `EventRecord` - 46 edges
8. `YardSnapshot` - 45 edges
9. `DatasetPlan` - 40 edges
10. `DispatchContext` - 37 edges

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

## Communities (49 total, 4 thin omitted)

### Community 0 - "load_config"
Cohesion: 0.06
Nodes (96): load_config(), Path, Load and validate a JSON configuration from a local path., canonical_payload_schemas(), derive_controlled_projection(), _jsonl_bytes(), load_event_latents(), Load and validate the canonical ``event_latents.jsonl`` payload. (+88 more)

### Community 1 - "audit.py"
Cohesion: 0.08
Nodes (49): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _pair_key() (+41 more)

### Community 2 - "ScenarioConfig"
Cohesion: 0.07
Nodes (41): factorial_scenarios(), One point in the confirmatory factorial design., Require exact equality with every frozen field in confirmatory.json., Enumerate the complete factorial in N, m, b, regime order., ScenarioConfig, validate_confirmatory_config(), DayResult, Canonical output of one scenario/seed/policy execution. (+33 more)

### Community 3 - "Any"
Cohesion: 0.16
Nodes (6): _dataset_digest(), _freeze_dataset_value(), Any, Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation., Detach a JSON-compatible value into immutable containers.

### Community 4 - "dataset.py"
Cohesion: 0.10
Nodes (45): _canonical_confirmatory_config(), canonical_event_latent_schema(), _coalesced_rain_rows(), _controlled_event_hash(), _derive_controlled_instance(), _digest_value(), _disruption_payload_hash(), _expected_instance_ids() (+37 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.11
Nodes (8): _DaySimulation, Any, Return mean/p95 accumulated wait per truck and censored residual., Return a reproducible substream independent of dispatch order. The policy is…, Count queued and in-flight trucks that still need unload capacity. A scale-in…, Apply the protocol's mandatory-priority and short-window rules., _round_metric(), Random

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.16
Nodes (34): Execute one deterministic scenario using a local RNG and policy., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), _validate_regime(), make_policy(), Construct one of the frozen policy-panel implementations., _per_truck_waits_from_events() (+26 more)

### Community 7 - "export.py"
Cohesion: 0.09
Nodes (40): BaseException, _destination(), _ensure_targets_absent(), _export_analysis_core(), export_audit_table(), ExportedArtifacts, _figure_improvement(), _figure_p95() (+32 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.06
Nodes (32): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+24 more)

### Community 9 - "Candidate"
Cohesion: 0.11
Nodes (26): Candidate, DispatchContext, DispatchPolicy, feasible_candidates(), Alias matching the domain truck terminology., Alias for the current-stage entry timestamp., Immutable observable state supplied to a policy at one decision point., Base interface: subclasses may rank, but never change feasibility. (+18 more)

### Community 10 - "EventRecord"
Cohesion: 0.13
Nodes (28): Replay ``events`` from an optional detached physical snapshot., Create an empty projection with no applied events., Apply one event atomically, rejecting ordering and state violations., replay_events(), Create the canonical empty yard state., EventRecord, One ordered, validated event in the experiment trace., _arrival_event() (+20 more)

### Community 11 - "validate_face_validation_receipt"
Cohesion: 0.15
Nodes (19): FaceValidationReport, materialize_face_validation_template(), _pending(), _project_root(), Any, Path, Verifiable human face-validation receipt gate. The receipt is an input…, Write the empty, versioned receipt template without human values. (+11 more)

### Community 12 - "emulator.py"
Cohesion: 0.09
Nodes (18): Event-applied digital projection of the physical yard., canonical_allowed_cargo_types(), _cargo_tuple(), _finite_nonnegative(), _identifier(), The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs., Compatibility alias for callers that used the earlier name. (+10 more)

### Community 13 - "config.py"
Cohesion: 0.07
Nodes (58): _as_finite_number(), _as_positive_integer_tuple(), _as_probability(), _as_text_tuple(), _as_tuple(), canonical_json(), _canonical_nested_fields(), CapacityRequirements (+50 more)

### Community 14 - "FrozenDataset"
Cohesion: 0.17
Nodes (6): freeze_dataset(), Strictly validate a complete production freeze., Finalize a directory containing the six payloads and return its freeze., validate_frozen_dataset(), FrozenDataset, Immutable view of a validated, persisted frozen dataset.

### Community 15 - "FrozenInstance"
Cohesion: 0.16
Nodes (16): _generate_one_candidate(), _generate_until_rejection(), _materialize_production_header(), _PayloadWriter, Collect deterministic rows for one complete production freeze., Materialize one complete immutable instance into the payload writer., Validate one fully generated candidate before any payload write. The priority-…, Private seam delegating to the canonical validator. Tests may monkeypatch this… (+8 more)

### Community 16 - "events.py"
Cohesion: 0.16
Nodes (15): _canonicalize(), _freeze(), Any, Path, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Write events as one canonical JSON object per line., Read and validate every non-empty JSONL event line. (+7 more)

### Community 17 - "AbortedStaging"
Cohesion: 0.20
Nodes (7): plan_explicit_resample(), Copy accepted source rows into a fresh writer without loading instances., Build an explicit one-attempt resample plan from retained STAGING state., _writer_from_aborted_staging(), AbortedStaging, Retained, hash-linked staging state after a fail-fast rejection., Ordinal of the next candidate to be attempted after rejection.

### Community 18 - "Path"
Cohesion: 0.15
Nodes (31): _as_utc(), _build_manifest(), _create_staging_directory(), generate_synthetic_dataset(), _git_inventory(), _install_tiny_generation_fixture(), load_aborted_staging(), _persist_staging_abort() (+23 more)

### Community 19 - "NoFeasibleCandidate"
Cohesion: 0.15
Nodes (9): DispatchBlocked, NoFeasibleCandidate, RuntimeError, Raised when hard constraints leave no admissible dispatch choice., Raised when ``fifo_strict`` must idle behind an ineligible head truck., _RecordingPolicy, _ScaleOutFirstPolicy, test_fixed_score_weights_waiting_before_priority_with_deterministic_ties() (+1 more)

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.23
Nodes (16): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., Return the canonical SHA-256 digest used in log state boundaries. (+8 more)

### Community 22 - "PairingError"
Cohesion: 0.12
Nodes (22): _as_frame(), canonical_scenario_metadata(), _decimal_relative_improvements(), _derived_stratum(), _normalise_stratum(), _pair_identifier(), PairingError, _positive_integer() (+14 more)

### Community 23 - "ExperimentConfig"
Cohesion: 0.12
Nodes (14): ExperimentConfig, The complete, immutable protocol configuration., _build_event_latents(), _build_instance(), _draw_uniform(), _instance_id(), _priority_shift_eligible_count(), Count eligible trucks for a priority shift without materializing an instance. (+6 more)

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "statistics.py"
Cohesion: 0.33
Nodes (11): _bootstrap(), _comparison_stats(), _finite_array(), _hodges_lehmann(), _iqr(), ndarray, _rank_biserial(), Confirmatory paired statistics for the PequiFlux experiment. The analysis… (+3 more)

### Community 26 - "canonical_bytes"
Cohesion: 0.13
Nodes (29): canonical_bytes(), Serialize any JSON-compatible value in the canonical byte representation., _assert_finite_json(), _digest_bytes(), _finalize_freeze(), _load_frozen_dataset(), _load_json(), Write canonical checksums/manifest and return their linked digests. (+21 more)

### Community 27 - "YardSnapshot"
Cohesion: 0.20
Nodes (9): DigitalModel, Any, Extract the fields that identify a recommendation's selection. Decision records…, Apply an ordered event stream to an isolated ``YardSnapshot``., Return a detached copy that cannot mutate the projection., A complete, JSON-friendly observation of the yard at one instant., YardSnapshot, test_existing_truck_arrival_validates_priority_before_assignment() (+1 more)

### Community 28 - "test_admissible_window_filters_cargo_before_priority_and_top_h0"
Cohesion: 0.53
Nodes (6): candidate(), dispatch_context(), parametrize, test_admissible_window_filters_cargo_before_priority_and_top_h0(), test_blocked_truck_and_failed_resource_never_generate_command(), test_policy_select_also_fails_closed_on_unavailable_resource()

### Community 29 - "EventLatentLedger"
Cohesion: 0.20
Nodes (3): EventLatentLedger, Explicit alias for the immutable event-latent payload., Immutable, keyed collection of all pre-realisation event candidates. Rows are…

### Community 30 - "DatasetContractError"
Cohesion: 0.13
Nodes (27): DatasetContractError, _instance_headers_from_manifest(), _load_aborted_staging_internal(), load_freeze_receipt(), plan_synthetic_dataset(), Return the zero-based ordinal immediately after ``instance_id``., Build JSON objects while rejecting duplicate keys at parse time., Validate provenance reference, content bytes, and header reconciliation. This… (+19 more)

### Community 31 - "test_a2_structural.py"
Cohesion: 0.38
Nodes (8): _build_bundle(), parametrize, Path, Regression checks for the explicit five-field A2 decision contract., _rewrite_first_decision(), test_audit_rejects_invented_rule_or_overlapping_exclusion(), test_audit_rejects_semantically_incoherent_a2_justification(), test_pending_human_audit_is_not_an_approved_a2_result()

### Community 33 - "H1Report"
Cohesion: 0.16
Nodes (14): _evaluate_h1_core(), _first_column(), H1Report, _holm_adjust(), _long_metric_column(), _metric_column(), paired_dataframe(), DataFrame (+6 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.35
Nodes (11): Namespace, BootstrapResult, estimate_mde80(), load_pairs(), main(), parse_args(), ndarray, Path (+3 more)

### Community 35 - "File Map"
Cohesion: 0.18
Nodes (10): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 1: Configuração congelada e manifesto, Task 2: Eventos e projeção independente do modelo digital, Task 3: Restrições, políticas e emulador DES, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação (+2 more)

### Community 36 - "DatasetPlan"
Cohesion: 0.08
Nodes (27): DatasetPlan, FaceValidationError, GenerationPlanReceipt, GenerationRejectedError, probe_generation_attempt(), Return detached, lightweight headers in canonical plan order., Pure cardinality receipt; it never publishes or loads a dataset., Validate only lightweight generation headers against the pure plan. (+19 more)

### Community 37 - "dispatch.py"
Cohesion: 0.11
Nodes (14): ABC, _activated_rules(), _build_justification(), _fifo_reference(), _finite_nonnegative(), _identifier(), Any, Feasibility and recommendation boundaries for the yard dispatcher. The… (+6 more)

### Community 38 - "_extract_pair_frame"
Cohesion: 0.22
Nodes (10): _canonical_protocol_error(), _extract_pair_frame(), _hashes(), Return a diagnostic when ``config`` is not the frozen H1 protocol., Reject malformed primary outcomes before any grid aggregation., Validate every source metric before selecting H1 policies., Validate and materialise the complete frozen confirmatory grid. Unlike the…, _validate_source_numeric() (+2 more)

### Community 39 - "test_notebook.py"
Cohesion: 0.25
Nodes (9): _cell_source(), Path, Contract checks for the central experiment notebook. The structural check…, The load profile must re-audit, analyse, and export persisted evidence., Load the notebook without requiring the optional notebook stack., _read_notebook_with_stdlib(), test_notebook_has_ordered_sections_and_validation_default(), test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() (+1 more)

### Community 40 - "ExecutionControls"
Cohesion: 0.19
Nodes (10): _controlled_view_hash(), _event_overlay_hash(), Hash the complete immutable seven-field control recipe., Hash projection semantics independently of stream-local bookkeeping., _controlled_projection_overlay_hash(), _controlled_projection_view_hash(), _controlled_rain_covered_latent_ids(), ExecutionControls (+2 more)

### Community 41 - "Notebook de experimentos PequiFlux"
Cohesion: 0.22
Nodes (8): Ambiente deliberado, Estado deste checkout, Execução limpa canônica, Fronteiras científicas, Layout de artefatos, Notebook de experimentos PequiFlux, Perfis, Testes

### Community 42 - "domain.py"
Cohesion: 0.19
Nodes (13): _dataset_canonical_bytes(), _expected_scenario_factors(), _latent_number(), _latent_resource(), _latent_sha256(), Mutable physical-domain values used by the independent digital model. The…, Return the canonical confirmatory factorial in protocol order., Hash canonical event-latent rows without importing the dataset layer. (+5 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (7): Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "FrozenTruck"
Cohesion: 0.15
Nodes (6): FrozenResource, FrozenTruck, Immutable truck record persisted in ``trucks.parquet``., Immutable resource record used by a frozen instance., test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order(), test_frozen_instance_service_order_keeps_truck_identity()

### Community 45 - "FrozenServiceTime"
Cohesion: 0.33
Nodes (3): FrozenServiceTime, One pre-generated service duration and its CRN provenance., test_frozen_service_rejects_forged_crn_draw_key()

## Knowledge Gaps
- **81 isolated node(s):** `pequiflux-experiment`, `graphify`, `graphify`, `Fontes normativas do projeto`, `Classificação correta do artefato visual` (+76 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ScenarioConfig` connect `ScenarioConfig` to `ComparisonStats`, `audit.py`, `H1Report`, `dataset.py`, `DatasetPlan`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `emulator.py`, `config.py`, `FrozenInstance`, `PairingError`, `ExperimentConfig`, `statistics.py`, `YardSnapshot`, `DatasetContractError`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Why does `ExperimentConfig` connect `ExperimentConfig` to `load_config`, `audit.py`, `ScenarioConfig`, `ComparisonStats`, `dataset.py`, `DatasetPlan`, `_extract_pair_frame`, `H1Report`, `validate_face_validation_receipt`, `config.py`, `FrozenInstance`, `AbortedStaging`, `Path`, `PairingError`, `statistics.py`, `DatasetContractError`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `_DaySimulation` connect `_DaySimulation` to `ScenarioConfig`, `dispatch.py`, `test_dispatch_emulator.py`, `Candidate`, `EventRecord`, `emulator.py`, `NoFeasibleCandidate`, `YardSnapshot`, `test_admissible_window_filters_cargo_before_priority_and_top_h0`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `_DaySimulation` (e.g. with `ScenarioConfig` and `DigitalModel`) actually correct?**
  _`_DaySimulation` has 12 INFERRED edges - model-reasoned connections that need verification._