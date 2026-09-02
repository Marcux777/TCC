# Experimento Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um projeto experimental autocontido cujo notebook central valida o protótipo, executa uma demonstração determinística, persiste e audita resultados, analisa H1 e exporta tabelas e figuras.

**Architecture:** Um pacote Python local contém as regras e os tipos; `TCC_experimentos.ipynb` é uma interface linear sobre essas APIs. O emulador e o modelo digital mantêm estados independentes e trocam somente eventos serializáveis. Toda execução usa configuração validada, namespace novo, manifesto e artefatos persistidos; análise e auditoria leem apenas esses artefatos.

**Tech Stack:** Python 3.11+, biblioteca padrão, NumPy, pandas, SciPy, PyArrow, Matplotlib, pytest, nbformat, nbclient e Jupyter nbconvert.

**Spec:** `experimento-notebook/docs/superpowers/specs/2026-09-01-experimento-notebook-design.md`

## Global Constraints

- Todo conteúdo novo deve permanecer em `experimento-notebook/`.
- Não importar nem copiar código de `../agro-yard-des-experiment`.
- Não modificar arquivos preexistentes na raiz do TCC.
- Usar “modelo digital”; “gêmeo digital” somente em explicação negativa da fronteira científica.
- H1 é confirmatória; A1 e A2 são critérios de aceitação; sincronização é diagnóstico, não A3.
- Toda fronteira é fail-fast: sem fallback, retry, substituição automática, resultado fabricado ou escolha do run “mais recente”.
- `RUN_PROFILE` aceita somente `validation`, `pilot`, `load-confirmatory` e `execute-confirmatory`.
- Não instalar ou atualizar dependências automaticamente.
- Não executar a matriz confirmatória durante desenvolvimento ou validação cotidiana.
- Não criar commits durante a implementação sem nova autorização explícita; a autorização anterior cobriu somente o commit da especificação.

## File Map

- `pyproject.toml`: metadados, dependências limitadas e configuração do pytest.
- `config/confirmatory.json`: configuração canônica, sementes e painel de políticas.
- `src/pequiflux_experiment/config.py`: validação, hash e configurações fatoriais.
- `src/pequiflux_experiment/manifest.py`: inventário do ambiente e manifesto do run.
- `src/pequiflux_experiment/domain.py`: tipos de domínio e snapshots canônicos.
- `src/pequiflux_experiment/events.py`: eventos públicos, ordenação e JSONL.
- `src/pequiflux_experiment/digital_model.py`: projeção independente de eventos.
- `src/pequiflux_experiment/dispatch.py`: factibilidade, domínio admissível e recomendações.
- `src/pequiflux_experiment/policies.py`: cinco políticas com a mesma interface.
- `src/pequiflux_experiment/emulator.py`: DES terminante de quatro etapas.
- `src/pequiflux_experiment/experiment.py`: perfis, matriz, namespace e persistência.
- `src/pequiflux_experiment/replay.py`: reconstrução e equivalência do estado final.
- `src/pequiflux_experiment/audit.py`: auditoria independente de A1/A2 e integridade.
- `src/pequiflux_experiment/statistics.py`: pareamento, estatísticas e decisão de H1.
- `src/pequiflux_experiment/export.py`: Parquet, CSV e figuras.
- `tests/`: cinco grupos de checks, um por risco material descrito na especificação.
- `TCC_experimentos.ipynb`: jornada linear, sem implementação duplicada.
- `README.md`: ambiente, execução, perfis e limites científicos.

---

### Task 1: Configuração congelada e manifesto

**Files:**
- Create: `experimento-notebook/pyproject.toml`
- Create: `experimento-notebook/config/confirmatory.json`
- Create: `experimento-notebook/src/pequiflux_experiment/__init__.py`
- Create: `experimento-notebook/src/pequiflux_experiment/config.py`
- Create: `experimento-notebook/src/pequiflux_experiment/manifest.py`
- Test: `experimento-notebook/tests/test_config_manifest.py`

**Interfaces:**
- Produces: `ExperimentConfig`, `ScenarioConfig`, `load_config(path)`, `factorial_scenarios(config)`, `config_hash(config)`, `create_run_directory(root, phase, commit, checksum)`, `build_manifest(...)`.
- Consumes: filesystem local e comandos Git somente leitura.

