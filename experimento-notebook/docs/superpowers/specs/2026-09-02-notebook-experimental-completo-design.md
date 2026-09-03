# PequiFlux — especificação vinculante do notebook experimental completo

**Data:** 2026-09-02  
**Escopo:** `C:\p\PequiFlux\TCC\experimento-notebook`  
**Status:** desenho arquitetural aprovado; este documento é o contrato de implementação  
**Fonte científica:** `C:\p\PequiFlux\TCC\main.pdf`, Capítulo 3 e Apêndices A–B  
**Regra de alteração:** qualquer mudança no protocolo, nos esquemas de dados, nos limiares, no painel de políticas ou nas regras estatísticas exige uma nova versão do protocolo e registro explícito; não há migração silenciosa.

## 1. Objetivo e fronteira científica

O projeto entrega um único notebook Jupyter, literate e reexecutável, que é a interface pública para construir o dataset sintético, executar as fases autorizadas, auditar os artefatos e gerar as análises do TCC. O notebook contém narrativa, tabelas de configuração, chamadas para APIs locais e resumos curtos de saída. A lógica do simulador, do despacho, da geração e da análise permanece em módulos Python pequenos e testáveis; não se duplica implementação em células.

O artefato é um **modelo digital** de um pátio de recebimento de grãos. Não se reivindica gêmeo digital: não há ativo físico individual pareado, telemetria contínua ou sincronização bidirecional. H1 é a única hipótese comparativa confirmatória. A1 (segurança operacional) e A2 (governança/rastreabilidade) são critérios de aceitação do artefato. Equivalência entre estado físico emulado e projeção digital, quando reportada, é diagnóstico de engenharia, nunca um A3 ou evidência de superioridade.

O projeto é autocontido. Não importa, copia ou consulta em tempo de execução o repositório adjacente `agro-yard-des-experiment`; não altera `main.tex`, `main.pdf`, `refs.bib` ou qualquer outro arquivo preexistente na raiz. A raiz pode permanecer suja. O estado Git é lido para o manifesto e nunca é limpo, ocultado, resetado, rebaseado ou sobrescrito.

### Barreira verificável de validação de face

O `main.pdf` é a fonte primária do protocolo. A afirmação da p. 27 sobre rodada cega por pares independentes não é receipt verificável e, sozinha, não pode ser elevada a `PASS`. O repositório deve conter o artefato de entrada obrigatório `inputs/face_validation_receipt.json` e o template versionado `inputs/face_validation_receipt.template.v1.json`. O receipt aprovado tem schema mínimo:

```json
{
  "status": "APPROVED",
  "protocol_version": "<igual ao config>",
  "config_hash": "<sha256>",
  "source_document": "main.pdf",
  "source_sha256": "<sha256 dos bytes do main.pdf>",
  "round_id": "<id não vazio>",
  "completed_at": "<timestamp ISO-8601 com fuso>",
  "blind": true,
  "reviewer_ids": [
    {"id": "<id>", "independent": true},
    {"id": "<id>", "independent": true}
  ],
  "rubric_path": "inputs/face_validation_rubric.v1.json",
  "rubric_version": "<versão>",
  "rubric_sha256": "<sha256>",
  "discrepancies": [
    {"item": "<id>", "decision": "ADJUSTED", "rationale": "<texto>"}
  ],
  "final_decision": "APPROVED"
}
```

`inputs/face_validation_rubric.v1.json` é um artefato real, versionado e serializado em JSON canônico UTF-8. Seu conteúdo mínimo congelado é:

```json
{
  "rubric_version": "face_validation_rubric.v1",
  "ratings": ["PASS", "REVISE", "FAIL"],
  "criteria": {
    "parameter_plausibility": {"question": "Os parâmetros estão dentro das faixas e unidades do protocolo?", "threshold": "todos os valores verificáveis no intervalo do PDF", "rationale_required": true},
    "scenario_semantic_feasibility": {"question": "O cenário é semanticamente executável nas quatro etapas?", "threshold": "recursos, precedências e capacidades coerentes", "rationale_required": true},
    "exemplar_trace_coherence": {"question": "Os exemplos e rastros correspondem às entradas e regras declaradas?", "threshold": "cada exemplar reconstrói sem contradição", "rationale_required": true},
    "hard_constraint_consistency": {"question": "As restrições rígidas são aplicadas sem exceção silenciosa?", "threshold": "nenhuma violação aceita", "rationale_required": true}
  },
  "decision_rule": "APPROVED somente com dois revisores independentes e todos os critérios PASS, ou divergências resolvidas e documentadas"
}
```

O template `face_validation_receipt.template.v1.json` referencia `rubric_path` e deixa `rubric_sha256`, IDs de revisores, discrepâncias e decisões vazios; a implementação nunca preenche esses valores humanos.

`validate_face_validation_receipt(path, config, pdf_path) -> FaceValidationReport` valida tipos, `status/final_decision=APPROVED`, `blind=true`, pelo menos dois `reviewer_ids` distintos com `independent=true`, `rubric_path='inputs/face_validation_rubric.v1.json'`, hashes SHA-256 do PDF e da rubrica, correspondência exata de `protocol_version`/`config_hash` e cada discrepância com `decision ∈ {ADJUSTED, MAINTAINED}` e `rationale` não vazio. O caminho da rubrica é resolvido dentro da raiz do projeto; traversal, caminho absoluto ou arquivo diverso são rejeitados. A implementação calcula os hashes reais de `main.pdf` e da rubrica; não aceita valores apenas porque foram declarados no JSON. Ausência, template não preenchido, campo incompleto, hash/versão divergente ou receipt de outro protocolo resulta em `FACE_VALIDATION=PENDING`, nunca `PASS`, com causa persistida.

O notebook sempre mostra `FACE_VALIDATION` e sua causa e materializa o template versionado por implementação, sem preencher IDs, decisões, hashes ou textos humanos. `validation` continua executável: gera e persiste um dataset sintético reduzido para todos os seus checks, sempre rotulado `non_confirmatory=true` e `FACE_VALIDATION=PENDING` quando o receipt aprovado não existe. `generate-synthetic` principal, `pilot`, `execute-confirmatory` e `sensitivity` exigem `FaceValidationReport.status=APPROVED` **antes** de criar namespace, escrever dataset ou executar policy-day; falham com a exceção causal se a barreira estiver ausente. `audit-analyze` pode auditar pacote existente sem receipt verificável, mas a publicação/promovibilidade científica fica `PENDING` e nenhuma conclusão confirmatória é alegada.

## 2. Protocolo congelado derivado do PDF

### 2.1 Fatorial, sementes e estratos

O desenho confirmatório é exatamente:

- `N ∈ {60, 120, 180}` caminhões/dia;
- `m ∈ {1, 2, 3}` moegas ativas;
- `b ∈ {1, 2}` balanças físicas no pool compartilhado entre pesagem inicial e final;
- regimes `nominal`, `peak`, `critical_failure` e `priority_shift`;
- sementes `101..150` (50 por configuração);
- políticas `fifo_strict`, `fifo_flow_faithful`, `priority_local`, `fixed_score` e `lexicographic`.

O produto `3 × 3 × 2 × 4` contém **72 configurações**. A ordem canônica dos loops é `N=(60,120,180)` externo, depois `m=(1,2,3)`, depois `b=(1,2)` e, por fim, `regime=(nominal,peak,critical_failure,priority_shift)` interno. Nessa ordem, `scenario_index` é exatamente `0..71` e o identificador é injetivo: `scenario_id=f"n{N}-m{m}-b{b}-{regime}"`. O carregador verifica a sequência completa, a correspondência índice–tupla e a regex do identificador; qualquer alteração de ordem, índice, nível ou nome é rejeitada.

Cada configuração × semente é uma instância de dia e há `72 × 50 = 3.600` instâncias. Cada instância será executada por cinco políticas, totalizando **18.000 policy-days**. Um policy-day é uma execução de uma política sobre uma instância congelada; não é uma nova geração de dados.

O índice nominal de carga é congelado antes da execução:

```text
rho(N,m,b) = N / min(36*m, 72*b)
```

