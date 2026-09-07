# Notebook de experimentos PequiFlux

Este diretório contém a interface linear para a validação do modelo digital do
despacho online de caminhões. O notebook [TCC_experimentos.ipynb](TCC_experimentos.ipynb)
orquestra as APIs públicas de `pequiflux_experiment`; as regras permanecem nos
módulos em `src/`.

## Ambiente deliberado

O projeto requer Python 3.12 ou superior: os pins de NumPy e SciPy no lock
exigem esse mínimo. O interpretador escolhido para a instalação local é
CPython 3.13.3 (Windows x64). O `pyproject.toml` declara as
dependências com intervalos de versão; `requirements.lock` fixa as versões
aprovadas para o experimento. Prepare o ambiente isolado com o lock:

```text
rtk proxy py -3.13 --version
rtk proxy py -3.13 -m venv .venv
rtk proxy .\.venv\Scripts\python.exe -m pip install -r requirements.lock
rtk proxy .\.venv\Scripts\python.exe -m pip check
rtk proxy .\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name python3 --display-name "PequiFlux (Python 3.13)"
```

`requirements.lock` reproduz as versões exatas do ambiente validado e já inclui
o pacote local como `-e .`. O lock inclui `numpy`, `pandas`, `scipy`, `pyarrow`,
`matplotlib`, `pytest`, `nbformat`, `nbclient`, `nbconvert` e todas as transitivas
instaladas. `ipykernel` fornece o kernel nativo local usado pela execução do
notebook. Não substitua o lock por uma instalação solta com versões divergentes;
o notebook não instala dependências durante a execução.

## Testes

No diretório `experimento-notebook/`, o comando de teste é:

```text
rtk .\.venv\Scripts\python.exe -m pytest -q
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
executada, dos controles e do dataset. O esquema de resultados/logs é versão 2;
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
