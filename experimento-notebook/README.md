# PequiFlux — experimento central do TCC

O [TCC_experimentos.ipynb](TCC_experimentos.ipynb) é o ponto operacional único:
plano, geração/congelamento, piloto completo, principal, auditoria, H1, estresse,
políticas exploratórias, tabelas e pendências. Não contém testes, demonstrações
reduzidas ou fallback para amostras.

## Protocolo vigente

A [emenda prospectiva v2](docs/protocol-v2-amendment.md), autorizada em
24/09/2026 antes das campanhas científicas, define uma comparação computacional
com dados sintéticos. Parâmetros são hipóteses de engenharia. Face e avaliação
humana são NOT_EVALUATED, fora dos requisitos v2; não foram aprovadas.
A1 verifica restrições modeladas e A2 verifica rastreabilidade/reconstruibilidade
automatizadas. Nenhum resultado estabelece validade operacional externa.

H1, CRN, cenários, sementes, painel principal, IUT/Holm, hashes e capacidade
permanecem preservados. A configuração v1 e seu recibo real pendente continuam
nos arquivos históricos; o carregador de datasets usa a versão vigente.

## Windows nativo com uv

Em PowerShell, dentro desta pasta:

```powershell
uv sync --locked
uv run --locked python -m ipykernel install --sys-prefix --name python3 --display-name "PequiFlux (Python 3.13.3)"
uv run --locked python tools/execute_notebook.py
```

CPython 3.13.3 e os 64 pins de `requirements.lock` são preservados por
`uv.lock` e pelas constraints de `pyproject.toml`. O grupo `provenance`
instala setuptools, exigido pelo recibo. `ipykernel` fornece o kernel nativo local.
O notebook não instala dependências. Pode iniciar na raiz do TCC ou nesta pasta.

O executor roda todas as células em ordem, com sete dias de limite por célula,
e salva outputs no próprio notebook inclusive quando uma falha o interrompe.
Não gera outro notebook e não aceita perfil reduzido. Falhas permanecem falhas,
não há continuação automática após erro. Os testes de software ficam fora:

```powershell
uv run --locked pytest -q
```

## Campanha integral

| Fase | Policy-days |
| --- | ---: |
| Piloto prescrito (15 cenários, 50 sementes, 5 políticas) | 3.750 |
| Principal (72 cenários, 50 sementes, 5 políticas) | 18.000 |
| Estresse (54 controles, 72 cenários, 50 sementes, 4 políticas) | 777.600 |
| Exploratório (72 cenários, 50 sementes, 3 políticas) | 10.800 |
| Total | 810.150 |

O piloto relata ganhos pareados por estrato, IQR e IC95%, sem tuning.
Somente o principal entra em H1. Estresse exige ganho e guarda de throughput
positivos contra os três comparadores simultaneamente em pelo menos 75% das
54 células completas. Incompletude é INVALID_INPUT, nunca NON_ROBUST.

O painel exploratório implementa slack previsto, janela sem estabilidade e
agrupamento por última carga servida no recurso, com controles base e
análise descritiva. CO₂ continua exploratório, com a faixa 0,5–1,0 galão/h
já incluída nas métricas. Nenhum vencedor exploratório é promovido a H1.

## Entradas e armazenamento

O padrão `DATASET_ACTION="generate"` usa um destino novo e gera todas as
3.600 instâncias. Para `"load"`, informe caminho e SHA-256 externo explícitos.
O notebook não infere o pin lendo o próprio dataset. Rejeições estruturais
preservam staging e exigem a ação explícita de reamostragem do contrato.

`PEQUIFLUX_RUNS_ROOT` e `PEQUIFLUX_RESULTS_ROOT` redirecionam saídas para
armazenamento local suficiente. A raiz de resultados deve ser inexistente;
por padrão é `results/<sessão>/`. Nenhuma evidência anterior é sobrescrita.

Em 24/09/2026, o único volume tinha cerca de 42 GiB livres. O gate principal
exige **pelo menos 87,4 GiB**, ainda sem dataset. A campanha integral continua
bloqueada por espaço; o estresse requer espaço adicional muito maior para
retenção. O notebook mede novamente o destino e salva `storage.json`.
Pela fórmula vigente, as quatro fases somam 3.186.622.464.000 bytes estimados
de saídas, antes dos datasets e das margens: aproximadamente 3,19 TB decimais.
Isso é estimativa do protocolo, não volume medido de uma campanha realizada.
Essa antecipação é somente a condição necessária do gate existente; cada fase
ainda exige inspeção atual, no mesmo processo, com TTL de 60 segundos.
Não se reduz a campanha, elimina logs ou altera margens para fazê-la caber.

## Evidência e pendências

Cada namespace em `runs/` retém manifesto, resultados, logs JSONL, métricas
e auditoria. `results/<sessão>/` reúne identidade documental, registros de
capacidade, tabelas e resumo. As implementações reutilizáveis ficam em
`src/pequiflux_experiment/`; a execução e interpretação permanecem no notebook.

O código das fases adicionais tem verificações de software, mas a campanha
integral e seu replay permanecem **não executados** por capacidade. Não há
métricas científicas finais. A cena Unreal, integração técnica do replay e
redação de resultados/discussão também permanecem pendentes. H1 negativa pode
concluir uma pesquisa; ausência de resultados não pode.

Fontes canônicas: [main.tex](../main.tex), [governança](docs/governance-status.md),
[catálogo sintético](docs/synthetic-input-catalog.md) e
[especificação técnica](docs/superpowers/specs/2026-09-02-notebook-experimental-completo-design.md),
com os requisitos humanos substituídos pela emenda v2.
