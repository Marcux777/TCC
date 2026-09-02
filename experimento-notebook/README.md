# Notebook de experimentos PequiFlux

Este diretório contém a interface linear para a validação do modelo digital do
despacho online de caminhões. O notebook [TCC_experimentos.ipynb](TCC_experimentos.ipynb)
orquestra as APIs públicas de `pequiflux_experiment`; as regras permanecem nos
módulos em `src/`.

## Ambiente deliberado

O projeto requer Python 3.11 ou superior. O `pyproject.toml` não instala
dependências automaticamente. Em um ambiente isolado, a instalação é uma ação
deliberada do operador e deve ser feita uma única vez, com a versão aprovada
para o experimento:

```text
rtk py -3 -m venv .venv
rtk .\.venv\Scripts\python.exe -m pip install -r requirements.lock
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
Quando `nbformat`, `nbclient` e `nbconvert` estão disponíveis, o mesmo teste
executa o notebook inteiro em uma raiz temporária e exige zero outputs de erro e
`results/tables/table_audit.csv`. Se algum desses três módulos estiver ausente,
o teste falha explicitamente com `BLOCKED execution gate`; isso não é convertido
em `skip` ou em sucesso.

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
  evidência de engenharia e é o valor fixo de `RUN_PROFILE` nesta rodada.
- `pilot`: amostra piloto pré-especificada em namespace próprio. O notebook
  expõe um bloqueador porque os pré-requisitos de piloto e a gate de capacidade
  ainda não estão materializados.
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
  de protocolo e capacidade. Nenhuma campanha confirmatória é executada nesta
  rodada; o notebook expõe o bloqueador desses gates.

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