Estratos são derivados somente de `rho`, independentemente da política: `low` se `rho < 0,70`, `medium` se `0,70 ≤ rho < 0,85` e `high` se `rho ≥ 0,85`. Com os níveis congelados, `low` contém 4 configurações (200 pares), `medium` contém 12 (600 pares) e `high` contém 56 (2.800 pares). `low` é controle operacional; H1 é avaliada separadamente em `medium` e `high`.

### 2.2 Horizonte, chegadas, serviços e perturbações

Cada dia terminante começa às 06:00 (`t=0`) com buffers vazios e termina às 18:00 (`720` minutos). Chegadas são condicionadas a `N` e usam quatro blocos 06–09, 09–11, 11–14 e 14–18. Para cada caminhão, o gerador escolhe o bloco com probabilidade proporcional a `peso_do_bloco × duração_do_bloco`, sorteia uniformemente dentro do bloco e ordena de forma estável por `(arrival_time, truck_id)`. Os pesos são `6, 3, 7, 2`; o regime `peak` usa `9, 2, 10, 2`. Caminhões não concluídos até o horizonte são remanescentes da fila final e não contam no throughput do dia.

As distribuições triangulares congeladas são realizadas durante a ação `generate-synthetic`, nunca durante `run_day`:

| operação | Triangular `(a, moda, b)` em minutos |
| --- | --- |
| entrada/gate | `(2, 4, 7)` |
| pesagem inicial | `(3, 5, 8)` |
| descarga/moega | `(12, 20, 35)` |
| pesagem final | `(3, 5, 8)` |

Também são materializados antes das políticas. Para cada caminhão, a prioridade é `p2` se o draw uniforme for `<0,15`, `p1` se for `<0,35` e `p0` caso contrário. O bloqueio documental é Bernoulli `0,03`; sua liberação usa `Tri(30,60,120)`. A tabela do `main.tex` congela falha-base Bernoulli `0,05` por turno, mas omite recurso/instante e sua relação com o regime crítico; esta especificação resolve essa lacuna como ruling de engenharia. Em `nominal`, `peak` e `priority_shift`, quando o Bernoulli dispara, selecionar uniformemente um recurso da lista canônica ordenada (`gate-1`, `scale-1..b`, `hopper-1..m`), iniciar em `U(240,480)` e durar `Tri(20,40,70)`. Em `critical_failure`, não sortear Bernoulli adicional: substituí-lo por exatamente uma falha forçada no gargalo, definido como `hopper-1` quando `36*m <= 72*b`, senão `scale-1`, com o mesmo início e duração. Assim não há dupla falha nem evento indefinido; toda falha é não preemptiva e o início efetivo fica adiado até a conclusão do atendimento corrente do recurso. O regime `priority_shift` sorteia o instante `U(240,480)`, promove exatamente `ceil(0,10*N)` caminhões elegíveis após o instante, em ordem `(arrival_time, truck_id)`, e aumenta a prioridade no máximo até `p2`. Para `m>=2`, chuva é Bernoulli `0,10` em cada um dos 24 blocos de 30 minutos, somente no primeiro hopper; blocos adjacentes são coalescidos e `m=1` fica protegido. Os eventos, horários, recursos afetados, durações e causas entram em `disruptions`; não são reamostrados pela política.

Controles estruturais: buffer intermediário de 12 caminhões; janela ordinária `H0=6`; limiares de pressão `tau2=10`, `tau1=30` e `tau0=60` minutos. A guarda de throughput usa a margem específica de cada par:

```text
delta(N) = max(2, 0,02*N) caminhões/dia
```

### 2.3 Painel de políticas

Todas as políticas recebem o mesmo instantâneo observável, o mesmo domínio de candidatos factíveis, as mesmas restrições rígidas, eventos, instância e semente. Só a regra de seleção muda.

1. `fifo_strict`: consulta a cabeça da fila **bruta** do estágio. O avaliador comum aplica as restrições rígidas a essa cabeça; se ela estiver inelegível, o recurso fica ocioso e registra o bloqueio, sem ultrapassá-la. É limite inferior descritivo, fora do teste substantivo de H1.
2. `fifo_flow_faithful`: escolhe o candidato factível mais antigo dentro do domínio admissível. É comparador primário.
3. `priority_local`: ordena candidatos factíveis por prioridade operacional e chegada à etapa. É comparador primário.
4. `fixed_score`: escore congelado `0,45*espera_normalizada + 0,35*prioridade + 0,20*afinidade_imediata`. É comparador dinâmico primário; pesos não são calibrados pelo piloto.
5. `lexicographic`: política proposta. Aplica pressão, espera, penalidade de reordenação, afinidade e desempates determinísticos em ordem lexicográfica, com prioridade mandatória antes de FIFO e expansão de candidatos críticos por pressão positiva.

O avaliador comum remove, antes do ranking de `fifo_flow_faithful`, `priority_local`, `fixed_score` e `lexicographic`, incompatibilidade carga–recurso, documento bloqueado, recurso indisponível/em falha, destino fechado por chuva, precedência não concluída e transição que excederia o buffer, formando `C_adm`. Essas quatro políticas recebem `C_adm`; `fifo_strict` recebe a cabeça da fila bruta e somente a checagem de factibilidade dessa cabeça. Todos compartilham restrições, eventos e schema de log; a diferença de seleção é intencional e corresponde aos comparadores do PDF. Sem candidato seguro, o motor registra o bloqueio e não emite comando. Intervenção humana só é aceita com perfil autorizado, motivo textual e verificação das mesmas restrições.

## 3. Notebook único e ações explícitas

`TCC_experimentos.ipynb` é a única interface de execução. A primeira célula executável contém uma constante literal, editável e visível:

```python
ACTION = "validation"
```

Os únicos valores aceitos são `validation`, `generate-synthetic`, `pilot`, `execute-confirmatory`, `audit-analyze` e `sensitivity`. Um valor desconhecido, vazio ou obtido por descoberta automática aborta com `InvalidAction`. Não há seleção por “último run”, variável de ambiente, estado de célula anterior ou perfil implícito. `DATASET_RUN_ID` e `RUN_ID` são identificadores explícitos nas células de entrada quando a ação exige artefato existente.

Cada ação é uma rota executável e possui um namespace, manifesto e resultado próprios:

| ação | operação obrigatória | pré-condições e saída |
| --- | --- | --- |
| `validation` | validar configuração/esquemas, gerar e persistir um dataset sintético reduzido para todos os checks, executar testes mínimos, demonstração curta, replay e suíte adversarial A1 | não executa campanha; publica evidência de engenharia rotulada `non_confirmatory=true` e `FACE_VALIDATION=PENDING` se não houver receipt aprovado |
| `generate-synthetic` | exigir receipt de face `APPROVED`, materializar 72 × 50 instâncias, validar, persistir, calcular hashes e congelar | publica um `synthetic` dataset completo antes de qualquer policy-day; rejeição aborta sem `FREEZE` |
| `pilot` | exigir receipt de face `APPROVED`, carregar um dataset congelado, selecionar previamente `ceil(0,20×72)=15` configurações e executar 50 sementes × 5 políticas | repete as instâncias do dataset sem removê-las; não recalibra H0, tau, pesos ou regras |
| `execute-confirmatory` | exigir receipt de face `APPROVED`, revalidar dataset, fazer gates de capacidade e executar a grade completa | exatamente 18.000 linhas policy-day, sem iniciar se um gate falhar |
| `audit-analyze` | carregar somente um `RUN_ID` explícito, auditar, materializar o workflow/amostra A2, calcular H1 e exportar | nenhum policy-day novo; H1 pode ser publicada com `A2_human=PENDING`, enquanto a aceitação global do artefato permanece `PENDING`; falha se o pacote não for confirmatório, completo e auditado |
| `sensitivity` | exigir receipt de face `APPROVED`, carregar o mesmo dataset congelado e executar a grade exploratória em namespace separado | resultados descritivos; nunca entram no IUT/Holm ou em linguagem confirmatória |

As células seguem sempre esta ordem: identificação/ACTION; manifesto e inventário; configuração; apresentação do protocolo; estado do dataset; execução da ação; leitura dos artefatos persistidos; auditoria/análise aplicável; exportação; resumo de limites. A célula de política só é alcançada depois de a célula de dataset confirmar `frozen=true`, cardinalidade e hash. O notebook não instala dependências, não cria dados escondidos e não contém chamadas a `random`/`numpy.random` para sintetizar uma instância.

