# Notebook de experimentos PequiFlux

Este diretório contém a interface linear para a validação do modelo digital do
despacho online de caminhões. O notebook [TCC_experimentos.ipynb](TCC_experimentos.ipynb)
orquestra as APIs públicas de `pequiflux_experiment`; as regras permanecem nos
módulos em `src/`.

## Ambiente deliberado

O ambiente suportado deste fechamento é CPython 3.13.x em Windows x64;
`requires-python = ">=3.13,<3.14"`. Python 3.11 não é suportado. Outras séries
não são cobertas por esta verificação. A instalação limpa, a versão exata,
o kernel e o resultado atual da suíte estão registrados em
[closure/baseline.md](docs/closure/baseline.md).

O `pyproject.toml` declara intervalos de dependências e `requirements.lock`
fixa as versões do ambiente. Em PowerShell, a partir deste diretório,
confirme o interpretador e use uma `.venv` nova. Se ela já existir, preserve-a
e escolha outro caminho vazio, ajustando os comandos seguintes:

```powershell
rtk proxy py -3.13 --version
rtk proxy py -3.13 -m venv .venv
rtk proxy .\.venv\Scripts\python.exe -m pip install -r requirements.lock
rtk proxy .\.venv\Scripts\python.exe -m pip check
rtk proxy .\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name python3 --display-name "PequiFlux (Python 3.13)"
rtk proxy .\.venv\Scripts\python.exe -m jupyter kernelspec list --json
```

`requirements.lock` reproduz as versões exatas do ambiente validado e já inclui
o pacote local como `-e .`. O lock inclui `numpy`, `pandas`, `scipy`, `pyarrow`,
`matplotlib`, `pytest`, `nbformat`, `nbclient`, `nbconvert` e todas as transitivas
instaladas. `ipykernel` fornece o kernel nativo local usado pela execução do
notebook. Não substitua o lock por uma instalação solta com versões divergentes;
o notebook não instala dependências durante a execução.

## Testes

No diretório `experimento-notebook/`, o comando de teste é:

```powershell
rtk proxy .\.venv\Scripts\python.exe -m pytest -q
rtk proxy .\.venv\Scripts\python.exe -m compileall -q src
```

`tests/test_notebook.py` sempre valida a estrutura JSON com a biblioteca padrão.
Quando `nbformat`, `nbclient` e `nbconvert` estão disponíveis, o teste de execução
executa o notebook inteiro em uma raiz temporária e exige zero outputs de erro e
`results/tables/table_audit.csv`. Se algum desses três módulos estiver ausente,
o teste falha explicitamente com `BLOCKED execution gate`; isso não é convertido
em `skip` ou em sucesso.

O notebook executa uma seleção explícita de testes rápidos das seis áreas do
pacote, seguida de sua própria demonstração, matriz de validação, replay e
auditoria persistida. A seleção não repete os testes de materialização e
proveniência de datasets; esses permanecem na suíte completa do comando acima.
Os números históricos abaixo descrevem rodadas anteriores. O baseline desta
auditoria e os logs integrais ficam em [closure/baseline.md](docs/closure/baseline.md).

## Execução limpa canônica

Depois da instalação deliberada, execute a partir deste diretório:

```text
rtk .\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute TCC_experimentos.ipynb --output TCC_experimentos_executado.ipynb --ExecutePreprocessor.timeout=600
```

O notebook usa a constante `RUN_PROFILE = "validation"` por padrão. Os outros
perfis documentados têm guards explícitos e não são ativados nesta rodada. As
variáveis opcionais `PEQUIFLUX_RUNS_ROOT` e `PEQUIFLUX_RESULTS_ROOT` apenas
alteram as raízes de saída. Elas não selecionam perfil, não procuram o run mais
recente e não ativam uma rota alternativa.

## Perfis

- `validation`: duas sementes, cenário mínimo e as cinco políticas; produz
  manifesto, resultados, logs, replay, auditoria e `table_audit.csv`. É
  evidência de engenharia, com fixtures materializadas explicitamente por
  `build_validation_inputs` e consumidas por `run_validation_matrix`.
- `pilot`: 15 cenários pré-especificados, 50 sementes e cinco políticas (3.750
  células), em namespace próprio. O executor exige dataset congelado, aprovação
  de face e recibo de capacidade vigente antes de criar o namespace.