- [x] **Step 1: Escrever o teste RED de configuração e namespace**

```python
def test_config_is_frozen_and_run_directory_never_overwrites(tmp_path):
    config = load_config(CONFIG_PATH)
    assert config.seeds == tuple(range(101, 151))
    assert len(factorial_scenarios(config)) == 72
    assert len(config_hash(config)) == 64
    run_dir = create_run_directory(tmp_path, "validation", "abc1234", config_hash(config), now_utc="2026-09-01T12:00:00Z")
    with pytest.raises(FileExistsError, match="run directory already exists"):
        create_run_directory(tmp_path, "validation", "abc1234", config_hash(config), now_utc="2026-09-01T12:00:00Z")
    assert run_dir.name.startswith("validation__20260901T120000Z__abc1234__")
```

- [x] **Step 2: Executar o teste e confirmar RED**

Run: `rtk py -3 -m pytest tests/test_config_manifest.py -q`

Expected: FAIL durante importação porque `pequiflux_experiment.config` ainda não existe.

- [x] **Step 3: Implementar configuração, hash e manifesto mínimos**

Use dataclasses congeladas. `load_config` deve rejeitar chaves desconhecidas, sementes fora de ordem, painel diferente das cinco políticas e produto fatorial diferente de 72. `canonical_json` deve usar `sort_keys=True`, separadores compactos e UTF-8. `create_run_directory` deve usar `mkdir(exist_ok=False)`.

O JSON deve fixar:

```json
{
  "project_name": "PequiFlux - Experimento Reprodutivel",
  "protocol_version": "1.0.0",
  "hypothesis": "H1",
  "seeds": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150],
  "horizon_minutes": 720,
  "ordinary_window": 6,
  "priority_thresholds": [60, 30, 10],
  "throughput_margin_rate": 0.02,
  "minimum_throughput_margin": 2,
  "truck_counts": [60, 120, 180],
  "hopper_counts": [1, 2, 3],
  "scale_counts": [1, 2],
  "regimes": ["nominal", "peak", "critical_failure", "priority_shift"],
  "policies": ["fifo_strict", "fifo_flow_faithful", "priority_local", "fixed_score", "lexicographic"]
}
```

- [x] **Step 4: Executar o teste GREEN**

Run: `rtk py -3 -m pytest tests/test_config_manifest.py -q`

Expected: PASS.

- [x] **Step 5: Executar checagem de estilo estrutural**

Run: `rtk py -3 -m compileall -q src tests`

Expected: exit code 0.

### Task 2: Eventos e projeção independente do modelo digital

**Files:**
- Create: `experimento-notebook/src/pequiflux_experiment/domain.py`
- Create: `experimento-notebook/src/pequiflux_experiment/events.py`
- Create: `experimento-notebook/src/pequiflux_experiment/digital_model.py`
- Test: `experimento-notebook/tests/test_digital_model_replay.py`

**Interfaces:**
- Produces: `Truck`, `Resource`, `YardSnapshot`, `EventRecord`, `write_jsonl`, `read_jsonl`, `DigitalModel.apply(event)`, `DigitalModel.snapshot()`, `replay_events(events)`.
- Consumes: `ScenarioConfig` da Task 1.

- [x] **Step 1: Escrever o teste RED de isolamento e replay**

```python
def test_digital_model_uses_serialized_events_and_replays_identically(tmp_path):
    physical = YardSnapshot.empty()
    digital = DigitalModel.empty()
    event = EventRecord(time=0.0, sequence=1, kind="TRUCK_ARRIVED", payload={"truck_id": "T001", "priority": 0, "document_ok": True, "stage": 0})
    digital.apply(EventRecord.from_dict(event.to_dict()))
    physical.trucks["T001"] = Truck("T001", 0.0, "soy", 0, True, 0)
    assert digital.snapshot().canonical_dict() == physical.canonical_dict()
    physical.trucks["T001"].priority = 2
    assert digital.snapshot().trucks["T001"].priority == 0
    path = tmp_path / "events.jsonl"
    write_jsonl(path, [event])
    replayed = replay_events(read_jsonl(path))
    assert replayed.canonical_dict()["trucks"]["T001"]["priority"] == 0
```

- [x] **Step 2: Executar o teste e confirmar RED**