## 4. Dataset sintético: geração visível, persistência e congelamento

### 4.1 Contrato da geração

`generate_synthetic_dataset(config, dataset_root, *, now_utc, generator_version) -> FrozenDataset` é a única API que pode gerar entradas. Ela enumera a ordem canônica de `scenario_index=0..71` e as sementes `101..150`, valida cada instância e publica o pacote somente quando as 3.600 instâncias estiverem presentes.

O notebook mostra, antes de executar qualquer política, as contagens `72`, `50`, `3.600`, os 72 `scenario_index`, a distribuição de `rho`/estrato, o número de rejeições e o hash do dataset. `pilot` e `execute-confirmatory` apenas leem esse pacote. Se o pacote estiver ausente, incompleto, alterado ou com hash divergente, a ação falha; não chama o gerador como fallback.

`validation` escreve um namespace próprio `runs/validation__<timestamp>__<config-hash>/validation_dataset/` com o mesmo schema de payload do dataset principal, porém com o subconjunto reduzido e determinístico declarado em `config/validation.json`. O manifesto desse pacote registra `non_confirmatory=true`, `validation_scope`, `validation_instance_count`, `FACE_VALIDATION` e sua causa. Cada check da ação recebe somente esse `FrozenValidationDataset` persistido (nunca um gerador ad hoc ou dados do namespace confirmatório); o pacote não pode alimentar `pilot`, `execute-confirmatory` ou `sensitivity`.

`config/validation.json` é exatamente:

```json
{
  "scenario_indices": [20, 12, 24],
  "seeds": [101],
  "policies": ["fifo_strict", "fifo_flow_faithful", "priority_local", "fixed_score", "lexicographic"]
}
```

A ordem declarada é parte do contrato e o loader verifica as três linhas: `20 = n60-m3-b2-nominal` (`low`), `12 = n60-m2-b2-nominal` (`medium`) e `24 = n120-m1-b1-nominal` (`high`). Assim, `validation` materializa exatamente três instâncias e quinze policy-days, sem alterar a grade confirmatória. A ação persiste `a1_adversarial_fixtures.jsonl` com exatamente oito fixtures canônicas derivadas dessas instâncias congeladas: `cargo_incompatible`, `document_blocked`, `resource_failed`, `hopper_rain_closed`, `buffer_full`, `human_override_invalid`, `incomplete_precedence` e `mandatory_priority`. Cada linha contém `fixture_id`, `base_instance_id`, `base_instance_hash`, `derivation`, `transformation`, `dispatch_context` completo e canônico e `expected_outcome`; o hash é `sha256` dos demais campos serializados canonicamente. O `dispatch_context` fixa `context_time=720`, `stage='unload'`, `resource_id='hopper-1'`, identidades `T-001`/`T-002` da instância-base e os campos `candidates`, `resource_state`, `completed_operations`, `document`, `cargo`, `priority`, `downstream_buffer` e `operator_command`. Para as sete violações/inelegibilidades o resultado esperado é `BLOCK_NO_COMMAND`; em `mandatory_priority`, a fila contém `T-002` com `p2` e `T-001` com `p0`, e o resultado esperado é `SELECT_T-002_P2`. O gerador copia identidades e cargas da `FrozenInstance`, aplica somente a transformação declarada e persiste o contexto completo antes do teste. A suíte A1 lê exclusivamente os oito contextos persistidos, nunca constrói estados durante o check. O manifesto e o relatório registram `validation_scope_hash=sha256(canonical_bytes(config/validation.json)+":"+canonical_bytes(a1_adversarial_fixtures.jsonl))`; qualquer divergência de configuração, ordem, instância-base ou fixture invalida a ação.

O mapeamento fixture--instância é congelado para tornar o arquivo reexecutável:

| `fixture_id` | `base_instance_id` | `transformation` | `expected_outcome` |
| --- | --- | --- | --- |
| `f01` | `s20-seed101` | tornar o `cargo_type` incompatível com todos os recursos elegíveis da etapa | `BLOCK_NO_COMMAND` |
| `f02` | `s12-seed101` | manter `document_status=BLOCKED` até a tentativa de despacho | `BLOCK_NO_COMMAND` |
| `f03` | `s24-seed101` | marcar o recurso canônico da etapa como falho/indisponível | `BLOCK_NO_COMMAND` |
| `f04` | `s20-seed101` | fechar `hopper-1` por chuva no instante da tentativa | `BLOCK_NO_COMMAND` |
| `f05` | `s12-seed101` | preencher o buffer intermediário até a capacidade 12 | `BLOCK_NO_COMMAND` |
| `f06` | `s24-seed101` | submeter override humano que viola uma restrição rígida | `BLOCK_NO_COMMAND` |
| `f07` | `s12-seed101` | remover uma operação precedente obrigatória do conjunto concluído | `BLOCK_NO_COMMAND` |
| `f08` | `s20-seed101` | fixar fila com `T-002` em `p2` e `T-001` em `p0` para prioridade mandatória | `SELECT_T-002_P2` |

A validação de cenário exige exatamente `N` caminhões, pelo menos um recurso em cada etapa obrigatória, taxas e eventos dentro das faixas congeladas, ausência de colapso degenerado e `media_entrada < media_pesagem < media_descarga`. H1, throughput observado ou qualquer resultado de política nunca pode justificar aceitar/rejeitar um cenário.

### Emenda de governança sem retry

Esta especificação datada é uma emenda operacional posterior e prevalece, para a implementação do notebook, sobre a frase “nova amostragem” do `main.tex`. Uma rejeição de candidato é registrada e aborta a ação corrente **sem criar `FREEZE.json`**. Antes de abortar, a implementação finaliza atomicamente os payloads parciais, `manifest.json` e `checksums.sha256` e grava `STAGING.json` com `status='ABORTED'`, `manifest_hash`, `checksums_hash`, `staging_root_hash=sha256(manifest_hash+':'+checksums_hash)`, `accepted_instance_ids`, `rejected_instance_ids` e `next_candidate_ordinal`. O staging e o `rejection_log` ficam preservados; cada linha inclui `seed`, motivo, `automatic_resample_status='PROHIBITED'`, `next_action='EXPLICIT_RESAMPLE_REQUIRED'` e o `dataset_id` abortado. Nenhuma nova amostra ocorre na mesma ação.

Uma nova execução explícita de `generate-synthetic` pode receber `RESAMPLE_SOURCE_DATASET_ID`, `source_staging_root_hash` e a lista exata de `instance_id` rejeitados. Antes de escrever, valida toda a cadeia do `STAGING.json` (manifesto, checksums e `staging_root_hash`) e a partição entre aceitos, rejeitados e `next_candidate_ordinal`; só então cria novo `dataset_id`/namespace. Os aceitos são conservados com registros em bytes canônicos e `instance_hash` idênticos (não se promete identidade dos bytes físicos de Parquet). Cada rejeitado recebe exatamente uma nova amostra com `generation_attempt=previous+1`; os candidatos ainda não gerados continuam em ordem canônica com `generation_attempt=0`, até completar 3.600 instâncias válidas ou encontrar nova rejeição. `resample_provenance.json` registra `source_dataset_id`, `source_staging_root_hash`, lista de `instance_id`, `generation_attempt`, hashes canônicos dos registros/instâncias aceitos e a ação que autorizou a operação. Nova rejeição aborta novamente sem freeze. Não há loop/retry automático; a implementação da “nova amostragem” do PDF é esta ação explícita e auditável, não um fallback. O dataset só congela ao atingir exatamente 3.600 instâncias válidas, mantendo desenho, potência e cardinalidade; rejeição nunca depende de H1 ou desempenho.

### 4.2 Esquema mínimo e arquivos

O diretório de dataset é imutável por contrato depois de `FREEZE.json`:

```text
runs/
└── synthetic__<timestamp>__<commit>__<config-hash>/
    ├── scenario_index.parquet
    ├── trucks.parquet
    ├── service_times.parquet
    ├── disruptions.jsonl
    ├── manifest.json
    ├── rejection_log.jsonl
    ├── resample_provenance.json  # somente quando esta foi uma ação explícita de resample
    ├── checksums.sha256
    ├── FREEZE.json               # somente dataset válido completo
    └── STAGING.json              # somente rejeição abortada; nunca junto com FREEZE
```