- `load-confirmatory`: carrega somente o namespace identificado por
  `CONFIRMATORY_RUN_ID`, definido explicitamente na célula de identificação.
  ID ausente ou inexistente falha claramente. O pacote carregado é reauditado
  integralmente por `audit_run`; se qualquer artefato persistido estiver
  ausente, inconsistente ou fora do namespace, a auditoria falha sem fallback.
  Após a auditoria, `evaluate_h1` recebe diretamente o `RunBundle` persistido;
  a API valida a grade canônica, deriva os estratos medium/high e
  `export_analysis` regenera as tabelas e figuras em `PEQUIFLUX_RESULTS_ROOT`.
  Não há descoberta de resultado mais recente nem fallback para execução.
- `execute-confirmatory`: reservado à matriz confirmatória completa, após gates
  de protocolo e capacidade no núcleo da API. Exige exatamente 18.000 células,
  dataset congelado validado, aprovação de face e recibo de capacidade vigente.

`run_experiment_matrix` recebe `dataset_path`, `expected_dataset_root_hash`,
`controls`, `face_receipt_path` e `capacity_receipt`. O hash externo fixa a
origem; o executor revalida os seis payloads e usa suas instâncias no
`run_day(instance, policy, controls, event_latents)`. Não há geração interna
no DES. Resultados e logs registram os hashes da instância original, da projeção
executada, dos controles e do dataset. O esquema de resultados/logs é versão 3;
artefatos antigos precisam ser identificados como antigos, sem converter sua
proveniência em consumo de entradas congeladas.

Para preparar uma execução científica, carregue o dataset com
`dataset.load_frozen_dataset(path, expected_dataset_root_hash=pin)`, construa
`ExecutionControls.build(ordinary_window=6, buffer_capacity=12,
threshold_multiplier=Decimal('1.00'), intensity='base',
source_dataset_root_hash=pin, event_latents_sha256=dataset.event_latents.event_latents_sha256)`
e use `ConfirmatoryWorkload.from_dataset(dataset, CONFIG, phase=RUN_PROFILE)`.
`inspect_capacity(workload, CONFIG.capacity, RUNS_ROOT)` persiste a inspeção;
seu objeto de retorno preenche `CAPACITY_RECEIPT` no notebook. O executor
revalida o recibo imediatamente antes do namespace: TTL de 60 segundos,
hashes, processo, dependências, RAM, disco e concorrência devem continuar
válidos. A inspeção é uma estimativa de capacidade, não uma medição da campanha.

Os caminhos e controles científicos são explícitos na célula inicial do
notebook. Sem evidência válida, a chamada falha no executor também quando
feita fora do notebook. Aprovações humanas pendentes não são preenchidas
automaticamente. Fixtures, piloto e instalação limpa não comprovam a campanha
confirmatória nem autorizam conclusões de H1.

Não há seleção de perfil por variável de ambiente ou por descoberta de arquivos.
Cada execução canônica deve receber uma `PEQUIFLUX_RESULTS_ROOT` nova e vazia;
uma colisão no mesmo namespace é erro fail-closed, não idempotência. O cwd
canônico é `experimento-notebook/`, de onde o notebook resolve `src/` e `config/`.

## Escopo dos dados sintéticos

O [escopo fechado](docs/synthetic-data-scope.md) conserva as quatro operações,
o fatorial, as chaves CRN e os seis payloads. O
[catálogo de entradas](docs/synthetic-input-catalog.md) explicita unidades,
valores, origem, justificativa e limites das hipóteses. As 432.000 linhas de
caminhões e 1.728.000 durações são quantidades previstas, não evidência de uma
geração executada. Planos, fixtures e resultados principais têm estados distintos.

## Layout de artefatos

```text
experimento-notebook/
├── TCC_experimentos.ipynb
├── README.md
├── config/confirmatory.json
├── src/pequiflux_experiment/
├── tests/
├── runs/
│   └── <run_id>/{manifest.json,results.csv,logs/*.jsonl,audit.json}
└── results/
    ├── raw/
    ├── processed/
    ├── tables/table_audit.csv
    └── figures/
```

Cada run recebe uma pasta nova; colisão de namespace interrompe a operação.
Logs completos ficam em `runs/<run_id>/logs/`. A tabela de auditoria da
validação é produzida por `export_audit_table(audit_json_path, output_path)`,
que lê exclusivamente o `audit.json` persistido, valida campos e estado, e
publica o CSV atomicamente sem sobrescrever colisões. Tabelas estatísticas,
Parquet e figuras de H1 só podem ser regenerados por `export_analysis` a partir
de uma grade confirmatória persistida e auditada.