Run: `rtk py -3 -m pytest tests/test_digital_model_replay.py -q`

Expected: FAIL por módulos ausentes.

- [x] **Step 3: Implementar tipos, eventos e projeção**

`EventRecord` deve validar tempo finito, sequência positiva, tipo conhecido e payload obrigatório por tipo. `DigitalModel.apply` deve rejeitar sequência duplicada/regressiva e transições impossíveis. `snapshot()` deve devolver cópia profunda, nunca referência interna.

Eventos mínimos: `RUN_STARTED`, `TRUCK_ARRIVED`, `DOCUMENT_RELEASED`, `PRIORITY_CHANGED`, `RESOURCE_FAILED`, `RESOURCE_RECOVERED`, `SERVICE_STARTED`, `SERVICE_COMPLETED`, `DECISION_RECORDED`, `OPERATOR_DECISION`, `END_OF_DAY`.

- [x] **Step 4: Executar o teste GREEN**

Run: `rtk py -3 -m pytest tests/test_digital_model_replay.py -q`

Expected: PASS.

### Task 3: Restrições, políticas e emulador DES

**Files:**
- Create: `experimento-notebook/src/pequiflux_experiment/dispatch.py`
- Create: `experimento-notebook/src/pequiflux_experiment/policies.py`
- Create: `experimento-notebook/src/pequiflux_experiment/emulator.py`
- Test: `experimento-notebook/tests/test_dispatch_emulator.py`

**Interfaces:**
- Produces: `Candidate`, `DispatchContext`, `Recommendation`, `DispatchPolicy.select(candidates, context)`, `make_policy(name)`, `tiny_scenario(...)`, `run_day(scenario, seed, policy) -> DayResult`.
- Consumes: tipos/eventos da Task 2 e configuração da Task 1.

- [x] **Step 1: Escrever o teste RED de segurança e determinismo**

```python
@pytest.mark.parametrize("policy", POLICY_NAMES)
def test_blocked_truck_and_failed_resource_never_generate_command(policy):
    candidates = [candidate("T-blocked", document_ok=False), candidate("T-ok", document_ok=True)]
    context = dispatch_context(resource_available=False)
    with pytest.raises(NoFeasibleCandidate, match="resource unavailable"):
        recommend(candidates, context, make_policy(policy))

def test_same_seed_produces_identical_events_and_metrics():
    scenario = tiny_scenario(truck_count=8, hoppers=1, scales=1, regime="nominal")
    first = run_day(scenario, 101, make_policy("lexicographic"))
    second = run_day(scenario, 101, make_policy("lexicographic"))
    assert [e.to_dict() for e in first.events] == [e.to_dict() for e in second.events]
    assert first.metrics == second.metrics
    assert first.hard_constraint_violations == 0
```

- [x] **Step 2: Executar o teste e confirmar RED**

Run: `rtk py -3 -m pytest tests/test_dispatch_emulator.py -q`

Expected: FAIL por APIs ausentes.

- [x] **Step 3: Implementar o mínimo end-to-end**

O DES usa `heapq` com chave `(time, rank, sequence)`. O fluxo tem quatro operações: portaria, pesagem inicial, descarga e pesagem final; as duas pesagens compartilham o mesmo pool de balanças. Cada decisão gera `Recommendation`, `OPERATOR_DECISION=accept` e somente então um comando de serviço.

As políticas devem diferir apenas no ranking de candidatos já factíveis. `fixed_score` usa pesos congelados 0,45/0,35/0,20. `lexicographic` ordena prioridade, espera, estabilidade, afinidade e identificador determinístico. Nenhuma política recebe duração futura realizada.

- [x] **Step 4: Executar o teste GREEN**

Run: `rtk py -3 -m pytest tests/test_dispatch_emulator.py -q`

Expected: PASS para as cinco políticas sem retry.

### Task 4: Matriz, persistência, replay e auditoria

**Files:**
- Create: `experimento-notebook/src/pequiflux_experiment/experiment.py`
- Create: `experimento-notebook/src/pequiflux_experiment/replay.py`
- Create: `experimento-notebook/src/pequiflux_experiment/audit.py`
- Test: `experimento-notebook/tests/test_experiment_audit.py`