`scenario_index.parquet` contém exatamente uma linha por configuração: `scenario_index`, `scenario_id`, `N`, `hopper_count`, `scale_count`, `regime`, `rho`, `stratum`, `protocol_version`, `config_hash` e `generator_version`. A ordem do arquivo é a ordem do fatorial e faz parte do hash. O carregador exige índices consecutivos `0..71`, a ordem `N` externo → `m` → `b` → `regime` interno e `scenario_id` exatamente em `n{N}-m{m}-b{b}-{regime}`.

`trucks.parquet` contém uma linha por caminhão de cada instância (`instance_id=f"s{scenario_index:02d}-seed{seed:03d}"`): `scenario_index`, `scenario_id`, `seed`, `truck_id`, `arrival_minute`, `cargo_type`, `priority`, `document_status`, `stage`, `eligible_resources` e `truck_record_hash`. A cardinalidade de cada instância é exatamente `N`; o carregador valida a regex `^s(?:0[0-9]|[1-6][0-9]|7[01])-seed(?:10[1-9]|1[1-4][0-9]|150)$` e a reconstrução injetiva de índice e seed.

`service_times.parquet` contém uma linha por `(instance_id, truck_id, operation)` para as quatro operações, com `duration_min`, parâmetros de origem, `draw_key`, `crn_version` e hash. Não há geração tardia de duração.

`disruptions.jsonl` contém eventos exógenos canônicos ordenados por `(instance_id, time, event_rank, resource_id_or_empty, truck_id_or_empty, sequence)`: falha/retorno de recurso, chuva início/fim, mudança de prioridade, bloqueio/liberação documental e demais eventos previstos. O registro inclui causa, recurso, operação, duração/retorno e `payload_hash`.

A precedência temporal é congelada por `event_rank` numérico. As diferenças dentro da mesma classe do `main.tex` são este ruling determinístico: `service_completion=0`, `resource_recovery=10`, `rain_end=11`, `resource_failure=12`, `rain_start=13`, `document_release=20`, `priority_change=21` e `arrival=30`. Ordenar sempre por `(time,event_rank,resource_id_or_empty,truck_id_or_empty,sequence)` e somente despachar depois de aplicar todo o lote de eventos no mesmo timestamp. Recuperação/fim precedem nova falha/início; em uma colisão, a indisponibilidade nova prevalece. A ordem mantém as classes do PDF: liberações de serviço; falha/recuperação/chuva; prioridade/liberação documental; chegada.

`manifest.json` inclui `dataset_id`, fase `synthetic`, `protocol_version`, `config_hash`, `scenario_index_hash`, `instance_count=3600`, `scenario_count=72`, `seed_count=50`, cardinalidades por tabela, `crn_version`, `generator_version`, parâmetros congelados, `freeze_status`, horário UTC, commit e estado sujo/limpo da raiz, versão Python/dependências, inventário de CPU/RAM/GPU, caminhos e a lista ordenada de SHA-256 somente dos cinco payloads (`scenario_index.parquet`, `trucks.parquet`, `service_times.parquet`, `disruptions.jsonl`, `rejection_log.jsonl`), contagem de rejeições e a afirmação de que nenhum policy-day foi executado. O manifesto não contém hash de si próprio, de `FREEZE.json` ou de `checksums.sha256`.

Quando houver resample, o manifesto inclui também `resample_provenance={path,sha256,source_dataset_id,source_staging_root_hash,resampled_instance_ids,generation_attempts}`. `path` é relativo ao namespace novo; o loader recalcula o SHA-256 real de `resample_provenance.json` em bytes do serializer canônico (JSON UTF-8, chaves ordenadas, separadores `(',', ':')`, LF final único, sem `NaN`/`Infinity`) e rejeita ausência, mismatch, caminho divergente, lista de IDs divergente ou tentativa incompatível. No dataset inicial, `resample_provenance=null` e o arquivo deve estar ausente. Esse objeto adicional é referenciado pelo manifesto (e, portanto, coberto por `manifest_hash`), mas não entra nos cinco payloads científicos nem em `checksums.sha256`.

`rejection_log.jsonl` existe mesmo quando vazio. Cada linha tem `dataset_id`, `candidate_ordinal`, `scenario_index`, `instance_id`, `seed`, `generation_attempt`, `reason_code`, `validator`, `observed`, `expected`, `candidate_hash`, `automatic_resample_status='PROHIBITED'`, `next_action='EXPLICIT_RESAMPLE_REQUIRED'` e timestamp. Ausência, corrupção, alteração ou ordem inválida do log é erro de auditoria.

`checksums.sha256` cobre **somente** os cinco payloads, em linhas ordenadas canônicas (`nome_relativo<TAB>sha256_hex`, uma linha por payload). `FREEZE.json` contém `manifest_hash`, `checksums_hash` e `dataset_root_hash`; os próprios `FREEZE.json` e `checksums.sha256` ficam fora da lista de payloads. Carregadores recalculam e comparam esses hashes antes de fornecer uma instância. O congelamento é lógico e verificável por hash; não se depende de atributo de arquivo somente-leitura do sistema operacional.

#### Integridade e hash sem ciclo

Os bytes canônicos de cada payload são aqueles produzidos pelo serializer versionado (Parquet determinístico com schema/ordem de linhas fixos; JSONL UTF-8 com newline final e ordem de eventos definida). Para eliminar ciclo de hash, a construção é obrigatoriamente:

```text
checksums.sha256   = linhas ordenadas dos cinco payloads
manifest.json      = configuração + lista ordenada dessas linhas; sem hash de si/FREEZE/checksums
manifest_hash      = sha256(bytes_canônicos(manifest.json))
checksums_hash     = sha256(bytes_canônicos(checksums.sha256))
dataset_root_hash  = sha256(manifest_hash + ":" + checksums_hash)
FREEZE.json         = {manifest_hash, checksums_hash, dataset_root_hash}
```

Nenhum desses três hashes pode ser usado para alterar retroativamente payload, manifesto ou checksums. A validação falha se a lista do manifesto divergir da lista de `checksums.sha256`, se a ordem canônica mudar ou se qualquer hash incluir `manifest.json`, `FREEZE.json` ou `checksums.sha256`.

`manifest.json` e `FREEZE.json` usam JSON canônico UTF-8: chaves ordenadas, separadores exatamente `(',', ':')`, ausência de `NaN`/`Infinity` (`allow_nan=false`) e exatamente um newline LF final. Esses bytes canônicos, sem normalização posterior, são os bytes usados nos hashes.

### 4.3 Common random numbers (CRN)

Toda aleatoriedade é resolvida na geração com substreams independentes derivados por SHA-256 da tupla completa `(crn_version, scenario_index, seed, generation_attempt, entity_id, operation/event)`. A geração inicial usa `generation_attempt=0`; um resample explícito usa exatamente `generation_attempt=previous+1` somente nos `instance_id` rejeitados, mantendo os aceitos byte a byte. O nome da política não participa da chave. Chegadas, prioridades, documentos, tempos de serviço e perturbações são, portanto, idênticos para as cinco políticas de uma instância (inclusive depois de resample). O manifesto grava o esquema CRN e cada policy-day grava `dataset_hash`/`instance_hash`.

`run_day(instance, policy, ...)` recebe um `FrozenInstance` completo, valida cardinalidade, hashes, quatro tempos por caminhão e lista de eventos e executa somente o DES. A função não aceita apenas `(ScenarioConfig, seed)`, não chama gerador, não acessa relógio aleatório, não sorteia duração/disrupção e não cria defaults. Qualquer campo ausente, extra ou divergente falha antes do primeiro evento. O resultado inclui a instância consumida, eventos, métricas, snapshots físico/digital e hashes de replay.

## 5. Arquitetura e mapa de interfaces