## Fronteiras científicas

O esquema de execução 4 deriva `results.csv` exclusivamente de logs já
persistidos por `compute_policy_day_metrics`. Cada dia inclui `metrics/*.json`
com SHA-256, definições e detalhes por recurso/caminhão; a auditoria reconstrói
todos os valores por implementação independente e os reconcilia. `DayResult`
contém eventos e estado, sem métricas. `scale_occupancy_peak` mede ocupação simultânea.
Utilização bruta/líquida e ociosidade são temporais, com paradas sobrepostas
contadas uma vez. Espera, tempo total e censura, estabilidade entre filas,
quebras de FIFO, comandos e intervenções também são derivados dos eventos.
Throughput é a contagem concluída até 720 minutos; `throughput_per_hour` divide
por 12 horas. `observed_makespan_minutes` termina na última conclusão de qualquer
etapa observada, sem estimar o atendimento da fila remanescente.
CO2 é exploratório: espera elegível acumulada em horas × fração de motor ligado
assumida em 1,0 × 0,8 galão americano/h × 10,18 kg/galão americano. Os cenários de
0,5 e 1,0 galão americano/h são hipóteses, não limites de emissões medidas.
As definições, unidades, populações, janelas e fontes constam no
[contrato das métricas](docs/canonical-metrics.md) e no catálogo de cada `MetricRow`.

`export_metrics` publica `table_metrics.csv`, `table_metric_catalog.csv`,
`table_metric_assumptions.csv`, detalhes por recurso e caminhão,
agregados por classe e médias aritméticas de dias por cenário/estrato
(`_day_mean`). As utilizações agregadas (`_pooled`) dividem somas de
recurso-minutos, preservando a ponderação por capacidade. `export_analysis` inclui
essas tabelas na publicação confirmatória. Na validação, os dados descritivos
são de fixtures e ficam em `descriptive_metrics/`. Valores ausentes ou
indefinidos interrompem a derivação; não recebem zero ou NaN.

A matriz científica usa `operator_mode=synthetic_auto_accept`; `operator_decision` no log
não representa uma pessoa. `overall_pass` cobre somente verificações
automáticas, e `global_acceptance_status` permanece `pending`. O executor
não transforma `human_audit_status` em `complete`. A aprovação real de face,
a revisão humana de A2 e o consumidor Unreal continuam pendentes.
`run_synthetic_operator_trial` exercita aceitar, rejeitar e override admissível
em instâncias de validação, com origem simulada explícita e replay de JSONL.
Esses ensaios não integram a campanha nem demonstram participação humana.
Veja [governança](docs/governance-status.md).

Os intervalos pareados usam 5.000 reamostragens e registram a quantidade.
A matriz RHFS e seus hashes estão em `../data/`; a análise auxiliar é uma
âncora exploratória de um Wilcoxon isolado, sem comprovar poder da regra
completa de H1. Veja [proveniência](../data/power_analysis_provenance.md).

O artefato é chamado de **modelo digital**. Não há ativo físico individual
pareado, telemetria contínua ou sincronização bidirecional operacional; portanto
“gêmeo digital” não é uma conclusão válida. H1 continua sendo uma hipótese
comparativa confirmatória. A1 e A2 são critérios de aceitação do artefato, e a
equivalência de replay é somente um diagnóstico de engenharia, não um novo A3.

A fase `validation` não preenche observações ausentes, não fabrica uma decisão
de H1 e não pode ser apresentada como campanha confirmatória. Resultados
observados, quando autorizados, devem permanecer ligados ao manifesto, ao hash
de configuração, à grade pareada, aos logs e à auditoria correspondente.

## Estado deste checkout

No preflight inicial de 2026-09-02, `nbformat`, `nbclient` e `nbconvert` estavam
ausentes e a gate top-to-bottom ficou `BLOCKED` até a instalação deliberada.
Depois, o ambiente `.venv` foi instalado pelo `requirements.lock`, incluindo
`ipykernel==7.3.0`; o gate canônico passou com `2 passed` em 54,76 s. O warning
de IDs ausentes do nbformat foi corrigido nesta rodada. Permanece somente o
warning ambiental residual do ZMQ no Windows; ele não indica erro do notebook.