**Interfaces:**
- Produces: `run_experiment_matrix(...) -> RunBundle`, `load_run_bundle(run_dir)`, `replay_run(log_path)`, `audit_run(run_dir) -> AuditReport`.
- Consumes: `run_day`, eventos, snapshots, manifesto e hash das Tasks 1-3.

- [x] **Step 1: Escrever o teste RED de persistência e auditoria**

```python
def test_validation_bundle_is_complete_replayable_and_auditable(tmp_path):
    bundle = run_experiment_matrix(
        scenarios=[tiny_scenario()], seeds=[101, 102], policies=POLICY_NAMES,
        config=load_config(CONFIG_PATH), runs_root=tmp_path, phase="validation",
        now_utc="2026-09-01T12:00:00Z",
    )
    assert len(bundle.results) == 10
    assert bundle.manifest_path.exists()
    assert bundle.results_path.exists()
    report = audit_run(bundle.run_dir)
    assert report.a1_pass is True
    assert report.a2_structural_pass is True
    assert report.a2_human_audit_pending is True
    assert report.replay_pass is True

def test_missing_log_fails_without_fallback(tmp_path):
    bundle = build_validation_bundle(tmp_path)
    next(bundle.logs_dir.glob("*.jsonl")).unlink()
    with pytest.raises(AuditError, match="missing decision log"):
        audit_run(bundle.run_dir)
```

- [x] **Step 2: Executar o teste e confirmar RED**

Run: `rtk py -3 -m pytest tests/test_experiment_audit.py -q`

Expected: FAIL por APIs ausentes.

- [x] **Step 3: Implementar bundle imutável e auditor independente**

Persistir um JSONL por combinação cenário/semente/política, `results.csv`, `manifest.json` e `audit.json`. Escrever arquivos por caminho temporário no mesmo diretório e `Path.replace` após flush bem-sucedido. O auditor deve verificar cardinalidade esperada, unicidade da chave pareada, um único hash de configuração, SHA-256 dos logs, cabeçalhos, monotonicidade, campos A2, violações A1 e equivalência de replay.

- [x] **Step 4: Executar o teste GREEN**

Run: `rtk py -3 -m pytest tests/test_experiment_audit.py -q`

Expected: PASS.

### Task 5: Estatística confirmatória e exportação

**Files:**
- Create: `experimento-notebook/src/pequiflux_experiment/statistics.py`
- Create: `experimento-notebook/src/pequiflux_experiment/export.py`
- Test: `experimento-notebook/tests/test_statistics_export.py`

**Interfaces:**
- Produces: `evaluate_h1(results, config) -> H1Report`, `export_analysis(bundle, report, output_root) -> ExportedArtifacts`.
- Consumes: tabela pareada e configuração das Tasks 1 e 4.

- [x] **Step 1: Escrever o teste RED da regra científica**

```python
def test_h1_is_conjunctive_and_throughput_guard_can_block_support(tmp_path):
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    supported = evaluate_h1(rows, load_config(CONFIG_PATH))
    assert supported.h1_overall == "SUPPORTED"
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=3)
    blocked = evaluate_h1(rows, load_config(CONFIG_PATH))
    assert blocked.h1_overall == "NOT_SUPPORTED"
    artifacts = export_analysis(rows, blocked, tmp_path)
    assert artifacts.table_h1.exists()
    assert artifacts.summary_parquet.exists()
    assert artifacts.p95_figure.exists()

def test_incomplete_pairing_is_invalid_not_inconclusive():
    rows = synthetic_paired_rows(artifact_improvement=0.20, throughput_loss=0)
    rows.pop()
    with pytest.raises(PairingError, match="incomplete paired grid"):
        evaluate_h1(rows, load_config(CONFIG_PATH))
```

- [x] **Step 2: Executar o teste e confirmar RED**

Run: `rtk py -3 -m pytest tests/test_statistics_export.py -q`

Expected: FAIL por APIs ausentes.

- [x] **Step 3: Implementar análise e artefatos**

Calcular por estrato e comparador: mediana, IQR, diferença pareada, melhoria relativa, Wilcoxon unilateral, Hodges--Lehmann, bootstrap pareado com seed fixa, rank-biserial e guarda `max(2, 0.02*N)`. Aplicar Holm somente às duas hipóteses de estrato depois da conjunção entre comparadores. Exportar CSV/Parquet e três figuras a partir dos dataframes persistidos; texto digitado manualmente não entra nas figuras.