```text
experimento-notebook/
├── TCC_experimentos.ipynb
├── README.md
├── pyproject.toml
├── requirements.lock
├── config/confirmatory.json
├── config/validation.json
├── inputs/
│   ├── face_validation_rubric.v1.json
│   ├── face_validation_receipt.template.v1.json
│   └── face_validation_receipt.json
├── src/pequiflux_experiment/
│   ├── __init__.py
│   ├── config.py
│   ├── face_validation.py
│   ├── validation.py
│   ├── manifest.py
│   ├── capacity.py
│   ├── dataset.py
│   ├── domain.py
│   ├── events.py
│   ├── digital_model.py
│   ├── dispatch.py
│   ├── policies.py
│   ├── emulator.py
│   ├── experiment.py
│   ├── replay.py
│   ├── audit.py
│   ├── a2.py
│   ├── statistics.py
│   ├── sensitivity.py
│   └── export.py
├── tests/
├── runs/
└── results/{raw,processed,tables,figures}/
```

### Interfaces públicas obrigatórias

- `config.py`: `ExperimentConfig`, `ScenarioConfig`, `load_config`, `factorial_scenarios`, `validate_confirmatory_config`, `config_hash`. Estruturas são imutáveis; chaves desconhecidas, níveis fora do protocolo e produto diferente de 72 são rejeitados.
- `face_validation.py`: `validate_face_validation_receipt(path, config, pdf_path) -> FaceValidationReport` e `materialize_face_validation_template(path)`. Valida receipt humano sem preencher valores; ausência/divergência é `PENDING`.
- `validation.py`: `build_validation_dataset(config, validation_config, run_root) -> FrozenValidationDataset` e `run_validation_checks(dataset) -> ValidationReport`. Persiste o subconjunto reduzido versionado em `validation_dataset/`, força `non_confirmatory=true`, carrega o estado `FACE_VALIDATION`/causa e impede que checks leiam o gerador ou o namespace confirmatório.
- `manifest.py`: `create_run_directory` (colisão recusa), `build_manifest` e `write_manifest`. Registra commit/dirty state, ambiente, capacidade observada, hashes e caminhos; nunca modifica Git.
- `capacity.py`: `inspect_capacity(workload, requirements) -> CapacityReceipt` e `require_capacity(receipt)`. A receipt é persistida e contém memória/disco disponíveis, CPU lógico, GPU detectada, processo concorrente, estimativa de pico e decisão. Gate falho levanta `CapacityGateError` com causa.
- `dataset.py`: `generate_synthetic_dataset`, `resample_synthetic_dataset`, `load_frozen_dataset`, `validate_frozen_dataset`, `freeze_dataset`, `select_pilot_configurations`. `resample_synthetic_dataset` exige `RESAMPLE_SOURCE_DATASET_ID` e a lista exata de `instance_id` rejeitados, copia aceitos byte a byte, usa uma única `generation_attempt+1` por rejeitado e grava `resample_provenance.json`. As APIs publicam atomicamente em diretório novo e recusam colisão, alteração pós-freeze ou cardinalidade incompleta.
- `domain.py`/`events.py`: tipos de caminhão, recurso, snapshot, evento serializável, ordenação determinística, `write_jsonl`/`read_jsonl`; nenhuma estrutura mutável do emulador atravessa a fronteira.
- `digital_model.py`: projeção independente por eventos, `DigitalModel.apply`, `snapshot`, `replay_events`. Sequência duplicada/regressiva, transição impossível e hash divergente são fatais.
- `dispatch.py`/`policies.py`: filtro de restrições rígidas, domínio admissível, ranking e justificativa; `make_policy`; interface única para as cinco políticas. Despacho não muta o emulador.
- `emulator.py`: `run_day(instance: FrozenInstance, policy: DispatchPolicy | str) -> DayResult`. DES terminante de quatro etapas, balança reentrante compartilhada, intervenção explícita e zero amostragem.
- `experiment.py`: `run_policy_days(dataset, policies, phase, run_root, capacity_receipt=None) -> RunBundle`; `load_run_bundle`; persistência de uma linha por policy-day, logs JSONL por instância/política, manifesto e auditoria. `execute-confirmatory` só aceita a grade canônica completa.
- `replay.py`: `replay_run` e comparação de snapshots. Lê somente logs persistidos; não reconstrói por chamada ao emulador.
- `audit.py`: `audit_run`, verificação de checksums, cardinalidade, A1, A2 estrutural, replay, monotonicidade, logs e mistura de hashes. Auditoria não confia no relatório do produtor.
- `a2.py`: `build_a2_sample`, `apply_rubric`, `compute_cohen_kappa`, `persist_a2_review`. A API sempre materializa workflow, amostra e rubrica por cenário, mas não fabrica rótulos humanos. Um avaliador pode concluir a revisão; Cohen κ só é calculado quando houver dois. Ausência de revisão deixa `A2_human=PENDING`, nunca `NOT_SUPPORTED`.
- `statistics.py`: `evaluate_h1(confirmatory_bundle, config) -> H1Report`, `paired_dataframe`, estimadores robustos e decisão IUT/Holm. Aceita apenas `execute-confirmatory` completo, auditado e com hash único.
- `sensitivity.py`: `run_sensitivity(dataset, grid, ...)` e `summarize_sensitivity`; namespace e schema separados de H1, sem p-valores confirmatórios.
- `export.py`: `export_analysis` e `export_audit_table`; todas as tabelas/figuras leem DataFrames derivados de artefatos persistidos e recusam sobrescrever destinos existentes.

O fluxo de estado é:

```text
dataset generator -> persisted/frozen instance
frozen instance -> run_day -> event log + metric row
event log -> digital projection/replay -> independent audit
audited confirmatory rows -> H1 IUT/Holm -> tables/figures
```

## 6. Piloto e campanha confirmatória

O piloto seleciona antes do freeze estatístico `ceil(0,20×72)=15` `scenario_index`, por hash canônico de `scenario_index` e versão do protocolo, e executa as 50 sementes e cinco políticas dessas configurações. São `15 × 50 × 5 = 3.750` policy-days exploratórios. O `pilot_selection_hash` e a lista são registrados. O piloto verifica cardinalidades, métricas finitas, ausência de degeneração, violações e estabilidade de replay; não escolhe parâmetros, não altera o dataset e não consome instâncias da campanha principal.

A campanha confirmatória reexecuta as mesmas instâncias congeladas, inclusive as 15 do piloto, com a mesma semente e CRN. `execute-confirmatory` recusa qualquer subconjunto, ordem diferente, política faltante, seed faltante ou cenário alterado; só libera análise quando houver exatamente 18.000 linhas únicas em `(scenario_index, seed, policy)` e logs correspondentes. O namespace de confirmação é distinto do namespace do dataset e do piloto.

Cada policy-day persiste uma linha com `dataset_id`, `instance_id`, `scenario_index`, `scenario_id`, `seed`, `policy`, `config_hash`, `dataset_hash`, `stratum`, `regime`, `N`, `m`, `b`, cardinalidade/event count, todas as métricas, contagem A1, campos A2, hashes de estado e log. A escrita é progressiva e atômica; a análise só lê o pacote fechado.

## 7. Métricas obrigatórias do PDF

Para cada policy-day, por caminhão quando aplicável e também agregadas por cenário/estrato, devem existir:

1. **Espera acumulada em fila:** soma, nas quatro etapas, do intervalo entre elegibilidade e início do serviço; reportar `p50`, `p95`, média, IQR e espera censurada dos remanescentes. É a métrica primária de H1.
2. **Throughput:** número de caminhões que concluem o ciclo dentro de 720 minutos; remanescentes entram explicitamente na fila final e não podem ser abandonados para inflar o ganho. Reportar contagem, taxa e mediana pareada.
3. **Tempo total no sistema:** chegada ao pátio até conclusão da pesagem final, com mediana/IQR e distribuição por estrato.
4. **Makespan:** primeira chegada até a última conclusão registrada no dia; não substituir por tempo de CPU.
5. **Utilização e ociosidade:** tempo ocupado por recurso sobre horizonte disponível (líquida) e sobre horizonte bruto; ociosidade é o complemento, por recurso e agregado.
6. **Estabilidade e reordenação:** inversões entre filas consecutivas, quebras de FIFO, deslocamento máximo/médio e frequência de replanejamento. Reportar também ativação da janela ordinária `H0`, candidatos mandatórios e expansão crítica.
7. **Factibilidade e justificativa legível:** violações de restrições rígidas, bloqueios, comandos emitidos, cobertura dos cinco campos A2, intervenções aceitas/rejeitadas e hashes para reconstrução.
8. **CO2 estimado:** `E_CO2 = sum(wait_queue_i/60) × 0,8 galão/h × 10,18 kg CO2/galão`; deslocamento, partida a frio, poeira, eletricidade e ciclo de vida ficam fora. `0,5–1,0 galão/h` é sensibilidade. É indicador exploratório, nunca parte de H1/IUT.

