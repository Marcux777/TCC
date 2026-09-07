# Graph Report - TCC  (2026-09-07)

## Corpus Check
- 41 files · ~96,251 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1186 nodes · 3416 edges · 50 communities (45 shown, 5 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 236 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `771a522f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_config
- experiment.py
- ScenarioConfig
- Any
- DatasetContractError
- _DaySimulation
- test_dispatch_emulator.py
- export.py
- PequiFlux — especificação vinculante do notebook experimental completo
- Candidate
- EventRecord
- validate_face_validation_receipt
- Truck
- config.py
- FrozenDataset
- FrozenInstance
- digital_model.py
- AbortedStaging
- Path
- _RecordingPolicy
- Projeto experimental reproduzível em notebook
- replay.py
- statistics.py
- ExperimentConfig
- Exact Invariants and Check Mapping
- emulator.py
- canonical_bytes
- YardSnapshot
- _build_event_latents
- EventLatentLedger
- DatasetPlan
- test_a2_structural.py
- ComparisonStats
- H1Report
- power_analysis_rhfs.py
- File Map
- dataset.py
- Any
- _validate_source_numeric
- test_notebook.py
- FrozenTruck
- Notebook de experimentos PequiFlux
- domain.py
- TCC PequiFlux
- FrozenServiceTime
- test_event_round_trip_and_replay_are_independent_from_physical_snapshot
- crn_digest
- AGENTS.md
- CLAUDE.md
- pequiflux-experiment

## God Nodes (most connected - your core abstractions)
1. `ExperimentConfig` - 81 edges
2. `DatasetContractError` - 79 edges
3. `load_config()` - 75 edges
4. `ScenarioConfig` - 58 edges
5. `_DaySimulation` - 53 edges
6. `Candidate` - 49 edges
7. `YardSnapshot` - 46 edges
8. `EventRecord` - 46 edges
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
- `AuditError` --uses--> `ReplayError`  [INFERRED]
  experimento-notebook/src/pequiflux_experiment/audit.py → experimento-notebook/src/pequiflux_experiment/replay.py

## Import Cycles
- None detected.

## Communities (50 total, 5 thin omitted)

### Community 0 - "load_config"
Cohesion: 0.05
Nodes (97): factorial_scenarios(), load_config(), Path, Require exact equality with every frozen field in confirmatory.json., Load and validate a JSON configuration from a local path., Enumerate the complete factorial in N, m, b, regime order., validate_confirmatory_config(), canonical_payload_schemas() (+89 more)

### Community 1 - "experiment.py"
Cohesion: 0.05
Nodes (83): _atomic_write_json(), _audit_bundle(), audit_run(), AuditError, AuditReport, _canonical_json(), _derived_log_metrics(), _pair_key() (+75 more)

### Community 3 - "Any"
Cohesion: 0.22
Nodes (3): Any, Expose a lightweight scenario-like object for downstream consumers., Return a detached, deterministically ordered state representation.

### Community 4 - "DatasetContractError"
Cohesion: 0.09
Nodes (53): _assert_finite_json(), _canonical_confirmatory_config(), DatasetContractError, _expected_instance_ids(), freeze_dataset(), _instance_headers_from_manifest(), _load_aborted_staging_internal(), load_freeze_receipt() (+45 more)

### Community 5 - "_DaySimulation"
Cohesion: 0.10
Nodes (10): canonical_allowed_cargo_types(), Return the immutable protocol matrix for a physical resource. Hopper 1 is…, _DaySimulation, Any, Return mean/p95 accumulated wait per truck and censored residual., Return a reproducible substream independent of dispatch order. The policy is…, Count queued and in-flight trucks that still need unload capacity. A scale-in…, Apply the protocol's mandatory-priority and short-window rules. (+2 more)

### Community 6 - "test_dispatch_emulator.py"
Cohesion: 0.14
Nodes (41): Execute one deterministic scenario using a local RNG and policy., Return a validated, compact ScenarioConfig for demonstrations., run_day(), tiny_scenario(), _validate_regime(), make_policy(), Construct one of the frozen policy-panel implementations., candidate() (+33 more)

### Community 7 - "export.py"
Cohesion: 0.10
Nodes (38): BaseException, _destination(), _ensure_targets_absent(), _export_analysis_core(), export_audit_table(), ExportedArtifacts, _figure_improvement(), _figure_p95() (+30 more)

### Community 8 - "PequiFlux — especificação vinculante do notebook experimental completo"
Cohesion: 0.06
Nodes (32): 10. Sensibilidade separada, 11. Gates de capacidade e execução pesada, 12. Fail-fast, no fallback, no retry e preservação da raiz, 13. Testes mínimos por risco material, 14. Artefatos de saída e mapa de publicação, 15. Critérios de aceitação, 16. Auto-revisão contra `main.pdf`, 1. Objetivo e fronteira científica (+24 more)

### Community 9 - "Candidate"
Cohesion: 0.11
Nodes (23): _activated_rules(), _build_justification(), Candidate, DispatchContext, _fifo_reference(), Alias matching the domain truck terminology., Alias for the current-stage entry timestamp., Immutable observable state supplied to a policy at one decision point. (+15 more)

### Community 10 - "EventRecord"
Cohesion: 0.14
Nodes (25): Replay ``events`` from an optional detached physical snapshot., Create an empty projection with no applied events., Apply one event atomically, rejecting ordering and state violations., replay_events(), Create the canonical empty yard state., EventRecord, One ordered, validated event in the experiment trace., _decision_chain_prefix() (+17 more)

### Community 11 - "validate_face_validation_receipt"
Cohesion: 0.16
Nodes (20): _validate_approved_face(), FaceValidationReport, materialize_face_validation_template(), _pending(), _project_root(), Any, Path, Verifiable human face-validation receipt gate. The receipt is an input… (+12 more)

### Community 12 - "Truck"
Cohesion: 0.10
Nodes (12): _cargo_tuple(), _finite_nonnegative(), _identifier(), The canonical state of one truck in the yard., Short alias useful at boundaries that use generic entity IDs., Compatibility alias for callers that used the earlier name., The canonical state of one service resource (scale, hopper, or similar)., Alias for ``clock`` at event-oriented boundaries. (+4 more)

### Community 13 - "config.py"
Cohesion: 0.07
Nodes (53): _as_finite_number(), _as_positive_integer_tuple(), _as_probability(), _as_text_tuple(), _as_tuple(), canonical_json(), _canonical_nested_fields(), CapacityRequirements (+45 more)

### Community 14 - "FrozenDataset"
Cohesion: 0.20
Nodes (4): Strictly validate a complete production freeze., validate_frozen_dataset(), FrozenDataset, Immutable view of a validated, persisted frozen dataset.

### Community 15 - "FrozenInstance"
Cohesion: 0.13
Nodes (20): _generate_one_candidate(), _generate_until_rejection(), _materialize_production_header(), _PayloadWriter, Collect deterministic rows for one complete production freeze., Materialize one complete immutable instance into the payload writer., Validate one fully generated candidate before any payload write. The priority-…, Private seam delegating to the canonical validator. Tests may monkeypatch this… (+12 more)

### Community 16 - "digital_model.py"
Cohesion: 0.23
Nodes (8): Event-applied digital projection of the physical yard., _canonicalize(), _freeze(), Any, Validated event records and their JSONL persistence boundary., Return a detached JSON-compatible representation., Normalize JSON values into detached dict/list/scalar containers., _thaw()

### Community 17 - "AbortedStaging"
Cohesion: 0.15
Nodes (10): _instance_event_latent_hashes(), plan_explicit_resample(), _provenance_payload(), Copy accepted source rows into a fresh writer without loading instances., Build an explicit one-attempt resample plan from retained STAGING state., Hash each instance's ordered event-latent rows as canonical JSONL bytes., _writer_from_aborted_staging(), AbortedStaging (+2 more)

### Community 18 - "Path"
Cohesion: 0.13
Nodes (34): _as_utc(), _build_manifest(), _create_staging_directory(), generate_synthetic_dataset(), _git_inventory(), _install_tiny_generation_fixture(), load_aborted_staging(), _load_frozen_dataset() (+26 more)

### Community 19 - "_RecordingPolicy"
Cohesion: 0.20
Nodes (4): _RecordingPolicy, _ScaleOutFirstPolicy, test_fixed_score_weights_waiting_before_priority_with_deterministic_ties(), test_lexicographic_h_uses_pressure_wait_reorder_affinity_then_stage_entry()

### Community 20 - "Projeto experimental reproduzível em notebook"
Cohesion: 0.10
Nodes (19): Auditoria e replay, Componentes e responsabilidades, Configuração e manifesto, Critérios de aceitação, Dependências e execução, Despacho e políticas, Domínio e eventos, Emulador e modelo digital (+11 more)

### Community 21 - "replay.py"
Cohesion: 0.23
Nodes (16): Any, Path, ValueError, Strict reconstruction of one persisted decision log., Raised when a persisted log cannot be reconstructed fail-closed., Reconstruct and return the final digital snapshot from one JSONL log., Internal replay evidence retained for the independent auditor., Return the canonical SHA-256 digest used in log state boundaries. (+8 more)

### Community 22 - "statistics.py"
Cohesion: 0.11
Nodes (33): _as_frame(), _bootstrap(), canonical_scenario_metadata(), _comparison_stats(), _decimal_relative_improvements(), _derived_stratum(), _finite_array(), _hodges_lehmann() (+25 more)

### Community 23 - "ExperimentConfig"
Cohesion: 0.13
Nodes (4): ExperimentConfig, The complete, immutable protocol configuration., _canonical_protocol_error(), Return a diagnostic when ``config`` is not the frozen H1 protocol.

### Community 24 - "Exact Invariants and Check Mapping"
Cohesion: 0.11
Nodes (18): Architecture, Data Flow, and Public Interfaces, Exact Invariants and Check Mapping, Final Verification and Handoff, Global Constraints, Notebook Experimental Completo Implementation Plan, Self-review against the spec, Task 10: Audited transactional exports, Task 11: Single literate notebook, explicit actions and subproject handoff (+10 more)

### Community 25 - "emulator.py"
Cohesion: 0.11
Nodes (21): ABC, DispatchBlocked, DispatchPolicy, feasible_candidates(), NoFeasibleCandidate, RuntimeError, Feasibility and recommendation boundaries for the yard dispatcher. The…, Raised when hard constraints leave no admissible dispatch choice. (+13 more)

### Community 26 - "canonical_bytes"
Cohesion: 0.12
Nodes (35): canonical_bytes(), Serialize any JSON-compatible value in the canonical byte representation., canonical_event_latent_schema(), _digest_bytes(), _finalize_freeze(), _load_json(), Write canonical checksums/manifest and return their linked digests., Validate an ABORTED staging namespace without requiring FREEZE.json. (+27 more)

### Community 27 - "YardSnapshot"
Cohesion: 0.21
Nodes (9): DigitalModel, Any, Extract the fields that identify a recommendation's selection. Decision records…, Apply an ordered event stream to an isolated ``YardSnapshot``., Return a detached copy that cannot mutate the projection., A complete, JSON-friendly observation of the yard at one instant., YardSnapshot, test_existing_truck_arrival_validates_priority_before_assignment() (+1 more)

### Community 28 - "_build_event_latents"
Cohesion: 0.29
Nodes (12): _build_event_latents(), _build_instance(), _draw_uniform(), _instance_id(), _priority_shift_eligible_count(), Count eligible trucks for a priority shift without materializing an instance., Create a deterministic NumPy generator from the complete CRN tuple., Materialize every event candidate before its disruption realization. (+4 more)

### Community 29 - "EventLatentLedger"
Cohesion: 0.22
Nodes (3): EventLatentLedger, Explicit alias for the immutable event-latent payload., Immutable, keyed collection of all pre-realisation event candidates. Rows are…

### Community 30 - "DatasetPlan"
Cohesion: 0.18
Nodes (4): DatasetPlan, Return detached, lightweight headers in canonical plan order., Return the zero-based ordinal immediately after ``instance_id``., Pure cardinality/ordering plan for the complete synthetic dataset.

### Community 31 - "test_a2_structural.py"
Cohesion: 0.30
Nodes (10): _build_bundle(), parametrize, Path, Regression checks for the explicit five-field A2 decision contract., _rewrite_first_decision(), test_audit_rejects_invented_rule_or_overlapping_exclusion(), test_audit_rejects_semantically_incoherent_a2_justification(), test_pending_human_audit_is_not_an_approved_a2_result() (+2 more)

### Community 33 - "H1Report"
Cohesion: 0.16
Nodes (19): Recompute and compare the report before any destination mutation., _validated_report(), _evaluate_h1_core(), _extract_pair_frame(), _first_column(), H1Report, _hashes(), _holm_adjust() (+11 more)

### Community 34 - "power_analysis_rhfs.py"
Cohesion: 0.35
Nodes (11): Namespace, BootstrapResult, estimate_mde80(), load_pairs(), main(), parse_args(), ndarray, Path (+3 more)

### Community 35 - "File Map"
Cohesion: 0.18
Nodes (10): Experimento Notebook Implementation Plan, File Map, Global Constraints, Task 1: Configuração congelada e manifesto, Task 2: Eventos e projeção independente do modelo digital, Task 3: Restrições, políticas e emulador DES, Task 4: Matriz, persistência, replay e auditoria, Task 5: Estatística confirmatória e exportação (+2 more)

### Community 36 - "dataset.py"
Cohesion: 0.07
Nodes (45): _coalesced_rain_rows(), _controlled_event_hash(), _controlled_view_hash(), _derive_controlled_instance(), _digest_value(), _disruption_payload_hash(), _event_overlay_hash(), _expected_scenario_factors() (+37 more)

### Community 37 - "Any"
Cohesion: 0.22
Nodes (4): _finite_nonnegative(), _identifier(), Any, Construct a candidate from a Task 2 ``Truck`` value.

### Community 38 - "_validate_source_numeric"
Cohesion: 0.40
Nodes (5): Reject malformed primary outcomes before any grid aggregation., Validate every source metric before selecting H1 policies., _validate_source_numeric(), _validate_source_p95(), Series

### Community 39 - "test_notebook.py"
Cohesion: 0.25
Nodes (9): _cell_source(), Path, Contract checks for the central experiment notebook. The structural check…, The load profile must re-audit, analyse, and export persisted evidence., Load the notebook without requiring the optional notebook stack., _read_notebook_with_stdlib(), test_notebook_has_ordered_sections_and_validation_default(), test_notebook_load_confirmatory_and_runtime_dependencies_are_explicit() (+1 more)

### Community 40 - "FrozenTruck"
Cohesion: 0.18
Nodes (5): _dataset_digest(), _freeze_dataset_value(), FrozenTruck, Immutable truck record persisted in ``trucks.parquet``., Detach a JSON-compatible value into immutable containers.

### Community 41 - "Notebook de experimentos PequiFlux"
Cohesion: 0.22
Nodes (8): Ambiente deliberado, Estado deste checkout, Execução limpa canônica, Fronteiras científicas, Layout de artefatos, Notebook de experimentos PequiFlux, Perfis, Testes

### Community 42 - "domain.py"
Cohesion: 0.15
Nodes (13): _controlled_rain_covered_latent_ids(), _dataset_canonical_bytes(), _latent_number(), _latent_resource(), _latent_sha256(), Decimal, Mutable physical-domain values used by the independent digital model. The…, Hash canonical event-latent rows without importing the dataset layer. (+5 more)

### Community 43 - "TCC PequiFlux"
Cohesion: 0.25
Nodes (7): Arquitetura dos artefatos, Classificação correta do artefato visual, Compilação, Enquadramento acadêmico, Estado atual, Fontes normativas do projeto, TCC PequiFlux

### Community 44 - "FrozenServiceTime"
Cohesion: 0.15
Nodes (7): FrozenResource, FrozenServiceTime, Immutable resource record used by a frozen instance., One pre-generated service duration and its CRN provenance., test_frozen_instance_round_trip_preserves_hash_cargo_and_service_order(), test_frozen_instance_service_order_keeps_truck_identity(), test_frozen_service_rejects_forged_crn_draw_key()

### Community 45 - "test_event_round_trip_and_replay_are_independent_from_physical_snapshot"
Cohesion: 0.23
Nodes (11): Path, Write events as one canonical JSON object per line., Read and validate every non-empty JSONL event line., read_jsonl(), write_jsonl(), _arrival_event(), _physical_snapshot(), Path (+3 more)

### Community 46 - "crn_digest"
Cohesion: 0.29
Nodes (6): crn_digest(), crn_seed(), Return the SHA-256 digest for one canonical CRN substream key., Map a CRN key to a stable non-negative integer seed., Select the preregistered 20% pilot by stable scenario hash order., select_pilot_configurations()

## Knowledge Gaps
- **81 isolated node(s):** `pequiflux-experiment`, `graphify`, `graphify`, `Fontes normativas do projeto`, `Classificação correta do artefato visual` (+76 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ScenarioConfig` connect `ScenarioConfig` to `load_config`, `experiment.py`, `ComparisonStats`, `H1Report`, `dataset.py`, `DatasetContractError`, `_DaySimulation`, `test_dispatch_emulator.py`, `EventRecord`, `config.py`, `crn_digest`, `FrozenInstance`, `digital_model.py`, `statistics.py`, `emulator.py`, `YardSnapshot`, `_build_event_latents`, `DatasetPlan`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Why does `ExperimentConfig` connect `ExperimentConfig` to `load_config`, `experiment.py`, `ComparisonStats`, `H1Report`, `dataset.py`, `DatasetContractError`, `validate_face_validation_receipt`, `config.py`, `crn_digest`, `FrozenInstance`, `AbortedStaging`, `Path`, `statistics.py`, `_build_event_latents`, `DatasetPlan`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `_DaySimulation` connect `_DaySimulation` to `ScenarioConfig`, `test_dispatch_emulator.py`, `Candidate`, `EventRecord`, `Truck`, `emulator.py`, `YardSnapshot`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `ExperimentConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ExperimentConfig` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DatasetContractError` (e.g. with `ExperimentConfig` and `ScenarioConfig`) actually correct?**
  _`DatasetContractError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `ScenarioConfig` (e.g. with `AuditError` and `AuditReport`) actually correct?**
  _`ScenarioConfig` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `_DaySimulation` (e.g. with `ScenarioConfig` and `DigitalModel`) actually correct?**
  _`_DaySimulation` has 12 INFERRED edges - model-reasoned connections that need verification._