- [x] **Step 4: Executar o teste GREEN**

Run: `rtk py -3 -m pytest tests/test_statistics_export.py -q`

Expected: PASS.

### Task 6: Notebook central e documentação

**Files:**
- Create: `experimento-notebook/TCC_experimentos.ipynb`
- Create: `experimento-notebook/README.md`
- Create: `experimento-notebook/tests/test_notebook.py`
- Create: `experimento-notebook/results/raw/.gitkeep`
- Create: `experimento-notebook/results/processed/.gitkeep`
- Create: `experimento-notebook/results/tables/.gitkeep`
- Create: `experimento-notebook/results/figures/.gitkeep`
- Create: `experimento-notebook/runs/.gitkeep`

**Interfaces:**
- Produces: notebook executável com `RUN_PROFILE="validation"` por padrão e README com comandos literais.
- Consumes: todas as APIs das Tasks 1-5.

- [x] **Step 1: Escrever o teste RED do notebook**

```python
def test_notebook_validation_profile_executes_cleanly(tmp_path):
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    with patch.dict(os.environ, {"PEQUIFLUX_RUNS_ROOT": str(tmp_path / "runs"), "PEQUIFLUX_RESULTS_ROOT": str(tmp_path / "results")}):
        executed = NotebookClient(notebook, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(PROJECT_ROOT)}}).execute()
    errors = [output for cell in executed.cells if cell.cell_type == "code" for output in cell.get("outputs", []) if output.output_type == "error"]
    assert errors == []
    assert (tmp_path / "results" / "tables" / "table_audit.csv").exists()
```

- [x] **Step 2: Executar o teste e confirmar RED**

Run: `rtk py -3 -m pytest tests/test_notebook.py -q`

Expected: FAIL porque o notebook não existe.

- [x] **Step 3: Criar notebook linear e README**

O notebook deve conter as 14 seções da especificação, importar somente `pequiflux_experiment`, manter outputs pequenos e mostrar claramente a fase `validation`. O perfil deve vir de uma única célula e não pode ser alterado por descoberta automática de arquivos. O README deve documentar instalação deliberada, testes, execução limpa, perfis, diretórios e fronteiras das conclusões.

- [x] **Step 4: Executar o teste GREEN**

Run: `rtk py -3 -m pytest tests/test_notebook.py -q`

Expected: PASS com zero outputs de erro e artefatos mínimos produzidos.

### Task 7: Verificação integral e atualização do grafo

**Files:**
- Modify only if verification reveals a defect: files under `experimento-notebook/`

**Interfaces:**
- Consumes: projeto completo.
- Produces: evidência repetível de testes, notebook e isolamento do escopo.

- [x] **Step 1: Executar a suíte completa sem retry**

Run: `rtk py -3 -m pytest -q`

Expected: todos os testes PASS em uma única execução.

- [x] **Step 2: Executar compilação estática**

Run: `rtk py -3 -m compileall -q src tests`

Expected: exit code 0.

- [x] **Step 3: Executar o notebook limpo pelo caminho canônico**

Run: `rtk py -3 -m jupyter nbconvert --to notebook --execute TCC_experimentos.ipynb --output TCC_experimentos_executado.ipynb --ExecutePreprocessor.timeout=600`

Expected: exit code 0, zero outputs de erro e perfil `validation` identificado no manifesto.

- [x] **Step 4: Confirmar isolamento do escopo**

Run: `rtk git status --short`

Expected: além das mudanças preexistentes do usuário, somente caminhos sob `experimento-notebook/` são novos ou modificados nesta implementação.

- [x] **Step 5: Atualizar o grafo se o comando estiver disponível e o grafo existir**

Run somente se `graphify-out/graph.json` existir: `rtk graphify update .`

Expected: grafo atualizado sem tocar arquivos fora da saída gerenciada pelo Graphify. Se o grafo não existir, registrar “não aplicável”; não criar um grafo novo por fallback.

- [x] **Step 6: Relatar evidência sem commit**

Separar no handoff: testes criados, testes executados, comando do notebook, artefatos gerados, limitações, arquivos novos e ausência de execução confirmatória. Não chamar validação cotidiana de evidência de H1.