Os arquivos de resultado não podem omitir uma métrica por não haver valor: caso uma métrica não seja definida para uma instância, a execução falha com a causa e não grava `0`, `NaN` ou texto de sucesso. Todos os valores publicados são derivados dos eventos/logs persistidos.

## 8. Inferência confirmatória de H1

### 8.1 Unidade, efeito e comparadores

Unidade pareada é `(scenario_index, seed)`; políticas compartilham a mesma instância. Para cada estrato `s ∈ {medium, high}` e comparador primário `c ∈ {fifo_flow_faithful, priority_local, fixed_score}`, calcular por policy-day:

```text
g_i = (p95_comp,i - p95_lexicographic,i) / p95_comp,i
```

Denominador zero, pares ausentes, duplicados ou hashes misturados são `INVALID_INPUT`, não resultado inconclusivo. Reportar mediana, IQR, diferença pareada, melhoria percentual, Hodges–Lehmann, bootstrap pareado de 5.000 reamostragens, IC 95% e rank-biserial `r_rb`.

Se mais de 50% das diferenças pareadas de p95 forem exatamente zero em um estrato/comparador, registrar a contagem de zeros e executar adicionalmente o teste de sinais unilateral exato. Esse teste é apenas robustez/sensibilidade; nunca substitui o Wilcoxon, o IUT ou o ajuste de Holm e não altera a decisão de H1.

### 8.2 IUT com guarda de throughput

Para cada `(s,c)`, o componente de espera é unilateral: testar `H0: mediana(g_i - 0,15) ≤ 0` contra `H1: mediana(g_i - 0,15) > 0` pelo Wilcoxon signed-rank, além de exigir estimativa mediana `g ≥ 0,15`. A guarda de throughput usa, para cada par, `d'_i = (T_lex,i - T_comp,i) + delta(N_i)` e testa `H0: mediana(d') ≤ 0` contra `H1: mediana(d') > 0` pelo Wilcoxon unilateral. Os dois componentes devem rejeitar com `alpha=0,05` e a mediana de throughput deve respeitar `delta(N)`.

O teste `(s,c)` é um **intersection–union test**: `IUT(s,c) = espera_pass ∧ throughput_pass`. O p-valor do comparador é o maior p-valor de seus componentes. No nível do estrato, o artefato só vence quando o IUT passa contra os três comparadores primários. `fifo_strict` permanece descritivo e não entra no IUT.

### 8.3 Holm e linguagem permitida

Os dois p-valores globais de estrato (`p_IUT_medium` e `p_IUT_high`) recebem uma única correção sequencial de Holm (`alpha=0,05`). Não há correção de multiplicidade entre comparadores dentro de um IUT. `low`, métricas secundárias, A1, A2, CO2 e sensibilidade são reportados descritivamente.

`H1=SUPPORTED` somente se ambos os estratos substantivos passarem o IUT contra todos os três comparadores e os dois p-valores Holm ajustados rejeitarem. Caso contrário, `H1=NOT_SUPPORTED`; grade incompleta ou inválida é `H1=INVALID_INPUT`. Nunca usar piloto, sensibilidade, média agregada dos estratos ou uma política exploratória para preencher um componente ausente.

## 9. A1 adversarial e A2 independente

### 9.1 A1 adversarial

`validation` executa `run_a1_adversarial_suite` desserializando exclusivamente os oito `dispatch_context` completos persistidos em `a1_adversarial_fixtures.jsonl`: `cargo_incompatible`, `document_blocked`, `resource_failed`, `hopper_rain_closed`, `buffer_full`, `human_override_invalid`, `incomplete_precedence` e `mandatory_priority`. Cada contexto fixa `context_time=720`, `stage='unload'`, `resource_id='hopper-1'`, identidades `T-001`/`T-002` da instância-base, `candidates`, `resource_state`, `completed_operations`, `document`, `cargo`, `priority`, `downstream_buffer` e `operator_command`; sete têm `expected_outcome='BLOCK_NO_COMMAND'` e `mandatory_priority` tem `T-002=p2`, `T-001=p0` e `expected_outcome='SELECT_T-002_P2'`.

A1 passa somente se a suíte adversarial e a auditoria da campanha tiverem zero violações, nenhum comando em estado bloqueado, nenhum override ilegal aceito e nenhuma exceção engolida. Um resultado nominal limpo sem a suíte adversarial não é A1. A suíte é persistida (`a1_adversarial.jsonl` e `a1_report.json`) e não é usada para gerar p-valores de H1.

### 9.2 A2: estrutura, amostra, rubrica e kappa

A2 exige os cinco campos de justificativa definidos no PDF para cada recomendação/intervenção: (1) caminhão e etapa; (2) recurso escolhido ou bloqueado; (3) regras ativadas; (4) motivo da decisão; (5) quebra de FIFO. O auditor verifica estruturalmente 100% dos logs, incluindo candidatos considerados, exclusões e decisão humana.

A revisão manual opcional usa somente os logs da política `lexicographic`, por cenário (`scenario_index`) e sem substituir o denominador por uma amostra global. `audit-analyze` sempre gera o workflow, a amostra e a rubrica versionada; ele não inventa rótulos, decisões de revisor ou kappa. Se `D_s` é o número de recomendações dessa política no cenário `s`, selecionar sem reposição, por ordem de hash de `decision_id`,

```text
n_s = min(D_s, max(50, ceil(0,10 * D_s)))
```

Assim cada cenário com pelo menos 50 decisões tem amostra mínima de 50 e 10%; cenário menor é auditado integralmente. A seleção, o hash do log e a versão da rubrica são persistidos em `a2_sample.jsonl`.

Quando houver dois avaliadores, eles devem ser independentes e cegos para resultados, rotulando cada item `PASS`, `FAIL` ou `UNCLEAR` conforme a rubrica versionada (`a2_rubric_v1`): identificação, recurso/estado, regra ativada, motivo legível, FIFO/intervenção e respeito às restrições. Um único avaliador também pode concluir conteúdo e rubrica. `a2_review.csv` guarda rótulos e motivos; havendo dois avaliadores, `a2_kappa.json` guarda Cohen κ por cenário e global. Se κ < 0,60, a rubrica deve ser revisada antes do congelamento final e o pacote permanece `PENDING`; não se usa esse desacordo para declarar suporte. A2 humana só pode ser marcada como `COMPLETE` quando a amostra estiver materializada, os itens não tiverem `FAIL`/`UNCLEAR` e a cobertura estrutural estiver completa. Avaliador único sem conclusão, avaliadores ausentes ou revisão ainda não realizada deixam `a2_human_audit_status=PENDING` (e κ `not_applicable` quando não houver dois), nunca `NOT_SUPPORTED`; não há reamostragem ou retry para esconder desacordo. `audit-analyze` pode calcular e publicar H1 com `A2_human=PENDING`, mas a aceitação global do artefato continua `PENDING` até a revisão amostral concluída. A2 estrutural e A2 humana são reportadas separadamente.

## 10. Sensibilidade separada

`sensitivity` não altera o dataset, a configuração confirmatória ou os resultados do IUT. Usa namespace, manifesto e tabelas próprios e as mesmas instâncias/CRN. Na intensidade `high`, somente as taxas Bernoulli de bloqueio documental, falha base e chuva são multiplicadas por `2,0` e limitadas a `1,0`; eventos forçados e suas durações permanecem inalterados. A grade de estresse cruza `H0 ∈ {4,6,8}`, buffer `∈ {8,12,16}`, multiplicador de limiares `∈ {0,75;1,00;1,25}` e intensidade `{base, high}`. Essa grade roda `lexicographic` e os três comparadores primários.

O painel exploratório roda somente a configuração base, em namespace separado, com as seguintes políticas determinísticas: `myopic_predicted_delay` escolhe o menor slack (`tau_prioridade - waiting`), depois prioridade decrescente, chegada ao estágio e `truck_id`; `window_without_stability` preserva a mesma elegibilidade e janela `H0=6` da proposta, remove somente o componente de reordenação da chave lexicográfica e desempata por prioridade decrescente, chegada e id; `batch_by_cargo` prefere o tipo de carga do último caminhão servido no recurso, depois chegada e id, e, sem último caminhão, usa chegada e id. Nenhuma dessas políticas ou a grade de estresse entra em H1/IUT/Holm.

Reportar medianas, IQR e bootstrap descritivo de 95%; não aplicar Holm, não usar p-valores para H1 e não promover uma variante vencedora a política principal. A sensibilidade de CO2 (`0,5–1,0 galão/h`) também é exploratória. Qualquer conclusão forte vira hipótese futura e requer nova versão/pré-registro.

Para a grade de estresse, publicar o resumo `ROBUST` somente pela fração **conjunta**: em cada célula completa, o ganho mediano de p95 deve ser `>0` contra **todos** os três comparadores primários e o throughput deve permanecer dentro da margem contra **todos** eles; a mesma célula conta uma única vez, e a fração conjunta deve ser `≥75%` das células completas. Reportar essa fração/contagem conjunta como decisão; frações e contagens por comparador são apenas diagnóstico. A regra é não confirmatória, não altera H1/IUT/Holm; pacote ou qualquer célula incompleta é `INVALID_INPUT`, nunca `NON_ROBUST`.

## 11. Gates de capacidade e execução pesada

Antes de `execute-confirmatory`, `capacity.py` faz uma inspeção única do workload completo (18.000 policy-days), dos limites declarados no `config/confirmatory.json`, do espaço livre, da RAM, CPU, GPU e processos concorrentes. Considere `GiB = 1024**3` bytes. A estimativa é numérica e congelada: `estimate_output_bytes = sum(32768*N)` sobre cada policy-day + `dataset_size_bytes`; `required_disk_bytes = ceil(1.25 * estimate_output_bytes) + 5 GiB`. O gate requer `free_disk_bytes >= required_disk_bytes`. Para RAM, reserva 2 GiB e 1 GiB por worker: `workers = min(4, logical_cpu - 1, floor((free_ram_bytes - 2 GiB) / 1 GiB))`; exige `workers >= 1` e pelo menos 4 GiB livres observados.

A receipt registra:

- cardinalidade estimada de linhas/logs e espaço de dataset/resultados;
- RAM livre e pico estimado, espaço livre e margem operacional;
- CPU lógico e workers autorizados;
- GPU/driver apenas como inventário; GPU não é requisito, pois o caminho CPU é canônico;
- processo/proprietário concorrente detectado e decisão `PASS`/`BLOCKED`;
- timestamp, versão da inspeção, TTL e hashes do dataset, configuração e workload.

O gate bloqueia se capacidade mínima, espaço, executável/dependência ou propriedade de recursos não puderem ser provados. Outro processo Python/Jupyter/pytest vivo que aponte ao projeto bloqueia, exceto o kernel atual e seus descendentes registrados na receipt. Não se troca algoritmo, precisão, escopo, sementes, iterações ou validação para caber. A receipt expira em 60 segundos (`TTL=60s`); ela é revalidada imediatamente antes de criar o namespace da campanha, e os hashes de dataset, configuração e workload devem casar exatamente. Não há espera ativa, retry, kill de processo ou fallback automático. O erro inclui operação, recurso, workload e causa original.

`validation`, `pilot` e `sensitivity` são executáveis sem iniciar a carga confirmatória; a campanha completa nunca é executada como efeito colateral de `Run All` padrão.

## 12. Fail-fast, no fallback, no retry e preservação da raiz

Todas as fronteiras validam entrada e estado antes de mutar o destino. São erros fatais: configuração ou hash divergente; dataset sem `FREEZE.json`; arquivo ausente/corrompido; rejeição ou cardinalidade incompleta; `run_day` sem instância pronta; policy-day duplicado; mistura de hashes; log fora de ordem; replay divergente; violação rígida; A1 ou A2 **estrutural** incompleto; grade H1 parcial; gate de capacidade bloqueado; dependência/executável ausente; destino já existente. `A2_human=PENDING` é um estado válido para `audit-analyze` e não bloqueia a publicação de H1; bloqueia somente a aceitação global final do artefato até a revisão prevista.

Exceções preservam `__cause__` e incluem operação, `dataset_id`/`run_id`, `scenario_index`, seed, política, caminho e configuração pertinente. Não se engolem exceções, não se escrevem `None`/`NaN` como sucesso, não se procura outro artefato, não se faz retry e não se sobrescreve pasta. Qualquer nova tentativa deve ser uma nova ação explícita e namespace novo.

Todos os writes ficam sob `experimento-notebook/`. `runs/` e `results/` recusam colisões e publicam arquivos por staging/rename atômico. Nenhum comando de limpeza ou alteração Git é permitido. O manifesto registra a raiz suja sem tratá-la como falha de produto.

## 13. Testes mínimos por risco material

O conjunto permanente é o menor que observa cada invariável no limite correto; smoke test, execução manual e receipt são evidências adicionais, não substitutos dos checks repetíveis.

| mudança/risco | invariável distinta | check mínimo repetível |
| --- | --- | --- |
| configuração/fatorial | 72 configurações, 50 seeds, política exata e hash estável | `test_config_contract_and_hash` |
| barreira de face | receipt/template versionados, hash real de `main.pdf` e protocolo exato; ausência ou divergência fica `FACE_VALIDATION=PENDING` antes de qualquer namespace principal | `test_face_validation_receipt_gate` |
| validação reduzida | `config/validation.json` fixa `[20,12,24]`, seed `[101]`, cinco políticas, 3 instâncias/15 policy-days; dataset e oito contextos A1 completos persistidos, `validation_scope_hash` estável e todos os checks consumindo somente esses artefatos | `test_validation_dataset_persisted_and_non_confirmatory` |
| geração/freeze | 3.600 instâncias, payloads/manifest/rejeição/checksums/freeze presentes, cardinalidades e rejeição explícita | `test_generate_freezes_complete_dataset` |
| resample explícito | source/rejected IDs exatos, aceitos copiados byte a byte, uma tentativa `generation_attempt+1` em toda derivação SHA, provenance canônica referenciada e hashada no manifesto (ausente/null no inicial), nova rejeição aborta sem retry | `test_explicit_resample_provenance_and_abort` |
| consumo da instância | `run_day` não amostra nem gera dados escondidos; falta de campo falha antes do DES | `test_run_day_requires_frozen_instance` |
| CRN | cinco políticas recebem os mesmos tempos/eventos e `instance_hash` | `test_crn_is_policy_independent` |
| restrições/A1 | estados adversariais nunca produzem comando ilegal | `test_a1_adversarial_suite_fail_closed` |
| isolamento/replay | emulador e modelo digital não compartilham mutabilidade; JSONL reconstrói estado | `test_replay_matches_independent_projection` |
| persistência de matriz | chave `(scenario,seed,policy)` é única e 18.000 no confirmatório | `test_confirmatory_cardinality_and_pairing` |
| A2 | cinco campos estruturais, amostra `max(50,10%)` por cenário, rubrica e κ reportado quando houver dois avaliadores | `test_a2_sample_rubric_and_kappa_contract` |
| inferência | IUT conjuntivo, guarda de throughput e Holm apenas nos dois estratos | `test_iut_holm_and_invalid_pairing` |
| sensibilidade conjunta | `ROBUST` usa as mesmas células com ganho e throughput contra os três comparadores; pacote/célula incompleta é `INVALID_INPUT` e a saída fica fora da H1 | `test_joint_sensitivity_robustness_and_invalid_input` |
| capacidade/fail-fast | gate ocupado/insuficiente bloqueia sem iniciar campanha ou retry | `test_capacity_gate_blocks_with_cause` |
| jornada literate | `ACTION=validation` executa top-to-bottom sem erro e publica manifest/auditoria | `test_notebook_actions_and_validation_run` |

Não adicionar testes duplicados para a mesma falha. Qualquer check acima desse conjunto precisa declarar o novo risco material que cobre.

## 14. Artefatos de saída e mapa de publicação

Um run de dataset publica os arquivos da Seção 4. Um run de policy-days publica, no mínimo:

O run de `validation` publica, adicionalmente, um pacote próprio e reduzido (nunca misturado ao confirmatório):

```text
runs/validation__<run_id>/validation_dataset/
├── scenario_index.parquet
├── trucks.parquet
├── service_times.parquet
├── disruptions.jsonl
├── rejection_log.jsonl
├── a1_adversarial_fixtures.jsonl  # oito contextos completos derivados das 3 instâncias congeladas
└── manifest.json        # non_confirmatory=true, FACE_VALIDATION e causa
```

`resample_provenance.json` acompanha somente um namespace criado pela ação explícita de resample e vincula o novo dataset ao `source_dataset_id`, ao `source_staging_root_hash`, à lista exata de rejeitados, aos hashes dos aceitos copiados e a `generation_attempt+1`.

```text
runs/<run_id>/
├── manifest.json
├── results.csv                 # 1 linha por policy-day
├── decision_logs/*.jsonl       # eventos enriquecidos e A2
├── a1_adversarial.jsonl        # quando aplicável
├── audit.json
├── a2_sample.jsonl             # audit-analyze
├── a2_review.csv               # audit-analyze, somente se houver rótulos submetidos
└── a2_kappa.json               # audit-analyze, somente se houver dois avaliadores
```

`results/` recebe somente de artefatos auditados:

```text
results/
├── raw/experiment_runs.parquet
├── raw/decision_logs.jsonl
├── processed/summary.parquet
├── tables/table_h1.csv
├── tables/table_throughput.csv
├── tables/table_metrics.csv
├── tables/table_audit.csv
├── tables/table_a2.csv
├── figures/p95_by_policy.pdf
├── figures/paired_improvement.pdf
├── figures/throughput_waiting_tradeoff.pdf
└── figures/sensitivity_*.pdf
```

Cada export valida assinatura/formato, cardinalidade, hash de origem e ausência do destino antes de publicar. `table_h1.csv` contém componentes p95/throughput, IUT, p-valores brutos e Holm, estimativas e decisão; `table_metrics.csv` contém todas as oito famílias de métricas; `table_audit.csv` expõe A1, A2 estrutural/humana, replay, checksums e pendências. A ausência de Parquet/`pyarrow` é bloqueador explícito.

## 15. Critérios de aceitação

O desenho está implementado quando, em ambiente compatível e sem retry:

1. existe um único `TCC_experimentos.ipynb` literate com exatamente as seis ações válidas e nenhuma seleção implícita;
2. `generate-synthetic` mostra e persiste 72 configurações × 50 seeds antes de qualquer policy-day, com `scenario_index`, `trucks`, `service_times`, `disruptions`, `manifest`, `rejection_log`, checksums e freeze verificável;
2a. `inputs/face_validation_receipt.template.v1.json` e `inputs/face_validation_receipt.json` são materializados; o loader verifica tipos, hashes reais de `main.pdf`/rubrica e correspondência de protocolo, mantém `FACE_VALIDATION=PENDING` quando ausente/divergente e bloqueia `generate-synthetic`, `pilot`, `execute-confirmatory` e `sensitivity` antes de criar namespace; `validation` persiste o pacote reduzido e rotulado `non_confirmatory=true`;
2b. rejeição aborta a geração sem `FREEZE.json`, preservando staging/log; somente uma nova ação explícita com `RESAMPLE_SOURCE_DATASET_ID` e IDs exatos copia aceitos byte a byte, amostra cada rejeitado uma vez com `generation_attempt+1` e grava `resample_provenance.json`, sem retry automático;
3. `run_day` aceita apenas instância pronta e reproduzida; não há geração ou aleatoriedade oculta;
4. CRN é comprovado por hashes/receipts e os cinco policy-days de uma instância compartilham entradas exógenas;
5. `pilot` executa a amostra pré-fixada de 15 configurações (20% arredondado para cima), sem recalibrar ou remover dados;
6. `execute-confirmatory`, após gate de capacidade, produz exatamente 18.000 policy-days sobre 3.600 instâncias; cada comparação usa os 3.600 pares de instância (um por cenário-semente) no total, com logs completos;
7. as oito famílias de métricas do PDF são calculadas com unidades/definições e CO2 marcado exploratório;
8. H1 usa somente média/alta, os três comparadores primários, IUT de p95 + throughput e Holm entre os dois estratos; nenhuma grade incompleta gera suporte;
9. A1 inclui suíte adversarial persistida e zero violações; A2 tem cobertura estrutural integral e workflow/amostra manual `max(50,10%)` por cenário, rubrica versionada e Cohen κ somente quando houver dois avaliadores, mantendo `A2_human=PENDING` na ausência de revisão;
10. `sensitivity` é separada, descritiva e não altera H1; a etiqueta `ROBUST` exige, nas mesmas células completas, ganho mediano p95 `>0` e throughput dentro da margem contra todos os três comparadores em pelo menos 75% delas, enquanto pacote/célula incompleta é `INVALID_INPUT`;
11. gates de capacidade, dependências, hashes, colisões, logs e replay falham cedo com causa preservada; não há fallback, retry ou resultado fabricado;
12. testes mínimos por risco passam em uma única execução e o notebook `validation` conclui do início ao fim, sem tocar arquivos da raiz suja.

Nenhum resultado de `validation`, `pilot` ou `sensitivity` pode ser chamado de evidência confirmatória. H1 só pode ser apresentada após `audit-analyze` sobre um namespace `execute-confirmatory` completo, imutável e independentemente auditado; A1/A2 continuam critérios de aceitação, não alegações de superioridade.

## 16. Auto-revisão contra `main.pdf`

- [x] Fatorial 3 × 3 × 2 × 4, 72 configurações, seeds 101–150, quatro regimes e 18.000 policy-days preservados.
- [x] Quatro etapas, balanças compartilhadas/reentrantes, chegadas, serviços triangulares, eventos e controles `H0`, `tau`, buffer e `delta(N)` preservados.
- [x] Métricas da Tabela 10, políticas da Tabela 11, estratos da Tabela 7 e separação de sensibilidade do Apêndice B explicitados.
- [x] H1 p95, throughput, Wilcoxon, Hodges–Lehmann, bootstrap, teste de sinais condicionado a zeros, IUT e Holm estão vinculantes; baixa congestão é controle.
- [x] A1 foi ampliada para suíte adversarial sem transformar A1 em hipótese; A2 inclui os cinco campos, workflow/amostra por cenário, rubrica, κ quando houver dois avaliadores e estado `PENDING` quando não houver revisão.
- [x] O dataset pré-política, CRN, `run_day` sem geração escondida, precedência numérica de eventos, gates de capacidade e fail-fast tornam a execução reproduzível e auditável.
- [x] A falha-base e o regime crítico têm ruling de recurso/instante único; a emenda de governança torna rejeição sem retry explícita; sensibilidade reporta `ROBUST` apenas sob a regra de 75% e `INVALID_INPUT` para pacote incompleto.
- [x] A barreira de face exige receipt/template versionados e hash verificável de `main.pdf`; `validation` deixa dataset reduzido persistido e não confirmatório; resample explícito deixa provenance; sensibilidade decide `ROBUST` pela fração conjunta das mesmas células.
- [x] Nenhum caminho de fallback, retry, cópia de repositório adjacente ou alteração da raiz suja é permitido.

**Nota de drift (não decisória):** `main.pdf` pretérito permanece a fonte primária congelada. Qualquer alteração futura em `main.tex` deve ser registrada como drift (versão, data, diff e impacto) apenas para acompanhamento; não pode sobrepor valores, regras ou hashes do PDF. Para adotar mudança, é obrigatória nova versão do protocolo e novo receipt/namespace, nunca uma atualização silenciosa.

Preocupações residuais deliberadas: a revisão humana A2 é opcional; um avaliador pode concluir conteúdo/rubrica, dois permitem reportar κ e κ < 0,60 exige revisão da rubrica antes do congelamento, mantendo `PENDING` até resolver; a disponibilidade real de CPU/RAM/disco é verificada somente no gate da campanha; e rejeições do gerador devem permanecer visíveis, mesmo que o dataset canônico seja construído por validação determinística sem rejeições.
